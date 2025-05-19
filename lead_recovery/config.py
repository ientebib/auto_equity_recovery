"""
Centralized application configuration using pydantic.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

# Pydantic v2 moved BaseSettings to pydantic_settings; fall back if older v1
try:
    from pydantic_settings import BaseSettings
except ModuleNotFoundError:  # pragma: no cover – v1 fallback
    from pydantic import BaseSettings  # type: ignore

from pydantic import Field, validator

# ---------------------------------------------------------------------------- #
# Logging configuration (importing this module sets global logging defaults)
# ---------------------------------------------------------------------------- #
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
# Only configure the root logger if the application running this module
# has not configured logging yet.  This prevents 3rd‑party code from
# changing global logging behaviour unexpectedly when it merely
# imports ``lead_recovery``.
if not logging.getLogger().handlers:
    logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
logger = logging.getLogger(__name__)

# The currently active settings instance, can be overridden for testing
_CURRENT_SETTINGS = None

class Settings(BaseSettings):
    """Validated settings loaded from environment variables or .env file."""

    # ------------------------------------------------------------------ #
    # Database credentials (Redshift)
    # ------------------------------------------------------------------ #
    REDSHIFT_HOST: str | None = None
    REDSHIFT_DB: str | None = Field(default=None, alias="REDSHIFT_DATABASE")
    REDSHIFT_USER: str | None = None
    REDSHIFT_PASS: str | None = Field(default=None, alias="REDSHIFT_PASSWORD")
    REDSHIFT_PORT: int = 5439

    # ------------------------------------------------------------------ #
    # OpenAI API and Google Credentials
    # ------------------------------------------------------------------ #
    OPENAI_API_KEY: str | None = None
    GOOGLE_CREDENTIALS_PATH: str | None = None

    # ------------------------------------------------------------------ #
    # Project paths
    # ------------------------------------------------------------------ #
    # We compute absolute paths so that CLI commands work regardless of the
    # shell's current working directory.
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

    # ------------------------------------------------------------------ #
    # BigQuery configuration
    # ------------------------------------------------------------------ #
    # Optional: override the GCP project used by google‑cloud‑bigquery.
    # Leave unset to rely on Application‑Default credentials logic.
    BQ_PROJECT: str | None = None

    # ------------------------------------------------------------------ #
    # Performance and processing parameters
    # ------------------------------------------------------------------ #
    BQ_BATCH_SIZE: int = 500
    BQ_MAX_CONCURRENT_QUERIES: int = 10
    OUTPUT_DIR: Path = Path("output_run")
    SQLITE_JOURNAL_MODE: str = Field(default="WAL", description="SQLite journal mode for cache (WAL or DELETE)")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"

    # ------------------------------------------------------------------ #
    @validator("OUTPUT_DIR", pre=True, always=True)
    def _validate_output_dir(cls, v: str | Path) -> Path:  # noqa: D401
        """Ensure output directory exists."""
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return path


def get_settings(override_values: Optional[Dict[str, Any]] = None) -> Settings:
    """Get the current settings, with optional overrides for testing.
    
    Args:
        override_values: Optional dictionary of settings values to override
        
    Returns:
        Settings instance with overrides applied if any
    
    This function allows tests to override settings without modifying
    global configuration.
    """
    global _CURRENT_SETTINGS
    
    # If no overrides and we already have settings, return cached instance
    if override_values is None and _CURRENT_SETTINGS is not None:
        return _CURRENT_SETTINGS
    
    # Create a new Settings instance
    if override_values:
        # Apply overrides for testing
        settings_instance = Settings(**override_values)
        logger.debug("Created settings with overrides: %s", 
                    {k: "****" if k == "OPENAI_API_KEY" else v for k, v in override_values.items()})
    else:
        # Normal settings from environment
        settings_instance = Settings()
    
    # Store as current if no overrides
    if override_values is None:
        _CURRENT_SETTINGS = settings_instance
    
    # Hide sensitive info in logs
    safe_dict = settings_instance.dict()
    if "OPENAI_API_KEY" in safe_dict and safe_dict["OPENAI_API_KEY"]:
        safe_dict["OPENAI_API_KEY"] = "****"
    logger.debug("Loaded settings: %s", safe_dict)
    
    return settings_instance


# Instantiate a global settings object for convenient import
# This is kept for backwards compatibility
settings = get_settings() 