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

__all__: _List[str] = _modules  # re‑export 