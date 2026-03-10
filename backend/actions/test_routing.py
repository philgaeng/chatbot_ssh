"""
Test action to verify routing_map dictionary structure.
This action validates the routing dictionary without calling the actual function.
"""
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet


class ActionTestRouting(Action):
    """Test action to verify routing_map dictionary returns correct values."""
    
    SKIP_VALUE = "/__skip__"
    
    def name(self) -> Text:
        return "action_test_routing"
    
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        """
        Test the routing_map dictionary structure with mock navigation logic.
        """
        test_results = []
        failed_tests = []
        
        # Mock routing_map (same structure as in get_next_action_for_form)
        dic_status_check_next_action = {    
            self.SKIP_VALUE: "action_skip_status_check_outro",
            "status_check_modify": "form_status_check_modify",
            "status_check_follow_up": "action_status_check_follow_up"
        }
        
        routing_map = {
            "new_grievance": {
                "form_grievance": "form_contact",
                "form_contact": "form_otp",
                "form_otp": "action_submit_grievance"
            },
            "status_check": {
                "form_status_check_1": {
                    "route_status_check_grievance_id": "form_story_step",
                    "route_status_check_phone": "form_otp",
                    self.SKIP_VALUE: "form_status_check_skip"
                },
                "form_status_check_2": "form_story_step",
                "form_otp": {
                    "route_status_check_phone": "form_status_check_2",
                    self.SKIP_VALUE: "form_status_check_skip",
                    "route_status_check_grievance_id": dic_status_check_next_action
                },
                "form_story_step": {
                    "route_status_check_grievance_id": {
                        "status_check_request_follow_up": "action_status_check_request_follow_up",
                        "status_check_modify": "form_status_check_modify"
                    },
                    "route_status_check_phone": {
                        "status_check_request_follow_up": "action_status_check_request_follow_up",
                        "status_check_modify": "form_status_check_modify"
                    },
                    self.SKIP_VALUE: "form_status_check_skip"
                },
                "form_status_check_skip": "action_skip_status_check_outro"
            }
        }
        
        # Test cases: (test_name, (story_main, form, route, step), expected_action)
        test_cases = [
            # New Grievance Flow
            ("New Grievance: form_grievance", ("new_grievance", "form_grievance", None, None), "form_contact"),
            ("New Grievance: form_contact", ("new_grievance", "form_contact", None, None), "form_otp"),
            ("New Grievance: form_otp", ("new_grievance", "form_otp", None, None), "action_submit_grievance"),
            
            # Status Check: Phone Route
            ("Status Check: form_status_check_1 (phone)", ("status_check", "form_status_check_1", "route_status_check_phone", None), "form_otp"),
            ("Status Check: form_otp (phone)", ("status_check", "form_otp", "route_status_check_phone", None), "form_status_check_2"),
            ("Status Check: form_status_check_2", ("status_check", "form_status_check_2", None, None), "form_story_step"),
            ("Status Check: form_story_step (phone) + request_follow_up", 
             ("status_check", "form_story_step", "route_status_check_phone", "status_check_request_follow_up"), 
             "action_status_check_request_follow_up"),
            ("Status Check: form_story_step (phone) + modify", 
             ("status_check", "form_story_step", "route_status_check_phone", "status_check_modify"), 
             "form_status_check_modify"),
            
            # Status Check: Grievance ID Route
            ("Status Check: form_status_check_1 (grievance_id)", ("status_check", "form_status_check_1", "route_status_check_grievance_id", None), "form_story_step"),
            ("Status Check: form_story_step (grievance_id) + request_follow_up", 
             ("status_check", "form_story_step", "route_status_check_grievance_id", "status_check_request_follow_up"), 
             "action_status_check_request_follow_up"),
            ("Status Check: form_story_step (grievance_id) + modify", 
             ("status_check", "form_story_step", "route_status_check_grievance_id", "status_check_modify"), 
             "form_status_check_modify"),
            
            # Skip scenarios
            ("Status Check: form_status_check_1 + skip", ("status_check", "form_status_check_1", self.SKIP_VALUE, None), "form_status_check_skip"),
            ("Status Check: form_story_step + skip", ("status_check", "form_story_step", None, self.SKIP_VALUE), "form_status_check_skip"),
            ("Status Check: form_status_check_skip", ("status_check", "form_status_check_skip", None, None), "action_skip_status_check_outro"),
        ]
        
        # Mock navigation logic (simplified version of get_next_action_for_form)
        def navigate_routing_map(story_main, form_name, story_route, story_step):
            """Navigate through routing_map to get next action."""
            if story_main not in routing_map:
                raise ValueError(f"story_main '{story_main}' not in routing_map")
            
            result = routing_map[story_main]
            
            # Navigate by form
            if isinstance(result, dict) and form_name:
                if form_name not in result:
                    raise ValueError(f"form '{form_name}' not in routing_map['{story_main}']")
                result = result[form_name]
            
            # Navigate by route
            if isinstance(result, dict) and story_route:
                if story_route in result:
                    result = result[story_route]
            
            # Navigate by step
            if isinstance(result, dict) and story_step:
                if story_step in result:
                    result = result[story_step]
            
            return result
        
        # Run tests
        for test_name, (story_main, form_name, story_route, story_step), expected_action in test_cases:
            try:
                actual_action = navigate_routing_map(story_main, form_name, story_route, story_step)
                
                if actual_action == expected_action:
                    test_results.append(f"✅ {test_name}")
                else:
                    failed_tests.append(f"❌ {test_name}\n   Expected: {expected_action}\n   Got: {actual_action}")
            
            except Exception as e:
                failed_tests.append(f"❌ {test_name}\n   Error: {str(e)}")
        
        # Generate summary
        total = len(test_cases)
        passed = len(test_results)
        failed = len(failed_tests)
        
        summary = f"\n{'='*60}\n"
        summary += f"ROUTING MAP DICTIONARY TEST\n"
        summary += f"{'='*60}\n"
        summary += f"Total: {total} | Passed: {passed} | Failed: {failed}\n"
        summary += f"{'='*60}\n\n"
        
        if failed_tests:
            summary += "❌ FAILED:\n" + "\n".join(failed_tests) + "\n\n"
        
        if test_results:
            summary += "✅ PASSED:\n" + "\n".join(test_results) + "\n"
        
        summary += f"{'='*60}\n"
        
        dispatcher.utter_message(text=summary)
        
        return []


class ActionTestStoryStepExtraction(Action):
    """Test action to verify story_step slot extraction from intents."""
    
    def name(self) -> Text:
        return "action_test_story_step_extraction"
    
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        """
        Test that story_step intents are properly extracted.
        """
        latest_message = tracker.latest_message
        message_text = latest_message.get("text", "")
        intent = latest_message.get("intent", {}).get("name", "")
        
        current_story_step = tracker.get_slot("story_step")
        
        # Test the extraction logic
        extracted_value = None
        if message_text.startswith("/"):
            if intent:
                extracted_value = intent
            else:
                extracted_value = message_text.strip("/").strip()
        
        result = f"\n\n{'='*60}\n"
        result += f"STORY_STEP EXTRACTION TEST\n"
        result += f"{'='*60}\n"
        result += f"Message Text: {message_text}\n"
        result += f"Detected Intent: {intent}\n"
        result += f"Current story_step slot: {current_story_step}\n"
        result += f"Extracted Value: {extracted_value}\n"
        result += f"{'='*60}\n\n"
        
        if extracted_value == "status_check_request_follow_up":
            result += "✅ PASS: Correctly extracted status_check_request_follow_up\n"
        elif extracted_value == "status_check_modify_grievance":
            result += "✅ PASS: Correctly extracted status_check_modify_grievance\n"
        else:
            result += f"⚠️  INFO: Extracted value: {extracted_value}\n"
        
        result += f"{'='*60}\n"
        
        dispatcher.utter_message(text=result)
        
        return [SlotSet("story_step", extracted_value)] if extracted_value else []

