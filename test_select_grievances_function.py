#!/usr/bin/env python3
"""
Test script for the select_grievances_from_full_name_list function in form_status_check.py
"""

import sys
import os
from datetime import datetime
from typing import List, Dict, Any
from unittest.mock import Mock, MagicMock

# Add the project root to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))

# Import the class we want to test
from rasa_chatbot.actions.form_status_check import ValidateFormStatusCheck

class MockHelpers:
    """Mock helpers class for testing"""
    def __init__(self):
        pass
    
    def match_full_name(self, input_name: str, reference_name: str) -> bool:
        """Mock implementation of match_full_name for testing"""
        # Simple exact match for testing
        # In real implementation, this would be fuzzy matching
        return input_name.lower().strip() == reference_name.lower().strip()

class MockDispatcher:
    """Mock dispatcher for testing"""
    def __init__(self):
        pass

def create_sample_grievances() -> List[Dict[str, Any]]:
    """Create sample grievance data for testing"""
    return [
        {
            "grievance_id": "GRIE-001",
            "complainant_name": "John Smith",
            "status": "OPEN",
            "grievance_creation_date": datetime(2024, 1, 15),
            "description": "First grievance"
        },
        {
            "grievance_id": "GRIE-002", 
            "complainant_name": "John Smith",
            "status": "IN_PROGRESS",
            "grievance_creation_date": datetime(2024, 1, 20),
            "description": "Second grievance"
        },
        {
            "grievance_id": "GRIE-003",
            "complainant_name": "John Smith", 
            "status": "CLOSED",
            "grievance_creation_date": datetime(2024, 1, 10),
            "description": "Third grievance (closed)"
        },
        {
            "grievance_id": "GRIE-004",
            "complainant_name": "Jane Doe",
            "status": "OPEN", 
            "grievance_creation_date": datetime(2024, 1, 25),
            "description": "Different person"
        },
        {
            "grievance_id": "GRIE-005",
            "complainant_name": "John Smith",
            "status": "CLOSED",
            "grievance_creation_date": datetime(2024, 1, 5),
            "description": "Another closed grievance"
        },
        {
            "grievance_id": "GRIE-006",
            "complainant_name": "john smith",  # Different case
            "status": "PENDING",
            "grievance_creation_date": datetime(2024, 1, 30),
            "description": "Case insensitive test"
        }
    ]

def create_test_instance() -> ValidateFormStatusCheck:
    """Create a test instance of ValidateFormStatusCheck"""
    instance = ValidateFormStatusCheck()
    
    # Mock the helpers
    instance.helpers = MockHelpers()
    
    # Mock the match_full_name method (this seems to be missing from the class)
    def mock_match_full_name(input_name: str, reference_name: str) -> bool:
        return instance.helpers.match_full_name(input_name, reference_name)
    
    instance.match_full_name = mock_match_full_name
    
    return instance

def test_select_grievances_basic_functionality():
    """Test basic functionality of select_grievances_from_full_name_list"""
    
    print("🧪 Testing Basic Functionality")
    print("=" * 80)
    
    instance = create_test_instance()
    dispatcher = MockDispatcher()
    sample_grievances = create_sample_grievances()
    
    # Test case 1: Exact match with multiple grievances
    print("\n📋 Test Case 1: Exact match with multiple grievances")
    input_name = "John Smith"
    result = instance.select_grievances_from_full_name_list(
        input_name, sample_grievances, dispatcher
    )
    
    print(f"   Input: '{input_name}'")
    print(f"   Expected: 5 grievances (4 non-closed, 1 closed)")
    print(f"   Result: {len(result)} grievances")
    
    # Verify we got the right grievances
    john_smith_grievances = [g for g in sample_grievances if g["complainant_name"].lower() == "john smith"]
    print(f"   John Smith grievances in sample: {len(john_smith_grievances)}")
    
    # Check sorting: non-closed first, then closed, both sorted by date (newest first)
    non_closed = [g for g in result if g["status"] not in ["CLOSED"]]
    closed = [g for g in result if g["status"] in ["CLOSED"]]
    
    print(f"   Non-closed grievances: {len(non_closed)}")
    print(f"   Closed grievances: {len(closed)}")
    
    # Verify order within non-closed (newest first)
    if len(non_closed) > 1:
        for i in range(len(non_closed) - 1):
            current_date = non_closed[i]["grievance_creation_date"]
            next_date = non_closed[i + 1]["grievance_creation_date"]
            if current_date < next_date:
                print(f"   ❌ Sorting error: {current_date} should come after {next_date}")
                return False
    
    print(f"   ✅ Non-closed grievances are sorted correctly (newest first)")
    
    # Verify order within closed (newest first)
    if len(closed) > 1:
        for i in range(len(closed) - 1):
            current_date = closed[i]["grievance_creation_date"]
            next_date = closed[i + 1]["grievance_creation_date"]
            if current_date < next_date:
                print(f"   ❌ Sorting error: {current_date} should come after {next_date}")
                return False
    
    print(f"   ✅ Closed grievances are sorted correctly (newest first)")
    
    return True

def test_select_grievances_edge_cases():
    """Test edge cases for select_grievances_from_full_name_list"""
    
    print("\n🧪 Testing Edge Cases")
    print("=" * 80)
    
    instance = create_test_instance()
    dispatcher = MockDispatcher()
    sample_grievances = create_sample_grievances()
    
    # Test case 1: No matches
    print("\n📋 Test Case 1: No matches")
    input_name = "Non Existent Person"
    result = instance.select_grievances_from_full_name_list(
        input_name, sample_grievances, dispatcher
    )
    
    print(f"   Input: '{input_name}'")
    print(f"   Expected: Empty list")
    print(f"   Result: {result}")
    
    if len(result) == 0:
        print("   ✅ Correctly returned empty list")
    else:
        print("   ❌ Should return empty list for no matches")
        return False
    
    # Test case 2: Empty grievance list
    print("\n📋 Test Case 2: Empty grievance list")
    input_name = "John Smith"
    result = instance.select_grievances_from_full_name_list(
        input_name, [], dispatcher
    )
    
    print(f"   Input: '{input_name}'")
    print(f"   Expected: Empty list")
    print(f"   Result: {result}")
    
    if len(result) == 0:
        print("   ✅ Correctly handled empty input list")
    else:
        print("   ❌ Should return empty list for empty input")
        return False
    
    # Test case 3: Single match
    print("\n📋 Test Case 3: Single match")
    input_name = "Jane Doe"
    result = instance.select_grievances_from_full_name_list(
        input_name, sample_grievances, dispatcher
    )
    
    print(f"   Input: '{input_name}'")
    print(f"   Expected: 1 grievance")
    print(f"   Result: {len(result)} grievances")
    
    if len(result) == 1 and result[0]["complainant_name"] == "Jane Doe":
        print("   ✅ Correctly found single match")
    else:
        print("   ❌ Should find exactly one Jane Doe grievance")
        return False
    
    # Test case 4: Case insensitive matching
    print("\n📋 Test Case 4: Case insensitive matching")
    input_name = "JOHN SMITH"
    result = instance.select_grievances_from_full_name_list(
        input_name, sample_grievances, dispatcher
    )
    
    print(f"   Input: '{input_name}' (uppercase)")
    print(f"   Expected: 5 grievances")
    print(f"   Result: {len(result)} grievances")
    
    if len(result) == 5:
        print("   ✅ Correctly handled case insensitive matching")
    else:
        print("   ❌ Should find all John Smith grievances regardless of case")
        return False
    
    return True

def test_sorting_logic():
    """Test the sorting logic more thoroughly"""
    
    print("\n🧪 Testing Sorting Logic")
    print("=" * 80)
    
    instance = create_test_instance()
    dispatcher = MockDispatcher()
    
    # Create grievances with specific dates for testing
    test_grievances = [
        {
            "grievance_id": "A",
            "complainant_name": "Test User",
            "status": "CLOSED",
            "grievance_creation_date": datetime(2024, 1, 1),
            "description": "Oldest closed"
        },
        {
            "grievance_id": "B", 
            "complainant_name": "Test User",
            "status": "OPEN",
            "grievance_creation_date": datetime(2024, 1, 15),
            "description": "Middle open"
        },
        {
            "grievance_id": "C",
            "complainant_name": "Test User", 
            "status": "CLOSED",
            "grievance_creation_date": datetime(2024, 1, 20),
            "description": "Newest closed"
        },
        {
            "grievance_id": "D",
            "complainant_name": "Test User",
            "status": "IN_PROGRESS",
            "grievance_creation_date": datetime(2024, 1, 10),
            "description": "Oldest open"
        },
        {
            "grievance_id": "E",
            "complainant_name": "Test User",
            "status": "PENDING",
            "grievance_creation_date": datetime(2024, 1, 25),
            "description": "Newest open"
        }
    ]
    
    result = instance.select_grievances_from_full_name_list(
        "Test User", test_grievances, dispatcher
    )
    
    print(f"   Input: 5 grievances with mixed statuses and dates")
    print(f"   Result: {len(result)} grievances")
    
    # Expected order: non-closed first (newest to oldest), then closed (newest to oldest)
    # E (PENDING, 2024-01-25), B (OPEN, 2024-01-15), D (IN_PROGRESS, 2024-01-10), C (CLOSED, 2024-01-20), A (CLOSED, 2024-01-01)
    expected_order = ["E", "B", "D", "C", "A"]
    actual_order = [g["grievance_id"] for g in result]
    
    print(f"   Expected order: {expected_order}")
    print(f"   Actual order: {actual_order}")
    
    if actual_order == expected_order:
        print("   ✅ Sorting logic is correct")
        return True
    else:
        print("   ❌ Sorting logic is incorrect")
        return False

def test_function_issues():
    """Test for issues in the current implementation"""
    
    print("\n🧪 Testing for Implementation Issues")
    print("=" * 80)
    
    instance = create_test_instance()
    dispatcher = MockDispatcher()
    sample_grievances = create_sample_grievances()
    
    # Test the actual function call
    try:
        result = instance.select_grievances_from_full_name_list(
            "John Smith", sample_grievances, dispatcher
        )
        print("   ✅ Function executes without errors")
        
        # Check return type
        if isinstance(result, list):
            print("   ✅ Function returns a list")
        else:
            print(f"   ❌ Function should return a list, got {type(result)}")
            return False
            
    except Exception as e:
        print(f"   ❌ Function failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def main():
    """Main test function"""
    print("🧪 Comprehensive Test Suite for select_grievances_from_full_name_list")
    print("=" * 80)
    
    all_tests_passed = True
    
    # Run all tests
    tests = [
        test_select_grievances_basic_functionality,
        test_select_grievances_edge_cases, 
        test_sorting_logic,
        test_function_issues
    ]
    
    for test_func in tests:
        try:
            result = test_func()
            if not result:
                all_tests_passed = False
        except Exception as e:
            print(f"❌ Test {test_func.__name__} failed with error: {e}")
            import traceback
            traceback.print_exc()
            all_tests_passed = False
    
    # Summary
    print("\n" + "=" * 80)
    print("📋 Test Summary")
    print("=" * 80)
    
    if all_tests_passed:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed - check the output above")
    
    print("\n📝 Notes:")
    print("   - This test uses a mock implementation of match_full_name")
    print("   - In production, you should use the actual fuzzy matching logic")
    print("   - The function appears to have the correct sorting logic")
    print("   - Make sure the match_full_name method is properly implemented in the class")

if __name__ == "__main__":
    main()
