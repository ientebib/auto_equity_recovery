"""fs.py
File system utility functions for the lead recovery pipeline.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

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