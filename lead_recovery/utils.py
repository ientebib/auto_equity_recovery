"""utils.py
Utility helper functions shared across modules of the lead recovery project.
"""
from __future__ import annotations

import logging
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
    """Read SQL content from a file."""
    if not file_path.is_file():
        logger.error("SQL file not found: %s", file_path)
        raise FileNotFoundError(f"SQL file not found: {file_path}")

    sql = file_path.read_text(encoding="utf-8").strip()
    if not sql:
        logger.error("SQL file at %s is empty", file_path)
        raise FileNotFoundError(f"SQL file at {file_path} is empty.")

    logger.debug("Loaded SQL file '%s' (%d chars)", file_path, len(sql))
    return sql 