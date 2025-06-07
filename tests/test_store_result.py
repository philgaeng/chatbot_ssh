import unittest
from actions_server.db_manager import DatabaseManagers

db_manager = DatabaseManagers()

class TestExtractStoreResultToDbTask(unittest.TestCase):
    
    def setUp(self):
        self.retry_count = 0
        # Define test inputs
        self.test_inputs = [
            {'status': 'SUCCESS', 'operation': 'classification', 'entity_key': 'transcription_id', 'id': '3610a7b8-e95d-4412-b54b-a12b6834f7e5', 'task_id': '3f3ca06d-4505-4461-85b5-75c3ec9af1fb', 'grievance_id': 'GR-20250605-KO-JH-5707', 'values': {'grievance_summary': 'Il y a trop de poussière à cause des travaux routiers, ce qui provoque des problèmes de santé aux enfants. Mais, le manque d\'argent pose problème pour les soins médicaux.', 'grievance_categories': ['Environmental - Air Pollution'], 'grievance_details': 'Il y a de la poussière partout, je dois emmener les enfants à l\'hôpital, je ne sais pas comment payer parce que je n\'ai pas d\'argent.'}, 'language_code': 'fr', 'user_id': 'US-20250605-KO-JH-BDCC', 'user_province': 'Koshi', 'user_district': 'Jhapa'},
            {'status': 'SUCCESS', 'operation': 'contact_info', 'entity_key': 'user_id', 'id': 'US-20250605-KO-JH-BDCC', 'language_code': 'fr', 'task_id': 'b21b02a5-fc67-4f34-ae7c-4ba1133e0371', 'grievance_id': 'GR-20250605-KO-JH-5707', 'user_id': 'US-20250605-KO-JH-BDCC', 'values': {'user_village': 'Nom du village de l\'utilisateur'}, 'user_province': 'Koshi', 'user_district': 'Jhapa'},
            {'status': 'SUCCESS', 'operation': 'contact_info', 'entity_key': 'user_id', 'id': 'US-20250605-KO-JH-BDCC', 'language_code': 'fr', 'task_id': '82c2d11b-cc47-4d6e-8d48-997ab32f1f3b', 'grievance_id': 'GR-20250605-KO-JH-5707', 'user_id': 'US-20250605-KO-JH-BDCC', 'values': {'user_municipality': 'value'}, 'user_province': 'Koshi', 'user_district': 'Jhapa'},
            {'status': 'SUCCESS', 'operation': 'transcription', 'field_name': 'user_village', 'values': {'user_village': 'Recording started.'}, 'file_path': 'uploads/GR-20250605-KO-JH-5707/user_village.webm', 'language_code': 'fr', 'task_id': '22c3e0ac-91bf-4036-9c6c-c651d8a986cf', 'entity_key': 'transcription_id', 'id': '22c3e0ac-91bf-4036-9c6c-c651d8a986cf', 'grievance_id': 'GR-20250605-KO-JH-5707', 'recording_id': '5def406e-632b-496e-9652-d3c74ca01cac', 'user_id': 'US-20250605-KO-JH-BDCC', 'user_province': 'Koshi', 'user_district': 'Jhapa'},
            {'status': 'SUCCESS', 'operation': 'contact_info', 'entity_key': 'user_id', 'id': 'US-20250605-KO-JH-BDCC', 'language_code': 'fr', 'task_id': '1bc8f67a-4054-4654-b0fe-cd6b880b32ad', 'grievance_id': 'GR-20250605-KO-JH-5707', 'user_id': 'US-20250605-KO-JH-BDCC', 'values': {'user_address': 'Le 21 août d\'une week.'}, 'user_province': 'Koshi', 'user_district': 'Jhapa'},
            {'status': 'SUCCESS', 'operation': 'transcription', 'field_name': 'user_contact_phone', 'values': {'user_contact_phone': 'Recording started. 0 9 8 7 6 5 4 3 2'}, 'file_path': 'uploads/GR-20250605-KO-JH-5707/user_contact_phone.webm', 'language_code': 'fr', 'task_id': 'f11248e5-d11c-4d09-af09-cd0744f8a8e1', 'entity_key': 'transcription_id', 'id': 'f11248e5-d11c-4d09-af09-cd0744f8a8e1', 'grievance_id': 'GR-20250605-KO-JH-5707', 'recording_id': '7d196e88-4c00-4422-9025-7e070dcac5bc', 'user_id': 'US-20250605-KO-JH-BDCC', 'user_province': 'Koshi', 'user_district': 'Jhapa'},
            {'status': 'SUCCESS', 'operation': 'transcription', 'field_name': 'grievance_details', 'values': {'grievance_details': "Il y a de la poussière partout, je dois emmener les enfants à l'hôpital, je ne sais pas comment payer parce que je n'ai pas d'argent."}, 'file_path': 'uploads/GR-20250605-KO-JH-5707/grievance_details.webm', 'language_code': 'fr', 'task_id': '3610a7b8-e95d-4412-b54b-a12b6834f7e5', 'entity_key': 'transcription_id', 'id': '3610a7b8-e95d-4412-b54b-a12b6834f7e5', 'grievance_id': 'GR-20250605-KO-JH-5707', 'recording_id': 'f31c78f1-5a9c-45a8-b53f-601921776c63', 'user_id': 'US-20250605-KO-JH-BDCC', 'user_province': 'Koshi', 'user_district': 'Jhapa'}
        ]
        
    def prepare_task_result_data_to_db(self, input_data: dict) -> dict:
        """Extract and prepare data from task results for database operations
        
        Args:
            operation: Type of database operation (user, grievance, transcription, etc.)
            result: Standardized task result data containing operation, field, value, etc.
            file_data: File metadata and context data
            
        Returns:
            dict: Prepared data ready for database operation
            
        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Validate result has required fields
        try:
            required_fields = ['status', 'entity_key', 'id', 'values', 'grievance_id', 'user_id']
            missing_fields = [field for field in required_fields if field not in input_data]
            if missing_fields:
                raise ValueError(f"Task result missing required fields: {missing_fields} in input data: {input_data}")
                
            entity_key = input_data['entity_key']
            entity_id = input_data['id']
            # Start with file_data as base
            update_data = input_data['values']
            if 'language_code' in input_data and not 'language_code' in update_data:
                update_data['language_code'] = input_data['language_code']
                
            # Add entity ID from result
            update_data[entity_key] = entity_id
            if entity_key not in ['user_id', 'grievance_id']:
                update_data['grievance_id'] = input_data['grievance_id']
                update_data['user_id'] = input_data['user_id']
                update_data['task_id'] = input_data['task_id']
            
            # Add result data based on entity key
            if entity_key == 'transcription_id':
                update_data['field_name'] = input_data['field_name']
                field_name = input_data['field_name']
                update_data['automated_transcript'] = input_data[field_name]
                # Remove the field_name entry from update_data
                del update_data[field_name]
                
            
                
            elif entity_key == 'translation_id':
                update_data['source_language'] = input_data['language_code']
                # Remove the language_code entry from update_data
                del update_data['language_code']
                
            
            return update_data
        except Exception as e:
 
            raise ValueError(f"Error in prepare_task_result_data_to_db: {str(e)}")
    


    def handle_db_operation(self, input_data: dict) -> dict:
        """Handle database operations with retroactive task record creation.
        
        This method:
        1. Creates/updates the entity in the relevant table first
        2. Then creates or updates the task record (handling retries)
        3. This solves the chicken-and-egg problem where entities need to exist before task creation
        """
        operation = 'default'
        task_name = 'unknown_task'
        try:
            update_data = self.prepare_task_result_data_to_db(input_data)
            entity_key = input_data['entity_key']
            entity_id = input_data['id']
            if not entity_key:
                raise ValueError(f"Missing entity key in input data: {input_data}")
            if not db_manager.task.is_valid_entity_key(entity_key):
                raise ValueError(f"Invalid entity key: {entity_key} in input data: {input_data}")
            
            operation = entity_key.split('_')[0]
            task_name = f"{operation}_task"
            
            # STEP 1: Create/update the entity first
            if entity_key == 'user_id':
                actual_entity_id = db_manager.user.create_or_update_user(update_data)
            elif entity_key == 'grievance_id':
                actual_entity_id = db_manager.grievance.create_or_update_grievance(update_data)
            elif entity_key == 'recording_id':
                actual_entity_id = db_manager.recording.create_or_update_recording(update_data)
            elif entity_key == 'transcription_id':
                actual_entity_id = db_manager.transcription.create_or_update_transcription(update_data)
            elif entity_key == 'translation_id':
                actual_entity_id = db_manager.translation.create_or_update_translation(update_data)
            else:
                raise ValueError(f"Unsupported entity_key: {entity_key}")
            
            if not actual_entity_id:
                raise ValueError(f"Failed to create/update entity for {entity_key}")
            
            # STEP 2: Handle task record creation/update (including retry scenarios)
            task_id = input_data.get('task_id')  # Get original task ID from input_data
            if task_id:

                if self.retry_count == 0:

                    # FIRST EXECUTION: Create new task record
                    created_task_id = db_manager.task.create_task(
                        task_id=task_id,
                        task_name=task_name,
                        entity_key=entity_key,
                        entity_id=actual_entity_id
                    )
                    
                    if not created_task_id:
                        raise ValueError(f"Failed to create task record even after entity creation")
                    
                # Update task status 
                status_code = 'SUCCESS' if input_data.get('status') == 'SUCCESS' else 'FAILED'
                error_message = input_data.get('error') if status_code == 'FAILED' else None
                
                # db_manager.task.update_task(
                #     task_id,
                #     {
                #         'status_code': status_code,
                #         'result': json.dumps(input_data.get('value', {})),
                #         'error_message': error_message,
                #         # 'retry_count': self.retry_count  # First execution
                #     }
                # )
                
                # self.monitoring.log_task_event(
                #     task_name,
                #     'first_execution_completed',
                #     {
                #         'entity_key': entity_key,
                #         'entity_id': actual_entity_id,
                #         'task_id': task_id,
                #         'status': status_code,
                #         # 'retry_count': self.retry_count,
                #     },
                #     # service=self.service
                # )
            
            result = {
                'status': 'SUCCESS',
                'operation': operation,
                'entity_key': entity_key,
                'entity_id': actual_entity_id,
                'task_id': task_id,
                # 'retry_count': self.retry_count,
            }
            
            return result
            
        except Exception as e:
            error_msg = f"Error in {operation} operation: {str(e)}"
            # self.monitoring.log_task_event(
            #     task_name,
            #     'operation_failed',
            #     {
            #         'entity_key': input_data.get('entity_key', 'unknown'),
            #         'entity_id': input_data.get('id', 'unknown'),
            #         'task_id': input_data.get('task_id', 'unknown'),
            #         'error': error_msg,
            #         'note': 'Database operation failed'
            #     },
            #     service=self.service
            # )
            return {'status': 'error', 'error': error_msg}

    def test_store_result_to_db_task(self):
        # Mock the TaskManager and extract_contact_info function

        for input_data in self.test_inputs:
            with self.subTest(input_data=input_data):
                result = self.handle_db_operation(input_data)
                self.assertEqual(result['status'], 'SUCCESS')

        list_of_values = []
        for input_data in self.test_inputs:
            list_of_values.append(input_data['values'])
        dic_of_values = {}  # Initialize as an empty dictionary
        existing_keys = []
        for i in list_of_values:
            k, v = list(i.items())[0]
            if k not in existing_keys:
                existing_keys.append(k)
                dic_of_values[k] = v  # Correctly assign values to the dictionary
        print(dic_of_values)
        list_of_all_fields = ['grievance_summary', 'grievance_categories', 'grievance_details', 'user_full_name', 'user_contact_phone', 'user_contact_email', 'user_province', 'user_district', 'user_municipality', 'user_village', 'user_address']
        list_of_fields = [i for i in list_of_all_fields if i in dic_of_values.keys()]
        print("list of fields to analyze: ", list_of_fields)

        grievance_details = db_manager.grievance.get_grievance_details(input_data['grievance_id'])
        for i in list_of_fields:
            self.assertEqual(grievance_details[i], dic_of_values[i])
        
        
                


if __name__ == '__main__':
    unittest.main()