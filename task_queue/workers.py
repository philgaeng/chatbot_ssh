"""
Worker management utilities for the queue system.
"""

import os
import sys
import time
import signal
import subprocess
import psutil
from typing import Optional, Dict, Any, List
from pathlib import Path
from .config import (
    celery_app,
    QUEUE_HIGH,
    QUEUE_MEDIUM,
    QUEUE_LOW,
    worker_config,
    logging_config,
    directory_config
)

# Create logs directory
LOG_DIR = Path(logging_config.dir)
LOG_DIR.mkdir(exist_ok=True)

def get_worker_command(queue: str, worker_name: str) -> List[str]:
    """
    Get the command to start a worker
    
    Args:
        queue: Queue name
        worker_name: Worker name
        
    Returns:
        List of command arguments
    """
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Create logs directory if it doesn't exist
    log_dir = script_dir / 'logs'
    log_dir.mkdir(exist_ok=True)
    
    return [
        'python',
        '-m',
        'celery',
        '-A', 'task_queue.config.celery_app',
        'worker',
        '-Q', queue,
        '-n', f'{worker_name}@%h',
        '-l', worker_config.log_level,
        '--concurrency', str(worker_config.concurrency),
        '--max-tasks-per-child', str(worker_config.max_tasks_per_child),
        '--prefetch-multiplier', str(worker_config.prefetch_multiplier),
        '--logfile', str(log_dir / worker_config.log_file),
        '--pidfile', str(log_dir / f'{worker_name}.pid')
    ]

def start_worker(queue: str, worker_name: str) -> Optional[subprocess.Popen]:
    """
    Start a worker process
    
    Args:
        queue: Queue name
        worker_name: Worker name
        
    Returns:
        Process object if successful, None otherwise
    """
    try:
        # Check if worker is already running
        script_dir = Path(__file__).parent
        log_dir = script_dir / 'logs'
        pid_file = log_dir / f'{worker_name}.pid'
        
        if pid_file.exists():
            with open(pid_file) as f:
                pid = int(f.read().strip())
                if psutil.pid_exists(pid):
                    print(f"Worker {worker_name} is already running with PID {pid}")
                    return None
        
        # Set PYTHONPATH
        project_root = script_dir.parent
        env = os.environ.copy()
        env['PYTHONPATH'] = f"{project_root}:{env.get('PYTHONPATH', '')}"
        
        # Start worker
        cmd = get_worker_command(queue, worker_name)
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid,
            env=env
        )
        
        # Wait for worker to start
        time.sleep(2)
        if process.poll() is None:
            print(f"Started {worker_name} worker with PID {process.pid}")
            return process
        else:
            stdout, stderr = process.communicate()
            print(f"Failed to start {worker_name} worker")
            print(f"STDOUT: {stdout.decode()}")
            print(f"STDERR: {stderr.decode()}")
            return None
            
    except Exception as e:
        print(f"Error starting {worker_name} worker: {str(e)}")
        return None

def stop_worker(worker_name: str) -> bool:
    """
    Stop a worker process
    
    Args:
        worker_name: Worker name
        
    Returns:
        True if successful, False otherwise
    """
    try:
        pid_file = LOG_DIR / f'{worker_name}.pid'
        if not pid_file.exists():
            print(f"No PID file found for {worker_name}")
            return False
            
        with open(pid_file) as f:
            pid = int(f.read().strip())
            
        if not psutil.pid_exists(pid):
            print(f"Worker {worker_name} is not running")
            return True
            
        # Send SIGTERM to process group
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        
        # Wait for process to terminate
        for _ in range(10):
            if not psutil.pid_exists(pid):
                print(f"Stopped {worker_name} worker")
                return True
            time.sleep(1)
            
        # Force kill if still running
        if psutil.pid_exists(pid):
            os.killpg(os.getpgid(pid), signal.SIGKILL)
            print(f"Force killed {worker_name} worker")
            
        return True
        
    except Exception as e:
        print(f"Error stopping {worker_name} worker: {str(e)}")
        return False

def check_worker_health(worker_name: str) -> Dict[str, Any]:
    """
    Check worker health
    
    Args:
        worker_name: Worker name
        
    Returns:
        Dictionary with health information
    """
    try:
        pid_file = LOG_DIR / f'{worker_name}.pid'
        if not pid_file.exists():
            return {
                'status': 'not_running',
                'message': 'No PID file found'
            }
            
        with open(pid_file) as f:
            pid = int(f.read().strip())
            
        if not psutil.pid_exists(pid):
            return {
                'status': 'not_running',
                'message': 'Process not found'
            }
            
        process = psutil.Process(pid)
        return {
            'status': 'running',
            'pid': pid,
            'cpu_percent': process.cpu_percent(),
            'memory_percent': process.memory_percent(),
            'uptime': time.time() - process.create_time()
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }

def start_high_priority_worker() -> Optional[subprocess.Popen]:
    """
    Start a worker for high priority tasks
    """
    return start_worker(QUEUE_HIGH, 'high_priority')

def start_medium_priority_worker() -> Optional[subprocess.Popen]:
    """
    Start a worker for medium priority tasks
    """
    return start_worker(QUEUE_MEDIUM, 'medium_priority')

def start_low_priority_worker() -> Optional[subprocess.Popen]:
    """
    Start a worker for low priority tasks
    """
    return start_worker(QUEUE_LOW, 'low_priority')

def start_all_workers() -> Dict[str, Optional[subprocess.Popen]]:
    """
    Start workers for all priority levels
    
    Returns:
        Dictionary mapping worker names to process objects
    """
    return {
        'high_priority': start_high_priority_worker(),
        'medium_priority': start_medium_priority_worker(),
        'low_priority': start_low_priority_worker()
    }

def stop_all_workers() -> Dict[str, bool]:
    """
    Stop all workers
    
    Returns:
        Dictionary mapping worker names to success status
    """
    return {
        'high_priority': stop_worker('high_priority'),
        'medium_priority': stop_worker('medium_priority'),
        'low_priority': stop_worker('low_priority')
    }

def check_all_workers() -> Dict[str, Dict[str, Any]]:
    """
    Check health of all workers
    
    Returns:
        Dictionary mapping worker names to health information
    """
    return {
        'high_priority': check_worker_health('high_priority'),
        'medium_priority': check_worker_health('medium_priority'),
        'low_priority': check_worker_health('low_priority')
    }

def start_flower() -> Optional[subprocess.Popen]:
    """
    Start Flower monitoring
    """
    try:
        cmd = [
            'celery',
            '-A', 'task_queue.config.celery_app',
            'flower',
            '--port=5555',
            '--logfile', str(LOG_DIR / 'flower.log'),
            '--pidfile', str(LOG_DIR / 'flower.pid')
        ]
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )
        
        # Wait for Flower to start
        time.sleep(2)
        if process.poll() is None:
            print("Started Flower monitoring")
            return process
        else:
            print("Failed to start Flower monitoring")
            return None
            
    except Exception as e:
        print(f"Error starting Flower monitoring: {str(e)}")
        return None 