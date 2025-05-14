__version__ = "0.1.0"

"""lead_recovery package

This lightweight package wraps the existing top‑level modules so they can be
imported as `lead_recovery.<module>` without physically moving every file at
once.  It lets us install the project as `pip install -e .` and run the CLI via

    python -m lead_recovery.cli  # or simply: lead-recovery  (via console script)

When we later move modules into this folder we can drop these indirections.
"""
from importlib import import_module as _import
from types import ModuleType as _ModuleType
from typing import List as _List

_modules: _List[str] = [
    "config",
    "db_clients",
    "utils",
    "summarizer",
    "reporting",
    "recipe_loader",
    "cli",
]

globals().update({name: _import(f"lead_recovery.{name}") for name in _modules})

# Directly import functions from modules that were previously re-exported through pipeline.py
from .fs import update_link, ensure_dir
from .gsheets import upload_to_google_sheets
from .cache import normalize_phone
from .analysis import run_summarization_step

# Import handoff detection functions
from .python_flags import (
    handoff_invitation,
    handoff_started,
    handoff_finalized,
    analyze_handoff_process,
    detect_human_transfer,
    detect_recovery_template,
    detect_topup_template,
    count_consecutive_recovery_templates,
    extract_message_metadata
)

__all__: _List[str] = _modules + [
    "run_summarization_step", 
    "upload_to_google_sheets", 
    "normalize_phone", 
    "update_link",
    # Add handoff detection functions
    "handoff_invitation",
    "handoff_started",
    "handoff_finalized",
    "analyze_handoff_process"
] 