# Python Flags System

## Overview

The Lead Recovery project uses a system of Python flags to control various aspects of conversation analysis. These flags are primarily used to:

1. Enable/disable specific analysis features
2. Control which operations are performed during conversation processing
3. Skip certain computation-heavy calculations when not needed
4. Enable recipe-specific processing behaviors

## Architecture

The Python flags system is implemented across several files:

- `lead_recovery/python_flags_manager.py`: The central manager for Python flags, defining function parameters and available flags
- `lead_recovery/analysis.py`: Uses the flags to control processing behavior
- `lead_recovery/cli/run.py`: CLI interface that exposes flags as command-line options
- `lead_recovery/cli/summarize.py`: Another CLI interface for the summarization step

## Flag Types

There are several types of flags in the system:

1. **Temporal flags**: Control time-based calculations (`skip_temporal_flags`, `skip_detailed_temporal`, etc.)
2. **Handoff flags**: Control handoff detection (`skip_handoff_detection`, `skip_handoff_invitation`, etc.)
3. **Template flags**: Control template detection (`skip_recovery_template_detection`, etc.)
4. **Metadata flags**: Control extraction of message metadata (`skip_metadata_extraction`)

## How to Add a New Flag

Adding a new Python flag requires changes in multiple files:

### 1. Add the flag to `python_flags_manager.py`

```python
def get_python_flag_columns(
    # ... existing parameters
    skip_existing_flag: bool = False,
    skip_your_new_flag: bool = False,  # Add your new flag here
    # ... other parameters
) -> List[str]:
    """Get the list of Python-calculated flag columns.
    
    Args:
        # ... existing args
        skip_your_new_flag: Whether to skip your new flag calculation
        
    Returns:
        List of column names for all enabled Python flags
    """
    # ... existing code
    
    if not skip_your_new_flag:
        py_flag_columns.append("your_new_flag_column_name")
    
    return py_flag_columns
```

Also update the `get_python_flags_from_meta` function to include your new flag:

```python
def get_python_flags_from_meta(meta_config: Optional[Dict[str, Any]]) -> Dict[str, bool]:
    # ... existing code
    
    # Default values for all skip flags (don't skip by default)
    skip_flags = {
        # ... existing flags
        "skip_your_new_flag": False,
    }
    
    # ... rest of function
```

### 2. Update CLI interfaces in `run.py`

Add the flag to the CLI options:

```python
@app.callback(invoke_without_command=True)
def run_pipeline(
    # ... existing parameters
    skip_your_new_flag: bool = typer.Option(False, help="Skip your new flag functionality"),
    # ... other parameters
):
    # ... existing code
    
    # Add to override_options dictionary
    override_options = {
        # ... existing options
        "skip_your_new_flag": skip_your_new_flag,
    }
```

### 3. Update CLI interface in `summarize.py`

```python
@app.callback(invoke_without_command=True)
def summarize(
    # ... existing parameters
):
    # ... existing code
    
    skip_your_new_flag_from_meta = override_options.get("skip_your_new_flag", False)
    
    # ... existing code
    
    loop.run_until_complete(
        run_summarization_step(
            # ... existing parameters
            skip_your_new_flag=skip_your_new_flag_from_meta,
            # ... other parameters
        )
    )
```

### 4. Update the `run_summarization_step` function in `analysis.py`

```python
async def run_summarization_step(
    # ... existing parameters
    skip_your_new_flag: bool = False,
    # ... other parameters
):
    # ... existing code
    
    # Log the new flag
    logger.info(f"Using skip_your_new_flag = {skip_your_new_flag}")
    
    # ... existing code
    
    # Use the flag in get_python_flag_columns call
    python_flag_columns = get_python_flag_columns(
        # ... existing parameters
        skip_your_new_flag=skip_your_new_flag,
        # ... other parameters
    )
```

### 5. Add implementation of your flag's functionality

Implement the actual functionality your flag controls in the appropriate module.

## How to Modify an Existing Flag

To modify an existing flag:

1. Update the parameter name and documentation in `python_flags_manager.py`
2. Update the help text in CLI interfaces (`run.py`, `summarize.py`)
3. Modify the implementation where the flag is used

## How to Delete a Flag

Deleting a flag needs to be done carefully to avoid breaking the codebase. Follow these steps:

### 1. Remove the flag from `python_flags_manager.py`

Remove the parameter from `get_python_flag_columns` and `get_python_flags_from_meta`.

### 2. Remove the flag from CLI interfaces

Remove the flag from the parameter lists in:
- `lead_recovery/cli/run.py`
- `lead_recovery/cli/summarize.py`

### 3. Remove the flag from `analysis.py`

Remove the parameter from the `run_summarization_step` function and any usage of the flag.

### 4. Search for all usages and remove them

Use `grep` or another search tool to find all usages of the flag throughout the codebase:

```bash
grep -r "your_flag_name" .
```

Remove all instances of the flag that you find.

### 5. Test thoroughly

After removing the flag, test the application thoroughly to ensure no functionality is broken.

## Best Practices

1. **Flag naming consistency**: Use the `skip_` prefix for flags that disable functionality
2. **Default values**: Set default values to `False` for `skip_` flags (don't skip by default)
3. **Documentation**: Always update help text and function docstrings when adding or modifying flags
4. **Testing**: Test all affected functionality when changing the flags system
5. **Logging**: Add appropriate logging when flag values affect behavior

## Common Issues

### Debugging Flag Issues

If flag behavior seems incorrect, check:

1. The flag's value in `run_pipeline` logs
2. The flag's value in `run_summarization_step` logs
3. The usage of the flag in actual implementation functions

### Adding Recipe-Specific Flags

For flags that only apply to certain recipes:
1. Add the flag normally to the system
2. Check the `recipe_name` in your implementation to conditionally use the flag

```python
if recipe_name == "your_specific_recipe" and not skip_your_flag:
    # Recipe-specific behavior
``` 