"""Main entry point for CLI commands."""
import logging
import sys

import typer
from typing import Optional

from . import app
from . import fetch_leads, fetch_convos, summarize, report, run
from . import update_recipe_columns

# Configure main CLI application
logger = logging.getLogger(__name__)

# Add subcommands to the main CLI app
app.add_typer(fetch_leads.app, name="fetch-leads")
app.add_typer(fetch_convos.app, name="fetch-convos")
app.add_typer(summarize.app, name="summarize")
app.add_typer(report.app, name="report")
app.add_typer(run.app, name="run")
app.add_typer(update_recipe_columns.app, name="update-recipe-columns")

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
    skip_topup_template_detection: bool = typer.Option(False, help="Skip top-up template detection (top_up_may recipe)"),
    skip_consecutive_templates_count: bool = typer.Option(False, help="Skip counting consecutive recovery templates"),
    include_columns: Optional[str] = typer.Option(None, help="Comma-separated list of columns to include in the output"),
    exclude_columns: Optional[str] = typer.Option(None, help="Comma-separated list of columns to exclude from the output"),
    limit: Optional[int] = typer.Option(None, help="Limit the number of conversations to process (for testing)"),
    log_level: str = typer.Option("INFO", help="Logging level (INFO, DEBUG, WARNING, ERROR)")
):
    """Run the full pipeline for a recipe: fetch leads, fetch conversations, summarize."""
    # Configure logging level
    logging.basicConfig(level=getattr(logging, log_level.upper(), logging.INFO))
    logging.getLogger().setLevel(logging.DEBUG)
    logger.info(f"Set log level to DEBUG explicitly.")
    
    # Call main pipeline entry point
    run_pipeline(
        recipe=recipe,
        skip_redshift=skip_redshift,
        skip_bigquery=skip_bigquery,
        skip_summarize=skip_summarize,
        max_workers=max_workers,
        output_dir=output_dir,
        use_cached_redshift=use_cached_redshift,
        use_cache=use_cache,
        ignore_redshift_marker=ignore_redshift_marker,
        skip_temporal_flags=skip_temporal_flags,
        skip_detailed_temporal=skip_detailed_temporal,
        skip_hours_minutes=skip_hours_minutes,
        skip_reactivation_flags=skip_reactivation_flags,
        skip_timestamps=skip_timestamps,
        skip_user_message_flag=skip_user_message_flag,
        skip_handoff_detection=skip_handoff_detection,
        skip_metadata_extraction=skip_metadata_extraction,
        skip_handoff_invitation=skip_handoff_invitation,
        skip_handoff_started=skip_handoff_started,
        skip_handoff_finalized=skip_handoff_finalized,
        skip_human_transfer=skip_human_transfer,
        skip_recovery_template_detection=skip_recovery_template_detection,
        skip_topup_template_detection=skip_topup_template_detection,
        skip_consecutive_templates_count=skip_consecutive_templates_count,
        include_columns=include_columns,
        exclude_columns=exclude_columns,
        limit=limit
    )

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