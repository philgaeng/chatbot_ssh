#!/usr/bin/env python3
"""
Standalone test for validate_village_input function
This test properly sets up the import paths to test the actual ContactLocationValidator class.
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path so we can import backend modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Add backend to Python path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

print(f"Project root: {project_root}")
print(f"Backend path: {backend_path}")
print(f"Python path: {sys.path[:3]}...")

try:
    # Now import the actual validator
    from shared_functions.location_validator import ContactLocationValidator
    print("✅ Successfully imported ContactLocationValidator")
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Trying alternative import path...")
    
    # Try alternative import path
    try:
        sys.path.insert(0, str(project_root / "backend"))
        from shared_functions.location_validator import ContactLocationValidator
        print("✅ Successfully imported ContactLocationValidator (alternative path)")
    except ImportError as e2:
        print(f"❌ Alternative import also failed: {e2}")
        print("Please run this script from the project root directory:")
        print("cd /home/philg/projects/nepal_chatbot")
        print("python backend/standalone_test.py")
        sys.exit(1)

def test_validate_village_input():
    """
    Test function for validate_village_input method.
    Tests various scenarios including valid matches, fuzzy matches, and invalid inputs.
    """
    
    # Initialize the validator
    validator = ContactLocationValidator()
    
    print("=" * 60)
    print("TESTING validate_village_input FUNCTION")
    print("=" * 60)
    
    # Test cases based on the CSV data
    test_cases = [
        # Valid exact matches
        {
            "input_text": "Birtamod",
            "qr_municipality": "Birtamod",
            "expected_village": "Birtamod",
            "expected_ward": "1",
            "description": "Exact match for Birtamod village in Birtamod municipality"
        },
        {
            "input_text": "Dhulabari",
            "qr_municipality": "Mechinagar",
            "expected_village": "Dhulabari",
            "expected_ward": "10",
            "description": "Exact match for Dhulabari village in Mechinagar municipality"
        },
        {
            "input_text": "Charali",
            "qr_municipality": "Mechinagar",
            "expected_village": "Charali",
            "expected_ward": "13",  # First occurrence
            "description": "Exact match for Charali village in Mechinagar municipality"
        },
        {
            "input_text": "Mechi",
            "qr_municipality": "Mechinagar",
            "expected_village": "Mechi",
            "expected_ward": "10",  # First occurrence
            "description": "Exact match for Mechi village in Mechinagar municipality"
        },
        
        # Fuzzy matches (slight variations)
        {
            "input_text": "birtamod",
            "qr_municipality": "Birtamod",
            "expected_village": "Birtamod",
            "expected_ward": "1",
            "description": "Case-insensitive match for Birtamod"
        },
        {
            "input_text": "DHULABARI",
            "qr_municipality": "Mechinagar",
            "expected_village": "Dhulabari",
            "expected_ward": "10",
            "description": "Uppercase input for Dhulabari"
        },
        {
            "input_text": "kanchan tole",
            "qr_municipality": "Mechinagar",
            "expected_village": "Kanchan Tole",
            "expected_ward": "10",
            "description": "Lowercase with space for Kanchan Tole"
        },
        
        # Additional casing variations
        {
            "input_text": "bIrTaMoD",
            "qr_municipality": "Birtamod",
            "expected_village": "Birtamod",
            "expected_ward": "1",
            "description": "Mixed case input for Birtamod"
        },
        {
            "input_text": "dhulabari",
            "qr_municipality": "Mechinagar",
            "expected_village": "Dhulabari",
            "expected_ward": "10",
            "description": "All lowercase input for Dhulabari"
        },
        {
            "input_text": "CHARALI",
            "qr_municipality": "Mechinagar",
            "expected_village": "Charali",
            "expected_ward": "13",
            "description": "All uppercase input for Charali"
        },
        {
            "input_text": "mEcHi",
            "qr_municipality": "Mechinagar",
            "expected_village": "Mechi",
            "expected_ward": "10",
            "description": "Mixed case input for Mechi"
        },
        {
            "input_text": "parijat tole",
            "qr_municipality": "Mechinagar",
            "expected_village": "Parijat Tole",
            "expected_ward": "10",
            "description": "All lowercase multi-word input for Parijat Tole"
        },
        {
            "input_text": "SHRIJANA TOLE",
            "qr_municipality": "Mechinagar",
            "expected_village": "Shrijana Tole",
            "expected_ward": "6",
            "description": "All uppercase multi-word input for Shrijana Tole"
        },
        {
            "input_text": "sHrIjAnA tOlE",
            "qr_municipality": "Mechinagar",
            "expected_village": "Shrijana Tole",
            "expected_ward": "6",
            "description": "Alternating case multi-word input for Shrijana Tole"
        },
        {
            "input_text": "kanchan TOLE",
            "qr_municipality": "Mechinagar",
            "expected_village": "Kanchan Tole",
            "expected_ward": "10",
            "description": "Mixed case multi-word input for Kanchan Tole"
        },
        {
            "input_text": "KANCHAN tole",
            "qr_municipality": "Mechinagar",
            "expected_village": "Kanchan Tole",
            "expected_ward": "10",
            "description": "Mixed case multi-word input for Kanchan Tole (reversed)"
        },
        
        # Invalid inputs (should return None, None)
        {
            "input_text": "NonExistentVillage",
            "qr_municipality": "Birtamod",
            "expected_village": None,
            "expected_ward": None,
            "description": "Non-existent village in Birtamod municipality"
        },
        {
            "input_text": "RandomVillage",
            "qr_municipality": "Mechinagar",
            "expected_village": None,
            "expected_ward": None,
            "description": "Non-existent village in Mechinagar municipality"
        },
        {
            "input_text": "",
            "qr_municipality": "Birtamod",
            "expected_village": None,
            "expected_ward": None,
            "description": "Empty input"
        },
        {
            "input_text": "   ",
            "qr_municipality": "Birtamod",
            "expected_village": None,
            "expected_ward": None,
            "description": "Whitespace-only input"
        },
        {
            "input_text": "Birtamod",
            "qr_municipality": "NonExistentMunicipality",
            "expected_village": None,
            "expected_ward": None,
            "description": "Valid village but non-existent municipality"
        },
        
        # Edge cases
        {
            "input_text": "Birtamod Municipality",
            "qr_municipality": "Birtamod",
            "expected_village": "Birtamod",
            "expected_ward": "1",
            "description": "Village name with municipality suffix"
        },
        {
            "input_text": "Parijat Tole",
            "qr_municipality": "Mechinagar",
            "expected_village": "Parijat Tole",
            "expected_ward": "10",
            "description": "Multi-word village name"
        },
        {
            "input_text": "Shrijana Tole",
            "qr_municipality": "Mechinagar",
            "expected_village": "Shrijana Tole",
            "expected_ward": "6",
            "description": "Another multi-word village name"
        },
        
        # Whitespace and formatting edge cases
        {
            "input_text": "  Birtamod  ",
            "qr_municipality": "Birtamod",
            "expected_village": "Birtamod",
            "expected_ward": "1",
            "description": "Village name with extra whitespace"
        },
        {
            "input_text": "  Dhulabari  ",
            "qr_municipality": "Mechinagar",
            "expected_village": "Dhulabari",
            "expected_ward": "10",
            "description": "Village name with extra whitespace"
        },
        {
            "input_text": "Parijat  Tole",
            "qr_municipality": "Mechinagar",
            "expected_village": "Parijat Tole",
            "expected_ward": "10",
            "description": "Multi-word with extra spaces"
        },
        {
            "input_text": "Shrijana\tTole",
            "qr_municipality": "Mechinagar",
            "expected_village": "Shrijana Tole",
            "expected_ward": "6",
            "description": "Multi-word with tab character"
        },
        
        # Common typos and variations
        {
            "input_text": "Birtamode",
            "qr_municipality": "Birtamod",
            "expected_village": "Birtamod",
            "expected_ward": "1",
            "description": "Typo: extra 'e' at the end"
        },
        {
            "input_text": "Dhulabri",
            "qr_municipality": "Mechinagar",
            "expected_village": "Dhulabari",
            "expected_ward": "10",
            "description": "Typo: missing 'a' in Dhulabari"
        },
        {
            "input_text": "Charli",
            "qr_municipality": "Mechinagar",
            "expected_village": "Charali",
            "expected_ward": "13",
            "description": "Typo: missing 'a' in Charali"
        },
        {
            "input_text": "Parijat Tole",
            "qr_municipality": "Mechinagar",
            "expected_village": "Parijat Tole",
            "expected_ward": "10",
            "description": "Correct spelling of Parijat Tole"
        },
        {
            "input_text": "Mechi",
            "qr_municipality": "Mechinagar",
            "expected_village": "Mechi",
            "expected_ward": "10",
            "description": "Short village name that's also part of municipality name"
        },
        {
            "input_text": "yekata tol",
            "qr_municipality": "Mechinagar Municipality",
            "expected_village": "Yekata Tole",
            "expected_ward": "6",
            "description": "Multi-word village name"
        },
        {
            "input_text": "yakata tol",
            "qr_municipality": "Mechinagar Municipality",
            "expected_village": "Yekata Tole",
            "expected_ward": "6",
            "description": "Multi-word village name"
        }

    ]
    
    passed_tests = 0
    total_tests = len(test_cases)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_case['description']}")
        print(f"Input: '{test_case['input_text']}' | Municipality: '{test_case['qr_municipality']}'")
        
        try:
            # Call the function
            result_village, result_ward = validator.validate_village_input(
                test_case['input_text'],
                test_case['qr_municipality']
            )
            
            # Check if results match expectations
            village_match = result_village == test_case['expected_village']
            ward_match = result_ward == test_case['expected_ward']
            
            if village_match and ward_match:
                print(f"✅ PASSED: Expected ({test_case['expected_village']}, {test_case['expected_ward']}), Got ({result_village}, {result_ward})")
                passed_tests += 1
            else:
                print(f"❌ FAILED: Expected ({test_case['expected_village']}, {test_case['expected_ward']}), Got ({result_village}, {result_ward})")
                
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
    
    print("\n" + "=" * 60)
    print(f"TEST RESULTS: {passed_tests}/{total_tests} tests passed")
    print("=" * 60)
    
    # Additional debugging information
    print("\nDEBUGGING INFORMATION:")
    print(f"CSV columns: {list(validator.municipality_villages.columns)}")
    print(f"CSV shape: {validator.municipality_villages.shape}")
    print("\nFirst few rows of CSV data:")
    print(validator.municipality_villages.head())
    
    # Test municipality filtering
    print(f"\nMunicipalities in CSV: {validator.municipality_villages['municipality'].unique()}")
    
    # Test specific municipality data
    birtamod_data = validator.municipality_villages[validator.municipality_villages['municipality'] == 'Birtamod']
    print(f"\nBirtamod municipality data:")
    print(birtamod_data[:5][:5])
    
    mechinagar_data = validator.municipality_villages[validator.municipality_villages['municipality'] == 'Mechinagar']
    print(f"\nMechinagar municipality data:")
    print(mechinagar_data[:5][:5])
    
    return passed_tests == total_tests

if __name__ == "__main__":
    test_validate_village_input()
