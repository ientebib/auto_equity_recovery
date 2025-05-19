"""analysis.py
Core orchestration module for the lead recovery pipeline.

This module is responsible for orchestrating the entire lead processing flow:
1. Loading data from conversations and leads
2. Running all configured processors via ProcessorRunner
3. Calling the LLM via ConversationSummarizer
4. Validating and fixing outputs via YamlValidator
5. Writing results to output files
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from .cache import SummaryCache, compute_conversation_digest
from .config import settings
from .constants import (
    CLEANED_PHONE_COLUMN_NAME,
    MESSAGE_COLUMN_NAME,
)
from .exceptions import ApiError, LeadRecoveryError, RecipeConfigurationError, ValidationError
from .fs import update_link
from .gsheets import upload_to_google_sheets
from .processor_runner import ProcessorRunner
from .reporting import export_data, to_csv
from .summarizer import ConversationSummarizer
from .utils import log_memory_usage, optimize_dataframe
from .yaml_validator import YamlValidator

logger = logging.getLogger(__name__)

# Define missing constant
SENDER_COLUMN_NAME = "msg_from"

async def run_summarization_step(
    output_dir: Path,
    prompt_template_path: Optional[Path] = None,
    max_workers: Optional[int] = None,
    recipe_name: Optional[str] = None,
    use_cache: bool = True,
    gsheet_config: Optional[Dict[str, str]] = None,
    meta_config: Optional[Dict[str, Any]] = None,
    include_columns: Optional[List[str]] = None,
    exclude_columns: Optional[List[str]] = None,
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
    skip_pre_validacion_detection: bool = False, 
    skip_conversation_state: bool = False,
    limit: Optional[int] = None
):
    """Run the conversation summarization pipeline.
    
    This function is the primary orchestrator for the lead recovery pipeline. It:
    1. Loads conversation and lead data from files
    2. Initializes the ProcessorRunner with meta_config
    3. Processes each lead's conversations with all configured processors
    4. Calls the LLM via ConversationSummarizer for each lead
    5. Validates responses with YamlValidator
    6. Merges results with lead data
    7. Saves results to files and optionally uploads to Google Sheets
    
    Args:
        output_dir: Directory containing conversations and where to write summaries.
        prompt_template_path: Custom prompt template path.
        max_workers: Maximum concurrent LLM API calls.
        recipe_name: Recipe name for output files.
        use_cache: Whether to use cached summaries.
        gsheet_config: Google Sheets configuration.
        meta_config: Dictionary containing serialized RecipeMeta configuration.
        include_columns: List of columns to include in output.
        exclude_columns: List of columns to exclude from output.
        skip_*: Various flags to control which processors and analyses to run.
        limit: Maximum number of conversations to process (for testing).
        
    Returns:
        DataFrame with analysis results.
    """
    # ========== SETUP PHASE ==========
    # Ensure the output directory exists
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Check required files exist
    conversations_file = output_dir / "conversations.csv"
    leads_file = output_dir / "leads.csv"
    
    if not conversations_file.exists():
        raise LeadRecoveryError("Conversations file not found. Run fetch-convos first.")
    
    if not leads_file.exists():
        raise LeadRecoveryError("Leads file not found. Run fetch-convos first.")
    
    # Set up cache 
    cache = None
    cached_results = {}
    conversation_digests = {}
    
    if use_cache:
        cache = SummaryCache(output_dir)
        cached_results = await cache.load_all_cached_results() if hasattr(cache, 'load_all_cached_results') else {}
        conversation_digests = {k: v.get("conversation_digest", "") for k, v in cached_results.items()}
    
    # Log all skip flags for debugging
    logger.info("--- Skip Flag Configuration ---")
    logger.info(f"skip_detailed_temporal_calc = {skip_detailed_temporal_calc}")
    logger.info(f"skip_hours_minutes = {skip_hours_minutes}")
    logger.info(f"skip_reactivation_flags = {skip_reactivation_flags}")
    logger.info(f"skip_timestamps = {skip_timestamps}")
    logger.info(f"skip_user_message_flag = {skip_user_message_flag}")
    logger.info(f"skip_handoff_detection = {skip_handoff_detection}")
    logger.info(f"skip_metadata_extraction = {skip_metadata_extraction}")
    logger.info(f"skip_handoff_invitation = {skip_handoff_invitation}")
    logger.info(f"skip_handoff_started = {skip_handoff_started}")
    logger.info(f"skip_handoff_finalized = {skip_handoff_finalized}")
    logger.info(f"skip_human_transfer = {skip_human_transfer}")
    logger.info(f"skip_recovery_template_detection = {skip_recovery_template_detection}")
    logger.info(f"skip_consecutive_templates_count = {skip_consecutive_templates_count}")
    logger.info(f"skip_pre_validacion_detection = {skip_pre_validacion_detection}")
    logger.info(f"skip_conversation_state = {skip_conversation_state}")
    logger.info("---------------------------")

    # Apply limit from meta_config if not specified via CLI
    if limit is None and meta_config and 'limit' in meta_config and meta_config['limit'] is not None:
        limit = meta_config['limit']
        logger.info(f"Using conversation limit from meta_config: {limit}")
    
    # ========== PROCESSOR INITIALIZATION ==========
    # Initialize ProcessorRunner from meta_config (strict policy)
    processor_runner = None
    if recipe_name:
        try:
            if not (meta_config and isinstance(meta_config, dict) and meta_config.get('python_processors') is not None):
                error_msg = "CRITICAL: Valid recipe configuration (meta_config dict) was not properly passed to analysis.py"
                logger.error(error_msg)
                raise RecipeConfigurationError("Invalid or missing meta_config in analysis.py")
            
            logger.info(f"Initializing ProcessorRunner with config from meta_config for recipe: {meta_config.get('recipe_name')}")
            processor_runner = ProcessorRunner(recipe_config=meta_config)
            logger.info(f"ProcessorRunner loaded with processors: {[p.__class__.__name__ for p in processor_runner.processors]}")
        except Exception as e:
            logger.error(f"Error initializing ProcessorRunner: {e}", exc_info=True)
            raise RecipeConfigurationError(f"Failed to initialize ProcessorRunner: {e}") from e
    
    # Use output_columns from meta_config if present
    if meta_config and 'output_columns' in meta_config:
        output_columns = meta_config['output_columns']
    else:
        output_columns = None  # Or set a sensible default if needed
    
    # Calculate effective skip flags (can be used for processor logic, but not for columns)
    effective_skip_temporal_flags = (
        skip_detailed_temporal_calc and
        skip_hours_minutes and
        skip_reactivation_flags and
        skip_timestamps and
        skip_user_message_flag
    )
    
    # Removed deprecated python_flag_columns logic
    
    # ========== DATA LOADING ==========
    # Load conversation and lead data
    log_memory_usage("Before loading data: ")
    
    try:
        # Load conversations with chunks for large files
        convos_reader = pd.read_csv(conversations_file, chunksize=100000)
        convos_df = pd.concat(convos_reader, ignore_index=True)
        convos_df = optimize_dataframe(convos_df)
        
        # Load leads
        leads_df = pd.read_csv(leads_file)
        leads_df = optimize_dataframe(leads_df)
        
        logger.info(f"Loaded {len(convos_df)} conversation messages and {len(leads_df)} leads")
        
        # Handle column renames from DB layer
        if "cleaned_phone_number" in convos_df.columns and CLEANED_PHONE_COLUMN_NAME not in convos_df.columns:
            convos_df.rename(columns={"cleaned_phone_number": CLEANED_PHONE_COLUMN_NAME}, inplace=True)
        
        # ------------------------------------------------------------
        # NORMALISE PHONE NUMBER COLUMNS (critical for join matching)
        # ------------------------------------------------------------
        # Ensure both DataFrames use consistent string dtype with no
        # leading/trailing whitespace so that phone keys actually match
        # during grouping and later lookup. Inconsistent dtypes (e.g.
        # pandas StringArray versus plain Python str) or stray spaces
        # were causing valid conversations to be missed, leading to the
        # observed "No conversation data found" issue.

        def _normalise_phone_series(s):
            # Cast to str, strip, keep exactly 10 digit numbers.
            s = s.astype(str).str.strip()
            s = s.str.extract(r"(\d{10})")[0]  # NaN for invalid rows
            return s

        leads_df[CLEANED_PHONE_COLUMN_NAME] = _normalise_phone_series(leads_df[CLEANED_PHONE_COLUMN_NAME])
        convos_df[CLEANED_PHONE_COLUMN_NAME] = _normalise_phone_series(convos_df[CLEANED_PHONE_COLUMN_NAME])

        # Drop any rows with invalid phone after normalisation
        leads_df.dropna(subset=[CLEANED_PHONE_COLUMN_NAME], inplace=True)
        convos_df.dropna(subset=[CLEANED_PHONE_COLUMN_NAME], inplace=True)
        
        # Validate required columns
        if CLEANED_PHONE_COLUMN_NAME not in convos_df.columns and not convos_df.empty:
            raise ValueError(f"Conversation data missing required column: {CLEANED_PHONE_COLUMN_NAME}")
        
        # Check for required columns only if there are conversations
        if not convos_df.empty:
            REQUIRED_CONVO_COLUMNS = {"creation_time", "msg_from", MESSAGE_COLUMN_NAME, CLEANED_PHONE_COLUMN_NAME}
            missing_columns = REQUIRED_CONVO_COLUMNS - set(convos_df.columns)
            if missing_columns:
                raise LeadRecoveryError(f"Conversation data missing required columns: {missing_columns}")
        
        # Check for empty data
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
            return result_df
        
        # Group conversations by phone number
        phone_groups = convos_df.groupby(CLEANED_PHONE_COLUMN_NAME)
        logger.info(f"Found {len(phone_groups)} unique phone numbers in conversations")
        
        # Apply limit if specified
        if limit is not None and limit > 0:
            phone_numbers = list(phone_groups.groups.keys())[:limit]
            logger.info(f"Limiting processing to {limit} phone numbers")
            # Create a new groupby object with only the limited phones
            filter_mask = convos_df[CLEANED_PHONE_COLUMN_NAME].isin(phone_numbers)
            convos_df = convos_df[filter_mask]
            phone_groups = convos_df.groupby(CLEANED_PHONE_COLUMN_NAME)
        
        # ========== LLM SETUP ==========
        # Create summarizer instance
        summarizer = ConversationSummarizer(
            prompt_template_path=prompt_template_path,
            use_cache=use_cache,
            meta_config=meta_config
        )
        
        # Create validator instance
        yaml_validator = YamlValidator(meta_config=meta_config)
        
        # Determine concurrency
        if max_workers is None:
            max_workers = min(32, max(4, os.cpu_count() or 4))
        logger.info(f"Using max_workers={max_workers} for concurrent processing")
        
        # ========== CONVERSATION PROCESSING ==========
        # Prepare for parallel processing
        total = len(phone_groups)
        completed = 0
        summaries = {}
        errors = {}
        
        # Use semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_workers)
        
        async def process_conversation(phone: str, conv_df: pd.DataFrame) -> None:
            """Process a single conversation with retry logic for semaphore timeouts."""
            nonlocal completed
            max_retries = 3
            retry_delay = 5  # seconds
            attempt = 0
            semaphore_acquired = False  # Track if semaphore was acquired
            while attempt < max_retries:
                attempt += 1
                try:
                    # Try to acquire semaphore with timeout to prevent deadlocks
                    try:
                        await asyncio.wait_for(semaphore.acquire(), timeout=300)
                        semaphore_acquired = True
                        logger.debug(f"Acquired semaphore for phone {phone} (attempt {attempt})")
                    except asyncio.TimeoutError:
                        logger.error(f"Timed out waiting for semaphore for phone {phone} (attempt {attempt})")
                        if attempt < max_retries:
                            logger.info(f"Retrying phone {phone} after {retry_delay}s (attempt {attempt+1}/{max_retries})")
                            await asyncio.sleep(retry_delay)
                            continue
                        summaries[phone] = {
                            "summary": "ERROR: Timed out waiting to acquire processing slot after retries.",
                            "inferred_stall_stage": "ERROR_TIMEOUT",
                            "primary_stall_reason_code": "ERROR_SEMAPHORE_TIMEOUT",
                            "next_action_code": "ERROR_RETRY_FAILED",
                        }
                        break
                    try:
                        # just run summarization as normal
                        # Check for cached results first
                        conversation_text = "\n".join(
                            f"{getattr(row, 'creation_time', '')[:19]} {getattr(row, 'msg_from', '')}: {getattr(row, 'message', '')}"
                            for row in conv_df.itertuples(index=False)
                        )
                        digest = compute_conversation_digest(conversation_text)  # Always define digest
                        if use_cache and phone in cached_results:
                            cached_digest = conversation_digests.get(phone)
                            if cached_digest == digest:
                                logger.debug(f"Using cached result for phone {phone}")
                                summaries[phone] = cached_results[phone]
                                break
                        # STEP 1: Run processors to generate context for LLM
                        processor_results = {}
                        if processor_runner is not None:
                            try:
                                lead_data = pd.Series({"phone": phone}, name=phone)
                                processor_results = processor_runner.run_all(
                                    lead_data=lead_data,
                                    conversation_data=conv_df,
                                    initial_results={}
                                )
                                if completed == 0:
                                    print(f"[DEBUG] Processor results for {phone}: {processor_results}")
                                logger.debug(f"ProcessorRunner results for {phone}: {list(processor_results.keys())}")
                            except Exception as e:
                                logger.error(f"Error running processors for {phone}: {e}", exc_info=True)
                                processor_results = {}  # Use empty results on error
                        # STEP 2: Call LLM for summarization
                        llm_result = await summarizer.summarize(
                            conv_df.copy(),
                            temporal_flags=processor_results  # Pass processor results to LLM
                        )
                        if completed == 0:
                            print(f"[DEBUG] LLM result for {phone}: {llm_result}")
                        # STEP 3: Validate and fix LLM output
                        validated_result = yaml_validator.fix_yaml(
                            llm_result, 
                            temporal_flags=processor_results
                        )
                        # --- PATCH: Split embedded YAML fields if present ---
                        if validated_result is not None:
                            for key, value in list(validated_result.items()):
                                if isinstance(value, str) and '\n' in value and ':' in value:
                                    import yaml
                                    try:
                                        extra = yaml.safe_load(value)
                                        if isinstance(extra, dict):
                                            validated_result.pop(key)
                                            validated_result.update(extra)
                                    except Exception:
                                        pass
                        # --- END PATCH ---
                        if validated_result is None:
                            logger.error(f"Summarization failed for phone {phone}")
                            summaries[phone] = {
                                "summary": "ERROR: LLM summarization failed.",
                                "inferred_stall_stage": "ERROR_LLM_NONE",
                                "primary_stall_reason_code": "ERROR_LLM_NONE",
                                "next_action_code": "ERROR_LLM_NONE",
                            }
                            summaries[phone].update(processor_results)
                        else:
                            combined_result = {**validated_result, **processor_results}
                            combined_result[CLEANED_PHONE_COLUMN_NAME] = phone
                            combined_result["conversation_digest"] = digest
                            combined_result["cache_status"] = "FRESH"
                            summaries[phone] = combined_result
                        break  # Success, exit retry loop
                    except (ApiError, ValidationError) as e:
                        logger.error(f"API/Validation error for phone {phone}: {e}", exc_info=True)
                        errors[phone] = str(e)
                        summaries[phone] = {
                            "summary": f"ERROR: {type(e).__name__} during processing.",
                            "error_details": str(e),
                            "inferred_stall_stage": "ERROR_PROCESSING",
                            "primary_stall_reason_code": "ERROR_PROCESSING",
                            "next_action_code": "ERROR_PROCESSING",
                        }
                        break
                    except Exception as e:
                        logger.error(f"Unexpected error for phone {phone}: {e}", exc_info=True)
                        errors[phone] = f"Unexpected error: {e}"
                        summaries[phone] = {
                            "summary": f"ERROR: Unexpected {type(e).__name__}.",
                            "error_details": str(e),
                            "inferred_stall_stage": "ERROR_UNEXPECTED",
                            "primary_stall_reason_code": "ERROR_UNEXPECTED",
                            "next_action_code": "ERROR_UNEXPECTED",
                        }
                        break
                    finally:
                        if semaphore_acquired:
                            semaphore.release()
                            semaphore_acquired = False
                        logger.debug(f"Released semaphore for phone {phone}")
                finally:
                    completed += 1  # Only increment once per task
                    if completed % 10 == 0 or completed == total:
                        logger.info(f"Progress: {completed}/{total} ({completed/total:.1%})")
        
        # Create and run tasks for all phone numbers
        tasks = []
        for phone, group in phone_groups:
            tasks.append(asyncio.create_task(process_conversation(phone, group)))
        
        # Wait for all tasks to complete
        await asyncio.gather(*tasks)
        
        log_memory_usage("After processing all conversations: ")
        
        # ========== RESULT PREPARATION ==========
        # Merge results with leads data
        result_rows = []
        for _, lead in leads_df.iterrows():
            phone = lead[CLEANED_PHONE_COLUMN_NAME]
            row_data = lead.to_dict()
            
            if phone in summaries:
                row_data.update(summaries[phone])
            elif phone in errors:
                row_data["error"] = errors[phone]
            else:
                row_data["summary"] = "No conversation data found"
            
            if len(result_rows) == 0:
                print(f"[DEBUG] Final row_data for {phone}: {row_data}")
            result_rows.append(row_data)
        
        # Create final DataFrame
        result_df = pd.DataFrame(result_rows)
        result_df = optimize_dataframe(result_df)
        
        # Apply column filtering from meta_config
        include_cols = meta_config.get('include_columns', []) if meta_config else []
        exclude_cols = meta_config.get('exclude_columns', []) if meta_config else []
        
        # Override with function arguments if provided
        if include_columns:
            include_cols = include_columns
        if exclude_columns:
            exclude_cols = exclude_columns
            
        # Apply column filtering
        if include_cols:
            # Always include phone number
            essential_cols = {CLEANED_PHONE_COLUMN_NAME}
            cols_to_include = [col for col in include_cols if col in result_df.columns]
            
            # Add essential columns if not already included
            for col in essential_cols:
                if col not in cols_to_include and col in result_df.columns:
                    cols_to_include.insert(0, col)
                    
            result_df = result_df[cols_to_include]
            logger.info(f"Applied include_columns filter: {cols_to_include}")
            
        if exclude_cols:
            # Never exclude phone number
            cols_to_exclude = [col for col in exclude_cols if col != CLEANED_PHONE_COLUMN_NAME]
            result_df = result_df.drop(columns=cols_to_exclude, errors='ignore')
            logger.info(f"Applied exclude_columns filter: {cols_to_exclude}")
        
        # Ensure all output_columns exist in result_df, even if empty
        if output_columns:
            for col in output_columns:
                if col not in result_df.columns:
                    result_df[col] = ""
        
        # ========== OUTPUT ==========
        # Prepare output path and filename
        today_str = datetime.now().strftime('%Y%m%d')
        output_filename = f"{recipe_name}_analysis_{today_str}"
        
        # Save to multiple formats if configured in meta_config
        export_formats = ["csv"]  # Always export CSV as the base format
        if meta_config and isinstance(meta_config, dict):
            # Check if export_formats is specified in meta_config
            if "export_formats" in meta_config:
                config_formats = meta_config["export_formats"]
                if isinstance(config_formats, list):
                    # Add any valid formats that aren't already included
                    for fmt in config_formats:
                        if fmt.lower() in ["json"] and fmt.lower() not in export_formats:
                            export_formats.append(fmt.lower())
                elif isinstance(config_formats, str) and config_formats.lower() in ["json", "all"]:
                    if config_formats.lower() == "all":
                        export_formats = ["csv", "json"]
                    elif config_formats.lower() not in export_formats:
                        export_formats.append(config_formats.lower())
        
        # Export to all specified formats
        try:
            export_paths = export_data(
                df=result_df,
                output_dir=output_dir,
                base_name=output_filename,
                formats=export_formats,
                columns=output_columns
            )
            
            if "csv" in export_paths:
                output_path = export_paths["csv"]
                logger.info(f"Analysis saved to {output_path}")
            else:
                # Fallback if CSV export somehow failed
                output_path = output_dir / f"{output_filename}.csv"
                logger.warning(f"CSV export path not found in results, using {output_path}")
        except Exception as e:
            # Fallback to direct CSV export if the unified function fails
            logger.error(f"Error using unified export: {e}, falling back to direct CSV export")
            output_path = output_dir / f"{output_filename}.csv"
            to_csv(result_df, output_path)
            logger.info(f"Analysis saved to {output_path}")
        
        # Create a timestamped output directory
        run_ts = datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%dT%H-%M')
        run_dir = output_dir / run_ts
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # Save detailed outputs to the timestamped directory with all enabled formats
        dated_output_paths = {}  # Initialize with empty dict to prevent undefined variable issues
        try:
            dated_output_paths = export_data(
                df=result_df,
                output_dir=run_dir,
                base_name="analysis",
                formats=export_formats,
                columns=output_columns
            )
            
            if "csv" in dated_output_paths:
                dated_output_path = dated_output_paths["csv"]
            else:
                # Fallback if CSV export failed
                dated_output_path = run_dir / "analysis.csv"
                to_csv(result_df, dated_output_path)
                dated_output_paths["csv"] = dated_output_path
        except Exception as e:
            # Fallback to direct CSV if unified export fails
            logger.error(f"Error using unified export for dated output: {e}, falling back to direct CSV")
            dated_output_path = run_dir / "analysis.csv"
            to_csv(result_df, dated_output_path)
            dated_output_paths["csv"] = dated_output_path
        
        # Create symlinks to latest results
        latest_csv_path = output_dir / "latest.csv"
        update_link(dated_output_path, latest_csv_path)
        logger.info(f"Updated symlink {latest_csv_path} -> {dated_output_path}")
        
        # Create symlinks for other formats if they were successfully exported
        if "json" in dated_output_paths:
            latest_json_path = output_dir / "latest.json"
            update_link(dated_output_paths["json"], latest_json_path)
            logger.info(f"Updated symlink {latest_json_path} -> {dated_output_paths['json']}")
        
        # Save errors if any
        if errors:
            ignored_csv_path = run_dir / "ignored.csv"
            latest_ignored_path = output_dir / "latest_ignored.csv"
            
            error_rows = []
            for phone, error_msg in errors.items():
                error_rows.append({
                    CLEANED_PHONE_COLUMN_NAME: phone,
                    "error": error_msg,
                    "cache_status": "ERROR"
                })
            
            pd.DataFrame(error_rows).to_csv(ignored_csv_path, index=False)
            update_link(ignored_csv_path, latest_ignored_path)
            logger.info(f"Saved {len(errors)} error records to {ignored_csv_path}")
        
        # Update cache
        if use_cache and cache:
            cache_records = []
            for phone, data in summaries.items():
                if "conversation_digest" in data:
                    cache_records.append(data)
                    
            if cache_records:
                cache_df = pd.DataFrame(cache_records)
                cache_path = output_dir / "cache.csv"
                cache_df.to_csv(cache_path, index=False)
                logger.info(f"Updated cache with {len(cache_records)} records")
        
        # Upload to Google Sheets if configured
        if gsheet_config and isinstance(gsheet_config, dict):
            sheet_id = gsheet_config.get("sheet_id")
            worksheet_name = gsheet_config.get("worksheet_name")
            
            if sheet_id and worksheet_name:
                try:
                    credentials_path = settings.GOOGLE_CREDENTIALS_PATH
                    logger.info(f"Uploading results to Google Sheet {sheet_id}, worksheet '{worksheet_name}'")
                    
                    # Prefer JSON format if available for better data preservation
                    if "json" in dated_output_paths:
                        logger.info("Using JSON format for Google Sheets upload (better data type preservation)")
                        upload_path = dated_output_paths["json"]
                    else:
                        upload_path = latest_csv_path
                    
                    upload_to_google_sheets(upload_path, sheet_id, worksheet_name, credentials_path)
                    logger.info("Successfully uploaded to Google Sheets")
                except Exception as e:
                    logger.error(f"Error uploading to Google Sheets: {e}")
        
        return result_df
        
    except Exception as e:
        logger.exception(f"Error in summarization step: {e}")
        raise LeadRecoveryError(f"Summarization failed: {e}") from e