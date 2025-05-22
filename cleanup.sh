#!/bin/bash
# Cleanup script for lead_recovery_project

echo "Starting cleanup..."

# 1. Remove old marker files (keep today's)
today=$(date +%Y%m%d)
find . -name "redshift_queried_*.marker" | grep -v "$today" | xargs rm -v

# 2. Remove empty and debug log files
rm -v debug_output.log debug_recipe.log skip_test.log 2>/dev/null

# 3. Clean __pycache__ directories
find . -type d -name "__pycache__" -exec rm -rf {} +

# 4. Clean test output directory
read -p "Remove test_output_run directory? (y/n): " remove_test
if [ "$remove_test" == "y" ]; then
  rm -rf test_output_run
  echo "test_output_run directory removed."
fi

# 5. Optional: Clean old output runs
read -p "Remove old output runs (keeping the latest for each recipe)? (y/n): " remove_old_outputs
if [ "$remove_old_outputs" == "y" ]; then
  # For each recipe directory in output_run
  for recipe_dir in output_run/*/; do
    if [ -d "$recipe_dir" ]; then
      # Skip if this is just a file
      recipe_name=$(basename "$recipe_dir")
      echo "Cleaning old runs for recipe: $recipe_name"
      
      # Get latest output directory (excluding 'latest' symlinks)
      latest_dir=$(find "$recipe_dir" -maxdepth 1 -type d -name "20*" | sort | tail -n 1)
      
      if [ -n "$latest_dir" ]; then
        # Remove all other timestamp directories
        find "$recipe_dir" -maxdepth 1 -type d -name "20*" | grep -v "$latest_dir" | xargs rm -rf
        echo "Kept only latest output for $recipe_name: $(basename "$latest_dir")"
      fi
    fi
  done
fi

# 6. Cleanup old log files in root (older than 14 days)
read -p "Remove log files older than 14 days? (y/n): " remove_old_logs
if [ "$remove_old_logs" == "y" ]; then
  find . -maxdepth 1 -name "*.log" -type f -mtime +14 -delete -print
fi

echo "Cleanup completed!"
