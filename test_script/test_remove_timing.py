#!/usr/bin/env python
"""
Test script to verify timing_reasoning removal in reporting.py
"""
import os
import sys
from pathlib import Path

import pandas as pd

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the to_csv function and other utilities
from lead_recovery.reporting import to_csv


def create_test_dataframe():
    """Create a test dataframe with timing_reasoning field"""
    data = {
        'lead_id': ['lead1', 'lead2', 'lead3'],
        'summary': ['Test 1', 'Test 2', 'Test 3'],
        'timing_reasoning': ['Should be removed 1', 'Should be removed 2', 'Should be removed 3']
    }
    return pd.DataFrame(data)

def main():
    """Test the removal of timing_reasoning field"""
    print("Creating test DataFrame with timing_reasoning field...")
    df = create_test_dataframe()
    
    print(f"Original DataFrame columns: {df.columns.tolist()}")
    print(f"Contains timing_reasoning: {'timing_reasoning' in df.columns}")
    
    # Save to CSV using the to_csv function
    output_path = Path('test_output_timing.csv')
    print(f"Saving to {output_path} using lead_recovery.reporting.to_csv...")
    to_csv(df, output_path)
    
    # Read back and verify
    result_df = pd.read_csv(output_path)
    print(f"Result DataFrame columns: {result_df.columns.tolist()}")
    print(f"Still contains timing_reasoning: {'timing_reasoning' in result_df.columns}")
    
    # Clean up
    if output_path.exists():
        output_path.unlink()
        print(f"Removed test file {output_path}")

if __name__ == "__main__":
    main() 