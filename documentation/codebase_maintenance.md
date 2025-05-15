# Lead Recovery Codebase Maintenance Guide

This guide provides information on how to maintain the codebase and which files/directories are essential vs. non-essential.

## Core Directories

These directories are essential to the functioning of the lead recovery system:

- `lead_recovery/` - Main application code
  - `cli/` - Command-line interfaces
  - `processors/` - Data processing modules
- `recipes/` - Recipe configuration files
- `documentation/` - Project documentation
- `tests/` - Test cases (important for future development)

## Temporary/Generated Files (Safe to Delete)

These files are generated during runtime and can be safely deleted:

- `__pycache__/` directories - Python bytecode
- `*.pyc` files - Python compiled files
- `redshift_queried_*.marker` files - Old Redshift query markers
- Log files (`.log`) in the root directory - Runtime logs
- `.pytest_cache/` - Pytest cache

## Output Data (Consider Before Deleting)

- `output_run/` - Contains results from recipe runs
  - Consider keeping the most recent run for each recipe
  - Older runs can be deleted if space is needed

## Maintenance Tasks

### Regular Cleanup

Run the provided `cleanup.sh` script to automatically:
- Remove old marker files
- Clean Python cache directories
- Remove empty and debug log files
- Optionally clean old output runs (keeping only the latest for each recipe)
- Delete old log files

```bash
./cleanup.sh
```

### Pruning Output Directories

If disk space becomes an issue, you can safely prune the `output_run` directory:

```bash
# Keep only the most recent output for each recipe
for recipe_dir in output_run/*/; do
  if [ -d "$recipe_dir" ]; then
    recipe_name=$(basename "$recipe_dir")
    echo "Cleaning old runs for recipe: $recipe_name"
    
    # Get latest output directory
    latest_dir=$(find "$recipe_dir" -maxdepth 1 -type d -name "20*" | sort | tail -n 1)
    
    if [ -n "$latest_dir" ]; then
      # Remove all other timestamp directories
      find "$recipe_dir" -maxdepth 1 -type d -name "20*" | grep -v "$latest_dir" | xargs rm -rf
    fi
  fi
done
```

## Obsolete Components

The following components are no longer used or have been replaced:

1. **Deprecated Processor Files (Already Removed)**
   - `lead_recovery/processors/temporal_processor.py` - Replaced by `temporal.py`
   - `lead_recovery/processors/message_metadata_processor.py` - Replaced by `metadata.py`

2. **Legacy Directory**
   - The `legacy/` directory contains old recipe versions that are no longer maintained.
   - This can be safely deleted if those recipes are no longer needed.

3. **Test Output Directory**
   - `test_output_run/` is used only for testing and can be deleted.

## Do Not Delete

Never delete these critical configuration files:

- `.env` - Environment variables configuration
- `pyproject.toml` and `requirements.txt` - Dependency definitions
- `meta.yml` files in recipes - Recipe configurations

## Git Cleanup

To clean the Git repository from large files that are no longer needed:

```bash
# Remove large files from Git history (use with caution)
git filter-branch --force --tree-filter 'rm -f path/to/large/file' HEAD
git gc --aggressive
git prune
```

## Database Cleanup

The SQlite cache database (`data/cache/summary_cache.sqlite`) can grow large over time. You can safely delete this file to reclaim space, but it will cause the system to regenerate summaries for conversations:

```bash
rm data/cache/summary_cache.sqlite
``` 