#!/usr/bin/env python3
"""
Test script for the get_office_in_charge_info function
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.shared_functions.location_validator import ContactLocationValidator

def test_get_office_in_charge_info():
    """Test the get_office_in_charge_info function with Birtamod and Jhapa"""
    
    print("🧪 Testing get_office_in_charge_info function")
    print("=" * 80)
    
    try:
        # Initialize the ContactLocationValidator
        validator = ContactLocationValidator()
        
        # Test parameters
        municipality = "birtamod"
        district = "jhapa"
        province = "province_1"  # Jhapa is in Province 1
        
        print(f"📍 Testing with:")
        print(f"   Municipality: {municipality}")
        print(f"   District: {district}")
        print(f"   Province: {province}")
        print()
        
        # Call the function
        result = validator.get_office_in_charge_info(municipality, district, province)
        
        print("📊 Result:")
        if result is None:
            print("   ❌ No office in charge info found")
        else:
            print("   ✅ Office in charge info found:")
            for key, value in result.items():
                print(f"      {key}: {value}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error testing function: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_with_different_variations():
    """Test with different variations of the input"""
    
    print("\n" + "=" * 80)
    print("🔄 Testing with different input variations")
    print("=" * 80)
    
    try:
        validator = ContactLocationValidator()
        
        test_cases = [
            {"municipality": "birtamod", "district": "jhapa", "province": "province_1"},
            {"municipality": "Birtamod", "district": "Jhapa", "province": "Province_1"},
            {"municipality": "BIRTAMOD", "district": "JHAPA", "province": "PROVINCE_1"},
            {"municipality": "Birtamod Municipality", "district": "Jhapa District", "province": "Province 1"},
            {"municipality": "birtamod municipality", "district": "jhapa district", "province": "province 1"},
        ]
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n📋 Test Case {i}:")
            print(f"   Municipality: '{test_case['municipality']}'")
            print(f"   District: '{test_case['district']}'")
            print(f"   Province: '{test_case['province']}'")
            
            result = validator.get_office_in_charge_info(
                test_case['municipality'], 
                test_case['district'], 
                test_case['province']
            )
            
            if result is None:
                print("   ❌ No result found")
            else:
                print("   ✅ Result found:")
                print(f"      Name: {result.get('name', 'N/A')}")
                print(f"      Phone: {result.get('phone_number', 'N/A')}")
                print(f"      Address: {result.get('address', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Error in variation testing: {e}")
        import traceback
        traceback.print_exc()

def check_data_file():
    """Check if the office in charge data file exists and examine its structure"""
    
    print("\n" + "=" * 80)
    print("📁 Checking office in charge data file")
    print("=" * 80)
    
    try:
        import pandas as pd
        validator = ContactLocationValidator()
        
        # Check if file exists
        if not os.path.exists(validator.json_path_office_in_charge):
            print(f"❌ File not found: {validator.json_path_office_in_charge}")
            return
        
        print(f"✅ File found: {validator.json_path_office_in_charge}")
        
        # Load and examine the data
        office_in_charge = pd.read_csv(validator.json_path_office_in_charge)
        print(f"📊 Data shape: {office_in_charge.shape}")
        print(f"📋 Columns: {list(office_in_charge.columns)}")
        
        # Show first few rows
        print("\n📄 First 5 rows:")
        print(office_in_charge.head())
        
        # Check for Birtamod specifically
        print("\n🔍 Searching for Birtamod:")
        birtamod_data = office_in_charge[office_in_charge['municipality'].str.contains('birtamod', case=False, na=False)]
        if not birtamod_data.empty:
            print("✅ Found Birtamod data:")
            print(birtamod_data)
        else:
            print("❌ No Birtamod data found")
            
        # Check for Jhapa specifically
        print("\n🔍 Searching for Jhapa:")
        jhapa_data = office_in_charge[office_in_charge['district'].str.contains('jhapa', case=False, na=False)]
        if not jhapa_data.empty:
            print("✅ Found Jhapa data:")
            print(jhapa_data)
        else:
            print("❌ No Jhapa data found")
        
    except Exception as e:
        print(f"❌ Error checking data file: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main test function"""
    print("🧪 Comprehensive Test Suite for get_office_in_charge_info")
    print("=" * 80)
    
    # Check data file first
    check_data_file()
    
    # Test the main function
    result = test_get_office_in_charge_info()
    
    # Test with different variations
    test_with_different_variations()
    
    print("\n" + "=" * 80)
    print("📋 Test Summary")
    print("=" * 80)
    
    if result is not None:
        print("✅ Main test completed successfully")
    else:
        print("❌ Main test failed - no result found")
    
    print("📝 Note: Check the data file structure and content for debugging")

if __name__ == "__main__":
    main()
