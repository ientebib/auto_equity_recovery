#!/usr/bin/env python
"""
Script to clean timing_reasoning from cache.csv
"""
from pathlib import Path

import pandas as pd


def main():
    cache_path = Path('output_run/simulation_to_handoff/cache.csv')
    
    if not cache_path.exists():
        print(f"Cache file not found at {cache_path}")
        return
    
    print(f"Reading cache file from {cache_path}")
    df = pd.read_csv(cache_path)
    
    print(f"Original columns: {df.columns.tolist()}")
    
    if 'timing_reasoning' in df.columns:
        print("Removing timing_reasoning column from cache file")
        df = df.drop(columns=['timing_reasoning'])
        
        # Backup original
        backup_path = cache_path.with_suffix('.csv.bak')
        print(f"Backing up original cache to {backup_path}")
        cache_path.rename(backup_path)
        
        # Save clean version
        print(f"Saving cleaned cache to {cache_path}")
        df.to_csv(cache_path, index=False)
        
        print(f"Cleaned columns: {df.columns.tolist()}")
    else:
        print("No timing_reasoning column found in cache file")

if __name__ == "__main__":
    main() 