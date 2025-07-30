import uuid
import logging
import os
from typing import Dict, List, Optional, Any
import traceback
from icecream import ic
from .base_manager import BaseDatabaseManager
from rapidfuzz import process


class ComplainantDbManager(BaseDatabaseManager):
    """Handles complainant CRUD and lookup logic with field-level encryption"""
    
    # Whitelist of fields that can be updated
    ALLOWED_UPDATE_FIELDS = {
        'complainant_full_name',
        'complainant_phone',
        'complainant_email',
        'complainant_province',
        'complainant_district',
        'complainant_municipality',
        'complainant_ward',
        'complainant_village',
        'complainant_address'
    }
    
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Get encryption key from environment variable
        self.encryption_key = os.getenv('DB_ENCRYPTION_KEY')
        self.ENCRYPTED_FIELDS = {
            'complainant_phone',
            'complainant_email', 
            'complainant_full_name',
            'complainant_address'
        }
        self.HASHED_FIELDS = {
        'complainant_phone',
        'complainant_email', 
        'complainant_full_name'
    }

    


    def _encrypt_phone_number(self, phone_number: str) -> str:
        """Encrypt a phone number using pgcrypto"""
        if self.encryption_key:
            encrypted_phone_number = self._encrypt_field(phone_number)
            if isinstance(encrypted_phone_number, memoryview):
            # Try to decode as utf-8, or use .hex() if it's binary
                try:
                    encrypted_phone_number = encrypted_phone_number.tobytes().decode('utf-8')
                    self.logger.debug(f"encrypted phone number as utf-8: {encrypted_phone_number}")
                except UnicodeDecodeError:
                    encrypted_phone_number = encrypted_phone_number.tobytes().hex()
                    self.logger.debug(f"encrypted phone number as hex: {encrypted_phone_number}")
            return encrypted_phone_number
        else:
            self.logger.error("Encryption key not set")



    def get_complainants_by_phone_number(self, phone_number: str) -> List[Dict[str, Any]]:
        # Encrypt the phone number for search if encryption is enabled
        self.logger.debug(f"original phone number: {phone_number}")
        standardized_phone = self._standardize_phone_number(phone_number)
        search_phone = self._hash_value(standardized_phone) if self.encryption_key else standardized_phone
        self.logger.debug(f"hashed phone number: {search_phone}")
        
        # Add debug logging to track the hash
        self.logger.debug(f"Phone number '{standardized_phone}' hashed to '{search_phone}' in search")
        
        query = """
            SELECT complainant_id, complainant_unique_id, complainant_full_name, complainant_phone,
                   complainant_email, complainant_province, complainant_district,
                   complainant_municipality, complainant_ward, complainant_village, complainant_address,
                   created_at
            FROM complainants
            WHERE complainant_phone_hash = %s
            ORDER BY created_at DESC
        """
        try:
            self.logger.debug(f"search_phone at query time: {search_phone}")
            results = self.execute_query(query, (search_phone,), "get_complainants_by_phone_number")
            # Decrypt sensitive fields in results
            decrypted_results = []
            self.logger.debug(f"{len(results)} complainants found")
            self.logger.debug(f"results: {results}")
            for complainant in results:
                decrypted_results.append(self._decrypt_sensitive_data(complainant))
            self.logger.debug(f"{len(decrypted_results)} complainants successfully decrypted")
            self.logger.debug(f"decrypted results: {decrypted_results}")
            return decrypted_results
        except Exception as e:
            self.logger.error(f"Error retrieving complainants by phone number: {str(e)}")
            return []
            
    def get_complainant_by_id(self, complainant_id: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT complainant_id, complainant_unique_id, complainant_full_name,    complainant_phone,
                   complainant_email, complainant_province, complainant_district,
                   complainant_municipality, complainant_ward, complainant_village, complainant_address,
                   created_at
            FROM complainants
            WHERE complainant_id = %s
        """
        try:
            results = self.execute_query(query, (complainant_id,), "get_complainant_by_id")
            if results:
                # Decrypt sensitive fields in result
                return self._decrypt_sensitive_data(results[0])
            return None
        except Exception as e:
            self.logger.error(f"Error retrieving complainant by complainant_id: {str(e)}")
            return None

    def create_complainant(self, data: Dict[str, Any]) -> bool:
        """Create a new complainant record with encrypted sensitive fields"""
        try:
            complainant_id = data.get('complainant_id') or self.generate_id('complainant_id')
            data['complainant_id'] = complainant_id
            data['complainant_unique_id'] = complainant_id #complainant_unique_id is the same as complainant_id for now
            self.logger.info(f"create_complainant: Creating complainant with ID: {complainant_id}")
            allowed_fields = ['complainant_id', 'complainant_unique_id', 'complainant_full_name', 'complainant_phone', 'complainant_email', 'complainant_province', 'complainant_district', 'complainant_municipality', 'complainant_ward', 'complainant_village', 'complainant_address']

            data = {k: v for k, v in data.items() if k in allowed_fields}

            if data.get('complainant_phone'):
                data['complainant_phone'] = self._standardize_phone_number(data['complainant_phone'])

            input_data = self._encrypt_and_hash_sensitive_data(data) #manage encryption and hashing when required
                    
            #execute the upsert query
            result = self.execute_insert(table_name='complainants', input_data=input_data)
            self.logger.info(f"create_complainant: Successfully created complainant with ID: {complainant_id}")
            return True

        except Exception as e:
            if not complainant_id:
                self.logger.error(f"Missing complainant_id: {str(e)}")
                self.logger.error(f"Traceback: {traceback.format_exc()}")
            else:
                self.logger.error(f"Error in create_complainant: {str(e)}")
                self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def update_complainant(self, complainant_id: str, data: Dict[str, Any]) -> int:
        """Update an existing complainant record with encrypted sensitive fields"""
        try:
            self.logger.info(f"update_complainant: Updating complainant with ID: {complainant_id}")
            allowed_fields = ['complainant_full_name', 'complainant_phone', 'complainant_email', 'complainant_province', 'complainant_district', 'complainant_municipality', 'complainant_ward', 'complainant_village', 'complainant_address']
            # ensure the phone number is standardized
            if data.get('complainant_phone'):
                data['complainant_phone'] = self._standardize_phone_number(data['complainant_phone'])
            #ensure the data is within the allowed fields
            input_data = self.select_query_data(data, allowed_fields)
            # Encrypt sensitive fields before storing
            encrypted_data = self._encrypt_and_hash_sensitive_data(input_data)
            self.logger.debug(f"encrypted_data at update_complainant: {encrypted_data}")
            #prepare the query
            set_clause = ', '.join([f'{k} = %s' for k in encrypted_data.keys()])
            query = f"UPDATE complainants SET {set_clause} WHERE complainant_id = %s"
            values = tuple(encrypted_data.values()) + (complainant_id,)
            #execute the update query
            affected_rows = self.execute_update(query, values)
            return affected_rows  # Just return True if any rows were updated
            
        except Exception as e:
            self.logger.error(f"Error in update_complainant: {str(e)}")
            return False
        
    def get_complainant_from_grievance_id(self, grievance_id: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT c.*
            FROM complainants c
            JOIN grievances g ON c.complainant_id = g.complainant_id
            WHERE g.grievance_id = %s
        """
        try:
            results = self.execute_query(query, (grievance_id,), "get_complainant_from_grievance_id")
            if results:
                # Decrypt sensitive fields in result
                return self._decrypt_sensitive_data(results[0])
            return None
        except Exception as e:
            self.logger.error(f"Error retrieving complainant from grievance complainant_id: {str(e)}")
            return None
        
    def get_complainant_id_from_grievance_id(self, grievance_id: str) -> Optional[str]:
        query = """
            SELECT complainant_id
            FROM grievances
            WHERE grievance_id = %s
        """
        try:
            results = self.execute_query(query, (grievance_id,), "get_complainant_id_from_grievance_id")
            return results[0]['complainant_id'] if results else None
        except Exception as e:
            self.logger.error(f"Error retrieving complainant from grievance_id: {str(e)}")
            return None
        
    #create a function to merge different complainants with same phone number
    def merge_complainants_with_same_phone_number(self, complainant_id: int, target_complainant_id: int) -> bool:
        query = """
            UPDATE grievances
            SET complainant_id = %s
            WHERE complainant_id = %s
        """
        try:
            self.execute_update(query, (target_complainant_id, complainant_id), "merge_complainants_with_same_phone_number")
            return True
        except Exception as e:
            self.logger.error(f"Error merging complainants with same phone number: {str(e)}")
            return False
        

        
        
    def check_and_merge_complainants_by_phone_number(self, phone_number: str) -> Dict[str, Any]:
        """
        Check and merge complainants with same phone number
        Args:
            phone_number: The phone number to check and merge complainants for
        Returns:
            MERGE_SUCCESS: if check and merge was successful, 
            MERGE_FAIL: if complainants were found but merge failed
            MANUAL_REVIEW_REQUIRED: if complainants were found but manual review is required
            NO_USERS_FOUND: if no complainants with same phone number were found
            ERROR_UNKNOWN_PHONE_NUMBER: if there was an error with the phone number
        """
        try:
            complainants = self.get_complainants_by_phone_number(phone_number)
            if len(complainants) ==0:
                return {
                    'result': 'ERROR_UNKNOWN_PHONE_NUMBER',
                    'merged_complainants': [],
                    'merge_failed_complainants': [],
                    'manual_review_complainants': []
                }
            elif len(complainants) == 1:
                return {
                    'result': 'NO_USERS_FOUND',
                    'merged_complainants': [],
                    'merge_failed_complainants': [],
                    'manual_review_complainants': []
                }
            else:
                list_merged_complainants = []
                list_merge_failed_complainants = []
                list_manual_review_complainants = []
                complainant_names = [complainants['complainant_full_name'] for complainants in complainants]
                for i in range(len(complainant_names)):
                    for j in range(i+1, len(complainant_names)):
                        match_ratio = process.extractOne(complainant_names[i], complainant_names[j])
                        if match_ratio[1] > 90:
                            try:
                                self.merge_complainants_with_same_phone_number(complainants[i]['complainant_unique_id'], complainants[j]['complainant_unique_id'])
                                list_merged_complainants.append(complainants[i]['complainant_unique_id'])
                                list_merged_complainants.append(complainants[j]['complainant_unique_id'])
                            except Exception as e:
                                list_merge_failed_complainants.append(complainants[i]['complainant_unique_id'])
                                list_merge_failed_complainants.append(complainants[j]['complainant_unique_id'])
                        if match_ratio[1] >70:
                            list_manual_review_complainants.append(complainants[i]['complainant_unique_id'])
                            list_manual_review_complainants.append(complainants[j]['complainant_unique_id'])
                        else:
                            pass
                
                #prepare the response
                list_merged_complainants = list(set(list_merged_complainants))
                list_merge_failed_complainants = list(set(list_merge_failed_complainants))
                list_manual_review_complainants = list(set(list_manual_review_complainants))
                response = {
                    'merged_complainants': list_merged_complainants,
                    'merge_failed_complainants': list_merge_failed_complainants,
                    'manual_review_complainants': list_manual_review_complainants
                }
                if len(list_merged_complainants) + len(list_merge_failed_complainants) + len(list_manual_review_complainants) > 0:
                    response['result'] = 'MERGE_SUCCESS'
                    return response
                else:
                    response['result'] = 'MERGE_FAIL'
                    response['error'] = 'No complainants found'
                    return response
        except Exception as e:
            self.logger.error(f"Error checking and merging complainants by phone number: {str(e)}")
            return {
                'result': 'FAILED',
                'error': 'Error checking and merging complainants by phone number',
                'merged_complainants': [],
                'merge_failed_complainants': [],
                'manual_review_complainants': []
            }