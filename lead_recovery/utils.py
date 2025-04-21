"""utils.py
Utility helper functions shared across modules of the lead recovery project.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def clean_phone(raw: str | None) -> str | None:
    """Return the last 10 numeric digits of *raw* phone string, or None if invalid.

    Strips every non-digit character, checks if at least 10 digits remain,
    and returns the last 10. Returns None if the input is None or if fewer
    than 10 digits are found after cleaning.
    """
    if raw is None:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 10:
        logger.debug("Invalid phone number (too short): %s -> %s", raw, digits)
        return None
    return digits[-10:]


def clean_email(raw: str | None) -> str:
    """Normalise email address: lowercase + remove plus‑aliases.

    Example: ``Foo+Bar@Example.com`` → ``foo@example.com``.
    """
    if not raw:
        return ""
    local, _, domain = raw.partition("@")
    local = local.split("+", 1)[0]
    return f"{local.lower()}@{domain.lower()}" if domain else raw.lower()


def load_sql_file(path: Path) -> str:  # noqa: D401
    """Read *path* and return SQL text; raise if file missing/empty.

    This is used by the DB query modules to externalise SQL. Mimics runtime
    behaviour of the earlier pipeline but is now fully testable.
    """
    if not path.is_file():
        logger.error("SQL file not found: %s", path)
        raise FileNotFoundError(f"SQL file not found: {path}")

    sql = path.read_text(encoding="utf-8").strip()
    if not sql:
        logger.error("SQL file at %s is empty", path)
        raise FileNotFoundError(f"SQL file at {path} is empty.")

    logger.debug("Loaded SQL file '%s' (%d chars)", path, len(sql))
    return sql 