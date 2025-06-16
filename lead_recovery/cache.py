import hashlib
import json
import re
from pathlib import Path
from typing import Any, Optional

__all__ = ["SummaryCache", "compute_conversation_digest", "normalize_phone"]


def compute_conversation_digest(conversation_text: str) -> str:
    """Compute a stable MD5 digest for a conversation string.

    Parameters
    ----------
    conversation_text : str
        The raw conversation text.

    Returns
    -------
    str
        The hexadecimal MD5 digest of the normalized conversation text.
    """
    if conversation_text is None:
        conversation_text = ""
    # Normalize whitespace for consistent hashing
    normalized = " ".join(conversation_text.strip().split())
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


def normalize_phone(phone_str: str) -> str:
    """Normalize a phone number by extracting the last 10 digits.
    
    Parameters
    ----------
    phone_str : str
        Raw phone number string
        
    Returns
    -------
    str
        Normalized phone number (last 10 digits)
    """
    if not phone_str:
        return ""
    # Extract only digits
    digits = re.sub(r'\D', '', str(phone_str))
    # Return last 10 digits if available, otherwise return as-is
    return digits[-10:] if len(digits) >= 10 else digits


class SummaryCache:
    """A very lightweight file-based cache for conversation analysis results.

    The original Lead Recovery implementation depends on this module; however
    it was missing from the codebase. This minimal replacement provides the
    functionality required by the framework (read/write by digest).
    """

    def __init__(self, cache_dir: str | Path = ".cache") -> None:
        if cache_dir is None:
            cache_dir = ".cache"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------
    def _digest_path(self, digest: str) -> Path:
        """Return the path on disk for a given digest."""
        return self.cache_dir / f"{digest}.json"

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def get(self, digest: str) -> Optional[Any]:
        """Retrieve cached data for a digest. Returns None if not cached."""
        path = self._digest_path(digest)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            # Corrupted cache file – ignore and treat as miss
            return None

    def set(self, digest: str, data: Any) -> None:
        """Store data for a digest (overwrites if exists)."""
        path = self._digest_path(digest)
        try:
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            # Cache write failures should never crash the pipeline – emit warning
            print(f"⚠️  Warning: failed to write cache for {digest}: {exc}")

    # Allow instance to be used like a dict
    def __getitem__(self, digest: str) -> Optional[Any]:
        return self.get(digest)

    def __setitem__(self, digest: str, data: Any) -> None:
        self.set(digest, data)

    def __contains__(self, digest: str) -> bool:
        return self._digest_path(digest).exists() 