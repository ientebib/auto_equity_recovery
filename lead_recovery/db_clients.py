"""db_clients.py
DB connection and query helpers for Redshift and BigQuery.
"""
from __future__ import annotations

import logging
import re
import time
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import redshift_connector
from google.cloud import bigquery

from .config import settings

logger = logging.getLogger(__name__)


def _redact_pii(sql: str) -> str:
    """Redact potentially sensitive information from SQL for logging."""
    # Redact phone numbers, emails, and other PII patterns
    sql = re.sub(r'\b\d{10,}\b', '[PHONE_REDACTED]', sql)
    sql = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]', sql)
    return sql


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
        except Exception:  # noqa: BLE001
            logger.exception("Failed to connect to Redshift")
            raise

    # ------------------------------------------------------------------ #
    def query(self, sql: str, params: Dict[str, Any] | None = None) -> pd.DataFrame:
        """Execute *sql* with optional *params* and return a DataFrame."""
        try:
            logger.debug("Executing Redshift query: %s with params: %s", 
                        _redact_pii(sql), {k: '[REDACTED]' if k.lower() in ('phone', 'email', 'password') else v 
                                        for k, v in (params or {}).items()})
            start_time = time.time()
            conn = self.connect()
            with conn.cursor() as cur:
                cur.execute(sql, params or {})
                rows = cur.fetchall()
                columns = [col[0] for col in cur.description]
            duration = time.time() - start_time
            df = pd.DataFrame(rows, columns=columns)
            logger.debug("Redshift query completed in %.2f seconds, returned %d rows", duration, len(df))
            return df
        except Exception:  # noqa: BLE001
            logger.exception("Redshift query failed")
            raise


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
            project = getattr(settings, "BQ_PROJECT", None)
            self._client = bigquery.Client(project=project) if project else bigquery.Client()
            if project:
                logger.debug("Initialised BigQuery client for project %s", project)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to instantiate BigQuery client")
            raise

    # ------------------------------------------------------------------ #
    def query(
        self, sql: str, params: List[Any] | None = None
    ) -> pd.DataFrame:
        """Run a parameterised query and return a DataFrame, handling large results via temp files."""
        temp_dir = None
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
            
            start_time = time.time()
            job_config = bigquery.QueryJobConfig(query_parameters=params or [])
            job = self._client.query(sql, job_config=job_config)
            
            # Use an iterator to handle potentially large results
            # Convert directly to DataFrame (simplification)
            results_iterator = job.result()
            final_df = results_iterator.to_dataframe()
            
            duration = time.time() - start_time
            logger.info(
                "BigQuery query processing complete. Total rows: %d. Total time: %.2f seconds", 
                len(final_df), time.time() - start_time
            )
            return final_df

        except Exception:  # noqa: BLE001
            logger.exception("BigQuery query failed")
            raise
        finally:
            pass
            # Clean up temporary directory and files (No longer needed)
            # if temp_dir and temp_dir.exists():
            #      try:
            #          for item in temp_dir.iterdir():
            #              item.unlink()
            #          temp_dir.rmdir()
            #          logger.debug("Cleaned up temporary directory: %s", temp_dir)
            #      except Exception as e:
            #          logger.error("Failed to clean up temporary directory %s: %s", temp_dir, e) 