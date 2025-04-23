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
    batch_size: int = typer.Option(settings.BQ_BATCH_SIZE, "--batch-size", help="Number of phone numbers per BigQuery request."),
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
        # Ensure the output CSV has the expected header even if empty
        convos_df = pd.DataFrame(columns=["cleaned_phone_number"]) # Define expected columns
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
    # Ensure the output CSV has the expected header even if empty
    expected_columns = ["cleaned_phone_number"] # Add other expected columns if needed
    convos_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=expected_columns)
    
    # If the DataFrame isn't empty, ensure the required column exists
    if not convos_df.empty and "cleaned_phone_number" not in convos_df.columns:
        logger.error("BigQuery query result missing required 'cleaned_phone_number' column.")
        # Decide how to handle: raise error, add empty column, etc.
        # For now, let's raise an error as it indicates a problem with the SQL
        raise ValueError("BQ query must provide 'cleaned_phone_number' column")
        
    to_csv(convos_df, output_dir / "conversations.csv")


@app.command()
def summarize(
    output_dir: Path = typer.Option(settings.OUTPUT_DIR, "--output-dir"),
    max_workers: int = typer.Option(4, "--max-workers", help="Maximum number of parallel workers for summarization"),
    prompt_template_path: Optional[Path] = typer.Option(None, "--prompt-template", help="Custom prompt template path (overrides default)"),
    # Added: Allow expected keys to be passed directly (mainly for internal use by 'run')
    expected_yaml_keys_internal: Optional[List[str]] = typer.Option(None, hidden=True),
    # Added: Recipe name for output filename
    recipe_name: Optional[str] = typer.Option(None, hidden=True, help="Internal use: Recipe name for output filename.")
):
    """Create OpenAI summaries and merge with leads for reporting."""
    # Default recipe name if not provided (e.g., when called directly, not via 'run')
    _recipe_name = recipe_name or output_dir.name
    today_str = datetime.now().strftime('%Y%m%d')
    base_filename = f"{_recipe_name}_analysis_{today_str}"
    csv_output_path = output_dir / f"{base_filename}.csv"
    html_output_path = output_dir / f"{base_filename}.html"

    convos_path = output_dir / "conversations.csv"
    if not convos_path.is_file():
        # Gracefully allow recipes without a BigQuery step
        logger.warning("conversations.csv not found – proceeding with empty conversations.")
        pd.DataFrame().to_csv(convos_path, index=False)
        # Even if no convos, create empty analysis files with expected names
        leads_path = output_dir / "leads.csv"
        if leads_path.exists():
            leads_df = pd.read_csv(leads_path)
            for col in ["result", "stall_reason", "key_interaction", "suggestion", "summary"]:
                leads_df[col] = "N/A" if col != "stall_reason" else "NO_OUTBOUND"
            to_csv(leads_df, csv_output_path) # Use new path
            to_html(leads_df, html_output_path) # Use new path
        else:
            logger.warning("leads.csv not found either, cannot create empty analysis file.")
            return

    convos_df = pd.read_csv(convos_path)

    # If there is no conversation data, skip summarisation and just merge empty fields
    if convos_df.empty:
        logger.info("No conversation data found – skipping OpenAI summarisation.")
        leads_df = pd.read_csv(output_dir / "leads.csv")
        for col in ["result", "stall_reason", "key_interaction", "suggestion", "summary"]:
            leads_df[col] = "N/A" if col != "stall_reason" else "NO_OUTBOUND"
        to_csv(leads_df, csv_output_path) # Use new path
        to_html(leads_df, html_output_path) # Use new path
        return

    # Initialize summarizer, passing keys if provided
    summarizer = ConversationSummarizer(
        prompt_template_path=prompt_template_path, 
        expected_yaml_keys=expected_yaml_keys_internal # Pass the keys
    )
    
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
        summary_dict = summarizer.summarize(group_df) # Now returns a dict
        duration = time.time() - start_time
        logger.debug("Summarized conversation for %s in %.2f seconds", phone, duration)
        # Add the phone number to the dictionary before returning
        summary_dict["cleaned_phone_number"] = phone 
        return summary_dict # Return the full dictionary
    
    # Use ThreadPoolExecutor for parallel processing
    summary_results: List[Dict[str, Any]] = [] # List to hold summary dictionaries
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_phone = {executor.submit(summarize_group, phone): phone for phone in phones}

        for future in tqdm(as_completed(future_to_phone), total=len(future_to_phone), desc="Summarizing", unit="lead"):
            try:
                result_dict = future.result()
                summary_results.append(result_dict)
            except Exception as e:
                phone = future_to_phone[future]
                logger.error("Failed to summarize conversation for %s: %s", phone, str(e))
                # Optionally add a default error entry for this phone
                # error_entry = {
                #     "cleaned_phone_number": phone,
                #     "result": "Summarization Error", 
                #     "stall_reason": "OTHER", 
                #     # ... other default fields
                # }
                # summary_results.append(error_entry)
    
    # Convert results list of dicts to DataFrame
    # The keys of the dictionaries become the columns
    summaries_df = pd.DataFrame(summary_results)
    
    # Define expected summary columns to ensure they exist, fill with defaults if needed
    expected_summary_cols = ['result', 'stall_reason', 'key_interaction', 'suggestion', 'summary']
    for col in expected_summary_cols:
        if col not in summaries_df.columns:
            logger.warning("Column '%s' missing from summarization results. Filling with default.", col)
            # Determine appropriate default based on column (e.g., 'N/A' or 'OTHER')
            default_val = "OTHER" if col == 'stall_reason' else "N/A"
            summaries_df[col] = default_val 

    # --- Merging --- 
    leads_df = pd.read_csv(output_dir / "leads.csv")
    
    # Ensure 'cleaned_phone' exists in leads_df for merging
    if 'cleaned_phone' not in leads_df.columns:
        logger.error("'cleaned_phone' column missing from leads.csv. Cannot merge summaries.")
        raise typer.Exit(1)
        
    # Ensure 'cleaned_phone_number' exists in summaries_df for merging
    if 'cleaned_phone_number' not in summaries_df.columns:
         logger.error("'cleaned_phone_number' column missing from summarization results. Cannot merge.")
         # Handle this case - maybe create an empty summaries_df if it failed entirely?
         if not summary_results: # If no summaries were processed at all
             summaries_df = pd.DataFrame(columns=['cleaned_phone_number'] + expected_summary_cols)
         else: # Should not happen if we add default dicts on error, but as fallback:
             raise typer.Exit(1)

    merged_df = leads_df.merge(
        summaries_df,
        left_on="cleaned_phone",
        right_on="cleaned_phone_number",
        how="left",
    )
    
    # Optional: Drop the redundant phone number column from the merge
    if 'cleaned_phone_number' in merged_df.columns:
        merged_df.drop(columns=['cleaned_phone_number'], inplace=True)
        
    # Determine the correct summary columns based on expected keys if provided
    summary_cols_to_fill = expected_yaml_keys_internal or [
        'result', 'stall_reason', 'key_interaction', 'suggestion', 'summary' # Default fallback
    ]
    
    # Fill NaN values that might result from the left merge (leads with no summary)
    # Use a dynamic approach based on expected keys
    fillna_values = {
        key: 'N/A' for key in summary_cols_to_fill 
    }
    # Override defaults for common keys if they exist in the list
    if 'result' in fillna_values: fillna_values['result'] = 'Merge Error or No Summary'
    if 'stall_reason' in fillna_values: fillna_values['stall_reason'] = 'OTHER'
    if 'reason_for_drop' in fillna_values: fillna_values['reason_for_drop'] = 'OTHER'
    if 'summary' in fillna_values: fillna_values['summary'] = 'N/A - Check logs or original data'

    # Only fillna for columns that actually exist in merged_df and are in our target list
    cols_to_fill = {k: v for k, v in fillna_values.items() if k in merged_df.columns and k in summary_cols_to_fill}
    merged_df.fillna(value=cols_to_fill, inplace=True)

    # Save the final analysis file
    to_csv(merged_df, csv_output_path) # Use new path
    # Optionally update HTML reporting if it uses specific columns
    # Check to_html function in reporting.py if necessary
    to_html(merged_df, html_output_path) # Use new path


@app.command()
def report(
    output_dir: Path = typer.Option(settings.OUTPUT_DIR, "--output-dir"),
    # Added: Recipe name for output filename
    recipe_name: Optional[str] = typer.Option(None, hidden=True, help="Internal use: Recipe name for output filename.")
):
    """Alias to generate HTML/CSV report from merged analysis if not already."""
    # Default recipe name if not provided (e.g., when called directly, not via 'run')
    _recipe_name = recipe_name or output_dir.name
    today_str = datetime.now().strftime('%Y%m%d')
    base_filename = f"{_recipe_name}_analysis_{today_str}"
    csv_input_path = output_dir / f"{base_filename}.csv" # Input is the new CSV name
    html_output_path = output_dir / f"{base_filename}.html" # Output is the new HTML name

    if not csv_input_path.is_file():
        typer.echo(f"{csv_input_path.name} not found. Run summarize first.")
        raise typer.Exit(1)

    df = pd.read_csv(csv_input_path)
    to_html(df, html_output_path) # Use new HTML path
    typer.echo(f"Report generated at {html_output_path.name}")


# --------------------------------------------------------------------------- #
# New unified pipeline runner utilising *recipe* folders
# --------------------------------------------------------------------------- #


@app.command(name="run")
def run_pipeline(
    recipe: str = typer.Option(..., "--recipe", help="Name of recipe folder inside 'recipes/'"),
    since: Optional[datetime] = typer.Option(None, "--since", help="Fetch leads created after this timestamp"),
    output_base: Path = typer.Option(settings.OUTPUT_DIR, "--output-dir", help="Base output directory (runs are stored under this/<recipe>)"),
    # Added: Skip flags
    skip_redshift: bool = typer.Option(False, "--skip-redshift", help="Skip the Redshift (fetch leads) step."),
    skip_bigquery: bool = typer.Option(False, "--skip-bigquery", help="Skip the BigQuery (fetch conversations) step."),
    skip_summarize: bool = typer.Option(False, "--skip-summarize", help="Skip the OpenAI summarization step."),
):
    """Run the lead‑recovery pipeline for the selected *recipe*.

    Allows skipping specific steps like Redshift, BigQuery, or Summarization.
    """

    from .recipe_loader import load_recipe  # Local import avoids circular deps

    try:
        rec = load_recipe(recipe)
    except FileNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)

    # ------------------------------------------------------------------- #
    # Configure output directory for this run
    # ------------------------------------------------------------------- #
    output_dir = (output_base / recipe).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------- #
    # Dynamically patch global settings with recipe‑specific files
    # ------------------------------------------------------------------- #
    original_rs_sql_path = settings.RS_SQL_PATH
    original_bq_sql_path = settings.BQ_SQL_PATH
    
    try:
        settings.RS_SQL_PATH = rec.redshift_sql_path
        if rec.bigquery_sql_path is not None:
            settings.BQ_SQL_PATH = rec.bigquery_sql_path

        logger.info("Running pipeline for recipe '%s'", recipe)
        logger.debug("Using SQL paths: RS=%s | BQ=%s", settings.RS_SQL_PATH, settings.BQ_SQL_PATH)

        # ------------------------------------------------------------------- #
        # Step 1 – Fetch leads
        # ------------------------------------------------------------------- #
        if not skip_redshift:
            logger.info("STEP 1: Fetching leads from Redshift...")
            fetch_leads(since=since, output_dir=output_dir)  # type: ignore[arg-type]
        else:
            logger.info("STEP 1: Skipped Redshift (fetch leads).")

        # ------------------------------------------------------------------- #
        # Step 2 – Fetch conversations (if bigquery.sql available)
        # ------------------------------------------------------------------- #
        if not skip_bigquery and rec.bigquery_sql_path and rec.bigquery_sql_path.exists():
            logger.info("STEP 2: Fetching conversations from BigQuery...")
            fetch_convos(output_dir=output_dir, batch_size=settings.BQ_BATCH_SIZE)
        elif skip_bigquery:
            logger.info("STEP 2: Skipped BigQuery (fetch conversations).")
            # Ensure an empty conversations.csv exists if skipping BQ but not summarize
            convos_path = output_dir / "conversations.csv"
            if not convos_path.exists() and not skip_summarize:
                 if 'pd' not in globals(): import pandas as pd
                 pd.DataFrame().to_csv(convos_path, index=False)
                 logger.debug("Created empty conversations.csv as BigQuery was skipped.")
        else:
            logger.warning("STEP 2: Recipe '%s' has no bigquery.sql – skipping conversation fetch.", recipe)
            # Ensure an empty conversations.csv exists so `summarize` step doesn't abort
            convos_path = output_dir / "conversations.csv"
            if not convos_path.exists() and not skip_summarize:
                 if 'pd' not in globals(): import pandas as pd
                 pd.DataFrame().to_csv(convos_path, index=False)
                 logger.debug("Created empty conversations.csv as recipe has no BQ file.")

        # ------------------------------------------------------------------- #
        # Step 3 – Summarise conversations
        # ------------------------------------------------------------------- #
        if not skip_summarize:
            logger.info("STEP 3: Summarizing conversations...")
            # Pass expected keys from the recipe to the summarize function
            summarize(
                output_dir=output_dir, 
                prompt_template_path=rec.prompt_path, 
                max_workers=4, # Explicitly pass default max_workers
                expected_yaml_keys_internal=rec.expected_yaml_keys, # Pass the keys
                recipe_name=recipe # Pass recipe name
            ) 
        else:
            logger.info("STEP 3: Skipped Summarization.")

        # ------------------------------------------------------------------- #
        # Step 4 – Generate report (HTML)
        # ------------------------------------------------------------------- #
        report(output_dir=output_dir, recipe_name=recipe) # Pass recipe name

    finally:
        # Restore original settings
        settings.RS_SQL_PATH = original_rs_sql_path
        settings.BQ_SQL_PATH = original_bq_sql_path
        logger.debug("Restored original SQL path settings.")


def main() -> None:  # noqa: D401
    """CLI entrypoint."""
    app()


if __name__ == "__main__":
    main() 