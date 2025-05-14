"""
Marker Utilities Module

Functions for managing Redshift marker files.
"""
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger("dashboard.marker_utils")

def check_redshift_marker(recipe: str) -> tuple:
    """Check if Redshift has been queried today for this recipe.
    
    Args:
        recipe: Name of the recipe to check
        
    Returns:
        Tuple of (exists, marker_path)
    """
    today = datetime.now().strftime('%Y%m%d')
    marker_path = Path(f"redshift_queried_{recipe}_{today}.marker")
    return marker_path.exists(), marker_path

# Alias for backward compatibility
def has_redshift_marker(recipe: str) -> bool:
    """Check if Redshift has been queried today for this recipe.
    
    Args:
        recipe: Name of the recipe to check
        
    Returns:
        True if marker exists, False otherwise
    """
    exists, _ = check_redshift_marker(recipe)
    return exists

def has_bigquery_marker(recipe: str) -> bool:
    """Check if BigQuery has been queried today for this recipe.
    
    Args:
        recipe: Name of the recipe to check
        
    Returns:
        True if marker exists, False otherwise
    """
    today = datetime.now().strftime('%Y%m%d')
    marker_path = Path(f"bigquery_queried_{recipe}_{today}.marker")
    return marker_path.exists()

def create_redshift_marker(recipe: str) -> Path:
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

def create_bigquery_marker(recipe: str) -> Path:
    """Create a marker file indicating BigQuery was queried today.
    
    Args:
        recipe: Name of the recipe
        
    Returns:
        Path to the created marker file
    """
    today = datetime.now().strftime('%Y%m%d')
    marker_path = Path(f"bigquery_queried_{recipe}_{today}.marker")
    
    # Create marker with timestamp inside
    with open(marker_path, "w") as f:
        f.write(f"BigQuery queried for {recipe} at {datetime.now().isoformat()}")
    
    logger.info(f"Created BigQuery marker: {marker_path}")
    return marker_path

def delete_redshift_marker(recipe: str) -> bool:
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
    """List all Redshift marker files in the current directory.
    
    Returns:
        List of marker file paths sorted by modification time (newest first)
    """
    markers = list(Path().glob("redshift_queried_*.marker"))
    
    if not markers:
        logger.info("No Redshift markers found.")
        return []
    
    # Sort by modification time, newest first
    markers.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return markers 