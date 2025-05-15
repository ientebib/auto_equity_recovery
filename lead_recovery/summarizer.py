"""summarizer.py
Conversation summarisation using OpenAI ChatCompletion with retries.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime  # Added for datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import pytz  # Added for timezone
import tiktoken
from openai import APIError as OpenAI_APIError
from openai import AsyncOpenAI, OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, wait_random

from .cache import SummaryCache, compute_conversation_digest  # Import cache utilities
from .config import settings
from .exceptions import ApiError, ValidationError  # Import custom errors

logger = logging.getLogger(__name__)

class ConversationSummarizer:
    """Generate text summary for a single conversation DataFrame."""

    def __init__(
        self,
        model: str = "o4-mini",
        max_tokens: int = 4096,
        prompt_template_path: str | Path | None = None,
        use_cache: bool = True,
        cache_dir: Path | None = None,
        meta_config: Optional[Dict[str, Any]] = None # Add meta_config
    ):
        """Create a new summarizer instance.

        Args:
            model: OpenAI chat model to use.
            max_tokens: Max response tokens.
            prompt_template_path: Optional path to a *recipe‑specific* prompt
                template. If ``None`` (default), it falls back to the original
                global prompt shipped under ``lead_recovery/prompts``.
            use_cache: Whether to use the summary cache to avoid redundant API calls.
            cache_dir: Directory to store the cache database. If None, uses default.
            meta_config: Parsed content of the recipe's meta.yml file.
        """
        logger.debug(f"ConversationSummarizer.__init__ received use_cache={use_cache} (type: {type(use_cache)})")
        # Check for API key
        if not settings.OPENAI_API_KEY:
            raise ApiError("OPENAI_API_KEY is not set in environment or .env file")
            
        self._client = OpenAI(api_key=settings.OPENAI_API_KEY)
        # Allow model override from meta_config
        self.model = meta_config.get("model_name", model) if meta_config else model
        logger.info(f"Using model: {self.model}")
        self.max_tokens = max_tokens
        self.meta_config = meta_config if meta_config else {}
        
        # Store metadata needed for yaml parsing, but NOT for validation
        self.yaml_terminator_key = self.meta_config.get('yaml_terminator_key', 'suggested_message_es:')
        
        self._prompt_template_path = None # Store the path for potential later use
        self._recipe_name = Path(prompt_template_path).parent.name if prompt_template_path else None # Store recipe name
        
        # Initialize cache if enabled
        self.use_cache = use_cache
        self._cache = SummaryCache(cache_dir) if use_cache else None
        logger.debug(f"ConversationSummarizer.__init__ set self.use_cache={self.use_cache} (type: {type(self.use_cache)}), self._cache is {'None' if self._cache is None else 'initialized'}")

        # Initialize tiktoken encoding based on model
        try:
            self.encoding = tiktoken.encoding_for_model(self.model)
        except KeyError:
            # Fallback for models not directly supported by tiktoken
            self.encoding = tiktoken.get_encoding("cl100k_base")
            logger.warning(f"Model {self.model} not found in tiktoken, using cl100k_base encoding as fallback")

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
            self._prompt_template_path = prompt_path # Store the path

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

        # Initialize Async Client
        self._async_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    # ------------------------------------------------------------------ #
    def estimate_tokens(self, messages: List[Dict[str, str]]) -> int:
        """Estimate token count for messages using tiktoken.
        
        Args:
            messages: List of message dictionaries with 'content' key
            
        Returns:
            Estimated token count
        """
        # Count tokens for each message content
        token_count = 0
        for msg in messages:
            # Add tokens for the message content
            content = msg.get("content", "")
            tokens = self.encoding.encode(content)
            token_count += len(tokens)
            
            # Add a small constant for message format overhead
            # This accounts for role, formatting, etc.
            token_count += 4  # Conservative overhead per message
        
        # Add a constant for the response format overhead
        token_count += 3
        
        return token_count
    
    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10) + wait_random(0, 2), # Added jitter (0-2 seconds)
        stop=stop_after_attempt(3)
    )
    async def _call_openai(self, messages: List[Dict[str, str]]) -> str:
        """Internal helper wrapped with exponential backoff retry."""
        # Note: Using o4-mini model which uses the Responses API.
        target_model = self.model
        reasoning_effort = "low"

        # Use tiktoken for accurate token estimation
        num_tokens = self.estimate_tokens(messages)
        logger.debug(
            "Estimating input tokens for %s using tiktoken: %d tokens",
            target_model, num_tokens
        )

        try:
            start_time = time.time()
            # Check if model name suggests it's a Responses API model (o4-*)
            if target_model.startswith("o4-"):
                logger.debug("Using Responses API for model %s", target_model)
                # Try Responses API first
                try:
                    # Use the Responses API
                    response = await self._async_client.responses.create(
                        model=target_model,
                        input=messages,
                        reasoning={"effort": reasoning_effort},
                        # Pass the existing max_tokens as max_output_tokens.
                        # WARNING: This includes reasoning tokens AND output tokens.
                        # If reasoning uses many tokens, visible output might be truncated.
                        # Consider increasing this value if summaries are incomplete.
                        # Use the max_tokens defined in the instance (default 4096)
                        max_output_tokens=self.max_tokens,
                        timeout=60.0, # Added 60 second timeout
                        # store=False # Optional: Set to False if you don't need state for follow-ups
                    )
                    
                    # Extract content from output_text for Responses API
                    if response.status != "completed":
                        raise ApiError(f"OpenAI API call failed with status: {response.status}")
                    
                    content = response.output_text.strip()
                    
                    # Log token usage information from the response object
                    try:
                        input_tokens = response.usage.input_tokens
                        output_tokens = response.usage.output_tokens
                        reasoning_tokens = response.usage.output_tokens_details.reasoning_tokens
                        visible_output_tokens = output_tokens - reasoning_tokens
                        
                        logger.debug(
                            "OpenAI usage - Input: %d tokens, Output: %d tokens (Reasoning: %d, Visible: %d). Duration: %.2fs",
                            input_tokens, output_tokens, reasoning_tokens, visible_output_tokens, 
                            time.time() - start_time
                        )
                    except (AttributeError, KeyError) as e:
                        logger.warning(f"Could not extract detailed token usage from response: {e}")
                    
                except Exception as responses_error:
                    logger.warning(f"Responses API call failed for model {target_model}: {responses_error}. Falling back to Chat Completions API.")
                    # Fall back to Chat Completions API
                    fallback_model = "gpt-4o" if "mini" not in target_model else "gpt-4.1-mini"
                    logger.info(f"Falling back to model {fallback_model} with Chat Completions API")
                    response = await self._async_client.chat.completions.create(
                        model=fallback_model,
                        messages=messages,
                        max_tokens=self.max_tokens,
                        timeout=60.0
                    )
                    content = response.choices[0].message.content.strip()
                    
                    # Log token usage for fallback
                    try:
                        logger.debug(
                            "OpenAI fallback usage - Input: %d tokens, Output: %d tokens. Duration: %.2fs",
                            response.usage.prompt_tokens, response.usage.completion_tokens,
                            time.time() - start_time
                        )
                    except (AttributeError, KeyError) as e:
                        logger.warning(f"Could not extract token usage from fallback response: {e}")
            else:
                # For non-o4 models, use Chat Completions API directly
                logger.debug("Using Chat Completions API for model %s", target_model)
                response = await self._async_client.chat.completions.create(
                    model=target_model,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    timeout=60.0
                )
                content = response.choices[0].message.content.strip()
                
                # Log token usage
                try:
                    logger.debug(
                        "OpenAI usage - Input: %d tokens, Output: %d tokens. Duration: %.2fs",
                        response.usage.prompt_tokens, response.usage.completion_tokens,
                        time.time() - start_time
                    )
                except (AttributeError, KeyError) as e:
                    logger.warning(f"Could not extract token usage from response: {e}")
            
            time.time() - start_time
            
            if not content:
                logger.error("OpenAI response was empty despite status 'completed'")
                raise ApiError("OpenAI returned empty response with status 'completed'")
    
            return content
    
        except OpenAI_APIError as e:
            logger.error("OpenAI API Error: %s", e)
            # Re-wrap as our ApiError with original error message
            raise ApiError(f"OpenAI API Error: {e}")
        except Exception as e:
            logger.error("Unexpected error in OpenAI call: %s", e, exc_info=True)
            # Re-wrap as our ApiError
            raise ApiError(f"Unexpected error in OpenAI call: {e}")

    async def summarize(self, conv_df: pd.DataFrame, temporal_flags: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generates a summary by calling the LLM and returning the basic parsed result.
        
        Args:
            conv_df: DataFrame containing conversation messages for a single lead.
                     Expected columns: 'creation_time', 'msg_from', 'message'.
            temporal_flags: Comprehensive dictionary containing all Python-calculated flags
                            (including temporal, metadata, state, and other specific flags).

        Returns:
            A dictionary containing the parsed YAML from the LLM response.
            Does not perform validation against expected keys or enums - that's the caller's responsibility.
        """
        try:
            # Format conversation text 
            conversation_text = "\\n".join(
                f"[{str(getattr(row, 'creation_time', 'Unknown Time'))[:19]}] {getattr(row, 'msg_from', 'Unknown Sender')}: {getattr(row, 'message', 'No Message')}"
                for row in conv_df.itertuples(index=False)
            )

            # Compute digest for caching
            conversation_digest = compute_conversation_digest(conversation_text)
            
            # Basic timestamp calculations for prompt formatting if needed
            now_cdmx = datetime.now(pytz.timezone('America/Mexico_City'))
            hoy_es_cdmx = now_cdmx.isoformat()
            last_ts = None
            delta_min = float('inf')
            delta_real_time_hrs = float('inf')
            delta_real_time_formateado = "N/A"
            last_query_timestamp = 'N/A'
            
            # Get basic timestamp info from conversation data if available
            if not conv_df.empty and 'creation_time' in conv_df.columns:
                try:
                    creation_times = pd.to_datetime(conv_df['creation_time'], errors='coerce')
                    max_time = creation_times.max()
                    if pd.notna(max_time):
                        if max_time.tzinfo is None:
                             max_time = max_time.tz_localize('UTC') 
                        last_ts = max_time
                        last_query_timestamp = last_ts.isoformat()
                        # Calculate delta in minutes and hours
                        delta = now_cdmx - last_ts
                        delta_min = delta.total_seconds() / 60
                        delta_real_time_hrs = delta_min / 60

                        # Create formatted string
                        if delta_real_time_hrs < 1.0:
                            delta_real_time_formateado = f"{delta_min:.0f} min"
                        elif delta_real_time_hrs < 48.0:
                            delta_real_time_formateado = f"{delta_real_time_hrs:.1f} h"
                        else:
                            delta_real_time_formateado = f"{delta_real_time_hrs / 24:.1f} días"
                except Exception as e_time:
                     logger.warning(f"Error processing creation_time in conv_df: {e_time}")
            
            # Check cache first if enabled
            if self.use_cache and self._cache:
                cached_summary = self._cache.get(conversation_digest, self.model)
                if cached_summary is not None:
                    logger.info(f"Using cached summary for conversation digest: {conversation_digest[:8]}...")
                    # Add cache helper fields if not present
                    if "conversation_digest" not in cached_summary:
                        cached_summary["conversation_digest"] = conversation_digest
                    if "last_message_ts" not in cached_summary:
                        cached_summary["last_message_ts"] = last_query_timestamp
                    return cached_summary

            # Format the prompt
            try:
                # Create format args dictionary
                format_args = {
                    "conversation_text": conversation_text,
                    "HOY_ES": hoy_es_cdmx,
                    "LAST_QUERY_TIMESTAMP": last_query_timestamp,
                    "delta_min": delta_min, 
                    "delta_real_time_formateado": delta_real_time_formateado
                }
                
                # Add all Python-calculated flags to format_args
                if temporal_flags:
                    logger.debug(f"Adding all flags from temporal_flags to format_args. Keys: {sorted(list(temporal_flags.keys()))}")
                    format_args.update(temporal_flags)
                else:
                    logger.warning("temporal_flags dictionary is None or empty. Prompt might be missing expected keys for formatting.")
                
                # Format the prompt with all arguments
                prompt = self.prompt_template.format(**format_args)
                
            except KeyError as e:
                error_msg = f"Prompt template {self._prompt_template_path} missing expected format key: {e}"
                logger.error(error_msg)
                raise ValidationError(error_msg) from e
            except Exception as format_e:
                error_msg = f"Error formatting prompt template {self._prompt_template_path}: {format_e}"
                logger.error(error_msg, exc_info=True)
                raise ValidationError(error_msg) from format_e

            # Call OpenAI API
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful customer‑support summarisation bot that responds ONLY in valid YAML format as requested.",
                },
                {"role": "user", "content": prompt},
            ]
            
            # First attempt with standard system prompt
            raw_summary_text = await self._call_openai(messages)

            # Import helpers here to avoid circular imports
            from .summarizer_helpers import clean_response_text, parse_yaml_dict

            # Try to parse the response
            try:
                cleaned_text = clean_response_text(raw_summary_text, yaml_terminator_key=self.yaml_terminator_key)
                parsed_data = parse_yaml_dict(cleaned_text)
            except ValueError as e:
                # First parsing attempt failed, try again with a more explicit system prompt
                logger.warning(f"First YAML parsing attempt failed: {e}. Trying with a more explicit system prompt...")
                
                # Second attempt with more explicit system prompt about YAML format
                messages[0]["content"] = """You are a strict YAML generator. Follow these rules exactly:
1. Respond ONLY with valid YAML data, nothing else
2. Each field should be on its own line with format 'key: value'
3. For multi-line values, use proper YAML indentation (2 spaces)
4. Always quote strings containing colons or special characters
5. Never use tabs, only spaces
6. Never include extra text before or after the YAML
7. Do not explain your reasoning, just output the YAML
"""
                try:
                    raw_summary_text = await self._call_openai(messages)
                    cleaned_text = clean_response_text(raw_summary_text, yaml_terminator_key=self.yaml_terminator_key)
                    parsed_data = parse_yaml_dict(cleaned_text)
                except ValueError as second_e:
                    logger.error(f"Both YAML parsing attempts failed. First error: {e}, Second error: {second_e}")
                    logger.error(f"Raw response from second attempt:\n{raw_summary_text[:500]}...")
                    raise ValidationError(f"Failed to parse YAML response after multiple attempts: {second_e}", 
                                         raw_response=raw_summary_text) from second_e
            
            # Successfully parsed - attach cache helper fields
            parsed_data["conversation_digest"] = conversation_digest
            parsed_data["last_message_ts"] = last_query_timestamp
            
            # Save to cache if enabled
            if self.use_cache and self._cache:
                try:
                    self._cache.set(conversation_digest, parsed_data, self.model)
                    logger.debug(f"Saved summary to cache with digest: {conversation_digest[:8]}...")
                except Exception as e:
                    logger.warning(f"Failed to save summary to cache: {e}", exc_info=True)
            
            return parsed_data

        except (ApiError, ValidationError):
            # Let these specific exceptions propagate
            raise
        except Exception as e:  # Catch other unexpected errors
            logger.exception("Failed to summarise conversation: %s", e)
            # Wrap unknown errors - using 'from e' to preserve the original stack trace
            raise ApiError(f"Unexpected error during summarization: {e}") from e