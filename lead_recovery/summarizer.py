"""summarizer.py
Conversation summarisation using OpenAI ChatCompletion with retries.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional
import yaml
import re
import pandas as pd
from openai import OpenAI, AsyncOpenAI, APIError as OpenAI_APIError
from tenacity import retry, stop_after_attempt, wait_exponential, wait_random
from pathlib import Path
import pytz # Added for timezone
from datetime import datetime # Added for datetime
import hashlib
import tiktoken
import warnings

from .config import settings
from .exceptions import ApiError, ValidationError # Import custom errors
from .cache import SummaryCache, compute_conversation_digest # Import cache utilities

logger = logging.getLogger(__name__)

# Hardcoded enum values for 'simulation-to-handoff' specific validation (REMOVED - Now from meta.yml)
# SIMULATION_STALL_REASONS = { ... }
# SIMULATION_NEXT_ACTIONS = { ... }

class ConversationSummarizer:
    """Generate text summary for a single conversation DataFrame."""

    def __init__(
        self,
        model: str = "o4-mini",
        max_tokens: int = 4096,
        prompt_template_path: str | Path | None = None,
        # expected_yaml_keys: List[str] | None = None, # Now part of meta_config
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
            # expected_yaml_keys: List of keys expected in the YAML output for validation (deprecated, use meta_config).
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
        # self.expected_yaml_keys = set(expected_yaml_keys) if expected_yaml_keys else None # Now from meta_config
        self.meta_config = meta_config if meta_config else {}
        self.expected_yaml_keys = set(self.meta_config.get('expected_yaml_keys', []))
        self.validation_enums = self.meta_config.get('validation_enums', {})
        
        # Store the last key for cleanup from meta_config or use default
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
            
            duration = time.time() - start_time
            
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

    # ------------------------------------------------------------------ #
    def _validate_yaml(self, parsed_data: Dict[str, Any]) -> List[str]:
        """Validate parsed YAML data against expected keys and enums."""
        validation_errors = []
        actual_keys = set(parsed_data.keys())

        if self.expected_yaml_keys:
            missing_keys = self.expected_yaml_keys - actual_keys
            if missing_keys:
                validation_errors.append(f"Missing keys: {missing_keys}")
            
            extra_keys = actual_keys - self.expected_yaml_keys
            if extra_keys:
                logger.warning("Found extra keys in YAML output: %s", extra_keys)
        else:
            logger.warning("No expected_yaml_keys provided for validation. Skipping key check.")

        # Enum Value Validation - This part is already in the summarize method's auto-fixing logic
        # but can be duplicated here for a standalone validation check if needed, or kept centralized.
        # For now, focusing on key validation as that was the direct cause of the error.
        # Consider moving enum validation here if it makes the code cleaner.
        return validation_errors

    async def summarize(self, conv_df: pd.DataFrame, temporal_flags: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generates a summary and parses it into a structured dictionary.
        
        Args:
            conv_df: DataFrame containing conversation messages for a single lead.
                     Expected columns: 'creation_time', 'msg_from', 'message'.
            temporal_flags: Comprehensive dictionary containing all Python-calculated flags
                            (including temporal, metadata, state, and other specific flags).

        Returns:
            A dictionary containing parsed fields based on the prompt/recipe.
            Returns a dictionary with an 'error' key if parsing/validation fails.
        """
        # Define a standard way to return errors
        # Removed _create_error_result - will raise exceptions instead.

        try:
            # --- Prompt Formatting (Now done *before* calling summarize) ---
            # This section assumes the prompt template has already been loaded in __init__
            # and expects cli.py (or the caller) to format it using runtime args.
            
            # Calculate formatting args from conv_df if they weren't passed (fallback/direct use case)
            # This might need refinement depending on how cli.py passes info
            now_cdmx = datetime.now(pytz.timezone('America/Mexico_City'))
            hoy_es_cdmx = now_cdmx.isoformat()
            last_ts = None
            delta_min = float('inf') # Default to infinity if no last timestamp
            delta_real_time_hrs = float('inf') # Initialize hours delta
            delta_real_time_formateado = "N/A" # Initialize formatted string
            
            # --- Explicitly convert creation_time to datetime before finding max ---
            if not conv_df.empty and 'creation_time' in conv_df.columns:
                try:
                    creation_times = pd.to_datetime(conv_df['creation_time'], errors='coerce')
                    max_time = creation_times.max()
                    if pd.notna(max_time):
                        # Ensure max_time is timezone-aware (assume UTC if naive, adjust as needed)
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
                    else:
                        last_query_timestamp = 'N/A'
                except Exception as e_time:
                     logger.warning(f"Error processing creation_time in conv_df: {e_time}")
                     last_query_timestamp = 'N/A'
            else:
                 last_query_timestamp = 'N/A'
            # --- End conversion and delta calculation ---

            # Format conversation text
            conversation_text = "\\n".join(
                f"[{str(getattr(row, 'creation_time', 'Unknown Time'))[:19]}] {getattr(row, 'msg_from', 'Unknown Sender')}: {getattr(row, 'message', 'No Message')}"
                for row in conv_df.itertuples(index=False)
            )

            # Compute digest early for caching - use conversation text for stable hashing
            conversation_digest = compute_conversation_digest(conversation_text)
            
            # Check cache first if enabled
            logger.debug(f"ConversationSummarizer.summarize: Checking cache for digest {conversation_digest[:8]}... with self.use_cache={self.use_cache} (type: {type(self.use_cache)})")
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

            # Format the prompt using the template loaded in __init__
            try:
                 # Create format args dictionary. Start with locally calculated/static values.
                 format_args = {
                     "conversation_text": conversation_text,
                     "HOY_ES": hoy_es_cdmx,
                     "LAST_QUERY_TIMESTAMP": last_query_timestamp,
                     "delta_min": delta_min, 
                     "delta_real_time_formateado": delta_real_time_formateado
                     # Python-calculated flags will be added next from temporal_flags
                 }
                 
                 # Add all Python-calculated flags (passed via temporal_flags) to format_args
                 if temporal_flags:
                     # Log the flags being added to help with debugging
                     logger.debug(f"Adding all flags from temporal_flags to format_args. Keys: {sorted(list(temporal_flags.keys()))}")
                     format_args.update(temporal_flags)
                 else:
                     logger.warning("temporal_flags dictionary is None or empty. Prompt might be missing expected keys for formatting.")
                 
                 # Format the prompt with all arguments
                 prompt = self.prompt_template.format(**format_args)
                 
                 # Log a success message with the keys used in formatting
                 logger.debug(f"Successfully formatted prompt with keys: {sorted(format_args.keys())}")
            except KeyError as e:
                 # Handle cases where the prompt template might be missing expected placeholders
                 error_msg = f"Prompt template {self._prompt_template_path} missing expected format key: {e}"
                 logger.error(error_msg)
                 # Return error including the missing key information
                 # Raise ValidationError instead of returning error dict
                 raise ValidationError(error_msg) from e
            except Exception as format_e:
                 # Catch other formatting errors
                 error_msg = f"Error formatting prompt template {self._prompt_template_path}: {format_e}"
                 logger.error(error_msg, exc_info=True)
                 # Raise ValidationError instead of returning error dict
                 raise ValidationError(error_msg) from format_e

            # --- Call OpenAI API ---
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
                    # Both attempts failed, log the details and raise the exception
                    logger.error(f"Both YAML parsing attempts failed. First error: {e}, Second error: {second_e}")
                    logger.error(f"Raw response from second attempt:\n{raw_summary_text[:500]}...")
                    raise ValidationError(f"Failed to parse YAML response after multiple attempts: {second_e}", 
                                         raw_response=raw_summary_text) from second_e

            # --- Validation ---
            validation_errors = []

            # 1. Key Validation
            actual_keys = set(parsed_data.keys())
            if self.expected_yaml_keys:
                # Check for missing keys
                missing_keys = self.expected_yaml_keys - actual_keys
                extra_keys = actual_keys - self.expected_yaml_keys
                if missing_keys:
                    validation_errors.append(f"Missing keys: {missing_keys}")
                if extra_keys:
                     logger.warning("Found extra keys in YAML output: %s", extra_keys)
            else:
                logger.warning("No expected_yaml_keys provided for validation. Skipping key check.")

            # 3. Enum Value Validation (Conditional based on keys present in validation_enums and parsed_data)
            for enum_key, allowed_values_list in self.validation_enums.items():
                if enum_key in parsed_data:
                    value_to_check = parsed_data.get(enum_key)
                    allowed_values_set = set(allowed_values_list) # Convert list to set for efficient lookup
                    if value_to_check not in allowed_values_set:
                        validation_errors.append(f"Invalid value for '{enum_key}': '{value_to_check}'. Allowed: {allowed_values_set}")
            
            # --- Handle Validation Results ---
            if validation_errors:
                # Auto-fix invalid values
                warnings.warn(f"YAML Validation issues detected: {validation_errors}. Attempting to fix automatically.")
                
                # Special handling for cases where no user messages exist
                logger.info(f"CHECKING TEMPORAL_FLAGS: {temporal_flags}")
                if temporal_flags and temporal_flags.get('NO_USER_MESSAGES_EXIST', False):
                    logger.info(f"FOUND NO_USER_MESSAGES_EXIST=True in temporal_flags")
                    # If no user messages exist, always set these values regardless of LLM output
                    if 'primary_stall_reason_code' in parsed_data:
                        logger.warning(f"Auto-fixing primary_stall_reason_code to 'NUNCA_RESPONDIO' for conversation with NO_USER_MESSAGES_EXIST=True")
                        parsed_data['primary_stall_reason_code'] = 'NUNCA_RESPONDIO'
                    
                    if 'next_action_code' in parsed_data:
                        # Check how long since last message
                        hours_mins = temporal_flags.get('HOURS_MINUTES_SINCE_LAST_MESSAGE', '')
                        logger.info(f"HOURS_MINUTES_SINCE_LAST_MESSAGE = {hours_mins}")
                        if hours_mins and hours_mins.startswith(('0h', '1h')):
                            # If less than 2 hours, set to ESPERAR
                            logger.warning(f"Auto-fixing next_action_code to 'ESPERAR' for conversation with NO_USER_MESSAGES_EXIST=True and recent message")
                            parsed_data['next_action_code'] = 'ESPERAR'
                        else:
                            # Otherwise, call the lead
                            logger.warning(f"Auto-fixing next_action_code to 'LLAMAR_LEAD_NUNCA_RESPONDIO' for conversation with NO_USER_MESSAGES_EXIST=True")
                            parsed_data['next_action_code'] = 'LLAMAR_LEAD_NUNCA_RESPONDIO'
                else:
                    logger.info(f"NO_USER_MESSAGES_EXIST condition not met. temporal_flags: {temporal_flags}")
                    # Auto-fix missing keys by adding defaults
                    if self.expected_yaml_keys:
                        for key in self.expected_yaml_keys:
                            if key not in parsed_data:
                                parsed_data[key] = "N/A"  # Default placeholder for missing keys
                                logger.warning(f"Auto-fixing missing key \'{key}\' by setting to N/A")
                    
                    # Auto-fix invalid enum values
                    for enum_key, allowed_values_list in self.validation_enums.items():
                        if enum_key in parsed_data:
                            value = parsed_data.get(enum_key)
                            original_value_for_logging = str(value) # Keep original for logging/comparison

                            # 1. Attempt to strip common quotes and whitespace if value is a string
                            if isinstance(value, str):
                                stripped_value = value.strip() # Remove leading/trailing whitespace first
                                if stripped_value: # Ensure not an empty string after stripping whitespace
                                    if (stripped_value.startswith("'") and stripped_value.endswith("'")) or \
                                       (stripped_value.startswith('"') and stripped_value.endswith('"')):
                                        # Remove one layer of quotes
                                        stripped_value = stripped_value[1:-1]
                                
                                if value != stripped_value: # If stripping changed the value
                                     logger.info(f"Stripped quotes/whitespace from '{original_value_for_logging}' to '{stripped_value}' for key '{enum_key}'")
                                value = stripped_value # Use the potentially stripped value for further checks
                            
                            # 2. Check if (potentially stripped) value is valid
                            if value in allowed_values_list:
                                if parsed_data.get(enum_key) != value: # Update only if different from original in parsed_data
                                    logger.info(f"Corrected value for '{enum_key}' to (stripped and valid) '{value}' from '{original_value_for_logging}'")
                                    parsed_data[enum_key] = value
                                continue # Value is now valid and stored, move to next enum_key

                            # 3. If still not valid after stripping, apply defaulting logic:
                            default_value_to_set: Optional[str] = None

                            if enum_key in ["primary_stall_reason_code", "next_action_code"]:
                                default_value_to_set = "N/A"
                            elif allowed_values_list: # For non-critical fields, use the first allowed value
                                default_value_to_set = allowed_values_list[0]
                            else: # Fallback if no allowed values (should not happen with good config)
                                logger.error(f"No allowed values defined for enum_key '{enum_key}' in meta.yml. Cannot set a default for original value '{original_value_for_logging}'. Using 'ERROR_NO_DEFAULTS'.")
                                default_value_to_set = "ERROR_NO_DEFAULTS"
                            
                            if parsed_data.get(enum_key) != default_value_to_set : # Log and set only if different
                                logger.warning(f"Auto-fixing invalid value '{original_value_for_logging}' (after stripping attempts yielded '{value}') for field '{enum_key}' to default '{default_value_to_set}'.")
                                parsed_data[enum_key] = default_value_to_set
                            elif value == default_value_to_set and parsed_data.get(enum_key) != default_value_to_set:
                                # This case might occur if original value was, say, "N/A" (string) but was not in allowed_values_list
                                # and the default is also "N/A". We still want to ensure the correct type/value is set.
                                logger.info(f"Ensuring default value '{default_value_to_set}' is set for '{enum_key}' from original invalid '{original_value_for_logging}'.")
                                parsed_data[enum_key] = default_value_to_set

            # One more validation pass to ensure everything is fixed
            final_validation_errors = self._validate_yaml(parsed_data)
            if final_validation_errors:
                logger.warning(f"FINAL VALIDATION ISSUES DETECTED: {final_validation_errors}. Fixing critical fields.")
                # Special handling for critical fields that must be fixed
                for enum_key in ["primary_stall_reason_code", "next_action_code"]:
                    if enum_key in parsed_data:
                        value = parsed_data.get(enum_key)
                        if any([error.startswith(f"Invalid value for '{enum_key}'") for error in final_validation_errors]):
                            parsed_data[enum_key] = "N/A"
                            logger.warning(f"Critical field forced to N/A: {enum_key}")
                            
            # Process any NUNCA_RESPONDIO special case
            if temporal_flags and temporal_flags.get('NO_USER_MESSAGES_EXIST') == True:
                logger.info(f"NO_USER_MESSAGES_EXIST condition met. Setting special values for nunca respondio case.")
                parsed_data['inferred_stall_stage'] = "PRE_VALIDACION"
                parsed_data['primary_stall_reason_code'] = "NUNCA_RESPONDIO"
                
            # Successfully parsed and validated (or auto-fixed)
            # ------------------------------------------------------------
            # Attach cache helper fields
            parsed_data["conversation_digest"] = conversation_digest
            parsed_data["last_message_ts"] = last_query_timestamp
            # ------------------------------------------------------------
            
            # Save to cache if enabled
            if self.use_cache and self._cache:
                try:
                    self._cache.set(conversation_digest, parsed_data, self.model)
                    logger.debug(f"Saved summary to cache with digest: {conversation_digest[:8]}...")
                except Exception as e:
                    logger.warning(f"Failed to save summary to cache: {e}", exc_info=True)
                    # Don't fail the operation if caching fails
            
            return parsed_data

        except (ApiError, ValidationError) as e:
            # Let these specific exceptions propagate
            raise
        except Exception as e:  # Catch other unexpected errors
            logger.exception("Failed to summarise conversation: %s", e)
            # Wrap unknown errors
            raise ApiError(f"Unexpected error during summarization: {e}") from e