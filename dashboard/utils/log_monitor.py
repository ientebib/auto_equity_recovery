"""
Log Monitor Module

Utilities for monitoring log output.
"""
import logging
import queue
import subprocess
import threading
import time
from typing import List

logger = logging.getLogger(__name__)

MAX_LOG_LINES = 1000  # Limit the number of log lines to prevent WebSocket overload
MAX_LOG_CHUNK = 100   # Maximum number of lines to process at once

def capture_output(process: subprocess.Popen, log_queue: queue.Queue) -> None:
    """
    Capture output from a subprocess and add it to a queue.
    
    Args:
        process: The subprocess to capture output from
        log_queue: Queue to add output lines to
    """
    try:
        # Make sure we have a stdout to read from
        if process.stdout is None:
            log_queue.put(f"ERROR: No stdout available for process {process.pid}")
            return
            
        # Read and queue output lines
        for line in iter(process.stdout.readline, ''):
            if not line:  # Empty line means process is done
                break
                
            # Add to the queue, with overflow protection
            try:
                # Don't let the queue get too large (which could cause memory issues)
                if log_queue.qsize() > MAX_LOG_LINES:
                    # Remove oldest items if queue gets too large
                    try:
                        for _ in range(MAX_LOG_CHUNK):
                            log_queue.get_nowait()
                            log_queue.task_done()
                    except queue.Empty:
                        pass
                        
                log_queue.put(line.rstrip())
            except Exception as e:
                # Don't crash if queue operations fail
                logger.error(f"Error adding to log queue: {e}")
                
        # Process is done, add a termination message
        if process.poll() is not None:
            exit_code = process.returncode
            log_queue.put(f"Process exited with code: {exit_code}")
            
    except Exception as e:
        # Log any errors but don't crash
        error_msg = f"Error capturing process output: {e}"
        logger.error(error_msg)
        try:
            log_queue.put(f"ERROR: {error_msg}")
        except Exception:
            pass

class LogMonitor:
    """
    Monitor for capturing and streaming log output.
    """
    
    def __init__(self, logfile: str, callback=None):
        """
        Initialize the log monitor.
        
        Args:
            logfile: Path to the log file to monitor
            callback: Optional callback function to call with new log lines
        """
        self.logfile = logfile
        self.callback = callback
        self.running = False
        self.thread = None
        self.log_lines = []
        
    def start(self):
        """Start monitoring the log file."""
        if self.thread and self.thread.is_alive():
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._monitor_log, daemon=True)
        self.thread.start()
        
    def stop(self):
        """Stop monitoring the log file."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
            
    def _monitor_log(self):
        """Monitor the log file for new lines."""
        try:
            with open(self.logfile, 'r') as f:
                # Seek to the end of the file
                f.seek(0, 2)
                
                while self.running:
                    line = f.readline()
                    if not line:
                        # No new line, sleep briefly
                        time.sleep(0.1)
                        continue
                        
                    # Got a new line
                    line = line.rstrip()
                    self.log_lines.append(line)
                    
                    # Trim log lines if they get too long
                    if len(self.log_lines) > MAX_LOG_LINES:
                        self.log_lines = self.log_lines[-MAX_LOG_LINES:]
                        
                    # Call callback if provided
                    if self.callback:
                        try:
                            self.callback(line)
                        except Exception as e:
                            logger.error(f"Error in log callback: {e}")
        except Exception as e:
            logger.error(f"Error monitoring log file: {e}")
            
    def get_logs(self) -> List[str]:
        """Get all captured log lines.
        
        Returns:
            List of log lines
        """
        return self.log_lines 