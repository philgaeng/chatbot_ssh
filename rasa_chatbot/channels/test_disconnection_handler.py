#!/usr/bin/env python3
"""
Test SocketIO disconnection handler to verify tracker access
"""

import asyncio
import logging
from rasa.core.channels.socketio import SocketIOInput
from rasa.core.tracker_store import TrackerStore
from rasa.core.domain import Domain
from rasa.core.brokers.broker import EventBroker

# Set up logging
logger = logging.getLogger(__name__)

class TestDisconnectionSocketIOInput(SocketIOInput):
    """Extended SocketIO input with disconnection testing"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("🔧 Initialized TestDisconnectionSocketIOInput")
    
    async def on_disconnect(self, sid, data=None):
        """Handle user disconnection with tracker access test"""
        
        logger.info("=" * 80)
        logger.info(f"🔌 USER DISCONNECTED: {sid}")
        logger.info("=" * 80)
        
        try:
            # Test 1: Basic disconnection info
            logger.info(f"Disconnection data: {data}")
            logger.info(f"Session ID: {sid}")
            
            # Test 2: Try to access tracker store
            logger.info("🔍 Testing tracker store access...")
            
            # Get tracker store (this is what we'd use in real implementation)
            tracker_store = self._get_tracker_store()
            
            if tracker_store:
                logger.info("✅ Tracker store accessible")
                
                # Test 3: Try to retrieve tracker
                logger.info(f"🔍 Attempting to retrieve tracker for session: {sid}")
                
                try:
                    # This is the key test - can we get the tracker after disconnection?
                    tracker = await tracker_store.retrieve(sid)
                    
                    if tracker:
                        logger.info("✅ SUCCESS: Tracker retrieved after disconnection!")
                        logger.info(f"✅ Tracker sender_id: {tracker.sender_id}")
                        logger.info(f"✅ Tracker slots count: {len(tracker.slots)}")
                        logger.info(f"✅ Tracker events count: {len(tracker.events)}")
                        
                        # Check for specific slots we care about
                        grievance_id = tracker.get_slot("grievance_id")
                        has_draft_updates = tracker.get_slot("has_draft_updates")
                        additional_description = tracker.get_slot("additional_description")
                        
                        logger.info(f"🔍 Grievance ID: {grievance_id}")
                        logger.info(f"🔍 Has draft updates: {has_draft_updates}")
                        logger.info(f"🔍 Additional description: {additional_description}")
                        
                        # Test 4: Check if we would trigger auto-save
                        if has_draft_updates and grievance_id:
                            logger.info("🚨 WOULD TRIGGER AUTO-SAVE HERE 🚨")
                            logger.info("🚨 This is where we'd call finalize_updates_from_tracker()")
                        else:
                            logger.info("ℹ️ No draft updates to auto-save")
                        
                        # Test 5: Log recent events
                        logger.info("🔍 Recent events:")
                        recent_events = tracker.events[-5:] if len(tracker.events) >= 5 else tracker.events
                        for i, event in enumerate(recent_events):
                            logger.info(f"  Event {i}: {event}")
                        
                    else:
                        logger.warning("⚠️ Tracker not found for session")
                        
                except Exception as e:
                    logger.error(f"❌ Error retrieving tracker: {str(e)}")
                    import traceback
                    logger.error(f"❌ Traceback: {traceback.format_exc()}")
                    
            else:
                logger.error("❌ Tracker store not accessible")
            
            # Test 6: Call parent disconnect
            logger.info("🔍 Calling parent disconnect...")
            await super().on_disconnect(sid, data)
            logger.info("✅ Parent disconnect completed")
            
        except Exception as e:
            logger.error(f"❌ Error in on_disconnect: {str(e)}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            
            # Still call parent disconnect
            try:
                await super().on_disconnect(sid, data)
            except Exception as parent_error:
                logger.error(f"❌ Error in parent disconnect: {str(parent_error)}")
        
        logger.info("=" * 80)
        logger.info("🔌 DISCONNECTION HANDLING COMPLETE")
        logger.info("=" * 80)
    
    def _get_tracker_store(self):
        """Get the tracker store instance"""
        try:
            # This is how we'd access the tracker store in a real implementation
            # The exact method depends on how Rasa is configured
            
            # Method 1: Try to get from agent (if available)
            if hasattr(self, 'agent') and self.agent:
                return self.agent.tracker_store
            
            # Method 2: Try to get from channel (if available)
            if hasattr(self, 'tracker_store'):
                return self.tracker_store
            
            # Method 3: Create new instance (for testing)
            logger.warning("⚠️ Creating new tracker store instance for testing")
            # This would need proper configuration
            # return TrackerStore.create(tracker_store_config)
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting tracker store: {str(e)}")
            return None


class TestDisconnectionHandler:
    """Standalone disconnection handler for testing"""
    
    def __init__(self, tracker_store=None):
        self.tracker_store = tracker_store
        logger.info("🔧 Initialized TestDisconnectionHandler")
    
    async def handle_disconnection_test(self, session_id: str):
        """Test disconnection handling without SocketIO"""
        
        logger.info("=" * 80)
        logger.info(f"🧪 TESTING DISCONNECTION HANDLER FOR: {session_id}")
        logger.info("=" * 80)
        
        try:
            if not self.tracker_store:
                logger.error("❌ No tracker store available")
                return False
            
            # Test tracker retrieval
            logger.info(f"🔍 Attempting to retrieve tracker for: {session_id}")
            tracker = await self.tracker_store.retrieve(session_id)
            
            if tracker:
                logger.info("✅ SUCCESS: Tracker retrieved!")
                logger.info(f"✅ Session ID: {tracker.sender_id}")
                logger.info(f"✅ Slots: {len(tracker.slots)}")
                logger.info(f"✅ Events: {len(tracker.events)}")
                
                # Check for draft updates
                has_draft = tracker.get_slot("has_draft_updates")
                grievance_id = tracker.get_slot("grievance_id")
                
                logger.info(f"🔍 Has draft updates: {has_draft}")
                logger.info(f"🔍 Grievance ID: {grievance_id}")
                
                if has_draft and grievance_id:
                    logger.info("🚨 WOULD AUTO-SAVE HERE 🚨")
                    return True
                else:
                    logger.info("ℹ️ No auto-save needed")
                    return True
            else:
                logger.warning("⚠️ No tracker found")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error in disconnection test: {str(e)}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return False
        
        finally:
            logger.info("=" * 80)
            logger.info("🧪 DISCONNECTION TEST COMPLETE")
            logger.info("=" * 80)

