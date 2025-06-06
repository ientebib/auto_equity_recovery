from importlib import import_module as _import
from types import ModuleType as _ModuleType
from typing import List as _List

from .analysis import run_summarization_step
from .cache import normalize_phone
from .fs import ensure_dir, update_link
from .gsheets import upload_to_google_sheets

__version__ = "0.1.0"

"""lead_recovery package

This lightweight package wraps the existing top‑level modules so they can be
imported as `lead_recovery.<module>` without physically moving every file at
once.  It lets us install the project as `pip install -e .` and run the CLI via

    python -m lead_recovery.cli  # or simply: lead-recovery  (via console script)

When we later move modules into this folder we can drop these indirections.
"""

_modules: _List[str] = [
    "config",
    "db_clients",
    "utils",
    "recipe_loader",
    "constants",
    "recipe_schema",
    "fs",
    "gsheets",
    "cache",
    "analysis",
    "yaml_validator",
    "reporting",
    "processors",
    "processor_runner",
    "exceptions",
    "cli",
    "summarizer",
    "summarizer_helpers"
]

for _module in _modules:
    globals()[_module] = _import("lead_recovery." + _module)
    if isinstance(globals()[_module], _ModuleType):
        globals()[_module].__package__ = "lead_recovery"

# Directly import functions from modules that were previously re-exported through pipeline.py

__all__: _List[str] = _modules + [
    "run_summarization_step", 
    "upload_to_google_sheets", 
    "normalize_phone", 
    "update_link"
]