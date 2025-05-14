# Redshift Marker System

## Overview

The Redshift marker system prevents redundant Redshift queries by creating date-specific marker files. This is useful for:

1. Avoiding unnecessary load on the Redshift database
2. Speeding up recipe execution when cached data can be used
3. Coordinating multiple runs of the same recipe on the same day

## How It Works

When a recipe successfully queries Redshift, it creates a marker file with the format:
```
redshift_queried_<recipe_name>_<YYYYMMDD>.marker
```

For example:
```
redshift_queried_simulation_to_handoff_20250512.marker
```

On subsequent runs of the same recipe:
1. The system checks if today's marker exists
2. If it does, and cached lead data is available, it skips the Redshift query
3. If the marker exists but no cached data is found, it still performs the query
4. If you want to force a query regardless of the marker, use the `--ignore-redshift-marker` flag

## Recipes Without Redshift

Some recipes don't require Redshift data. The system handles these recipes automatically:

1. If a recipe doesn't have a `redshift.sql` file, the system automatically skips the Redshift step
2. No marker file is created for recipes without Redshift queries
3. You can also manually skip Redshift with the `--skip-redshift` flag

This allows you to have both types of recipes in your system:
- Recipes that use Redshift and benefit from the marker system
- Recipes that don't use Redshift and automatically bypass that step

## Command-Line Options

The following CLI options control the marker system:

```bash
# Normal run - will use cached Redshift data if marker exists
python -m lead_recovery.cli.main run --recipe your_recipe_name

# Force fresh Redshift query - ignores existing marker
python -m lead_recovery.cli.main run --recipe your_recipe_name --ignore-redshift-marker

# Skip Redshift entirely - doesn't check or create markers
python -m lead_recovery.cli.main run --recipe your_recipe_name --skip-redshift
```

## Utility Script

A utility script `test_marker_system.py` is provided for:
- Listing all existing markers
- Creating markers manually
- Deleting markers
- Checking if a marker exists for a specific recipe

Usage:
```bash
# List all markers
./test_marker_system.py --action list

# Check if a marker exists for a recipe
./test_marker_system.py --recipe your_recipe_name --action check

# Create a marker for a recipe
./test_marker_system.py --recipe your_recipe_name --action create

# Delete a marker for a recipe
./test_marker_system.py --recipe your_recipe_name --action delete
```

## Implementation Details

The marker system is implemented in:
1. `lead_recovery/cli/run.py` - Core logic to check/create markers
2. `lead_recovery/scripts/automate_pipeline.py` - Additional logic for cron jobs

Each marker file contains a timestamp of when the Redshift query was performed.

## Troubleshooting

If you're having issues with the marker system:

1. Check if markers exist with `./test_marker_system.py --action list`
2. Delete unwanted markers with `./test_marker_system.py --recipe <name> --action delete`
3. Use `--ignore-redshift-marker` to force a fresh query if needed
4. Check the log output for marker-related messages

## Future Enhancements

Potential future improvements:

1. Add a TTL (time-to-live) option for markers
2. Support marker expiration based on time of day
3. Add a global override flag to ignore all markers
4. Store markers in a centralized location for multi-user environments 