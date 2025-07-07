import os
import time
import logging
import threading
from typing import Optional, Dict, Any
from contextlib import contextmanager
import paramiko
from paramiko import SSHClient, AutoAddPolicy
from backend.config.grm_config import SSH_TUNNEL_CONFIG

# Setup logging
logger = logging.getLogger(__name__)

class SSHTunnelManager:
    """Manages SSH tunnel connections for secure database access"""
    
    def __init__(self):
        self.config = SSH_TUNNEL_CONFIG
        self.ssh_client: Optional[SSHClient] = None
        self.transport: Optional[paramiko.Transport] = None
        self.is_connected = False
        self._lock = threading.Lock()
        
    def _setup_ssh_client(self) -> bool:
        """Setup SSH client with proper authentication"""
        try:
            self.ssh_client = SSHClient()
            self.ssh_client.set_missing_host_key_policy(AutoAddPolicy())
            
            # Determine authentication method
            if self.config['ssh_key_path'] and os.path.exists(self.config['ssh_key_path']):
                # Use SSH key authentication
                logger.info(f"Using SSH key authentication: {self.config['ssh_key_path']}")
                self.ssh_client.connect(
                    hostname=self.config['ssh_host'],
                    port=self.config['ssh_port'],
                    username=self.config['ssh_user'],
                    key_filename=self.config['ssh_key_path'],
                    timeout=30
                )
            elif self.config['ssh_password']:
                # Use password authentication
                logger.info("Using SSH password authentication")
                self.ssh_client.connect(
                    hostname=self.config['ssh_host'],
                    port=self.config['ssh_port'],
                    username=self.config['ssh_user'],
                    password=self.config['ssh_password'],
                    timeout=30
                )
            else:
                logger.error("No SSH authentication method configured")
                return False
                
            logger.info(f"SSH connection established to {self.config['ssh_host']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup SSH client: {str(e)}")
            return False
    
    def _create_tunnel(self) -> bool:
        """Create SSH tunnel for database connection"""
        try:
            if not self.ssh_client:
                if not self._setup_ssh_client():
                    return False
            
            # Create transport and tunnel
            self.transport = self.ssh_client.get_transport()
            self.transport.request_port_forward(
                '',  # bind to all interfaces
                self.config['local_bind_port'],
                'localhost',
                self.config['remote_bind_port']
            )
            
            logger.info(f"SSH tunnel created: localhost:{self.config['local_bind_port']} -> {self.config['ssh_host']}:{self.config['remote_bind_port']}")
            self.is_connected = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to create SSH tunnel: {str(e)}")
            return False
    
    def connect(self) -> bool:
        """Establish SSH tunnel connection"""
        if not self.config['enabled']:
            logger.info("SSH tunnel is disabled in configuration")
            return False
            
        with self._lock:
            if self.is_connected:
                logger.info("SSH tunnel already connected")
                return True
                
            logger.info("Establishing SSH tunnel connection...")
            return self._create_tunnel()
    
    def disconnect(self):
        """Disconnect SSH tunnel"""
        with self._lock:
            if self.transport:
                try:
                    self.transport.close()
                    logger.info("SSH tunnel transport closed")
                except Exception as e:
                    logger.error(f"Error closing SSH tunnel transport: {str(e)}")
                finally:
                    self.transport = None
            
            if self.ssh_client:
                try:
                    self.ssh_client.close()
                    logger.info("SSH client closed")
                except Exception as e:
                    logger.error(f"Error closing SSH client: {str(e)}")
                finally:
                    self.ssh_client = None
            
            self.is_connected = False
    
    def is_tunnel_active(self) -> bool:
        """Check if SSH tunnel is active"""
        if not self.is_connected or not self.transport:
            return False
        
        try:
            # Try to get tunnel status
            return self.transport.is_active()
        except Exception:
            return False
    
    def get_tunnel_info(self) -> Dict[str, Any]:
        """Get information about the current tunnel"""
        return {
            'enabled': self.config['enabled'],
            'connected': self.is_connected,
            'active': self.is_tunnel_active(),
            'ssh_host': self.config['ssh_host'],
            'ssh_port': self.config['ssh_port'],
            'local_port': self.config['local_bind_port'],
            'remote_port': self.config['remote_bind_port'],
            'username': self.config['ssh_user']
        }
    
    def test_connection(self) -> Dict[str, Any]:
        """Test SSH tunnel connection"""
        try:
            if not self.config['enabled']:
                return {
                    'status': 'disabled',
                    'message': 'SSH tunnel is disabled in configuration',
                    'success': False
                }
            
            if self.connect():
                # Test if tunnel is working by trying to connect to local port
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex(('localhost', self.config['local_bind_port']))
                sock.close()
                
                if result == 0:
                    return {
                        'status': 'success',
                        'message': 'SSH tunnel is working correctly',
                        'success': True,
                        'tunnel_info': self.get_tunnel_info()
                    }
                else:
                    return {
                        'status': 'error',
                        'message': 'SSH tunnel created but local port is not accessible',
                        'success': False
                    }
            else:
                return {
                    'status': 'error',
                    'message': 'Failed to establish SSH tunnel',
                    'success': False
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'message': f'SSH tunnel test failed: {str(e)}',
                'success': False
            }

@contextmanager
def ssh_tunnel_context():
    """Context manager for SSH tunnel operations"""
    tunnel_manager = SSHTunnelManager()
    try:
        if tunnel_manager.connect():
            logger.info("SSH tunnel context established")
            yield tunnel_manager
        else:
            logger.error("Failed to establish SSH tunnel context")
            yield None
    finally:
        tunnel_manager.disconnect()
        logger.info("SSH tunnel context closed")

# Global tunnel manager instance
_global_tunnel_manager: Optional[SSHTunnelManager] = None

def get_global_tunnel_manager() -> SSHTunnelManager:
    """Get or create global SSH tunnel manager"""
    global _global_tunnel_manager
    if _global_tunnel_manager is None:
        _global_tunnel_manager = SSHTunnelManager()
    return _global_tunnel_manager

def initialize_ssh_tunnel() -> bool:
    """Initialize SSH tunnel if enabled"""
    if not SSH_TUNNEL_CONFIG['enabled']:
        logger.info("SSH tunnel is disabled, skipping initialization")
        return True
    
    tunnel_manager = get_global_tunnel_manager()
    return tunnel_manager.connect()

def cleanup_ssh_tunnel():
    """Cleanup SSH tunnel resources"""
    global _global_tunnel_manager
    if _global_tunnel_manager:
        _global_tunnel_manager.disconnect()
        _global_tunnel_manager = None

if __name__ == "__main__":
    # Test SSH tunnel functionality
    print("=== SSH Tunnel Test ===")
    
    tunnel_manager = SSHTunnelManager()
    
    print("Configuration:")
    config_summary = tunnel_manager.get_tunnel_info()
    for key, value in config_summary.items():
        print(f"  {key}: {value}")
    
    print("\nConnection Test:")
    test_result = tunnel_manager.test_connection()
    print(f"  Status: {test_result['status']}")
    print(f"  Message: {test_result['message']}")
    print(f"  Success: {test_result['success']}")
    
    if test_result['success']:
        print("\nTunnel Info:")
        tunnel_info = test_result.get('tunnel_info', {})
        for key, value in tunnel_info.items():
            print(f"  {key}: {value}")
    
    tunnel_manager.disconnect() 