"""db_clients.py
DB connection and query helpers for Redshift and BigQuery.
"""
from __future__ import annotations

import csv
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import redshift_connector
from google.cloud import bigquery

from .config import settings
from .exceptions import DatabaseConnectionError, DatabaseQueryError

logger = logging.getLogger(__name__)


def _redact_pii(sql: str) -> str:
    """Redact potentially sensitive information from SQL for logging."""
    # Redact phone numbers, emails, and other PII patterns
    sql = re.sub(r'\b\d{10,}\b', '[PHONE_REDACTED]', sql)
    sql = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]', sql)
    return sql


def _log_memory_usage(prefix: str = ""):
    """Log current memory usage of the process."""
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024
        logger.debug(f"{prefix}Memory usage: {memory_mb:.1f} MB")
    except ImportError:
        # psutil not available, skip memory logging
        pass


class RedshiftClient:
    """Lightweight wrapper around a Redshift connection."""

    def __init__(self) -> None:
        self._conn: redshift_connector.Connection | None = None

    # ------------------------------------------------------------------ #
    def connect(self) -> redshift_connector.Connection:  # noqa: D401
        """Return a cached or fresh Redshift connection."""
        # Check if connection exists and is open using getattr for compatibility
        conn_is_closed = getattr(self._conn, "is_closed", getattr(self._conn, "closed", None))
        if self._conn and conn_is_closed is False:
            return self._conn
        # Handle case where neither attribute exists (unlikely but safe)
        # if self._conn and conn_is_closed is None:
        #    logger.warning("Could not determine if Redshift connection is closed.")
        #    # Decide behavior: try to use it, or force reconnect? Force reconnect is safer.
        #    pass # Fall through to reconnect

        try:
            self._conn = redshift_connector.connect(
                host=settings.REDSHIFT_HOST,
                database=settings.REDSHIFT_DB,
                user=settings.REDSHIFT_USER,
                password=settings.REDSHIFT_PASS,
                port=settings.REDSHIFT_PORT,
            )
            logger.info("Connected to Redshift %s", settings.REDSHIFT_HOST)
            return self._conn
        except Exception as e:  # Catch specific connection errors if possible, otherwise wrap
            logger.exception("Failed to connect to Redshift")
            # Wrap the original exception for context
            raise DatabaseConnectionError(f"Redshift connection failed: {e}") from e

    # ------------------------------------------------------------------ #
    def query(self, sql: str, params: List[Any] | Tuple[Any, ...] | None = None) -> pd.DataFrame:
        """Execute *sql* with optional *params* and return a DataFrame.
        
        Args:
            sql: SQL query to execute. Use %s for parameter placeholders.
            params: List or tuple of parameter values for positional %s placeholders.
            
        Returns:
            pandas DataFrame with query results
        """
        try:
            # Log params as is for now, or use a generic redaction for lists if preferred.
            # For example: params_to_log = "[PARAMS_LIST_REDACTED]" if params else "None"
            params_to_log = params if params is not None else "None"
            logger.debug("Executing Redshift query: %s with params: %s", 
                        _redact_pii(sql), params_to_log)
            
            start_time = time.time()
            conn = self.connect()
            
            with conn.cursor() as cur:
                # Use proper parameterized queries
                if params:
                    cur.execute(sql, params)
                else:
                    cur.execute(sql)
                
                rows = [tuple(row) for row in cur.fetchall()] # Ensure rows are tuples
                columns = [col[0] for col in cur.description]
            
            duration = time.time() - start_time
            
            _log_memory_usage("Before DataFrame creation: ")
            df = pd.DataFrame(rows, columns=columns)
            
            # Optimize memory usage for string columns
            for col in df.columns:
                if df[col].dtype == 'object':
                    try:
                        df[col] = df[col].astype("string[pyarrow]")
                    except (ImportError, TypeError):
                        # Fall back if pyarrow not available or column has mixed types
                        pass
            
            _log_memory_usage("After DataFrame optimization: ")
            logger.debug("Redshift query completed in %.2f seconds, returned %d rows", duration, len(df))
            return df
        except Exception as e:
            logger.exception("Redshift query failed")
            raise DatabaseQueryError(f"Redshift query failed: {e}") from e
            
    def query_from_file(self, file_path: Path | str, params: List[Any] | Tuple[Any, ...] | None = None) -> pd.DataFrame:
        """Execute a SQL query from a file with optional parameters and return the results as a DataFrame.
        
        Args:
            file_path: Path to the SQL file
            params: Optional list or tuple of parameters for the query.
            
        Returns:
            pandas DataFrame with query results
            
        Raises:
            FileNotFoundError: If the SQL file doesn't exist
            DatabaseConnectionError: If connection to Redshift fails
            DatabaseQueryError: If the query execution fails
        """
        from .utils import load_sql_file
        
        try:
            # Load SQL from file
            sql = load_sql_file(file_path)
            
            # Execute the query
            return self.query(sql, params)
        except FileNotFoundError:
            # Re-raise file not found errors directly
            raise
        except IOError as e:
            # Wrap IO errors for context
            logger.error(f"Error reading SQL file: {e}")
            raise DatabaseQueryError(f"Error reading SQL file: {e}") from e
        except Exception as e:
            # Wrap any other exceptions
            logger.error(f"Error executing SQL from file {file_path}: {e}")
            raise DatabaseQueryError(f"Error executing SQL from file {file_path}: {e}") from e


class BigQueryClient:
    """Wrapper around google-cloud-bigquery for Pandas results."""

    def __init__(self) -> None:
        """Instantiate a BigQuery client.

        If the optional ``settings.BQ_PROJECT`` is provided (e.g. via env
        var), pass it explicitly so the code can run outside of GCP where
        ADC might not infer a default project.  Otherwise fall back to the
        default google‑cloud‑bigquery behaviour.
        """
        try:
            # --- REVERTED: Use standard project/credential loading --- #
            project = getattr(settings, "BQ_PROJECT", None)
            # Use default client instantiation - relies on GOOGLE_APPLICATION_CREDENTIALS env var or ADC
            self._client = bigquery.Client(project=project, location="US") if project else bigquery.Client(location="US")
            if project:
                logger.debug("Initialised BigQuery client for project %s", project)
            else: 
                logger.debug("Initialised BigQuery client using default project/credentials.")
            # --- END REVERT --- #    
        except Exception as e:
            logger.exception("Failed to instantiate BigQuery client")
            raise DatabaseConnectionError(f"BigQuery client instantiation failed: {e}") from e

    # ------------------------------------------------------------------ #
    def query(
        self, sql: str, params: List[Any] | None = None
    ) -> pd.DataFrame:
        """Run a parameterised query and return a DataFrame, handling large results via temp files."""
        
        try:
            # Log query details with PII redacted and safe attribute access
            if params:
                params_str_parts = []
                for p in params:
                    # Use getattr for safe access to type/value attributes
                    p_name = getattr(p, "name", "UNKNOWN_PARAM")
                    type_ = getattr(p, "type_", getattr(p, "array_type", "UNKNOWN_TYPE"))
                    
                    # Redact value based on name or if it's an array
                    is_sensitive = p_name.lower() in ('phone', 'target_phone_numbers_list')
                    is_array = hasattr(p, "values") # Check for ArrayQueryParameter specific attr

                    if is_sensitive:
                        value_str = '[REDACTED]'
                    elif is_array:
                         # For arrays, maybe log length instead of redacting entirely?
                         array_len = len(getattr(p, 'values', []))
                         value_str = f"[ARRAY(len={array_len})]" 
                         # Or keep it simple: value_str = "[REDACTED_ARRAY]"
                    else:
                        value_str = str(getattr(p, "value", "[UNKNOWN_VALUE]"))

                    params_str_parts.append(f"{p_name}={type_}:{value_str}")
                params_str = ", ".join(params_str_parts)
            else:
                 params_str = "None"

            # Redact the SQL string itself
            logged_sql = _redact_pii(sql)

            logger.debug("Executing BigQuery query: %s with params: %s", logged_sql, params_str)
            
            _log_memory_usage("Before BigQuery query: ")
            start_time = time.time()
            job_config = bigquery.QueryJobConfig(query_parameters=params or [])
            
            # Cache the query job to avoid recomputing query plan for the same SQL
            job = self._client.query(sql, job_config=job_config)
            
            # Get the schema (field names)
            results_iterator = job.result()
            schema = [field.name for field in results_iterator.schema]
            
            # Stream results into chunks
            row_count = 0
            chunk_size = 10000
            current_chunk = []
            all_chunks = []  # Store all chunks to concatenate once at the end
            
            logger.debug("Streaming BigQuery results into chunks...")
            
            for row in results_iterator:
                current_chunk.append({field: value for field, value in zip(schema, row.values())})
                row_count += 1
                
                # When we reach chunk_size, append to chunks list
                if len(current_chunk) >= chunk_size:
                    chunk_df = pd.DataFrame(current_chunk)
                    # Optimize memory usage for string columns
                    for col in chunk_df.columns:
                        if chunk_df[col].dtype == 'object':
                            try:
                                chunk_df[col] = chunk_df[col].astype("string[pyarrow]")
                            except (ImportError, TypeError):
                                # Fall back if pyarrow not available or column has mixed types
                                pass
                    
                    # Add to chunks list instead of concatenating incrementally
                    all_chunks.append(chunk_df)
                    current_chunk = []
                    _log_memory_usage(f"After processing {row_count} rows: ")
                    logger.debug(f"Processed {row_count} rows from BigQuery")
            
            # Don't forget the last chunk if any rows remain
            if current_chunk:
                chunk_df = pd.DataFrame(current_chunk)
                # Optimize memory usage for string columns
                for col in chunk_df.columns:
                    if chunk_df[col].dtype == 'object':
                        try:
                            chunk_df[col] = chunk_df[col].astype("string[pyarrow]")
                        except (ImportError, TypeError):
                            # Fall back if pyarrow not available or column has mixed types
                            pass
                
                # Add to chunks list
                all_chunks.append(chunk_df)
            
            # Concatenate all chunks once, instead of incrementally
            if all_chunks:
                logger.debug(f"Concatenating {len(all_chunks)} chunks into final DataFrame...")
                final_df = pd.concat(all_chunks, ignore_index=True)
            else:
                # Create empty DataFrame with correct schema if no data
                final_df = pd.DataFrame(columns=schema)
            
            duration = time.time() - start_time
            _log_memory_usage("After BigQuery processing: ")
            logger.info(
                "BigQuery query processing complete. Total rows: %d. Total time: %.2f seconds", 
                row_count, duration
            )
            return final_df

        except Exception as e:
            logger.exception("BigQuery query failed")
            raise DatabaseQueryError(f"BigQuery query failed: {e}") from e
            
    def query_to_csv(
        self, sql: str, output_path: Path | str, params: List[Any] | None = None
    ) -> Path:
        """Run a query and stream results directly to a CSV file, avoiding memory issues.
        
        Args:
            sql: SQL query to execute
            output_path: Path where CSV will be saved
            params: Optional query parameters
            
        Returns:
            Path to the saved CSV file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Log query details with redacted PII
            logged_sql = _redact_pii(sql)
            logger.debug("Executing BigQuery query to CSV: %s", logged_sql)
            
            _log_memory_usage("Before BigQuery CSV query: ")
            start_time = time.time()
            job_config = bigquery.QueryJobConfig(query_parameters=params or [])
            
            # Start the query
            query_job = self._client.query(sql, job_config=job_config)
            
            # Wait for the query to complete
            iterator = query_job.result()
            schema = [field.name for field in iterator.schema]
            
            # Open CSV file for writing
            with open(output_path, 'w', newline='', encoding='utf-8') as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=schema)
                writer.writeheader()
                
                # Stream rows to CSV
                row_count = 0
                for row in iterator:
                    writer.writerow({field: value for field, value in zip(schema, row.values())})
                    row_count += 1
                    
                    # Log progress occasionally
                    if row_count % 50000 == 0:
                        _log_memory_usage(f"After streaming {row_count} rows: ")
                        logger.debug(f"Streamed {row_count} rows to CSV")
            
            duration = time.time() - start_time
            _log_memory_usage("After BigQuery CSV processing: ")
            logger.info(
                "BigQuery query to CSV complete. Wrote %d rows to %s. Total time: %.2f seconds", 
                row_count, output_path, duration
            )
            return output_path
            
        except Exception as e:
            logger.exception(f"BigQuery query to CSV failed: {e}")
            raise DatabaseQueryError(f"BigQuery query to CSV failed: {e}") from e 