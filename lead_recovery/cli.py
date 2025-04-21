"""cli.py
Command‑line interface for lead recovery pipeline.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import time

import pandas as pd
import typer
from tqdm import tqdm
from google.cloud.bigquery import ArrayQueryParameter

from .config import settings
from .db_clients import BigQueryClient, RedshiftClient
from .summarizer import ConversationSummarizer
from .utils import clean_phone, load_sql_file
from .reporting import to_csv, to_html

logger = logging.getLogger(__name__)

app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)


@app.command()
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


@app.command()
def fetch_convos(
    batch_size: int = typer.Option(settings.BQ_BATCH_SIZE, "--batch-size"),
    output_dir: Path = typer.Option(settings.OUTPUT_DIR, "--output-dir"),
):
    """Fetch WhatsApp conversation history for all target leads."""
    leads_path = output_dir / "leads.csv"
    if not leads_path.is_file():
        typer.echo("Leads CSV not found. Run fetch-leads first.")
        raise typer.Exit(1)

    leads_df = pd.read_csv(leads_path)
    phones: List[str] = leads_df["cleaned_phone"].dropna().unique().tolist()

    if not phones:
        logger.warning("No valid phone numbers found in leads.csv to fetch conversations for.")
        convos_df = pd.DataFrame() # Create empty DataFrame
        to_csv(convos_df, output_dir / "conversations.csv")
        return # Exit early

    bq_client = BigQueryClient()
    sql_template = load_sql_file(settings.BQ_SQL_PATH)

    frames: List[pd.DataFrame] = []
    # Chunk phone numbers for batch processing
    phones_chunks = [phones[i : i + batch_size] for i in range(0, len(phones), batch_size)]
    logger.info("Fetching BQ data for %d phones in %d chunks (size %d, max concurrent %d)",
                len(phones), len(phones_chunks), batch_size, settings.BQ_MAX_CONCURRENT_QUERIES)

    # Use ThreadPoolExecutor for concurrent BQ queries
    with ThreadPoolExecutor(max_workers=settings.BQ_MAX_CONCURRENT_QUERIES) as executor:
        future_to_chunk = {
            executor.submit(
                bq_client.query,
                sql_template,
                [ArrayQueryParameter("target_phone_numbers_list", "STRING", chunk)],
            ): chunk
            for chunk in phones_chunks
        }

        # Process completed futures with progress bar
        for future in tqdm(as_completed(future_to_chunk), total=len(future_to_chunk), desc="Fetching Convos", unit="batch"):
            chunk = future_to_chunk[future]
            try:
                result_df = future.result()
                frames.append(result_df)
            except Exception as e:
                # Log error with more context if possible (e.g., first phone in chunk)
                first_phone = chunk[0] if chunk else 'N/A'
                logger.error("Failed to fetch BQ chunk starting with phone %s: %s", first_phone, e)
                # Optionally: Add failed chunk info to a separate list for retry/review

    logger.info("Finished fetching BQ data. Concatenating %d frames.", len(frames))
    convos_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    to_csv(convos_df, output_dir / "conversations.csv")


@app.command()
def summarize(
    output_dir: Path = typer.Option(settings.OUTPUT_DIR, "--output-dir"),
    max_workers: int = typer.Option(4, "--max-workers", help="Maximum number of parallel workers for summarization"),
):
    """Create OpenAI summaries and merge with leads for reporting."""
    convos_path = output_dir / "conversations.csv"
    if not convos_path.is_file():
        typer.echo("Conversations CSV not found. Run fetch-convos first.")
        raise typer.Exit(1)

    convos_df = pd.read_csv(convos_path)
    summarizer = ConversationSummarizer()
    
    # Ensure the required column from BQ exists before grouping
    assert "cleaned_phone_number" in convos_df.columns, \
        "BQ query must alias phone column as 'cleaned_phone_number'"

    # Group conversations by phone number
    phone_groups = {phone: group for phone, group in convos_df.groupby("cleaned_phone_number")}
    phones = list(phone_groups.keys())
    
    # Function to summarize one group with timing
    def summarize_group(phone: str) -> Dict[str, Any]:
        start_time = time.time()
        group_df = phone_groups[phone]
        summary = summarizer.summarize(group_df)
        duration = time.time() - start_time
        logger.debug("Summarized conversation for %s in %.2f seconds", phone, duration)
        return {"cleaned_phone_number": phone, "summary": summary}
    
    # Use ThreadPoolExecutor for parallel processing
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_phone = {executor.submit(summarize_group, phone): phone for phone in phones}

        for future in tqdm(as_completed(future_to_phone), total=len(future_to_phone), desc="Summarizing", unit="lead"):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                phone = future_to_phone[future]
                logger.error("Failed to summarize conversation for %s: %s", phone, str(e))
    
    # Convert results to DataFrame
    summaries = pd.DataFrame(results)
    
    leads_df = pd.read_csv(output_dir / "leads.csv")
    merged_df = leads_df.merge(
        summaries,
        left_on="cleaned_phone",
        right_on="cleaned_phone_number",
        how="left",
    )

    to_csv(merged_df, output_dir / "analysis.csv")
    to_html(merged_df, output_dir / "analysis.html")


@app.command()
def report(output_dir: Path = typer.Option(settings.OUTPUT_DIR, "--output-dir")):
    """Alias to generate HTML/CSV report from merged analysis if not already."""
    analyze_path = output_dir / "analysis.csv"
    if not analyze_path.is_file():
        typer.echo("analysis.csv not found. Run summarize first.")
        raise typer.Exit(1)

    df = pd.read_csv(analyze_path)
    to_html(df, output_dir / "analysis.html")
    typer.echo("Report generated at analysis.html")


def main() -> None:  # noqa: D401
    """CLI entrypoint."""
    app()


if __name__ == "__main__":
    main() 