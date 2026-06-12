"""Pydantic schemas for project-level officer messaging config."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class OfficerMessagingConfig(BaseModel):
    sms_enabled: bool = False
    sms_levels: list[int] = Field(default_factory=list)
    whatsapp_levels: list[int] = Field(default_factory=list)


class ProjectMessagingResponse(BaseModel):
    sms_enabled: bool
    sms_levels: list[int]
    whatsapp_levels: list[int] = Field(default_factory=list)
    max_levels: int


class ProjectMessagingPatch(BaseModel):
    sms_enabled: bool | None = None
    sms_levels: list[int] | None = None
    whatsapp_levels: list[int] | None = None

    @field_validator("sms_levels")
    @classmethod
    def _unique_positive_levels(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return v
        if any(level < 1 for level in v):
            raise ValueError("sms_levels must be positive integers")
        if len(set(v)) != len(v):
            raise ValueError("sms_levels must be unique")
        return sorted(v)

    @field_validator("whatsapp_levels")
    @classmethod
    def _unique_whatsapp_levels(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return v
        if any(level < 1 for level in v):
            raise ValueError("whatsapp_levels must be positive integers")
        if len(set(v)) != len(v):
            raise ValueError("whatsapp_levels must be unique")
        return sorted(v)
