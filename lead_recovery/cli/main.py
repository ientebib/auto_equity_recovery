"""Main entry point for CLI commands."""
import logging
import sys
from typing import List, Optional

import typer
import subprocess

from . import app, fetch_convos, fetch_leads, report, run, summarize
from . import recipes_migrate  # Migration helper CLI
from . import update_output_columns  # Output columns updater CLI

# Configure main CLI application
logger = logging.getLogger(__name__)

# Add subcommands to the main CLI app
app.add_typer(fetch_leads.app, name="fetch-leads")
app.add_typer(fetch_convos.app, name="fetch-convos")
app.add_typer(summarize.app, name="summarize")
app.add_typer(report.app, name="report")
app.add_typer(run.app, name="run")
app.add_typer(recipes_migrate.app, name="recipes-migrate")  # Migration helper CLI
app.add_typer(update_output_columns.app, name="update-output-columns")  # Output columns updater CLI

@app.command()
def run(
    recipe: str = typer.Option(..., help="Recipe name (folder name under recipes/)"),
    skip_redshift: bool = typer.Option(False, help="Skip fetching leads from Redshift"),
    skip_bigquery: bool = typer.Option(False, help="Skip fetching conversations from BigQuery"),
    skip_summarize: bool = typer.Option(False, help="Skip summarizing conversations"),
    max_workers: Optional[int] = typer.Option(None, help="Max concurrent workers for OpenAI calls"),
    output_dir: Optional[str] = typer.Option(None, help="Override base output directory"),
    use_cached_redshift: bool = typer.Option(True, help="Use cached Redshift data if available"),
    use_cache: bool = typer.Option(True, "--use-cache/--no-cache", help="Use summarization cache if available."),
    ignore_redshift_marker: bool = typer.Option(False, "--ignore-redshift-marker", help="Ignore existing Redshift marker and run query even if already run today."),
    skip_processors: Optional[List[str]] = typer.Option(None, "--skip-processor", help="List of processor class names to skip (e.g., 'TemporalProcessor')"),
    run_only_processors: Optional[List[str]] = typer.Option(None, "--run-only-processor", help="List of processor class names to run exclusively. All others will be skipped."),
    include_columns: Optional[str] = typer.Option(None, help="Comma-separated list of columns to include in the output"),
    exclude_columns: Optional[str] = typer.Option(None, help="Comma-separated list of columns to exclude from the output"),
    limit: Optional[int] = typer.Option(None, help="Limit the number of conversations to process (for testing)"),
    log_level: str = typer.Option("INFO", help="Logging level (INFO, DEBUG, WARNING, ERROR)")
):
    """Run the full pipeline for a recipe: fetch leads, fetch conversations, summarize."""
    # Configure logging level
    logging.basicConfig(level=getattr(logging, log_level.upper(), logging.INFO))
    logging.getLogger().setLevel(logging.DEBUG)
    logger.info("Set log level to DEBUG explicitly.")
    
    # Call main pipeline entry point
    run.run_pipeline(
        recipe=recipe,
        skip_redshift=skip_redshift,
        skip_bigquery=skip_bigquery,
        skip_summarize=skip_summarize,
        max_workers=max_workers,
        output_dir=output_dir,
        use_cached_redshift=use_cached_redshift,
        use_cache=use_cache,
        ignore_redshift_marker=ignore_redshift_marker,
        skip_processors=skip_processors,
        run_only_processors=run_only_processors,
        include_columns=include_columns,
        exclude_columns=exclude_columns,
        limit=limit
    )

@app.command()
def validate_recipes():
    """Validate all recipes for schema and output column compliance."""
    result = subprocess.run(["python", "scripts/validate_all_recipes.py"])
    if result.returncode != 0:
        raise typer.Exit(result.returncode)

def main() -> None:  # noqa: D401
    """CLI entrypoint."""
    try:
        app()
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.exception(f"Unhandled exception: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 