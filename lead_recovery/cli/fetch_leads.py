"""CLI command for fetching leads from Redshift."""
from typing import Optional
from datetime import datetime
from pathlib import Path

import typer
import pandas as pd

from ..config import settings
from ..db_clients import RedshiftClient
from ..utils import load_sql_file
from ..reporting import to_csv

import logging
logger = logging.getLogger(__name__)

app = typer.Typer()

@app.callback(invoke_without_command=True)
def fetch_leads(
    since: Optional[datetime] = typer.Option(None, "--since", help="Fetch leads created after this timestamp."),
    output_dir: Path = typer.Option(settings.OUTPUT_DIR, "--output-dir"),
):
    """Retrieve relevant leads from Redshift and store as CSV."""
    rs_client = RedshiftClient()
    sql = load_sql_file(settings.RS_SQL_PATH)
    params = {"since": since} if since else None
    leads_df = rs_client.query(sql, params)

    # Ensure the expected column from Redshift exists
    if "cleaned_phone_number" not in leads_df.columns:
        logger.error("Redshift query did not return 'cleaned_phone_number' column.", exc_info=True)
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