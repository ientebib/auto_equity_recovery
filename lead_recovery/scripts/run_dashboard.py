#!/usr/bin/env python3
"""
Dashboard launch script.

This script launches the Streamlit dashboard for visualizing lead recovery data.
"""
import logging
import os
import subprocess
import sys
from pathlib import Path

# Add parent directory to path to allow imports from lead_recovery package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
)
logger = logging.getLogger("dashboard_launcher")

def main():
    """Start the Streamlit dashboard."""
    try:
        # Change to the repo root directory
        repo_root = Path(__file__).resolve().parent.parent.parent
        os.chdir(repo_root)
        logger.info(f"Working directory set to: {repo_root}")
        
        # Path to dashboard app
        dashboard_app = repo_root / "dashboard" / "app.py"
        
        if not dashboard_app.exists():
            logger.error(f"Dashboard app not found at: {dashboard_app}")
            sys.exit(1)
        
        # Launch Streamlit with the dashboard app
        logger.info(f"Launching dashboard from: {dashboard_app}")
        
        # Find streamlit in path
        import shutil
        streamlit_path = shutil.which("streamlit")
        
        if not streamlit_path:
            logger.error("Streamlit not found in PATH")
            print("Error: Streamlit is not installed or not in PATH")
            print("Install it with: pip install streamlit")
            sys.exit(1)
        
        # Run streamlit
        cmd = [streamlit_path, "run", str(dashboard_app), "--server.port=8501"]
        logger.info(f"Running command: {' '.join(cmd)}")
        
        # Use subprocess.run in a way that forwards output to the console
        subprocess.run(cmd, check=True)
    
    except KeyboardInterrupt:
        logger.info("Dashboard stopped by user")
    except Exception as e:
        logger.error(f"Error launching dashboard: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 