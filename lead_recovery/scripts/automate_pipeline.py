#!/usr/bin/env python3
"""
Automated script to run the lead recovery pipeline with proper environment setup.
This script can be called by cron or other schedulers to automate the pipeline.
"""
import logging
import os
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import dotenv
import pytz

# Add parent directory to path to allow imports from lead_recovery package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# Load environment variables from .env file first
dotenv.load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    handlers=[
        logging.FileHandler("cron_lead_recovery.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("lead_recovery_automation")

def setup_environment():
    """Set up environment variables needed for the pipeline"""
    # Set the working directory to the repo root directory
    os.chdir(Path(__file__).resolve().parent.parent.parent)
    
    # Get settings using get_settings() function, not direct import
    try:
        from lead_recovery.config import get_settings
        settings = get_settings()
        credentials_path = settings.GOOGLE_CREDENTIALS_PATH
    except ImportError:
        logger.warning("Could not import lead_recovery.config.get_settings, falling back to environment variable")
        credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    
    # Use environment variables only, no hard-coded paths
    if not credentials_path:
        logger.error("GOOGLE_APPLICATION_CREDENTIALS not set in environment variables or .env file")
        return False
    else:
        # Verify the path exists
        if not os.path.exists(credentials_path):
            logger.error(f"Credentials file not found at specified path: {credentials_path}")
            return False
        # Use the existing path
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
        logger.info(f"Using credentials from settings: {credentials_path}")
    
    return True

def run_pipeline(recipe: str, additional_args=None):
    """
    Run the lead recovery pipeline for the specified recipe using the standardized CLI.
    
    Args:
        recipe: Name of the recipe to run
        additional_args: List of additional CLI arguments to pass to the main CLI
    """
    start_time = datetime.now()
    logger.info(f"*** STARTING AUTOMATED PIPELINE RUN AT {start_time} FOR RECIPE: {recipe} ***")
    
    # Setup environment
    if not setup_environment():
        logger.error("Environment setup failed. Exiting.")
        return
    
    # Choose recipe
    logger.info(f"Running recipe: {recipe}")
    
    # Construct the command to run the pipeline module directly
    project_root = Path(__file__).resolve().parent.parent.parent # Project root
    python_executable = project_root / "fresh_env" / "bin" / "python"
    module_to_run = "lead_recovery.cli.main"

    if not python_executable.exists():
        logger.error(f"Python executable not found at: {python_executable}")
        logger.error("Ensure the virtual environment 'fresh_env' exists and is correctly structured.")
        return

    # Build the base command
    cli_command = [
        str(python_executable),
        "-m", module_to_run,
        "run",
        "--recipe", recipe
    ]
    
    # Check if we should use cached Redshift data
    today = datetime.now().strftime('%Y%m%d')
    cache_marker_path = Path(f"redshift_queried_{recipe}_{today}.marker")
    if cache_marker_path.exists():
        # We already queried Redshift today for this recipe, use cached data
        cli_command.append("--use-cached-redshift")
        logger.info(f"Using cached Redshift data for recipe {recipe} (marker found: {cache_marker_path})")
    else:
        # First run of the day for this recipe, query Redshift
        cli_command.append("--no-use-cached-redshift")
        logger.info(f"Will attempt to query fresh Redshift data for recipe {recipe} (marker not found: {cache_marker_path})")
    
    # Add any additional CLI arguments
    if additional_args:
        cli_command.extend(additional_args)
    
    # Print the full command for debugging
    command_str = " ".join(cli_command)
    logger.info(f"Executing command: {command_str}")
    
    try:
        # Run the command and capture output
        result = subprocess.run(
            cli_command, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # Log all output
        for line in result.stdout.splitlines():
            logger.info(f"[{recipe}] {line.strip()}")
            
        if result.returncode != 0:
            logger.error(f"Command for recipe {recipe} failed with return code {result.returncode}")
            logger.error(f"Command output: {result.stdout}")
        else:
            logger.info(f"Pipeline for recipe {recipe} executed successfully")
            
        end_time = datetime.now()
        duration = end_time - start_time
        logger.info(f"*** PIPELINE RUN FOR RECIPE {recipe} COMPLETED IN {duration} ***")
            
    except Exception as e:
        logger.error(f"Failed to execute pipeline: {str(e)}")
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    # Check if we're within business hours (Mexico City time, 10:30am-6:30pm weekdays)
    mexico_tz = pytz.timezone("America/Mexico_City")
    now = datetime.now(timezone.utc).astimezone(mexico_tz)
    
    # Only run during business hours
    # Uncomment this for production to limit execution times
    """
    if now.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
        logger.info("Not running on weekends")
        sys.exit(0)
        
    business_start = time(10, 30)  # 10:30am
    business_end = time(18, 30)    # 6:30pm
    
    current_time = now.time()
    if current_time < business_start or current_time > business_end:
        logger.info("Outside business hours (10:30am-6:30pm Mexico City time)")
        sys.exit(0)
    """
    
    # Get recipe from command-line arguments
    if len(sys.argv) > 1:
        recipe_to_run = sys.argv[1]
        
        # Collect any additional arguments (after the recipe name)
        additional_args = sys.argv[2:] if len(sys.argv) > 2 else None
        
        logger.info(f"Running recipe: {recipe_to_run} with additional args: {additional_args}")
        run_pipeline(recipe_to_run, additional_args)
    else:
        logger.error("No recipe specified on the command line. Usage: python -m lead_recovery.scripts.automate_pipeline <recipe_name> [additional CLI arguments]")
        sys.exit(1) # Exit with an error code 