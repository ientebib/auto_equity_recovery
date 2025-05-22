#!/usr/bin/env python
"""
Script to clean timing_reasoning from the SQLite cache
"""
from pathlib import Path
import sqlite3
from datetime import datetime
import yaml


def main():
    cache_dir = Path('output_run/simulation_to_handoff')
    db_path = cache_dir / 'summary_cache.sqlite'

    if not db_path.exists():
        print(f"Cache database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT conversation_digest, yaml_summary FROM summary_cache")
    rows = cursor.fetchall()

    cleaned = 0
    for digest, yaml_str in rows:
        data = yaml.safe_load(yaml_str)
        if 'timing_reasoning' in data:
            del data['timing_reasoning']
            new_yaml = yaml.dump(data, default_flow_style=False)
            now = datetime.now().isoformat()
            cursor.execute(
                "UPDATE summary_cache SET yaml_summary = ?, last_accessed_ts = ? WHERE conversation_digest = ?",
                (new_yaml, now, digest)
            )
            cleaned += 1

    conn.commit()
    conn.close()

    print(f"Cleaned {cleaned} cache records")

if __name__ == "__main__":
    main() 