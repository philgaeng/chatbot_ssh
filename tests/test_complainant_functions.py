#!/usr/bin/env python3
"""
Test script for complainant manager functions
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.services.database_services.postgres_services import db_manager

def test_get_all_full_names_query():
    """Test the get_all_full_names_query function"""
    print("=" * 60)
    print("Testing get_all_full_names_query()...")
    print("=" * 60)
    
    try:
        encrypted_names = db_manager.complainant.get_all_full_names_query()
        print(f"✅ Function executed successfully")
        print(f"📊 Number of encrypted names retrieved: {len(encrypted_names)}")
        
        if encrypted_names:
            print(f"📝 First few encrypted names:")
            for i, name in enumerate(encrypted_names[:3]):
                print(f"   {i+1}. {name[:50]}{'...' if len(name) > 50 else ''}")
        else:
            print("⚠️  No names found in database")
            
        return encrypted_names
        
    except Exception as e:
        print(f"❌ Error in get_all_full_names_query: {e}")
        return []

def test_get_all_full_names():
    """Test the get_all_full_names function"""
    print("\n" + "=" * 60)
    print("Testing get_all_full_names()...")
    print("=" * 60)
    
    try:
        decrypted_names = db_manager.complainant.get_all_full_names()
        print(f"✅ Function executed successfully")
        print(f"📊 Number of decrypted names retrieved: {len(decrypted_names)}")
        
        if decrypted_names:
            print(f"📝 First few decrypted names:")
            for i, name in enumerate(decrypted_names[:5]):
                print(f"   {i+1}. {name}")
        else:
            print("⚠️  No names found or decryption failed")
            
        return decrypted_names
        
    except Exception as e:
        print(f"❌ Error in get_all_full_names: {e}")
        return []

def compare_results(encrypted_names, decrypted_names):
    """Compare the results of both functions"""
    print("\n" + "=" * 60)
    print("Comparing Results...")
    print("=" * 60)
    
    print(f"📊 Encrypted names count: {len(encrypted_names)}")
    print(f"📊 Decrypted names count: {len(decrypted_names)}")
    
    if len(encrypted_names) == len(decrypted_names):
        print("✅ Counts match - good!")
    else:
        print("⚠️  Counts don't match - potential issue")
    
    # Check for any None values in decrypted names
    none_count = sum(1 for name in decrypted_names if name is None)
    if none_count > 0:
        print(f"⚠️  Found {none_count} None values in decrypted names")
    else:
        print("✅ No None values found in decrypted names")
    
    # Check for empty strings
    empty_count = sum(1 for name in decrypted_names if name == "")
    if empty_count > 0:
        print(f"⚠️  Found {empty_count} empty strings in decrypted names")
    else:
        print("✅ No empty strings found in decrypted names")

def main():
    """Main test function"""
    print("🧪 Testing Complainant Manager Functions")
    print("=" * 60)
    
    try:
        # Test both functions
        encrypted_names = test_get_all_full_names_query()
        decrypted_names = test_get_all_full_names()
        
        # Compare results
        compare_results(encrypted_names, decrypted_names)
        
        print("\n" + "=" * 60)
        print("✅ Test completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

