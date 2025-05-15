"""
Recipe Manager Module

Utilities for managing and loading recipe information for the dashboard.
"""
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# Setup logger
logger = logging.getLogger("dashboard.recipe_manager")

# Add project root to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Use absolute paths
PROJECT_ROOT = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
RECIPE_ROOT = PROJECT_ROOT / "recipes"
OUTPUT_ROOT = PROJECT_ROOT / "output_run"

@dataclass
class Recipe:
    """Container object holding resolved file paths and meta information."""
    name: str
    dir_path: Path
    redshift_sql_path: Path
    bigquery_sql_path: Path
    prompt_path: Path
    meta_path: Path
    meta: Dict[str, Any]
    needs_redshift: bool = False
    
    @property
    def has_redshift(self) -> bool:
        """Check if the recipe has a Redshift query."""
        return self.redshift_sql_path.exists()
    
    @property
    def has_bigquery(self) -> bool:
        """Check if the recipe has a BigQuery query."""
        return self.bigquery_sql_path.exists()
    
    @property
    def has_prompt(self) -> bool:
        """Check if the recipe has a prompt file."""
        return self.prompt_path.exists()
    
    @property
    def has_custom_analyzer(self) -> bool:
        """Check if the recipe has a custom analyzer."""
        return (self.dir_path / "analyzer.py").exists()
    
    @property
    def expected_yaml_keys(self) -> List[str]:
        """Get the expected YAML keys from the meta.yml file."""
        return self.meta.get("expected_yaml_keys", [])
    
    @property
    def output_columns(self) -> List[str]:
        """Get the output columns from the meta.yml file."""
        return self.meta.get("output_columns", [])
    
    @property
    def google_sheets_config(self) -> Dict[str, str]:
        """Get the Google Sheets configuration from the meta.yml file."""
        sheets_config = self.meta.get("google_sheets", {})
        if isinstance(sheets_config, dict):
            return sheets_config
        return {}

def get_recipes() -> List[str]:
    """Get a list of available recipe names."""
    
    if not RECIPE_ROOT.exists():
        logger.error(f"Recipe root directory does not exist: {RECIPE_ROOT}")
        return []
    
    logger.info(f"Scanning recipe directory: {RECIPE_ROOT}")
    recipes = []
    
    for p in RECIPE_ROOT.iterdir():
        if p.is_dir() and not p.name.startswith('.'):
            logger.info(f"Found recipe directory: {p.name}")
            recipes.append(p.name)
        else:
            logger.debug(f"Skipping non-recipe item: {p.name}")
    
    logger.info(f"Found {len(recipes)} recipes: {recipes}")
    return sorted(recipes)

def get_recipe_details(recipe_name: str) -> Recipe:
    """Get detailed information about a specific recipe."""
    if not isinstance(recipe_name, str):
        # Convert numeric/non-string values to string to prevent PosixPath / int error
        recipe_name = str(recipe_name)
        
    recipe_dir = RECIPE_ROOT / recipe_name
    if not recipe_dir.exists():
        raise FileNotFoundError(f"Recipe directory not found: {recipe_dir}")
    
    # Find the meta.yml file
    meta_path = recipe_dir / "meta.yml"
    meta_data = {}
    
    if meta_path.exists():
        try:
            with open(meta_path, 'r') as f:
                loaded_data = yaml.safe_load(f)
                if isinstance(loaded_data, dict):
                    meta_data = loaded_data
        except Exception as e:
            print(f"Error loading meta.yml: {e}")
    
    # Determine file paths
    redshift_sql_name = meta_data.get("redshift_sql", "redshift.sql")
    bigquery_sql_name = meta_data.get("bigquery_sql", "bigquery.sql")
    prompt_name = meta_data.get("prompt_file", "prompt.txt")
    
    redshift_sql_path = recipe_dir / redshift_sql_name
    bigquery_sql_path = recipe_dir / bigquery_sql_name
    prompt_path = recipe_dir / prompt_name
    
    # Handle input_csv_file path if specified
    input_csv_path = meta_data.get("input_csv_file")
    if input_csv_path:
        # Check if leads.csv exists at the target output location
        output_dir = OUTPUT_ROOT / recipe_name
        leads_csv_path = output_dir / "leads.csv"
        
        if not leads_csv_path.exists():
            logger.warning(f"leads.csv not found at {leads_csv_path}")
            
            # If input_csv_file points to a file that exists, create a symlink
            try:
                # Try possible interpretations of the input_csv_file path
                possible_paths = [
                    recipe_dir / input_csv_path,  # Relative to recipe dir
                    Path(input_csv_path),  # Absolute path
                    PROJECT_ROOT / input_csv_path  # Relative to project root
                ]
                
                csv_found = False
                for src_path in possible_paths:
                    if src_path.exists() and src_path.is_file():
                        # Create output directory if it doesn't exist
                        output_dir.mkdir(parents=True, exist_ok=True)
                        
                        # Create a symlink instead of copying to save space
                        if not leads_csv_path.exists():
                            import os
                            try:
                                os.symlink(src_path, leads_csv_path)
                                logger.info(f"Created symlink from {src_path} to {leads_csv_path}")
                                csv_found = True
                                break
                            except Exception as e:
                                logger.error(f"Error creating symlink: {e}")
                                # If symlink fails, try copy
                                try:
                                    import shutil
                                    shutil.copy2(src_path, leads_csv_path)
                                    logger.info(f"Copied {src_path} to {leads_csv_path}")
                                    csv_found = True
                                    break
                                except Exception as e2:
                                    logger.error(f"Error copying file: {e2}")
                
                if not csv_found:
                    logger.warning(f"Could not find or create leads.csv from {input_csv_path}")
            except Exception as e:
                logger.error(f"Error handling input_csv_file: {e}")
    
    # Check if the recipe really needs Redshift
    needs_redshift = False
    
    # Determine if recipe needs Redshift based on:
    # 1. Does the redshift file actually exist?
    # 2. Is there a special flag in meta.yml?
    if redshift_sql_path.exists():
        needs_redshift = True
    elif meta_data.get("skip_redshift", False) is False and meta_data.get("needs_redshift", False) is True:
        # If explicitly configured to need Redshift but file is missing, log warning
        logger.warning(f"Recipe {recipe_name} is configured to use Redshift, but {redshift_sql_name} is missing.")
        needs_redshift = True
    
    # Add a property to Recipe class
    recipe = Recipe(
        name=recipe_name,
        dir_path=recipe_dir,
        redshift_sql_path=redshift_sql_path,
        bigquery_sql_path=bigquery_sql_path,
        prompt_path=prompt_path,
        meta_path=meta_path,
        meta=meta_data,
        needs_redshift=needs_redshift
    )
    
    return recipe

def get_recipe_outputs(recipe_name: str) -> Dict[str, Any]:
    """Get information about a recipe's output directories and files.
    
    Args:
        recipe_name: Name of the recipe
        
    Returns:
        Dictionary with output directory information
    """
    recipe_output_dir = OUTPUT_ROOT / recipe_name
    
    if not recipe_output_dir.exists():
        logger.info(f"No output directory for recipe: {recipe_name}")
        return {"exists": False}
    
    # Find all timestamp directories
    timestamp_dirs = []
    
    for d in recipe_output_dir.iterdir():
        if d.is_dir() and d.name[0].isdigit():  # Timestamp directories start with digits
            # Get creation time
            created = d.stat().st_mtime
            timestamp_dirs.append({
                "path": d,
                "name": d.name,
                "created": created,
                "created_str": datetime.fromtimestamp(created).strftime("%Y-%m-%d %H:%M:%S")
            })
    
    # Sort by creation time (newest first)
    timestamp_dirs.sort(key=lambda x: x["created"], reverse=True)
    
    # Check for common output files in the recipe directory
    lead_csv = recipe_output_dir / "leads.csv"
    conv_csv = recipe_output_dir / "conversations.csv"
    summary_csv = recipe_output_dir / "summary.csv"
    
    return {
        "exists": True,
        "path": str(recipe_output_dir),
        "timestamp_dirs": timestamp_dirs,
        "has_leads_csv": lead_csv.exists(),
        "has_conversations_csv": conv_csv.exists(),
        "has_summary_csv": summary_csv.exists(),
        "leads_csv_size": lead_csv.stat().st_size if lead_csv.exists() else 0,
        "conversations_csv_size": conv_csv.stat().st_size if conv_csv.exists() else 0,
        "summary_csv_size": summary_csv.stat().st_size if summary_csv.exists() else 0,
        "timestamp_count": len(timestamp_dirs)
    }

def check_marker_status(recipe_name: str) -> Tuple[bool, Path, Optional[str]]:
    """Check if a Redshift marker exists for today for the given recipe.
    
    Returns:
        Tuple of (exists, marker_path, timestamp_string)
    """
    today = datetime.now().strftime('%Y%m%d')
    marker_path = Path(f"redshift_queried_{recipe_name}_{today}.marker")
    
    if marker_path.exists():
        # Try to read the timestamp from the marker
        try:
            with open(marker_path, 'r') as f:
                marker_content = f.read().strip()
                # Extract the timestamp if possible
                if "at " in marker_content:
                    timestamp_str = marker_content.split("at ")[1]
                    # Format timestamp for display
                    try:
                        dt = datetime.fromisoformat(timestamp_str)
                        return True, marker_path, dt.strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        return True, marker_path, timestamp_str
                return True, marker_path, None
        except Exception:
            return True, marker_path, None
    return False, marker_path, None 