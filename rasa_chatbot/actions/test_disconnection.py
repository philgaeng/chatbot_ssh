#!/usr/bin/env python3
"""
Test action to verify tracker access on disconnection
This is a simple test to see what data is available in the tracker
"""

import asyncio
import json
import logging
from typing import Any, Text, Dict, List
from rasa_sdk import Action
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
from rasa_sdk import Tracker

# Set up logging
logger = logging.getLogger(__name__)

class TestDisconnectionAction(Action):
    """Test action to log tracker data - can be triggered manually or on disconnection"""
    
    def name(self) -> Text:
        return "action_test_disconnection_log"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        """Log full tracker data for testing"""
        
        try:
            logger.info("=" * 80)
            logger.info("TEST DISCONNECTION ACTION - TRACKER DATA DUMP")
            logger.info("=" * 80)
            
            # Basic tracker info
            logger.info(f"Sender ID: {tracker.sender_id}")
            logger.info(f"Session ID: {tracker.sender_id}")
            logger.info(f"Latest Action Name: {tracker.latest_action_name}")
            logger.info(f"Active Loop: {tracker.active_loop}")
            logger.info(f"Latest Message: {tracker.latest_message}")
            
            # All slots
            logger.info("\n--- ALL SLOTS ---")
            all_slots = tracker.slots
            for slot_name, slot_value in all_slots.items():
                logger.info(f"Slot '{slot_name}': {slot_value}")
            
            # Recent events (last 10)
            logger.info("\n--- RECENT EVENTS (last 10) ---")
            recent_events = tracker.events[-10:] if len(tracker.events) > 10 else tracker.events
            for i, event in enumerate(recent_events):
                logger.info(f"Event {i}: {event}")
            
            # Check for specific status check related slots
            logger.info("\n--- STATUS CHECK RELATED SLOTS ---")
            status_slots = [
                "status_check_method",
                "status_check_list_grievance_id", 
                "status_check_complainant_phone",
                "status_check_complainant_full_name",
                "grievance_id",
                "additional_description",
                "has_draft_updates",
                "status_check_update_major"
            ]
            
            for slot_name in status_slots:
                slot_value = tracker.get_slot(slot_name)
                if slot_value is not None:
                    logger.info(f"Status Slot '{slot_name}': {slot_value}")
                else:
                    logger.info(f"Status Slot '{slot_name}': None")
            
            # Check if we have any draft updates
            has_draft = tracker.get_slot("has_draft_updates")
            grievance_id = tracker.get_slot("grievance_id")
            
            logger.info(f"\n--- DRAFT UPDATE STATUS ---")
            logger.info(f"Has draft updates: {has_draft}")
            logger.info(f"Grievance ID: {grievance_id}")
            
            if has_draft and grievance_id:
                logger.info("🚨 WOULD TRIGGER AUTO-SAVE HERE 🚨")
                # This is where we would call the actual save logic
                # await self.auto_save_draft_updates(tracker)
            
            # Form state
            logger.info(f"\n--- FORM STATE ---")
            logger.info(f"Active loop: {tracker.active_loop}")
            logger.info(f"Latest action: {tracker.latest_action_name}")
            
            # Convert tracker to dict for full inspection
            logger.info("\n--- FULL TRACKER AS DICT ---")
            tracker_dict = {
                "sender_id": tracker.sender_id,
                "slots": dict(tracker.slots),
                "latest_action_name": tracker.latest_action_name,
                "active_loop": tracker.active_loop,
                "latest_message": tracker.latest_message.as_dict() if tracker.latest_message else None,
                "events_count": len(tracker.events),
                "latest_events": [event.as_dict() for event in tracker.events[-5:]]
            }
            
            # Log as JSON for easier reading
            logger.info(f"Tracker Summary JSON:\n{json.dumps(tracker_dict, indent=2, default=str)}")
            
            logger.info("=" * 80)
            logger.info("END TEST DISCONNECTION ACTION")
            logger.info("=" * 80)
            
            # Return a simple confirmation
            return [
                SlotSet("test_disconnection_logged", True)
            ]
            
        except Exception as e:
            logger.error(f"Error in test disconnection action: {str(e)}")
            logger.error(f"Exception type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            return [
                SlotSet("test_disconnection_error", str(e))
            ]


class TestTrackerAccessAction(Action):
    """Action to test accessing tracker data programmatically (for testing purposes)"""
    
    def name(self) -> Text:
        return "action_test_tracker_access"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        """Test accessing tracker data - can be called manually"""
        
        try:
            logger.info("🧪 TESTING TRACKER ACCESS")
            
            # Test getting tracker by sender_id (this is what we'd do on disconnection)
            sender_id = tracker.sender_id
            
            # This is the key test - can we access tracker data programmatically?
            # In a real disconnection handler, we'd do something like:
            # tracker = await tracker_store.retrieve(sender_id)
            
            logger.info(f"✅ Successfully accessed tracker for sender_id: {sender_id}")
            logger.info(f"✅ Tracker has {len(tracker.slots)} slots")
            logger.info(f"✅ Tracker has {len(tracker.events)} events")
            
            # Test specific slots we care about
            test_slots = ["grievance_id", "additional_description", "has_draft_updates"]
            for slot_name in test_slots:
                value = tracker.get_slot(slot_name)
                logger.info(f"✅ Slot '{slot_name}': {value}")
            
            dispatcher.utter_message(
                text=f"✅ Tracker access test successful! Found {len(tracker.slots)} slots and {len(tracker.events)} events."
            )
            
            return [
                SlotSet("tracker_access_test_passed", True)
            ]
            
        except Exception as e:
            logger.error(f"❌ Tracker access test failed: {str(e)}")
            dispatcher.utter_message(
                text=f"❌ Tracker access test failed: {str(e)}"
            )
            
            return [
                SlotSet("tracker_access_test_failed", str(e))
            ]


class SimulateDisconnectionAction(Action):
    """Action to simulate what happens on disconnection"""
    
    def name(self) -> Text:
        return "action_simulate_disconnection"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        """Simulate disconnection handling"""
        
        try:
            logger.info("🔌 SIMULATING DISCONNECTION HANDLING")
            
            # Simulate what we'd do on actual disconnection
            sender_id = tracker.sender_id
            
            # Check for draft updates
            has_draft_updates = tracker.get_slot("has_draft_updates")
            grievance_id = tracker.get_slot("grievance_id")
            
            logger.info(f"🔍 Checking for draft updates...")
            logger.info(f"🔍 Has draft updates: {has_draft_updates}")
            logger.info(f"🔍 Grievance ID: {grievance_id}")
            
            if has_draft_updates and grievance_id:
                logger.info("🚨 WOULD TRIGGER AUTO-SAVE HERE 🚨")
                
                # Simulate the auto-save process
                additional_description = tracker.get_slot("additional_description")
                
                if additional_description:
                    logger.info(f"🚨 Would save additional description: {additional_description}")
                    logger.info("🚨 Would call: update_grievance_with_tracking()")
                    logger.info("🚨 Would call: LLM classification")
                    
                    dispatcher.utter_message(
                        text="🔌 Simulated disconnection handling: Would auto-save your updates!"
                    )
                else:
                    dispatcher.utter_message(
                        text="🔌 Simulated disconnection handling: No updates to save."
                    )
            else:
                logger.info("ℹ️ No draft updates to auto-save")
                dispatcher.utter_message(
                    text="🔌 Simulated disconnection handling: No draft updates found."
                )
            
            return [
                SlotSet("disconnection_simulation_completed", True)
            ]
            
        except Exception as e:
            logger.error(f"❌ Error in disconnection simulation: {str(e)}")
            dispatcher.utter_message(
                text=f"❌ Disconnection simulation failed: {str(e)}"
            )
            
            return [
                SlotSet("disconnection_simulation_error", str(e))
            ]
