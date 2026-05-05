"""
Grievance API router. Same URL surface and behaviour as Flask backend.
"""

import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from psycopg2 import sql

from backend.config.constants import EMAIL_TEMPLATES, DIC_SMS_TEMPLATES
from backend.services.database_services.grievance_manager import GrievanceDbManager
from backend.services.messaging_http_dispatch import (
    grievance_dispatch_send_email,
    grievance_dispatch_send_sms,
)

router = APIRouter()

grievance_manager = GrievanceDbManager()


# --- Request/response models (preserve Flask response structure) ---


class UpdateStatusBody(BaseModel):
    status_code: str = Field(..., description="New status code")
    notes: Optional[str] = None
    created_by: Optional[str] = None


class ComplainantPatchBody(BaseModel):
    complainant_address: Optional[str] = None
    complainant_village: Optional[str] = None
    complainant_ward: Optional[str] = None
    complainant_municipality: Optional[str] = None
    complainant_district: Optional[str] = None
    complainant_province: Optional[str] = None
    complainant_email: Optional[str] = None


def _ticketing_auth_check(x_api_key: Optional[str] = Header(default=None)) -> None:
    expected = os.environ.get("TICKETING_SECRET_KEY", "")
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")


def _send_status_update_notifications(
    grievance_id: str,
    status_code: str,
    notes: Optional[str],
    created_by: Optional[str],
) -> None:
    """Send email and SMS on status update via messaging API (or inprocess — see messaging_http_dispatch)."""
    try:
        grievance = grievance_manager.get_grievance_by_id(grievance_id)
        if not grievance:
            print(f"Grievance {grievance_id} not found for notifications")
            return

        complainant_phone = grievance.get("complainant_phone")
        office_emails = grievance_manager.get_office_emails_for_grievance(grievance_id)

        email_data: Dict[str, Any] = {
            "grievance_id": grievance_id,
            "complainant_id": grievance.get("complainant_id"),
            "grievance_status": status_code,
            "grievance_timeline": grievance.get("grievance_timeline"),
            "complainant_full_name": grievance.get("complainant_full_name"),
            "complainant_phone": complainant_phone,
            "municipality": grievance.get("complainant_municipality"),
            "village": grievance.get("complainant_village"),
            "address": grievance.get("complainant_address"),
            "grievance_details": grievance.get("grievance_description"),
            "grievance_summary": grievance.get("grievance_summary"),
            "grievance_categories": grievance.get("grievance_categories"),
            "grievance_status_update_date": grievance.get("grievance_status_update_date", "N/A"),
        }

        if office_emails:
            email_subject = EMAIL_TEMPLATES["GRIEVANCE_STATUS_UPDATE_SUBJECT"]["en"].format(**email_data)
            email_body = EMAIL_TEMPLATES["GRIEVANCE_STATUS_UPDATE_BODY"]["en"].format(**email_data)
            ctx = {
                "source_system": "ticketing",
                "purpose": "grievance_status_update",
                "grievance_id": grievance_id,
            }
            email_success = grievance_dispatch_send_email(
                office_emails,
                email_subject,
                email_body,
                context=ctx,
            )
            if email_success:
                print(f"Status update email sent to {len(office_emails)} office staff")
            else:
                print("Failed to send status update email")

        if complainant_phone:
            sms_data = {
                "grievance_id": grievance_id,
                "grievance_status": status_code,
                "grievance_timeline": grievance.get("grievance_timeline", "N/A"),
            }
            sms_message = DIC_SMS_TEMPLATES["GRIEVANCE_STATUS_UPDATE"]["en"].format(**sms_data)
            sms_success = grievance_dispatch_send_sms(
                complainant_phone,
                sms_message,
                context={
                    "source_system": "ticketing",
                    "purpose": "grievance_status_update",
                    "grievance_id": grievance_id,
                },
            )
            if sms_success:
                print(f"Status update SMS sent to complainant: {complainant_phone}")
            else:
                print(f"Failed to send status update SMS to {complainant_phone}")
    except Exception as e:
        print(f"Error in send_status_update_notifications: {str(e)}")


# --- Endpoints (paths include /api/grievance; no router prefix) ---
# Define fixed path /api/grievance/statuses before /api/grievance/{grievance_id} so "statuses" is not captured as id.


@router.get("/api/grievance/statuses")
def get_available_statuses():
    """Get all available grievance statuses. Same response as Flask."""
    try:
        statuses = grievance_manager.get_available_statuses()
        return {
            "status": "SUCCESS",
            "message": "Available statuses retrieved successfully",
            "data": statuses,
        }
    except Exception as e:
        print(f"Error retrieving available statuses: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "ERROR", "message": f"Internal server error: {str(e)}"},
        )


@router.post("/api/grievance/{grievance_id}/status")
def update_grievance_status(grievance_id: str, body: UpdateStatusBody):
    """Update the status of a specific grievance. Same behaviour as Flask."""
    try:
        grievance = grievance_manager.get_grievance_by_id(grievance_id)
        if not grievance:
            return JSONResponse(
                status_code=404,
                content={"status": "ERROR", "message": f"Grievance {grievance_id} not found"},
            )

        success = grievance_manager.update_grievance_status(
            grievance_id=grievance_id,
            status_code=body.status_code,
            created_by=body.created_by,
            notes=body.notes,
        )

        if not success:
            return JSONResponse(
                status_code=500,
                content={"status": "ERROR", "message": "Failed to update status"},
            )

        try:
            _send_status_update_notifications(grievance_id, body.status_code, body.notes, body.created_by)
        except Exception as e:
            print(f"Error sending notifications: {str(e)}")

        return {
            "status": "SUCCESS",
            "message": "Status updated successfully",
            "data": {
                "grievance_id": grievance_id,
                "status_code": body.status_code,
                "notes": body.notes,
                "created_by": body.created_by,
            },
        }
    except Exception as e:
        print(f"Error updating grievance status: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "ERROR", "message": f"Internal server error: {str(e)}"},
        )


@router.get("/api/grievance/{grievance_id}")
def get_grievance(grievance_id: str):
    """Get detailed information about a specific grievance. Same response as Flask."""
    try:
        grievance = grievance_manager.get_grievance_by_id(grievance_id)
        if not grievance:
            return JSONResponse(
                status_code=404,
                content={"status": "ERROR", "message": f"Grievance {grievance_id} not found"},
            )

        status_history = grievance_manager.get_grievance_status_history(grievance_id)
        files = grievance_manager.get_grievance_files(grievance_id)
        current_status = grievance_manager.get_grievance_status(grievance_id)

        response_data = {
            "grievance": grievance,
            "current_status": current_status,
            "status_history": status_history,
            "files": files,
        }
        return {
            "status": "SUCCESS",
            "message": "Grievance retrieved successfully",
            "data": response_data,
        }
    except Exception as e:
        print(f"Error retrieving grievance: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "ERROR", "message": f"Internal server error: {str(e)}"},
        )


@router.patch("/api/complainant/{complainant_id}")
def patch_complainant(
    complainant_id: str,
    body: ComplainantPatchBody,
    _: None = Depends(_ticketing_auth_check),
):
    """
    Update whitelisted complainant fields. Called by ticketing API - never
    stores PII in ticketing.*, proxies edits back here instead.
    Identity fields (full_name, phone, phone_hash) are NOT in the whitelist
    and cannot be changed through this endpoint.
    """
    allowed_fields = {
        "complainant_address",
        "complainant_village",
        "complainant_ward",
        "complainant_municipality",
        "complainant_district",
        "complainant_province",
        "complainant_email",
    }

    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        return JSONResponse(status_code=422, content={"status": "ERROR", "message": "No fields provided"})

    # Safety: re-check whitelist (defense in depth)
    fields = {k: v for k, v in fields.items() if k in allowed_fields}
    if not fields:
        return JSONResponse(
            status_code=422,
            content={"status": "ERROR", "message": "No allowed fields provided"},
        )

    try:
        set_fragments = [
            sql.SQL("{} = %s").format(sql.Identifier(column_name)) for column_name in fields.keys()
        ]
        update_query = sql.SQL("UPDATE complainants SET {} WHERE complainant_id = %s").format(
            sql.SQL(", ").join(set_fragments)
        )
        values = [*fields.values(), complainant_id]

        with grievance_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(update_query, values)
                updated_rows = cursor.rowcount
            conn.commit()

        if updated_rows == 0:
            return JSONResponse(
                status_code=404,
                content={"status": "ERROR", "message": f"Complainant {complainant_id} not found"},
            )

        return {
            "ok": True,
            "updated_fields": list(fields.keys()),
            "complainant_id": complainant_id,
        }
    except Exception as e:
        print(f"Error in patch_complainant: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "ERROR", "message": f"Internal server error: {str(e)}"},
        )
