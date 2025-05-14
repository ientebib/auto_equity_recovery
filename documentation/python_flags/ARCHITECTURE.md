# Python Flags System Architecture

This document explains the architecture of the Python flags system in the lead_recovery project, how flags flow through the system, and best practices for maintenance.

## System Overview

The Python flags system provides a flexible way to control various aspects of the lead recovery pipeline's behavior through command-line options. It allows users to:

- Enable or disable specific analysis features
- Skip computation-heavy steps when not needed
- Customize behavior for different recipes

## Key Components

The system consists of these key components:

1. **Flag Definition**: Flags are defined in `python_flags_manager.py`
2. **CLI Interface**: Command-line options in `run.py` and `summarize.py`
3. **Processing Logic**: Implementation of flag behavior in various modules
4. **Data Flow**: How flag values propagate through the system

### Component Relationships

```
┌─────────────────┐     ┌───────────────┐     ┌───────────────────────┐
│  Command Line   │     │  CLI Modules  │     │ python_flags_manager  │
│    Arguments    │────▶│  (run.py,     │────▶│                       │
│ (--skip-xyz)    │     │ summarize.py) │     │ get_python_flag_columns│
└─────────────────┘     └───────────────┘     └───────────────────────┘
                               │                          │
                               ▼                          ▼
                        ┌─────────────┐           ┌─────────────────┐
                        │ analysis.py │◀─────────▶│ Python Flag     │
                        │             │           │ Implementation  │
                        └─────────────┘           └─────────────────┘
```

## Flag Flow Through the System

### 1. Command-Line to Python

When a user runs a command like:

```bash
python -m lead_recovery.cli.main run --recipe my_recipe --skip-detailed-temporal
```

Typer parses the arguments and sets `skip_detailed_temporal=True` in the `run_pipeline` function.

### 2. CLI to Analysis Module

The CLI module (`run.py`) creates an `override_options` dictionary and passes these values to `summarize.py`, which then passes them to `run_summarization_step` in `analysis.py`.

```python
# In run.py
override_options = {
    "skip_detailed_temporal": skip_detailed_temporal,
    # Other flags...
}

# This eventually gets to summarize.py
skip_detailed_temporal_from_meta = override_options.get("skip_detailed_temporal", False)

# Which calls analysis.py
run_summarization_step(
    # ...
    skip_detailed_temporal_calc=skip_detailed_temporal_from_meta,
    # ...
)
```

### 3. Analysis to Flag Manager

The `run_summarization_step` function in `analysis.py` logs received flag values, then calls `get_python_flag_columns` from `python_flags_manager.py` to determine which columns should be included in the output:

```python
# In analysis.py
python_flag_columns = get_python_flag_columns(
    skip_detailed_temporal=skip_detailed_temporal_calc,
    # Other flags...
)
```

### 4. Implementation Logic

The actual functionality controlled by each flag is implemented in various places:

- Some functionality in `analysis.py` itself
- Some in dedicated modules like `python_flags.py`
- Some in recipe-specific code

## Directory Structure

```
lead_recovery/
├── python_flags_manager.py  # Central flag management
├── analysis.py              # Main analysis with flag usage
├── cli/
│   ├── run.py               # Primary CLI entrypoint
│   └── summarize.py         # Summarization CLI
├── python_flags.py          # Implementation of flag functionality
└── [other modules]
```

## How to Navigate the System

### Finding Flag Definitions

To find how a flag is defined:

```bash
grep -r "def get_python_flag_columns" lead_recovery/
```

This will show you the function signature in `python_flags_manager.py` with all available flags.

### Finding Flag Usage

To find where a specific flag is used:

```bash
grep -r "skip_your_flag_name" lead_recovery/
```

This will show all places where the flag is referenced.

### Understanding Flag Dependencies

Some flags have dependencies or hierarchies. For example, in `run.py`:

```python
override_options = {
    "skip_temporal_flags": skip_temporal_flags,
    "skip_detailed_temporal": skip_detailed_temporal or skip_temporal_flags,
    # ...
}
```

Here, `skip_detailed_temporal` is also set to `True` if `skip_temporal_flags` is `True`, creating a hierarchy.

## Best Practices for Maintaining the System

### Flag Organization

1. **Logical grouping**: Keep related flags together (temporal, handoff, templates)
2. **Consistent naming**: Use `skip_` prefix for flags that disable functionality
3. **Default values**: Use `False` as the default for `skip_` flags (don't skip by default)

### Code Quality

1. **Documentation**: Always document what each flag controls
2. **Single responsibility**: Each flag should control a specific aspect of functionality
3. **Flag dependencies**: Clearly document dependencies between flags
4. **Consistent pattern**: Follow the established pattern when adding new flags

### Testing

1. **Test both states**: Ensure code works correctly when flags are both True and False
2. **Integration tests**: Create tests that verify flags affect the expected output
3. **CLI tests**: Verify command-line options correctly set the flags

## Common Architecture Questions

### How do I know which flags affect my recipe?

Check the recipe's `meta.yml` file for any recipe-specific flag settings:

```yaml
behavior_flags:
  skip_detailed_temporal_processing: true
```

Also look for recipe-specific checks in the code:

```python
if recipe_name == "your_recipe" and not skip_your_flag:
    # Recipe-specific behavior
```

### How are flags propagated to the OpenAI summarization step?

Flags like `skip_temporal_flags` affect which data is passed to the LLM prompt. The `python_flag_columns` list determined by `get_python_flag_columns` controls which columns are included in the analysis output.

### How are default values determined?

Default values are set in three places:
1. Function parameter defaults in `python_flags_manager.py`
2. CLI option defaults in `run.py` and `summarize.py`
3. Recipe-specific defaults in `meta.yml` files

The precedence is: CLI options > meta.yml > function defaults.

## Architecture Evolution

The flag system was designed to evolve over time:

1. **Adding flags**: New flags can be added while maintaining backward compatibility
2. **Deprecating flags**: Flags can be marked as deprecated before removal
3. **Flag groups**: Related flags can be controlled by a master flag (e.g., `skip_temporal_flags`)

## Design Principles

The flag system follows these design principles:

1. **Configurability**: Make behavior configurable without code changes
2. **Performance optimization**: Allow skipping expensive computations
3. **Feature toggles**: Enable/disable features at runtime
4. **Backward compatibility**: Support existing automation
5. **Recipe specialization**: Allow recipes to customize behavior 