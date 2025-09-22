#!/usr/bin/env python3
"""
Test script for the match_full_name function in helpers_repo.py
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.shared_functions.helpers_repo import helpers_repo

def create_test_reference_names():
    """Create a comprehensive list of reference names for testing"""
    return [
        # Exact match
        "Paolo Maldini",
        
        # Similar names with variations
        "Paolo Maldinni",  # Slight misspelling
        "Paul Maldini",    # Name variation
        "Paolo Maldini Jr", # With suffix
        "Dr. Paolo Maldini", # With title
        
        # Different order
        "Maldini Paolo",
        
        # Partial matches
        "Paolo",
        "Maldini",
        "Paolo Roberto",
        "Roberto Maldini",
        
        # Close but different names
        "Paolo Rossi",
        "Mario Maldini",
        "Paolo Baldi",
        
        # Completely different names
        "John Smith",
        "Maria Garcia",
        "Francesco Totti",
        
        # Names with extra words
        "Paolo Antonio Maldini",
        "Maldini Paolo Antonio",
        "Captain Paolo Maldini",
        
        # Edge cases
        "paolo maldini",      # lowercase
        "PAOLO MALDINI",      # uppercase
        "Paolo  Maldini",     # extra spaces
        " Paolo Maldini ",    # leading/trailing spaces
        
        # Nepali names for diversity
        "Ram Bahadur",
        "Sita Kumari",
        "Krishna Prasad Sharma",
        
        # Names with special characters
        "Paolo-Maldini",
        "Paolo.Maldini",
        "Paolo_Maldini",
    ]

def test_match_full_name():
    """Test the match_full_name function with various scenarios"""
    
    print("🧪 Testing match_full_name function")
    print("=" * 80)
    
    input_name = "Paolo Maldini"
    reference_names = create_test_reference_names()
    
    print(f"🎯 Input name: '{input_name}'")
    print(f"📝 Testing against {len(reference_names)} reference names:")
    
    # Display reference names
    for i, name in enumerate(reference_names, 1):
        print(f"   {i:2d}. {name}")
    
    print("\n" + "=" * 80)
    print("🔍 Running match_full_name function...")
    print("=" * 80)
    
    try:
        # Test the function
        result = helpers_repo._match_name_with_reference_list(input_name, reference_names)
        
        print(f"✅ Function executed successfully")
        print(f"📊 Result type: {type(result)}")
        print(f"📊 Result length: {len(result) if hasattr(result, '__len__') else 'N/A'}")
        print(f"📝 Result: {result}")
        
        return result
        
    except Exception as e:
        print(f"❌ Function failed with error: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_edge_cases():
    """Test various edge cases"""
    
    print("\n" + "=" * 80)
    print("🔬 Testing Edge Cases")
    print("=" * 80)
    
    edge_cases = [
        # Case 1: Empty input
        ("", ["Paolo Maldini", "John Smith"]),
        
        # Case 2: Empty reference list
        ("Paolo Maldini", []),
        
        # Case 3: Single word input
        ("Paolo", ["Paolo Maldini", "Paolo Rossi", "Mario Paolo"]),
        
        # Case 4: Single word references
        ("Paolo Maldini", ["Paolo", "Maldini", "John"]),
        
        # Case 5: Special characters
        ("Paolo-Maldini", ["Paolo Maldini", "Paolo_Maldini", "Paolo.Maldini"]),
        
        # Case 6: Numbers in names
        ("Paolo Maldini 3", ["Paolo Maldini", "Paolo Maldini Jr", "Paolo Maldini III"]),
        
        # Case 7: Very long names
        ("Paolo Antonio Roberto Maldini", ["Paolo Maldini", "Antonio Maldini", "Roberto Paolo"]),
    ]
    
    for i, (input_name, ref_names) in enumerate(edge_cases, 1):
        print(f"\n📋 Edge Case {i}: Input='{input_name}', References={len(ref_names)} names")
        
        try:
            result = helpers_repo._match_name_with_reference_list(input_name, ref_names)
            print(f"   ✅ Success: {result}")
        except Exception as e:
            print(f"   ❌ Error: {e}")



def main():
    """Main test function"""
    print("🧪 Comprehensive Test Suite for match_full_name")
    print("=" * 80)
    
    # Test basic functionality
    result = test_match_full_name()
    
    # Test edge cases
    test_edge_cases()
    
    
    print("\n" + "=" * 80)
    print("📋 Test Summary")
    print("=" * 80)
    
    if result is not None:
        print("✅ Basic test completed (with potential issues)")
    else:
        print("❌ Basic test failed - function has errors")
    
    print("📝 Recommendation: Fix the identified issues before using this function")

if __name__ == "__main__":
    main()

