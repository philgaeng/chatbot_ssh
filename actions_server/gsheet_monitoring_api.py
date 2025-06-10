from flask import Blueprint, request
import os
from actions_server.api_manager import APIManager
from actions_server.db_manager import DatabaseManagers


class GSheetMonitoringAPI:
    """API routes for Google Sheets monitoring operations"""
    
    def __init__(self):
        self.blueprint = Blueprint('gsheet_monitoring', __name__)
        self.api_manager = APIManager('gsheet_monitoring')
        self._register_routes()
        self.gsheet_bearer_token = os.getenv('GSHEET_BEARER_TOKEN')
        self.db = DatabaseManagers()

    def _register_routes(self):
        """Register all routes with the blueprint"""
        self.blueprint.route('/gsheet-get-grievances', methods=['GET'])(self.handle_request(self.get_grievances))

    def _verify_auth(self):
        """Verify the authorization token"""
        auth_header = request.headers.get('Authorization')
        if auth_header != f"Bearer {self.gsheet_bearer_token}":
            return self.api_manager.error_response("Invalid token", 403)
        return None

    def handle_request(self, func):
        def wrapper(*args, **kwargs):
            try:
                self.api_manager.log_event('started', {'args': args, 'kwargs': kwargs})
                result = func(*args, **kwargs)
                # Only log the type, not the full result
                self.api_manager.log_event('completed', {'result_type': str(type(result))})
                return result
            except Exception as e:
                self.api_manager.log_event('failed', {'error': str(e)})
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

            print(f"[DEBUG] Query params: status={status}, start_date={start_date}, end_date={end_date}")

            # Fetch grievances using database manager
            grievances = self.db.gsheet.get_grievances_for_gsheet(
                status=status,
                start_date=start_date,
                end_date=end_date
            )
            print("[DEBUG] grievances type:", type(grievances), "length:", len(grievances))

            response = self.api_manager.success_response({
                "count": len(grievances),
                "data": grievances
            }, "Grievances retrieved successfully")
            print("[DEBUG] response type:", type(response), response)
            return response

        except Exception as e:
            print("[DEBUG] Exception in get_grievances:", e)
            error_response = self.api_manager.error_response(str(e))
            print("[DEBUG] error_response type:", type(error_response), error_response)
            return error_response

# Create the API instance
gsheet_monitoring = GSheetMonitoringAPI()
gsheet_monitoring_bp = gsheet_monitoring.blueprint
