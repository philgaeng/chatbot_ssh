"""
Script to run example tasks with proper setup and teardown.

This script:
1. Checks Redis connection
2. Starts workers for each priority level
3. Runs example tasks
4. Monitors task execution
5. Cleans up workers
"""

import os
import sys
import time
import signal
import subprocess
from pathlib import Path
from typing import Dict, Optional
import redis

# Add the parent directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from task_queue.config import (
    QUEUE_FOLDER,
    redis_config,
    worker_config,
    logging_config
)
from task_queue.workers import (
    start_high_priority_worker,
    start_medium_priority_worker,
    start_low_priority_worker,
    stop_all_workers,
    check_all_workers
)
from task_queue.example_tasks import run_example_tasks

def check_redis_connection() -> bool:
    """Check if Redis is running and accessible"""
    try:
        # Create Redis connection without password first
        r = redis.Redis(
            host=redis_config.host,
            port=redis_config.port,
            db=redis_config.db
        )
        
        # Try to ping without auth
        try:
            r.ping()
            print("✓ Redis connection successful (no auth required)")
            return True
        except redis.AuthenticationError:
            # If auth is required, try with password
            if redis_config.password:
                r = redis.Redis(
                    host=redis_config.host,
                    port=redis_config.port,
                    db=redis_config.db,
                    password=redis_config.password
        )
        r.ping()
                print("✓ Redis connection successful (with auth)")
        return True
            else:
                print("✗ Redis requires password but none provided")
                return False
                
    except redis.ConnectionError as e:
        print(f"✗ Redis connection failed: {str(e)}")
        return False

def start_workers() -> Dict[str, Optional[subprocess.Popen]]:
    """Start workers for all priority levels"""
    print("\nStarting workers...")
    
    workers = {
        'high': start_high_priority_worker(),
        'medium': start_medium_priority_worker(),
        'low': start_low_priority_worker()
    }
    
    # Check if all workers started successfully
    for priority, worker in workers.items():
        if worker is None:
            print(f"✗ Failed to start {priority} priority worker")
        else:
            print(f"✓ Started {priority} priority worker with PID {worker.pid}")
    
    return workers

def monitor_workers() -> None:
    """Monitor worker health"""
    print("\nMonitoring workers...")
    
    for _ in range(5):  # Monitor for 5 iterations
        health = check_all_workers()
        for priority, status in health.items():
            if status['status'] == 'running':
                print(f"✓ {priority} worker is running (CPU: {status['cpu_percent']}%, Memory: {status['memory_percent']}%)")
            else:
                print(f"✗ {priority} worker status: {status['status']} - {status.get('message', '')}")
        time.sleep(2)

def cleanup(workers: Dict[str, Optional[subprocess.Popen]]) -> None:
    """Clean up workers and temporary files"""
    print("\nCleaning up...")
    
    # Stop workers
    stop_all_workers()
    
    # Clean up any remaining temporary files
    for filename in ['audio.mp3', 'document.pdf', 'image.jpg']:
        if os.path.exists(filename):
            os.remove(filename)
            print(f"✓ Removed {filename}")

def main() -> None:
    """Main function to run example tasks"""
    workers = {}  # Initialize workers dict
    
    try:
        # Check Redis connection
        if not check_redis_connection():
            print("Please start Redis and try again")
            sys.exit(1)
        
        # Start workers
        workers = start_workers()
        if not all(workers.values()):
            print("Failed to start all workers")
            sys.exit(1)
        
        # Monitor workers
        monitor_workers()
        
        # Run example tasks
        print("\nRunning example tasks...")
        run_example_tasks()
        
        # Monitor task execution
        print("\nMonitoring task execution...")
        time.sleep(10)  # Give tasks time to execute
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"\nError: {str(e)}")
    finally:
        # Clean up
        if workers:  # Only cleanup if workers were started
        cleanup(workers)
        print("\nDone!")

if __name__ == '__main__':
    main() 