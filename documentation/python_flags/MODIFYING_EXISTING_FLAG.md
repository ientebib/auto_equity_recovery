# Guide: Modifying an Existing Python Flag

This document provides guidance on how to safely modify an existing Python flag in the lead_recovery project.

## Common Reasons to Modify a Flag

1. **Changing flag behavior**: Updating what functionality the flag controls
2. **Renaming a flag**: Making the name more descriptive or consistent
3. **Changing default value**: Altering the default state of a feature
4. **Adding new functionality**: Extending what an existing flag controls
5. **Deprecating a flag**: Marking a flag for future removal

## Example Scenario

Let's consider modifying the existing flag `skip_detailed_temporal` to expand its functionality.

## Step-by-Step Guide

### 1. Identify All Uses of the Flag

Use `grep` to find all references to the existing flag:

```bash
grep -r "skip_detailed_temporal" .
```

You should find references in:
- `lead_recovery/python_flags_manager.py`
- `lead_recovery/analysis.py`
- `lead_recovery/cli/run.py`
- `lead_recovery/cli/summarize.py`

### 2. Update Flag Documentation

Start by updating the documentation to reflect the new behavior:

```python
# Before
skip_detailed_temporal: bool = False,  # Skip detailed temporal calculations

# After
skip_detailed_temporal: bool = False,  # Skip detailed temporal calculations and extended time analysis
```

### 3. Update the Implementation in `python_flags_manager.py`

```python
def get_python_flag_columns(
    # ... other parameters
    skip_detailed_temporal: bool = False,
    # ... other parameters
) -> List[str]:
    """Get the list of Python-calculated flag columns.
    
    Args:
        # ... other args
        skip_detailed_temporal: Whether to skip detailed temporal calculations and extended time analysis
        # ... other args
    """
    py_flag_columns = []
    
    # ... existing code
    
    # Update the implementation of the flag
    if not skip_detailed_temporal:
        # Original columns
        py_flag_columns.append("hours_since_last_message")
        py_flag_columns.append("hours_since_last_user_message")
        
        # Add new columns for extended functionality
        py_flag_columns.append("days_since_first_message")
        py_flag_columns.append("conversation_duration_days")
    
    return py_flag_columns
```

### 4. Update the CLI Help Text in `run.py`

```python
@app.callback(invoke_without_command=True)
def run_pipeline(
    # ... other parameters
    skip_detailed_temporal: bool = typer.Option(
        False, 
        help="Skip detailed temporal processing and extended time analysis"
    ),
    # ... other parameters
):
    # ... existing code
```

### 5. Update Implementation in `analysis.py`

```python
async def run_summarization_step(
    # ... other parameters
    skip_detailed_temporal_calc: bool = False,
    # ... other parameters
):
    # ... existing code
    
    # Update implementation to match new behavior
    if not skip_detailed_temporal_calc:
        # Original temporal calculations
        temporal_flags = calculate_temporal_flags(conv_df)
        
        # Add new extended time calculations
        if "creation_time" in conv_df.columns:
            conv_df_sorted = conv_df.sort_values("creation_time")
            first_msg_time = conv_df_sorted.iloc[0]["creation_time"]
            last_msg_time = conv_df_sorted.iloc[-1]["creation_time"]
            
            # Calculate additional metrics
            first_msg_dt = pd.to_datetime(first_msg_time)
            last_msg_dt = pd.to_datetime(last_msg_time)
            now = pd.to_datetime(datetime.now())
            
            days_since_first = (now - first_msg_dt).total_seconds() / (60 * 60 * 24)
            conversation_duration = (last_msg_dt - first_msg_dt).total_seconds() / (60 * 60 * 24)
            
            # Add to temporal flags
            temporal_flags["days_since_first_message"] = round(days_since_first, 1)
            temporal_flags["conversation_duration_days"] = round(conversation_duration, 1)
    else:
        # Skip all calculations if flag is True
        temporal_flags = {
            "hours_since_last_message": None,
            "hours_since_last_user_message": None,
            "days_since_first_message": None,
            "conversation_duration_days": None
        }
```

### 6. Update Tests

If you have tests for this flag, update them to check the new behavior:

```python
def test_skip_detailed_temporal_flag():
    # Test with flag enabled (skip functionality)
    results_with_skip = run_test_with_flag(skip_detailed_temporal=True)
    assert "hours_since_last_message" not in results_with_skip
    assert "days_since_first_message" not in results_with_skip
    
    # Test with flag disabled (include functionality)
    results_without_skip = run_test_with_flag(skip_detailed_temporal=False)
    assert "hours_since_last_message" in results_without_skip
    assert "days_since_first_message" in results_without_skip
```

### 7. Update README and Documentation

Update the project's documentation to reflect the modified flag:

```markdown
## CLI Options

* `--skip-detailed-temporal`: Skip detailed temporal processing and extended time analysis 
  (disables hours since last message, days since first message, and conversation duration calculations)
```

## Handling Flag Renaming

If you're renaming a flag, follow these additional steps:

### 1. Add Both Old and New Names Temporarily

```python
def get_python_flag_columns(
    # ... other parameters
    skip_old_name: bool = False,  # DEPRECATED: Use skip_new_name instead
    skip_new_name: bool = False,  # New parameter name
    # ... other parameters
) -> List[str]:
    # Use the old or new flag (whichever is True)
    skip_effective = skip_old_name or skip_new_name
    
    # ... use skip_effective in your code
```

### 2. Add Deprecation Warning

```python
def get_python_flag_columns(
    # ... other parameters
    skip_old_name: bool = False,
    # ... other parameters
) -> List[str]:
    if skip_old_name:
        import warnings
        warnings.warn(
            "The 'skip_old_name' parameter is deprecated. Use 'skip_new_name' instead.",
            DeprecationWarning,
            stacklevel=2
        )
```

### 3. Update CLI with Deprecated Flag

```python
@app.callback(invoke_without_command=True)
def run_pipeline(
    # ... other parameters
    skip_old_name: bool = typer.Option(
        False, 
        help="[DEPRECATED] Use --skip-new-name instead"
    ),
    skip_new_name: bool = typer.Option(
        False, 
        help="New flag name with same functionality as old skip_old_name"
    ),
    # ... other parameters
):
    # ... existing code
```

### 4. Eventual Removal

After a transition period (e.g., in the next major release), remove the old flag name completely.

## Best Practices for Modifying Flags

1. **Backward compatibility**: Try to maintain backward compatibility when changing flag behavior
2. **Deprecation notice**: If significantly changing a flag's meaning, consider deprecating the old flag and adding a new one
3. **Documentation**: Update all documentation to reflect the new behavior
4. **Testing**: Test both the old and new behavior to ensure compatibility
5. **Gradual transition**: For widely used flags, consider a phased approach:
   - Phase 1: Add new flag alongside old flag
   - Phase 2: Deprecate old flag with warnings
   - Phase 3: Remove old flag

## Common Pitfalls

1. **Breaking existing scripts**: Changing default values can break existing automation
2. **Inconsistent updates**: Forgetting to update all places where the flag is used
3. **Missing documentation**: Not updating documentation to reflect new behavior
4. **Silent changes**: Making substantial behavior changes without clearly communicating them
5. **Dependencies**: Not considering how other flags might depend on the one being modified 