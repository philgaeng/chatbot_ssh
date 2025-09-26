"""
Test runner for the Nepal Chatbot Queue System.

This script sets up the test environment and runs the test suite.
"""

import os
import sys

# Set environment variables BEFORE any other imports
os.environ['REDIS_HOST'] = 'localhost'
os.environ['REDIS_PORT'] = '6379'
os.environ['REDIS_DB'] = '0'
os.environ['REDIS_PASSWORD'] = 'test_password'
os.environ['UPLOAD_FOLDER'] = '/tmp/uploads'
os.environ['ALLOWED_EXTENSIONS'] = 'wav,mp3,mp4'

# Now import unittest after environment is set
import unittest

def run_tests():
    """Run the test suite"""
    # Discover and run tests
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(__file__)
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)