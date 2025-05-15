"""cache.py
Cache management for the lead recovery pipeline.
"""
from __future__ import annotations

import logging
import hashlib
import sqlite3
import json
import os
import time
import re
from typing import Dict, Any, Optional, List, Tuple, Set, Iterator
from datetime import datetime, timedelta
from pathlib import Path

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
    
    def __init__(self, cache_dir: Optional[Path] = None, max_age_days: int = 30):
        """Initialize the summary cache.
        
        Args:
            cache_dir: Directory to store the cache database. If None, uses data/cache
                in the project directory.
            max_age_days: Maximum age of cache entries in days before they expire
        """
        if cache_dir is None:
            # Default to data/cache in project directory
            cache_dir = Path(settings.PROJECT_ROOT) / "data" / "cache"
            
        # Ensure directory exists
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = cache_dir / "summary_cache.sqlite"
        self.max_age_days = max_age_days
        self._init_db()
        
    def _init_db(self):
        """Initialize the database schema and indexes if they don't exist."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Create table if it doesn't exist with all columns initially planned
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS summary_cache (
                    conversation_digest TEXT PRIMARY KEY,
                    yaml_summary TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    created_ts TEXT NOT NULL,
                    cleaned_phone TEXT,    -- Added in later versions
                    recipe_name TEXT,      -- Added in later versions
                    last_accessed_ts TEXT  -- Added in later versions
                )
            ''')
            conn.commit() # Commit initial table creation

            # Columns that might be missing in older schemas
            columns_to_ensure = {
                "cleaned_phone": "TEXT",
                "recipe_name": "TEXT",
                "last_accessed_ts": "TEXT"
            }

            for col_name, col_type in columns_to_ensure.items():
                try:
                    cursor.execute(f"ALTER TABLE summary_cache ADD COLUMN {col_name} {col_type}")
                    conn.commit()
                    logger.info(f"Added missing column '{col_name}' to summary_cache.")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" in str(e).lower():
                        pass # Column already exists, which is fine
                    else:
                        # Log other errors but don't necessarily stop _init_db
                        logger.warning(f"Could not add column '{col_name}' (may be benign or an issue): {e}")
            
            # Create indexes for faster lookups
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_model_version ON summary_cache(model_version)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_cleaned_phone ON summary_cache(cleaned_phone)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_recipe_name ON summary_cache(recipe_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_ts ON summary_cache(created_ts)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_last_accessed_ts ON summary_cache(last_accessed_ts)')
            
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"SQLite error during _init_db: {e}", exc_info=True)
            # Depending on the error, you might want to re-raise or handle differently
        finally:
            conn.close()
            
    def _get_connection(self) -> sqlite3.Connection:
        """Get a connection to the SQLite database with optimized settings."""
        # Set busy_timeout to 30 seconds to wait for locks to be released
        # Use WAL journal mode for better concurrency and performance
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")  # 30 seconds in milliseconds
        conn.execute("PRAGMA synchronous=NORMAL")  # Faster, still safe
        conn.execute("PRAGMA cache_size=-10000")   # Use 10MB of memory for caching
        conn.execute("PRAGMA temp_store=MEMORY")   # Store temp tables in memory
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
            
            # Get the entry and update last_accessed_ts in one transaction
            cursor.execute(
                """
                SELECT yaml_summary FROM summary_cache 
                WHERE conversation_digest = ? AND model_version = ?
                """,
                (conversation_digest, model_version)
            )
            result = cursor.fetchone()
            
            if result:
                # Update last_accessed_ts
                now = datetime.now().isoformat()
                cursor.execute(
                    """
                    UPDATE summary_cache SET last_accessed_ts = ?
                    WHERE conversation_digest = ? AND model_version = ?
                    """,
                    (now, conversation_digest, model_version)
                )
                conn.commit()
                
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
            
    def set(self, conversation_digest: str, summary: Dict[str, Any], model_version: str, 
            phone_number: Optional[str] = None, recipe_name: Optional[str] = None):
        """Store a summary in the cache.
        
        Args:
            conversation_digest: The digest/hash of the conversation
            summary: The summary dictionary to cache
            model_version: The model version used for summarization
            phone_number: Optional phone number for indexing. If None, 'cleaned_phone' from summary is used.
            recipe_name: Optional recipe name for grouping cache entries
        """
        # Use 'cleaned_phone' from summary if phone_number parameter is not directly provided
        # This ensures the correct key is used for cache storage and retrieval operations
        # when phone_number is not explicitly passed to this method.
        effective_phone_key = phone_number if phone_number is not None else summary.get('cleaned_phone')
            
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
                
                # Insert or replace with additional metadata
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO summary_cache 
                    (conversation_digest, yaml_summary, model_version, created_ts, 
                     cleaned_phone, recipe_name, last_accessed_ts)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (conversation_digest, yaml_str, model_version, now, 
                     effective_phone_key, recipe_name, now)
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
    
    def bulk_set(self, summaries: List[Dict[str, Any]], model_version: str, recipe_name: Optional[str] = None):
        """Store multiple summaries in the cache.
        
        Args:
            summaries: List of summaries to cache
            model_version: The model version used for summarization
            recipe_name: Optional recipe name for grouping cache entries
        """
        if not summaries:
            return
            
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Start transaction
            cursor.execute("BEGIN TRANSACTION")
            
            # Current timestamp
            now = datetime.now().isoformat()
            
            # Prepare YAML serializer once
            import yaml
            
            # Batch insert in chunks to avoid memory issues
            chunk_size = 100
            values = []
            
            for summary in summaries:
                if "conversation_digest" not in summary:
                    logger.warning("Skipping cache entry without conversation_digest")
                    continue
                    
                digest = summary["conversation_digest"]
                phone = summary.get("cleaned_phone", None)
                yaml_str = yaml.dump(summary, default_flow_style=False)
                
                values.append((digest, yaml_str, model_version, now, phone, recipe_name, now))
                
                # If we've reached chunk_size, execute the batch
                if len(values) >= chunk_size:
                    cursor.executemany(
                        """
                        INSERT OR REPLACE INTO summary_cache 
                        (conversation_digest, yaml_summary, model_version, created_ts, 
                         cleaned_phone, recipe_name, last_accessed_ts)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        values
                    )
                    values = []
            
            # Insert any remaining values
            if values:
                cursor.executemany(
                    """
                    INSERT OR REPLACE INTO summary_cache 
                    (conversation_digest, yaml_summary, model_version, created_ts, 
                     cleaned_phone, recipe_name, last_accessed_ts)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    values
                )
            
            # Commit transaction
            conn.commit()
            logger.info(f"Bulk cached {len(summaries)} summaries in one transaction")
            
        except Exception as e:
            logger.error(f"Error in bulk_set: {e}", exc_info=True)
            if 'conn' in locals():
                conn.rollback()
        finally:
            if 'conn' in locals():
                conn.close()
            
    def clear(self, model_version: Optional[str] = None, recipe_name: Optional[str] = None):
        """Clear the cache, optionally filtered by model or recipe.
        
        Args:
            model_version: Optional model version to clear
            recipe_name: Optional recipe name to clear
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            if model_version and recipe_name:
                cursor.execute(
                    "DELETE FROM summary_cache WHERE model_version = ? AND recipe_name = ?",
                    (model_version, recipe_name)
                )
            elif model_version:
                cursor.execute(
                    "DELETE FROM summary_cache WHERE model_version = ?",
                    (model_version,)
                )
            elif recipe_name:
                cursor.execute(
                    "DELETE FROM summary_cache WHERE recipe_name = ?",
                    (recipe_name,)
                )
            else:
                cursor.execute("DELETE FROM summary_cache")
                
            rows_deleted = cursor.rowcount
            conn.commit()
            logger.info(f"Cleared {rows_deleted} entries from cache")
        finally:
            conn.close()
            
    def expire_old_entries(self, days: Optional[int] = None):
        """Delete cache entries older than specified days.
        
        Args:
            days: Number of days after which entries expire (default: self.max_age_days)
        """
        days = days or self.max_age_days
        conn = self._get_connection()
        
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM summary_cache WHERE created_ts < datetime('now', ?)",
                (f"-{days} days",)
            )
            rows_deleted = cursor.rowcount
            conn.commit()
            logger.info(f"Expired {rows_deleted} cache entries older than {days} days")
        finally:
            conn.close()
            
    def prune_by_access_time(self, keep_percentage: float = 0.8):
        """Prune least recently accessed entries to reduce cache size.
        
        Args:
            keep_percentage: Percentage of most recently accessed entries to keep (0.0-1.0)
        """
        if not (0.0 < keep_percentage < 1.0):
            logger.error(f"Invalid keep_percentage: {keep_percentage}. Must be between 0.0 and 1.0")
            return
            
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Get total count
            cursor.execute("SELECT COUNT(*) FROM summary_cache")
            total_count = cursor.fetchone()[0]
            
            # Calculate how many to delete
            delete_count = int(total_count * (1.0 - keep_percentage))
            
            if delete_count <= 0:
                logger.info("No entries to prune")
                return
                
            # Delete oldest accessed entries
            cursor.execute("""
                DELETE FROM summary_cache 
                WHERE conversation_digest IN (
                    SELECT conversation_digest 
                    FROM summary_cache 
                    ORDER BY last_accessed_ts ASC 
                    LIMIT ?
                )
            """, (delete_count,))
            
            rows_deleted = cursor.rowcount
            conn.commit()
            
            logger.info(f"Pruned {rows_deleted} least recently accessed entries ({keep_percentage:.1%} kept)")
        finally:
            conn.close()
    
    def optimize_database(self):
        """Run VACUUM and ANALYZE to optimize database performance."""
        conn = self._get_connection()
        try:
            logger.info("Running SQLite VACUUM to optimize database")
            conn.execute("VACUUM")
            logger.info("Running SQLite ANALYZE to optimize query planning")
            conn.execute("ANALYZE")
            logger.info("Database optimization complete")
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
            
            # Count entries by recipe name
            cursor.execute("SELECT recipe_name, COUNT(*) FROM summary_cache GROUP BY recipe_name")
            recipes = {row[0] or 'unknown': row[1] for row in cursor.fetchall()}
            
            # Get age distribution
            cursor.execute("""
                SELECT 
                    COUNT(CASE WHEN created_ts > datetime('now', '-1 day') THEN 1 END) as day1,
                    COUNT(CASE WHEN created_ts > datetime('now', '-7 day') THEN 1 END) as day7,
                    COUNT(CASE WHEN created_ts > datetime('now', '-30 day') THEN 1 END) as day30,
                    COUNT(CASE WHEN created_ts <= datetime('now', '-30 day') THEN 1 END) as older
                FROM summary_cache
            """)
            age_data = cursor.fetchone()
            age_distribution = {
                'last_day': age_data[0],
                'last_week': age_data[1],
                'last_month': age_data[2],
                'older_than_month': age_data[3]
            }
            
            # Get the size of the database file
            size_bytes = 0
            if self.db_path.exists():
                size_bytes = self.db_path.stat().st_size
                
            return {
                "total_entries": total,
                "models": models,
                "recipes": recipes,
                "age_distribution": age_distribution,
                "size_bytes": size_bytes,
                "size_mb": round(size_bytes / (1024 * 1024), 2),
                "db_path": str(self.db_path)
            }
        finally:
            conn.close()
            
    def get_for_phone(self, phone_number: str) -> List[Dict[str, Any]]:
        """Retrieve all cached summaries for a specific phone number.
        
        Args:
            phone_number: The phone number to retrieve summaries for.
            
        Returns:
            A list of cached summaries (as dictionaries) for the given phone number.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Query using cleaned_phone as this is the consistent column name now
            cursor.execute("SELECT yaml_summary FROM summary_cache WHERE cleaned_phone = ?", (phone_number,))
            rows = cursor.fetchall()
            
            summaries = []
            for row in rows:
                try:
                    import yaml
                    summary = yaml.safe_load(row[0])
                    summaries.append(summary)
                except Exception as e:
                    logger.warning(f"Failed to parse cached summary for phone {phone_number}: {e}")
                    continue
                    
            return summaries
        finally:
            conn.close()
    
    def iter_entries(self, batch_size: int = 100, model_version: Optional[str] = None,
                   recipe_name: Optional[str] = None) -> Iterator[List[Dict[str, Any]]]:
        """Iterate through cache entries in batches.
        
        Args:
            batch_size: Number of entries to fetch in each batch
            model_version: Optional filter by model version
            recipe_name: Optional filter by recipe name
            
        Yields:
            Batches of parsed summaries
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Build query based on filters
            query = "SELECT yaml_summary FROM summary_cache"
            params = []
            
            if model_version or recipe_name:
                query += " WHERE"
                conditions = []
                
                if model_version:
                    conditions.append("model_version = ?")
                    params.append(model_version)
                    
                if recipe_name:
                    conditions.append("recipe_name = ?")
                    params.append(recipe_name)
                    
                query += " " + " AND ".join(conditions)
                
            # Add order and limit
            query += " ORDER BY created_ts DESC LIMIT ? OFFSET ?"
            
            offset = 0
            while True:
                cursor.execute(query, params + [batch_size, offset])
                rows = cursor.fetchall()
                
                if not rows:
                    break
                    
                batch = []
                for row in rows:
                    try:
                        import yaml
                        summary = yaml.safe_load(row[0])
                        batch.append(summary)
                    except Exception as e:
                        logger.warning(f"Failed to parse cached summary: {e}")
                        continue
                        
                yield batch
                offset += batch_size
                
                if len(rows) < batch_size:
                    break
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
                SELECT conversation_digest, yaml_summary, model_version, cleaned_phone
                FROM summary_cache
                WHERE created_ts > datetime('now', ?)
                """,
                (f"-{self.max_age_days} days",)
            )
            
            results = {}
            for row in cursor.fetchall():
                digest, yaml_str, model, phone = row
                
                # Parse YAML string back to dict
                try:
                    import yaml
                    summary = yaml.safe_load(yaml_str)
                    
                    # Get phone from row or summary if available
                    if phone:
                        phone_key = phone
                    elif "cleaned_phone" in summary:
                        phone_key = summary["cleaned_phone"]
                    else:
                        continue  # Skip entries without a phone number
                        
                    # Add the digest to the summary for tracking
                    summary["conversation_digest"] = digest
                    results[phone_key] = summary
                    
                    # Update last_accessed_ts for this entry
                    now = datetime.now().isoformat()
                    cursor.execute(
                        "UPDATE summary_cache SET last_accessed_ts = ? WHERE conversation_digest = ?",
                        (now, digest)
                    )
                    
                except Exception as e:
                    logger.warning(f"Failed to parse cached summary for digest {digest}: {e}")
                    continue
            
            # Commit the updates to last_accessed_ts
            conn.commit()        
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