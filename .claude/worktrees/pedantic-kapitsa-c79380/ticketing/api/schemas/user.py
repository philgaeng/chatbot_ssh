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
    permissions: Any
    created_at: datetime

    class Config:
        from_attributes = True


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
