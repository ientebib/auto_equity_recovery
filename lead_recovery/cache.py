"""cache.py
Cache management for the lead recovery pipeline.
"""
from __future__ import annotations

import logging
import hashlib
from pathlib import Path
import pandas as pd
import re
import sqlite3
import json
import os
from typing import Dict, Any, Optional
from datetime import datetime
import time

from .reporting import to_csv
from .config import settings

logger = logging.getLogger(__name__)

# Simplified phone number normalization
_PHONE_PATTERN = re.compile(r"(?:\+?521|\+?52|0)?(\d{10})$")

def normalize_phone(phone: str) -> str:
    """Normalize Mexican phone number to 10 digits (strip +52/521/0)."""
    if not phone:
        return ""
    match = _PHONE_PATTERN.search(phone.strip())
    if match:
        return match.group(1)
    return phone.strip()

def compute_conversation_digest(conversation_text: str) -> str:
    """Compute a digest/hash for a conversation text.
    
    Args:
        conversation_text: The conversation text to hash
        
    Returns:
        A hex digest string that uniquely identifies the conversation
    """
    return hashlib.md5(conversation_text.encode('utf-8')).hexdigest()

class SummaryCache:
    """Cache for conversation summaries to avoid repeated API calls."""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize the summary cache.
        
        Args:
            cache_dir: Directory to store the cache database. If None, uses data/cache
                in the project directory.
        """
        if cache_dir is None:
            # Default to data/cache in project directory
            cache_dir = Path(settings.PROJECT_ROOT) / "data" / "cache"
            
        # Ensure directory exists
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = cache_dir / "summary_cache.sqlite"
        self._init_db()
        
    def _init_db(self):
        """Initialize the database if it doesn't exist."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Create table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS summary_cache (
                    conversation_digest TEXT PRIMARY KEY,
                    yaml_summary TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    created_ts TEXT NOT NULL
                )
            ''')
            conn.commit()
        finally:
            conn.close()
            
    def _get_connection(self) -> sqlite3.Connection:
        """Get a connection to the SQLite database."""
        # Set busy_timeout to 30 seconds to wait for locks to be released
        # Use WAL journal mode for better concurrency
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")  # 30 seconds in milliseconds
        return conn
            
    def get(self, conversation_digest: str, model_version: str) -> Optional[Dict[str, Any]]:
        """Get a cached summary for a conversation digest.
        
        Args:
            conversation_digest: The digest/hash of the conversation
            model_version: The model version used for summarization
            
        Returns:
            The cached summary as a dictionary, or None if not found
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT yaml_summary FROM summary_cache WHERE conversation_digest = ? AND model_version = ?",
                (conversation_digest, model_version)
            )
            result = cursor.fetchone()
            
            if result:
                # Parse YAML string back to dict
                try:
                    import yaml
                    return yaml.safe_load(result[0])
                except Exception as e:
                    logger.warning(f"Failed to parse cached summary: {e}", exc_info=True)
                    return None
            return None
        except sqlite3.OperationalError as e:
            # Handle database locked errors
            logger.warning(f"SQLite operational error in get(): {e} - will return None")
            return None
        finally:
            conn.close()
            
    def set(self, conversation_digest: str, summary: Dict[str, Any], model_version: str):
        """Store a summary in the cache.
        
        Args:
            conversation_digest: The digest/hash of the conversation
            summary: The summary dictionary to cache
            model_version: The model version used for summarization
        """
        retry_count = 0
        max_retries = 3
        retry_delay = 1  # seconds
        
        while retry_count < max_retries:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                
                # Convert dict to YAML string
                import yaml
                yaml_str = yaml.dump(summary, default_flow_style=False)
                
                # Current timestamp
                now = datetime.now().isoformat()
                
                # Insert or replace
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO summary_cache 
                    (conversation_digest, yaml_summary, model_version, created_ts)
                    VALUES (?, ?, ?, ?)
                    """,
                    (conversation_digest, yaml_str, model_version, now)
                )
                conn.commit()
                return  # Success, exit the retry loop
            except sqlite3.OperationalError as e:
                # Handle database locked errors with exponential backoff
                retry_count += 1
                if retry_count < max_retries:
                    # Exponential backoff with jitter
                    import random
                    sleep_time = retry_delay * (2 ** (retry_count - 1)) * (0.5 + random.random())
                    logger.warning(
                        f"SQLite operational error in set() (attempt {retry_count}/{max_retries}): {e} - "
                        f"retrying in {sleep_time:.2f}s"
                    )
                    time.sleep(sleep_time)
                else:
                    logger.error(f"Failed to cache summary after {max_retries} attempts: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Unexpected error caching summary: {e}", exc_info=True)
                break  # Don't retry for non-operational errors
            finally:
                try:
                    conn.close()
                except UnboundLocalError:
                    # conn might not be defined if connection failed
                    pass
            
    def clear(self):
        """Clear the entire cache."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM summary_cache")
            conn.commit()
        finally:
            conn.close()
            
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            A dictionary with cache statistics
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Count total entries
            cursor.execute("SELECT COUNT(*) FROM summary_cache")
            total = cursor.fetchone()[0]
            
            # Count entries by model version
            cursor.execute("SELECT model_version, COUNT(*) FROM summary_cache GROUP BY model_version")
            models = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Get the size of the database file
            size_bytes = 0
            if self.db_path.exists():
                size_bytes = self.db_path.stat().st_size
                
            return {
                "total_entries": total,
                "models": models,
                "size_bytes": size_bytes,
                "size_mb": round(size_bytes / (1024 * 1024), 2),
                "db_path": str(self.db_path)
            }
        finally:
            conn.close()
            
    async def load_all_cached_results(self) -> Dict[str, Dict[str, Any]]:
        """Load all cached results for a specific model.
        
        Returns:
            Dictionary mapping phone numbers to their cached summaries
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Get all cached entries (latest model version for each digest)
            cursor.execute(
                """
                SELECT conversation_digest, yaml_summary, model_version 
                FROM summary_cache
                """
            )
            
            results = {}
            for row in cursor.fetchall():
                digest, yaml_str, model = row
                
                # Parse YAML string back to dict
                try:
                    import yaml
                    summary = yaml.safe_load(yaml_str)
                    
                    # Get phone from summary (if available) or use digest as key
                    phone = summary.get("cleaned_phone", None)
                    if not phone:
                        continue  # Skip entries without a phone number
                        
                    # Add the digest to the summary for tracking
                    summary["conversation_digest"] = digest
                    results[phone] = summary
                except Exception as e:
                    logger.warning(f"Failed to parse cached summary for digest {digest}: {e}")
                    continue
                    
            return results
        except sqlite3.OperationalError as e:
            logger.warning(f"SQLite operational error in load_all_cached_results(): {e}")
            return {}
        finally:
            conn.close()

def run_cache_self_test(output_dir: Path) -> bool:
    """Run a self-test to verify cache write/read consistency.
    
    Returns:
        True if test passed, False otherwise
    """
    # Create a test cache record and verify we can read it back correctly
    test_cache = {
        'test_phone': {
            'cleaned_phone': 'test_phone',
            'conversation_digest': 'test_digest',
            'cache_status': 'TEST'
        }
    }
    test_df = pd.DataFrame([test_cache['test_phone']])
    test_path = output_dir / "cache_test.csv" 
    to_csv(test_df, test_path)
    
    try:
        # Read back and verify
        test_read = pd.read_csv(test_path)
        if test_read.empty:
            logger.error("TEST: Failed to read back cache test file - file is empty")
            return False
        elif 'conversation_digest' not in test_read.columns:
            logger.error("TEST: Failed to read back cache test - missing conversation_digest column")
            return False
        elif test_read['conversation_digest'].iloc[0] != 'test_digest':
            logger.error(f"TEST: Digest mismatch: expected 'test_digest', got '{test_read['conversation_digest'].iloc[0]}'")
            return False
        else:
            logger.info("TEST: Cache write/read consistency test passed")
            return True
    except Exception as e:
        logger.error(f"TEST: Failed to read back cache test: {e}")
        return False
    finally:
        # Delete the test file
        try:
            test_path.unlink()
        except Exception:
            pass 

def run_summary_cache_class_self_test() -> bool:
    """Run a self-test of the SummaryCache class functionality.
    
    Returns:
        True if the test passes, False otherwise
    """
    # Create a temporary cache
    import tempfile
    temp_dir = Path(tempfile.mkdtemp())
    try:
        cache = SummaryCache(temp_dir)
        
        # Test basic functionality
        test_digest = "test_digest"
        test_summary = {"key1": "value1", "key2": 123}
        test_model = "test-model"
        
        # Should not exist initially
        assert cache.get(test_digest, test_model) is None
        
        # Add to cache
        cache.set(test_digest, test_summary, test_model)
        
        # Should exist now
        result = cache.get(test_digest, test_model)
        assert result is not None
        assert result["key1"] == "value1"
        assert result["key2"] == 123
        
        # Stats should show one entry
        stats = cache.stats()
        assert stats["total_entries"] == 1
        
        # Clear should remove entry
        cache.clear()
        assert cache.get(test_digest, test_model) is None
        
        logger.info("Cache self-test passed")
        return True
    except Exception as e:
        logger.error(f"Cache self-test failed: {e}", exc_info=True)
        return False
    finally:
        # Clean up temp directory
        import shutil
        shutil.rmtree(temp_dir) 