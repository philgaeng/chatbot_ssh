"""Pydantic schemas for operational reports."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ReportSectionBlock(BaseModel):
    items: list[dict[str, Any]]
    total: int


class ReportQueryResponse(BaseModel):
    filters: dict[str, Any]
    summary: dict[str, int]
    columns: list[str]
    column_labels: dict[str, str]
    sections: dict[str, ReportSectionBlock]
    field_catalog: list[dict[str, str]]


class PivotValueSpec(BaseModel):
    field: str = "ticket_id"
    agg: Literal["count", "sum", "avg", "max", "min"] = "count"


class PivotConfig(BaseModel):
    """Excel-style pivot: row/column dimensions + aggregated values."""

    rows: list[str] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    values: list[PivotValueSpec] = Field(
        default_factory=lambda: [PivotValueSpec(field="ticket_id", agg="count")]
    )
    filters: dict[str, list[str]] = Field(default_factory=dict)


class QuarterlyReportSchedule(BaseModel):
    frequency: Literal["quarterly"] = "quarterly"
    day_of_month: int = Field(5, ge=1, le=28)


class QuarterlyReportTemplate(BaseModel):
    name: str = "GRM quarterly overview"
    kind: Literal["overview", "pivot"] = "overview"
    include_seah: bool = False
    project_ids: list[str] = Field(default_factory=list)
    package_ids: list[str] = Field(default_factory=list)
    location_codes: list[str] = Field(default_factory=list)
    pivot: Optional[PivotConfig] = None


class ReportLimitsInfo(BaseModel):
    max_export_rows: int
    max_exports_per_user_per_hour: int
    max_reports_per_role_per_quarter: int
    quarterly_email_enabled: bool
    allowed_recipient_roles: list[str] | None = None


class QuarterlyAssignmentOut(BaseModel):
    id: str
    quarter_key: str
    role_key: str
    name: str
    template: QuarterlyReportTemplate
    active: bool = True


class QuarterlyAssignmentCreate(BaseModel):
    quarter_key: str
    role_keys: list[str] = Field(..., min_length=1)
    name: str
    template: QuarterlyReportTemplate


class QuarterlyAssignmentUpdate(BaseModel):
    name: Optional[str] = None
    template: Optional[QuarterlyReportTemplate] = None
    active: Optional[bool] = None


class QuarterlyRolePlan(BaseModel):
    role_key: str
    count: int
    max: int
    assignments: list[QuarterlyAssignmentOut]


class QuarterlyPlanResponse(BaseModel):
    quarter_key: str
    max_per_role: int
    schedule: QuarterlyReportSchedule
    limits: ReportLimitsInfo
    roles: list[QuarterlyRolePlan]


class QuarterlyScheduleUpdate(BaseModel):
    day_of_month: int = Field(5, ge=1, le=28)


class ReportBuildRequest(BaseModel):
    date_from: date
    date_to: date
    project_ids: list[str] = Field(default_factory=list)
    package_ids: list[str] = Field(default_factory=list)
    location_codes: list[str] = Field(default_factory=list)
    include_seah: bool = False
    columns: list[str] = Field(default_factory=list)
    pivot: Optional[PivotConfig] = None
    group_by: Optional[str] = None
    aggregate: Literal["none", "count", "avg_total_days", "sum_total_days"] = "none"
    page: int = Field(1, ge=1)
    page_size: int = Field(100, ge=1, le=500)
    format: Literal["json", "xlsx"] = "json"
