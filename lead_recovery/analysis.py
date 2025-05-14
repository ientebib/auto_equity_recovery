"""analysis.py
Core analysis and summarization logic for the lead recovery pipeline.
"""
from __future__ import annotations

import logging
import asyncio
import csv
import time
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

import pandas as pd
import pytz
import hashlib
import yaml
import re
import concurrent.futures
import pickle
import random

from .config import settings
from .summarizer import ConversationSummarizer
from .reporting import to_csv
from .exceptions import ApiError, ValidationError, LeadRecoveryError
from .cache import run_summary_cache_class_self_test, normalize_phone, compute_conversation_digest, SummaryCache
from .fs import update_link, ensure_dir
from .gsheets import upload_to_google_sheets
from .constants import MESSAGE_COLUMN_NAME, CLEANED_PHONE_COLUMN_NAME, CONVERSATION_DIGEST_COLUMN_NAME
from .python_flags import (
    handoff_finalized as check_handoff_finalized,
    detect_human_transfer as check_human_transfer,
    detect_recovery_template as check_recovery_template,
    detect_topup_template as check_topup_template,
    count_consecutive_recovery_templates,
    extract_message_metadata,
    calculate_temporal_flags,
    analyze_handoff_process,
    determine_conversation_state, # <<< ADDED IMPORT
    detect_pre_validacion # <<< ADDED IMPORT FOR GLOBAL SCOPE
)
from .python_flags_manager import get_python_flag_columns

logger = logging.getLogger(__name__)

# Define missing constant
SENDER_COLUMN_NAME = "msg_from"

def _log_memory_usage(prefix: str = ""):
    """Log current memory usage of the process."""
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024
        logger.debug(f"{prefix}Memory usage: {memory_mb:.1f} MB")
    except ImportError:
        # psutil not available, skip memory logging
        pass

def _optimize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Optimize the memory usage of a DataFrame."""
    # Optimize string columns
    for col in df.columns:
        if df[col].dtype == 'object':
            try:
                df[col] = df[col].astype("string[pyarrow]")
            except (ImportError, TypeError):
                # Fall back if pyarrow not available or column has mixed types
                pass
    return df

async def run_summarization_step(
    output_dir: Path,
    prompt_template_path: Optional[Path] = None,
    max_workers: Optional[int] = None,
    recipe_name: Optional[str] = None,
    use_cache: bool = True,
    gsheet_config: Optional[Dict[str, str]] = None,
    meta_config: Optional[Dict[str, Any]] = None,
    skip_detailed_temporal_calc: bool = False,
    skip_hours_minutes: bool = False,
    skip_reactivation_flags: bool = False,
    skip_timestamps: bool = False,
    skip_user_message_flag: bool = False,
    skip_handoff_detection: bool = False,
    skip_metadata_extraction: bool = False,
    skip_handoff_invitation: bool = False,
    skip_handoff_started: bool = False,
    skip_handoff_finalized: bool = False,
    skip_human_transfer: bool = False,
    skip_recovery_template_detection: bool = False,
    skip_consecutive_templates_count: bool = False,
    skip_pre_validacion_detection: bool = False, # Existing, ensure it's passed if needed
    skip_conversation_state: bool = False, # <<< ADDED skip_conversation_state PARAM
    limit: Optional[int] = None
):
    """Run the conversation summarization step.
    
    Args:
        output_dir: Directory containing conversations and where to write summaries.
        prompt_template_path: Custom prompt template path.
        max_workers: Maximum concurrent LLM API calls.
        recipe_name: Recipe name for output files.
        use_cache: Whether to use cached summaries.
        gsheet_config: Google Sheets configuration.
        meta_config: Additional configuration.
        skip_detailed_temporal_calc: Skip detailed temporal calculations.
        skip_hours_minutes: Skip hours/minutes calculations.
        skip_reactivation_flags: Skip reactivation window flags.
        skip_timestamps: Skip timestamp formatting.
        skip_user_message_flag: Skip user message flag.
        skip_handoff_detection: Skip handoff detection.
        skip_metadata_extraction: Skip message metadata extraction.
        skip_handoff_invitation: Skip handoff invitation detection.
        skip_handoff_started: Skip handoff started detection.
        skip_handoff_finalized: Skip handoff finalized detection.
        skip_human_transfer: Skip human transfer detection.
        skip_recovery_template_detection: Skip recovery template detection.
        skip_consecutive_templates_count: Skip counting consecutive recovery templates.
        skip_pre_validacion_detection: Skip pre-validation detection (existing, ensure it's passed if needed)
        skip_conversation_state: Skip conversation state determination (added, ensure it's passed if needed)
        limit: Maximum number of conversations to process (for testing).
        
    Returns:
        None. Results are written to files.
    """
    # Ensure the output directory exists
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Validate the conversations.csv file exists
    conversations_file = output_dir / "conversations.csv"
    if not conversations_file.exists():
        raise LeadRecoveryError("Conversations file not found. Run fetch-convos first.")
    
    # Load the prompt template - use the recipe's prompt.txt file or the default from the summarizer
    # Default prompt is handled by the ConversationSummarizer class, no need to specify it here
    
    # Set up a cache for results
    cache = None
    cached_results = {}
    conversation_digests = {}
    
    if use_cache:
        cache = SummaryCache(output_dir)
        cached_results = await cache.load_all_cached_results() if hasattr(cache, 'load_all_cached_results') else {}
        conversation_digests = {k: v.get("conversation_digest", "") for k, v in cached_results.items()}
    
    # The skip_* flags are received as function arguments, presumably set by the CLI.
    # Log these received values.
    logger.info("--- Skip Flag Arguments Received by run_summarization_step ---")
    logger.info(f"Using skip_detailed_temporal_calc = {skip_detailed_temporal_calc}")
    logger.info(f"Using skip_hours_minutes = {skip_hours_minutes}")
    logger.info(f"Using skip_reactivation_flags = {skip_reactivation_flags}")
    logger.info(f"Using skip_timestamps = {skip_timestamps}")
    logger.info(f"Using skip_user_message_flag = {skip_user_message_flag}")
    logger.info(f"Using skip_handoff_detection = {skip_handoff_detection}")
    logger.info(f"Using skip_metadata_extraction = {skip_metadata_extraction}")
    logger.info(f"Using skip_handoff_invitation = {skip_handoff_invitation}")
    logger.info(f"Using skip_handoff_started = {skip_handoff_started}")
    logger.info(f"Using skip_handoff_finalized = {skip_handoff_finalized}")
    logger.info(f"Using skip_human_transfer = {skip_human_transfer}")
    logger.info(f"Using skip_recovery_template_detection = {skip_recovery_template_detection}")
    logger.info(f"Using skip_consecutive_templates_count = {skip_consecutive_templates_count}")
    logger.info(f"Using skip_pre_validacion_detection = {skip_pre_validacion_detection if 'skip_pre_validacion_detection' in locals() else 'Not Passed'}") # Adjusted for safety
    logger.info(f"Using skip_conversation_state = {skip_conversation_state}") # <<< LOGGING ADDED PARAM
    logger.info("-------------------------------------------------------------")

    # Note: The overall 'skip_temporal_flags' is a bit ambiguous here.
    # It was previously read from meta_config or defaulted.
    # For now, we assume the specific skip_detailed_temporal_calc etc. flags govern behavior.
    # If there's a general --skip-temporal-flags CLI option, it should ideally control these sub-flags
    # or be passed as a separate 'master' skip_temporal_flags argument.
    # For this revision, we will rely on the specific flags.
    
    # Extract limit parameter if present in meta_config
    # CLI limit takes precedence if both are provided (handled by CLI argument parsing)
    if limit is None and meta_config and 'limit' in meta_config and meta_config['limit'] is not None:
        limit = meta_config['limit']
        logger.info(f"Using conversation limit from meta_config: {limit}")

    # Get dynamic Python flag columns based on the *actual* skip flag arguments received.
    # The 'skip_temporal_flags' argument to get_python_flag_columns needs a clear source.
    # Let's define it based on whether all its sub-components are skipped.
    effective_skip_temporal_flags = (
        skip_detailed_temporal_calc and
        skip_hours_minutes and
        skip_reactivation_flags and
        skip_timestamps and
        skip_user_message_flag
    )
    logger.info(f"Effective skip_temporal_flags for get_python_flag_columns = {effective_skip_temporal_flags}")

    python_flag_columns = get_python_flag_columns(
        skip_temporal_flags=effective_skip_temporal_flags, # Use the derived effective flag
        skip_metadata_extraction=skip_metadata_extraction,
        skip_handoff_detection=skip_handoff_detection,
        skip_human_transfer=skip_human_transfer,
        skip_recovery_template_detection=skip_recovery_template_detection,
        skip_consecutive_templates_count=skip_consecutive_templates_count,
        skip_handoff_invitation=skip_handoff_invitation,
        skip_handoff_started=skip_handoff_started,
        skip_handoff_finalized=skip_handoff_finalized,
        skip_detailed_temporal=skip_detailed_temporal_calc,
        skip_hours_minutes=skip_hours_minutes,
        skip_reactivation_flags=skip_reactivation_flags,
        skip_timestamps=skip_timestamps,
        skip_user_message_flag=skip_user_message_flag,
        skip_pre_validacion_detection=skip_pre_validacion_detection if 'skip_pre_validacion_detection' in locals() else False, # Ensure it's passed
        skip_conversation_state=skip_conversation_state # <<< PASSING ADDED PARAM
    )
    
    logger.info(f"Dynamic Python flag columns: {python_flag_columns}")
    
    # Store the python_flag_columns in meta_config for later use
    if meta_config:
        meta_config['python_flag_columns'] = python_flag_columns

    # Extract expected_yaml_keys from meta_config if available
    expected_yaml_keys_internal = meta_config.get('expected_yaml_keys') if meta_config else None
    if isinstance(expected_yaml_keys_internal, list):
        logger.info(f"Using expected_yaml_keys from meta_config: {len(expected_yaml_keys_internal)} keys")
    else:
        logger.warning("Could not find 'expected_yaml_keys' list in meta_config or meta_config not provided.")
        expected_yaml_keys_internal = None # Ensure it's None if not a list

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Check required files exist
    convos_path = output_dir / "conversations.csv"
    leads_path = output_dir / "leads.csv"
    
    if not leads_path.exists():
        raise LeadRecoveryError(f"Leads CSV not found at {leads_path}")
    
    if not convos_path.exists():
        raise LeadRecoveryError(f"Conversations CSV not found at {convos_path}")
    
    # Load the conversation data
    try:
        convos_df = pd.read_csv(convos_path)
        leads_df = pd.read_csv(leads_path)
        logger.info(f"Loaded {len(convos_df)} conversation messages and {len(leads_df)} leads")
        
        # --- Handle Column Renames From DB Layer (APPLYING RENAME HERE AGAIN) --- 
        if "cleaned_phone_number" in convos_df.columns and CLEANED_PHONE_COLUMN_NAME not in convos_df.columns:
            convos_df.rename(columns={"cleaned_phone_number": CLEANED_PHONE_COLUMN_NAME}, inplace=True)
        
        # Ensure the essential column is present after attempting rename
        if CLEANED_PHONE_COLUMN_NAME not in convos_df.columns and not convos_df.empty:
            raise ValueError(
                f"Conversation data is missing the crucial phone column '{CLEANED_PHONE_COLUMN_NAME}' even after rename attempt."
            )

        # Basic validation
        if convos_df.empty:
            logger.warning("No conversation data found. Creating empty analysis file.")
            result_df = leads_df.copy()
            result_df["summary"] = "No conversation data available"
            
            # Save results
            today_str = datetime.now().strftime('%Y%m%d')
            output_filename = f"{recipe_name}_analysis_{today_str}.csv" if recipe_name else "analysis.csv"
            output_path = output_dir / output_filename
            to_csv(result_df, output_path)
            logger.info(f"Analysis saved to {output_path}")
            return
        
        # Validate required columns are present in the conversation data
        REQUIRED_CONVO_COLUMNS = {
            "creation_time", 
            "msg_from", 
            MESSAGE_COLUMN_NAME, 
            CLEANED_PHONE_COLUMN_NAME
        }
        missing_columns = REQUIRED_CONVO_COLUMNS - set(convos_df.columns)
        if missing_columns:
            raise LeadRecoveryError(
                f"Conversation data is missing required columns: {missing_columns}. "
                f"Available columns: {list(convos_df.columns)}"
            )
        
        # Group conversations by phone number
        phone_groups = convos_df.groupby(CLEANED_PHONE_COLUMN_NAME)
        logger.info(f"Found {len(phone_groups)} unique phone numbers in conversations")
        
        # Determine concurrency 
        if max_workers is None:
            # Adaptive based on CPU count but with reasonable limits
            max_workers = min(32, max(4, os.cpu_count() or 4))
        logger.info(f"Using max_workers={max_workers} for summarization")
        
        # Create summarizer instance
        # We'll reuse the same instance for all conversations, allowing model caching
        summarizer = ConversationSummarizer(
            prompt_template_path=prompt_template_path,
            use_cache=use_cache,  # Pass cache flag to summarizer
            meta_config=meta_config # Pass the whole meta_config
        )
        
        # Track progress
        total = len(phone_groups)
        completed = 0
        summaries: Dict[str, Dict[str, Any]] = {}
        errors: Dict[str, str] = {}
        
        # Use semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_workers)
        
        async def process_conversation(phone: str, conv_df: pd.DataFrame, current_skip_detailed_temporal: bool) -> None:
            """Process a single conversation with concurrency control."""
            nonlocal completed
            # Pass skip_conversation_state to where determine_conversation_state will be called
            # This might need to be passed further down if determine_conversation_state is called in a helper
            logger.info(f"PROCESS_CONVERSATION for {phone}: effective skip_temporal_flags (from run_summarization_step scope) = {effective_skip_temporal_flags}, skip_conversation_state = {skip_conversation_state}")
            try:
                # Try to acquire semaphore with timeout to prevent deadlocks
                try:
                    # Allow 60 seconds to acquire the semaphore
                    acquire_timeout = 60  # seconds
                    logger.debug(f"Attempting to acquire semaphore for phone {phone} (timeout: {acquire_timeout}s)")
                    
                    # Use asyncio.wait_for to add timeout to semaphore acquisition
                    await asyncio.wait_for(semaphore.acquire(), timeout=acquire_timeout)
                    logger.debug(f"Acquired semaphore for phone {phone}")
                except asyncio.TimeoutError:
                    logger.error(f"Timed out waiting for semaphore for phone {phone} after {acquire_timeout}s")
                    # Still increment completed count and add an error to summaries
                    completed += 1
                    summaries[phone] = {
                        "summary": f"ERROR: Timed out waiting to acquire processing slot after {acquire_timeout}s.",
                        "inferred_stall_stage": "ERROR_TIMEOUT",
                        "primary_stall_reason_code": "ERROR_SEMAPHORE_TIMEOUT",
                        "next_action_code": "ERROR_RETRY_SUGGESTED",
                    }
                    return
                
                try:
                    # Skip temporal flags if requested through CLI override
                    temporal_flags = None
                    
                    # CRITICAL: Use the global skip_temporal_flags variable, not just rely on the passed parameter
                    current_skip_temporal = effective_skip_temporal_flags or current_skip_detailed_temporal
                    
                    if effective_skip_temporal_flags:
                        # If skip_temporal_flags is true, set minimal defaults and don't even call the function
                        logger.debug(f"Completely skipping temporal flags calculation for phone {phone} due to skip_temporal_flags=True")
                        temporal_flags = {
                            "LAST_MESSAGE_TIMESTAMP_TZ": None,
                            "NO_USER_MESSAGES_EXIST": True,
                            "HOURS_MINUTES_SINCE_LAST_USER_MESSAGE": None,
                            "HOURS_MINUTES_SINCE_LAST_MESSAGE": None, 
                            "IS_WITHIN_REACTIVATION_WINDOW": False,
                            "IS_RECOVERY_PHASE_ELIGIBLE": False,
                            "LAST_USER_MESSAGE_TIMESTAMP_TZ": None
                        }
                    else:
                        # Only calculate if not skipping all temporal flags
                        # Calculate temporal flags for the conversation
                        logger.debug(f"Processing temporal flags for phone {phone}")
                        temporal_flags = calculate_temporal_flags(
                            conv_df, 
                            skip_detailed_temporal=current_skip_temporal,
                            skip_hours_minutes=skip_hours_minutes,
                            skip_reactivation_flags=skip_reactivation_flags,
                            skip_timestamps=skip_timestamps,
                            skip_user_message_flag=skip_user_message_flag
                        )
                        logger.debug(f"Calculated temporal flags for phone {phone} (skip_detailed={current_skip_temporal}): {temporal_flags}")
                    
                    # Initialize all flags
                    human_transfer_detected_by_python = False
                    last_bot_message_is_recovery_template = False
                    consecutive_recovery_templates_count = 0
                    handoff_finalized = False
                    handoff_invitation_detected = False # Initialize new handoff flags
                    handoff_response = "NO_INVITATION" # Initialize new handoff flags
                    pre_validacion_detected_flag = False # Initialize pre_validacion_detected
                    conversation_state_value = "UNKNOWN" # Initialize conversation_state

                    # Define the message and sender column names
                    MESSAGE_COLUMN_NAME_LOCAL = "message"
                    SENDER_COLUMN_NAME_LOCAL = "msg_from"

                    # Check for handoff/transfer/template flags if not skipped by CLI
                    if not conv_df.empty and MESSAGE_COLUMN_NAME_LOCAL in conv_df.columns and SENDER_COLUMN_NAME_LOCAL in conv_df.columns:
                        # Get relevant skip flags from meta_config if available
                        skip_human_transfer_local = skip_human_transfer # Use the value passed to run_summarization_step
                        skip_recovery_template_detection_local = skip_recovery_template_detection
                        skip_consecutive_templates_count_local = skip_consecutive_templates_count
                        # Handoff sub-flags (passed to analyze_handoff_process)
                        skip_handoff_invitation_local = skip_handoff_invitation
                        skip_handoff_started_local = skip_handoff_started
                        skip_handoff_finalized_local = skip_handoff_finalized
                        
                        # Create a list of message dictionaries
                        messages = []
                        for _, row in conv_df.iterrows():
                            sender = str(row[SENDER_COLUMN_NAME_LOCAL]).lower()
                            message_text = str(row[MESSAGE_COLUMN_NAME_LOCAL])
                            message_dict = {
                                'msg_from': 'bot' if sender == 'bot' else 'user',
                                'message': message_text,
                                'cleaned_phone_number': phone,
                                # Add timestamp for potential future use, ensure it's datetime
                                'creation_time': pd.to_datetime(row.get('creation_time', None), errors='coerce') 
                            }
                            messages.append(message_dict)
                        
                        # Sort messages by creation_time if available
                        if all(m.get('creation_time') is not None for m in messages):
                             messages.sort(key=lambda x: x['creation_time'])
                        else:
                             logger.warning(f"Cannot sort messages for phone {phone} due to missing timestamps; relying on DataFrame order.")

                        # --- Message Metadata Extraction ---
                        # Ensure conv_df is used here, as it's the DataFrame for the current phone group
                        # Use skip_metadata_extraction directly from the outer scope (it's a param of run_summarization_step)
                        message_metadata = extract_message_metadata(conv_df, skip=skip_metadata_extraction)
                        logger.debug(f"Message metadata for {phone}: {message_metadata}")
                        
                        # Use the global flag functions
                        if messages:
                            # --- Pre-validation Detection ---
                            # Assuming skip_pre_validacion_detection is available from outer scope
                            if not (skip_pre_validacion_detection if 'skip_pre_validacion_detection' in locals() else False):
                                from .python_flags import detect_pre_validacion # Local import if specific
                                for msg_idx, msg_content in enumerate(messages):
                                    if msg_content.get('msg_from') == 'bot':
                                        if detect_pre_validacion(msg_content.get('message','')):
                                            pre_validacion_detected_flag = True
                                            logger.debug(f"Pre-validacion detected for {phone} at message {msg_idx}")
                                            break # Found it
                            else:
                                logger.debug(f"Skipping pre-validation detection for {phone}")

                            # --- Determine Conversation State ---
                            # Use the skip_conversation_state flag passed down
                            if not skip_conversation_state:
                                conversation_state_value = determine_conversation_state(messages, skip=skip_conversation_state)
                                logger.debug(f"Determined conversation_state for {phone}: {conversation_state_value}")
                            else:
                                logger.debug(f"Skipping conversation_state determination for {phone}")
                                conversation_state_value = "SKIPPED_BY_FLAG"

                            # --- Handoff Analysis ---
                            # Call analyze_handoff_process if skip_handoff_detection is False
                            if not skip_handoff_detection:
                                logger.debug(f"Running analyze_handoff_process for phone {phone} with skips: invitation={skip_handoff_invitation_local}, started={skip_handoff_started_local}, finalized={skip_handoff_finalized_local}")
                                handoff_analysis_result = analyze_handoff_process(
                                    messages,
                                    skip_handoff_invitation=skip_handoff_invitation_local,
                                    skip_handoff_started=skip_handoff_started_local,
                                    skip_handoff_finalized=skip_handoff_finalized_local
                                )
                                handoff_invitation_detected = handoff_analysis_result["handoff_invitation_detected"]
                                handoff_response = handoff_analysis_result["handoff_response"]
                                handoff_finalized = handoff_analysis_result["handoff_finalized"] # Overwrites previous default
                                logger.debug(f"Handoff analysis result for {phone}: {handoff_analysis_result}")
                            else:
                                logger.debug(f"Skipping analyze_handoff_process for phone {phone} (skip_handoff_detection=True)")
                                # Use default values if skipped
                                handoff_invitation_detected = False
                                handoff_response = "SKIPPED"
                                handoff_finalized = False

                            # --- Human Transfer Detection ---
                            if not skip_human_transfer_local:
                                human_transfer_detected_by_python = check_human_transfer(messages, skip=skip_human_transfer_local)
                                if human_transfer_detected_by_python:
                                    logger.info(f"Human transfer detected in process_conversation for phone {phone}")
                            else:
                                logger.debug(f"Skipping human transfer detection for phone {phone} (skip_human_transfer=True)")

                            # --- Template Detection ---
                            # Check for recovery template in last bot message
                            if not skip_recovery_template_detection_local:
                                last_bot_message = None
                                for msg in reversed(messages):
                                    if msg.get('msg_from') == 'bot':
                                        last_bot_message = msg
                                        break
                                if last_bot_message:
                                    last_bot_message_is_recovery_template = check_recovery_template(
                                        last_bot_message.get('message', ''), 
                                        skip=skip_recovery_template_detection_local
                                    )
                                    if last_bot_message_is_recovery_template:
                                        logger.debug(f"Recovery template detected in last bot message for phone {phone}")
                            else:
                                logger.debug(f"Skipping recovery template detection for phone {phone} (skip_recovery_template_detection=True)")
                                
                            # Count consecutive recovery templates if not skipped
                            if not skip_consecutive_templates_count_local:
                                consecutive_recovery_templates_count = count_consecutive_recovery_templates(
                                    messages, 
                                    skip=skip_consecutive_templates_count_local
                                )
                                if consecutive_recovery_templates_count > 0:
                                    logger.debug(f"Found {consecutive_recovery_templates_count} consecutive recovery templates for {phone}")
                            else:
                                logger.debug(f"Skipping consecutive templates count for phone {phone} (skip_consecutive_templates_count=True)")
                                
                            # Check for topup template (This seems less critical than handoff, keep separate for now)
                            # if not skip_topup_template_detection_local: ... (add if needed)

                    else:
                         logger.debug(f"Skipping Python flag detections for phone {phone} due to empty/invalid DataFrame or CLI skip flags.")

                    # Store Python flag results in a dictionary
                    python_flags_results = {
                        "human_transfer_detected_by_python": human_transfer_detected_by_python,
                        "recovery_template_detected": last_bot_message_is_recovery_template, # Changed key name
                        "consecutive_recovery_templates_count": consecutive_recovery_templates_count,
                        "handoff_invitation_detected": handoff_invitation_detected,
                        "handoff_response": handoff_response,
                        "handoff_finalized": handoff_finalized,
                        "pre_validacion_detected": pre_validacion_detected_flag,
                        "conversation_state": conversation_state_value,
                        "last_message_sender": message_metadata.get("last_message_sender", "N/A"),
                        "last_user_message_text": message_metadata.get("last_user_message_text", "N/A"),
                        "last_kuna_message_text": message_metadata.get("last_kuna_message_text", "N/A"),
                        "last_message_ts": message_metadata.get("last_message_ts")
                    }
                    
                    # Add temporal flags (from calculate_temporal_flags) to python_flags_results
                    if temporal_flags: # temporal_flags is from calculate_temporal_flags()
                        python_flags_results.update(temporal_flags)

                    # Call the summarizer and pass all Python flags as parameters
                    # The 'temporal_flags' argument for summarizer.summarize will be our comprehensive python_flags_results
                    summary_result_from_llm = await summarizer.summarize(
                        conv_df.copy(),
                        temporal_flags=python_flags_results # Ensure this is the ONLY way flags are passed
                    )
                    
                    if summary_result_from_llm is None:
                        logger.error(f"Summarization for {phone} returned None from summarizer.summarize. Storing error dict.")
                        summaries[phone] = {
                            "summary": "ERROR: LLM summarization failed (returned None).",
                            "inferred_stall_stage": "ERROR_LLM_NONE",
                            "primary_stall_reason_code": "ERROR_LLM_NONE",
                            "prior_reactivation_attempt_count": 0,
                            "reactivation_status_assessment": "ERROR_LLM_NONE",
                            "last_message_sender": "N/A",
                            "last_user_message_text": "N/A",
                            "last_kuna_message_text": "N/A",
                            "transfer_context_analysis": "N/A (LLM Error)",
                            "next_action_code": "ERROR_LLM_NONE",
                            "next_action_context": "LLM summarization failed (returned None from process_conversation).",
                            "suggested_message_es": "",
                            "llm_error_details": "Summarizer.summarize in process_conversation returned None."
                        }
                        # Also store python flags for errored conversations
                        summaries[phone].update(python_flags_results)
                    else:
                        # Store the LLM result directly without merging Python flags again,
                        # since they were already included in the prompt and considered by the LLM
                        summaries[phone] = summary_result_from_llm
                        
                        # Add Python flags to the summary result
                        summaries[phone].update(python_flags_results)
                        
                        # Add additional metadata fields if needed
                        if "conversation_digest" not in summary_result_from_llm and "conversation_digest" in locals():
                            summaries[phone]["conversation_digest"] = conversation_digest
                        if "cleaned_phone" not in summary_result_from_llm:
                            summaries[phone]["cleaned_phone"] = phone
                except (ApiError, ValidationError) as e:
                    logger.error(f"Error summarizing conversation for {phone}: {e}", exc_info=True)
                    errors[phone] = str(e)
                    # Ensure an error placeholder is in summaries if an error occurs before assignment
                    summaries[phone] = {
                        "summary": f"ERROR: {type(e).__name__} during summarization.",
                        "error_details": str(e),
                        "inferred_stall_stage": "ERROR_PROCESSING",
                        "primary_stall_reason_code": "ERROR_PROCESSING",
                        "next_action_code": "ERROR_PROCESSING",
                    }
                except Exception as e:
                    logger.error(f"Unexpected error summarizing conversation for {phone}: {e}", exc_info=True)
                    errors[phone] = f"Unexpected error: {e}"
                    summaries[phone] = {
                        "summary": f"ERROR: Unexpected {type(e).__name__} during summarization.",
                        "error_details": str(e),
                        "inferred_stall_stage": "ERROR_UNEXPECTED",
                        "primary_stall_reason_code": "ERROR_UNEXPECTED",
                        "next_action_code": "ERROR_UNEXPECTED",
                    }
                finally:
                    # Always release the semaphore in the inner finally block
                    semaphore.release()
                    logger.debug(f"Released semaphore for phone {phone}")
            finally:
                # Always increment completion counter in the outer finally block
                completed += 1
                if completed % 10 == 0 or completed == total:
                    logger.info(f"Summarization progress: {completed}/{total} ({completed/total:.1%})")
        
        # Create tasks for all conversations
        tasks = []
        for phone, group in phone_groups:
            # Create a task for each phone number
            task = asyncio.create_task(process_conversation(phone, group, skip_detailed_temporal_calc))
            tasks.append(task)
        
        # Wait for all tasks to complete
        await asyncio.gather(*tasks)
        
        # Check for errors
        if errors:
            logger.warning(f"Summarization completed with {len(errors)} errors out of {total} conversations")
        else:
            logger.info(f"Summarization completed successfully for all {total} conversations")
            
        # Merge results with leads data
        result_rows = []
        for _, lead in leads_df.iterrows():
            phone = lead[CLEANED_PHONE_COLUMN_NAME]
            row_data = lead.to_dict()
            
            if phone in summaries:
                # Add all summary fields to the lead data
                row_data.update(summaries[phone])
            elif phone in errors:
                # Add error information
                row_data["error"] = errors[phone]
            else:
                # No conversation data for this lead
                row_data["summary"] = "No conversation data found"
                
            result_rows.append(row_data)
            
        # Create final DataFrame
        result_df = pd.DataFrame(result_rows)
        
        # --- Column Selection/Exclusion ---
        include_cols = None
        exclude_cols = None
        
        if meta_config:
            if 'include_columns' in meta_config and isinstance(meta_config['include_columns'], list):
                include_cols = meta_config['include_columns']
                logger.info(f"Applying include_columns from meta_config: {include_cols}")
            if 'exclude_columns' in meta_config and isinstance(meta_config['exclude_columns'], list):
                exclude_cols = meta_config['exclude_columns']
                logger.info(f"Applying exclude_columns from meta_config: {exclude_cols}")

        final_columns = list(result_df.columns) # Start with all columns

        # Apply include_cols first if specified
        if include_cols:
            # Ensure essential columns like the phone number are always kept
            essential_cols = {CLEANED_PHONE_COLUMN_NAME} 
            final_columns = [col for col in include_cols if col in result_df.columns]
            # Add essential columns if they were not explicitly included
            for ecol in essential_cols:
                if ecol not in final_columns and ecol in result_df.columns:
                    final_columns.insert(0, ecol) # Add essential columns at the beginning
            logger.info(f"Columns after applying include_columns: {final_columns}")

        # Apply exclude_cols if specified
        if exclude_cols:
            original_cols = set(final_columns)
            final_columns = [col for col in final_columns if col not in exclude_cols]
            excluded = original_cols - set(final_columns)
            if excluded:
                logger.info(f"Columns excluded based on exclude_columns: {list(excluded)}")
            else:
                 logger.info(f"No columns were excluded based on provided exclude_columns list: {exclude_cols}")


        # Filter the DataFrame to only include the final columns
        missing_final_cols = [col for col in final_columns if col not in result_df.columns]
        if missing_final_cols:
            logger.warning(f"Attempting to select columns that do not exist in the DataFrame: {missing_final_cols}. These will be ignored.")
            final_columns = [col for col in final_columns if col in result_df.columns]
            
        if set(final_columns) != set(result_df.columns):
             logger.info(f"Final selected columns for output: {final_columns}")
             result_df = result_df[final_columns]
        else:
            logger.info("No column filtering applied (either not specified or resulted in same columns).")
        # --- End Column Selection/Exclusion ---

        # Save results
        today_str = datetime.now().strftime('%Y%m%d')
        output_filename = f"{recipe_name}_analysis_{today_str}.csv" if recipe_name else "analysis.csv"
        output_path = output_dir / output_filename
        to_csv(result_df, output_path)
        logger.info(f"Analysis saved to {output_path}")
        
        # Display cache stats if available
        if hasattr(summarizer, '_cache') and summarizer._cache is not None:
            try:
                cache_stats = summarizer._cache.stats()
                logger.info(f"Cache statistics: {cache_stats}")
            except:
                pass
                
    except Exception as e:
        logger.exception(f"Error in summarization step: {e}")
        raise LeadRecoveryError(f"Summarization failed: {e}") from e

    # --- Quick self-test for cache consistency ---
    run_summary_cache_class_self_test()
    
    # --- Filename Setup --- 
    _recipe_name = recipe_name or output_dir.name
    today_str = datetime.now().strftime('%Y%m%d')
    run_ts = datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%dT%H-%M')

    run_dir = output_dir / run_ts
    run_dir.mkdir(parents=True, exist_ok=True)

    csv_output_path = run_dir / "analysis.csv"
    ignored_csv_path = run_dir / "ignored.csv"

    # Convenience links in the recipe root
    latest_csv_path = output_dir / "latest.csv"
    latest_ignored_path = output_dir / "latest_ignored.csv"

    # --- Handle Missing/Empty Conversations CSV --- 
    try:
        with open(output_dir / "conversations.csv", 'r', encoding='utf-8') as f_check:
            header = f_check.readline()
            first_data_line = f_check.readline()
            convos_exist_and_not_empty = header and first_data_line
    except FileNotFoundError:
        convos_exist_and_not_empty = False
    except Exception as e_check:
         logger.warning(f"Could not check if conversations.csv is empty: {e_check}. Assuming not empty.")
         convos_exist_and_not_empty = True # Proceed cautiously

    if not convos_exist_and_not_empty:
        logger.info("conversations.csv is empty or missing – skipping OpenAI summarisation.")
        leads_path = output_dir / "leads.csv"  # Create the Path object first
        if leads_path.exists():  # Call exists() on the Path object
            leads_df = pd.read_csv(leads_path)
            # Optimize memory usage
            leads_df = _optimize_dataframe(leads_df)
            
            # Populate leads with defaults based on *expected* keys
            if expected_yaml_keys_internal:
                for col in expected_yaml_keys_internal:
                    if col not in leads_df.columns:
                        leads_df[col] = ""  # Add empty default
            # Consider adding a 'skipped_reason' column to explain why we're just copying leads
            leads_df['cache_status'] = 'NO_CONVERSATIONS'
            # Continue with write paths that match what the real process would produce
            to_csv(leads_df, csv_output_path)
            update_link(csv_output_path, latest_csv_path)
            # Don't create an ignored file since we didn't process anything
            
            # Extract sheet info (if was in meta.yml)
            sheet_id = gsheet_config.get("sheet_id") if gsheet_config else None
            worksheet_name = gsheet_config.get("worksheet_name") if gsheet_config else None

            if sheet_id and worksheet_name:
                try:
                    credentials_path = settings.GOOGLE_CREDENTIALS_PATH
                    logger.info(f"Uploading default values for '{_recipe_name}' to Google Sheet {sheet_id}, worksheet '{worksheet_name}'")
                    upload_to_google_sheets(csv_output_path, sheet_id, worksheet_name, credentials_path)
                except Exception as e:
                    logger.error(f"Error uploading to Google Sheets: {str(e)}")

            return
    
    # --- Read Input CSVs --- 
    leads_path = output_dir / "leads.csv"
    if not leads_path.exists():
        logger.error("leads.csv not found at %s", leads_path)
        raise FileNotFoundError(f"Missing crucial leads.csv file in {output_dir}")

    _log_memory_usage("Before loading leads: ")
    leads_df = pd.read_csv(leads_path)
    # Optimize memory usage
    leads_df = _optimize_dataframe(leads_df)
    logger.info(f"Loaded {len(leads_df)} leads from {leads_path}")
    _log_memory_usage("After loading leads: ")
    
    # Ensure cleaned_phone column exists and normalize it
    if CLEANED_PHONE_COLUMN_NAME not in leads_df.columns:
        raise ValueError(f"leads.csv is missing required '{CLEANED_PHONE_COLUMN_NAME}' column")

    _log_memory_usage("Before loading conversations: ")
    convos_path = output_dir / "conversations.csv"
    # Use chunksize for large files
    convos_reader = pd.read_csv(convos_path, chunksize=100000, encoding='utf-8')
    convos_df = pd.concat(convos_reader, ignore_index=True)
    # Optimize memory usage
    convos_df = _optimize_dataframe(convos_df)
    logger.info(f"Loaded {len(convos_df)} conversation rows from {convos_path}")
    _log_memory_usage("After loading conversations: ")

    # --- Handle Column Renames From DB Layer (APPLYING RENAME HERE AGAIN) --- 
    if "cleaned_phone_number" in convos_df.columns and CLEANED_PHONE_COLUMN_NAME not in convos_df.columns:
        convos_df.rename(columns={"cleaned_phone_number": CLEANED_PHONE_COLUMN_NAME}, inplace=True)
    
    # Ensure the essential column is present after attempting rename
    if CLEANED_PHONE_COLUMN_NAME not in convos_df.columns and not convos_df.empty:
        raise ValueError(
            f"Conversation data is missing the crucial phone column '{CLEANED_PHONE_COLUMN_NAME}' even after rename attempt."
        )

    # --- Group by Phone and Prepare for Processing --- 
    # Find any phones that appear in leads but not in conversations
    leads_phones = set(leads_df[CLEANED_PHONE_COLUMN_NAME].astype(str))
    convos_phones = set(convos_df[CLEANED_PHONE_COLUMN_NAME].astype(str))
    phones_without_convos = leads_phones - convos_phones
    
    if phones_without_convos:
        logger.warning(f"{len(phones_without_convos)} phones from leads have no conversations")
        
    # Group conversations by phone number (efficient since we sorted in fetch_convos)
    convos_df = convos_df.sort_values(CLEANED_PHONE_COLUMN_NAME)
    grouped = convos_df.groupby(CLEANED_PHONE_COLUMN_NAME)
        
    # --- Load Cache (Previous Run Results) --- 
    _log_memory_usage("Before loading cache: ")
    cache_file = output_dir / "cache.csv"
    cached_results = {}
    conversation_digests = {}
    
    try:
        if cache_file.exists():
            # Use chunksize for potentially large cache files
            cache_df_reader = pd.read_csv(cache_file, chunksize=50000)
            cache_df = pd.concat(cache_df_reader, ignore_index=True)
            # Optimize memory usage
            cache_df = _optimize_dataframe(cache_df)
            
            if not cache_df.empty and CLEANED_PHONE_COLUMN_NAME in cache_df.columns and CONVERSATION_DIGEST_COLUMN_NAME in cache_df.columns:
                for _, row in cache_df.iterrows():
                    try:
                        key = str(row[CLEANED_PHONE_COLUMN_NAME])
                        digest = str(row[CONVERSATION_DIGEST_COLUMN_NAME])
                        conversation_digests[key] = digest
                        
                        # Store all fields from the cache row
                        cached_row_dict = {col: val for col, val in row.items() if pd.notna(val)}
                        cached_row_dict["cache_status"] = "CACHED" # Mark as from cache
                        cached_results[key] = cached_row_dict
                    except Exception as e:
                        logger.error(f"Error processing cache row: {e}")
                logger.info(f"Loaded {len(cached_results)} cached results from {cache_file}")
            else:
                logger.warning(f"Cache file exists but is empty or missing required columns")
    except Exception as cache_error:
        logger.error(f"Error loading cache: {cache_error}")
    
    _log_memory_usage("After loading cache: ")

    # --- Setup Summarizer with Recipe-Specific Prompt --- 
    summarizer = ConversationSummarizer(
        prompt_template_path=prompt_template_path,
        meta_config=meta_config # Pass the whole meta_config
    )

    # --- Process Conversations with OpenAI --- 
    async def summarize_group_df(phone: str, group_df: pd.DataFrame, summarizer: ConversationSummarizer, skip_detailed_temporal: bool = False) -> Dict[str, Any]:
        """Helper to summarize a single group of messages for a phone number."""
        # Set defaults for base flags calculated within this function
        human_transfer_detected_by_python = False
        last_bot_message_is_recovery_template = False 
        consecutive_recovery_templates_count = 0
        handoff_finalized_in_group = False # Specific to this function's scope
        pre_validacion_detected_in_group = False
        conversation_state_in_group = "UNKNOWN"
        handoff_invitation_detected_in_group = False 
        handoff_response_in_group = "NO_INVITATION_SGF"

        # --- Initialize skip flags to prevent UnboundLocalError ---
        skip_handoff_detection = False
        skip_human_transfer = False
        skip_handoff_invitation = False
        skip_handoff_started = False
        skip_handoff_finalized = False
        skip_recovery_template_detection = False
        skip_consecutive_templates_count = False
        # --- End skip flag initialization ---

        last_message_sender = "N/A"
        # --- Initialize metadata placeholders to avoid UnboundLocalError in exception paths ---
        last_user_message_text = "N/A"
        last_kuna_message_text = "N/A"
        last_message_ts = None

        try:
            # Check if skip_temporal_flags is set in the summarizer's meta_config
            skip_temporal_flags = False
            if hasattr(summarizer, '_meta_config') and summarizer._meta_config:
                override_options = summarizer._meta_config.get('override_options', {})
                skip_temporal_flags = override_options.get('skip_temporal_flags', False)
            
            # Handle temporal flags calculation based on skip_temporal_flags
            if skip_temporal_flags:
                # Skip calculation completely and use minimal defaults
                logger.debug(f"Skipping all temporal flags for phone {phone} due to skip_temporal_flags=True")
                temporal_flags = {
                    "LAST_MESSAGE_TIMESTAMP_TZ": None,
                    "NO_USER_MESSAGES_EXIST": True,
                    "HOURS_MINUTES_SINCE_LAST_USER_MESSAGE": None,
                    "HOURS_MINUTES_SINCE_LAST_MESSAGE": None, 
                    "IS_WITHIN_REACTIVATION_WINDOW": False,
                    "IS_RECOVERY_PHASE_ELIGIBLE": False,
                    "LAST_USER_MESSAGE_TIMESTAMP_TZ": None,
                    "LAST_MESSAGE_TIMESTAMP_TZ": None,
                    "NO_USER_MESSAGES_EXIST": True
                }
            else:
                # Calculate temporal flags for the conversation, passing the skip flag
                temporal_flags = calculate_temporal_flags(
                    group_df, 
                    skip_detailed_temporal=skip_detailed_temporal,
                    skip_hours_minutes=skip_hours_minutes,
                    skip_reactivation_flags=skip_reactivation_flags,
                    skip_timestamps=skip_timestamps,
                    skip_user_message_flag=skip_user_message_flag
                )
                # Don't log when skipping but do log when actually calculating
                if not skip_detailed_temporal:
                    logger.info(f"[DEBUG] Calculated temporal flags for phone {phone} (skip_detailed={skip_detailed_temporal}): {temporal_flags}")
            
            # Python-based human transfer detection
            if MESSAGE_COLUMN_NAME in group_df.columns and SENDER_COLUMN_NAME in group_df.columns:
                # Check if we should skip handoff or human transfer detection
                skip_handoff_detection = False
                skip_human_transfer = False
                if hasattr(summarizer, '_meta_config') and summarizer._meta_config:
                    override_options = summarizer._meta_config.get('override_options', {})
                    skip_handoff_detection = override_options.get('skip_handoff_detection', False)
                    skip_human_transfer = override_options.get('skip_human_transfer', False)
                
                # Create a list of message dictionaries in the format expected by the handoff detection functions
                messages = []
                for _, row in group_df.iterrows():
                    sender = str(row[SENDER_COLUMN_NAME]).lower()
                    message_text = str(row[MESSAGE_COLUMN_NAME])
                    message_dict = {
                        'msg_from': 'bot' if sender == 'bot' else 'user',
                        'message': message_text,
                        'cleaned_phone_number': phone,
                        'creation_time': pd.to_datetime(row.get('creation_time', None), errors='coerce') 
                    }
                    messages.append(message_dict)
                
                if all(m.get('creation_time') is not None for m in messages):
                    messages.sort(key=lambda x: x['creation_time'])
                else:
                    logger.warning(f"Cannot sort messages for phone {phone} in summarize_group_df due to missing timestamps.")

                # Use the global handoff detection functions to check for transfer and handoff completion
                if messages:  # Only check if there are messages
                    # --- Pre-validation Detection ---
                    if not skip_pre_validacion_detection: # from outer scope
                        # from .python_flags import detect_pre_validacion # Already imported globally
                        for msg_idx, msg_content in enumerate(messages):
                            if msg_content.get('msg_from') == 'bot':
                                if detect_pre_validacion(msg_content.get('message','')):
                                    pre_validacion_detected_in_group = True
                                    logger.debug(f"Pre-validacion detected for {phone} at message {msg_idx} (in summarize_group_df)")
                                    break 
                    # --- Determine Conversation State ---
                    if not skip_conversation_state: # from outer scope
                        conversation_state_in_group = determine_conversation_state(messages, skip=skip_conversation_state)
                        logger.debug(f"Determined conversation_state for {phone}: {conversation_state_in_group} (in summarize_group_df)")

                    # Check for human transfer if not skipped
                    if not skip_human_transfer: # from outer scope
                        human_transfer_detected_by_python = check_human_transfer(messages, skip=skip_human_transfer)
                        if human_transfer_detected_by_python:
                            logger.info(f"Human transfer detected for phone {phone} using global detection")
                    
                    # Check for handoff finalization if not skipped    
                    if not skip_handoff_detection: # from outer scope
                        handoff_finalized_in_group = check_handoff_finalized(messages, skip=skip_handoff_finalized) # from outer scope
                        if handoff_finalized_in_group:
                            logger.info(f"Handoff finalized detected for phone {phone} using global detection (in summarize_group_df)")
            else:
                missing_cols = []
                if MESSAGE_COLUMN_NAME not in group_df.columns: missing_cols.append(MESSAGE_COLUMN_NAME)
                if SENDER_COLUMN_NAME not in group_df.columns: missing_cols.append(SENDER_COLUMN_NAME)
                logger.warning(f"Skipping Python-based detection for phone {phone} due to missing columns: {', '.join(missing_cols)}")

            # Recipe-specific recovery template detection
            # Access recipe_name from the summarizer instance
            current_recipe_name = summarizer._recipe_name if hasattr(summarizer, '_recipe_name') else None
            
            # Get custom skip flags for recipe-specific functions
            skip_handoff_invitation = False
            skip_handoff_started = False
            skip_handoff_finalized = False
            skip_human_transfer = False
            skip_handoff_detection = False
            skip_recovery_template_detection = False
            skip_consecutive_templates_count = False
            if hasattr(summarizer, '_meta_config') and summarizer._meta_config:
                override_options = summarizer._meta_config.get('override_options', {})
                skip_handoff_invitation = override_options.get('skip_handoff_invitation', False)
                skip_handoff_started = override_options.get('skip_handoff_started', False)
                skip_handoff_finalized = override_options.get('skip_handoff_finalized', False)
                skip_human_transfer = override_options.get('skip_human_transfer', False)
                skip_handoff_detection = override_options.get('skip_handoff_detection', False)
                skip_recovery_template_detection = override_options.get('skip_recovery_template_detection', False)
                skip_consecutive_templates_count = override_options.get('skip_consecutive_templates_count', False)
            
            if current_recipe_name == "simulation_to_handoff":
                logger.debug(f"Processing simulation_to_handoff recipe-specific detection for phone {phone}")
                if not skip_recovery_template_detection and MESSAGE_COLUMN_NAME in group_df.columns and SENDER_COLUMN_NAME in group_df.columns:
                    # Assuming group_df is sorted chronologically
                    bot_messages_df = group_df[group_df[SENDER_COLUMN_NAME].astype(str).str.lower() == "bot"]
                    
                    if not bot_messages_df.empty:
                        # Check last bot message for recovery template
                        last_bot_message_text = bot_messages_df[MESSAGE_COLUMN_NAME].iloc[-1]
                        
                        # Use global function to check for recovery template
                        last_bot_message_is_recovery_template = check_recovery_template(last_bot_message_text, skip=skip_recovery_template_detection)
                        
                        # Add debug logging
                        if "template" in str(last_bot_message_text).lower() and not last_bot_message_is_recovery_template:
                            logger.debug(f"Message contains 'template' but not detected as recovery template for phone {phone}. Message: {last_bot_message_text[:100]}...")
                        
                        # Count consecutive recovery templates if not skipped
                        if not skip_consecutive_templates_count:
                            # Convert to format expected by the function
                            bot_messages = []
                            for _, row in bot_messages_df.iterrows():
                                bot_messages.append({
                                    'msg_from': 'bot',
                                    'message': row[MESSAGE_COLUMN_NAME],
                                    'cleaned_phone_number': phone
                                })
                            
                            consecutive_recovery_templates_count = count_consecutive_recovery_templates(bot_messages, skip=skip_consecutive_templates_count)
                            logger.debug(f"Found {consecutive_recovery_templates_count} consecutive recovery templates for {phone}")
                        
                        # Check all messages for handoff finalization using the global function
                        if not skip_handoff_finalized and not handoff_finalized_in_group and not bot_messages_df.empty:
                            # Use the already converted bot_messages if available
                            if not 'bot_messages' in locals():
                                bot_messages = []
                                for _, row in bot_messages_df.iterrows():
                                    bot_messages.append({
                                        'msg_from': 'bot',
                                        'message': row[MESSAGE_COLUMN_NAME],
                                        'cleaned_phone_number': phone
                                    })
                            
                            # Check using the global function
                            if check_handoff_finalized(bot_messages, skip=skip_handoff_detection):
                                handoff_finalized_in_group = True
                                logger.info(f"Handoff finalized detected for phone {phone} (recipe-specific check)")
                else:
                    if skip_recovery_template_detection:
                        logger.debug(f"Skipping recovery template detection for {phone} due to skip_recovery_template_detection=True")
                    else:
                        logger.warning(f"Skipping recovery template detection for recipe {current_recipe_name}, phone {phone} due to missing columns.")
            # Recipe-specific top-up template detection for top_up_may recipe
            elif current_recipe_name == "top_up_may":
                logger.debug(f"Processing top_up_may recipe-specific detection for phone {phone}")
                if not skip_consecutive_templates_count and MESSAGE_COLUMN_NAME in group_df.columns and SENDER_COLUMN_NAME in group_df.columns:
                    # Check if any bot message matches the template patterns
                    contains_top_up_template = False
                    
                    bot_messages = group_df[group_df[SENDER_COLUMN_NAME].astype(str).str.lower() == "bot"]
                    if not bot_messages.empty:
                        for _, row in bot_messages.iterrows():
                            message_text = str(row[MESSAGE_COLUMN_NAME])
                            if check_topup_template(message_text, skip=skip_consecutive_templates_count):
                                contains_top_up_template = True
                                logger.debug(f"Found top-up template in conversation for phone {phone}")
                                break
                        
                        if not contains_top_up_template:
                            # Skip this conversation as it doesn't contain a top-up template
                            logger.info(f"Skipping conversation for phone {phone} as it doesn't contain any top-up template message")
                            # Create a placeholder result without conversation_digest
                            skip_result = {
                                CLEANED_PHONE_COLUMN_NAME: phone,
                                "cache_status": "SKIPPED_NO_TOPUP_TEMPLATE",
                                "summary": "No top-up template message found in conversation",
                                "transfer_context_analysis": "N/A - Skipped conversation without top-up template",
                                "human_transfer_detected_by_python": False,
                                "last_bot_message_is_recovery_template": False,
                                "consecutive_recovery_templates_count": 0,
                                "last_message_sender": "N/A",
                                "last_user_message_text": "N/A",
                                "last_kuna_message_text": "N/A"
                            }
                            # Add other expected fields if needed
                            if expected_yaml_keys_internal:
                                for key in expected_yaml_keys_internal:
                                    if key not in skip_result:
                                        skip_result[key] = ""
                            return skip_result
                else:
                    if skip_consecutive_templates_count:
                        logger.debug(f"Skipping top-up template detection for phone {phone} due to skip_consecutive_templates_count=True")
                    else:
                        logger.warning(f"Skipping top-up template detection for recipe {current_recipe_name}, phone {phone} due to missing columns.")

            # --- Message metadata extraction (last sender, last user message, last kuna message, last_message_ts) ---
            # This logic should remain, as these are generally useful and not part of the "detailed" temporal flags.
            if not skip_metadata_extraction and not group_df.empty and MESSAGE_COLUMN_NAME in group_df.columns and SENDER_COLUMN_NAME in group_df.columns:
                metadata = extract_message_metadata(group_df, skip=skip_metadata_extraction)
                last_message_sender = metadata["last_message_sender"]
                last_user_message_text = metadata["last_user_message_text"]
                last_kuna_message_text = metadata["last_kuna_message_text"]
                last_message_ts = metadata["last_message_ts"]
            else:
                # Skip metadata extraction if requested
                if skip_metadata_extraction:
                    logger.debug(f"Skipping metadata extraction for phone {phone} (CLI override)")
                # Use default values from function
                metadata = extract_message_metadata(None, skip=True)
                last_message_sender = metadata["last_message_sender"]
                last_user_message_text = metadata["last_user_message_text"]
                last_kuna_message_text = metadata["last_kuna_message_text"]
                last_message_ts = metadata["last_message_ts"]
            # --- End of message metadata extraction ---

            if MESSAGE_COLUMN_NAME not in group_df.columns: 
                logger.error(f"'{MESSAGE_COLUMN_NAME}' column not found in group_df for phone {phone}. Columns: {group_df.columns}")
                return {
                    "cleaned_phone": phone, "error": f"Missing {MESSAGE_COLUMN_NAME} column", "cache_status": "ERROR",
                    "human_transfer_detected_by_python": human_transfer_detected_by_python,
                    "last_bot_message_is_recovery_template": last_bot_message_is_recovery_template,
                    "consecutive_recovery_templates_count": consecutive_recovery_templates_count,
                    # Include Python-extracted message metadata (will be defaults in this case)
                    "last_message_sender": last_message_sender if last_message_sender is not None else "N/A",
                    "last_user_message_text": last_user_message_text,
                    "last_kuna_message_text": last_kuna_message_text,
                    "last_message_ts": last_message_ts
                }
            
            conversation_text = " ".join(group_df[MESSAGE_COLUMN_NAME].astype(str).tolist()) 
            digest = compute_conversation_digest(conversation_text)
            
            # ---> ADD use_cache CHECK HERE <---
            if use_cache: 
                cached_digest = conversation_digests.get(phone, None)
                if phone in cached_results and cached_digest == digest:
                    cached_val = cached_results[phone]
                    # Ensure new fields are present if loading from an older cache
                    cached_val.setdefault("human_transfer_detected_by_python", human_transfer_detected_by_python)
                    cached_val.setdefault("last_bot_message_is_recovery_template", last_bot_message_is_recovery_template)
                    cached_val.setdefault("consecutive_recovery_templates_count", consecutive_recovery_templates_count)
                    logger.debug(f"Using cached result for phone {phone} (digest unchanged)")
                    return cached_val
                elif phone in cached_results and cached_digest != digest:
                    logger.debug(f"Conversation changed for {phone}, reprocessing (old digest: {cached_digest}, new: {digest})")
            # ---> END ADDED CHECK <---
            # elif phone in cached_results and cached_digest != digest: # <-- This condition is now inside the use_cache block
            #     logger.debug(f"Conversation changed for {phone}, reprocessing (old digest: {cached_digest}, new: {digest})")
                
            # Consolidate all flags into a single dictionary for the summarizer
            all_python_flags_for_summarizer = {
                "human_transfer_detected_by_python": human_transfer_detected_by_python,
                "recovery_template_detected": last_bot_message_is_recovery_template, 
                "consecutive_recovery_templates_count": consecutive_recovery_templates_count,
                "handoff_finalized": handoff_finalized_in_group,
                "pre_validacion_detected": pre_validacion_detected_in_group, 
                "conversation_state": conversation_state_in_group, 
                "handoff_invitation_detected": handoff_invitation_detected_in_group, # Still simplified here
                "handoff_response": handoff_response_in_group, # Still simplified here

                "last_message_sender": last_message_sender if last_message_sender is not None else "N/A",
                "last_user_message_text": last_user_message_text,
                "last_kuna_message_text": last_kuna_message_text,
                "last_message_ts": last_message_ts if last_message_ts is not None else "N/A",
                # Add flags from calculate_temporal_flags output
                **(temporal_flags or {}),
                # Explicitly add flags that might not be in temporal_flags but are calculated in this scope
                # (e.g. if specific pre_validacion or conversation_state were determined here)
                # For now, relying on the structure where most detailed flags are passed in temporal_flags
                # or are part of the core set above.
                # Ensure keys used by prompt template are present here with correct names.
                # Example: if conversation_state was determined here, it would be added:
                # "conversation_state": conversation_state_value_if_calculated_here,
            }

            # If analyze_handoff_process was called (it's not in summarize_group_df currently, but in process_conversation)
            # its results (handoff_invitation_detected, handoff_response) would also be merged here.
            # The current structure has process_conversation prepare a more complete python_flags_results.
            # This summarize_group_df seems to be an older/alternative path.
            # For consistency, it should ideally receive the full python_flags_results like process_conversation does.
            # However, to fix the immediate TypeError, we ensure the call to summarizer.summarize is correct based on its new signature.

            llm_output_data = await summarizer.summarize(
                group_df.copy(), 
                temporal_flags=all_python_flags_for_summarizer # Ensure this is the ONLY way flags are passed
            )

            if llm_output_data is None:
                logger.error(f"Summarization failed for phone {phone} (digest: {digest[:8]}), LLM/summarizer returned None. Constructing error entry for LLM data.")
                # This dict should ONLY contain the fields expected from the LLM, filled with error values.
                # The subsequent code will add CLEANED_PHONE_COLUMN_NAME etc.
                llm_output_data = {
                    "summary": "ERROR: LLM summarization failed (returned None).",
                    "inferred_stall_stage": "ERROR_LLM_NONE",
                    "primary_stall_reason_code": "ERROR_LLM_NONE",
                    "prior_reactivation_attempt_count": 0, 
                    "reactivation_status_assessment": "ERROR_LLM_NONE",
                    # Use Python-extracted values for message metadata when available
                    "last_message_sender": last_message_sender if last_message_sender is not None else "N/A",
                    "last_user_message_text": last_user_message_text,
                    "last_kuna_message_text": last_kuna_message_text,
                    "last_message_ts": last_message_ts,
                    "transfer_context_analysis": "N/A (LLM Error)",
                    "next_action_code": "ERROR_LLM_NONE",
                    "next_action_context": "LLM summarization failed (returned None).",
                    "suggested_message_es": "",
                    "llm_error_details": "Summarizer's LLM call returned None, likely API issue (e.g., quota, timeout, or unparseable response)."
                }
            
            # Now, llm_output_data is guaranteed to be a dictionary.
            summary_result = llm_output_data
            
            # Add metadata about the processing
            summary_result[CLEANED_PHONE_COLUMN_NAME] = phone
            summary_result[CONVERSATION_DIGEST_COLUMN_NAME] = digest
            summary_result["cache_status"] = "FRESH"
            
            # Add all Python flags to the summary_result
            python_flags = {
                "human_transfer_detected_by_python": human_transfer_detected_by_python,
                "last_bot_message_is_recovery_template": last_bot_message_is_recovery_template,
                "consecutive_recovery_templates_count": consecutive_recovery_templates_count,
                "handoff_finalized": handoff_finalized_in_group,
                "pre_validacion_detected": pre_validacion_detected_in_group, 
                "conversation_state": conversation_state_in_group, 
                "handoff_invitation_detected": handoff_invitation_detected_in_group, # Still simplified here
                "handoff_response": handoff_response_in_group, # Still simplified here

                "last_message_sender": last_message_sender if last_message_sender is not None else "N/A",
                "last_user_message_text": last_user_message_text,
                "last_kuna_message_text": last_kuna_message_text,
                "last_message_ts": last_message_ts if last_message_ts is not None else "N/A",
            }
            # Add temporal flags if available
            if temporal_flags:
                python_flags.update(temporal_flags)
            
            # Update the summary result with all Python flags
            summary_result.update(python_flags)
            
            # CRITICAL: Override inferred_stall_stage if handoff_finalized is True
            if handoff_finalized_in_group and "inferred_stall_stage" in summary_result:
                logger.info(f"Enforcing HANDOFF_COMPLETADO for phone {phone} due to handoff_finalized=True")
                summary_result["inferred_stall_stage"] = "HANDOFF_COMPLETADO"
            
            if expected_yaml_keys_internal and not all(key in summary_result for key in expected_yaml_keys_internal):
                missing_keys = set(expected_yaml_keys_internal) - set(summary_result.keys())
                logger.warning(f"Summary result for {phone} is missing expected keys: {missing_keys}")
                for key in missing_keys:
                    summary_result[key] = ""
                    
            return summary_result
                
        except (ApiError, ValidationError) as e:
            logger.error(f"API/Validation error processing phone {phone}: {e}")
            return {
                CLEANED_PHONE_COLUMN_NAME: phone, "cache_status": "ERROR", "error_message": str(e),
                CONVERSATION_DIGEST_COLUMN_NAME: digest if 'digest' in locals() else "",
                "human_transfer_detected_by_python": human_transfer_detected_by_python,
                "last_bot_message_is_recovery_template": last_bot_message_is_recovery_template,
                "consecutive_recovery_templates_count": consecutive_recovery_templates_count,
                # Include Python-extracted message metadata
                "last_message_sender": last_message_sender if last_message_sender is not None else "N/A",
                "last_user_message_text": last_user_message_text,
                "last_kuna_message_text": last_kuna_message_text,
                "last_message_ts": last_message_ts
            }
        except Exception as e:
            logger.error(f"Unexpected error processing phone {phone}: {e}", exc_info=True)
            return {
                CLEANED_PHONE_COLUMN_NAME: phone, "cache_status": "ERROR", "error_message": f"Unexpected error: {str(e)}",
                CONVERSATION_DIGEST_COLUMN_NAME: digest if 'digest' in locals() else "",
                "human_transfer_detected_by_python": human_transfer_detected_by_python,
                "last_bot_message_is_recovery_template": last_bot_message_is_recovery_template,
                "consecutive_recovery_templates_count": consecutive_recovery_templates_count,
                # Include Python-extracted message metadata
                "last_message_sender": last_message_sender if last_message_sender is not None else "N/A",
                "last_user_message_text": last_user_message_text,
                "last_kuna_message_text": last_kuna_message_text,
                "last_message_ts": last_message_ts
            }

    # --- Process Groups in Parallel with Semaphore --- 
    # Limit concurrency to avoid OpenAI rate limits and memory issues
    # Default to CPU core count (common heuristic) if not specified
    concurrency_limit = max_workers if max_workers is not None else min(32, os.cpu_count() or 4)
    logger.info(f"Setting up {concurrency_limit} semaphore for concurrency limits")
    semaphore = asyncio.Semaphore(concurrency_limit)

    # For each unique phone number, process their conversation group
    results = []
    errors = []
    
    # Process phones that appear in both leads AND convos
    async def run_group_with_semaphore(phone: str, group):
        async with semaphore:
            logger.debug(f"Processing phone {phone} with {len(group)} messages")
            start_time = time.time()
            result = await summarize_group_df(phone, group, summarizer, skip_detailed_temporal=skip_detailed_temporal_calc)
            duration = time.time() - start_time
            logger.debug(f"Finished phone {phone} in {duration:.2f}s")
            
            if result.get("cache_status") == "ERROR":
                errors.append(result)
            else:
                results.append(result)
                
    # Schedule tasks
    tasks = []
    for phone, group in grouped:
        tasks.append(run_group_with_semaphore(phone, group))
        
    # Add missing phones with empty results
    for phone in phones_without_convos:
        if phone in cached_results:
            # Use cache if available
            logger.debug(f"Using cached result for phone {phone} (no conversations in this run)")
            cached_val = cached_results[phone]
            cached_val["cache_status"] = "CACHED_NO_CONV"
            results.append(cached_val)
        else:
            # Create a blank record
            logger.debug(f"Adding empty record for phone {phone} (no conversations)")
            empty_record = {
                CLEANED_PHONE_COLUMN_NAME: phone,
                "cache_status": "NO_CONVERSATIONS",
                "human_transfer_detected_by_python": False, 
                "last_bot_message_is_recovery_template": False, # Default for no conversations
                "consecutive_recovery_templates_count": 0    # Default for no conversations
            }
            # Add expected fields with empty values
            if expected_yaml_keys_internal:
                for key in expected_yaml_keys_internal:
                    empty_record[key] = ""
            results.append(empty_record)
    
    # Run all tasks concurrently within concurrency limits
    if tasks:  # Only gather if we have tasks
        await asyncio.gather(*tasks)
        
    # --- Convert Results to DataFrames --- 
    _log_memory_usage("Before processing results: ")
    if not results and not errors:
        logger.warning("No successful results or errors were produced")
        
    # Create DataFrames from results
    results_df = pd.DataFrame(results) if results else pd.DataFrame()
    errors_df = pd.DataFrame(errors) if errors else pd.DataFrame()
    
    # Optimize memory usage
    if not results_df.empty:
        results_df = _optimize_dataframe(results_df)
    if not errors_df.empty:
        errors_df = _optimize_dataframe(errors_df)
    
    # Setup output frames with all expected columns from leads
    if not results_df.empty:
        # ---> FIX: Ensure consistent types before merging <---
        if CLEANED_PHONE_COLUMN_NAME in leads_df.columns:
            logger.debug(f"Converting leads_df['{CLEANED_PHONE_COLUMN_NAME}'] to string before merge.")
            leads_df[CLEANED_PHONE_COLUMN_NAME] = leads_df[CLEANED_PHONE_COLUMN_NAME].astype(str)
        if CLEANED_PHONE_COLUMN_NAME in results_df.columns:
            logger.debug(f"Converting results_df['{CLEANED_PHONE_COLUMN_NAME}'] to string before merge.")
            results_df[CLEANED_PHONE_COLUMN_NAME] = results_df[CLEANED_PHONE_COLUMN_NAME].astype(str)
        # ---> End of Fix <---
        
        # Merge with leads data
        results_df = pd.merge(
            leads_df,
            results_df,
            on=CLEANED_PHONE_COLUMN_NAME,
            how="right",
            suffixes=("_leads", "")
        )
        # Optimize again after merge
        results_df = _optimize_dataframe(results_df)
    else:
        # If we have no results, just use leads with empty LLM columns
        results_df = leads_df.copy()
        results_df["cache_status"] = "NO_RESULTS"
        # Add expected fields if needed
        if expected_yaml_keys_internal:
            for key in expected_yaml_keys_internal:
                if key not in results_df.columns:
                    results_df[key] = ""
    
    _log_memory_usage("After processing results: ")
    
    # --- Prepare Final Results --- 
    # Start with leads_df as base
    final_results = results_df.copy()
    
    # Debug: Log all columns that exist in the final_results DataFrame
    logger.info(f"All columns in final_results: {sorted(list(final_results.columns))}")

    # --- Determine Final Columns Dynamically --- 
    
    # 1. Identify all available columns in the merged results
    available_columns = set(final_results.columns)
    
    # 2. Identify which Python flags were *actually* calculated (not skipped)
    calculated_python_columns = set()
    all_python_columns_mapping = { # Map skip flag arg name to column names
        'skip_temporal_flags': [ # Check the effective flag first
             'HOURS_MINUTES_SINCE_LAST_USER_MESSAGE', 
             'HOURS_MINUTES_SINCE_LAST_MESSAGE',
             'IS_WITHIN_REACTIVATION_WINDOW',
             'IS_RECOVERY_PHASE_ELIGIBLE',
             'LAST_USER_MESSAGE_TIMESTAMP_TZ',
             'LAST_MESSAGE_TIMESTAMP_TZ',
             'NO_USER_MESSAGES_EXIST'
        ],
        'skip_metadata_extraction': [
            'last_message_sender', 
            'last_user_message_text', 
            'last_kuna_message_text', 
            'last_message_ts'
        ],
        'skip_handoff_detection': [
            'handoff_invitation_detected', # Added
            'handoff_response' # Added
            # 'handoff_finalized' is handled separately below
        ],
        'skip_handoff_finalized': ['handoff_finalized'],
        'skip_human_transfer': ['human_transfer_detected_by_python'],
        'skip_recovery_template_detection': ['last_bot_message_is_recovery_template'],
        # 'skip_topup_template_detection': [], # No specific column, affects filtering
        'skip_consecutive_templates_count': ['consecutive_recovery_templates_count'],
        # Add sub-temporal flags if needed for finer control, checking individual skip_* args
        'skip_detailed_temporal_calc': [], # Covered by effective_skip_temporal_flags
        'skip_hours_minutes': ['HOURS_MINUTES_SINCE_LAST_USER_MESSAGE', 'HOURS_MINUTES_SINCE_LAST_MESSAGE'],
        'skip_reactivation_flags': ['IS_WITHIN_REACTIVATION_WINDOW', 'IS_RECOVERY_PHASE_ELIGIBLE'],
        'skip_timestamps': ['LAST_USER_MESSAGE_TIMESTAMP_TZ', 'LAST_MESSAGE_TIMESTAMP_TZ'],
        'skip_user_message_flag': ['NO_USER_MESSAGES_EXIST'],
        'skip_handoff_invitation': ['handoff_invitation_detected'], # Added specific
        'skip_handoff_started': ['handoff_response'], # Added specific (maps to response currently)
    }
    
    # Use the effective skip flags passed into the function
    skip_flags_status = {
        'skip_temporal_flags': effective_skip_temporal_flags, # Use the derived one
        'skip_metadata_extraction': skip_metadata_extraction,
        'skip_handoff_detection': skip_handoff_detection,
        'skip_handoff_finalized': skip_handoff_finalized,
        'skip_human_transfer': skip_human_transfer,
        'skip_recovery_template_detection': skip_recovery_template_detection,
        'skip_consecutive_templates_count': skip_consecutive_templates_count,
        # Add individual flags for potential finer grain control if needed
        'skip_detailed_temporal_calc': skip_detailed_temporal_calc,
        'skip_hours_minutes': skip_hours_minutes,
        'skip_reactivation_flags': skip_reactivation_flags,
        'skip_timestamps': skip_timestamps,
        'skip_user_message_flag': skip_user_message_flag,
        'skip_handoff_invitation': skip_handoff_invitation,
        'skip_handoff_started': skip_handoff_started,
    }

    # Determine which python columns were calculated
    for flag_name, columns in all_python_columns_mapping.items():
        if not skip_flags_status.get(flag_name, True): # If the flag was NOT skipped (False)
            for col in columns:
                if col in available_columns:
                    calculated_python_columns.add(col)

    # 3. Identify core lead columns and LLM columns (use expected_yaml_keys)
    core_lead_columns = set(leads_df.columns)
    llm_columns = set(expected_yaml_keys_internal or [])
    # Always include certain metadata columns
    essential_columns = {CLEANED_PHONE_COLUMN_NAME, CONVERSATION_DIGEST_COLUMN_NAME, 'cache_status', 'error_message'}

    # 4. Define columns to definitely include
    columns_to_include = set()
    columns_to_include.update(core_lead_columns.intersection(available_columns))
    columns_to_include.update(llm_columns.intersection(available_columns))
    columns_to_include.update(calculated_python_columns) # Add python flags only if calculated
    columns_to_include.update(essential_columns.intersection(available_columns))
    
    # Explicitly add ALL Python flag columns from meta_config if they exist in the DataFrame
    if meta_config and 'python_flag_columns' in meta_config and isinstance(meta_config['python_flag_columns'], list):
        meta_python_flag_columns = meta_config['python_flag_columns']
        existing_meta_flag_columns = set(col for col in meta_python_flag_columns if col in available_columns)
        if existing_meta_flag_columns:
            logger.info(f"Adding {len(existing_meta_flag_columns)} Python flag columns from meta_config to columns_to_include: {sorted(list(existing_meta_flag_columns))}")
            columns_to_include.update(existing_meta_flag_columns)
    
    # Add all Python flag columns from meta_config if available
    if meta_config and 'python_flag_columns' in meta_config and isinstance(meta_config['python_flag_columns'], list):
        python_flag_columns_from_meta = set(meta_config['python_flag_columns'])
        python_flag_columns_in_df = python_flag_columns_from_meta.intersection(available_columns)
        if python_flag_columns_in_df:
            logger.info(f"Including {len(python_flag_columns_in_df)} python flag columns from meta_config: {sorted(list(python_flag_columns_in_df))}")
            columns_to_include.update(python_flag_columns_in_df)
    
    # 5. Use meta.yml output_columns primarily for ORDERING
    output_columns_order_preference = meta_config.get('output_columns', []) if meta_config else []
    
    # Force include ALL Python flag columns from meta.yml if they exist in available_columns
    if meta_config and 'python_flag_columns' in meta_config and isinstance(meta_config['python_flag_columns'], list):
        python_flag_cols = meta_config['python_flag_columns']
        for flag_col in python_flag_cols:
            # If the column exists in the DataFrame but isn't in output_columns_order_preference, add it
            if flag_col in available_columns and flag_col not in output_columns_order_preference:
                logger.info(f"Adding Python flag column '{flag_col}' to output columns preference list")
                output_columns_order_preference.append(flag_col)
    
    final_column_order = []
    remaining_columns_to_include = columns_to_include.copy()
    
    # Add columns based on output_columns preference if they are in our include list
    for col in output_columns_order_preference:
        if col in remaining_columns_to_include:
            final_column_order.append(col)
            remaining_columns_to_include.remove(col)
            
    # Add any remaining columns from the include list (e.g., not mentioned in output_columns) sorted alphabetically
    final_column_order.extend(sorted(list(remaining_columns_to_include)))
    
    # Ensure conversation_state is in the final list if it was calculated and exists
    if 'conversation_state' in available_columns and 'conversation_state' not in final_column_order:
        final_column_order.append('conversation_state')
    if 'pre_validacion_detected' in available_columns and 'pre_validacion_detected' not in final_column_order:
        final_column_order.append('pre_validacion_detected')

    # Ensure essential columns are present if they exist in the data, put phone first
    if CLEANED_PHONE_COLUMN_NAME in final_column_order:
        final_column_order.remove(CLEANED_PHONE_COLUMN_NAME)
        final_column_order.insert(0, CLEANED_PHONE_COLUMN_NAME)
        
    # Filter the DataFrame to the final dynamic column list
    # Ensure all columns in final_column_order actually exist in final_results
    final_column_order = [col for col in final_column_order if col in final_results.columns]
    
    # Force include all Python flag columns from meta_config if they exist in final_results
    if meta_config and 'python_flag_columns' in meta_config and isinstance(meta_config['python_flag_columns'], list):
        python_flag_cols = meta_config['python_flag_columns']
        for col in python_flag_cols:
            if col in final_results.columns and col not in final_column_order:
                logger.info(f"Forcing inclusion of Python flag column: {col}")
                final_column_order.append(col)
    
    # Remove conversation_digest if in exclude_columns list from meta_config
    if meta_config and 'exclude_columns' in meta_config and isinstance(meta_config['exclude_columns'], list):
        exclude_cols = meta_config['exclude_columns']
        if CONVERSATION_DIGEST_COLUMN_NAME in exclude_cols and CONVERSATION_DIGEST_COLUMN_NAME in final_column_order:
            logger.info(f"Explicitly removing {CONVERSATION_DIGEST_COLUMN_NAME} from final output as specified in exclude_columns")
            final_column_order.remove(CONVERSATION_DIGEST_COLUMN_NAME)
    
    final_results = final_results[final_column_order]
    
    # Log the final column structure
    logger.info(f"Final output dynamically includes {len(final_column_order)} columns based on runtime flags: {final_column_order}")
    
    # --- Write Results ---
    # Ensure the run directory exists
    run_dir.mkdir(parents=True, exist_ok=True)
    
    # Save to CSV
    final_results.to_csv(csv_output_path, index=False, quoting=csv.QUOTE_MINIMAL)
    logger.info(f"Saved analysis results to {csv_output_path}")
    
    # Create symlink to latest results
    update_link(csv_output_path, latest_csv_path)
    logger.info(f"Updated symlink {latest_csv_path} -> {csv_output_path}")
    
    # Now also save results as timestamped file in the recipe's base output directory
    if recipe_name:
        today_str = datetime.now().strftime('%Y%m%d')
        dated_filename = f"{recipe_name}_analysis_{today_str}.csv"
        dated_path = output_dir / dated_filename
        final_results.to_csv(dated_path, index=False, quoting=csv.QUOTE_MINIMAL)
        logger.info(f"Saved dated analysis to {dated_path}")
    
    # --- Save Cache ---
    # Update cache with new results
    cache_records = []
    for _, row in final_results.iterrows():
        if CLEANED_PHONE_COLUMN_NAME in row and CONVERSATION_DIGEST_COLUMN_NAME in row:
            phone = str(row[CLEANED_PHONE_COLUMN_NAME])
            digest = str(row[CONVERSATION_DIGEST_COLUMN_NAME])
            
            # Only add to cache if we have a valid phone and digest
            if phone and digest:
                cache_record = {CLEANED_PHONE_COLUMN_NAME: phone, CONVERSATION_DIGEST_COLUMN_NAME: digest}
                # Add all other columns
                for col in final_results.columns:
                    if col not in [CLEANED_PHONE_COLUMN_NAME, CONVERSATION_DIGEST_COLUMN_NAME]:
                        cache_record[col] = row[col]
                cache_records.append(cache_record)
    
    # Create cache DataFrame and save
    if cache_records:
        cache_df = pd.DataFrame(cache_records)
        cache_df.to_csv(cache_file, index=False, quoting=csv.QUOTE_MINIMAL)
        logger.info(f"Updated cache with {len(cache_records)} records")
    
    # --- Handle Ignored Records ---
    if not errors_df.empty:
        errors_df.to_csv(ignored_csv_path, index=False, quoting=csv.QUOTE_MINIMAL)
        update_link(ignored_csv_path, latest_ignored_path)
        logger.info(f"Saved {len(errors_df)} error records to {ignored_csv_path}")
    
    # --- Google Sheets Upload ---
    # Extract sheet info from meta.yml if available
    if gsheet_config and isinstance(gsheet_config, dict):
        sheet_id = gsheet_config.get("sheet_id")
        worksheet_name = gsheet_config.get("worksheet_name")
        
        if sheet_id and worksheet_name:
            try:
                credentials_path = settings.GOOGLE_CREDENTIALS_PATH
                logger.info(f"Uploading results for '{recipe_name}' to Google Sheet {sheet_id}, worksheet '{worksheet_name}'")
                upload_to_google_sheets(csv_output_path, sheet_id, worksheet_name, credentials_path)
                logger.info(f"Successfully uploaded to Google Sheets")
            except Exception as e:
                logger.error(f"Error uploading to Google Sheets: {str(e)}")
    
    return final_results 

def calculate_temporal_flags(conversation_history: pd.DataFrame, target_timezone_str: str = 'America/Mexico_City', skip_detailed_temporal: bool = False, skip_hours_minutes: bool = False, skip_reactivation_flags: bool = False, skip_timestamps: bool = False, skip_user_message_flag: bool = False) -> Dict[str, Any]:
    """Calculate temporal flags and deltas from a conversation history dataframe.
    
    This function analyzes the timestamps in a conversation history and returns
    time-related flags and values that can be passed to the LLM prompt.
    
    Args:
        conversation_history: DataFrame containing conversation messages.
                             Should have columns: 'creation_time', 'msg_from'.
        target_timezone_str: Timezone to convert timestamps to (default: 'America/Mexico_City')
        skip_detailed_temporal: If True, skips calculation of detailed hour/minute deltas
                                and window-based flags, returning only basic timestamp info.
        skip_hours_minutes: If True, skips calculation of hours and minutes since last message
        skip_reactivation_flags: If True, skips calculation of reactivation flags
        skip_timestamps: If True, skips calculation of timestamps
        skip_user_message_flag: If True, skips calculation of hours and minutes since last user message
        
    Returns:
        Dictionary containing temporal flags.
    """
    # Log the skip flag for debugging
    logger.debug(f"calculate_temporal_flags called with skip_detailed_temporal={skip_detailed_temporal}")
    
    # Return minimal data if skip_detailed_temporal is True
    if skip_detailed_temporal:
        logger.debug("Skipping temporal flags calculation due to skip_detailed_temporal=True")
        return {
            "HOURS_MINUTES_SINCE_LAST_USER_MESSAGE": None, 
            "HOURS_MINUTES_SINCE_LAST_MESSAGE": None,
            "IS_WITHIN_REACTIVATION_WINDOW": False,
            "IS_RECOVERY_PHASE_ELIGIBLE": False,
            "LAST_USER_MESSAGE_TIMESTAMP_TZ": None,
            "LAST_MESSAGE_TIMESTAMP_TZ": None,
            "NO_USER_MESSAGES_EXIST": True
        }
    
    # Initialize default return values
    result = {
        "HOURS_MINUTES_SINCE_LAST_USER_MESSAGE": None, 
        "HOURS_MINUTES_SINCE_LAST_MESSAGE": None,
        "IS_WITHIN_REACTIVATION_WINDOW": False,
        "IS_RECOVERY_PHASE_ELIGIBLE": False,
        "LAST_USER_MESSAGE_TIMESTAMP_TZ": None,
        "LAST_MESSAGE_TIMESTAMP_TZ": None,
        "NO_USER_MESSAGES_EXIST": True  # Default to True (no user messages)
    }
    
    if conversation_history.empty or 'creation_time' not in conversation_history.columns or 'msg_from' not in conversation_history.columns:
        logger.warning("Cannot calculate temporal flags: conversation history is empty or missing required columns")
        return result
    
    try:
        target_tz = pytz.timezone(target_timezone_str)
        now = datetime.now(target_tz)
        
        conversation_history = conversation_history.copy()
        conversation_history['creation_time_dt'] = pd.to_datetime(conversation_history['creation_time'], errors='coerce')
        
        valid_times = conversation_history.dropna(subset=['creation_time_dt'])
        if valid_times.empty:
            logger.warning("No valid timestamps found in conversation history")
            return result
        
        valid_times = valid_times.sort_values('creation_time_dt')
        
        last_message = valid_times.iloc[-1]
        last_message_ts = last_message['creation_time_dt']
        if last_message_ts.tzinfo is None:
            last_message_ts = last_message_ts.tz_localize('UTC')
        last_message_ts_tz = last_message_ts.astimezone(target_tz)
        result["LAST_MESSAGE_TIMESTAMP_TZ"] = last_message_ts_tz.isoformat()
        
        user_messages = valid_times[valid_times['msg_from'].str.lower() == 'user']
        result["NO_USER_MESSAGES_EXIST"] = user_messages.empty

        if skip_detailed_temporal:
            # If skipping, we've already populated LAST_MESSAGE_TIMESTAMP_TZ and NO_USER_MESSAGES_EXIST.
            # We might still want LAST_USER_MESSAGE_TIMESTAMP_TZ if user messages exist.
            if not result["NO_USER_MESSAGES_EXIST"]:
                last_user_message = user_messages.iloc[-1]
                last_user_message_ts = last_user_message['creation_time_dt']
                if last_user_message_ts.tzinfo is None:
                    last_user_message_ts = last_user_message_ts.tz_localize('UTC')
                last_user_message_ts_tz = last_user_message_ts.astimezone(target_tz)
                result["LAST_USER_MESSAGE_TIMESTAMP_TZ"] = last_user_message_ts_tz.isoformat()
            return result # Return early with basic flags

        # --- Full detailed temporal calculations (if not skipped) ---
        delta = now - last_message_ts_tz
        total_seconds = delta.total_seconds()
        hours_since_last = total_seconds / 3600
        hours = int(hours_since_last)
        minutes = int((hours_since_last - hours) * 60)
        result["HOURS_MINUTES_SINCE_LAST_MESSAGE"] = f"{hours}h {minutes}m"
        
        if not result["NO_USER_MESSAGES_EXIST"]:
            last_user_message = user_messages.iloc[-1]
            last_user_message_ts = last_user_message['creation_time_dt']
            if last_user_message_ts.tzinfo is None:
                last_user_message_ts = last_user_message_ts.tz_localize('UTC')
            last_user_message_ts_tz = last_user_message_ts.astimezone(target_tz)
            result["LAST_USER_MESSAGE_TIMESTAMP_TZ"] = last_user_message_ts_tz.isoformat()
            
            delta_user = now - last_user_message_ts_tz
            total_seconds_user = delta_user.total_seconds()
            hours_since_last_user = total_seconds_user / 3600
            user_hours = int(hours_since_last_user)
            user_minutes = int((hours_since_last_user - user_hours) * 60)
            result["HOURS_MINUTES_SINCE_LAST_USER_MESSAGE"] = f"{user_hours}h {user_minutes}m"
            
            result["IS_WITHIN_REACTIVATION_WINDOW"] = hours_since_last_user < 24
            result["IS_RECOVERY_PHASE_ELIGIBLE"] = hours_since_last_user >= 24
        
        return result
    
    except Exception as e:
        logger.error(f"Error calculating temporal flags: {e}", exc_info=True)
        # Return the initialized dict with whatever could be populated if an error occurs mid-way
        return result 