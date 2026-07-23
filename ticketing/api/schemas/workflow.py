"""
Pydantic schemas for workflow definitions, steps, and assignments.
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


# ── Steps ─────────────────────────────────────────────────────────────────────

class WorkflowStepResponse(BaseModel):
    step_id: str
    workflow_id: str
    step_order: int
    step_key: str
    display_name: str
    assigned_role_key: str
    response_time_hours: Optional[int]
    resolution_time_days: Optional[int]
    # Spec 12 tier model
    supervisor_role: Optional[str] = None
    informed_roles: list[str] = []
    observer_roles: list[str] = []
    informed_pii_access: bool = False
    stakeholders: Optional[Any]
    expected_actions: Optional[Any]
    is_deleted: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkflowStepCreate(BaseModel):
    display_name: str
    step_key: Optional[str] = None          # auto-generated if omitted
    # Optional: the tier-toggle editor omits it (Actor is auto-minted a synthetic per-step
    # key). Legacy/template callers may still pass a named key.
    assigned_role_key: str = ""
    response_time_hours: Optional[int] = None
    resolution_time_days: Optional[int] = None
    supervisor_role: Optional[str] = None
    informed_roles: list[str] = []
    observer_roles: list[str] = []
    informed_pii_access: bool = False
    stakeholders: Optional[list[str]] = None
    expected_actions: Optional[list[str]] = None
    # Tier-toggle editor (DESIGN-cast-model §3.5): when any of these is set, the step's tier
    # fields are (re)derived from on/off toggles — enabled empty slots mint synthetic keys.
    supervisor_enabled: Optional[bool] = None
    participants_enabled: Optional[bool] = None
    observers_enabled: Optional[bool] = None


class WorkflowStepUpdate(BaseModel):
    display_name: Optional[str] = None
    step_key: Optional[str] = None
    assigned_role_key: Optional[str] = None
    response_time_hours: Optional[int] = None
    resolution_time_days: Optional[int] = None
    supervisor_role: Optional[str] = None
    informed_roles: Optional[list[str]] = None
    observer_roles: Optional[list[str]] = None
    informed_pii_access: Optional[bool] = None
    stakeholders: Optional[list[str]] = None
    expected_actions: Optional[list[str]] = None
    # Tier-toggle editor (see WorkflowStepCreate).
    supervisor_enabled: Optional[bool] = None
    participants_enabled: Optional[bool] = None
    observers_enabled: Optional[bool] = None


class StepReorderRequest(BaseModel):
    step_ids: list[str]   # full ordered list of step_ids


# ── Assignments ───────────────────────────────────────────────────────────────

class WorkflowAssignmentResponse(BaseModel):
    assignment_id: str
    workflow_id: str
    organization_id: str
    location_code: Optional[str]
    project_code: Optional[str]
    priority: Optional[str]

    class Config:
        from_attributes = True


class WorkflowAssignmentCreate(BaseModel):
    organization_id: str
    location_code: Optional[str] = None
    project_code: Optional[str] = None
    priority: Optional[str] = None


# ── Workflow definitions ──────────────────────────────────────────────────────

class WorkflowDefinitionResponse(BaseModel):
    workflow_id: str
    workflow_key: str
    display_name: str
    description: Optional[str]
    workflow_type: str
    status: str
    version: int
    is_template: bool
    template_source_id: Optional[str]
    steps: list[WorkflowStepResponse] = []
    assignments: list[WorkflowAssignmentResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkflowListResponse(BaseModel):
    items: list[WorkflowDefinitionResponse]
    total: int


class WorkflowCreate(BaseModel):
    display_name: str
    workflow_type: str = "standard"         # "standard" | "seah"
    description: Optional[str] = None
    clone_from_id: Optional[str] = None     # clone steps from this workflow/template
    is_template: bool = False               # True → reusable template (not assigned to tickets)


class SaveAsTemplateBody(BaseModel):
    display_name: Optional[str] = None      # defaults to "{source name} (template)"


class WorkflowUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    workflow_key: Optional[str] = None
