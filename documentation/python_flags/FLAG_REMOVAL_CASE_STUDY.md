# Case Study: Removing the `skip_topup_template_detection` Flag

This document provides a real-world example of safely removing a Python flag from the codebase.

## Background

The `skip_topup_template_detection` flag was originally added to control template detection for top-up-related messages. Over time, this functionality was no longer needed, and the flag needed to be removed from the system.

## Removal Process

### 1. Identifying All References

First, we used `grep` to find all references to the flag:

```bash
grep -r "skip_topup_template_detection" .
```

This revealed references in the following files:
- `lead_recovery/python_flags_manager.py`
- `lead_recovery/analysis.py`
- `lead_recovery/cli/run.py`
- `lead_recovery/cli/summarize.py`

### 2. Removing from `python_flags_manager.py`

We removed the parameter from the function definition:

```python
# Before:
def get_python_flag_columns(
    # ... other parameters
    skip_topup_template_detection: bool = False,
    # ... other parameters
) -> List[str]:
    # ...

# After:
def get_python_flag_columns(
    # ... other parameters
    # skip_topup_template_detection parameter removed
    # ... other parameters
) -> List[str]:
    # ...
```

We also removed the parameter from the `get_python_flags_from_meta` function's default dictionary:

```python
# Before:
skip_flags = {
    # ... other flags
    "skip_topup_template_detection": False,
    # ... other flags
}

# After:
skip_flags = {
    # ... other flags
    # "skip_topup_template_detection" entry removed
    # ... other flags
}
```

### 3. Removing from CLI Interface

We removed the parameter from `run.py`:

```python
# Before:
@app.callback(invoke_without_command=True)
def run_pipeline(
    # ... other parameters
    skip_topup_template_detection: bool = typer.Option(False, help="Skip top-up template detection"),
    # ... other parameters
):
    # ...
    override_options = {
        # ... other options
        "skip_topup_template_detection": skip_topup_template_detection,
        # ... other options
    }

# After:
@app.callback(invoke_without_command=True)
def run_pipeline(
    # ... other parameters
    # skip_topup_template_detection parameter removed
    # ... other parameters
):
    # ...
    override_options = {
        # ... other options
        # "skip_topup_template_detection" entry removed
        # ... other options
    }
```

Similarly, we removed it from `summarize.py`:

```python
# Before:
skip_topup_template_detection_from_meta = override_options.get("skip_topup_template_detection", False)
# ...
loop.run_until_complete(
    run_summarization_step(
        # ... other parameters
        skip_topup_template_detection=skip_topup_template_detection_from_meta,
        # ... other parameters
    )
)

# After:
# skip_topup_template_detection_from_meta line removed
# ...
loop.run_until_complete(
    run_summarization_step(
        # ... other parameters
        # skip_topup_template_detection parameter removed
        # ... other parameters
    )
)
```

### 4. Removing from `analysis.py`

We removed the parameter from the `run_summarization_step` function:

```python
# Before:
async def run_summarization_step(
    # ... other parameters
    skip_topup_template_detection: bool = False,
    # ... other parameters
):
    # ...
    logger.info(f"Using skip_topup_template_detection = {skip_topup_template_detection}")
    # ...
    python_flag_columns = get_python_flag_columns(
        # ... other parameters
        skip_topup_template_detection=skip_topup_template_detection,
        # ... other parameters
    )

# After:
async def run_summarization_step(
    # ... other parameters
    # skip_topup_template_detection parameter removed
    # ... other parameters
):
    # ...
    # logger.info line for skip_topup_template_detection removed
    # ...
    python_flag_columns = get_python_flag_columns(
        # ... other parameters
        # skip_topup_template_detection parameter removed
        # ... other parameters
    )
```

### 5. Removing Implementation Code

We also removed any associated implementation code that depended on this flag, such as conditional checks like:

```python
# Before:
if not skip_topup_template_detection_local:
    # Top-up template detection code
    # ...

# After:
# Entire conditional block removed
```

## Testing After Removal

After removing the flag and all associated code, we tested the application with the following commands:

```bash
# Test with a recipe that previously used the flag
python -m lead_recovery.cli.main run --recipe simulation_to_handoff --no-cache --skip-redshift
```

## Lessons Learned

1. **Thorough search**: Using grep to find all references is essential.
2. **Complete removal**: Ensure all references are removed, not just function parameters.
3. **Consistent changes**: Make changes consistently across all files.
4. **Testing**: Test affected recipes to ensure functionality remains intact.
5. **User communication**: Update documentation to inform users about the removed flag.

## Future Flag Removals

When removing flags in the future:

1. Announce deprecation in advance when possible
2. Create a clear plan for removal
3. Consider using a staged approach for widely-used flags
4. Test thoroughly after removal
5. Update documentation to remove references to the deleted flag 