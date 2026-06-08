"""
Grievance API router. Same URL surface and behaviour as Flask backend.
"""

import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from backend.clients.messaging_api import send_email as send_email_via_api
from backend.clients.messaging_api import send_sms as send_sms_via_api
from backend.config.constants import EMAIL_TEMPLATES, DIC_SMS_TEMPLATES
from backend.services.database_services.grievance_manager import GrievanceDbManager

router = APIRouter()
logger = logging.getLogger(__name__)

grievance_manager = GrievanceDbManager()


# --- Request/response models (preserve Flask response structure) ---


class UpdateStatusBody(BaseModel):
    status_code: str = Field(..., description="New status code")
    notes: Optional[str] = None
    created_by: Optional[str] = None


class GrievanceClassificationPatchBody(BaseModel):
    grievance_classification_status: str = Field(..., max_length=64)
    grievance_summary: Optional[str] = None
    grievance_categories: Optional[Any] = None


class ComplainantPatchBody(BaseModel):
    complainant_full_name: Optional[str] = Field(None, max_length=255)
    complainant_phone: Optional[str] = Field(None, max_length=64)
    complainant_address: Optional[str] = None
    complainant_village: Optional[str] = None
    complainant_ward: Optional[str] = None
    complainant_municipality: Optional[str] = None
    complainant_district: Optional[str] = None
    complainant_province: Optional[str] = None
    complainant_email: Optional[str] = None


_COMPLAINANT_ADDRESS_FIELDS = frozenset({
    "complainant_address",
    "complainant_village",
    "complainant_ward",
    "complainant_municipality",
    "complainant_district",
    "complainant_province",
    "complainant_email",
})
_IDENTITY_FILL_FIELDS = frozenset({"complainant_full_name", "complainant_phone"})


def _identity_value_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        s = value.strip()
        if len(s) >= 40 and all(c in "0123456789abcdefABCDEF" for c in s):
            return True
    s = str(value).strip()
    if not s:
        return True
    if s.lower() in {"anonymous", "unknown", "n/a", "na", "not provided"}:
        return True
    return False


def _ticketing_auth_check(x_api_key: Optional[str] = Header(default=None)) -> None:
    valid = {
        k.strip()
        for k in (
            os.environ.get("TICKETING_SECRET_KEY", ""),
            os.environ.get("MESSAGING_API_KEY", ""),
        )
        if k and k.strip()
    }
    if valid and (not x_api_key or x_api_key not in valid):
        raise HTTPException(status_code=401, detail="Invalid API key")


def _send_status_update_notifications(
    grievance_id: str,
    status_code: str,
    notes: Optional[str],
    created_by: Optional[str],
) -> None:
    """Send email and SMS when grievance status is updated via Messaging API."""
    try:
        grievance = grievance_manager.get_grievance_by_id(grievance_id)
        if not grievance:
            logger.warning("Grievance %s not found for status notifications", grievance_id)
            return

        complainant_phone = grievance.get("complainant_phone")
        office_emails = grievance_manager.get_office_emails_for_grievance(grievance_id)
        base_context: Dict[str, Any] = {
            "source_system": "backend",
            "purpose": "grievance_status_update",
            "grievance_id": grievance_id,
        }
        if created_by:
            base_context["office_user"] = created_by

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
            try:
                send_email_via_api(
                    office_emails,
                    email_subject,
                    email_body,
                    context={**base_context, "channel": "email"},
                )
                logger.info(
                    "Status update email sent to %d office staff for %s",
                    len(office_emails),
                    grievance_id,
                )
            except Exception as email_err:
                logger.error("Failed to send status update email for %s: %s", grievance_id, email_err)

        if complainant_phone:
            sms_data = {
                "grievance_id": grievance_id,
                "grievance_status": status_code,
                "grievance_timeline": grievance.get("grievance_timeline", "N/A"),
            }
            sms_message = DIC_SMS_TEMPLATES["GRIEVANCE_STATUS_UPDATE"]["en"].format(**sms_data)
            try:
                send_sms_via_api(
                    complainant_phone,
                    sms_message,
                    context={**base_context, "channel": "sms"},
                )
                logger.info("Status update SMS sent for grievance %s", grievance_id)
            except Exception as sms_err:
                logger.error("Failed to send status update SMS for %s: %s", grievance_id, sms_err)
    except Exception as e:
        logger.exception("Error in send_status_update_notifications: %s", e)


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


@router.patch("/api/grievance/{grievance_id}/classification")
def patch_grievance_classification(
    grievance_id: str,
    body: GrievanceClassificationPatchBody,
    _: None = Depends(_ticketing_auth_check),
):
    """
    Update classification status and optional summary/categories.
    Called by ticketing when an officer validates classification (TP-14).
    """
    from backend.config.classification_status import OFFICER_CONFIRMED, ACTIVE_CODES

    status = body.grievance_classification_status
    if status not in ACTIVE_CODES:
        return JSONResponse(
            status_code=422,
            content={"status": "ERROR", "message": f"Invalid classification status: {status}"},
        )
    payload: Dict[str, Any] = {"grievance_classification_status": status}
    if body.grievance_summary is not None:
        payload["grievance_summary"] = body.grievance_summary
    if body.grievance_categories is not None:
        payload["grievance_categories"] = body.grievance_categories

    if not grievance_manager.get_grievance_by_id(grievance_id):
        return JSONResponse(
            status_code=404,
            content={"status": "ERROR", "message": f"Grievance {grievance_id} not found"},
        )

    try:
        grievance_manager.update_grievance(grievance_id, payload)
        return {
            "ok": True,
            "grievance_id": grievance_id,
            "grievance_classification_status": status,
            "officer_confirmed": status == OFFICER_CONFIRMED,
        }
    except Exception as e:
        logger.exception("patch_grievance_classification failed for %s", grievance_id)
        return JSONResponse(
            status_code=500,
            content={"status": "ERROR", "message": str(e)},
        )


@router.patch("/api/complainant/{complainant_id}")
def patch_complainant(
    complainant_id: str,
    body: ComplainantPatchBody,
    _: None = Depends(_ticketing_auth_check),
):
    """
    Update whitelisted complainant fields (ticketing officer edit form).

    Address/location/email: always editable when provided.
    full_name / phone: fill-missing only — allowed when DB value is empty; rejected if already set.
    """
    from backend.services.database_services.complainant_manager import ComplainantDbManager

    raw = {k: v for k, v in body.model_dump().items() if v is not None}
    if not raw:
        return JSONResponse(status_code=422, content={"status": "ERROR", "message": "No fields provided"})

    complainant_mgr = ComplainantDbManager()
    current = complainant_mgr.get_complainant_by_id(complainant_id)
    if not current:
        return JSONResponse(
            status_code=404,
            content={"status": "ERROR", "message": f"Complainant {complainant_id} not found"},
        )

    update_data: dict[str, Any] = {}
    blocked: list[str] = []

    for key, value in raw.items():
        if key in _COMPLAINANT_ADDRESS_FIELDS:
            if str(value).strip():
                update_data[key] = str(value).strip()
            continue
        if key in _IDENTITY_FILL_FIELDS:
            if not str(value).strip():
                continue
            if _identity_value_missing(current.get(key)):
                update_data[key] = str(value).strip()
            else:
                blocked.append(key)
            continue

    if blocked:
        labels = ", ".join(blocked)
        return JSONResponse(
            status_code=422,
            content={
                "status": "ERROR",
                "message": (
                    f"Cannot change {labels} — already on file from chatbot. "
                    "Contact the chatbot admin to correct identity fields."
                ),
            },
        )

    if not update_data:
        return JSONResponse(
            status_code=422,
            content={"status": "ERROR", "message": "No allowed fields provided"},
        )

    try:
        affected = complainant_mgr.update_complainant(complainant_id, update_data)
        if not affected:
            return JSONResponse(
                status_code=404,
                content={"status": "ERROR", "message": f"Complainant {complainant_id} not found"},
            )

        return {
            "ok": True,
            "updated_fields": list(update_data.keys()),
            "complainant_id": complainant_id,
        }
    except Exception as e:
        logger.exception("patch_complainant failed for %s", complainant_id)
        return JSONResponse(
            status_code=500,
            content={"status": "ERROR", "message": f"Internal server error: {str(e)}"},
        )
