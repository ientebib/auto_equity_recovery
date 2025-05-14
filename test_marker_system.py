#!/usr/bin/env python3
"""
Test script to demonstrate how to use the Redshift marker system.
This script shows how to check, create, and manage Redshift markers.
"""
import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
)
logger = logging.getLogger("redshift_marker_test")

def check_redshift_marker(recipe: str):
    """Check if Redshift has been queried today for this recipe.
    
    Args:
        recipe: Name of the recipe to check
        
    Returns:
        Tuple of (exists, marker_path)
    """
    today = datetime.now().strftime('%Y%m%d')
    marker_path = Path(f"redshift_queried_{recipe}_{today}.marker")
    return marker_path.exists(), marker_path

def create_redshift_marker(recipe: str):
    """Create a marker file indicating Redshift was queried today.
    
    Args:
        recipe: Name of the recipe
        
    Returns:
        Path to the created marker file
    """
    today = datetime.now().strftime('%Y%m%d')
    marker_path = Path(f"redshift_queried_{recipe}_{today}.marker")
    
    # Create marker with timestamp inside
    with open(marker_path, "w") as f:
        f.write(f"Redshift queried for {recipe} at {datetime.now().isoformat()}")
    
    logger.info(f"Created Redshift marker: {marker_path}")
    return marker_path

def delete_redshift_marker(recipe: str):
    """Delete a marker file for the given recipe.
    
    Args:
        recipe: Name of the recipe
        
    Returns:
        True if marker was deleted, False if it didn't exist
    """
    today = datetime.now().strftime('%Y%m%d')
    marker_path = Path(f"redshift_queried_{recipe}_{today}.marker")
    
    if marker_path.exists():
        marker_path.unlink()
        logger.info(f"Deleted Redshift marker: {marker_path}")
        return True
    else:
        logger.info(f"No marker found to delete for recipe: {recipe}")
        return False

def list_all_markers():
    """List all Redshift marker files in the current directory."""
    markers = list(Path().glob("redshift_queried_*.marker"))
    
    if not markers:
        logger.info("No Redshift markers found.")
        return []
    
    # Sort by modification time, newest first
    markers.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    
    logger.info(f"Found {len(markers)} Redshift markers:")
    for marker in markers:
        # Try to parse recipe and date from marker name
        parts = marker.name.split("_")
        if len(parts) >= 4:
            recipe = parts[2]
            date = parts[3].split(".")[0]
            logger.info(f"  - {recipe} (date: {date})")
        else:
            logger.info(f"  - {marker.name}")
    
    return markers

def main():
    parser = argparse.ArgumentParser(description="Redshift Marker System Demo")
    parser.add_argument("--recipe", type=str, default="test_recipe", help="Recipe name")
    parser.add_argument("--action", type=str, choices=["check", "create", "delete", "list"], default="list", help="Action to perform")
    
    args = parser.parse_args()
    
    if args.action == "check":
        exists, marker_path = check_redshift_marker(args.recipe)
        if exists:
            logger.info(f"Redshift marker exists for recipe '{args.recipe}': {marker_path}")
        else:
            logger.info(f"No Redshift marker found for recipe '{args.recipe}'")
    elif args.action == "create":
        marker_path = create_redshift_marker(args.recipe)
        logger.info(f"Created Redshift marker for recipe '{args.recipe}': {marker_path}")
    elif args.action == "delete":
        deleted = delete_redshift_marker(args.recipe)
        if deleted:
            logger.info(f"Successfully deleted marker for recipe '{args.recipe}'")
        else:
            logger.info(f"No marker found to delete for recipe '{args.recipe}'")
    elif args.action == "list":
        list_all_markers()
    else:
        logger.error(f"Invalid action: {args.action}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 