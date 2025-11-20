import eventlet
eventlet.monkey_patch()

from flask import Flask, request, jsonify
from flask_cors import CORS
from backend.api.channels_api import FileServerAPI
from backend.services.file_server_core import FileServerCore
from backend.services.accessible.voice_grievance import voice_grievance_bp
from backend.api.websocket_utils import socketio, emit_status_update_accessible, SOCKETIO_PATH
from backend.config.constants import ALLOWED_EXTENSIONS
from backend.api.gsheet_monitoring_api import gsheet_monitoring_bp
from backend.services.database_services.grievance_manager import GrievanceDbManager
from backend.services.messaging import Messaging
from backend.config.constants import EMAIL_TEMPLATES, DIC_SMS_TEMPLATES
import os
from backend.logger.logger import TaskLogger
from flask_socketio import join_room, rooms

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
socketio.init_app(app, path=SOCKETIO_PATH)

# Initialize core and API instances
file_server_core = FileServerCore(
    upload_folder=os.getenv('UPLOAD_FOLDER', 'uploads'),
    allowed_extensions=ALLOWED_EXTENSIONS
)
file_server = FileServerAPI(core=file_server_core)
grievance_manager = GrievanceDbManager()
messaging_service = Messaging()

# Register blueprints
app.register_blueprint(file_server.blueprint)
app.register_blueprint(voice_grievance_bp)
app.register_blueprint(gsheet_monitoring_bp)

# Make the function available to the file_server blueprint
file_server.blueprint.emit_status_update_accessible = emit_status_update_accessible

# === Add these handlers here ===

logger = TaskLogger(service_name='socketio').logger

def log_event(event, data):
    logger.log_event(f"[SOCKETIO] Event: {event}, Data: {data}")

@socketio.on('status_update')
def handle_status_update(data):
    log_event('status_update', data)
    # Re-emit the event to ensure the client receives it
    socketio.emit('status_update', data, room=data.get('session_id', request.sid))
    logger.info("Re-emitted status update to client", extra_data={"data": data})

@socketio.on('another_event')
def handle_another_event(data):
    log_event('another_event', data)

@socketio.on_error()
def error_handler(e):
    logger.error(f"[SOCKETIO] Error: {e}")

@socketio.on('join_room')
def on_join_room(data):
    room = data.get('room')
    if room:
        join_room(room)
        print(f"Client {request.sid} joined room: {room}")
        print(f"Rooms for {request.sid}: {rooms(request.sid)}")
        # Confirm to client
        socketio.emit('room_joined', room, room=request.sid)

# === End handlers ===

# === Grievance API Endpoints ===

@app.route('/api/grievance/<grievance_id>/status', methods=['POST'])
def update_grievance_status(grievance_id):
    """
    Update the status of a specific grievance
    
    Args:
        grievance_id (str): The ID of the grievance to update
        
    Request Body:
        {
            "status_code": "RESOLVED",
            "notes": "Issue has been resolved",
            "created_by": "office_user_id"
        }
        
    Returns:
        JSON response with success/error status
    """
    try:
        # Get request data
        data = request.get_json()
        
        if not data:
            return jsonify({"status": "ERROR", "message": "No JSON data provided"}), 400
        
        # Validate required fields
        status_code = data.get('status_code')
        if not status_code:
            return jsonify({"status": "ERROR", "message": "status_code is required"}), 400
        
        # Get optional fields
        notes = data.get('notes')
        created_by = data.get('created_by')
        
        print(f"Updating grievance {grievance_id} status to {status_code}")
        
        # Verify grievance exists
        grievance = grievance_manager.get_grievance_by_id(grievance_id)
        if not grievance:
            return jsonify({"status": "ERROR", "message": f"Grievance {grievance_id} not found"}), 404
        
        # Update the status
        success = grievance_manager.update_grievance_status(
            grievance_id=grievance_id,
            status_code=status_code,
            created_by=created_by,
            notes=notes
        )
        
        if success:
            print(f"Successfully updated grievance {grievance_id} status to {status_code}")
            
            # Send notifications
            try:
                send_status_update_notifications(grievance_id, status_code, notes, created_by)
            except Exception as e:
                print(f"Error sending notifications: {str(e)}")
                # Don't fail the request if notifications fail
            
            return jsonify({
                "status": "SUCCESS",
                "message": "Status updated successfully",
                "data": {
                    "grievance_id": grievance_id,
                    "status_code": status_code,
                    "notes": notes,
                    "created_by": created_by
                }
            }), 200
        else:
            return jsonify({"status": "ERROR", "message": "Failed to update status"}), 500
            
    except Exception as e:
        print(f"Error updating grievance status: {str(e)}")
        return jsonify({"status": "ERROR", "message": f"Internal server error: {str(e)}"}), 500

@app.route('/api/grievance/<grievance_id>', methods=['GET'])
def get_grievance(grievance_id):
    """
    Get detailed information about a specific grievance
    
    Args:
        grievance_id (str): The ID of the grievance to retrieve
        
    Returns:
        JSON response with grievance details
    """
    try:
        print(f"Retrieving grievance {grievance_id}")
        
        # Get grievance details
        grievance = grievance_manager.get_grievance_by_id(grievance_id)
        
        if not grievance:
            return jsonify({"status": "ERROR", "message": f"Grievance {grievance_id} not found"}), 404
        
        # Get status history
        status_history = grievance_manager.get_grievance_status_history(grievance_id)
        
        # Get files
        files = grievance_manager.get_grievance_files(grievance_id)
        
        # Get current status
        current_status = grievance_manager.get_grievance_status(grievance_id)
        
        response_data = {
            "grievance": grievance,
            "current_status": current_status,
            "status_history": status_history,
            "files": files
        }
        
        print(f"Successfully retrieved grievance {grievance_id}")
        return jsonify({
            "status": "SUCCESS",
            "message": "Grievance retrieved successfully",
            "data": response_data
        }), 200
        
    except Exception as e:
        print(f"Error retrieving grievance: {str(e)}")
        return jsonify({"status": "ERROR", "message": f"Internal server error: {str(e)}"}), 500

@app.route('/api/grievance/statuses', methods=['GET'])
def get_available_statuses():
    """
    Get all available grievance statuses
    
    Returns:
        JSON response with available statuses
    """
    try:
        print("Retrieving available grievance statuses")
        
        # Get available statuses
        statuses = grievance_manager.get_available_statuses()
        
        print("Successfully retrieved available statuses")
        return jsonify({
            "status": "SUCCESS",
            "message": "Available statuses retrieved successfully",
            "data": statuses
        }), 200
        
    except Exception as e:
        print(f"Error retrieving available statuses: {str(e)}")
        return jsonify({"status": "ERROR", "message": f"Internal server error: {str(e)}"}), 500

def send_status_update_notifications(grievance_id: str, status_code: str, notes: str, created_by: str):
    """
    Send email and SMS notifications when grievance status is updated
    """
    try:
        # Get grievance details
        grievance = grievance_manager.get_grievance_by_id(grievance_id)
        if not grievance:
            print(f"Grievance {grievance_id} not found for notifications")
            return
        
        # Get complainant phone for SMS
        complainant_phone = grievance.get('complainant_phone')
        
        # Get office emails for email notifications
        office_emails = grievance_manager.get_office_emails_for_grievance(grievance_id)
        
        # Prepare email data
        email_data = {
            'grievance_id': grievance_id,
            'complainant_id': grievance.get('complainant_id'),
            'grievance_status': status_code,
            'grievance_timeline': grievance.get('grievance_timeline'),
            'complainant_full_name': grievance.get('complainant_full_name'),
            'complainant_phone': complainant_phone,
            'municipality': grievance.get('complainant_municipality'),
            'village': grievance.get('complainant_village'),
            'address': grievance.get('complainant_address'),
            'grievance_details': grievance.get('grievance_description'),
            'grievance_summary': grievance.get('grievance_summary'),
            'grievance_categories': grievance.get('grievance_categories'),
            'grievance_status_update_date': grievance.get('grievance_status_update_date', 'N/A')
        }
        
        # Send email to office staff
        if office_emails:
            email_subject = EMAIL_TEMPLATES['GRIEVANCE_STATUS_UPDATE_SUBJECT']['en'].format(**email_data)
            email_body = EMAIL_TEMPLATES['GRIEVANCE_STATUS_UPDATE_BODY']['en'].format(**email_data)
            
            email_success = messaging_service.send_email(
                to_emails=office_emails,
                subject=email_subject,
                body=email_body
            )
            
            if email_success:
                print(f"Status update email sent to {len(office_emails)} office staff")
            else:
                print("Failed to send status update email")
        
        # Send SMS to complainant
        if complainant_phone:
            sms_data = {
                'grievance_id': grievance_id,
                'grievance_status': status_code,
                'grievance_timeline': grievance.get('grievance_timeline', 'N/A')
            }
            
            sms_message = DIC_SMS_TEMPLATES['GRIEVANCE_STATUS_UPDATE']['en'].format(**sms_data)
            
            sms_success = messaging_service.send_sms(
                phone_number=complainant_phone,
                message=sms_message
            )
            
            if sms_success:
                print(f"Status update SMS sent to complainant: {complainant_phone}")
            else:
                print(f"Failed to send status update SMS to {complainant_phone}")
        
    except Exception as e:
        print(f"Error in send_status_update_notifications: {str(e)}")

@app.route('/health')
def health():
    return 'OK', 200



if __name__ == '__main__':
    import eventlet
    import eventlet.wsgi
    socketio.run(app, host='0.0.0.0', port=5001)


