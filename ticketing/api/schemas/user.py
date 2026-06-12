"""
Pydantic schemas for officers, roles, and user_roles.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class RoleResponse(BaseModel):
    role_id: str
    role_key: str
    display_name: str
    description: str | None = None
    workflow_scope: str | None = None
    jurisdiction_mode: str | None = None
    permissions: Any
    role_kind: str | None = None
    role_origin: str | None = None
    steps_count: int = 0
    officers_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RoleCreate(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=200)
    role_key: str | None = Field(None, max_length=64)
    workflow_scope: str = Field(..., pattern="^(Standard|SEAH|Both)$")
    jurisdiction_mode: str = Field(default="field", pattern="^(field|country|global)$")
    archetype: str = Field(default="field_actor")
    permissions: list[str] | None = None
    description: str | None = None


class RoleUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    workflow_scope: str | None = None
    jurisdiction_mode: str | None = None
    permissions: list[str] | None = None


class AdminScopeResponse(BaseModel):
    admin_scope_id: str
    user_id: str
    role_key: str
    country_code: str | None = None
    project_id: str | None = None
    organization_id: str | None = None
    package_id: str | None = None
    workflow_track: str
    created_at: datetime
    created_by_user_id: str | None = None
    can_resend_invite: bool = False
    can_send_setup_email: bool = False
    onboarding_status: str | None = None
    invite_email_sent: bool = False

    class Config:
        from_attributes = True


class AdminScopeCreate(BaseModel):
    user_id: str = Field(..., max_length=128)
    role_key: str = Field(..., pattern="^(country_admin|project_admin)$")
    country_code: str | None = Field(None, max_length=8)
    project_id: str | None = Field(None, max_length=64)
    organization_id: str | None = Field(None, max_length=64)
    package_id: str | None = Field(None, max_length=64)
    workflow_track: str = Field(..., pattern="^(standard|seah)$")


class AdminContextResponse(BaseModel):
    is_super_admin: bool
    is_country_admin: bool
    is_project_admin: bool
    admin_workflow_tracks: list[str]
    admin_project_ids: list[str]
    admin_country_codes: list[str]
    can_access_platform_settings: bool
    can_manage_structure: bool
    admin_scopes: list[dict]


class UserRoleCreate(BaseModel):
    user_id: str = Field(..., max_length=128)
    role_id: str = Field(..., max_length=36)
    organization_id: str = Field(..., max_length=64)
    location_code: Optional[str] = Field(None, max_length=64)


class UserRoleResponse(BaseModel):
    user_role_id: str
    user_id: str
    role_id: str
    organization_id: str
    location_code: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationBadgeResponse(BaseModel):
    """Unread event count for the notification badge in the officer UI."""
    unseen_count: int


class NotificationItem(BaseModel):
    """A single unseen event surfaced in the notification panel."""
    event_id: str
    ticket_id: str
    grievance_id: str
    grievance_summary: Optional[str]
    event_type: str
    note: Optional[str]
    created_at: datetime
    created_by_user_id: Optional[str]

    class Config:
        from_attributes = True


class NotificationsResponse(BaseModel):
    items: list[NotificationItem]
    total: int
