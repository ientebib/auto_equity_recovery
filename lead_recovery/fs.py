"""fs.py
File system utility functions for the lead recovery pipeline.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

def update_link(src: Path, link: Path):
    """Refresh *link* to point at *src*.

    • First tries to remove any existing file/symlink at *link* (missing_ok=True so we don't error).
    • Creates a relative symlink.  If the filesystem disallows symlinks (or permissions fail),
      falls back to copying the file so downstream code still works.
    """
    try:
        # Python ≥3.8: missing_ok avoids FileNotFoundError
        link.unlink(missing_ok=True)
        link.symlink_to(src.relative_to(link.parent))
    except Exception as e:  # pragma: no cover – fallback when symlinks not allowed
        logger.debug("Symlink failed (%s). Falling back to file copy for %s", e, link)
        try:
            shutil.copy2(src, link)
        except Exception as copy_err:
            logger.error("Failed to copy %s to %s: %s", src, link, copy_err)

def ensure_dir(path: Path) -> Path:
    """Ensure directory exists, creating it if necessary."""
    path.mkdir(parents=True, exist_ok=True)
    return path

def read_leads_csv(file_path: Path | str, required_columns: Optional[List[str]] = None) -> pd.DataFrame:
    """Read leads data from a CSV file with robust error handling.
    
    Args:
        file_path: Path to the CSV file (Path object or string)
        required_columns: Optional list of column names that must be present in the CSV
        
    Returns:
        DataFrame containing lead data
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If required columns are missing
        pd.errors.EmptyDataError: If the file is empty or has no data rows
    """
    # Convert to Path object if it's a string
    if isinstance(file_path, str):
        file_path = Path(file_path)
    
    # Check if file exists
    if not file_path.is_file():
        logger.error(f"Lead CSV file not found: {file_path}")
        raise FileNotFoundError(f"Lead CSV file not found: {file_path}")
    
    # Read CSV file
    try:
        df = pd.read_csv(file_path)
        
        # Check if data is empty
        if df.empty:
            logger.warning(f"Lead CSV file is empty: {file_path}")
            # Return empty DataFrame with required columns
            if required_columns:
                return pd.DataFrame(columns=required_columns)
            return df
        
        # Check for required columns
        if required_columns:
            missing_cols = set(required_columns) - set(df.columns)
            if missing_cols:
                logger.error(f"Lead CSV file missing required columns: {missing_cols}")
                raise ValueError(f"Lead CSV file missing required columns: {missing_cols}")
        
        # Optimize memory usage for string columns
        for col in df.columns:
            if df[col].dtype == 'object':
                try:
                    df[col] = df[col].astype("string[pyarrow]")
                except (ImportError, TypeError):
                    # Fall back if pyarrow not available or column has mixed types
                    pass
        
        logger.info(f"Successfully loaded {len(df)} leads from {file_path}")
        return df
    
    except pd.errors.EmptyDataError:
        logger.warning(f"Lead CSV file is empty or has no data rows: {file_path}")
        # Return empty DataFrame with required columns
        if required_columns:
            return pd.DataFrame(columns=required_columns)
        return pd.DataFrame()
    
    except pd.errors.ParserError as e:
        logger.error(f"Error parsing lead CSV file {file_path}: {e}")
        raise ValueError(f"Error parsing lead CSV file: {e}") from e
    
    except Exception as e:
        logger.error(f"Unexpected error reading lead CSV file {file_path}: {e}")
        raise IOError(f"Unexpected error reading lead CSV file: {e}") from e 