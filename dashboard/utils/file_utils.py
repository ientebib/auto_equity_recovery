"""
File Utilities Module

Functions for working with files and directories.
"""
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add project root to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Use absolute paths
PROJECT_ROOT = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
RECIPE_ROOT = PROJECT_ROOT / "recipes"
OUTPUT_ROOT = PROJECT_ROOT / "output_run"

def read_file_content(file_path: Path) -> str:
    """Read the content of a file.
    
    Args:
        file_path: Path to the file to read.
        
    Returns:
        The content of the file as a string.
    """
    if not file_path.exists():
        return f"File not found: {file_path}"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

def open_finder(directory_path: Path) -> bool:
    """Open the given directory in Finder (macOS) or Explorer (Windows).
    
    Args:
        directory_path: Path to the directory to open.
        
    Returns:
        True if successful, False otherwise.
    """
    try:
        if not directory_path.exists():
            return False
        
        # Use platform-specific command
        if os.name == 'posix':  # macOS or Linux
            if os.uname().sysname == 'Darwin':  # macOS
                subprocess.run(['open', str(directory_path)])
            else:  # Linux
                subprocess.run(['xdg-open', str(directory_path)])
        elif os.name == 'nt':  # Windows
            subprocess.run(['explorer', str(directory_path)])
        else:
            return False
        
        return True
    except Exception as e:
        print(f"Error opening directory: {e}")
        return False

def get_latest_output_timestamp(recipe_name: str) -> Optional[str]:
    """Get the timestamp of the most recent output directory for a recipe.
    
    Args:
        recipe_name: Name of the recipe.
        
    Returns:
        Formatted timestamp string or None if no output directories exist.
    """
    recipe_output_dir = OUTPUT_ROOT / recipe_name
    if not recipe_output_dir.exists():
        return None
    
    # Find the most recent output directory
    latest_dir = None
    latest_timestamp = 0
    
    for d in recipe_output_dir.iterdir():
        if d.is_dir() and d.name[0].isdigit():  # Timestamp directories start with a digit
            dir_timestamp = d.stat().st_mtime
            if dir_timestamp > latest_timestamp:
                latest_timestamp = dir_timestamp
                latest_dir = d
    
    if latest_dir:
        # Format the timestamp for display
        dt = datetime.fromtimestamp(latest_timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    
    return None 