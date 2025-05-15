#!/bin/bash
# Dry run version of cleanup script
echo "This is a dry run - nothing will be deleted"
echo "Old marker files that would be removed:"
find . -name "redshift_queried_*.marker" | grep -v "$(date +%Y%m%d)"
