"""CLI command for fetching leads from Redshift."""
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

from ..config import settings
from ..db_clients import RedshiftClient
from ..reporting import to_csv

logger = logging.getLogger(__name__)

app = typer.Typer()

@app.callback(invoke_without_command=True)
def fetch_leads(
    since: Optional[datetime] = typer.Option(None, "--since", help="Fetch leads created after this timestamp."),
    output_dir: Path = typer.Option(settings.OUTPUT_DIR, "--output-dir"),
    sql_file: Optional[Path] = typer.Option(None, "--sql-file", help="Path to SQL file for querying leads"),
):
    """Retrieve relevant leads from Redshift and store as CSV."""
    rs_client = RedshiftClient()
    
    # Use provided SQL file or try to find a default in recipe dir
    if sql_file is None:
        # Look in the output_dir parent for redshift.sql (assuming recipe structure)
        recipe_dir = output_dir
        if "output_run" in str(output_dir):
            # If in the output_run dir, try to find the corresponding recipe
            recipe_name = output_dir.name
            recipe_dir = settings.PROJECT_ROOT / "recipes" / recipe_name
        
        sql_file = recipe_dir / "redshift.sql"
        logger.info(f"No SQL file provided, looking for {sql_file}")
    
    if not sql_file.exists():
        logger.error(f"SQL file not found: {sql_file}")
        raise typer.Exit(1)
    
    logger.info(f"Using SQL file: {sql_file}")
    
    try:
        # Use the query_from_file method for better error handling
        params = {"since": since} if since else None
        leads_df = rs_client.query_from_file(sql_file, params)
        
        # Ensure the expected column from Redshift exists
        if "cleaned_phone_number" not in leads_df.columns:
            logger.error("Redshift query did not return 'cleaned_phone_number' column.")
            raise typer.Exit(1) # Or handle differently
            
        # Rename the column from SQL to match downstream usage (instead of redundant cleaning)
        leads_df.rename(columns={"cleaned_phone_number": "cleaned_phone"}, inplace=True)

        # Remove rows where cleaning failed (if any nulls resulted from SQL cleaning/casting)
        original_count = len(leads_df)
        leads_df.dropna(subset=["cleaned_phone"], inplace=True)
        if len(leads_df) < original_count:
            logger.warning("Removed %d leads with missing cleaned_phone after Redshift query.", 
                        original_count - len(leads_df))

        csv_path = output_dir / "leads.csv"
        to_csv(leads_df, csv_path)
        logger.info(f"Wrote {len(leads_df)} leads to {csv_path}")
        
        return leads_df  # Return DataFrame for use in testing/programmatic access
    except FileNotFoundError:
        logger.error(f"SQL file not found: {sql_file}")
        raise typer.Exit(1)
    except Exception as e:
        logger.error(f"Error fetching leads from Redshift: {e}")
        raise typer.Exit(1) 