#!/bin/bash

# Script to run a recipe with limit option for faster testing
# Usage: ./run_recipe.sh [recipe_name] [limit_number]

RECIPE=${1:-fede_abril_preperfilamiento}
LIMIT=${2:-10}  # Default to 10 conversations for quick testing

echo "Running recipe: $RECIPE with temporal flags disabled, OpenAI summarization skipped, and $LIMIT conversation limit"

# Run with ALL temporal flags explicitly disabled and skip OpenAI summarization
python -m lead_recovery.cli.main run --recipe $RECIPE \
  --skip-redshift \
  --skip-bigquery \
  --skip-temporal-flags \
  --skip-summarize \
  --limit $LIMIT

echo "Recipe run completed with exit code: $?" 