#!/usr/bin/env python3
"""
Test function for get_grievance_by_complainant_phone method in GrievanceManager class.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.services.database_services.grievance_manager import GrievanceDbManager


def test_get_grievance_by_phone():
    """Test the get_grievance_by_complainant_phone method with phone number 9876543210."""
    
    print("Testing get_grievance_by_complainant_phone method...")
    print("=" * 60)
    
    try:
        # Create an instance of GrievanceDbManager
        grievance_manager = GrievanceDbManager()
        
        # Test phone number
        test_phone = "9876543210"
        
        print(f"Testing with phone number: {test_phone}")
        print(f"Phone number type: {type(test_phone)}")
        print(f"Phone number length: {len(test_phone)}")
        
        # Call the method
        print("\nCalling get_grievance_by_complainant_phone...")
        result = grievance_manager.get_grievance_by_complainant_phone(test_phone)
        
        print(f"\nResult type: {type(result)}")
        print(f"Result: {result}")
        
        if result:
            print(f"\n✅ Found {len(result)} grievance(s) for phone number {test_phone}")
            for i, grievance in enumerate(result, 1):
                print(f"\nGrievance {i}:")
                for key, value in grievance.items():
                    print(f"  {key}: {value}")
        else:
            print(f"\n❌ No grievances found for phone number {test_phone}")
            print("This could mean:")
            print("  - No grievances exist for this phone number")
            print("  - Database connection issue")
            print("  - Phone number format/hashing issue")
        
    except Exception as e:
        print(f"❌ ERROR - Exception occurred: {e}")
        print(f"Exception type: {type(e)}")
        import traceback
        print(f"Traceback:\n{traceback.format_exc()}")


def test_phone_standardization():
    """Test phone number standardization logic."""
    print("\n" + "=" * 60)
    print("Testing Phone Number Standardization")
    print("=" * 60)
    
    try:
        grievance_manager = GrievanceDbManager()
        
        test_phones = [
            "9876543210",
            "+9779876543210", 
            "977-9876543210",
            "977 9876543210",
            "(977) 9876543210",
            "09876543210"  # If it handles this format
        ]
        
        for phone in test_phones:
            print(f"\nOriginal: '{phone}'")
            try:
                # Access the private method for testing
                standardized = grievance_manager._standardize_phone_number(phone)
                print(f"Standardized: '{standardized}'")
                
                # Show what the hash would be
                hashed = grievance_manager._hash_value(standardized) if grievance_manager.encryption_key else standardized
                print(f"Hash/Search value: '{hashed}'")
                
            except Exception as e:
                print(f"Error standardizing '{phone}': {e}")
                
    except Exception as e:
        print(f"❌ ERROR setting up phone standardization test: {e}")


def test_database_connection():
    """Test if database connection is working."""
    print("\n" + "=" * 60)
    print("Testing Database Connection")
    print("=" * 60)
    
    try:
        grievance_manager = GrievanceDbManager()
        
        # Try a simple query to test connection
        test_query = "SELECT 1 as test_value"
        result = grievance_manager.execute_query(test_query, (), "connection_test")
        
        if result:
            print("✅ Database connection successful")
            print(f"Test query result: {result}")
        else:
            print("❌ Database connection failed - no result")
            
    except Exception as e:
        print(f"❌ Database connection error: {e}")


if __name__ == "__main__":
    # Test database connection first
    test_database_connection()
    
    # Test phone standardization
    test_phone_standardization()
    
    # Run the main phone search test
    test_get_grievance_by_phone()
    
    print(f"\n{'='*60}")
    print("Test execution completed!")
