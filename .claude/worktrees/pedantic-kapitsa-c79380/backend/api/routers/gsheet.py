"""
Gsheet monitoring router. Same URL surface and behaviour as Flask blueprint.
Route: GET /gsheet-get-grievances with Bearer auth.
"""

import os
from typing import Optional

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from backend.services.database_services.postgres_services import db_manager

router = APIRouter()

GSHEET_BEARER_TOKEN = os.getenv("GSHEET_BEARER_TOKEN")


def _is_valid_office_user(username: str) -> bool:
    """Check if the username is a valid office user."""
    try:
        if username in ("pd_office", "adb_hq", "Adb_hq"):
            return True
        query = "SELECT 1 FROM office_user WHERE us_unique_id = %s AND user_status = 'active'"
        result = db_manager.execute_query(query, (username,), "check_office_user")
        return len(result) > 0
    except Exception:
        return False


def _verify_auth(authorization: Optional[str] = Header(None)) -> Optional[JSONResponse]:
    """Verify Bearer token or office username. Returns None if valid, else error response."""
    if not authorization:
        return JSONResponse(
            status_code=403,
            content={"status": "failed", "message": "Invalid token or username"},
        )
    if authorization == f"Bearer {GSHEET_BEARER_TOKEN}":
        return None
    if authorization.startswith("Bearer "):
        username = authorization.replace("Bearer ", "")
        if _is_valid_office_user(username):
            return None
    return JSONResponse(
        status_code=403,
        content={"status": "failed", "message": "Invalid token or username"},
    )


@router.get("/gsheet-get-grievances")
def get_grievances(
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    """Get grievances for Google Sheets monitoring. Same behaviour as Flask."""
    auth_error = _verify_auth(authorization)
    if auth_error:
        return auth_error

    try:
        username = None
        if authorization and authorization.startswith("Bearer "):
            username = authorization.replace("Bearer ", "")

        grievances = db_manager.gsheet.get_grievances_for_gsheet(
            status=status,
            start_date=start_date,
            end_date=end_date,
            username=username,
        )

        response_data = {
            "count": len(grievances),
            "data": grievances,
        }
        return {
            "status": "SUCCESS",
            "message": "Grievances retrieved successfully",
            "data": response_data,
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "failed", "message": str(e)},
        )
