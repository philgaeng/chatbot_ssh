"""
Example usage of the HelpersRepo for keyword detection and location validation.

This file demonstrates how to use the helpers repository in your application.
"""

from .helpers_repo import helpers_repo


def example_keyword_detection():
    """Example of using keyword detection through helpers repository."""
    
    # Test texts
    test_texts = [
        "Someone kissed me without my consent",
        "They touched my leg inappropriately", 
        "I have a land dispute with my neighbor",
        "Someone threatened to kill me",
        "I lost my harvest due to rain"
    ]
    
    print("=== Keyword Detection Examples ===")
    
    for text in test_texts:
        result = helpers_repo.detect_sensitive_content(text, language_code="en")
        
        print(f"\nText: {text}")
        print(f"Detected: {result['detected']}")
        print(f"Level: {result['level']}")
        print(f"Category: {result['category']}")
        print(f"Message: {result['message']}")
        print(f"Action Required: {result['action_required']}")


def example_location_validation():
    """Example of using location validation through helpers repository."""
    
    # Test locations
    test_locations = [
        "Kathmandu Metropolitan City",
        "Lalitpur District",
        "Pokhara",
        "Biratnagar",
        "Invalid Location Name"
    ]
    
    print("\n=== Location Validation Examples ===")
    
    for location in test_locations:
        result = helpers_repo.validate_location(
            location_string=location,
            qr_province="Bagmati Province",
            qr_district="Kathmandu"
        )
        
        print(f"\nInput: {location}")
        print(f"Province: {result.get('province', 'Not found')}")
        print(f"District: {result.get('district', 'Not found')}")
        print(f"Municipality: {result.get('municipality', 'Not found')}")


def example_integration_with_rasa():
    """Example of how to use helpers repository in Rasa actions."""
    
    # Simulate Rasa action usage
    def process_user_input(user_text: str, user_location: str):
        """Process user input with keyword detection and location validation."""
        
        # 1. Check for sensitive content
        sensitive_result = helpers_repo.detect_sensitive_content(user_text)
        
        if sensitive_result['detected']:
            print(f"⚠️  Sensitive content detected: {sensitive_result['message']}")
            print(f"   Action required: {sensitive_result['action_required']}")
        
        # 2. Validate location
        location_result = helpers_repo.validate_location(user_location)
        
        if location_result.get('province') and location_result.get('district'):
            print(f"✅ Location validated: {location_result['province']}, {location_result['district']}")
        else:
            print("❌ Location validation failed")
        
        return {
            'sensitive_content': sensitive_result,
            'location': location_result
        }
    
    # Test the integration
    print("\n=== Rasa Integration Example ===")
    
    test_cases = [
        ("Someone harassed me at work", "Kathmandu Metropolitan City"),
        ("I have a property dispute", "Lalitpur District"),
        ("Someone threatened me", "Invalid Location")
    ]
    
    for user_text, user_location in test_cases:
        print(f"\nProcessing: '{user_text}' from '{user_location}'")
        result = process_user_input(user_text, user_location)
        print(f"Result: {result}")


if __name__ == "__main__":
    # Run all examples
    example_keyword_detection()
    example_location_validation()
    example_integration_with_rasa() 