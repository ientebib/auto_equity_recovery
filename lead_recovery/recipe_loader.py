from __future__ import annotations

"""recipe_loader.py
Utility helpers to discover and load *recipe* folders.

A *recipe* is a directory under the project‑root `recipes/` folder that
contains the following files:
    redshift.sql   – Lead selector query for Redshift
    bigquery.sql   – Conversation selector query for BigQuery
    prompt.txt     – OpenAI prompt template used for summarisation
    meta.yml       – Human‑friendly metadata for dashboards / pipeline

Example layout::

    recipes/
        profile_incomplete/
            redshift.sql
            bigquery.sql
            prompt.txt
            meta.yml

This module exposes two main public helpers
------------------------------------------------
• list_recipes() → list[str]
    Returns the available recipe directory names (sorted)

• load_recipe(name) → Recipe
    Loads a specific recipe and returns a simple dataclass‑like object
    with handy attributes (redshift_sql_path, meta, …).

The implementation purposefully stays lightweight and has **zero** external
runtime dependencies beyond the Python std‑lib.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Any, Optional
import yaml

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
RECIPE_ROOT = Path("recipes")


@dataclass
class Recipe:
    """Container object holding resolved file paths and meta information."""

    # Core identifiers / paths
    name: str
    dir_path: Path
    redshift_sql_path: Path
    bigquery_sql_path: Path | None  # optional
    prompt_path: Path
    meta_path: Path
    
    # Parsed meta.yml content (loaded on demand by `load_recipe`)
    meta: Dict[str, Any]

    # Convenience helpers --------------------------------------------------- #
    @property
    def dashboard_title(self) -> str | None:  # noqa: D401
        return self.meta.get("dashboard_title")

    @property
    def output_columns(self) -> List[str] | None:  # noqa: D401
        return self.meta.get("output_columns")

    # Added: New fields
    expected_yaml_keys: Optional[List[str]] = None  # Added: List of expected keys for validation


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def list_recipes() -> List[str]:
    """Return all available recipe folder names (sorted alphabetical)."""
    if not RECIPE_ROOT.exists():
        return []

    return sorted(
        p.name for p in RECIPE_ROOT.iterdir() if p.is_dir() and (p / "meta.yml").exists()
    )


def load_recipe(name: str) -> Recipe:
    """Load a recipe by name and return a `Recipe` data‑object.

    Raises FileNotFoundError if the recipe folder (or mandatory files) are missing.
    """
    dir_path = RECIPE_ROOT / name
    if not dir_path.exists():
        raise FileNotFoundError(f"Recipe '{name}' does not exist under '{RECIPE_ROOT}'.")

    meta_path = dir_path / "meta.yml"
    if not meta_path.exists():
        raise FileNotFoundError(f"meta.yml not found for recipe '{name}'.")

    # Load YAML meta FIRST so we can read custom filenames
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta_dict: Dict[str, Any] = yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:  # pragma: no cover – edge‑case
        raise ValueError(f"Invalid YAML in {meta_path}: {exc}") from exc

    # Validate basic required fields
    required_fields = [
        "name",
        "output_columns",
        "dashboard_title",
        "summary_format",
        "redshift_sql",
        "prompt_file",
    ]
    for field in required_fields:
        if field not in meta_dict:
            raise ValueError(f"Missing required field '{field}' in {meta_path}")

    # Resolve filenames from meta (fallback to defaults) ------------------ #
    redshift_fn = meta_dict.get("redshift_sql", "redshift.sql")
    bigquery_fn = meta_dict.get("bigquery_sql", "bigquery.sql")
    prompt_fn = meta_dict.get("prompt_file", "prompt.txt")

    redshift_sql_path = dir_path / redshift_fn
    bigquery_sql_path = dir_path / bigquery_fn
    prompt_path = dir_path / prompt_fn

    # Validate presence ---------------------------------------------------- #
    missing: List[str] = []
    if not redshift_sql_path.exists():
        missing.append(redshift_fn)
    if not prompt_path.exists():
        missing.append(prompt_fn)
    if missing:
        raise FileNotFoundError(
            f"Recipe '{name}' is missing required file(s): {', '.join(missing)}"
        )

    # Added: Load expected YAML keys if provided
    expected_yaml_keys = meta_dict.get("expected_yaml_keys", None)
    if expected_yaml_keys is not None and not isinstance(expected_yaml_keys, list):
        raise ValueError(f"'expected_yaml_keys' in {meta_path} must be a list, if provided.")

    return Recipe(
        name=name,
        dir_path=dir_path,
        redshift_sql_path=redshift_sql_path,
        bigquery_sql_path=bigquery_sql_path if bigquery_sql_path.exists() else None,
        prompt_path=prompt_path,
        meta_path=meta_path,
        meta=meta_dict,
        expected_yaml_keys=expected_yaml_keys,
    ) 