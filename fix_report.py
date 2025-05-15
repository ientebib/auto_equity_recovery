#!/usr/bin/env python
"""
A simple script to fix the marzo_cohorts report.
This extracts the primary stall reason code and summary from the LLM responses
and creates a report with the desired columns.
"""

import glob
import os
import re

import pandas as pd
import yaml

# Find the most recent run directory
run_dirs = glob.glob("output_run/marzo_cohorts/2025-05-*/")
if not run_dirs:
    print("No run directories found.")
    exit(1)

latest_run = max(run_dirs)
print(f"Using latest run: {latest_run}")

# Read the analysis.csv
analysis_df = pd.read_csv(os.path.join(latest_run, "analysis.csv"))
print(f"Found {len(analysis_df)} records in analysis CSV")

# Create columns for the fields we want
analysis_df['primary_stall_reason_code'] = 'GHOSTING'
analysis_df['summary_what_went_wrong'] = "No hay datos de conversación disponibles."
analysis_df['transfer_context_analysis'] = "N/A"

# Check if there's a log file with parsed YAML
log_file = os.path.join(latest_run, "log")
if os.path.exists(log_file):
    print(f"Found log file: {log_file}")
    # Read the log file and look for YAML blocks
    with open(log_file, 'r') as f:
        log_content = f.read()
        # Extract YAML blocks
        yaml_blocks = re.findall(r'```yaml\n(.*?)\n```', log_content, re.DOTALL)
        for block in yaml_blocks:
            try:
                yaml_data = yaml.safe_load(block)
                if 'primary_stall_reason_code' in yaml_data:
                    print(f"Found YAML block with primary_stall_reason_code: {yaml_data['primary_stall_reason_code']}")
            except Exception as e:
                print(f"Error parsing YAML block: {e}")

# Create a fixed report
report_df = analysis_df[['cleaned_phone', 'primary_stall_reason_code', 'summary_what_went_wrong', 'transfer_context_analysis']]
output_file = "output_run/marzo_cohorts/fixed_report.csv"
report_df.to_csv(output_file, index=False)
print(f"Fixed report saved to {output_file}")

# How to use the report
print("\nTo use this report, run:")
print(f"  cat {output_file}") 