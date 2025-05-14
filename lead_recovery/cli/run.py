"""CLI command for running the full lead recovery pipeline."""
import os
import logging
import importlib
from pathlib import Path
from typing import Optional, List
from datetime import datetime
import json

import typer
import yaml

from ..config import settings
from ..exceptions import RecipeNotFoundError
from .fetch_leads import fetch_leads
from .fetch_convos import fetch_convos
from .summarize import summarize
from .report import report

logger = logging.getLogger(__name__)

app = typer.Typer()

def check_redshift_marker(recipe: str) -> tuple:
    """Check if Redshift has been queried today for this recipe.
    
    Args:
        recipe: Name of the recipe to check
        
    Returns:
        Tuple of (exists, marker_path)
    """
    today = datetime.now().strftime('%Y%m%d')
    marker_path = Path(f"redshift_queried_{recipe}_{today}.marker")
    return marker_path.exists(), marker_path

def create_redshift_marker(recipe: str) -> Path:
    """Create a marker file indicating Redshift was queried today.
    
    Args:
        recipe: Name of the recipe
        
    Returns:
        Path to the created marker file
    """
    today = datetime.now().strftime('%Y%m%d')
    marker_path = Path(f"redshift_queried_{recipe}_{today}.marker")
    
    # Create marker with timestamp inside
    with open(marker_path, "w") as f:
        f.write(f"Redshift queried for {recipe} at {datetime.now().isoformat()}")
    
    logger.info(f"Created Redshift marker: {marker_path}")
    return marker_path

def setup_environment():
    """Set up environment variables needed for the pipeline"""
    # Set service account credentials path if not already set
    credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    
    if not credentials_path:
        logger.error("GOOGLE_APPLICATION_CREDENTIALS not set in environment or .env")
        return False
    
    if not os.path.exists(credentials_path):
        logger.error(f"Credentials file not found at {credentials_path}")
        return False
        
    logger.info(f"Using GOOGLE_APPLICATION_CREDENTIALS: {credentials_path}")
    return True

@app.callback(invoke_without_command=True)
def run_pipeline(
    recipe: str = typer.Option(..., help="Recipe name (folder name under recipes/)"),
    skip_redshift: bool = typer.Option(False, help="Skip fetching leads from Redshift"),
    skip_bigquery: bool = typer.Option(False, help="Skip fetching conversations from BigQuery"),
    skip_summarize: bool = typer.Option(False, help="Skip summarizing conversations"),
    max_workers: Optional[int] = typer.Option(None, help="Max concurrent workers for OpenAI calls"),
    output_dir: Optional[str] = typer.Option(None, help="Override base output directory"),
    use_cached_redshift: bool = typer.Option(True, help="Use cached Redshift data if available"),
    use_cache: bool = typer.Option(True, "--use-cache/--no-cache", help="Use summarization cache if available."),
    ignore_redshift_marker: bool = typer.Option(False, "--ignore-redshift-marker", help="Ignore existing Redshift marker and run query even if already run today."),
    skip_temporal_flags: bool = typer.Option(False, help="Skip calculating temporal flags like hours since last message"),
    skip_detailed_temporal: bool = typer.Option(False, help="Skip detailed temporal processing (use simplified time calculations)"),
    skip_hours_minutes: bool = typer.Option(False, help="Skip hours/minutes calculations (HOURS_MINUTES_SINCE_LAST_USER_MESSAGE, HOURS_MINUTES_SINCE_LAST_MESSAGE)"),
    skip_reactivation_flags: bool = typer.Option(False, help="Skip reactivation flags (IS_WITHIN_REACTIVATION_WINDOW, IS_RECOVERY_PHASE_ELIGIBLE)"),
    skip_timestamps: bool = typer.Option(False, help="Skip timestamp formatting (LAST_USER_MESSAGE_TIMESTAMP_TZ, LAST_MESSAGE_TIMESTAMP_TZ)"),
    skip_user_message_flag: bool = typer.Option(False, help="Skip user flag (NO_USER_MESSAGES_EXIST)"),
    skip_handoff_detection: bool = typer.Option(False, help="Skip handoff detection in conversations"),
    skip_metadata_extraction: bool = typer.Option(False, help="Skip extraction of message metadata"),
    skip_handoff_invitation: bool = typer.Option(False, help="Skip handoff invitation detection"),
    skip_handoff_started: bool = typer.Option(False, help="Skip handoff started detection"),
    skip_handoff_finalized: bool = typer.Option(False, help="Skip handoff finalized detection"),
    skip_human_transfer: bool = typer.Option(False, help="Skip human transfer detection"),
    skip_recovery_template_detection: bool = typer.Option(False, help="Skip recovery template detection (simulation_to_handoff recipe)"),
    skip_consecutive_templates_count: bool = typer.Option(False, help="Skip counting consecutive recovery templates"),
    include_columns: Optional[str] = typer.Option(None, help="Comma-separated list of columns to include in the output"),
    exclude_columns: Optional[str] = typer.Option(None, help="Comma-separated list of columns to exclude from the output"),
    limit: Optional[int] = typer.Option(None, help="Limit the number of conversations to process (for testing)"),
):
    """Run the full pipeline for a recipe: fetch leads, fetch conversations, summarize."""
    # Path to recipe directory
    recipe_dir = Path(settings.PROJECT_ROOT) / "recipes" / recipe
    if not recipe_dir.exists():
        raise RecipeNotFoundError(f"Recipe directory '{recipe}' not found at: {recipe_dir}")

    # Set up environment and credentials
    if not setup_environment():
        logger.error("Environment setup failed")
        raise typer.Exit(1)

    # Optional log - who is running the script?
    try:
        import getpass
        logger.info("Running as user: %s", getpass.getuser())
    except Exception as e_user:  # Ignore errors
        logger.debug("Couldn't detect running user: %s", e_user)

    # Set the output directory, ensure it exists
    if output_dir is None:
        output_dir = Path(settings.OUTPUT_DIR) / recipe
    else:
        output_dir = Path(output_dir) / recipe
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Using output directory: {output_dir}")

    # Default SQL filenames
    default_redshift_sql_name = "redshift.sql"
    default_bigquery_sql_name = "bigquery.sql"
    default_prompt_name = "prompt.txt"

    # Initialize paths and schema
    redshift_sql_file_name = default_redshift_sql_name
    bigquery_sql_file_name = default_bigquery_sql_name
    prompt_file_name = default_prompt_name
    yaml_schema = None
    gsheet_config = None
    meta_yaml = {} # Ensure meta_yaml is a dict
    skip_detailed_temporal_processing_for_recipe = False # Default

    meta_path = recipe_dir / "meta.yml"
    if meta_path.exists():
        try:
            with open(meta_path, 'r') as f:
                loaded_meta_yaml = yaml.safe_load(f)
                if isinstance(loaded_meta_yaml, dict):
                    meta_yaml = loaded_meta_yaml
                    # Get SQL filenames from meta.yml if specified, else use defaults
                    redshift_sql_file_name = meta_yaml.get('redshift_sql', default_redshift_sql_name)
                    bigquery_sql_file_name = meta_yaml.get('bigquery_sql', default_bigquery_sql_name)
                    prompt_file_name = meta_yaml.get('prompt_file', default_prompt_name)

                    # Extract expected YAML keys for validation
                    yaml_schema = meta_yaml.get('expected_yaml_keys')
                    if isinstance(yaml_schema, list):
                        logger.info(f"Loaded {len(yaml_schema)} expected keys from meta.yml")
                    elif yaml_schema is not None: # If key exists but not a list
                        logger.warning("'expected_yaml_keys' in meta.yml is not a list, will be ignored.")
                        yaml_schema = None

                    # Extract Google Sheets information if present
                    sheets_info = meta_yaml.get('google_sheets')
                    if isinstance(sheets_info, dict):
                        sheet_id = sheets_info.get('sheet_id')
                        worksheet = sheets_info.get('worksheet_name') # Corrected key from previous diff
                        if sheet_id and worksheet:
                            gsheet_config = {"sheet_id": sheet_id, "worksheet_name": worksheet}
                            logger.info(f"Configured Google Sheets integration from meta.yml: {gsheet_config}")
                        else:
                            logger.debug("'google_sheets' in meta.yml is missing 'sheet_id' or 'worksheet_name'.")
                    elif sheets_info is not None:
                        logger.warning("'google_sheets' in meta.yml is not a dictionary.")

                    # NEW: Check for skip_detailed_temporal_processing flag
                    behavior_flags = meta_yaml.get('behavior_flags', {})
                    if isinstance(behavior_flags, dict):
                        skip_detailed_temporal_processing_for_recipe = behavior_flags.get('skip_detailed_temporal_processing', False)
                        # Override with CLI options if specified
                        if skip_detailed_temporal:
                            skip_detailed_temporal_processing_for_recipe = True
                            logger.info("Overriding recipe config: Skipping detailed temporal processing (CLI option)")

                        if skip_detailed_temporal_processing_for_recipe:
                            logger.info(f"Recipe {recipe} configured to skip detailed temporal processing.")
                    else:
                        logger.warning("'behavior_flags' in meta.yml is not a dictionary, will use defaults.")
                        # Still use CLI options if meta.yml format is invalid
                        if skip_detailed_temporal:
                            skip_detailed_temporal_processing_for_recipe = True
                            logger.info("Using CLI option: Skipping detailed temporal processing")
                else:
                    logger.warning(f"meta.yml for recipe {recipe} is not a valid YAML dictionary.")
        except Exception as e:
            logger.error(f"Error loading meta.yml for recipe {recipe}: {e}", exc_info=True)

    # Construct full paths to SQL and prompt files using names from meta.yml or defaults
    redshift_sql_path = recipe_dir / redshift_sql_file_name
    bigquery_sql_path = recipe_dir / bigquery_sql_file_name
    prompt_path = recipe_dir / prompt_file_name

    if redshift_sql_path.exists():
        settings.RS_SQL_PATH = redshift_sql_path
        logger.info(f"Using recipe Redshift SQL: {redshift_sql_path}")
    else:
        logger.warning(f"Redshift SQL file '{redshift_sql_path.name}' not found for recipe {recipe}. Downstream Redshift steps might fail or use incorrect defaults if not skipped.")
        # Decide if we should revert to a global default or error out if essential
        # For now, it will just use whatever was last in settings.RS_SQL_PATH (potentially from config.py defaults)

    if bigquery_sql_path.exists():
        settings.BQ_SQL_PATH = bigquery_sql_path
        logger.info(f"Using recipe BigQuery SQL: {bigquery_sql_path}")
    else:
        logger.warning(f"BigQuery SQL file '{bigquery_sql_path.name}' not found for recipe {recipe}. Downstream BigQuery steps might fail or use incorrect defaults if not skipped.")

    if not prompt_path.exists():
        prompt_path = None # Explicitly set to None if not found
        logger.warning(f"Prompt file '{prompt_file_name}' not found for recipe {recipe}. Summarization will use default prompt if available, or fail.")

    # Check for cached leads data
    leads_path = output_dir / "leads.csv"
    
    # --- (1) REDSHIFT --- fetch from Redshift if needed
    if skip_redshift:
        logger.info("Skipping Redshift step")
        if not leads_path.exists():
            logger.warning("Skipped Redshift but leads.csv does not exist. Downstream steps may fail.")
    else:
        # Check if Redshift query exists for this recipe
        has_redshift_query = redshift_sql_path.exists()
        if not has_redshift_query:
            # If the recipe doesn't have a redshift.sql file, automatically skip Redshift
            # This ensures recipes without Redshift don't create markers or try to run queries
            logger.info(f"No Redshift query file found for recipe {recipe}, skipping Redshift")
            skip_redshift = True
        else:
            # Check for today's marker unless explicitly ignored
            marker_exists, marker_path = check_redshift_marker(recipe)
            
            if marker_exists and not ignore_redshift_marker:
                logger.info(f"Redshift marker found for today ({marker_path}). Using cached Redshift data.")
                # Only skip if cached data exists
                if use_cached_redshift and leads_path.exists():
                    logger.info(f"Using cached leads data from {leads_path}")
                    skip_redshift = True
                else:
                    logger.info("Redshift marker exists but no cached leads data found. Will query Redshift.")
            else:
                if marker_exists and ignore_redshift_marker:
                    logger.info(f"Ignoring existing Redshift marker ({marker_path}) as requested.")
                    
                # If we get here, either:
                # 1. No marker exists for today, or
                # 2. Force flag is set to ignore the marker, or
                # 3. use_cached_redshift is False
                logger.info("Will query Redshift for fresh data.")
                
    # Perform the Redshift query if not skipped
    if not skip_redshift:
        try:
            logger.info("Fetching leads from Redshift...")
            fetch_leads(output_dir=output_dir)
            logger.info("Redshift fetch completed.")
            
            # Create a marker file to indicate successful Redshift query for today
            create_redshift_marker(recipe)
        except Exception as e:
            logger.error(f"Error fetching from Redshift: {e}", exc_info=True)
            # If this fails and we have cached data, try to use it
            if use_cached_redshift and leads_path.exists():
                logger.warning("Falling back to cached leads data after Redshift error")
            else:
                # No fallback available
                raise typer.Exit(1)

    # --- (2) BIGQUERY --- fetch conversations if needed
    if skip_bigquery:
        logger.info("Skipping BigQuery step")
        if not (output_dir / "conversations.csv").exists():
            logger.warning("Skipped BigQuery but conversations.csv does not exist. Downstream steps may fail.")
    else:
        logger.info("Fetching conversations from BigQuery...")
        fetch_convos(output_dir=output_dir, batch_size=settings.BQ_BATCH_SIZE)
        logger.info("BigQuery fetch completed.")

    # --- (3) SUMMARIZE --- run OpenAI summarization if needed
    if skip_summarize:
        logger.info("Skipping summarization step")
    else:
        logger.info("Starting summarization with OpenAI...")
        
        # Convert meta_yaml and gsheet_config to strings if they exist
        gsheet_config_str = json.dumps(gsheet_config) if gsheet_config else None
        meta_yaml_str = json.dumps(meta_yaml) if meta_yaml else None
        
        # Create options dictionary to override behavior flags
        override_options = {
            # If skip_temporal_flags is True, all temporal processing should be skipped
            # This sets all sub-flags to True when the master flag is True
            "skip_temporal_flags": skip_temporal_flags,
            "skip_detailed_temporal": skip_detailed_temporal or skip_temporal_flags,
            "skip_hours_minutes": skip_hours_minutes or skip_temporal_flags,
            "skip_reactivation_flags": skip_reactivation_flags or skip_temporal_flags,
            "skip_timestamps": skip_timestamps or skip_temporal_flags,
            "skip_user_message_flag": skip_user_message_flag or skip_temporal_flags,
            "skip_handoff_detection": skip_handoff_detection,
            "skip_metadata_extraction": skip_metadata_extraction,
            "skip_handoff_invitation": skip_handoff_invitation,
            "skip_handoff_started": skip_handoff_started,
            "skip_handoff_finalized": skip_handoff_finalized,
            "skip_human_transfer": skip_human_transfer,
            "skip_recovery_template_detection": skip_recovery_template_detection,
            "skip_consecutive_templates_count": skip_consecutive_templates_count,
            # Add limit option if provided
            "limit": limit
        }
        
        # Print the actual values of the flags for debugging
        logger.info(f"Flag values for override_options in run_pipeline:")
        logger.info(f"  - skip_temporal_flags: {skip_temporal_flags} (type: {type(skip_temporal_flags).__name__})")
        logger.info(f"  - skip_detailed_temporal: {override_options['skip_detailed_temporal']}")
        logger.info(f"  - skip_hours_minutes: {override_options['skip_hours_minutes']}")
        logger.info(f"  - skip_reactivation_flags: {override_options['skip_reactivation_flags']}")
        logger.info(f"  - skip_timestamps: {override_options['skip_timestamps']}")
        logger.info(f"  - skip_user_message_flag: {override_options['skip_user_message_flag']}")
        logger.info(f"  - skip_handoff_detection: {override_options['skip_handoff_detection']}")
        logger.info(f"  - skip_metadata_extraction: {override_options['skip_metadata_extraction']}")
        logger.info(f"  - skip_handoff_invitation: {override_options['skip_handoff_invitation']}")
        logger.info(f"  - skip_handoff_started: {override_options['skip_handoff_started']}")
        logger.info(f"  - skip_handoff_finalized: {override_options['skip_handoff_finalized']}")
        logger.info(f"  - skip_human_transfer: {override_options['skip_human_transfer']}")
        logger.info(f"  - skip_recovery_template_detection: {override_options['skip_recovery_template_detection']}")
        logger.info(f"  - skip_consecutive_templates_count: {override_options['skip_consecutive_templates_count']}")
        if limit:
            logger.info(f"  - limit: {limit} (will only process {limit} conversations)")
        
        # Add options dictionary to meta_yaml
        if meta_yaml is None:
            meta_yaml = {}
        meta_yaml["override_options"] = override_options
        
        # If columns are specified, add them to meta_yaml
        if include_columns:
            meta_yaml["include_columns"] = include_columns.split(",")
        if exclude_columns:
            meta_yaml["exclude_columns"] = exclude_columns.split(",")
            
        meta_yaml_str = json.dumps(meta_yaml)
        
        summarize(
            output_dir=output_dir,
            prompt_template_path=prompt_path,
            max_workers=max_workers,
            recipe_name=recipe,
            use_cache=use_cache,
            gsheet_config=gsheet_config_str,
            meta_config=meta_yaml_str,
            skip_detailed_temporal=skip_detailed_temporal_processing_for_recipe,
            limit=limit  # Pass the limit parameter to the summarize function
        )
        logger.info("Summarization completed.")
        
        # Generate a report as well
        logger.info("Generating reports...")
        report(
            output_dir=output_dir,
            recipe_name=recipe,
            format="both"
        )
        logger.info("Reports generated.")

    logger.info(f"Recipe '{recipe}' run complete. Results in {output_dir}")
    typer.echo(f"Done! Results saved to {output_dir}") 