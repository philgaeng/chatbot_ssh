#!/usr/bin/env python3
"""
Server initialization script for Nepal Chatbot.
This script initializes and runs:
1. The database
2. The file server for handling uploads (shared between Rasa and accessible interface)
3. The accessible interface web app
4. The Rasa server
5. The Rasa action server
"""

import os
import sys
import logging
import threading
import time
import argparse
import subprocess
import signal
import psutil
import socket
from logging.handlers import TimedRotatingFileHandler

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

# Default log retention period (in days)
DEFAULT_LOG_RETENTION_DAYS = 90

def setup_logging(log_retention_days=DEFAULT_LOG_RETENTION_DAYS):
    """Set up logging with specified retention period"""
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(project_root, 'logs')
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
        print(f"Created logs directory: {logs_dir}")
    
    # Common log format for all loggers
    log_format = '%(asctime)s - %(levelname)s - [%(name)s] - %(message)s'
    log_formatter = logging.Formatter(log_format)
    
    # Root logger configuration (console output)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Console handler for root logger
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    root_logger.addHandler(console_handler)
    
    # Create separate logger for main script
    server_manager_logger = logging.getLogger('ServerManager')
    # Create file handler for main script
    main_log_file = os.path.join(logs_dir, 'server_manager.log')
    main_file_handler = TimedRotatingFileHandler(
        main_log_file,
        when='midnight',
        interval=1,
        backupCount=log_retention_days  # Keep logs for specified days
    )
    main_file_handler.setFormatter(log_formatter)
    server_manager_logger.addHandler(main_file_handler)
    
    # Create loggers for each component
    rasa_server_logger = logging.getLogger('RasaServer')
    rasa_action_logger = logging.getLogger('RasaActionServer')
    file_server_logger = logging.getLogger('FileServer')
    accessible_logger = logging.getLogger('AccessibleServer')
    
    # Set up file handlers for each component
    rasa_server_log_file = os.path.join(logs_dir, 'rasa_server.log')
    rasa_action_log_file = os.path.join(logs_dir, 'actions_server.log')
    file_server_log_file = os.path.join(logs_dir, 'file_server.log')
    accessible_log_file = os.path.join(logs_dir, 'accessible_server.log')
    
    # Rasa server file handler
    rasa_server_file_handler = TimedRotatingFileHandler(
        rasa_server_log_file,
        when='midnight',
        interval=1,
        backupCount=log_retention_days
    )
    rasa_server_file_handler.setFormatter(log_formatter)
    rasa_server_logger.addHandler(rasa_server_file_handler)
    
    # Rasa action server file handler
    rasa_action_file_handler = TimedRotatingFileHandler(
        rasa_action_log_file,
        when='midnight',
        interval=1,
        backupCount=log_retention_days
    )
    rasa_action_file_handler.setFormatter(log_formatter)
    rasa_action_logger.addHandler(rasa_action_file_handler)
    
    # File server file handler
    file_server_file_handler = TimedRotatingFileHandler(
        file_server_log_file,
        when='midnight',
        interval=1,
        backupCount=log_retention_days
    )
    file_server_file_handler.setFormatter(log_formatter)
    file_server_logger.addHandler(file_server_file_handler)
    
    # Accessible server file handler
    accessible_file_handler = TimedRotatingFileHandler(
        accessible_log_file,
        when='midnight',
        interval=1,
        backupCount=log_retention_days
    )
    accessible_file_handler.setFormatter(log_formatter)
    accessible_logger.addHandler(accessible_file_handler)
    
    print(f"Logging initialized with {log_retention_days} days retention")
    return (
        server_manager_logger,
        rasa_server_logger,
        rasa_action_logger,
        file_server_logger,
        accessible_logger,
        # Return handlers for Flask apps to use
        file_server_file_handler,
        accessible_file_handler
    )

# Initialize global logger variables
logger = None
rasa_server_logger = None
rasa_action_logger = None
file_server_logger = None
accessible_logger = None
file_server_file_handler = None
accessible_file_handler = None

def init_database():
    """Initialize the database"""
    logger.info("Initializing database...")
    
    try:
        # Initialize the database using the shared db_manager
        from actions_server.db_manager import db_manager
        db_manager.init_db()
        logger.info("Database initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Database initialization error: {str(e)}", exc_info=True)
        return False

def start_file_server(port=5001):
    """Start the file server for handling uploads"""
    file_server_logger.info(f"Starting file server on port {port}...")
    
    try:
        # First, ensure actions_server is imported and initialized
        from actions_server import db_manager
        
        # Import file server app
        from actions_server.file_server import app as file_server_app
        
        # Create uploads directory if it doesn't exist
        uploads_dir = os.path.join(project_root, 'uploads')
        if not os.path.exists(uploads_dir):
            os.makedirs(uploads_dir)
            file_server_logger.info(f"Created uploads directory: {uploads_dir}")
        
        # Set up logging for Flask app
        import logging as flask_logging
        flask_app_logger = flask_logging.getLogger('werkzeug')
        flask_app_logger.setLevel(flask_logging.INFO)
        flask_app_logger.addHandler(file_server_file_handler)
        
        # Start the file server
        file_server_app.run(host='0.0.0.0', port=port, use_reloader=False, debug=False)
    except Exception as e:
        file_server_logger.error(f"Error starting file server: {str(e)}", exc_info=True)

def start_accessible_app(port=5006):
    """Start the accessibility web app"""
    accessible_logger.info(f"Starting accessibility app on port {port}...")
    
    try:
        # Import the accessibility app
        from actions_server.app import app as accessibility_app
        
        # Set up logging for Flask app
        import logging as flask_logging
        flask_app_logger = flask_logging.getLogger('werkzeug')
        flask_app_logger.setLevel(flask_logging.INFO)
        flask_app_logger.addHandler(accessible_file_handler)
        
        # Start the accessibility app
        accessibility_app.run(host='0.0.0.0', port=port, use_reloader=False, debug=False)
    except Exception as e:
        accessible_logger.error(f"Error starting accessibility app: {str(e)}", exc_info=True)

def start_rasa_action_server(port=5050):
    """Start the Rasa action server"""
    rasa_action_logger.info(f"Starting Rasa action server on port {port}...")
    
    try:
        import subprocess
        
        # Check if port is available before starting
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('0.0.0.0', port))
            sock.close()
        except OSError as e:
            rasa_action_logger.error(f"Port {port} is not available for Rasa action server: {e}")
            # Try to find what's using the port
            try:
                result = subprocess.run(["lsof", "-i", f":{port}"], capture_output=True, text=True)
                if result.stdout:
                    rasa_action_logger.error(f"Port {port} is in use by:\n{result.stdout}")
                    # Try one last kill
                    subprocess.run(["fuser", "-k", f"{port}/tcp"], capture_output=True)
                    time.sleep(2)
            except Exception as e:
                rasa_action_logger.error(f"Error checking port {port}: {e}")
            return None
        
        # Start the Rasa action server with the specified port
        cmd = [
            "rasa", "run", "actions", 
            "--port", str(port),
            "--actions", "actions"
        ]
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # Log output in a separate thread
        def log_output():
            for line in process.stdout:
                rasa_action_logger.info(line.strip())
            for line in process.stderr:
                rasa_action_logger.error(line.strip())
                
        threading.Thread(target=log_output, daemon=True).start()
        
        # Give Rasa a moment to start and check if it's running
        time.sleep(5)
        if process.poll() is not None:
            rasa_action_logger.error(f"Rasa action server failed to start, exit code: {process.poll()}")
            return None
            
        rasa_action_logger.info(f"Rasa action server started on port {port}")
        return process
    except Exception as e:
        rasa_action_logger.error(f"Error starting Rasa action server: {str(e)}", exc_info=True)
        return None

def start_rasa_server(port=5005):
    """Start the main Rasa server"""
    rasa_server_logger.info(f"Starting Rasa server on port {port}...")
    
    try:
        import subprocess
        
        # Check if port is available before starting
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('0.0.0.0', port))
            sock.close()
        except OSError as e:
            rasa_server_logger.error(f"Port {port} is not available for Rasa server: {e}")
            # Try to find what's using the port
            try:
                result = subprocess.run(["lsof", "-i", f":{port}"], capture_output=True, text=True)
                if result.stdout:
                    rasa_server_logger.error(f"Port {port} is in use by:\n{result.stdout}")
                    # Try one last kill
                    subprocess.run(["fuser", "-k", f"{port}/tcp"], capture_output=True)
                    time.sleep(2)
            except Exception as e:
                rasa_server_logger.error(f"Error checking port {port}: {e}")
            return None
        
        # Start the main Rasa server
        cmd = [
            "rasa", "run", 
            "--port", str(port),
            "--enable-api",
            "--cors", "*"
        ]
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # Log output in a separate thread
        def log_output():
            for line in process.stdout:
                rasa_server_logger.info(line.strip())
            for line in process.stderr:
                rasa_server_logger.error(line.strip())
                
        threading.Thread(target=log_output, daemon=True).start()
        
        # Give Rasa a moment to start and check if it's running
        time.sleep(5)
        if process.poll() is not None:
            rasa_server_logger.error(f"Rasa server failed to start, exit code: {process.poll()}")
            return None
            
        rasa_server_logger.info(f"Rasa server started on port {port}")
        return process
    except Exception as e:
        rasa_server_logger.error(f"Error starting Rasa server: {str(e)}", exc_info=True)
        return None

def check_server(url, name, max_attempts=5):
    """Check if a server is running by making an HTTP request"""
    import requests
    
    for attempt in range(max_attempts):
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                logger.info(f"{name} is running at {url}")
                return True
        except requests.RequestException:
            pass
        
        if attempt < max_attempts - 1:
            logger.info(f"Waiting for {name} to start (attempt {attempt+1}/{max_attempts})...")
            time.sleep(2)
    
    logger.error(f"{name} failed to start after {max_attempts} attempts")
    return False

def stop_servers_on_ports(ports):
    """Stop any processes listening on the specified ports
    
    Args:
        ports (list): List of ports to check and stop processes on
    """
    logger.info(f"Checking for existing processes on ports: {ports}")
    
    for port in ports:
        try:
            # Using netstat to find processes bound to the specified port
            result = subprocess.run(
                ["lsof", "-i", f":{port}"], 
                capture_output=True, 
                text=True
            )
            
            if result.stdout:
                # Extract PIDs from the output
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:  # Skip header line
                    for line in lines[1:]:
                        parts = line.split()
                        if len(parts) > 1:
                            pid = int(parts[1])
                            try:
                                process = psutil.Process(pid)
                                process_name = process.name()
                                logger.info(f"Stopping process {process_name} (PID: {pid}) on port {port}")
                                os.kill(pid, signal.SIGTERM)
                                time.sleep(1)  # Give it a moment to shut down
                                
                                # Check if it's still running and force kill if necessary
                                if psutil.pid_exists(pid):
                                    logger.info(f"Process {pid} still running, forcing termination")
                                    os.kill(pid, signal.SIGKILL)
                                    
                                    # Wait and check again
                                    time.sleep(2)
                                    if psutil.pid_exists(pid):
                                        logger.warning(f"Process {pid} could not be terminated, trying another approach")
                                        
                                        # Try more aggressive approach if process still exists
                                        try:
                                            subprocess.run(["kill", "-9", str(pid)], check=True)
                                            time.sleep(1)
                                        except subprocess.CalledProcessError:
                                            logger.error(f"Failed to kill process {pid} with kill -9")
                            except (psutil.NoSuchProcess, ProcessLookupError):
                                logger.info(f"Process {pid} already terminated")
                            except Exception as e:
                                logger.error(f"Error stopping process {pid}: {e}")
                                
            # After attempting to kill processes, verify the port is actually free
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.bind(('0.0.0.0', port))
                sock.close()
                logger.info(f"Port {port} is now available")
            except OSError:
                logger.error(f"Port {port} is still in use after kill attempts!")
                
                # Last resort - try finding any process still using the port
                result = subprocess.run(
                    ["fuser", "-k", f"{port}/tcp"], 
                    capture_output=True, 
                    text=True
                )
                logger.info(f"Attempted fuser kill on port {port}: {result.stdout}")
                time.sleep(2)
        except Exception as e:
            logger.error(f"Error checking for processes on port {port}: {e}")

def stop_all_rasa_processes():
    """Kill all Rasa-related processes"""
    logger.info("Stopping all Rasa processes...")
    try:
        # Find all Rasa processes
        subprocess.run(["pkill", "-f", "rasa"], capture_output=True)
        time.sleep(2)
        # Force kill any remaining Rasa processes
        subprocess.run(["pkill", "-9", "-f", "rasa"], capture_output=True)
    except Exception as e:
        logger.error(f"Error stopping Rasa processes: {e}")

def main():
    """Main function to run servers"""
    parser = argparse.ArgumentParser(description='Start Nepal Chatbot servers')
    parser.add_argument('--file-server-port', type=int, default=5001, help='Port for file server')
    parser.add_argument('--accessibility-port', type=int, default=5006, help='Port for accessibility app')
    parser.add_argument('--rasa-action-port', type=int, default=5050, help='Port for Rasa action server')
    parser.add_argument('--rasa-server-port', type=int, default=5005, help='Port for main Rasa server')
    parser.add_argument('--skip-db-init', action='store_true', help='Skip database initialization')
    parser.add_argument('--file-server-only', action='store_true', help='Run only the file server')
    parser.add_argument('--accessibility-only', action='store_true', help='Run only the accessibility app')
    parser.add_argument('--rasa-action-only', action='store_true', help='Run only the Rasa action server')
    parser.add_argument('--rasa-server-only', action='store_true', help='Run only the main Rasa server')
    parser.add_argument('--all', action='store_true', help='Run all servers')
    parser.add_argument('--log-retention', type=int, default=DEFAULT_LOG_RETENTION_DAYS, 
                      help=f'Log retention period in days (default: {DEFAULT_LOG_RETENTION_DAYS})')
    
    args = parser.parse_args()
    
    # Initialize logging with specified retention
    global logger, rasa_server_logger, rasa_action_logger, file_server_logger, accessible_logger
    global file_server_file_handler, accessible_file_handler
    
    logger, rasa_server_logger, rasa_action_logger, file_server_logger, accessible_logger, \
    file_server_file_handler, accessible_file_handler = setup_logging(args.log_retention)
    
    # If no specific server is selected, show help
    if not (args.file_server_only or args.accessibility_only or args.rasa_action_only or args.rasa_server_only or args.all):
        parser.print_help()
        return
    
    # Stop all Rasa processes first to ensure clean start
    stop_all_rasa_processes()
    
    # Build list of ports that will be used
    ports_to_check = []
    if args.file_server_only or args.all:
        ports_to_check.append(args.file_server_port)
    if args.accessibility_only or args.all:
        ports_to_check.append(args.accessibility_port)
    if args.rasa_action_only or args.all:
        ports_to_check.append(args.rasa_action_port)
    if args.rasa_server_only or args.all:
        ports_to_check.append(args.rasa_server_port)
    
    # Stop any existing servers on these ports
    stop_servers_on_ports(ports_to_check)
    
    # Double-check that all ports are available before proceeding
    unavailable_ports = []
    for port in ports_to_check:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('0.0.0.0', port))
            sock.close()
        except OSError:
            unavailable_ports.append(port)
            logger.error(f"Port {port} is still not available after cleanup attempts")
    
    if unavailable_ports:
        logger.error(f"Ports {unavailable_ports} are still in use. Please stop services manually or try again later.")
        return
    
    # Initialize database unless skipped
    if not args.skip_db_init:
        if not init_database():
            logger.error("Database initialization failed, exiting")
            return
    
    processes = []
    
    # Start file server if requested
    file_server_thread = None
    if args.file_server_only or args.all:
        file_server_thread = threading.Thread(
            target=start_file_server,
            args=(args.file_server_port,),
            daemon=True
        )
        file_server_thread.start()
        logger.info(f"File server thread started with port {args.file_server_port}")
        
        # Give the file server a moment to start
        time.sleep(2)
        check_server(f"http://localhost:{args.file_server_port}", "File server")
    
    # Start Rasa action server if requested
    rasa_action_process = None
    if args.rasa_action_only or args.all:
        rasa_action_process = start_rasa_action_server(args.rasa_action_port)
        if rasa_action_process:
            processes.append(rasa_action_process)
            # Give the Rasa action server a moment to start
            time.sleep(2)
    
    # Start main Rasa server if requested
    rasa_server_process = None
    if args.rasa_server_only or args.all:
        rasa_server_process = start_rasa_server(args.rasa_server_port)
        if rasa_server_process:
            processes.append(rasa_server_process)
            # Give the Rasa server a moment to start
            time.sleep(2)
    
    # Start accessibility app if requested
    accessibility_thread = None
    if args.accessibility_only or args.all:
        # Run accessibility app in a separate thread if we're running multiple servers
        if args.all:
            accessibility_thread = threading.Thread(
                target=start_accessible_app,
                args=(args.accessibility_port,),
                daemon=True
            )
            accessibility_thread.start()
            logger.info(f"Accessibility app thread started with port {args.accessibility_port}")
            time.sleep(2)
        else:
            # Run accessibility app in the main thread if it's the only server
            start_accessible_app(args.accessibility_port)
            return
    
    # Keep the main thread alive as long as any server is running
    try:
        while True:
            if file_server_thread and not file_server_thread.is_alive():
                logger.error("File server thread has stopped")
                break
                
            if accessibility_thread and not accessibility_thread.is_alive():
                logger.error("Accessibility app thread has stopped")
                break
                
            if rasa_action_process and rasa_action_process.poll() is not None:
                logger.error("Rasa action server has stopped")
                break
                
            if rasa_server_process and rasa_server_process.poll() is not None:
                logger.error("Rasa server has stopped")
                break
                
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
        # Terminate any subprocess
        for process in processes:
            process.terminate()
    
if __name__ == "__main__":
    main() 