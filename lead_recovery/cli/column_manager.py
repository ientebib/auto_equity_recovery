"""
Column Manager Module

Utilities for managing output columns based on enabled/disabled functions.
"""
import logging
import yaml
from pathlib import Path
from typing import Dict, Any, List, Set, Optional

from ..python_flags import FUNCTION_COLUMNS

logger = logging.getLogger(__name__)

def get_columns_from_yaml(recipe_path: Path) -> Dict[str, List[str]]:
    """
    Extract column information from recipe's meta.yml file.
    
    Args:
        recipe_path: Path to the recipe directory
        
    Returns:
        Dictionary mapping function names to lists of column names
    """
    result = {}
    
    meta_path = recipe_path / "meta.yml"
    if not meta_path.exists():
        logger.warning(f"No meta.yml found at {meta_path}")
        return result
    
    try:
        with open(meta_path, "r") as f:
            meta = yaml.safe_load(f)
        
        # Check if columns section exists
        if not meta or "columns" not in meta:
            return result
        
        columns_section = meta.get("columns", {})
        
        # Extract function-column mappings
        for function_name, info in columns_section.items():
            if isinstance(info, dict) and "outputs" in info:
                result[function_name] = info["outputs"]
    
    except Exception as e:
        logger.error(f"Error reading meta.yml at {meta_path}: {e}")
    
    return result

def get_columns_for_function(function_name: str) -> List[str]:
    """
    Get the columns produced by a specific function.
    
    Args:
        function_name: Name of the function
        
    Returns:
        List of column names produced by the function
    """
    # Special cases for function name mapping
    if function_name == "temporal_flags":
        function_name = "calculate_temporal_flags"
    
    return FUNCTION_COLUMNS.get(function_name, [])

def generate_column_includes(recipe_name: str, enabled_functions: List[str]) -> List[str]:
    """
    Generate CLI arguments for including specific columns based on enabled functions.
    
    Args:
        recipe_name: Name of the recipe
        enabled_functions: List of enabled function names
        
    Returns:
        List of CLI arguments for column inclusion
    """
    project_root = Path(__file__).resolve().parent.parent.parent
    recipe_path = project_root / "recipes" / recipe_name
    
    # Try to get function columns from meta.yml first (for backward compatibility)
    function_columns_from_yaml = get_columns_from_yaml(recipe_path)
    cli_args = []
    
    # Get all columns from enabled functions
    included_columns = set()
    for func_name in enabled_functions:
        # First try to get columns from the centralized FUNCTION_COLUMNS dictionary
        columns = get_columns_for_function(func_name)
        
        # If not found, fall back to the meta.yml definition (backward compatibility)
        if not columns and func_name in function_columns_from_yaml:
            columns = function_columns_from_yaml[func_name]
            
        included_columns.update(columns)
    
    # Add --include-columns argument if we have specific columns
    if included_columns:
        cli_args.append("--include-columns")
        cli_args.append(",".join(included_columns))
    
    return cli_args

def generate_column_excludes(recipe_name: str, disabled_functions: List[str]) -> List[str]:
    """
    Generate CLI arguments for excluding specific columns based on disabled functions.
    
    Args:
        recipe_name: Name of the recipe
        disabled_functions: List of disabled function names
        
    Returns:
        List of CLI arguments for column exclusion
    """
    project_root = Path(__file__).resolve().parent.parent.parent
    recipe_path = project_root / "recipes" / recipe_name
    
    # Try to get function columns from meta.yml first (for backward compatibility)
    function_columns_from_yaml = get_columns_from_yaml(recipe_path)
    cli_args = []
    
    # Get all columns from disabled functions
    excluded_columns = set()
    for func_name in disabled_functions:
        # First try to get columns from the centralized FUNCTION_COLUMNS dictionary
        columns = get_columns_for_function(func_name)
        
        # If not found, fall back to the meta.yml definition (backward compatibility)
        if not columns and func_name in function_columns_from_yaml:
            columns = function_columns_from_yaml[func_name]
            
        excluded_columns.update(columns)
    
    # Add --exclude-columns argument if we have specific columns
    if excluded_columns:
        cli_args.append("--exclude-columns")
        cli_args.append(",".join(excluded_columns))
    
    return cli_args 