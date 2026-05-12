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
    permissions: Any
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RoleUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    workflow_scope: str | None = None


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
