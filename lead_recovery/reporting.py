"""reporting.py
Functions to output analysis results to CSV and HTML.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def to_csv(df: pd.DataFrame, path: Path) -> Path:
    """Write DataFrame to *path* (CSV) and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    logger.info("CSV written to %s", path)
    return path


def to_html(df: pd.DataFrame, path: Path) -> Path:
    """Write DataFrame to *path* (HTML table)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_html(path, index=False, justify="center")
    logger.info("HTML written to %s", path)
    return path 