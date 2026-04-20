"""
Pydantic schemas for workflow definitions and steps.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class WorkflowStepResponse(BaseModel):
    step_id: str
    workflow_id: str
    step_order: int
    step_key: str
    display_name: str
    assigned_role_key: str
    response_time_hours: Optional[int]
    resolution_time_days: Optional[int]
    stakeholders: Optional[Any]
    expected_actions: Optional[Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkflowDefinitionResponse(BaseModel):
    workflow_id: str
    workflow_key: str
    display_name: str
    description: Optional[str]
    workflow_type: str
    steps: list[WorkflowStepResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkflowListResponse(BaseModel):
    items: list[WorkflowDefinitionResponse]
    total: int
