"""CLI command for fetching WhatsApp conversations from BigQuery."""
import csv
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from queue import Empty as QueueEmpty
from queue import Queue
from typing import Optional

import pandas as pd
import typer

# BigQuery imports used directly
from google.cloud.bigquery import ArrayQueryParameter, QueryJobConfig
from tqdm import tqdm

from ..config import settings
from ..db_clients import BigQueryClient
from ..reporting import to_csv
from ..utils import load_sql_file

logger = logging.getLogger(__name__)

app = typer.Typer()

@app.callback(invoke_without_command=True)
def fetch_convos(
    batch_size: int = typer.Option(settings.BQ_BATCH_SIZE, "--batch-size", help="Number of phone numbers per BigQuery request."),
    output_dir: Path = typer.Option(settings.OUTPUT_DIR, "--output-dir"),
    sql_file: Optional[Path] = typer.Option(None, "--sql-file", help="Path to SQL file for querying conversations"),
):
    """Fetch WhatsApp conversation history for all target leads."""
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Check leads CSV exists first
    leads_path = output_dir / "leads.csv"
    if not leads_path.is_file():
        typer.echo("Leads CSV not found. Run fetch-leads first.")
        raise typer.Exit(1)

    # Use provided SQL file or try to find a default in recipe dir
    if sql_file is None:
        # Look in the output_dir for bigquery.sql (assuming recipe structure)
        recipe_dir = output_dir
        if "output_run" in str(output_dir):
            # If in the output_run dir, try to find the corresponding recipe
            recipe_name = output_dir.name
            recipe_dir = settings.PROJECT_ROOT / "recipes" / recipe_name
            
        sql_file = recipe_dir / "bigquery.sql"
        logger.info(f"No SQL file provided, looking for {sql_file}")
    
    if not sql_file.exists():
        logger.error(f"SQL file not found: {sql_file}")
        raise typer.Exit(1)
        
    logger.info(f"Using SQL file: {sql_file}")

    # Use pandas to robustly read leads.csv and extract phone numbers
    try:
        leads_df = pd.read_csv(leads_path, dtype=str)
        if 'cleaned_phone' in leads_df.columns:
            phones = leads_df['cleaned_phone'].dropna().astype(str).str.strip()
            phones = [p for p in phones if p]
            phones = list(set(phones))
        else:
            phones = []
    except Exception as e:
        logger.error(f"Error reading leads.csv with pandas: {e}", exc_info=True)
        raise typer.Exit(1)

    if not phones:
        logger.warning("No valid phone numbers found in leads.csv to fetch conversations for.")
        # Ensure the output CSV has the expected header even if empty
        convos_df = pd.DataFrame(columns=["cleaned_phone_number"]) # Define expected columns
        to_csv(convos_df, output_dir / "conversations.csv")
        logger.info("Created empty conversations.csv file with headers only")
        return # Exit early

    # Initialize BigQuery client and load SQL
    bq_client = BigQueryClient()
    sql_template = load_sql_file(sql_file)
    convos_csv_path = output_dir / "conversations.csv"

    # Chunk phone numbers for batch processing
    phones_chunks = [phones[i : i + batch_size] for i in range(0, len(phones), batch_size)]
    logger.info("Fetching BQ data for %d phones in %d chunks (size %d, max concurrent %d)",
                len(phones), len(phones_chunks), batch_size, settings.BQ_MAX_CONCURRENT_QUERIES)

    # If only one chunk, just do a direct stream to CSV
    if len(phones_chunks) == 1:
        try:
            logger.info("Processing single chunk of %d phones - streaming directly to CSV", len(phones))
            bq_client.query_to_csv(
                sql_template,
                convos_csv_path,
                [ArrayQueryParameter("target_phone_numbers_list", "STRING", phones)]
            )
            logger.info("Completed BQ fetch - data written to %s", convos_csv_path)
            return
        except Exception as e:
            logger.error("Error fetching conversations: %s", e, exc_info=True)
            raise typer.Exit(1)

    # For multiple chunks, use a streaming approach with a shared queue
    # Create thread-safe queue and semaphore for line processing
    line_queue = Queue(maxsize=10000)  # Limit queue size to avoid memory issues
    header_event = threading.Event()  # Signal when header is written
    write_complete = threading.Event()  # Signal when writing is complete
    failed_chunks = []
    
    # Writer thread function
    def csv_writer_thread():
        try:
            with open(convos_csv_path, 'w', encoding='utf-8', newline='') as outfile:
                writer = None  # Will be initialized when the first line arrives
                
                while not (write_complete.is_set() and line_queue.empty()):
                    try:
                        item = line_queue.get(timeout=1.0)
                        
                        if item is None:  # Sentinel value
                            line_queue.task_done()
                            continue
                            
                        if isinstance(item, list):  # Header fields
                            writer = csv.DictWriter(outfile, fieldnames=item)
                            writer.writeheader()
                            header_event.set()  # Signal that header is written
                        elif isinstance(item, dict):  # Data row
                            if writer is None:
                                # Should not happen with proper coordination
                                logger.error("Got data row before header was set", exc_info=True)
                                line_queue.task_done()
                                continue
                            writer.writerow(item)
                        
                        line_queue.task_done()
                    except QueueEmpty:
                        # Timeout occurred, just continue and check conditions again
                        pass
                    except Exception as e:
                        logger.error(f"Error in writer thread: {e}", exc_info=True)
                        line_queue.task_done()
            
            logger.info(f"CSV writer thread completed, data written to {convos_csv_path}")
        except Exception as e:
            logger.error(f"Fatal error in writer thread: {e}", exc_info=True)
    
    # Start the writer thread
    writer_thread = threading.Thread(target=csv_writer_thread, daemon=True)
    writer_thread.start()
    
    try:
        # Process chunks in parallel with ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=settings.BQ_MAX_CONCURRENT_QUERIES) as executor:
            futures = []
            
            # Process function that handles one chunk and feeds to queue
            def process_chunk(chunk_idx, phone_chunk):
                try:
                    job_config = QueryJobConfig(query_parameters=[
                        ArrayQueryParameter("target_phone_numbers_list", "STRING", phone_chunk)
                    ])
                    
                    # Start the query job
                    query_job = bq_client._client.query(sql_template, job_config=job_config)
                    
                    # Get the schema (field names)
                    iterator = query_job.result()
                    field_names = [field.name for field in iterator.schema]
                    
                    # If this is the first chunk to complete, send the header
                    if not header_event.is_set():
                        line_queue.put(field_names)
                    
                    # Wait for header to be written before sending rows
                    # This ensures rows aren't written before the header
                    header_event.wait(timeout=60)
                    
                    # Stream rows to the queue
                    row_count = 0
                    for row in iterator:
                        # Convert row values to Python dict
                        row_dict = {field: value for field, value in zip(field_names, row.values())}
                        line_queue.put(row_dict)
                        row_count += 1
                        
                    logger.info(f"Chunk {chunk_idx} completed: {row_count} rows streamed to queue")
                    return row_count
                except Exception as e:
                    first_phone = phone_chunk[0] if phone_chunk else 'N/A'
                    logger.error(f"Error processing chunk {chunk_idx} starting with {first_phone}: {e}", exc_info=True)
                    raise e
            
            # Submit all chunks for processing
            for i, chunk in enumerate(phones_chunks):
                future = executor.submit(process_chunk, i, chunk)
                futures.append((i, chunk, future))
            
            # Process completed futures with progress bar
            total_rows = 0
            for i, chunk, future in tqdm([(i, c, f) for i, c, f in futures], desc="Fetching Convos", unit="batch"):
                try:
                    chunk_rows = future.result()
                    total_rows += chunk_rows
                except Exception:
                    # Already logged in process_chunk
                    first_phone = chunk[0] if chunk else 'N/A'
                    failed_chunks.append((i, first_phone))
        
        # Signal that all processing is complete
        write_complete.set()
        
        # Wait for queue to be empty 
        line_queue.join()
        
        # Wait for writer thread to complete
        writer_thread.join(timeout=30)
        
        if total_rows == 0 and failed_chunks:
            logger.error("All chunks failed, no data retrieved", exc_info=True)
            raise typer.Exit(1)
        
        # Report any failures
        if failed_chunks:
            logger.warning("%d out of %d chunks failed to fetch", len(failed_chunks), len(phones_chunks))
            for i, phone in failed_chunks:
                logger.warning("Failed chunk %d starting with phone %s", i, phone)
        
        logger.info(f"BigQuery fetch completed: {total_rows} total rows written to {convos_csv_path}")
        
    except Exception as e:
        logger.error(f"Error in fetch_convos: {e}", exc_info=True)
        # Signal writer to exit and clean up
        write_complete.set()
        if writer_thread.is_alive():
            writer_thread.join(timeout=5)
        raise typer.Exit(1) 