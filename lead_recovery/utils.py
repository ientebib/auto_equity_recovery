"""utils.py
Generic utility functions used across the lead recovery pipeline.
"""
from __future__ import annotations

import logging
import pandas as pd
from pathlib import Path
from typing import Any, Dict

from .config import settings

logger = logging.getLogger(__name__)


def clean_email(raw: str | None) -> str:
    """Normalise email address: lowercase + remove plus‑aliases.

    Example: ``Foo+Bar@Example.com`` → ``foo@example.com``.
    """
    if not raw:
        return ""
    local, _, domain = raw.partition("@")
    local = local.split("+", 1)[0]
    return f"{local.lower()}@{domain.lower()}" if domain else raw.lower()


def load_sql_file(file_path: Path | str) -> str:
    """Read SQL content from a file.
    
    Args:
        file_path: Path to the SQL file (Path object or string)
        
    Returns:
        SQL content as a string
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the file exists but is empty
        TypeError: If file_path is not a string or Path object
    """
    # Convert to Path object if it's a string
    if isinstance(file_path, str):
        file_path = Path(file_path)
    elif not isinstance(file_path, Path):
        raise TypeError(f"Expected file_path to be a string or Path object, got {type(file_path)}")

    # Check if file exists    
    if not file_path.is_file():
        logger.error("SQL file not found: %s", file_path)
        raise FileNotFoundError(f"SQL file not found: {file_path}")

    # Read file content
    try:
        sql = file_path.read_text(encoding="utf-8").strip()
    except Exception as e:
        logger.error(f"Error reading SQL file {file_path}: {e}")
        raise IOError(f"Could not read SQL file {file_path}: {e}") from e

    # Check if file is empty
    if not sql:
        logger.error("SQL file at %s is empty", file_path)
        raise ValueError(f"SQL file at {file_path} is empty.")

    logger.debug("Loaded SQL file '%s' (%d chars)", file_path, len(sql))
    return sql


def log_memory_usage(prefix: str = ""):
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


def optimize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Optimize the memory usage of a DataFrame."""
    # Optimize string columns
    for col in df.columns:
        if df[col].dtype == 'object':
            try:
                df[col] = df[col].astype("string[pyarrow]")
            except (ImportError, TypeError):
                # Fall back if pyarrow not available or column has mixed types
                pass
    return df 