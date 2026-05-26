"""
Settings CRUD — key/value store for GRM configuration.
Only super_admin / local_admin may write settings.
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.api.dependencies import CurrentUser, get_current_user, get_db
from ticketing.models.settings import Settings

router = APIRouter()

# Only super_admin may write these keys (IT / advanced settings).
SUPER_ADMIN_ONLY_KEYS = frozenset({"org_roles", "report_limits"})


class SettingsUpsert(BaseModel):
    value: Any


class SettingsResponse(BaseModel):
    key: str
    value: Any
    updated_by_user_id: str | None = None

    class Config:
        from_attributes = True


@router.get("/settings", response_model=list[SettingsResponse], summary="List all settings")
def list_settings(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> list[Settings]:
    return db.execute(select(Settings).order_by(Settings.key)).scalars().all()


@router.get("/settings/{key}", response_model=SettingsResponse, summary="Get a single setting")
def get_setting(
    key: str,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> Settings:
    setting = db.get(Settings, key)
    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    return setting


@router.put(
    "/settings/{key}",
    response_model=SettingsResponse,
    summary="Create or update a setting (admin only)",
)
def upsert_setting(
    key: str,
    payload: SettingsUpsert,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Settings:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    if key in SUPER_ADMIN_ONLY_KEYS and not current_user.is_super_admin:
        raise HTTPException(
            status_code=403,
            detail="Super-admin access required for this setting",
        )

    value = payload.value
    if key == "report_limits":
        from ticketing.services.report_limits import save_report_limits

        merged = save_report_limits(
            db,
            value if isinstance(value, dict) else {},
            current_user.user_id,
        )
        setting = db.get(Settings, key)
        assert setting is not None
        return setting

    setting = db.get(Settings, key)
    if setting:
        setting.value = value
        setting.updated_by_user_id = current_user.user_id
    else:
        setting = Settings(
            key=key,
            value=value,
            updated_by_user_id=current_user.user_id,
        )
        db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting


@router.delete(
    "/settings/{key}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a setting (admin only)",
)
def delete_setting(
    key: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    if key in SUPER_ADMIN_ONLY_KEYS and not current_user.is_super_admin:
        raise HTTPException(
            status_code=403,
            detail="Super-admin access required for this setting",
        )
    setting = db.get(Settings, key)
    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    db.delete(setting)
    db.commit()
