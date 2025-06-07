#!/usr/bin/env python3
"""
Test suite for extract_input_data_for_translation function

This file tests the function with various data structures that could be encountered
in the Nepal chatbot system, particularly from Celery group() results.
"""

import sys
import os
sys.path.append('/home/ubuntu/nepal_chatbot')

from actions_server.LLM_helpers import extract_input_data_for_translation

def test_flat_dictionary():
    """Test with a simple flat dictionary"""
    print("=== Test 1: Flat Dictionary ===")
    
    input_data = {
        'grievance_id': 'GRIEV-001',
        'language_code': 'ne',
        'grievance_details': 'सडक बिग्रिएको छ',
        'grievance_summary': 'सडक समस्या',
        'other_field': 'ignored'
    }
    
    try:
        result = extract_input_data_for_translation(input_data)
        print("✅ SUCCESS")
        print(f"Result: {result}")
        assert result['grievance_id'] == 'GRIEV-001'
        assert result['language_code'] == 'ne'
        assert result['grievance_details'] == 'सडक बिग्रिएको छ'
        assert result['grievance_summary'] == 'सडक समस्या'
        print("✅ All assertions passed")
    except Exception as e:
        print(f"❌ FAILED: {e}")
    print()

def test_nested_dictionary():
    """Test with nested dictionary structure"""
    print("=== Test 2: Nested Dictionary ===")
    
    input_data = {
        'status': 'SUCCESS',
        'operation': 'classification',
        'values': {
            'grievance_details': 'पानी बिग्रिएको छ',
            'grievance_summary': 'पानी समस्या',
            'grievance_categories': ['Water Supply']
        },
        'grievance_id': 'GRIEV-002',
        'metadata': {
            'language_code': 'ne',
            'timestamp': '2024-01-01'
        }
    }
    
    try:
        result = extract_input_data_for_translation(input_data)
        print("✅ SUCCESS")
        print(f"Result: {result}")
        assert result['grievance_id'] == 'GRIEV-002'
        assert result['language_code'] == 'ne'
        assert result['grievance_details'] == 'पानी बिग्रिएको छ'
        assert result['grievance_summary'] == 'पानी समस्या'
        print("✅ All assertions passed")
    except Exception as e:
        print(f"❌ FAILED: {e}")
    print()

def test_group_result_format():
    """Test with Celery group() result format - list of dictionaries"""
    print("=== Test 3: Group Result Format ===")
    
    # This simulates the result from group(classify_task, store_task)
    input_data = [
        {  # Result from classify_and_summarize_grievance_task
            'status': 'SUCCESS',
            'operation': 'classification',
            'grievance_id': 'GRIEV-003',
            'values': {
                'grievance_details': 'बिजुली समस्या छ',
                'grievance_summary': 'बिजुली कटौती',
                'grievance_categories': ['Electricity']
            }
        },
        {  # Result from store_result_to_db_task
            'status': 'success',
            'operation': 'store_result',
            'entity_key': 'grievance_id',
            'language_code': 'ne'
        }
    ]
    
    try:
        result = extract_input_data_for_translation(input_data)
        print("✅ SUCCESS")
        print(f"Result: {result}")
        assert result['grievance_id'] == 'GRIEV-003'
        assert result['language_code'] == 'ne'
        assert result['grievance_details'] == 'बिजुली समस्या छ'
        assert result['grievance_summary'] == 'बिजुली कटौती'
        print("✅ All assertions passed")
    except Exception as e:
        print(f"❌ FAILED: {e}")
    print()

def test_deep_nesting():
    """Test with deeply nested structure"""
    print("=== Test 4: Deep Nesting ===")
    
    input_data = {
        'task_result': {
            'celery_data': {
                'result': {
                    'processing': {
                        'grievance_id': 'GRIEV-004',
                        'content': {
                            'text_data': {
                                'grievance_details': 'ट्राफिक जाम समस्या',
                                'grievance_summary': 'ट्राफिक समस्या'
                            },
                            'language_code': 'ne'
                        }
                    }
                }
            }
        }
    }
    
    try:
        result = extract_input_data_for_translation(input_data)
        print("✅ SUCCESS")
        print(f"Result: {result}")
        assert result['grievance_id'] == 'GRIEV-004'
        assert result['language_code'] == 'ne'
        assert result['grievance_details'] == 'ट्राफिक जाम समस्या'
        assert result['grievance_summary'] == 'ट्राफिक समस्या'
        print("✅ All assertions passed")
    except Exception as e:
        print(f"❌ FAILED: {e}")
    print()

def test_missing_optional_field():
    """Test with missing grievance_summary (optional field)"""
    print("=== Test 5: Missing Optional Field (grievance_summary) ===")
    
    input_data = {
        'grievance_id': 'GRIEV-005',
        'language_code': 'en',
        'grievance_details': 'Road construction delay issue'
        # grievance_summary is missing - should use truncated grievance_details
    }
    
    try:
        result = extract_input_data_for_translation(input_data)
        print("✅ SUCCESS")
        print(f"Result: {result}")
        assert result['grievance_id'] == 'GRIEV-005'
        assert result['language_code'] == 'en'
        assert result['grievance_details'] == 'Road construction delay issue'
        assert 'grievance_summary' in result  # Should be auto-generated
        assert len(result['grievance_summary']) <= 203  # 200 chars + "..."
        print("✅ All assertions passed - auto-generated summary")
    except Exception as e:
        print(f"❌ FAILED: {e}")
    print()

def test_missing_required_field():
    """Test with missing required field (should raise error)"""
    print("=== Test 6: Missing Required Field ===")
    
    input_data = {
        'language_code': 'hi',
        'grievance_details': 'सड़क की समस्या है',
        'grievance_summary': 'सड़क समस्या'
        # grievance_id is missing - should raise ValueError
    }
    
    try:
        result = extract_input_data_for_translation(input_data)
        print(f"❌ UNEXPECTED SUCCESS: {result}")
        print("❌ Should have failed with missing grievance_id")
    except ValueError as e:
        print("✅ SUCCESS - Correctly raised ValueError")
        print(f"Error message: {e}")
        assert "grievance_id" in str(e)
        print("✅ Error message contains expected field name")
    except Exception as e:
        print(f"❌ FAILED with unexpected error: {e}")
    print()

def test_complex_group_scenario():
    """Test with realistic complex group scenario"""
    print("=== Test 7: Complex Group Scenario ===")
    
    # This simulates a more complex group result with multiple nested levels
    input_data = [
        {  # First task result
            'status': 'SUCCESS',
            'operation': 'classification',
            'task_id': 'task-123',
            'grievance_id': 'GRIEV-006',
            'values': {
                'grievance_details': 'पार्किङ स्थान अपर्याप्त छ',
                'grievance_summary': 'पार्किङ समस्या',
                'grievance_categories': ['Transportation', 'Infrastructure']
            }
        },
        {  # Second task result  
            'status': 'success',
            'operation': 'store_result',
            'metadata': {
                'processing_info': {
                    'language_code': 'ne',
                    'confidence': 0.95
                }
            }
        }
    ]
    
    try:
        result = extract_input_data_for_translation(input_data)
        print("✅ SUCCESS")
        print(f"Result: {result}")
        assert result['grievance_id'] == 'GRIEV-006'
        assert result['language_code'] == 'ne'
        assert result['grievance_details'] == 'पार्किङ स्थान अपर्याप्त छ'
        assert result['grievance_summary'] == 'पार्किङ समस्या'
        print("✅ All assertions passed")
    except Exception as e:
        print(f"❌ FAILED: {e}")
    print()

def test_mixed_languages():
    """Test with different language scenarios"""
    print("=== Test 8: Mixed Languages ===")
    
    test_cases = [
        {
            'name': 'English',
            'data': {
                'grievance_id': 'GRIEV-EN-001',
                'language_code': 'en',
                'grievance_details': 'Water supply is irregular in our area',
                'grievance_summary': 'Water supply issue'
            }
        },
        {
            'name': 'Hindi',
            'data': {
                'grievance_id': 'GRIEV-HI-001',
                'language_code': 'hi',
                'grievance_details': 'हमारे क्षेत्र में पानी की आपूर्ति अनियमित है',
                'grievance_summary': 'पानी आपूर्ति की समस्या'
            }
        },
        {
            'name': 'Nepali',
            'data': {
                'grievance_id': 'GRIEV-NE-001',
                'language_code': 'ne',
                'grievance_details': 'हाम्रो क्षेत्रमा पानीको आपूर्ति अनियमित छ',
                'grievance_summary': 'पानी आपूर्ति समस्या'
            }
        }
    ]
    
    for case in test_cases:
        try:
            result = extract_input_data_for_translation(case['data'])
            print(f"✅ {case['name']}: SUCCESS")
            print(f"   Extracted: {result['language_code']} - {result['grievance_summary']}")
            assert result['language_code'] == case['data']['language_code']
            assert result['grievance_id'] == case['data']['grievance_id']
        except Exception as e:
            print(f"❌ {case['name']}: FAILED - {e}")
    print()

def test_empty_and_edge_cases():
    """Test edge cases"""
    print("=== Test 9: Edge Cases ===")
    
    edge_cases = [
        ('Empty dict', {}),
        ('Empty list', []),
        ('List with empty dict', [{}]),
        ('None values', {'grievance_id': None, 'language_code': None}),
        ('Empty strings', {'grievance_id': '', 'language_code': '', 'grievance_details': ''}),
    ]
    
    for case_name, case_data in edge_cases:
        try:
            result = extract_input_data_for_translation(case_data)
            print(f"❌ {case_name}: UNEXPECTED SUCCESS - {result}")
        except ValueError as e:
            print(f"✅ {case_name}: Correctly failed with ValueError - {str(e)[:50]}...")
        except Exception as e:
            print(f"⚠️  {case_name}: Failed with unexpected error - {str(e)[:50]}...")
    print()

def run_all_tests():
    """Run all test functions"""
    print("🧪 TESTING extract_input_data_for_translation function")
    print("=" * 60)
    
    test_functions = [
        test_flat_dictionary,
        test_nested_dictionary,
        test_group_result_format,
        test_deep_nesting,
        test_missing_optional_field,
        test_missing_required_field,
        test_complex_group_scenario,
        test_mixed_languages,
        test_empty_and_edge_cases
    ]
    
    for test_func in test_functions:
        test_func()
    
    print("🏁 All tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    run_all_tests() 