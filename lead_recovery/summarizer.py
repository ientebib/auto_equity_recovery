"""summarizer.py
Conversation summarisation using OpenAI ChatCompletion with retries.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List
import yaml

import pandas as pd
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from pathlib import Path
import tiktoken

from .config import settings

logger = logging.getLogger(__name__)


class ConversationSummarizer:
    """Generate text summary for a single conversation DataFrame."""

    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        max_tokens: int = 4096,
        prompt_template_path: str | Path | None = None,
        expected_yaml_keys: List[str] | None = None,
    ):
        """Create a new summarizer instance.

        Args:
            model: OpenAI chat model to use.
            max_tokens: Max response tokens.
            prompt_template_path: Optional path to a *recipe‑specific* prompt
                template. If ``None`` (default), it falls back to the original
                global prompt shipped under ``lead_recovery/prompts``.
            expected_yaml_keys: List of keys expected in the YAML output for validation.
                If None, validation is skipped.
        """

        self._client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = model
        self.max_tokens = max_tokens
        self.expected_yaml_keys = set(expected_yaml_keys) if expected_yaml_keys else None
        
        # Resolve prompt template file ------------------------------------ #
        default_prompt_path = Path(__file__).parent / "prompts" / "openai_prompt.txt"
        
        if prompt_template_path is None:
            # Use the default prompt if no specific path is provided
            prompt_path = default_prompt_path
            logger.debug("No recipe-specific prompt provided, using default: %s", prompt_path)
        else:
            # Use the path provided by the recipe/user
            prompt_path = Path(prompt_template_path)
            logger.debug("Using recipe-specific prompt: %s", prompt_path)

        # Attempt to load the selected prompt file
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.prompt_template = f.read()
            logger.info("Successfully loaded prompt template from %s", prompt_path)
        except FileNotFoundError:
            logger.error("Prompt template file not found at %s. A recipe must provide a prompt.txt or the default prompt must exist.", prompt_path)
            # Raise a clear error if the file doesn't exist
            raise FileNotFoundError(
                f"Could not find prompt template file at {prompt_path}. "
                f"Ensure the recipe specifies a valid 'prompt.txt' or that the default "
                f"prompt exists at {default_prompt_path}."
            )
        except Exception as e: # Catch other potential file reading errors
            logger.error("Failed to read prompt template file from %s: %s", prompt_path, str(e))
            # Re-raise the exception after logging
            raise e

    # ------------------------------------------------------------------ #
    @retry(wait=wait_exponential(multiplier=2, min=2, max=10), stop=stop_after_attempt(3))
    def _call_openai(self, messages: List[Dict[str, str]]) -> str:
        """Internal helper wrapped with exponential backoff retry."""
        # Note: Using o4-mini model which uses the Responses API.
        target_model = "o4-mini"
        reasoning_effort = "low"

        # Input token calculation might differ slightly for Responses API, but tiktoken is a good estimate.
        try:
            # Use a known base model for tiktoken if target_model isn't directly supported yet
            # (e.g., gpt-4 as a proxy for o4-mini's tokenizer behavior)
            encoding = tiktoken.encoding_for_model("gpt-4")
            num_tokens = sum(len(encoding.encode(msg["content"])) for msg in messages)
            logger.debug(
                "Estimating input tokens for %s using gpt-4 encoding: %d tokens",
                target_model, num_tokens
            )
        except Exception as e:
            logger.warning(
                "Could not get tiktoken encoding for base model (gpt-4). Falling back to word count. Error: %s", e
            )
            word_count = sum(len(msg["content"].split()) for msg in messages)
            logger.debug(
                "Calling OpenAI Responses API (model: %s) with ~%d words in prompt",
                target_model, word_count
            )

        start_time = time.time()
        # Use the Responses API
        response = self._client.responses.create(
            model=target_model,
            input=messages,
            reasoning={"effort": reasoning_effort},
            # Pass the existing max_tokens as max_output_tokens.
            # WARNING: This includes reasoning tokens AND output tokens.
            # If reasoning uses many tokens, visible output might be truncated.
            # Consider increasing this value if summaries are incomplete.
            max_output_tokens=self.max_tokens,
            # store=False # Optional: Set to False if you don't need state for follow-ups
        )
        duration = time.time() - start_time

        # Handle potential incomplete responses due to token limits
        if response.status == "incomplete" and response.incomplete_details.reason == "max_output_tokens":
            logger.warning(
                "OpenAI API call for model %s was incomplete due to max_output_tokens (%d). Reasoning might have consumed tokens. Duration: %.2fs",
                target_model, self.max_tokens, duration
            )
            # Return potentially partial text, or handle as an error depending on requirements
            content = response.output_text.strip() if response.output_text else ""
            if not content:
                 logger.error("Response was incomplete (max_output_tokens) and generated no visible output text.")
                 # Raise an exception or return an error string
                 raise RuntimeError("OpenAI response incomplete due to max_output_tokens with no visible output.")
            else:
                 logger.warning("Returning partial output due to incomplete response (max_output_tokens).")

        elif response.status != "completed":
             logger.error(
                 "OpenAI API call for model %s failed or was incomplete for reasons other than token limits. Status: %s. Duration: %.2fs",
                 target_model, response.status, duration
             )
             raise RuntimeError(f"OpenAI API call failed with status: {response.status}")
        else:
            # Extract content from output_text for Responses API
            content = response.output_text.strip()

        # Log token usage information from the response object
        try:
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            reasoning_tokens = response.usage.output_tokens_details.reasoning_tokens
            visible_output_tokens = output_tokens - reasoning_tokens

            logger.debug(
                "OpenAI API call completed in %.2f seconds. Usage: Input=%d, Output=%d (Reasoning=%d, Visible=%d), Total=%d",
                duration, input_tokens, output_tokens, reasoning_tokens, visible_output_tokens, response.usage.total_tokens
            )
        except AttributeError:
            logger.warning("Could not log detailed token usage (usage object might be missing or structured differently). Duration: %.2fs", duration)
        except Exception as e:
            logger.warning("Error logging token usage: %s. Duration: %.2fs", e, duration)


        return content

    # ------------------------------------------------------------------ #
    def summarize(self, conv_df: pd.DataFrame) -> Dict[str, Any]:
        """Generates a summary and parses it into a structured dictionary.
        
        Returns:
            A dictionary containing parsed fields: 'result', 'stall_reason',
            'key_interaction', 'suggestion', and the raw 'summary' text.
            Returns default error values if parsing fails.
        """
        default_error_result = {
            "result": "Error during summarization",
            "stall_reason": "OTHER",
            "key_interaction": "N/A",
            "suggestion": "Review conversation manually",
            "summary": "Failed to get or parse summary."
        }
        try:
            # Limit the conversation to avoid token limit issues
            # Taking first 5 and last 15 messages if more than 20 messages
            # if len(conv_df) > 20:
            #     first_n = min(5, len(conv_df))
            #     last_n = min(15, len(conv_df) - first_n)
            #     truncated_df = pd.concat([
            #         conv_df.head(first_n), 
            #         conv_df.tail(last_n)
            #     ])
            #     logger.debug("Truncated conversation from %d to %d messages", 
            #                len(conv_df), len(truncated_df))
            #     conv_df = truncated_df
            
            # Format the conversation
            conversation_text = "\\n".join(
                # Format: [YYYY-MM-DD HH:MM:SS] Sender: Message
                f"[{str(getattr(row, 'creation_time', 'Unknown Time'))[:19]}] {getattr(row, 'msg_from', 'Unknown Sender')}: {getattr(row, 'message', 'No Message')}"
                for row in conv_df.itertuples(index=False)
            )
            
            # Apply the custom prompt template
            prompt = self.prompt_template.format(conversation_text=conversation_text)
            
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful customer‑support summarisation bot that responds ONLY in valid YAML format as requested.",
                },
                {"role": "user", "content": prompt},
            ]
            raw_summary_text = self._call_openai(messages)

            # --- YAML Parsing ---
            try:
                # Clean potential markdown code blocks if present
                if raw_summary_text.startswith("```yaml"):
                    raw_summary_text = raw_summary_text.strip("```yaml").strip("```").strip()
                elif raw_summary_text.startswith("```"):
                    raw_summary_text = raw_summary_text.strip("```").strip()

                parsed_data = None # Initialize
                try:
                    parsed_data = yaml.safe_load(raw_summary_text)
                except yaml.YAMLError as e:
                    logger.error("YAML Parsing Error: %s\nRaw Response:\n%s", e, raw_summary_text)
                    result = default_error_result.copy()
                    result['summary'] = f"YAML Parsing Error: {e}. Raw: {raw_summary_text}" # Include error in summary
                    return result

                # Validate expected keys if they were provided
                if self.expected_yaml_keys:
                    if not isinstance(parsed_data, dict):
                        logger.error("Parsed data is not a dictionary (Type: %s). Raw Response:\n%s", 
                                   type(parsed_data).__name__, raw_summary_text)
                        result = default_error_result.copy()
                        result['summary'] = f"Parsed data not a dict (Type: {type(parsed_data).__name__}). Raw: {raw_summary_text}"
                        return result
                    
                    if not self.expected_yaml_keys.issubset(parsed_data.keys()):
                        missing_keys = self.expected_yaml_keys - set(parsed_data.keys())
                        extra_keys = set(parsed_data.keys()) - self.expected_yaml_keys
                        logger.error("Parsed YAML missing expected keys (Missing: %s, Extra: %s). Expected: %s. Got: %s. Raw Response:\n%s",
                                   missing_keys or 'None', extra_keys or 'None', self.expected_yaml_keys, 
                                   list(parsed_data.keys()), raw_summary_text)
                        result = default_error_result.copy()
                        result['summary'] = f"Parsed YAML key mismatch (Missing: {missing_keys}, Extra: {extra_keys}). Raw: {raw_summary_text}"
                        return result
                else:
                    # If no expected keys were provided, skip validation but log a warning
                    logger.warning("No expected_yaml_keys provided for validation. Skipping check.")
                    if not isinstance(parsed_data, dict):
                         logger.error("Parsed response is not a dictionary, despite skipping key validation. Response: %s", raw_summary_text)
                         result = default_error_result.copy()
                         result['summary'] = f"Parsed data not dict (validation skipped). Raw: {raw_summary_text}"
                         return result

                # Successfully parsed (or validation skipped) - return the parsed dictionary
                return parsed_data

            # Catch unexpected errors during the parsing/validation block
            except Exception as e:
                logger.error("Unexpected error during YAML processing: %s", e, exc_info=True) # Log with traceback
                result = default_error_result.copy()
                result['summary'] = f"Unexpected parsing error: {e}. Raw: {raw_summary_text}"
                return result

        except Exception as e:  # Catch errors from _call_openai or formatting
            logger.exception("Failed to summarise conversation: %s", e)
            # Return default error structure if any step fails
            return default_error_result 