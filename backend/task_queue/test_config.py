"""
Test configuration for the Nepal Chatbot Queue System.

This module provides test configurations that don't require actual services.
"""

from typing import Dict, Any
import os

class TestRedisConfig:
    """Mock Redis configuration for testing"""
    def __init__(self):
        self.host = "localhost"
        self.port = 6379
        self.db = 0
        self.password = os.getenv('REDIS_PASSWORD', 'test_password')
        self.ssl = False
        self.retry_on_timeout = True
        self.socket_timeout = 5
        self.socket_connect_timeout = 5
        self.max_connections = 10
        self.decode_responses = True

    @classmethod
    def from_env(cls) -> 'TestRedisConfig':
        """Create a test Redis configuration"""
        return cls()

# Mock configurations
redis_config = TestRedisConfig()

# Import redis_url from the correct path
from .config import redis_url

print("Environment variables:")
print(f"REDIS_PASSWORD from env: {os.getenv('REDIS_PASSWORD')}")
print("\nRedis Config:")
print(f"Host: {redis_config.host}")
print(f"Port: {redis_config.port}")
print(f"DB: {redis_config.db}")
print(f"Password: {redis_config.password}")
print(f"\nRedis URL: {redis_url}") 