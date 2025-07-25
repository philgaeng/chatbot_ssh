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
    
    # Sensitive fields that should be encrypted
    ENCRYPTED_FIELDS = {
        'complainant_phone',
        'complainant_email', 
        'complainant_address',
        'complainant_full_name'
    }
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Get encryption key from environment variable
        self.encryption_key = os.getenv('DB_ENCRYPTION_KEY')
        if not self.encryption_key:
            self.logger.warning("DB_ENCRYPTION_KEY not set - encryption will be disabled")
        else:
            self.logger.info("Encryption enabled for sensitive fields")
    
    def _encrypt_field(self, value: str) -> Optional[str]:
        """Encrypt a field value using pgcrypto"""
        if not value or not self.encryption_key:
            return value
        
        try:
            query = "SELECT pgp_sym_encrypt(%s, %s)"
            result = self.execute_query(query, (value, self.encryption_key), "encrypt_field")
            return result[0]['pgp_sym_encrypt'] if result else value
        except Exception as e:
            self.logger.error(f"Error encrypting field: {str(e)}")
            return value
    
    def _decrypt_field(self, encrypted_value: str) -> Optional[str]:
        """Decrypt a field value using pgcrypto"""
        if not encrypted_value or not self.encryption_key:
            return encrypted_value
        
        try:
            query = "SELECT pgp_sym_decrypt(%s::bytea, %s)"
            result = self.execute_query(query, (encrypted_value, self.encryption_key), "decrypt_field")
            return result[0]['pgp_sym_decrypt'] if result else encrypted_value
        except Exception as e:
            self.logger.error(f"Error decrypting field: {str(e)}")
            return encrypted_value
    
    def _encrypt_complainant_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt sensitive fields in complainant data"""
        encrypted_data = data.copy()
        for field in self.ENCRYPTED_FIELDS:
            if field in encrypted_data and encrypted_data[field]:
                encrypted_data[field] = self._encrypt_field(encrypted_data[field])
                if field == 'complainant_phone':
                    self.logger.debug(f"encrypted phone number {data[field]} at encrypt_complainant_data: {encrypted_data[field].tobytes().hex()}")
        return encrypted_data
    
    def _decrypt_complainant_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt sensitive fields in complainant data"""
        decrypted_data = data.copy()
        for field in self.ENCRYPTED_FIELDS:
            if field in decrypted_data and decrypted_data[field]:
                decrypted_data[field] = self._decrypt_field(decrypted_data[field])
        return decrypted_data

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
        search_phone = self._encrypt_phone_number(phone_number) if self.encryption_key else phone_number
        self.logger.debug(f"encrypted phone number: {search_phone}")
        
        query = """
            SELECT complainant_id, complainant_unique_id, complainant_full_name, complainant_phone,
                   complainant_email, complainant_province, complainant_district,
                   complainant_municipality, complainant_ward, complainant_village, complainant_address,
                   created_at
            FROM complainants
            WHERE complainant_phone = %s
            ORDER BY created_at DESC
        """
        try:
            results = self.execute_query(query, (search_phone,), "get_complainants_by_phone_number")
            # Decrypt sensitive fields in results
            decrypted_results = []
            self.logger.debug(f"{len(results)} complainants found")
            self.logger.debug(f"results: {results}")
            for complainant in results:
                decrypted_results.append(self._decrypt_complainant_data(complainant))
            self.logger.debug(f"{len(decrypted_results)} complainants successfully decrypted")
            self.logger.debug(f"decrypted results: {decrypted_results}")
            return decrypted_results
        except Exception as e:
            self.logger.error(f"Error retrieving complainants by phone number: {str(e)}")
            return []
            
    def get_complainant_by_id(self, complainant_id: int) -> Optional[Dict[str, Any]]:
        query = """
            SELECT complainant_id, complainant_unique_id, complainant_full_name, complainant_phone,
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
                return self._decrypt_complainant_data(results[0])
            return None
        except Exception as e:
            self.logger.error(f"Error retrieving complainant by complainant_id: {str(e)}")
            return None

    def create_complainant(self, data: Dict[str, Any]) -> bool:
        """Create a new complainant record with encrypted sensitive fields"""
        try:
            complainant_id = data.get('complainant_id')
            self.logger.info(f"create_complainant: Creating complainant with ID: {complainant_id}")
            
            # Encrypt sensitive fields before storing
            encrypted_data = self._encrypt_complainant_data(data)
            
            insert_query = """
                    INSERT INTO complainants (
                        complainant_id, complainant_unique_id, complainant_full_name,
                        complainant_phone, complainant_email,
                        complainant_province, complainant_district, complainant_municipality,
                        complainant_ward, complainant_village, complainant_address
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING complainant_id
                """
            self.execute_insert(insert_query, (
                complainant_id,
                complainant_id,  # Use same ID for complainant_unique_id
                    encrypted_data.get('complainant_full_name'),
                    encrypted_data.get('complainant_phone'),
                    encrypted_data.get('complainant_email'),
                    encrypted_data.get('complainant_province'),
                    encrypted_data.get('complainant_district'),
                    encrypted_data.get('complainant_municipality'),
                    encrypted_data.get('complainant_ward'),
                    encrypted_data.get('complainant_village'),
                    encrypted_data.get('complainant_address')
                ))
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
    
    def update_complainant(self, complainant_id: str, data: Dict[str, Any]) -> bool:
        """Update an existing complainant record with encrypted sensitive fields"""
        try:
            self.logger.info(f"update_complainant: Updating complainant with ID: {complainant_id}")
            
            # Encrypt sensitive fields before storing
            encrypted_data = self._encrypt_complainant_data(data)
            
            update_query = """
                    UPDATE complainants 
                    SET complainant_full_name = %s,
                        complainant_phone = %s,
                        complainant_email = %s,
                        complainant_province = %s,
                        complainant_district = %s,
                        complainant_municipality = %s,
                        complainant_ward = %s,
                        complainant_village = %s,
                        complainant_address = %s
                    WHERE complainant_id = %s
                    RETURNING complainant_id
                """
            self.execute_update(update_query, (
                    encrypted_data.get('complainant_full_name'),
                    encrypted_data.get('complainant_phone'),
                    encrypted_data.get('complainant_email'),
                    encrypted_data.get('complainant_province'),
                    encrypted_data.get('complainant_district'),
                    encrypted_data.get('complainant_municipality'),
                    encrypted_data.get('complainant_ward'),
                    encrypted_data.get('complainant_village'),
                    encrypted_data.get('complainant_address'),
                    complainant_id
                ))
            self.logger.info(f"update_complainant: Updated complainant with ID: {complainant_id}, rows affected: {len(data)}")
            return True
            
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
                return self._decrypt_complainant_data(results[0])
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