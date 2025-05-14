"""
Lead Recovery Dashboard

A Streamlit dashboard for the Lead Recovery Pipeline that allows users to:
- View and run recipes
- Manage Redshift markers
- Monitor pipeline execution
- Explore recipe configurations
"""
import os
import sys
import time
import subprocess
import logging
from pathlib import Path
from datetime import datetime
import threading
import queue
import yaml
import json
import streamlit as st
from typing import List, Dict, Any, Tuple, Optional
import re

# Add project root to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import from utils
from dashboard.utils.recipe_manager import get_recipes, get_recipe_details, Recipe, check_marker_status, get_recipe_outputs
from dashboard.utils.file_utils import read_file_content, open_finder, get_latest_output_timestamp
from dashboard.utils.log_monitor import LogMonitor, capture_output
from dashboard.utils.process_manager import ProcessManager, run_recipe_process, get_running_processes, terminate_process
from dashboard.utils.marker_utils import (
    has_redshift_marker, has_bigquery_marker, 
    create_redshift_marker, create_bigquery_marker
)
from dashboard.components import render_function_panel

# Set page config
st.set_page_config(
    page_title="Lead Recovery Dashboard",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("dashboard")

# Use absolute paths
PROJECT_ROOT = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
RECIPE_ROOT = PROJECT_ROOT / "recipes"
OUTPUT_ROOT = PROJECT_ROOT / "output_run"

def setup_session_state():
    """Initialize session state variables"""
    if 'recipes' not in st.session_state:
        st.session_state.recipes = get_recipes()
    
    if 'selected_recipe' not in st.session_state:
        st.session_state.selected_recipe = None
    
    if 'recipe_details' not in st.session_state:
        st.session_state.recipe_details = None
    
    if 'running_process' not in st.session_state:
        st.session_state.running_process = None
    
    if 'log_queue' not in st.session_state:
        st.session_state.log_queue = queue.Queue()
    
    if 'log_monitor' not in st.session_state:
        st.session_state.log_monitor = None

def select_recipe():
    """Update selected recipe based on dropdown"""
    recipe_name = st.session_state.recipe_dropdown
    if recipe_name != st.session_state.selected_recipe:
        st.session_state.selected_recipe = recipe_name
        st.session_state.recipe_details = get_recipe_details(recipe_name)

def render_sidebar():
    """Render the sidebar with recipe selection and status chips"""
    with st.sidebar:
        st.title("Lead Recovery Dashboard")
        
        # Refresh recipes button
        if st.button("🔄 Refresh Recipes"):
            st.session_state.recipes = get_recipes()
            st.rerun()
        
        # Recipe selection dropdown
        recipe_options = ["Select a Recipe..."] + st.session_state.recipes
        selected_index = 0
        if st.session_state.selected_recipe in recipe_options:
            selected_index = recipe_options.index(st.session_state.selected_recipe)
        
        st.selectbox(
            "Select Recipe",
            recipe_options,
            key="recipe_dropdown",
            on_change=select_recipe,
            index=selected_index
        )
        
        # Show recipe status chips if a recipe is selected
        if st.session_state.selected_recipe and st.session_state.selected_recipe != "Select a Recipe...":
            recipe = st.session_state.recipe_details
            
            st.subheader("Recipe Status")
            
            # Status chips
            col1, col2, col3 = st.columns(3)
            
            # Has Redshift
            has_redshift = recipe.redshift_sql_path.exists()
            with col1:
                redshift_color = "green" if has_redshift else "gray"
                st.markdown(f"<span style='background-color:{redshift_color};color:white;padding:5px;border-radius:5px;'>{'Has Redshift' if has_redshift else 'No Redshift'}</span>", unsafe_allow_html=True)
            
            # Marker Today
            marker_exists, marker_path, marker_time = check_marker_status(recipe.name)
            with col2:
                marker_color = "green" if marker_exists else "red"
                marker_color = "gray" if not has_redshift else marker_color
                marker_text = "Marker Today" if marker_exists else "No Marker"
                marker_text = "N/A" if not has_redshift else marker_text
                st.markdown(f"<span style='background-color:{marker_color};color:white;padding:5px;border-radius:5px;'>{marker_text}</span>", unsafe_allow_html=True)
            
            # Cached leads.csv
            cached_leads = (OUTPUT_ROOT / recipe.name / "leads.csv").exists()
            with col3:
                cache_color = "green" if cached_leads else "gray"
                st.markdown(f"<span style='background-color:{cache_color};color:white;padding:5px;border-radius:5px;'>{'Cached Leads' if cached_leads else 'No Cached Leads'}</span>", unsafe_allow_html=True)
            
            # Last run timestamp
            last_timestamp = get_latest_output_timestamp(recipe.name)
            if last_timestamp:
                st.markdown(f"**Last Run:** {last_timestamp}")
            else:
                st.markdown("**Last Run:** Never")
            
            st.divider()

def render_recipe_explorer(recipe: Recipe):
    """Render the main recipe explorer area with tabs"""
    st.title(f"Recipe Explorer: {recipe.name}")
    
    # Set up tabs
    tab_meta, tab_sql, tab_prompt, tab_python = st.tabs([
        "Meta / Config", 
        "SQL", 
        "Prompt", 
        "Python"
    ])
    
    # Tab A: Meta / Config
    with tab_meta:
        if recipe.meta_path.exists():
            content = read_file_content(recipe.meta_path)
            st.code(content, language="yaml")
        else:
            st.warning(f"No meta.yml file found for recipe {recipe.name}")
    
    # Tab B: SQL
    with tab_sql:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Redshift SQL")
            if recipe.redshift_sql_path.exists():
                content = read_file_content(recipe.redshift_sql_path)
                st.code(content, language="sql")
            else:
                st.info("No Redshift query - this recipe skips Redshift")
        
        with col2:
            st.subheader("BigQuery SQL")
            if recipe.bigquery_sql_path and recipe.bigquery_sql_path.exists():
                content = read_file_content(recipe.bigquery_sql_path)
                st.code(content, language="sql")
            else:
                st.warning("BigQuery SQL file not found")
    
    # Tab C: Prompt
    with tab_prompt:
        if recipe.prompt_path.exists():
            content = read_file_content(recipe.prompt_path)
            st.code(content, language="text")
        else:
            st.warning(f"No prompt file found for recipe {recipe.name}")
    
    # Tab D: Python
    with tab_python:
        # Upper section: Global Functions
        st.subheader("Global Functions")
        
        global_functions = [
            {
                "name": "calculate_temporal_flags", 
                "description": "Calculate time-based flags for conversation analysis", 
                "trigger": "Executed for every conversation row"
            },
            {
                "name": "extract_message_metadata", 
                "description": "Extract last message content and sender information", 
                "trigger": "Executed for every conversation group"
            },
            {
                "name": "detect_handoff_finalization", 
                "description": "Check if a handoff process was finalized in the conversation", 
                "trigger": "Executed for every conversation group"
            },
            {
                "name": "detect_human_transfer", 
                "description": "Check if conversation was transferred to a human agent", 
                "trigger": "Executed for messages containing transfer patterns"
            },
            {
                "name": "count_consecutive_recovery_templates", 
                "description": "Count how many recovery templates were sent in sequence", 
                "trigger": "Executed when recipe has template detection enabled"
            }
        ]
        
        # Create a dataframe to display the functions
        func_data = {
            "Function": [f["name"] for f in global_functions],
            "Description": [f["description"] for f in global_functions],
            "Trigger Condition": [f["trigger"] for f in global_functions]
        }
        
        st.table(func_data)
        
        # Lower section: Custom analyzer if it exists
        st.subheader("Custom Analyzer")
        analyzer_path = recipe.dir_path / "analyzer.py"
        if analyzer_path.exists():
            content = read_file_content(analyzer_path)
            st.code(content, language="python")
        else:
            st.info("No custom analyzer")

def render_execution_controls(recipe: Recipe):
    """Render the recipe execution controls."""
    st.subheader("⚙️ Recipe Execution Settings")
    
    # Execution configuration section
    with st.container():
        # Redshift configuration
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Redshift Configuration")
            
            # Check if recipe has existing marker
            has_marker = has_redshift_marker(recipe.name)
            
            # Check if leads.csv exists
            leads_csv_exists = (OUTPUT_ROOT / recipe.name / "leads.csv").exists()
            
            # Skip Redshift checkbox
            skip_redshift = st.checkbox(
                "Skip Redshift Query",
                value=False if not has_marker else True,
                key=f"skip_redshift_{recipe.name}",
                help="Skip the Redshift query step for this recipe"
            )
            
            # Warning if skipping Redshift but no leads.csv
            if skip_redshift and not leads_csv_exists:
                st.warning(f"⚠️ Warning: leads.csv not found in output_run/{recipe.name}/. Recipe will fail if you skip Redshift!")
                if st.button("Copy Recipe Leads to Output Dir"):
                    try:
                        # Copy from recipe dir to output dir
                        recipe_leads = Path(f"recipes/{recipe.name}/leads.csv")
                        output_leads = OUTPUT_ROOT / recipe.name / "leads.csv"
                        if recipe_leads.exists():
                            OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
                            (OUTPUT_ROOT / recipe.name).mkdir(parents=True, exist_ok=True)
                            import shutil
                            shutil.copy2(recipe_leads, output_leads)
                            st.success(f"Copied leads.csv to output_run/{recipe.name}/")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"Could not find leads.csv in recipes/{recipe.name}/")
                    except Exception as e:
                        st.error(f"Error copying leads.csv: {e}")
            
            # BigQuery skip
            skip_bigquery = st.checkbox(
                "Skip BigQuery",
                value=False,
                key=f"skip_bigquery_{recipe.name}",
                help="Skip fetching conversation data from BigQuery"
            )
            
            # Summarization skip
            skip_summarize = st.checkbox(
                "Skip Summarization",
                value=False,
                key=f"skip_summarize_{recipe.name}",
                help="Skip the OpenAI summarization step"
            )
        
        with col2:
            st.markdown("#### Performance Configuration")
            
            # Max workers setting
            max_workers = st.number_input(
                "Max Workers",
                min_value=1,
                max_value=32,
                value=8,
                step=1,
                key=f"max_workers_{recipe.name}",
                help="Maximum number of concurrent workers for OpenAI calls"
            )
            
            # Debug mode setting
            debug_mode = st.checkbox(
                "Debug Mode",
                value=False,
                key=f"debug_mode_{recipe.name}",
                help="Enable verbose logging for debugging"
            )
            
            # Process timeout
            timeout_minutes = st.number_input(
                "Timeout (minutes)",
                min_value=1,
                max_value=120,
                value=30,
                step=1,
                key=f"timeout_{recipe.name}",
                help="Terminate the process after this many minutes"
            )
    
    # Get Python function configuration through function panel
    function_cli_args = render_function_panel(recipe.name)
    
    # Run button
    if not st.session_state.get("is_running", False):
        if st.button("▶️ Run Recipe", type="primary", key=f"run_{recipe.name}", use_container_width=True):
            # Build the command
            cmd = ["python", "-m", "lead_recovery.cli.main", "run", "--recipe", recipe.name]
            
            # Add skip parameters
            if skip_redshift:
                cmd.append("--skip-redshift")
            if skip_bigquery:
                cmd.append("--skip-bigquery")
            if skip_summarize:
                cmd.append("--skip-summarize")
            
            # Add performance parameters
            cmd.extend(["--max-workers", str(max_workers)])
            
            # Add verbose logging for debugging
            if debug_mode:
                cmd.extend(["--log-level", "DEBUG"])
            
            # Add function CLI arguments
            cmd.extend(function_cli_args)
            
            # Start the process
            process_manager = ProcessManager()
            process = process_manager.start_process(cmd)
            st.session_state.running_process = process
            st.session_state.is_running = True
            st.session_state.start_time = time.time()
            st.session_state.timeout_minutes = timeout_minutes
            
            # Set up a queue for logs
            st.session_state.log_queue = queue.Queue()
            
            # Start a thread to capture output
            threading.Thread(
                target=capture_output,
                args=(process, st.session_state.log_queue),
                daemon=True
            ).start()
            
            st.rerun()
    else:
        # Show stop button when running
        if st.button("⏹️ Stop Execution", type="primary", key=f"stop_{recipe.name}", use_container_width=True):
            terminate_process(st.session_state.running_process.pid)
            st.session_state.is_running = False
            st.rerun()

def format_time(seconds):
    """Format seconds into a readable time string."""
    if seconds < 60:
        return f"{int(seconds)} seconds"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}h {minutes}m"

def open_terminal_with_process(pid):
    """Open a terminal window and directly monitor the given process."""
    try:
        # Use absolute paths for everything
        project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        
        if os.name == 'posix':  # macOS or Linux
            if os.uname().sysname == 'Darwin':  # macOS
                # Find the most recent log file for direct monitoring
                recipe_name = st.session_state.get('selected_recipe')
                output_dir = os.path.join(project_dir, "output_run", recipe_name) if recipe_name else None
                
                # Look for latest log file or latest.log
                log_file = None
                
                # First try latest.log if it exists
                latest_log = os.path.join(output_dir, "latest.log") if output_dir else None
                if latest_log and os.path.exists(latest_log):
                    log_file = latest_log
                else:
                    # Look for the most recent timestamp directory if we have an output_dir
                    if output_dir:
                        # Look for the most recent timestamp directory
                        latest_timestamp = 0
                        latest_dir = None
                        
                        # Convert to Path for better glob support
                        output_path = Path(output_dir)
                        if output_path.exists():
                            for d in output_path.glob("[0-9]*"):
                                if d.is_dir() and d.stat().st_mtime > latest_timestamp:
                                    latest_timestamp = d.stat().st_mtime
                                    latest_dir = d
                        
                        if latest_dir:
                            # Look for log files in that directory
                            for f in latest_dir.glob("*.log"):
                                log_file = str(f.absolute())
                                break
                
                # Use a run_output.log in project dir if it exists, or create a dummy for monitoring
                latest_run_log = os.path.join(project_dir, "run_output.log")
                
                # If we found a log file, tail it directly; otherwise show process info
                if log_file:
                    script = f'''
                    tell application "Terminal"
                        activate
                        do script "cd '{project_dir}' && echo 'Monitoring process {pid} - Log file: {os.path.basename(log_file)}'; echo '-------------------------------------------'; tail -f '{log_file}'"
                    end tell
                    '''
                else:
                    # Fallback to just showing process info and create a temp log file to monitor
                    # Touch run_output.log if it doesn't exist
                    if not os.path.exists(latest_run_log):
                        with open(latest_run_log, 'w') as f:
                            f.write(f"Started monitoring process {pid} at {datetime.now()}\n")
                    
                    script = f'''
                    tell application "Terminal"
                        activate
                        do script "cd '{project_dir}' && echo 'Monitoring process {pid}'; ps -p {pid} -f; echo '-------------------------------------------'; echo 'Live process output (from run_output.log):'; tail -f '{latest_run_log}'"
                    end tell
                    '''
                
                subprocess.run(['osascript', '-e', script])
            else:  # Linux
                # For Linux, ensure we're in the right directory
                project_dir_abs = os.path.abspath(project_dir)
                recipe_name = st.session_state.selected_recipe
                output_dir = os.path.join(project_dir_abs, "output_run", recipe_name)
                latest_log = os.path.join(output_dir, "latest.log")
                
                if os.path.exists(latest_log):
                    cmd = f'cd "{project_dir_abs}" && tail -f "{latest_log}"'
                else:
                    run_output_log = os.path.join(project_dir_abs, "run_output.log")
                    if not os.path.exists(run_output_log):
                        with open(run_output_log, 'w') as f:
                            f.write(f"Started monitoring process {pid} at {datetime.now()}\n")
                    
                    cmd = f'cd "{project_dir_abs}" && ps -p {pid} -f --forest; echo; echo "Live process output (from run_output.log):"; tail -f "{run_output_log}"'
                
                subprocess.run(['x-terminal-emulator', '-e', f'bash -c "{cmd}"'], check=False)
        elif os.name == 'nt':  # Windows
            # Windows approach - directly monitor the process
            project_dir_abs = os.path.abspath(project_dir)
            recipe_name = st.session_state.selected_recipe
            output_dir = os.path.join(project_dir_abs, "output_run", recipe_name)
            latest_log = os.path.join(output_dir, "latest.log")
            
            if os.path.exists(latest_log):
                cmd = f'cd /d "{project_dir_abs}" && powershell -Command "Get-Content -Path \'{latest_log}\' -Wait"'
            else:
                run_output_log = os.path.join(project_dir_abs, "run_output.log")
                if not os.path.exists(run_output_log):
                    with open(run_output_log, 'w') as f:
                        f.write(f"Started monitoring process {pid} at {datetime.now()}\n")
                
                cmd = f'cd /d "{project_dir_abs}" && tasklist /fi "PID eq {pid}" /v & echo. & echo Monitoring process {pid} & echo. & powershell -Command "Get-Content -Path \'{run_output_log}\' -Wait"'
            
            subprocess.run(['start', 'cmd', '/k', cmd], shell=True, check=False)
    except Exception as e:
        logger.error(f"Error opening terminal: {e}")
        return False
    
    return True

def get_running_recipe_processes():
    """Get information about all currently running recipe processes.
    
    Returns:
        A dictionary with recipe names as keys and process info as values
    """
    running_recipes = {}
    project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    try:
        # Command to find all lead_recovery recipe processes
        if os.name == 'posix':  # macOS or Linux
            cmd = ["ps", "aux"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if "lead_recovery.cli.main run" in line and "--recipe" in line:
                        # Extract recipe name and process ID
                        parts = line.split()
                        pid = parts[1]
                        
                        # Extract recipe name from the command arguments
                        cmd_parts = line.split("--recipe")
                        if len(cmd_parts) > 1:
                            recipe_name = cmd_parts[1].strip().split()[0]
                            
                            # Extract start time and status using ps
                            start_time_result = subprocess.run(
                                ["ps", "-p", pid, "-o", "lstart="], 
                                capture_output=True, 
                                text=True
                            )
                            start_time = start_time_result.stdout.strip() if start_time_result.returncode == 0 else "Unknown"
                            
                            # Check for additional flags
                            max_workers = None
                            if "--max-workers" in line:
                                max_workers_parts = line.split("--max-workers")
                                if len(max_workers_parts) > 1:
                                    max_workers_str = max_workers_parts[1].strip().split()[0]
                                    try:
                                        max_workers = int(max_workers_str)
                                    except ValueError:
                                        pass
                            
                            # Try to find the output directory
                            output_dir = os.path.join(project_dir, "output_run", recipe_name)
                            
                            # Check for log file
                            log_file = None
                            latest_log = os.path.join(output_dir, "latest.log")
                            if os.path.exists(latest_log):
                                log_file = latest_log
                            else:
                                # Look for most recent timestamp directory
                                try:
                                    if os.path.exists(output_dir):
                                        dirs = [d for d in os.listdir(output_dir) 
                                               if os.path.isdir(os.path.join(output_dir, d)) and 
                                               d[0].isdigit()]
                                        
                                        if dirs:
                                            # Sort by modification time
                                            dirs.sort(key=lambda d: os.path.getmtime(os.path.join(output_dir, d)), 
                                                     reverse=True)
                                            latest_dir = os.path.join(output_dir, dirs[0])
                                            
                                            # Look for log files
                                            for f in os.listdir(latest_dir):
                                                if f.endswith('.log'):
                                                    log_file = os.path.join(latest_dir, f)
                                                    break
                                except Exception:
                                    pass  # Ignore errors in log file detection
                            
                            running_recipes[recipe_name] = {
                                "pid": pid,
                                "start_time": start_time,
                                "command": line.strip(),
                                "max_workers": max_workers,
                                "log_file": log_file
                            }
        elif os.name == 'nt':  # Windows
            cmd = ["tasklist", "/v", "/fi", "imagename eq python.exe", "/fo", "csv"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if "lead_recovery.cli.main run" in line and "--recipe" in line:
                        # Windows parsing would be more complex
                        # For now, we'll just capture the process
                        running_recipes["unknown"] = {
                            "pid": "unknown",
                            "start_time": "unknown",
                            "command": line
                        }
    except Exception as e:
        logger.error(f"Error checking for running recipes: {e}")
    
    return running_recipes

def render_running_processes_panel():
    """Render a panel showing all currently running recipe processes."""
    running_recipes = get_running_recipe_processes()
    
    if running_recipes:
        st.subheader("🔄 Running Recipe Processes")
        
        # Create styled panel
        st.markdown("""
        <style>
        .process-panel {
            background-color: #f0f2f6;
            border-radius: 5px;
            padding: 15px;
            margin-bottom: 20px;
        }
        .process-header {
            font-weight: bold;
            margin-bottom: 10px;
            font-size: 1.1em;
        }
        .process-details {
            font-size: 0.9em;
            color: #444;
            margin-bottom: 10px;
        }
        .log-file {
            font-family: monospace;
            background-color: #e6e6e6;
            padding: 3px 6px;
            border-radius: 3px;
            font-size: 0.85em;
        }
        </style>
        """, unsafe_allow_html=True)
        
        for recipe_name, process_info in running_recipes.items():
            # Don't show the currently selected recipe's process if it's the one we launched
            if (st.session_state.running_process and 
                hasattr(st.session_state.running_process, 'pid') and 
                process_info["pid"] == str(st.session_state.running_process.pid)):
                continue
                
            # Format the start time 
            start_time_display = process_info["start_time"]
            
            # Create HTML for the log file if it exists
            log_file_html = ""
            if process_info.get("log_file"):
                log_path = process_info["log_file"]
                log_file_html = f'<div class="log-file">Log file: {log_path}</div>'
            
            # Create a styled panel for each process
            max_workers_text = f"Max Workers: {process_info.get('max_workers')}" if process_info.get('max_workers') else ""
            
            st.markdown(f"""
            <div class='process-panel'>
                <div class='process-header'>Recipe: {recipe_name}</div>
                <div class='process-details'>
                    Process ID: {process_info["pid"]}<br>
                    Started: {start_time_display}<br>
                    {max_workers_text}<br>
                    {log_file_html}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Add buttons for actions
            col1, col2 = st.columns(2)
            with col1:
                if st.button(f"🖥️ View in Terminal ({process_info['pid']})", key=f"term_{process_info['pid']}"):
                    open_terminal_with_process(process_info["pid"])
            with col2:
                if st.button(f"⚠️ Terminate Process ({process_info['pid']})", key=f"kill_{process_info['pid']}"):
                    if st.session_state.get('confirm_terminate') == process_info["pid"]:
                        terminate_process(process_info["pid"])
                        st.success(f"Process {process_info['pid']} terminated")
                        st.session_state.pop('confirm_terminate', None)
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.session_state.confirm_terminate = process_info["pid"]
                        st.warning(f"Are you sure you want to terminate process {process_info['pid']}? Click again to confirm.")
                        
    elif not st.session_state.running_process:
        # Only show "No running processes" if we're not running anything ourselves
        st.info("No recipe processes are currently running on the system.")

def terminate_process(pid):
    """Terminate a process by PID."""
    try:
        if os.name == 'posix':  # macOS or Linux
            os.kill(int(pid), 15)  # SIGTERM
        elif os.name == 'nt':  # Windows
            subprocess.run(["taskkill", "/PID", pid, "/F"])
        return True
    except Exception as e:
        logger.error(f"Error terminating process {pid}: {e}")
        return False

def render_log_output():
    """Render the log output area"""
    if st.session_state.running_process:
        st.subheader("Recipe Execution Status")
        
        # Check if process is still running
        is_running = st.session_state.running_process.poll() is None
        
        # Get logs from the queue for analysis, but limit the number to prevent UI slowdown
        try:
            # Get up to 1000 most recent log lines
            all_logs = list(st.session_state.log_queue.queue)
            logs = all_logs[-1000:] if len(all_logs) > 1000 else all_logs
        except Exception as e:
            logger.error(f"Error getting logs: {e}")
            logs = ["Error retrieving logs. Process is still running in the background."]
        
        # If the process is running, update its info from logs
        process = st.session_state.running_process
        if hasattr(process, 'info') and is_running:
            try:
                process.info.update_from_logs(logs)
            except Exception as e:
                logger.error(f"Error updating process info: {e}")
        
        # Create a status container
        status_container = st.container()
        with status_container:
            # Status indicators
            col1, col2 = st.columns(2)
            with col1:
                if is_running:
                    st.info("⏳ Status: Recipe is actively running")
                    
                    # Get progress info
                    if hasattr(process, 'info'):
                        progress = process.info.progress
                        elapsed_time = process.info.get_elapsed_time()
                        remaining_time = process.info.get_estimated_remaining_time()
                        
                        # Show progress bar
                        progress_bar = st.progress(progress)
                        
                        # Show time information
                        st.caption(f"⏱️ Elapsed: {format_time(elapsed_time)} | Estimated remaining: {format_time(remaining_time)}")
                        
                        # Show phase information
                        st.caption(f"Current phase: {process.info.phase.replace('_', ' ').title()}")
                        
                        # Add a button to open Terminal with the running process
                        process_pid = process.pid if hasattr(process, 'pid') else None
                        if process_pid:
                            if st.button("🖥️ View in Terminal", type="primary"):
                                open_terminal_with_process(process_pid)
                    else:
                        # Fallback if process info not available
                        if 'progress_value' not in st.session_state:
                            st.session_state.progress_value = 0.0
                            st.session_state.progress_start_time = time.time()
                        
                        elapsed_time = time.time() - st.session_state.progress_start_time
                        # Simple progress estimation based on time
                        progress = min(elapsed_time / 600, 0.95)  # Assume 10-minute execution
                        st.session_state.progress_value = progress
                        st.progress(progress)
                else:
                    exit_code = st.session_state.running_process.returncode
                    if exit_code == 0:
                        st.success("✅ Status: Recipe completed successfully!")
                        st.progress(1.0)
                    else:
                        st.error(f"❌ Status: Recipe failed with exit code: {exit_code}")
                        # Show partial progress if available
                        if hasattr(process, 'info'):
                            st.progress(process.info.progress)
                        elif 'progress_value' in st.session_state:
                            st.progress(st.session_state.progress_value)
            
            with col2:
                # Show phase indicators
                # Use a try-except to handle potential UI crashes
                try:
                    log_text = '\n'.join(logs)
                    
                    phases = [
                        {"name": "Setup", "complete": True, "active": False},
                        {"name": "Redshift Query", "complete": "Redshift fetch completed" in log_text, 
                         "active": "Fetching leads from Redshift" in log_text and "Redshift fetch completed" not in log_text},
                        {"name": "BigQuery", "complete": "BigQuery fetch completed" in log_text, 
                         "active": "Fetching conversations from BigQuery" in log_text and "BigQuery fetch completed" not in log_text},
                        {"name": "OpenAI Analysis", "complete": "Summarization completed" in log_text, 
                         "active": "Starting summarization with OpenAI" in log_text and "Summarization completed" not in log_text},
                        {"name": "Report Generation", "complete": "Reports generated" in log_text, 
                         "active": "Generating reports" in log_text and "Reports generated" not in log_text}
                    ]
                    
                    for idx, phase in enumerate(phases):
                        if phase["complete"]:
                            st.markdown(f"✅ **{phase['name']}**: Completed")
                        elif phase["active"]:
                            st.markdown(f"⏳ **{phase['name']}**: In progress...")
                        else:
                            st.markdown(f"⏱️ **{phase['name']}**: Pending")
                except Exception as e:
                    st.error(f"Error displaying phases: {str(e)}")
                    logger.error(f"Error in phase display: {e}")
        
        # Show log section after status
        st.subheader("Log Output")
        
        # Create a placeholder for logs with fixed height and terminal-like appearance
        log_container = st.container()
        with log_container:
            # Display logs with terminal styling
            if logs:
                try:
                    # Create custom CSS for terminal-like appearance
                    st.markdown("""
                    <style>
                    .terminal-output {
                        background-color: #0e1117;
                        color: #FFFFFF;
                        padding: 10px;
                        border-radius: 5px;
                        font-family: 'Courier New', monospace;
                        height: 400px;
                        overflow-y: scroll;
                        white-space: pre-wrap;
                    }
                    .terminal-output::-webkit-scrollbar {
                        width: 8px;
                    }
                    .terminal-output::-webkit-scrollbar-track {
                        background: #1e1e24;
                    }
                    .terminal-output::-webkit-scrollbar-thumb {
                        background-color: #424242;
                        border-radius: 20px;
                    }
                    </style>
                    """, unsafe_allow_html=True)
                    
                    # Only show the last 100 log lines to prevent UI overload
                    displayed_logs = logs[-100:] if len(logs) > 100 else logs
                    log_text = "\n".join(displayed_logs)
                    
                    # If logs are too large, add a summary
                    if len(logs) > 100:
                        log_text = f"[Showing most recent {len(displayed_logs)} of {len(logs)} log lines]\n\n" + log_text
                    
                    # Display logs in a scrollable terminal-like container
                    st.markdown(f'<div class="terminal-output">{log_text}</div>', unsafe_allow_html=True)
                    
                    # Command display row
                    command_col1, command_col2 = st.columns([3, 1])
                    
                    with command_col1:
                        if hasattr(process, 'info') and hasattr(process.info, 'command'):
                            command = " ".join(process.info.command)
                            st.code(f"$ {command}", language="bash")
                    
                    with command_col2:
                        # Add auto-scroll feature with a button
                        auto_scroll = st.checkbox("Auto-scroll to latest logs", value=True)
                        if auto_scroll:
                            st.components.v1.html(
                                """
                                <script>
                                try {
                                    const terminalDivs = parent.document.querySelectorAll('.terminal-output');
                                    const lastTerminalDiv = terminalDivs[terminalDivs.length - 1];
                                    if (lastTerminalDiv) {
                                        lastTerminalDiv.scrollTop = lastTerminalDiv.scrollHeight;
                                    }
                                } catch (e) {
                                    console.error("Error in auto-scroll:", e);
                                }
                                </script>
                                """,
                                height=0
                            )
                except Exception as e:
                    st.error(f"Error rendering logs: {str(e)}")
                    logger.error(f"Error rendering logs: {e}")
                    st.text_area("Raw Logs (Fallback View)", "\n".join(logs[-50:]), height=300)
            else:
                st.info("Waiting for logs...")
        
        # Auto-refresh while process is running
        if is_running:
            st.empty()
            # Use a longer refresh interval to reduce UI stress
            time.sleep(2)
            st.rerun()

def main():
    """Main function to render the dashboard."""
    # Initialize session state
    setup_session_state()
    
    # Set up sidebar and main layout
    render_sidebar()
    
    # If a recipe is selected, show recipe explorer & controls
    if "selected_recipe" in st.session_state and st.session_state.selected_recipe:
        recipe_name = st.session_state.selected_recipe
        recipe = get_recipe_details(recipe_name)
        
        # Show recipe explorer
        if not st.session_state.get("is_running", False):
            render_recipe_explorer(recipe)
            
            # Show execution controls
            render_execution_controls(recipe)
        else:
            # If recipe is running, show live output
            render_log_output()
    else:
        st.title("Lead Recovery Dashboard")
        
        # Show running processes at the top
        render_running_processes_panel()
        
        st.info("Select a recipe from the sidebar to get started")

        # If a run_output.log exists, show its tail so users can still see results after refresh
        log_path_global = PROJECT_ROOT / "run_output.log"
        if log_path_global.exists():
            st.subheader("Latest Run Output (global)")
            try:
                with open(log_path_global, "r", encoding="utf-8", errors="replace") as f:
                    last_lines = f.readlines()[-400:]
                st.code("".join(last_lines) or "(Log file is empty)")
            except Exception as e:
                st.error(f"Error reading log file: {e}")

# Entry point
if __name__ == "__main__":
    main() 