# Python Flags Documentation

## Overview

This directory contains comprehensive documentation about the Python flags system used in the lead_recovery project. These guides explain how to manage, add, modify, and delete Python flags that control various aspects of the analysis pipeline.

## Table of Contents

1. [**README.md**](./README.md) - General overview of the Python flags system
2. [**ARCHITECTURE.md**](./ARCHITECTURE.md) - Detailed explanation of the flags architecture and design principles
3. [**ADDING_NEW_FLAG.md**](./ADDING_NEW_FLAG.md) - Step-by-step guide for adding a new Python flag
4. [**MODIFYING_EXISTING_FLAG.md**](./MODIFYING_EXISTING_FLAG.md) - Guide for safely modifying an existing flag
5. [**FLAG_REMOVAL_CASE_STUDY.md**](./FLAG_REMOVAL_CASE_STUDY.md) - Real-world case study of removing the `skip_topup_template_detection` flag

## Quick Reference

### Where to Find Flags

- **Flag definitions**: `lead_recovery/python_flags_manager.py`
- **CLI interface**: `lead_recovery/cli/run.py` and `lead_recovery/cli/summarize.py`
- **Implementation usage**: `lead_recovery/analysis.py`

### Adding a New Flag Checklist

1. Add parameter to `get_python_flag_columns()` in `python_flags_manager.py`
2. Add entry to `skip_flags` dictionary in `get_python_flags_from_meta()`
3. Add command-line option to `run_pipeline()` in `run.py`
4. Add extraction from options in `summarize.py`
5. Add parameter to `run_summarization_step()` in `analysis.py`
6. Implement the actual functionality
7. Update documentation

### Deleting a Flag Checklist

1. Remove parameter from `get_python_flag_columns()` in `python_flags_manager.py`
2. Remove entry from `skip_flags` dictionary in `get_python_flags_from_meta()`
3. Remove command-line option from `run_pipeline()` in `run.py`
4. Remove extraction from options in `summarize.py`
5. Remove parameter from `run_summarization_step()` in `analysis.py`
6. Remove any implementation code that uses the flag
7. Update documentation

## Code Examples

### Flag Usage Example

```python
# In CLI command
python -m lead_recovery.cli.main run --recipe my_recipe --skip-detailed-temporal

# In code
if not skip_detailed_temporal:
    # Perform detailed temporal analysis
    # ...
else:
    # Skip this step or provide simplified alternative
    # ...
```

## When to Use Python Flags

Use Python flags when:

1. You need to make a feature optionally skippable
2. You want to provide recipe-specific behavior
3. You need to optimize performance by skipping expensive calculations
4. You need to provide different execution paths based on user needs

## Getting Help

If you're unsure about how to work with the Python flags system, refer to these guides or check the implementation in the codebase. 