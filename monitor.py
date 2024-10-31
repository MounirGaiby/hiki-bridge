import sys
import time
import json
import logging
from pathlib import Path
import os
import signal

# Logging configuration
logging.basicConfig(
    filename='monitor.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def log_message(message, level=logging.INFO):
    """Log messages to file and stdout"""
    if level == logging.ERROR:
        logging.error(message)
    else:
        logging.info(message)
    print(message, flush=True)

def signal_handler(signum, frame):
    """Handle termination signals gracefully"""
    log_message("Received termination signal. Cleaning up...")
    cleanup()
    sys.exit(0)

def cleanup():
    """Clean up resources on exit"""
    try:
        Path('monitor.pid').unlink(missing_ok=True)
    except Exception as e:
        log_message(f"Error during cleanup: {e}", logging.ERROR)

def main():
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Validate arguments
    if len(sys.argv) != 4:
        log_message("Usage: monitor.py <folder_path> <api_endpoint> <api_key>", logging.ERROR)
        sys.exit(1)

    # Extract arguments
    folder_path = sys.argv[1]
    api_endpoint = sys.argv[2]
    api_key = sys.argv[3]

    # Write PID to file
    try:
        with open('monitor.pid', 'w') as f:
            f.write(str(os.getpid()))
    except IOError as e:
        log_message(f"Could not write PID file: {e}", logging.ERROR)
        sys.exit(1)

    # Log startup information
    log_message("HikiBridge Monitor Started")
    log_message(f"Monitoring Folder: {folder_path}")
    log_message(f"API Endpoint: {api_endpoint}")
    log_message(f"API Key: {'*' * len(api_key)}")

    try:
        # Proof of concept monitoring loop
        iteration = 0
        while True:
            iteration += 1
            log_message(f"Monitoring iteration {iteration}")
            
            # TODO: Implement actual file monitoring logic here
            # 1. Scan folder_path
            # 2. Detect new or modified files
            # 3. Process files with API endpoint
            
            time.sleep(1)  # Check every 1 seconds
    
    except Exception as e:
        log_message(f"Unexpected error in monitor: {e}", logging.ERROR)
    
    finally:
        cleanup()

if __name__ == "__main__":
    main()