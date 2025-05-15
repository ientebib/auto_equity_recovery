#!/bin/bash

# Script to run a recipe with limit option for faster testing
# Usage: ./run_recipe.sh [recipe_name] [limit_number]

RECIPE=${1:-simulation_to_handoff}
LIMIT=${2:-10}  # Default to 10 conversations for quick testing

echo "Running recipe: $RECIPE with processor execution enabled but data fetching and LLM summarization skipped, limited to $LIMIT conversations"

# Run with data fetching and LLM summarization skipped, but processors enabled
python -m lead_recovery.cli.main run --recipe $RECIPE \
  --skip-redshift \
  --skip-bigquery \
  --skip-summarize \
  --limit $LIMIT

echo "Recipe run completed with exit code: $?" 