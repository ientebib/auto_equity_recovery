"""CLI command for running the full lead recovery pipeline."""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import typer

from ..config import settings
from ..exceptions import RecipeNotFoundError, RecipeConfigurationError
from ..recipe_loader import RecipeLoader
from ..recipe_schema import RecipeMeta
from .report import report
from .summarize import summarize

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

def setup_environment() -> bool:
    """Set up environment variables needed for the pipeline
    
    Returns:
        bool: True if setup successful, False otherwise
    """
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

def load_recipe_config(recipe_name: str, recipe_dir: Path, skip_processors: Optional[List[str]] = None,
                      run_only_processors: Optional[List[str]] = None, recipes_base_dir: Optional[Path] = None) -> RecipeMeta:
    """Load recipe configuration from meta.yml and apply processor filters.
    
    Args:
        recipe_name: Name of the recipe
        recipe_dir: Path to the recipe directory
        skip_processors: List of processor class names to skip
        run_only_processors: List of processor class names to run exclusively
        recipes_base_dir: Optional custom base directory for recipes
        
    Returns:
        RecipeMeta object containing recipe configuration
    """
    try:
        # Load the recipe using RecipeLoader
        logger.info(f"Loading recipe configuration for: {recipe_name}")
        if recipes_base_dir:
            # Use custom recipes directory
            recipe_loader = RecipeLoader(project_root=recipes_base_dir.parent, recipes_dir_name=recipes_base_dir.name)
            logger.info(f"Using custom recipes directory: {recipes_base_dir}")
        else:
            # Use default RecipeLoader configuration
            recipe_loader = RecipeLoader()
        recipe_meta = recipe_loader.load_recipe_meta(recipe_name)
        
        # Apply processor filtering based on CLI options
        if recipe_meta.python_processors:
            original_processors = recipe_meta.python_processors
            filtered_processors = []
            
            if run_only_processors:
                logger.info(f"Filtering to only run processors: {run_only_processors}")
                for proc_config in original_processors:
                    module_path = proc_config.module
                    class_name = module_path.split('.')[-1] if module_path else ''
                    if class_name in run_only_processors:
                        filtered_processors.append(proc_config)
                        logger.info(f"Including processor: {class_name}")
                    else:
                        logger.info(f"Excluding processor: {class_name} (not in run_only_processors list)")
            elif skip_processors:
                logger.info(f"Skipping processors: {skip_processors}")
                for proc_config in original_processors:
                    module_path = proc_config.module
                    class_name = module_path.split('.')[-1] if module_path else ''
                    if class_name not in skip_processors:
                        filtered_processors.append(proc_config)
                        logger.info(f"Including processor: {class_name}")
                    else:
                        logger.info(f"Excluding processor: {class_name} (in skip_processors list)")
            else:
                # If no filtering options specified, use all processors
                filtered_processors = original_processors
                
            # Update recipe_meta with filtered processors
            recipe_meta.python_processors = filtered_processors
            logger.info(f"Using {len(filtered_processors)} of {len(original_processors)} processors after filtering")
        
        return recipe_meta
        
    except Exception as e:
        logger.error(
            f"Error loading recipe configuration for {recipe_name}: {e}",
            exc_info=True,
        )
        raise RecipeConfigurationError(
            f"Failed to load recipe configuration for {recipe_name}"
        ) from e

def setup_sql_and_prompt_paths(recipe_dir: Path, recipe_meta: RecipeMeta) -> Dict[str, Path]:
    """Set up paths to SQL and prompt files based on the recipe configuration.
    
    Args:
        recipe_dir: Path to the recipe directory
        recipe_meta: RecipeMeta object containing recipe configuration
        
    Returns:
        Dictionary containing paths to SQL and prompt files
    """
    # Default SQL filenames
    default_redshift_sql_name = "redshift.sql"
    default_bigquery_sql_name = "bigquery.sql"
    default_prompt_name = "prompt.txt"

    # Get SQL filenames from recipe_meta if specified, else use defaults
    redshift_sql_file_name = default_redshift_sql_name
    bigquery_sql_file_name = default_bigquery_sql_name
    prompt_file_name = default_prompt_name
    
    # Check data_input in RecipeMeta if available
    if hasattr(recipe_meta, 'data_input') and recipe_meta.data_input:
        if hasattr(recipe_meta.data_input, 'redshift_config') and recipe_meta.data_input.redshift_config:
            if hasattr(recipe_meta.data_input.redshift_config, 'sql_file') and recipe_meta.data_input.redshift_config.sql_file:
                redshift_sql_file_name = recipe_meta.data_input.redshift_config.sql_file
                
        if hasattr(recipe_meta.data_input, 'conversation_sql_file_bigquery') and recipe_meta.data_input.conversation_sql_file_bigquery:
            bigquery_sql_file_name = recipe_meta.data_input.conversation_sql_file_bigquery
    
    # Check llm_config in RecipeMeta if available
    if hasattr(recipe_meta, 'llm_config') and recipe_meta.llm_config:
        if hasattr(recipe_meta.llm_config, 'prompt_file') and recipe_meta.llm_config.prompt_file:
            prompt_file_name = recipe_meta.llm_config.prompt_file
    
    logger.info(f"Using prompt file name: {prompt_file_name}")
    
    # Construct full paths to SQL and prompt files
    redshift_sql_path = recipe_dir / redshift_sql_file_name
    bigquery_sql_path = recipe_dir / bigquery_sql_file_name
    prompt_path = recipe_dir / prompt_file_name

    # Log SQL path information
    if redshift_sql_path.exists():
        logger.info(f"Using recipe Redshift SQL: {redshift_sql_path}")
    else:
        logger.warning(f"Redshift SQL file '{redshift_sql_path.name}' not found for recipe. Downstream Redshift steps might fail if not skipped.")

    if bigquery_sql_path.exists():
        logger.info(f"Using recipe BigQuery SQL: {bigquery_sql_path}")
    else:
        logger.warning(f"BigQuery SQL file '{bigquery_sql_path.name}' not found for recipe. Downstream BigQuery steps might fail if not skipped.")

    if prompt_path.exists():
        logger.info(f"Using recipe prompt template: {prompt_path}")
    else:
        logger.warning(f"Prompt file '{prompt_file_name}' not found for recipe. Summarization may fail or use default prompt.")

    return {
        "redshift_sql_path": redshift_sql_path,
        "bigquery_sql_path": bigquery_sql_path,
        "prompt_path": prompt_path if prompt_path.exists() else None
    }

def handle_csv_leads(recipe_dir: Path, recipe_meta: RecipeMeta, output_dir: Path) -> bool:
    """Handle CSV lead source from recipe.
    
    Args:
        recipe_dir: Path to the recipe directory
        recipe_meta: RecipeMeta object containing recipe configuration
        output_dir: Output directory where leads.csv should be placed
        
    Returns:
        bool: True if CSV handling was successful, False otherwise
    """
    # Check if the recipe uses CSV as lead source
    if (not hasattr(recipe_meta, 'data_input') or 
        not hasattr(recipe_meta.data_input, 'lead_source_type') or
        recipe_meta.data_input.lead_source_type != 'csv'):
        # Not a CSV source, nothing to do
        return True
    
    logger.info("Recipe uses CSV as lead source")
    
    # Get the CSV file name from recipe_meta
    csv_file_name = "leads.csv"  # Default
    if (hasattr(recipe_meta.data_input, 'csv_config') and 
        recipe_meta.data_input.csv_config and 
        hasattr(recipe_meta.data_input.csv_config, 'csv_file')):
        csv_file_name = recipe_meta.data_input.csv_config.csv_file
    
    # Source path (recipe dir)
    source_path = recipe_dir / csv_file_name
    
    # Ensure the output directory path is absolute
    dest_path = output_dir.absolute() / "leads.csv"
    
    # Use resolve() to get canonical path for both source and destination
    source_path = source_path.resolve()
    dest_path = dest_path.resolve()
    
    # Check if source file exists
    if not source_path.exists():
        logger.error(f"CSV lead file not found: {source_path}")
        return False
    
    # Check if source and destination are the same file
    if source_path == dest_path:
        logger.info(f"Source and destination are the same file: {source_path}. No copy needed.")
        return True
    
    try:
        # Create parent directories if they don't exist
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Copy the CSV file to the output directory
        import shutil
        shutil.copy2(source_path, dest_path)
        logger.info(f"Copied CSV leads from {source_path} to {dest_path}")
        return True
    except Exception as e:
        logger.error(f"Error copying CSV leads file: {e}", exc_info=True)
        
        # Check if the file already exists at the destination
        if dest_path.exists():
            logger.info(f"Destination file already exists: {dest_path}. Using existing file.")
            return True
        
        return False

def handle_redshift_stage(recipe: str, skip_redshift: bool, redshift_sql_path: Path, 
                          ignore_redshift_marker: bool, use_cached_redshift: bool, 
                          leads_path: Path, output_dir: Path) -> bool:
    """Handle the Redshift data fetching stage.
    
    Args:
        recipe: Name of the recipe
        skip_redshift: Whether to skip Redshift fetch
        redshift_sql_path: Path to Redshift SQL file
        ignore_redshift_marker: Whether to ignore existing Redshift marker
        use_cached_redshift: Whether to use cached Redshift data
        leads_path: Path to leads CSV file
        output_dir: Output directory
        
    Returns:
        bool: True if Redshift stage completed successfully, False otherwise
    """
    # Handle skipping logic
    if skip_redshift:
        logger.info("Skipping Redshift step")
        if not leads_path.exists():
            logger.warning("Skipped Redshift but leads.csv does not exist. Downstream steps may fail.")
        return True
    
    # Check if Redshift query exists for this recipe
    has_redshift_query = redshift_sql_path.exists()
    if not has_redshift_query:
        # If the recipe doesn't have a redshift.sql file, automatically skip Redshift
        logger.info(f"No Redshift query file found for recipe {recipe}, skipping Redshift")
        return True
    
    # Check for today's marker unless explicitly ignored
    marker_exists, marker_path = check_redshift_marker(recipe)
    
    # If caller does NOT want to use cache, treat as ignore marker implicitly
    if not use_cached_redshift:
        ignore_redshift_marker = True

    if marker_exists and not ignore_redshift_marker:
        logger.info(f"Redshift marker found for today ({marker_path}). Using cached Redshift data.")
        # Only skip if cached data exists
        if use_cached_redshift and leads_path.exists():
            logger.info(f"Using cached leads data from {leads_path}")
            return True
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
    
    # Perform the Redshift query
    try:
        logger.info(f"Fetching leads from Redshift using SQL file: {redshift_sql_path}")
        
        # Import fetch_leads function to directly fetch leads
        from ..cli.fetch_leads import fetch_leads
        
        # Call fetch_leads with the SQL file path
        fetch_leads(output_dir=output_dir, sql_file=redshift_sql_path)
        
        # Create a marker file to indicate successful Redshift query for today
        create_redshift_marker(recipe)
        return True
    except Exception as e:
        logger.error(f"Error fetching from Redshift: {e}", exc_info=True)
        # If this fails and we have cached data, try to use it
        if use_cached_redshift and leads_path.exists():
            logger.warning("Falling back to cached leads data after Redshift error")
            return True
        return False

def handle_bigquery_stage(skip_bigquery: bool, output_dir: Path, bigquery_sql_path: Path) -> bool:
    """Handle the BigQuery data fetching stage.
    
    Args:
        skip_bigquery: Whether to skip BigQuery fetch
        output_dir: Output directory
        bigquery_sql_path: Path to BigQuery SQL file
        
    Returns:
        bool: True if BigQuery stage completed successfully, False otherwise
    """
    conversations_path = output_dir / "conversations.csv"
    
    if skip_bigquery:
        logger.info("Skipping BigQuery step")
        if not conversations_path.exists():
            logger.warning("Skipped BigQuery but conversations.csv does not exist. Downstream steps may fail.")
        return True
    
    # Check if BigQuery SQL file exists
    if not bigquery_sql_path.exists():
        logger.warning(f"BigQuery SQL file not found: {bigquery_sql_path}")
        if conversations_path.exists():
            logger.info("Using existing conversations.csv file")
            return True
        else:
            logger.error("No BigQuery SQL file and no existing conversations.csv file")
            return False
    
    try:
        logger.info(f"Fetching conversations from BigQuery using SQL file: {bigquery_sql_path}")
        
        # Import fetch_convos function to directly fetch conversations
        from ..cli.fetch_convos import fetch_convos
        
        # Call fetch_convos with the SQL file path
        fetch_convos(output_dir=output_dir, batch_size=settings.BQ_BATCH_SIZE, sql_file=bigquery_sql_path)
        
        logger.info("BigQuery fetch completed.")
        return True
    except Exception as e:
        logger.error(f"Error fetching from BigQuery: {e}", exc_info=True)
        # If this fails and we have cached data, try to use it
        if conversations_path.exists():
            logger.warning("Falling back to cached conversations data after BigQuery error")
            return True
        return False

def handle_summarize_stage(skip_summarize: bool, output_dir: Path, prompt_path: Optional[Path],
                           max_workers: Optional[int], recipe: str, use_cache: bool,
                           recipe_meta: RecipeMeta, include_columns: Optional[str],
                           exclude_columns: Optional[str], limit: Optional[int]) -> bool:
    """Handle the summarization stage.
    
    Args:
        skip_summarize: Whether to skip summarization
        output_dir: Output directory
        prompt_path: Path to prompt template
        max_workers: Maximum number of concurrent workers
        recipe: Recipe name
        use_cache: Whether to use cache
        recipe_meta: RecipeMeta object containing recipe configuration
        include_columns: Comma-separated list of columns to include
        exclude_columns: Comma-separated list of columns to exclude
        limit: Maximum number of conversations to process
        
    Returns:
        bool: True if summarization stage completed successfully, False otherwise
    """
    if skip_summarize:
        logger.info("Skipping summarization step")
        return True
    
    logger.info("Starting summarization with OpenAI...")
    
    # Get Google Sheets configuration from recipe_meta
    gsheet_config = None
    if recipe_meta.custom_analyzer_params and "google_sheets" in recipe_meta.custom_analyzer_params:
        gs_params = recipe_meta.custom_analyzer_params["google_sheets"]
        if isinstance(gs_params, dict):
            sheet_id = gs_params.get('sheet_id')
            worksheet_name = gs_params.get('worksheet_name')
            if sheet_id and worksheet_name:
                gsheet_config = {"sheet_id": sheet_id, "worksheet_name": worksheet_name}
                logger.info(f"Configured Google Sheets integration from custom_analyzer_params: {gsheet_config}")
    
    # Get behavior flags
    skip_detailed_temporal_processing_for_recipe = False
    if hasattr(recipe_meta, 'behavior_flags') and recipe_meta.behavior_flags:
        skip_detailed_temporal_processing_for_recipe = getattr(
            recipe_meta.behavior_flags, 'skip_detailed_temporal_processing', False)
    
    # Serialize RecipeMeta to dictionary
    meta_dict = {}
    if hasattr(recipe_meta, 'dict'):
        # If it has a dict() method (Pydantic)
        meta_dict = recipe_meta.dict()
    else:
        # Fallback manual serialization
        logger.warning("RecipeMeta does not have dict() method, using manual serialization")
        for attr in dir(recipe_meta):
            if not attr.startswith('_') and not callable(getattr(recipe_meta, attr)):
                meta_dict[attr] = getattr(recipe_meta, attr)
    
    # Add a flag to indicate this is a serialized RecipeMeta
    meta_dict['__is_recipe_meta__'] = True
    
    # Add override options
    meta_dict['override_options'] = {
        'limit': limit,
        'skip_detailed_temporal': skip_detailed_temporal_processing_for_recipe
    }
    
    # Convert serialized config to JSON string
    meta_config_str = json.dumps(meta_dict)
    
    # Convert gsheet_config to string if it exists
    gsheet_config_str = json.dumps(gsheet_config) if gsheet_config else None
    
    # Prepare columns
    include_cols = include_columns
    exclude_cols = exclude_columns
    
    try:
        # Call summarize with dictionary config and all necessary flags
        summarize(
            output_dir=output_dir,
            prompt_template_path=prompt_path,
            max_workers=max_workers,
            recipe_name=recipe,
            use_cache=use_cache,
            gsheet_config=gsheet_config_str,
            meta_config=meta_config_str,  # Pass serialized RecipeMeta
            include_columns=include_cols,
            exclude_columns=exclude_cols,
            skip_detailed_temporal=skip_detailed_temporal_processing_for_recipe,
            limit=limit
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
        return True
    except Exception as e:
        logger.error(f"Error in summarization step: {e}", exc_info=True)
        return False

@app.callback(invoke_without_command=True)
def run_pipeline(
    recipe: str = typer.Option(..., help="Recipe name (folder name under recipes/)"),
    skip_redshift: bool = typer.Option(False, help="Skip fetching leads from Redshift"),
    skip_bigquery: bool = typer.Option(False, help="Skip fetching conversations from BigQuery"),
    skip_summarize: bool = typer.Option(False, help="Skip summarizing conversations"),
    max_workers: Optional[int] = typer.Option(None, help="Max concurrent workers for OpenAI calls"),
    output_dir: Optional[str] = typer.Option(None, help="Override base output directory"),
    recipes_dir: Optional[str] = typer.Option(None, help="Override recipes directory path (default: recipes/ in project root)"),
    use_cached_redshift: bool = typer.Option(False, help="Use cached Redshift data if available (default: False – always refresh leads)"),
    use_cache: bool = typer.Option(True, "--use-cache/--no-cache", help="Use summarization cache if available."),
    ignore_redshift_marker: bool = typer.Option(False, "--ignore-redshift-marker", help="Ignore existing Redshift marker and run query even if already run today."),
    skip_processors: Optional[List[str]] = typer.Option(None, "--skip-processor", help="List of processor class names to skip"),
    run_only_processors: Optional[List[str]] = typer.Option(None, "--run-only-processor", help="List of processor class names to run exclusively"),
    include_columns: Optional[str] = typer.Option(None, help="Comma-separated list of columns to include in the output"),
    exclude_columns: Optional[str] = typer.Option(None, help="Comma-separated list of columns to exclude from the output"),
    limit: Optional[int] = typer.Option(None, help="Limit the number of conversations to process (for testing)"),
):
    """Run the lead recovery pipeline."""
    logger.info("Using GOOGLE_APPLICATION_CREDENTIALS: %s", os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))
    logger.info("Running as user: %s", os.environ.get("USER", "unknown"))
    
    # Override output directory if specified
    if output_dir:
        final_output_dir = Path(output_dir) / recipe
    else:
        final_output_dir = Path(settings.OUTPUT_DIR) / recipe
    
    logger.info(f"Using output directory: {final_output_dir}")
    final_output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find recipe directory and load recipe configuration
    if recipes_dir:
        # Use the custom recipes directory provided by the user
        recipes_base_dir = Path(recipes_dir)
        recipe_dir = recipes_base_dir / recipe
        logger.info(f"Using custom recipes directory: {recipes_base_dir}")
    else:
        # Use the default recipes directory
        recipes_base_dir = Path(settings.PROJECT_ROOT) / "recipes"
        recipe_dir = recipes_base_dir / recipe
        logger.info(f"Using default recipes directory: {recipes_base_dir}")
    
    if not recipe_dir.is_dir():
        msg = f"Recipe '{recipe}' not found in {recipes_base_dir}"
        logger.error(msg)
        raise RecipeNotFoundError(msg)
    
    # Load and filter processors
    recipe_meta = load_recipe_config(recipe, recipe_dir, skip_processors, run_only_processors, recipes_base_dir)
    
    # Set up SQL and prompt paths
    paths = setup_sql_and_prompt_paths(recipe_dir, recipe_meta)
    redshift_sql_path = paths["redshift_sql_path"]
    bigquery_sql_path = paths["bigquery_sql_path"]
    prompt_path = paths["prompt_path"]
    
    # Final paths
    leads_path = final_output_dir / "leads.csv"
    
    # Check if recipe uses CSV as lead source
    uses_csv_source = (hasattr(recipe_meta, 'data_input') and 
                      hasattr(recipe_meta.data_input, 'lead_source_type') and 
                      recipe_meta.data_input.lead_source_type == 'csv')
    
    # Handle CSV lead source if needed
    if uses_csv_source:
        logger.info("Recipe uses CSV as lead source type - copying CSV leads file")
        csv_success = handle_csv_leads(recipe_dir, recipe_meta, final_output_dir)
        if not csv_success:
            logger.error("Failed to copy CSV leads file, cannot continue")
            raise typer.Exit(1)
        # Skip Redshift since we're using CSV
        skip_redshift = True
    
    # Handle Redshift stage
    redshift_success = handle_redshift_stage(
        recipe, skip_redshift, redshift_sql_path, 
        ignore_redshift_marker, use_cached_redshift, 
        leads_path, final_output_dir
    )
    
    if not redshift_success and not skip_redshift:
        logger.error("Redshift stage failed and not skipped, cannot continue")
        raise typer.Exit(1)

    # Handle BigQuery stage
    bigquery_success = handle_bigquery_stage(skip_bigquery, final_output_dir, bigquery_sql_path)
    
    if not bigquery_success and not skip_bigquery:
        logger.error("BigQuery stage failed and not skipped, cannot continue")
        raise typer.Exit(1)

    # Handle Summarize stage
    summarize_success = handle_summarize_stage(
        skip_summarize, final_output_dir, prompt_path, 
        max_workers, recipe, use_cache, recipe_meta,
        include_columns, exclude_columns, limit
    )
    
    if not summarize_success and not skip_summarize:
        logger.error("Summarize stage failed and not skipped, cannot continue")
        raise typer.Exit(1)
        
    logger.info("Pipeline completed successfully")
    
    # Produce a summary report
    if not skip_summarize:
        report(output_dir=final_output_dir, recipe_name=recipe) 