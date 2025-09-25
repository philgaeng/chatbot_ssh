from flask import Blueprint, request
import os
from .api_manager import APIManager
from backend.services.database_services.postgres_services import db_manager


class GSheetMonitoringAPI:
    """API routes for Google Sheets monitoring operations"""
    
    def __init__(self):
        self.blueprint = Blueprint('gsheet_monitoring', __name__)
        self.api_manager = APIManager('gsheet_monitoring')
        self._register_routes()
        self.gsheet_bearer_token = os.getenv('GSHEET_BEARER_TOKEN')
        self.db = db_manager
        self.log_event = self.api_manager.log_event
        self.STARTED = self.api_manager.STARTED
        self.SUCCESS = self.api_manager.SUCCESS
        self.FAILED = self.api_manager.FAILED


    def _register_routes(self):
        """Register all routes with the blueprint"""
        self.blueprint.route('/gsheet-get-grievances', methods=['GET'])(self.handle_request(self.get_grievances))

    def _verify_auth(self):
        """Verify the authorization token or username"""
        auth_header = request.headers.get('Authorization')
        print(f"[DEBUG] Auth header: {auth_header}")
        print(f"[DEBUG] Expected bearer token: {self.gsheet_bearer_token}")
        
        # Check for original API token authentication
        if auth_header == f"Bearer {self.gsheet_bearer_token}":
            print("[DEBUG] Valid API token authentication")
            return None  # Valid API token
        
        # Check for username-based authentication (new office authentication)
        if auth_header and auth_header.startswith('Bearer '):
            username = auth_header.replace('Bearer ', '')
            print(f"[DEBUG] Checking office user authentication for: {username}")
            # Validate that it's a known office user
            if self._is_valid_office_user(username):
                print(f"[DEBUG] Valid office user authentication for: {username}")
                return None  # Valid office user
        
        print("[DEBUG] Authentication failed")
        return self.api_manager.error_response("Invalid token or username", 403)
    
    def _is_valid_office_user(self, username):
        """Check if the username is a valid office user"""
        try:
            # Check if it's an admin user (handle both cases)
            if username in ['pd_office', 'adb_hq', 'Adb_hq']:
                return True
            
            # Check if it's a valid office user in the database
            query = "SELECT 1 FROM office_user WHERE us_unique_id = %s AND user_status = 'active'"
            result = self.db.execute_query(query, (username,), "check_office_user")
            print(f"[DEBUG] Office user check for {username}: {len(result)} rows found")
            return len(result) > 0
        except Exception as e:
            print(f"[DEBUG] Error checking office user {username}: {str(e)}")
            return False

    def handle_request(self, func):
        def wrapper(*args, **kwargs):
            try:
                self.log_event(event_type=self.STARTED, details={'args': args, 'kwargs': kwargs})
                result = func(*args, **kwargs)
                # Only log the type, not the full result
                self.log_event(event_type=self.SUCCESS, details={'result_type': str(type(result))})
                return result
            except Exception as e:
                self.log_event(event_type=self.FAILED, details={'error': str(e)})
                return self.api_manager.error_response(str(e))
        return wrapper

    def get_grievances(self):
        """Get grievances for Google Sheets monitoring"""
        # Verify authentication
        auth_error = self._verify_auth()
        print("[DEBUG] auth_error:", auth_error)
        if auth_error:
            print("[DEBUG] Returning auth_error of type:", type(auth_error))
            return auth_error

        try:
            # Get query parameters
            status = request.args.get('status')
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            
            # Get user credentials from Authorization header
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.replace('Bearer ', '')
                # For now, we'll use the token as the username
                # In production, you'd decode/validate the token properly
                username = token
            else:
                username = None

            print(f"[DEBUG] Query params: status={status}, start_date={start_date}, end_date={end_date}, username={username}")

            # Fetch grievances using database manager with user filtering
            print("[DEBUG] Calling get_grievances_for_gsheet with params:", {"status": status, "start_date": start_date, "end_date": end_date, "username": username})
            grievances = self.db.gsheet.get_grievances_for_gsheet(
                status=status,
                start_date=start_date,
                end_date=end_date,
                username=username
            )
            print("[DEBUG] grievances type:", type(grievances), "length:", len(grievances))
            if grievances:
                print("[DEBUG] First grievance sample:", grievances[0])
            else:
                print("[DEBUG] No grievances returned!")

            response_data = {
                "count": len(grievances),
                "data": grievances
            }
            print("[DEBUG] Response data structure:", response_data)
            
            response = self.api_manager.success_response(response_data, "Grievances retrieved successfully")
            print("[DEBUG] Final response type:", type(response))
            return response

        except Exception as e:
            print("[DEBUG] Exception in get_grievances:", e)
            error_response = self.api_manager.error_response(str(e))
            print("[DEBUG] error_response type:", type(error_response), error_response)
            return error_response

# Create the API instance
gsheet_monitoring = GSheetMonitoringAPI()
gsheet_monitoring_bp = gsheet_monitoring.blueprint
