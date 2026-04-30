"""
Pydantic schemas for ticket requests and responses.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Inbound: chatbot/backend → ticketing ──────────────────────────────────────

class TicketCreate(BaseModel):
    """
    POST /api/v1/tickets — called by chatbot backend after grievance is stored.
    PII rules: no name/phone/email fields here; summary/categories/location are non-PII.
    """
    grievance_id: str = Field(..., max_length=64)
    complainant_id: Optional[str] = Field(None, max_length=64)
    session_id: Optional[str] = Field(None, max_length=255)
    chatbot_id: str = Field("nepal_grievance_bot", max_length=64)

    country_code: str = Field("NP", max_length=8)
    organization_id: str = Field(..., max_length=64)
    location_code: Optional[str] = Field(None, max_length=64)
    project_code: Optional[str] = Field(None, max_length=64)
    priority: str = Field("NORMAL", max_length=32)  # NORMAL | HIGH | SENSITIVE
    is_seah: bool = False

    # Non-PII grievance data cached at ticket creation (CLAUDE.md rule 4)
    grievance_summary: Optional[str] = None
    grievance_categories: Optional[str] = None
    grievance_location: Optional[str] = None


# ── Outbound: ticketing → officer UI ─────────────────────────────────────────

class WorkflowStepBrief(BaseModel):
    step_id: str
    step_order: int
    step_key: str
    display_name: str
    assigned_role_key: str
    response_time_hours: Optional[int]
    resolution_time_days: Optional[int]

    class Config:
        from_attributes = True


class TicketEventOut(BaseModel):
    event_id: str
    event_type: str
    old_status_code: Optional[str]
    new_status_code: Optional[str]
    old_assigned_to: Optional[str]
    new_assigned_to: Optional[str]
    workflow_step_id: Optional[str]
    note: Optional[str]
    payload: Optional[Any]
    seen: bool
    created_at: datetime
    created_by_user_id: Optional[str]
    # ── SEAH audit fields (seah-privacy-worktree-handoff.md) ──
    actor_role: Optional[str] = None
    case_sensitivity: str = "standard"
    summary_regen_required: bool = False

    class Config:
        from_attributes = True


class TicketCreateResponse(BaseModel):
    """Minimal response returned to chatbot after ticket creation."""
    ticket_id: str
    status_code: str
    current_workflow_id: str
    current_step_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class TicketListItem(BaseModel):
    ticket_id: str
    grievance_id: str
    grievance_summary: Optional[str]
    status_code: str
    priority: str
    is_seah: bool
    organization_id: str
    location_code: Optional[str]
    project_code: Optional[str]
    assigned_to_user_id: Optional[str]
    sla_breached: bool
    step_started_at: Optional[datetime]
    created_at: datetime
    # Unread badge: number of unseen events assigned to requesting user
    unseen_event_count: int = 0

    class Config:
        from_attributes = True


class TicketListResponse(BaseModel):
    items: list[TicketListItem]
    total: int
    page: int
    page_size: int


class TicketViewerOut(BaseModel):
    viewer_id: str
    user_id: str
    added_by_user_id: str
    added_at: str  # ISO string injected by endpoint

    class Config:
        from_attributes = True


class TicketDetail(BaseModel):
    ticket_id: str
    grievance_id: str
    complainant_id: Optional[str]
    session_id: Optional[str]
    chatbot_id: str
    grievance_summary: Optional[str]
    grievance_categories: Optional[str]
    grievance_location: Optional[str]
    country_code: str
    organization_id: str
    location_code: Optional[str]
    project_code: Optional[str]
    status_code: str
    priority: str
    is_seah: bool
    assigned_to_user_id: Optional[str]
    assigned_role_id: Optional[str]
    step_started_at: Optional[datetime]
    sla_breached: bool
    is_deleted: bool
    created_at: datetime
    created_by_user_id: Optional[str]
    updated_at: datetime
    updated_by_user_id: Optional[str]
    current_step: Optional[WorkflowStepBrief]
    events: list[TicketEventOut] = []
    viewers: list[TicketViewerOut] = []
    # LLM-generated findings (visible to grc_chair, adb_*, super_admin only)
    ai_summary_en: Optional[str] = None
    ai_summary_updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Actions ───────────────────────────────────────────────────────────────────

class TicketActionRequest(BaseModel):
    """
    POST /api/v1/tickets/{ticket_id}/actions
    action_type: ACKNOWLEDGE | ESCALATE | RESOLVE | CLOSE | NOTE | GRC_CONVENE | GRC_DECIDE
    """
    action_type: str = Field(
        ...,
        description="ACKNOWLEDGE | ESCALATE | RESOLVE | CLOSE | NOTE | GRC_CONVENE | GRC_DECIDE",
    )
    note: Optional[str] = None
    assign_to_user_id: Optional[str] = Field(None, max_length=128)
    # GRC-specific fields
    grc_hearing_date: Optional[str] = Field(None, description="ISO date string e.g. 2026-05-03")
    grc_decision: Optional[str] = Field(None, description="RESOLVED | ESCALATE_TO_LEGAL")


class TicketActionResponse(BaseModel):
    ticket_id: str
    action_type: str
    new_status_code: str
    current_step_id: Optional[str]
    event_id: str


class TicketReplyRequest(BaseModel):
    """
    POST /api/v1/tickets/{ticket_id}/reply
    Officer sends a message to the complainant via orchestrator.
    """
    text: str = Field(..., min_length=1, max_length=4000)


class TicketReplyResponse(BaseModel):
    ticket_id: str
    event_id: str
    delivered: bool
    detail: Optional[str] = None


# ── Patch ─────────────────────────────────────────────────────────────────────

class TicketPatch(BaseModel):
    """PATCH /api/v1/tickets/{ticket_id} — officer updates assignment or priority."""
    assign_to_user_id: Optional[str] = Field(None, max_length=128)
    assigned_role_id: Optional[str] = Field(None, max_length=36)
    priority: Optional[str] = Field(None, max_length=32)


class ComplainantPatch(BaseModel):
    """
    PATCH /api/v1/tickets/{ticket_id}/complainant

    Officers can correct non-identity complainant fields that were missing or
    wrong at submission time.  The update is proxied to the chatbot backend via
    PATCH {chatbot_base_url}/api/complainant/{complainant_id}.

    STRICTLY WHITELISTED — identity fields (full_name, phone, phone_hash) are
    never writable from ticketing.  All fields are optional; only provided
    (non-None) fields are sent to the backend.
    """
    complainant_address: Optional[str] = Field(None, max_length=512)
    complainant_village: Optional[str] = Field(None, max_length=255)
    complainant_ward: Optional[str] = Field(None, max_length=64)
    complainant_municipality: Optional[str] = Field(None, max_length=255)
    complainant_district: Optional[str] = Field(None, max_length=255)
    complainant_province: Optional[str] = Field(None, max_length=255)
    complainant_email: Optional[str] = Field(None, max_length=255)

    def non_null_fields(self) -> dict:
        """Return only the fields that were explicitly set (not None)."""
        return {k: v for k, v in self.model_dump().items() if v is not None}


class ComplainantPatchResponse(BaseModel):
    ticket_id: str
    complainant_id: str
    fields_updated: list[str]
    event_id: str
