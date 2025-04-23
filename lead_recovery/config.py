"""
Centralised application configuration using pydantic.
"""
from __future__ import annotations

import logging
from pathlib import Path

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
    # OpenAI API
    # ------------------------------------------------------------------ #
    OPENAI_API_KEY: str

    # ------------------------------------------------------------------ #
    # SQL file paths (can be overridden for testing) -------------------- #
    # We compute absolute paths so that CLI commands work regardless of the
    # shell's current working directory.
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

    # Default recipe (profiling_incomplete)
    RS_SQL_PATH: Path = PROJECT_ROOT / "recipes" / "profiling_incomplete" / "redshift.sql"
    BQ_SQL_PATH: Path = PROJECT_ROOT / "recipes" / "profiling_incomplete" / "bigquery.sql"

    # Optional: override the GCP project used by google‑cloud‑bigquery.
    # Leave unset to rely on Application‑Default credentials logic.
    BQ_PROJECT: str | None = None

    # ------------------------------------------------------------------ #
    # Pipeline parameters
    # ------------------------------------------------------------------ #
    TIME_WINDOW_DAYS: int = 90
    BQ_BATCH_SIZE: int = 500
    BQ_MAX_CONCURRENT_QUERIES: int = 10
    OUTPUT_DIR: Path = Path("output_run")

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


# Instantiate a global settings object for convenient import
settings = Settings()

# Hide sensitive info in logs
safe_dict = settings.dict()
if "OPENAI_API_KEY" in safe_dict:
    safe_dict["OPENAI_API_KEY"] = "****"
logger.debug("Loaded settings: %s", safe_dict) 