"""
Process Manager Module

Utilities for running and managing subprocesses.
"""
import logging
import os
import queue
import re
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import psutil

from .log_monitor import capture_output

logger = logging.getLogger("dashboard.process_manager")

# Use absolute paths 
PROJECT_ROOT = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class ProcessInfo:
    """Class to store information about a running process."""
    
    def __init__(self, command: List[str], start_time: float):
        """Initialize process information.
        
        Args:
            command: The command that was executed
            start_time: The time when the process started
        """
        self.command = command
        self.start_time = start_time
        self.phase = "initializing"
        self.progress = 0.0
        self.estimated_total_time = 600  # Default 10 minutes
        self.last_log_lines = []
        
    def get_elapsed_time(self) -> float:
        """Get the elapsed time since the process started.
        
        Returns:
            Elapsed time in seconds
        """
        return time.time() - self.start_time
    
    def get_estimated_remaining_time(self) -> float:
        """Get the estimated remaining time.
        
        Returns:
            Estimated remaining time in seconds
        """
        if self.progress <= 0:
            return self.estimated_total_time
        
        elapsed = self.get_elapsed_time()
        estimated_total = elapsed / self.progress
        return max(0, estimated_total - elapsed)
    
    def update_from_logs(self, logs: List[str]) -> None:
        """Update process information based on log analysis.
        
        Args:
            logs: Recent log lines to analyze
        """
        self.last_log_lines = logs[-100:] if logs else []
        log_text = '\n'.join(logs)
        
        # Detect phase
        if "Generating reports" in log_text:
            self.phase = "report_generation"
        elif "Starting summarization with OpenAI" in log_text:
            self.phase = "summarization"
        elif "Fetching conversations from BigQuery" in log_text:
            self.phase = "bigquery"
        elif "Fetching leads from Redshift" in log_text:
            self.phase = "redshift"
        else:
            self.phase = "initializing"
        
        # Update progress based on log content
        elapsed_time = self.get_elapsed_time()
        if "Recipe run complete" in log_text:
            self.progress = 1.0
        elif "Reports generated" in log_text:
            self.progress = 0.95 + (min(elapsed_time, 30) / 30) * 0.05
        elif "Summarization completed" in log_text:
            self.progress = 0.90 + (min(elapsed_time, 60) / 60) * 0.05
        elif "Starting summarization with OpenAI" in log_text:
            self.progress = 0.60 + (min(elapsed_time, 300) / 300) * 0.30
        elif "BigQuery fetch completed" in log_text:
            self.progress = 0.30 + (min(elapsed_time, 120) / 120) * 0.30
        elif "Fetching conversations from BigQuery" in log_text:
            self.progress = 0.10 + (min(elapsed_time, 180) / 180) * 0.20
        elif "Redshift fetch completed" in log_text:
            self.progress = 0.10
        else:
            # Default progress based on time - assume 10 minutes total
            self.progress = min(elapsed_time / 600, 0.95)

class ProcessManager:
    """Manager for running and tracking subprocess execution."""
    
    def __init__(self):
        """Initialize the process manager."""
        self.output_file = Path("run_output.log")
    
    def start_process(self, command: List[str]) -> subprocess.Popen:
        """Start a new process and capture its output.
        
        Args:
            command: Command to run as a list of strings
            
        Returns:
            The subprocess.Popen object representing the running process
        """
        try:
            # Create a queue for log lines
            log_queue = queue.Queue()
            
            # Log the command being executed
            cmd_str = " ".join(command)
            log_queue.put(f"Executing command: {cmd_str}")
            logger.info(f"Executing command: {cmd_str}")
            
            # Store process start time
            start_time = time.time()
            log_queue.put(f"Process started at: {datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Ensure unbuffered text output to capture logs in real time
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            
            # IMPORTANT: Always run from project root directory, not dashboard directory
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout so all logs come through one pipe
                bufsize=1,
                universal_newlines=True,
                env=env,
                cwd=str(PROJECT_ROOT)  # Set the working directory to project root
            )
            
            # Add process info to the process
            process.info = ProcessInfo(command, start_time)
            process.log_queue = log_queue
            
            # Start a thread to capture the output
            output_thread = threading.Thread(
                target=capture_output,
                args=(process, log_queue),
                daemon=True
            )
            output_thread.start()
            
            return process
        
        except Exception as e:
            error_msg = f"Error running process: {e}"
            logger.error(error_msg, exc_info=True)
            
            # Return a dummy process object with an error code
            dummy = DummyProcess(1)
            dummy.info = ProcessInfo(command, time.time())
            dummy.log_queue = queue.Queue()
            dummy.log_queue.put(f"ERROR: {error_msg}")
            return dummy
    
    def terminate_process(self, pid: int) -> bool:
        """Terminate a running process.
        
        Args:
            pid: Process ID to terminate
            
        Returns:
            True if terminated successfully, False otherwise
        """
        try:
            # Get the process
            process = psutil.Process(pid)
            
            # Try to terminate gracefully first
            process.terminate()
            
            # Wait for a moment
            try:
                process.wait(timeout=3)
                return True
            except psutil.TimeoutExpired:
                # If it didn't terminate, force kill
                process.kill()
                return True
                
        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception) as e:
            logger.error(f"Error terminating process {pid}: {e}")
            return False

def run_recipe_process(command: List[str], log_queue: queue.Queue) -> subprocess.Popen:
    """Run a recipe process and capture its output.
    
    Args:
        command: Command to run as a list of strings.
        log_queue: Queue to store output lines.
        
    Returns:
        The subprocess.Popen object representing the running process.
    """
    # Use the ProcessManager class
    manager = ProcessManager()
    process = manager.start_process(command)
    process.log_queue = log_queue
    return process

class DummyProcess:
    """A dummy process object to use when process creation fails."""
    
    def __init__(self, returncode: int):
        """Initialize the dummy process.
        
        Args:
            returncode: Return code to report.
        """
        self.returncode = returncode
        self.stdout = None
        self.stderr = None
        self.pid = None
    
    def poll(self) -> int:
        """Poll the process status.
        
        Returns:
            The return code.
        """
        return self.returncode
    
    def terminate(self) -> None:
        """Terminate the process (no-op for dummy)."""
        pass

def get_running_processes(pattern: str = "lead_recovery.cli.main run") -> List[Dict[str, Any]]:
    """Get a list of running recipe processes.
    
    Args:
        pattern: String pattern to match in the command line
        
    Returns:
        List of process information dictionaries
    """
    processes = []
    
    try:
        # Look for Python processes running our pattern
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'python' in proc.info['name'].lower() and pattern in cmdline:
                    # Extract recipe name
                    recipe_name = None
                    match = re.search(r'--recipe\s+(\w+)', cmdline)
                    if match:
                        recipe_name = match.group(1)
                    
                    # Create process info
                    process_info = {
                        'pid': proc.info['pid'],
                        'cmdline': cmdline,
                        'start_time': datetime.fromtimestamp(proc.info['create_time']).strftime('%Y-%m-%d %H:%M:%S'),
                        'runtime': time.time() - proc.info['create_time'],
                        'recipe': recipe_name
                    }
                    
                    processes.append(process_info)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
                
    except Exception as e:
        logger.error(f"Error getting running processes: {e}")
    
    return processes 

def terminate_process(pid: int) -> bool:
    """Terminate a running process.
    
    Args:
        pid: Process ID to terminate
        
    Returns:
        True if terminated successfully, False otherwise
    """
    # Use the ProcessManager class to terminate the process
    manager = ProcessManager()
    return manager.terminate_process(pid) 