"""reporting.py
Functions to output analysis results to CSV and HTML.
"""
from __future__ import annotations

import logging
import csv
from pathlib import Path
from typing import List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


def filter_dataframe_columns(df: pd.DataFrame, columns: Optional[List[str]] = None) -> pd.DataFrame:
    """Filter DataFrame to only include specified columns in the specified order.
    
    Args:
        df: Input DataFrame.
        columns: List of column names to keep. If None, return the original DataFrame.
        
    Returns:
        A DataFrame with only the specified columns, in the specified order.
        If columns is None or empty, or if none of the specified columns exist,
        returns the original DataFrame.
    """
    if not columns:
        return df
        
    # Find which of the requested columns actually exist in the DataFrame
    existing_columns = [col for col in columns if col in df.columns]
    
    if not existing_columns:
        logger.warning("None of the specified output columns exist in the DataFrame, returning original DataFrame")
        return df
        
    # Log which columns were requested but don't exist
    missing_columns = set(columns) - set(existing_columns)
    if missing_columns:
        logger.debug(f"Columns specified in output_columns but not found in DataFrame: {missing_columns}")
    
    # Return a DataFrame with only the specified columns, in the specified order
    return df[existing_columns]


def to_csv(df: pd.DataFrame, path: Path, columns: Optional[List[str]] = None, quoting=csv.QUOTE_MINIMAL) -> Path:
    """Write DataFrame to *path* (CSV) and return the path.
    
    Args:
        df: DataFrame to write.
        path: Path to write to.
        columns: Optional list of column names to include in the output, in the specified order.
        quoting: CSV quoting behavior.
        
    Returns:
        The path where the CSV was written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Explicitly remove timing_reasoning if present
    if 'timing_reasoning' in df.columns:
        logger.info("Removing 'timing_reasoning' column from output before writing to CSV")
        df = df.drop(columns=['timing_reasoning'])
    
    # Apply column filtering if specified
    if columns:
        df = filter_dataframe_columns(df, columns)
        
    df.to_csv(path, index=False, encoding='utf-8-sig', quoting=quoting)  # Use utf-8-sig encoding for better compatibility with Spanish characters in Excel
    logger.info("CSV written to %s", path)
    return path


def to_html(df: pd.DataFrame, path: Path, columns: Optional[List[str]] = None) -> Path:
    """Write DataFrame to *path* (HTML table).
    
    Args:
        df: DataFrame to write.
        path: Path to write to.
        columns: Optional list of column names to include in the output, in the specified order.
        
    Returns:
        The path where the HTML was written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Apply column filtering if specified
    if columns:
        df = filter_dataframe_columns(df, columns)
        
    df.to_html(path, index=False, justify="center")
    logger.info("HTML written to %s", path)
    return path 