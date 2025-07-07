import os
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import json

# Import our services
from backend.services.database_services.mysql_services import MySQLDatabaseManager, GRMIntegrationService
from backend.services.database_services.ssh_tunnel import initialize_ssh_tunnel, cleanup_ssh_tunnel
from backend.config.grm_config import (
    GRM_INTEGRATION_CONFIG, 
    GRM_FIELD_MAPPING, 
    GRM_STATUS_MAPPING,
    GRM_TABLE_NAMES
)

# Setup logging
logger = logging.getLogger(__name__)

class SyncStatus(Enum):
    """Status of synchronization operations"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"

@dataclass
class SyncResult:
    """Result of a synchronization operation"""
    success: bool
    status: SyncStatus
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class GRMDataMapper:
    """Maps data between chatbot format and GRM system format"""
    
    @staticmethod
    def map_grievance_to_grm(grievance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map grievance data from chatbot format to GRM format"""
        grm_data = {}
        
        for chatbot_field, grm_field in GRM_FIELD_MAPPING.items():
            if chatbot_field in grievance_data:
                grm_data[grm_field] = grievance_data[chatbot_field]
        
        # Handle special mappings
        if 'grievance_creation_date' in grievance_data:
            grm_data['submission_date'] = grievance_data['grievance_creation_date']
        
        # Map status
        chatbot_status = grievance_data.get('classification_status', 'pending')
        grm_data['status'] = GRM_STATUS_MAPPING.get(chatbot_status, 'pending')
        
        # Add metadata
        grm_data['source_system'] = 'chatbot'
        grm_data['sync_timestamp'] = datetime.now()
        
        return grm_data
    
    @staticmethod
    def map_grm_to_grievance(grm_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map grievance data from GRM format to chatbot format"""
        grievance_data = {}
        
        # Reverse mapping
        reverse_mapping = {v: k for k, v in GRM_FIELD_MAPPING.items()}
        
        for grm_field, chatbot_field in reverse_mapping.items():
            if grm_field in grm_data:
                grievance_data[chatbot_field] = grm_data[grm_field]
        
        # Handle special mappings
        if 'submission_date' in grm_data:
            grievance_data['grievance_creation_date'] = grm_data['submission_date']
        
        # Map status back
        grm_status = grm_data.get('status', 'pending')
        reverse_status_mapping = {v: k for k, v in GRM_STATUS_MAPPING.items()}
        grievance_data['classification_status'] = reverse_status_mapping.get(grm_status, 'pending')
        
        return grievance_data

class GRMSyncManager:
    """Manages synchronization between chatbot and GRM system"""
    
    def __init__(self):
        self.mysql_manager = MySQLDatabaseManager()
        self.grm_service = GRMIntegrationService()
        self.data_mapper = GRMDataMapper()
        self.sync_history: List[SyncResult] = []
        self.last_sync_time: Optional[datetime] = None
        
    def initialize_connection(self) -> bool:
        """Initialize connection to GRM system"""
        try:
            # Initialize SSH tunnel if needed
            if not initialize_ssh_tunnel():
                logger.warning("SSH tunnel initialization failed, continuing with direct connection")
            
            # Test MySQL connection
            if self.mysql_manager.test_connection():
                logger.info("GRM MySQL connection established successfully")
                return True
            else:
                logger.error("Failed to establish GRM MySQL connection")
                return False
                
        except Exception as e:
            logger.error(f"Error initializing GRM connection: {str(e)}")
            return False
    
    def sync_grievance(self, grievance_data: Dict[str, Any]) -> SyncResult:
        """Sync a single grievance to GRM system"""
        try:
            logger.info(f"Starting sync for grievance: {grievance_data.get('grievance_id')}")
            
            # Map data to GRM format
            grm_data = self.data_mapper.map_grievance_to_grm(grievance_data)
            
            # Sync to GRM system
            success = self.grm_service.sync_grievance_data(grm_data)
            
            if success:
                result = SyncResult(
                    success=True,
                    status=SyncStatus.SUCCESS,
                    message=f"Successfully synced grievance {grievance_data.get('grievance_id')} to GRM",
                    data=grm_data
                )
                logger.info(result.message)
            else:
                result = SyncResult(
                    success=False,
                    status=SyncStatus.FAILED,
                    message=f"Failed to sync grievance {grievance_data.get('grievance_id')} to GRM",
                    error="GRM sync operation failed"
                )
                logger.error(result.message)
            
            # Store in history
            self.sync_history.append(result)
            self.last_sync_time = datetime.now()
            
            return result
            
        except Exception as e:
            error_msg = f"Error syncing grievance: {str(e)}"
            logger.error(error_msg)
            
            result = SyncResult(
                success=False,
                status=SyncStatus.FAILED,
                message=error_msg,
                error=str(e)
            )
            
            self.sync_history.append(result)
            return result
    
    def sync_grievances_batch(self, grievances: List[Dict[str, Any]]) -> List[SyncResult]:
        """Sync multiple grievances in batch"""
        results = []
        
        logger.info(f"Starting batch sync for {len(grievances)} grievances")
        
        for grievance in grievances:
            result = self.sync_grievance(grievance)
            results.append(result)
            
            # Add small delay between syncs to avoid overwhelming the system
            time.sleep(0.1)
        
        success_count = sum(1 for r in results if r.success)
        logger.info(f"Batch sync completed: {success_count}/{len(grievances)} successful")
        
        return results
    
    def get_grm_status(self, grievance_id: str) -> Optional[Dict[str, Any]]:
        """Get grievance status from GRM system"""
        try:
            grm_status = self.grm_service.get_grm_grievance_status(grievance_id)
            if grm_status:
                # Map back to chatbot format
                return self.data_mapper.map_grm_to_grievance(grm_status)
            return None
        except Exception as e:
            logger.error(f"Error getting GRM status for {grievance_id}: {str(e)}")
            return None
    
    def update_grievance_status(self, grievance_id: str, status: str, notes: str = None) -> bool:
        """Update grievance status in GRM system"""
        try:
            # Map status to GRM format
            grm_status = GRM_STATUS_MAPPING.get(status, status)
            
            success = self.grm_service.update_grievance_status(grievance_id, grm_status, notes)
            
            if success:
                logger.info(f"Successfully updated status for grievance {grievance_id} in GRM")
            else:
                logger.error(f"Failed to update status for grievance {grievance_id} in GRM")
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating GRM status for {grievance_id}: {str(e)}")
            return False
    
    def get_sync_history(self, limit: int = 100) -> List[SyncResult]:
        """Get recent sync history"""
        return self.sync_history[-limit:] if self.sync_history else []
    
    def get_sync_stats(self) -> Dict[str, Any]:
        """Get synchronization statistics"""
        if not self.sync_history:
            return {
                'total_syncs': 0,
                'successful_syncs': 0,
                'failed_syncs': 0,
                'success_rate': 0.0,
                'last_sync_time': None
            }
        
        total = len(self.sync_history)
        successful = sum(1 for r in self.sync_history if r.success)
        failed = total - successful
        success_rate = (successful / total) * 100 if total > 0 else 0
        
        return {
            'total_syncs': total,
            'successful_syncs': successful,
            'failed_syncs': failed,
            'success_rate': round(success_rate, 2),
            'last_sync_time': self.last_sync_time.isoformat() if self.last_sync_time else None
        }
    
    def cleanup(self):
        """Cleanup resources"""
        try:
            cleanup_ssh_tunnel()
            logger.info("GRM sync manager cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

class GRMIntegrationOrchestrator:
    """Orchestrates GRM integration operations"""
    
    def __init__(self):
        self.sync_manager = GRMSyncManager()
        self.is_initialized = False
        
    def initialize(self) -> bool:
        """Initialize the GRM integration system"""
        if not GRM_INTEGRATION_CONFIG['enabled']:
            logger.info("GRM integration is disabled in configuration")
            return False
        
        try:
            if self.sync_manager.initialize_connection():
                self.is_initialized = True
                logger.info("GRM integration system initialized successfully")
                return True
            else:
                logger.error("Failed to initialize GRM integration system")
                return False
        except Exception as e:
            logger.error(f"Error initializing GRM integration: {str(e)}")
            return False
    
    def process_grievance(self, grievance_data: Dict[str, Any]) -> SyncResult:
        """Process a grievance through GRM integration"""
        if not self.is_initialized:
            return SyncResult(
                success=False,
                status=SyncStatus.FAILED,
                message="GRM integration not initialized",
                error="System not initialized"
            )
        
        return self.sync_manager.sync_grievance(grievance_data)
    
    def process_grievances_batch(self, grievances: List[Dict[str, Any]]) -> List[SyncResult]:
        """Process multiple grievances through GRM integration"""
        if not self.is_initialized:
            return [SyncResult(
                success=False,
                status=SyncStatus.FAILED,
                message="GRM integration not initialized",
                error="System not initialized"
            ) for _ in grievances]
        
        return self.sync_manager.sync_grievances_batch(grievances)
    
    def get_grievance_status(self, grievance_id: str) -> Optional[Dict[str, Any]]:
        """Get grievance status from GRM system"""
        if not self.is_initialized:
            logger.warning("GRM integration not initialized, cannot get status")
            return None
        
        return self.sync_manager.get_grm_status(grievance_id)
    
    def update_grievance_status(self, grievance_id: str, status: str, notes: str = None) -> bool:
        """Update grievance status in GRM system"""
        if not self.is_initialized:
            logger.warning("GRM integration not initialized, cannot update status")
            return False
        
        return self.sync_manager.update_grievance_status(grievance_id, status, notes)
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get overall integration status"""
        return {
            'enabled': GRM_INTEGRATION_CONFIG['enabled'],
            'initialized': self.is_initialized,
            'sync_stats': self.sync_manager.get_sync_stats(),
            'last_sync_time': self.sync_manager.last_sync_time.isoformat() if self.sync_manager.last_sync_time else None
        }
    
    def cleanup(self):
        """Cleanup integration resources"""
        self.sync_manager.cleanup()
        self.is_initialized = False

# Global orchestrator instance
_grm_orchestrator: Optional[GRMIntegrationOrchestrator] = None

def get_grm_orchestrator() -> GRMIntegrationOrchestrator:
    """Get or create global GRM orchestrator"""
    global _grm_orchestrator
    if _grm_orchestrator is None:
        _grm_orchestrator = GRMIntegrationOrchestrator()
    return _grm_orchestrator

def initialize_grm_integration() -> bool:
    """Initialize GRM integration system"""
    orchestrator = get_grm_orchestrator()
    return orchestrator.initialize()

def cleanup_grm_integration():
    """Cleanup GRM integration resources"""
    global _grm_orchestrator
    if _grm_orchestrator:
        _grm_orchestrator.cleanup()
        _grm_orchestrator = None

if __name__ == "__main__":
    # Test GRM integration
    print("=== GRM Integration Test ===")
    
    # Initialize integration
    orchestrator = get_grm_orchestrator()
    
    print("Initializing GRM integration...")
    if orchestrator.initialize():
        print("✅ GRM integration initialized successfully")
        
        # Test with sample grievance data
        sample_grievance = {
            'grievance_id': 'TEST-001',
            'user_full_name': 'Test User',
            'user_contact_phone': '+9771234567890',
            'user_contact_email': 'test@example.com',
            'grievance_details': 'This is a test grievance',
            'grievance_location': 'Kathmandu',
            'classification_status': 'pending'
        }
        
        print("\nTesting grievance sync...")
        result = orchestrator.process_grievance(sample_grievance)
        print(f"Sync result: {result.status.value}")
        print(f"Message: {result.message}")
        
        # Get integration status
        status = orchestrator.get_integration_status()
        print(f"\nIntegration status: {status}")
        
    else:
        print("❌ GRM integration initialization failed")
    
    # Cleanup
    cleanup_grm_integration() 