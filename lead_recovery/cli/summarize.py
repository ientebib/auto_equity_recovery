"""CLI command for summarizing conversations using OpenAI."""
from pathlib import Path
from typing import Optional, List, Dict, Any
import asyncio
import logging
import json

import typer

from ..config import settings
from ..exceptions import LeadRecoveryError
from ..analysis import run_summarization_step

logger = logging.getLogger(__name__)

app = typer.Typer()

@app.callback(invoke_without_command=True)
def summarize(
    output_dir: Path = typer.Option(settings.OUTPUT_DIR, "--output-dir"),
    prompt_template_path: Optional[Path] = typer.Option(None, "--prompt-template", help="Custom prompt template"),
    max_workers: Optional[int] = typer.Option(None, "--max-workers", help="Max concurrent API calls"),
    recipe_name: Optional[str] = typer.Option(None, "--recipe-name", help="Recipe name for output files"),
    use_cache: bool = typer.Option(True, "--use-cache/--no-cache", help="Use summarization cache if available"),
    gsheet_config: Optional[str] = typer.Option(None, hidden=True, help="Internal use only"),
    meta_config: Optional[str] = typer.Option(None, hidden=True, help="Serialized RecipeMeta from run.py"),
    include_columns: Optional[str] = typer.Option(None, help="Comma-separated list of columns to include"),
    exclude_columns: Optional[str] = typer.Option(None, help="Comma-separated list of columns to exclude"),
    skip_detailed_temporal: bool = typer.Option(False, hidden=True, help="Internal use: Skip detailed temporal calculations"),
    # Added: Allow expected keys to be passed directly (mainly for internal use by 'run')
    expected_yaml_keys_internal: Optional[List[str]] = typer.Option(None, hidden=True),
    limit: Optional[int] = typer.Option(None, help="Limit the number of conversations to process (for testing)"),
):
    """Create OpenAI summaries and merge with leads for reporting."""
    # Path handling
    output_dir = Path(output_dir)
    
    # Convert serialized dict strings back to dicts if provided
    gsheet_config_dict = None
    meta_config_dict = None
    
    if gsheet_config:
        try:
            gsheet_config_dict = json.loads(gsheet_config)
        except Exception as e:
            logger.warning(f"Failed to parse gsheet_config as JSON: {e}")
    
    # Parse meta_config as a JSON string
    if meta_config:
        try:
            meta_config_dict = json.loads(meta_config)
            # Check if this is a serialized RecipeMeta
            if meta_config_dict.get('__is_recipe_meta__'):
                logger.info(f"Using serialized RecipeMeta configuration")
        except Exception as e:
            logger.warning(f"Failed to parse meta_config as JSON: {e}")

    # Extract override options from meta_config_dict
    override_options = {}
    if isinstance(meta_config_dict, dict) and "override_options" in meta_config_dict:
        override_options = meta_config_dict.get("override_options", {})
    
    # Get specific skip flags from override_options, defaulting to False
    # These names must match the keys used in cli/run.py:override_options
    skip_temporal_flags_from_meta = override_options.get("skip_temporal_flags", False)
    skip_detailed_temporal_from_meta = override_options.get("skip_detailed_temporal", False)
    skip_hours_minutes_from_meta = override_options.get("skip_hours_minutes", False)
    skip_reactivation_flags_from_meta = override_options.get("skip_reactivation_flags", False)
    skip_timestamps_from_meta = override_options.get("skip_timestamps", False)
    skip_user_message_flag_from_meta = override_options.get("skip_user_message_flag", False)
    skip_handoff_detection_from_meta = override_options.get("skip_handoff_detection", False)
    skip_metadata_extraction_from_meta = override_options.get("skip_metadata_extraction", False)
    skip_handoff_invitation_from_meta = override_options.get("skip_handoff_invitation", False)
    skip_handoff_started_from_meta = override_options.get("skip_handoff_started", False)
    skip_handoff_finalized_from_meta = override_options.get("skip_handoff_finalized", False)
    skip_human_transfer_from_meta = override_options.get("skip_human_transfer", False)
    skip_recovery_template_detection_from_meta = override_options.get("skip_recovery_template_detection", False)
    skip_consecutive_templates_count_from_meta = override_options.get("skip_consecutive_templates_count", False)
    # Also get limit if it was passed via override_options
    limit_from_meta = override_options.get("limit", None)
    
    # Determine final limit (CLI option takes precedence)
    final_limit = limit if limit is not None else limit_from_meta

    # Handle include/exclude columns
    include_columns_list = None
    exclude_columns_list = None
    
    if include_columns:
        include_columns_list = include_columns.split(",")
    elif isinstance(meta_config_dict, dict) and "include_columns" in meta_config_dict:
        include_columns_list = meta_config_dict.get("include_columns")
    
    if exclude_columns:
        exclude_columns_list = exclude_columns.split(",")
    elif isinstance(meta_config_dict, dict) and "exclude_columns" in meta_config_dict:
        exclude_columns_list = meta_config_dict.get("exclude_columns")

    # Run the summarization step
    try:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        loop.run_until_complete(
            run_summarization_step(
                output_dir=output_dir,
                prompt_template_path=prompt_template_path,
                max_workers=max_workers,
                recipe_name=recipe_name,
                use_cache=use_cache,
                gsheet_config=gsheet_config_dict,
                meta_config=meta_config_dict,
                include_columns=include_columns_list,
                exclude_columns=exclude_columns_list,
                skip_detailed_temporal_calc=skip_detailed_temporal_from_meta,
                skip_hours_minutes=skip_hours_minutes_from_meta,
                skip_reactivation_flags=skip_reactivation_flags_from_meta,
                skip_timestamps=skip_timestamps_from_meta,
                skip_user_message_flag=skip_user_message_flag_from_meta,
                skip_handoff_detection=skip_handoff_detection_from_meta,
                skip_metadata_extraction=skip_metadata_extraction_from_meta,
                skip_handoff_invitation=skip_handoff_invitation_from_meta,
                skip_handoff_started=skip_handoff_started_from_meta,
                skip_handoff_finalized=skip_handoff_finalized_from_meta,
                skip_human_transfer=skip_human_transfer_from_meta,
                skip_recovery_template_detection=skip_recovery_template_detection_from_meta,
                skip_consecutive_templates_count=skip_consecutive_templates_count_from_meta,
                limit=final_limit
            )
        )
        
        logger.info("Summarization command finished.")
    except Exception as e:
        logger.error(f"Error in summarization step: {e}", exc_info=True)
        raise typer.Exit(1) 