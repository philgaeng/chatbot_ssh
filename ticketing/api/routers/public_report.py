"""Public report view API — no auth (TP-05)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ticketing.api.dependencies import CurrentUser, get_current_user, get_db
from ticketing.services.report_shares import get_share_by_token

router = APIRouter()


def _public_rows(share: dict) -> dict:
    return {
        "name": share.get("name"),
        "report_kind": share.get("report_kind"),
        "filters": share.get("filters") or {},
        "columns": share.get("columns_public") or [],
        "rows": share.get("rows_public") or [],
        "generated_at": share.get("created_at"),
    }


def _internal_rows(share: dict) -> dict:
    return {
        "name": share.get("name"),
        "report_kind": share.get("report_kind"),
        "filters": share.get("filters") or {},
        "columns": share.get("columns_internal") or [],
        "rows": share.get("rows_internal") or [],
        "generated_at": share.get("created_at"),
    }


@router.get("/public/report/{token}")
def get_public_report(token: str, db: Session = Depends(get_db)) -> dict:
    share = get_share_by_token(db, token)
    if not share or share.get("public_token") != token:
        raise HTTPException(status_code=404, detail="Report not found")
    return _public_rows(share)


@router.get("/reports/share/{token}")
def get_internal_report_share(
    token: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    share = get_share_by_token(db, token)
    if not share or share.get("internal_token") != token:
        raise HTTPException(status_code=404, detail="Report not found")
    return _internal_rows(share)
