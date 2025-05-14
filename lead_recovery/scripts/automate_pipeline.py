#!/usr/bin/env python3
"""
Automated script to run the lead recovery pipeline with proper environment setup.
This script can be called by cron or other schedulers to automate the pipeline.
"""
import os
import sys
import logging
import traceback
import subprocess
from pathlib import Path
from datetime import datetime, time, timezone
import pytz
import dotenv

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

def run_pipeline(recipe: str):
    """Run the lead recovery pipeline with the current settings."""
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

    # Check if we should use cached Redshift data
    today = datetime.now().strftime('%Y%m%d')
    cache_marker_path = Path(f"redshift_queried_{recipe}_{today}.marker")
    use_cached_option = ""
    ran_with_no_cache = False
    
    if cache_marker_path.exists():
        # We already queried Redshift today for this recipe, use cached data
        use_cached_option = "--use-cached-redshift"
        logger.info(f"Using cached Redshift data for recipe {recipe} (marker found: {cache_marker_path})")
    else:
        # First run of the day for this recipe, query Redshift
        use_cached_option = "--no-use-cached-redshift"
        ran_with_no_cache = True
        logger.info(f"Will attempt to query fresh Redshift data for recipe {recipe} (marker not found: {cache_marker_path})")
            
    # Build the command
    command_parts = [
        str(python_executable),
        "-m", module_to_run,
        "run",
        "--recipe", recipe
    ]
    if use_cached_option:
        # --use-cached-redshift or --no-use-cached-redshift
        command_parts.append(use_cached_option)
    
    # Add --no-cache if you want to disable summary cache by default in cron, 
    # or make it configurable if needed.
    # For now, let's assume we want to use the cache by default in cron like interactive runs.
    # command_parts.append("--no-cache") 

    command = " ".join(command_parts)
    logger.info(f"Executing command: {command}")
    
    try:
        # Run the command and capture output
        result = subprocess.run(
            command, 
            shell=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # Log all output
        for line in result.stdout.splitlines():
            logger.info(f"[{recipe}] {line.strip()}")
            
        if result.returncode != 0:
            logger.error(f"Command for recipe {recipe} failed with return code {result.returncode}")
        else:
            logger.info(f"Pipeline for recipe {recipe} executed successfully")
            if ran_with_no_cache:
                try:
                    cache_marker_path.touch()
                    logger.info(f"Created Redshift marker file for recipe {recipe}: {cache_marker_path}")
                except Exception as e:
                    logger.error(f"Failed to create Redshift marker file for recipe {recipe} post-run: {e}")
            
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
    
    # Modified: Get recipe from command-line arguments
    if len(sys.argv) > 1:
        recipe_to_run = sys.argv[1]
        print(f"*** DEBUG: Command-line argument received: {recipe_to_run} ***")
        run_pipeline(recipe_to_run)
    else:
        logger.error("No recipe specified on the command line. Usage: python -m lead_recovery.scripts.automate_pipeline <recipe_name>")
        sys.exit(1) # Exit with an error code 