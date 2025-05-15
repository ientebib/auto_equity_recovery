"""reporting.py
Functions to output analysis results to CSV, HTML, and JSON formats.
"""
from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

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


def prepare_dataframe_for_export(df: pd.DataFrame, columns: Optional[List[str]] = None) -> pd.DataFrame:
    """Prepare a DataFrame for export by cleaning and filtering it.
    
    Args:
        df: Input DataFrame to prepare
        columns: Optional list of columns to include in the specified order
        
    Returns:
        A clean DataFrame ready for export
        
    Raises:
        ValueError: If df is None or empty with no columns
    """
    # Basic validation
    if df is None:
        raise ValueError("Cannot export None DataFrame")
    if df.empty and len(df.columns) == 0:
        raise ValueError("Cannot export completely empty DataFrame with no columns")
    
    # Make a copy to avoid modifying the original
    result_df = df.copy()
    
    # Explicitly remove timing_reasoning if present
    if 'timing_reasoning' in result_df.columns:
        logger.info("Removing 'timing_reasoning' column from output before exporting")
        result_df = result_df.drop(columns=['timing_reasoning'])
    
    # Apply column filtering if specified
    if columns:
        result_df = filter_dataframe_columns(result_df, columns)
    
    # Replace NaN values with empty string for better export compatibility
    result_df = result_df.fillna('')
    
    return result_df


def to_csv(df: pd.DataFrame, path: Path, columns: Optional[List[str]] = None, quoting=csv.QUOTE_MINIMAL) -> Path:
    """Write DataFrame to a CSV file and return the path.
    
    Args:
        df: DataFrame to write.
        path: Path to write to.
        columns: Optional list of column names to include in the output, in the specified order.
        quoting: CSV quoting behavior.
        
    Returns:
        The path where the CSV was written.
        
    Raises:
        ValueError: If df is None or empty with no columns
        IOError: If there's an error writing to the file
    """
    path = Path(path)  # Ensure path is a Path object
    path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Prepare the DataFrame for export
        export_df = prepare_dataframe_for_export(df, columns)
        
        # Write to CSV
        export_df.to_csv(path, index=False, encoding='utf-8-sig', quoting=quoting)  # Use utf-8-sig encoding for better compatibility with Spanish characters in Excel
        logger.info("CSV written to %s", path)
        return path
    except ValueError as e:
        logger.error(f"Data validation error when writing CSV: {e}")
        raise
    except Exception as e:
        logger.error(f"Error writing CSV to {path}: {e}")
        raise IOError(f"Failed to write CSV to {path}: {e}") from e


def to_html(df: pd.DataFrame, path: Path, columns: Optional[List[str]] = None) -> Path:
    """Write DataFrame to an HTML table file and return the path.
    
    Args:
        df: DataFrame to write.
        path: Path to write to.
        columns: Optional list of column names to include in the output, in the specified order.
        
    Returns:
        The path where the HTML was written.
        
    Raises:
        ValueError: If df is None or empty with no columns
        IOError: If there's an error writing to the file
    """
    path = Path(path)  # Ensure path is a Path object
    path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Prepare the DataFrame for export
        export_df = prepare_dataframe_for_export(df, columns)
        
        # Write to HTML
        export_df.to_html(path, index=False, justify="center")
        logger.info("HTML written to %s", path)
        return path
    except ValueError as e:
        logger.error(f"Data validation error when writing HTML: {e}")
        raise
    except Exception as e:
        logger.error(f"Error writing HTML to {path}: {e}")
        raise IOError(f"Failed to write HTML to {path}: {e}") from e


def to_json(df: pd.DataFrame, path: Path, columns: Optional[List[str]] = None, orient: str = "records") -> Path:
    """Write DataFrame to a JSON file and return the path.
    
    Args:
        df: DataFrame to write.
        path: Path to write to.
        columns: Optional list of column names to include in the output, in the specified order.
        orient: Orientation of the JSON output. Default is "records" which produces a list of objects.
            See pandas.DataFrame.to_json documentation for other options.
        
    Returns:
        The path where the JSON was written.
        
    Raises:
        ValueError: If df is None or empty with no columns
        IOError: If there's an error writing to the file
    """
    path = Path(path)  # Ensure path is a Path object
    path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Prepare the DataFrame for export
        export_df = prepare_dataframe_for_export(df, columns)
        
        # Write to JSON
        export_df.to_json(path, orient=orient, date_format="iso", indent=2)
        logger.info("JSON written to %s", path)
        return path
    except ValueError as e:
        logger.error(f"Data validation error when writing JSON: {e}")
        raise
    except Exception as e:
        logger.error(f"Error writing JSON to {path}: {e}")
        raise IOError(f"Failed to write JSON to {path}: {e}") from e


def export_data(
    df: pd.DataFrame, 
    output_dir: Path, 
    base_name: str, 
    formats: Union[List[str], str] = "csv", 
    columns: Optional[List[str]] = None
) -> Dict[str, Path]:
    """Export DataFrame to multiple formats in one operation.
    
    Args:
        df: DataFrame to export
        output_dir: Directory to write files to
        base_name: Base filename without extension
        formats: Format(s) to export to. Can be a string (e.g., "csv") or list of strings (e.g., ["csv", "html", "json"])
        columns: Optional list of columns to include
        
    Returns:
        Dictionary mapping format names to output paths
        
    Raises:
        ValueError: If no valid formats are specified or data validation fails
        IOError: If there's an error writing to any of the files
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Convert string format to list
    if isinstance(formats, str):
        formats = [formats.lower()]
    else:
        formats = [f.lower() for f in formats]
    
    # Validate formats
    valid_formats = ["csv", "html", "json"]
    for fmt in formats:
        if fmt not in valid_formats:
            logger.warning(f"Ignoring unsupported format: {fmt}")
    
    formats = [fmt for fmt in formats if fmt in valid_formats]
    if not formats:
        raise ValueError(f"No valid export formats specified. Supported formats: {valid_formats}")
    
    # Prepare the DataFrame once for all exports
    try:
        export_df = prepare_dataframe_for_export(df, columns)
    except ValueError as e:
        logger.error(f"Data validation error during export: {e}")
        raise
    
    # Export to each format
    result_paths = {}
    for fmt in formats:
        output_path = output_dir / f"{base_name}.{fmt}"
        try:
            if fmt == "csv":
                result_paths["csv"] = to_csv(export_df, output_path)
            elif fmt == "html":
                result_paths["html"] = to_html(export_df, output_path)
            elif fmt == "json":
                result_paths["json"] = to_json(export_df, output_path)
        except Exception as e:
            logger.error(f"Error exporting to {fmt} format: {e}")
            # Continue with other formats instead of failing completely
    
    return result_paths 