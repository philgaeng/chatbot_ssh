#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

"""
Setup script for database encryption using pgcrypto
"""

import os
import secrets
from .base_manager import BaseDatabaseManager

def enable_pgcrypto_extension():
    """Enable the pgcrypto extension in PostgreSQL"""
    try:
        manager = BaseDatabaseManager()
        with manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
                conn.commit()
                print("✅ pgcrypto extension enabled successfully")
                return True
    except Exception as e:
        print(f"❌ Error enabling pgcrypto extension: {str(e)}")
        return False

def generate_encryption_key():
    """Generate a secure encryption key"""
    key = secrets.token_urlsafe(32)
    print(f"🔑 Generated encryption key: {key}")
    print("\n📝 Add this to your environment variables:")
    print(f"export DB_ENCRYPTION_KEY='{key}'")
    return key

def test_encryption():
    """Test encryption/decryption functionality"""
    try:
        from .complainant_manager import ComplainantDbManager
        
        # Set a test key
        os.environ['DB_ENCRYPTION_KEY'] = 'test_key_for_validation'
        
        manager = ComplainantDbManager()
        
        # Test data
        test_data = {
            'complainant_full_name': 'John Doe',
            'complainant_phone': '+977-1234567890',
            'complainant_email': 'john.doe@example.com',
            'complainant_address': '123 Main Street, Kathmandu'
        }
        
        # Test encryption
        encrypted = manager._encrypt_complainant_data(test_data)
        print("✅ Encryption test passed")
        
        # Test decryption
        decrypted = manager._decrypt_complainant_data(encrypted)
        print("✅ Decryption test passed")
        
        # Verify data integrity
        for key in test_data:
            if test_data[key] != decrypted[key]:
                print(f"❌ Data integrity check failed for {key}")
                return False
        
        print("✅ Data integrity check passed")
        return True
        
    except Exception as e:
        print(f"❌ Encryption test failed: {str(e)}")
        return False

def main():
    """Main setup function"""
    print("🔐 Database Encryption Setup")
    print("=" * 40)
    
    # Step 1: Enable pgcrypto extension
    print("\n1. Enabling pgcrypto extension...")
    if not enable_pgcrypto_extension():
        print("❌ Failed to enable pgcrypto extension")
        return
    
    # Step 2: Generate encryption key
    print("\n2. Generating encryption key...")
    key = generate_encryption_key()
    
    # Step 3: Test encryption
    print("\n3. Testing encryption functionality...")
    if test_encryption():
        print("\n✅ Encryption setup completed successfully!")
        print("\n📋 Next steps:")
        print("1. Add the encryption key to your environment variables")
        print("2. Restart your application")
        print("3. All new user data will be encrypted automatically")
    else:
        print("\n❌ Encryption setup failed")

if __name__ == "__main__":
    main() 