"""
Grievance API router. Same URL surface and behaviour as Flask backend.
"""

import hmac
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from backend.clients.messaging_api import send_email as send_email_via_api
from backend.clients.messaging_api import send_sms as send_sms_via_api
from backend.config.constants import EMAIL_TEMPLATES, DIC_SMS_TEMPLATES
from backend.services.database_services.grievance_manager import GrievanceDbManager

router = APIRouter()
logger = logging.getLogger(__name__)

# T3-06 step 2 — read audit for GET /api/grievance/{id}.
#
# Its own logger name so the trail can be filtered/shipped without dragging along
# the rest of the router's chatter, and grepped as one stream. Deliberately NOT a
# public.* table: a log line is reversible, a new table is a migration-stream
# commitment (CLAUDE.md §Migration traceability). Revisit if the trail needs to be
# queryable or retained — see PROGRESS.md T3-06.
#
# Emits at INFO because LOG_LEVEL=INFO is the deployed default (env.local:23);
# a .debug record would be invisible in production, which is how
# grievance_manager.py:172 already fails to be an audit trail.
audit_logger = logging.getLogger("audit.grievance_read")

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


class GrievanceRecord(BaseModel):
    """
    One row of ``get_grievance_by_id`` (T3-06 step 1).

    Fields are ``Any`` rather than ``str`` on purpose. ``_parse_field_from_database``
    (base_manager.py) runs ``json.loads`` over *every* string column, so a TEXT value
    that happens to parse ("5", "2024", a JSON array) reaches this model as int/list.
    ``grievance_categories``/``follow_up_question`` arrive as lists for that reason.
    Pinning those as ``str`` would turn ordinary data into a 500 under Pydantic v2,
    which rejects int->str. Only the psycopg2-native types (datetime, bool) are pinned.

    ``extra="allow"`` is load-bearing: the query is ``SELECT g.*`` plus a complainant
    and grievance_parties join, so the shape is defined by the tables. A model that
    omits a column would silently drop it from the API response — verified. Adding a
    column here is safe; removing one is an API change.
    """

    model_config = ConfigDict(extra="allow")

    # --- public.grievances (SELECT g.*) ---
    grievance_id: Optional[str] = None
    complainant_id: Optional[str] = None
    grievance_categories: Any = None
    grievance_categories_alternative: Any = None
    follow_up_question: Any = None
    grievance_summary: Any = None
    grievance_description: Any = None
    grievance_claimed_amount: Any = None
    grievance_location: Any = None
    language_code: Any = None
    grievance_classification_status: Any = None
    grievance_creation_date: Optional[datetime] = None
    grievance_modification_date: Optional[datetime] = None
    is_temporary: Optional[bool] = None
    source: Any = None
    grievance_sensitive_issue: Optional[bool] = None
    grievance_high_priority: Optional[bool] = None
    grievance_timeline: Any = None
    case_sensitivity: Any = None
    vault_payload_ref: Any = None
    vault_last_updated_at: Optional[datetime] = None
    is_archived: Optional[bool] = None
    archived_at: Optional[datetime] = None

    # --- public.complainants (LEFT JOIN via grievance_parties) ---
    # NOTE: the four ENCRYPTED_FIELDS below (full_name/phone/email/address) are served
    # as pgcrypto hex ciphertext today — get_grievance_by_id never decrypts. That is
    # the T3-04 defect; this model documents the shape as-built, it does not fix it.
    complainant_full_name: Any = None
    complainant_phone: Any = None
    complainant_email: Any = None
    complainant_address: Any = None
    complainant_province: Any = None
    complainant_district: Any = None
    complainant_municipality: Any = None
    complainant_ward: Any = None
    complainant_village: Any = None
    location_geo: Any = None
    contact_id: Any = None
    country_code: Any = None
    location_code: Any = None
    location_resolution_status: Any = None
    level_1_name: Any = None
    level_2_name: Any = None
    level_3_name: Any = None
    level_4_name: Any = None
    level_5_name: Any = None
    level_6_name: Any = None
    level_1_code: Any = None
    level_2_code: Any = None
    level_3_code: Any = None
    level_4_code: Any = None
    level_5_code: Any = None
    level_6_code: Any = None

    # --- public.grievance_parties ---
    party_role: Any = None
    is_primary_reporter: Optional[bool] = None


class GrievanceDetailData(BaseModel):
    """``data`` block of GET /api/grievance/{id}."""

    model_config = ConfigDict(extra="allow")

    grievance: GrievanceRecord
    current_status: Optional[Dict[str, Any]] = None
    status_history: List[Dict[str, Any]] = Field(default_factory=list)
    files: List[Dict[str, Any]] = Field(default_factory=list)


class GrievanceDetailResponse(BaseModel):
    """Envelope of GET /api/grievance/{id} — preserves the Flask response structure."""

    model_config = ConfigDict(extra="allow")

    status: str
    message: str
    data: GrievanceDetailData


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


def _principal_for_key(x_api_key: Optional[str]) -> str:
    """
    Name the caller behind an api key. Never returns or logs the key itself.

    The audit trail needs a principal, not a secret. Keys are compared with
    compare_digest so this cannot be used as a timing oracle.
    """
    if not x_api_key or not x_api_key.strip():
        return "anonymous"
    presented = x_api_key.strip()
    for name, env_var in (("ticketing", "TICKETING_SECRET_KEY"), ("messaging", "MESSAGING_API_KEY")):
        configured = os.environ.get(env_var, "").strip()
        if configured and hmac.compare_digest(presented, configured):
            return name
    return "unrecognized-key"


def _audit_grievance_read(
    grievance_id: str,
    principal: str,
    client_host: Optional[str],
    outcome: str,
) -> None:
    """
    Record one read of a grievance record.

    Emitted at INFO so it survives the deployed LOG_LEVEL. JSON payload so the
    trail is parseable if it is ever shipped to a collector; the key itself is
    never included, only the principal it resolves to.
    """
    audit_logger.info(
        "grievance_read %s",
        json.dumps(
            {
                "event": "grievance_read",
                "grievance_id": grievance_id,
                "principal": principal,
                "client": client_host or "unknown",
                "outcome": outcome,
                "at": datetime.now(timezone.utc).isoformat(),
            },
            sort_keys=True,
        ),
    )


def _ticketing_auth_check(x_api_key: Optional[str] = Header(default=None)) -> None:
    valid = {
        k.strip()
        for k in (
            os.environ.get("TICKETING_SECRET_KEY", ""),
            os.environ.get("MESSAGING_API_KEY", ""),
        )
        if k and k.strip()
    }
    if not valid:
        # Fail-closed (HR-01): an empty key list must NOT silently skip the check.
        # Only the dev bypass (APP_ENV=dev AUTH_MODE=bypass) may run without a key.
        if (
            os.environ.get("APP_ENV", "production").strip().lower() == "dev"
            and os.environ.get("AUTH_MODE", "keycloak").strip().lower() == "bypass"
        ):
            return
        raise HTTPException(
            status_code=503,
            detail="Grievance API key auth not configured "
            "(set TICKETING_SECRET_KEY/MESSAGING_API_KEY, or APP_ENV=dev AUTH_MODE=bypass for local dev)",
        )
    if not x_api_key or x_api_key not in valid:
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


@router.get("/api/grievance/{grievance_id}", response_model=GrievanceDetailResponse)
def get_grievance(
    grievance_id: str,
    request: Request,
    x_api_key: Optional[str] = Header(default=None),
):
    """Get detailed information about a specific grievance. Same response as Flask."""
    principal = _principal_for_key(x_api_key)
    client_host = request.client.host if request.client else None
    try:
        grievance = grievance_manager.get_grievance_by_id(grievance_id)
        if not grievance:
            _audit_grievance_read(grievance_id, principal, client_host, "not_found")
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
        # Audited after retrieval succeeds so the record reflects what was actually
        # disclosed, but before returning so no disclosure can go unrecorded.
        _audit_grievance_read(grievance_id, principal, client_host, "success")
        return {
            "status": "SUCCESS",
            "message": "Grievance retrieved successfully",
            "data": response_data,
        }
    except Exception as e:
        _audit_grievance_read(grievance_id, principal, client_host, "error")
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
