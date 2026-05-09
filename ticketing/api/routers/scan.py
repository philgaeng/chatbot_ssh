"""
QR token scan + management endpoints.

Public (no auth):
  GET  /api/v1/scan/{token}
    → resolves token → returns project/package/location context
    → chatbot calls this at session start to pre-fill slots

Any authenticated user:
  GET  /api/v1/my-packages/qr
    → returns QR codes for packages in the user's scope
    → auto-creates a token if the package has none

Admin-only:
  GET    /api/v1/packages/{package_id}/qr-tokens   list active tokens
  POST   /api/v1/packages/{package_id}/qr-tokens   create new token
  DELETE /api/v1/qr-tokens/{token}                 revoke token
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from ticketing.models.base import get_db
from ticketing.models.package import PackageLocation, ProjectPackage
from ticketing.models.project import Project
from ticketing.models.qr_token import QrToken
from ticketing.models.officer_scope import OfficerScope
from ticketing.api.dependencies import get_current_user, CurrentUser
from ticketing.config.settings import get_settings

router = APIRouter()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class ScanResponse(BaseModel):
    """Returned to the chatbot after a successful token scan."""
    project_code: str
    package_id: str
    package_code: str   # e.g. "SHEP/OCB/KL/01" — human-readable lot reference
    location_code: str  # primary district — chatbot pre-fills district + province slots
    label: str          # e.g. "Lot 1 — Kakarbhitta to Sitapur"


class QrTokenOut(BaseModel):
    token: str
    package_id: str
    is_active: bool
    created_at: datetime
    created_by_user_id: str | None
    expires_at: datetime | None
    scan_url: str | None = None   # populated by list_tokens / create_token

    class Config:
        from_attributes = True


class QrTokenCreateResponse(BaseModel):
    token: str
    package_id: str
    scan_url: str   # full URL to embed in QR, e.g. https://grm.facets-ai.com/chat?t=a3f9b2c1


class PackageQrItem(BaseModel):
    """One item in the my-packages/qr response."""
    package_id: str
    package_code: str
    name: str
    project_code: str
    token: str
    scan_url: str


# ── Public: scan ──────────────────────────────────────────────────────────────

@router.get(
    "/scan/{token}",
    response_model=ScanResponse,
    summary="Resolve QR token → package context (public, no auth)",
    tags=["QR Tokens"],
)
def scan_token(token: str, db: Session = Depends(get_db)) -> ScanResponse:
    """
    Called by the chatbot at session start after reading ?t= from the URL.
    Returns project/package/location context so the bot can pre-fill slots
    and skip district/province questions.

    Returns 404 if token is unknown, inactive, or expired.
    """
    now = datetime.now(timezone.utc)

    row = db.execute(
        select(QrToken).where(QrToken.token == token)
    ).scalar_one_or_none()

    if not row or not row.is_active:
        raise HTTPException(status_code=404, detail="invalid_token")

    if row.expires_at and row.expires_at < now:
        raise HTTPException(status_code=404, detail="invalid_token")

    # Resolve package and its primary location
    package = db.execute(
        select(ProjectPackage)
        .where(ProjectPackage.package_id == row.package_id)
    ).scalar_one_or_none()

    if not package:
        raise HTTPException(status_code=404, detail="invalid_token")

    # Primary location = first PackageLocation row for this package
    loc_row = db.execute(
        select(PackageLocation)
        .where(PackageLocation.package_id == package.package_id)
        .order_by(PackageLocation.location_code)
        .limit(1)
    ).scalar_one_or_none()

    if not loc_row:
        raise HTTPException(
            status_code=422,
            detail="package_has_no_location",
        )

    # Resolve project_code from project
    project = db.execute(
        select(Project).where(Project.project_id == package.project_id)
    ).scalar_one_or_none()

    project_code = project.short_code if project else package.project_id

    return ScanResponse(
        project_code=project_code,
        package_id=package.package_id,
        package_code=package.package_code,
        location_code=loc_row.location_code,
        label=package.name,
    )


# ── Any authenticated user: QR codes for my packages ─────────────────────────

@router.get(
    "/my-packages/qr",
    response_model=list[PackageQrItem],
    summary="QR codes for packages in the current user's scope (all authenticated users)",
    tags=["QR Tokens"],
)
def my_packages_qr(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[PackageQrItem]:
    """
    Returns one QR code per package accessible to the requesting user.
    Admins see all packages; scoped officers see only their assigned packages.
    Auto-creates a token if the package has no active token yet.
    """
    # ── 1. Resolve which packages this user can see ───────────────────────────
    if current_user.is_admin:
        packages = db.execute(
            select(ProjectPackage).where(ProjectPackage.is_active == True)
            .order_by(ProjectPackage.package_code)
        ).scalars().all()
    else:
        scopes = db.execute(
            select(OfficerScope).where(OfficerScope.user_id == current_user.user_id)
        ).scalars().all()

        pkg_ids  = {s.package_id for s in scopes if s.package_id}
        proj_ids = {s.project_id for s in scopes if s.project_id}

        if not pkg_ids and not proj_ids:
            return []

        conditions = []
        if pkg_ids:
            conditions.append(ProjectPackage.package_id.in_(pkg_ids))
        if proj_ids:
            conditions.append(ProjectPackage.project_id.in_(proj_ids))

        packages = db.execute(
            select(ProjectPackage)
            .where(ProjectPackage.is_active == True)
            .where(or_(*conditions))
            .order_by(ProjectPackage.package_code)
        ).scalars().all()

    if not packages:
        return []

    # ── 2. Build project code lookup ─────────────────────────────────────────
    proj_ids_needed = {p.project_id for p in packages}
    projects = db.execute(
        select(Project).where(Project.project_id.in_(proj_ids_needed))
    ).scalars().all()
    project_map = {p.project_id: p.short_code for p in projects}

    # ── 3. Ensure every package has an active token (auto-create if missing) ──
    chatbot_base = get_settings().chatbot_webchat_url
    result: list[PackageQrItem] = []
    created_any = False

    for pkg in packages:
        token_row = db.execute(
            select(QrToken)
            .where(QrToken.package_id == pkg.package_id, QrToken.is_active == True)
            .order_by(QrToken.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        if not token_row:
            token_row = QrToken(
                package_id=pkg.package_id,
                created_by_user_id=current_user.user_id,
            )
            db.add(token_row)
            db.flush()   # assigns token value without committing yet
            created_any = True

        result.append(PackageQrItem(
            package_id=pkg.package_id,
            package_code=pkg.package_code,
            name=pkg.name,
            project_code=project_map.get(pkg.project_id, pkg.project_id),
            token=token_row.token,
            scan_url=f"{chatbot_base}?t={token_row.token}",
        ))

    if created_any:
        db.commit()

    return result


# ── Admin: token management ───────────────────────────────────────────────────

@router.get(
    "/packages/{package_id}/qr-tokens",
    response_model=list[QrTokenOut],
    summary="List QR tokens for a package (admin)",
    tags=["QR Tokens"],
)
def list_tokens(
    package_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[QrTokenOut]:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")

    rows = db.execute(
        select(QrToken)
        .where(QrToken.package_id == package_id)
        .order_by(QrToken.created_at.desc())
    ).scalars().all()

    chatbot_base = get_settings().chatbot_webchat_url
    return [
        QrTokenOut(
            token=r.token,
            package_id=r.package_id,
            is_active=r.is_active,
            created_at=r.created_at,
            created_by_user_id=r.created_by_user_id,
            expires_at=r.expires_at,
            scan_url=f"{chatbot_base}?t={r.token}",
        )
        for r in rows
    ]


@router.post(
    "/packages/{package_id}/qr-tokens",
    response_model=QrTokenCreateResponse,
    summary="Generate a new QR token for a package (admin)",
    tags=["QR Tokens"],
    status_code=201,
)
def create_token(
    package_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> QrTokenCreateResponse:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")

    # Verify package exists
    package = db.execute(
        select(ProjectPackage).where(ProjectPackage.package_id == package_id)
    ).scalar_one_or_none()
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")

    token_row = QrToken(
        package_id=package_id,
        created_by_user_id=current_user.user_id,
    )
    db.add(token_row)
    db.commit()
    db.refresh(token_row)

    chatbot_base = get_settings().chatbot_webchat_url

    return QrTokenCreateResponse(
        token=token_row.token,
        package_id=package_id,
        scan_url=f"{chatbot_base}?t={token_row.token}",
    )


@router.delete(
    "/qr-tokens/{token}",
    status_code=204,
    summary="Revoke a QR token (admin)",
    tags=["QR Tokens"],
)
def revoke_token(
    token: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")

    row = db.execute(
        select(QrToken).where(QrToken.token == token)
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Token not found")

    row.is_active = False
    db.commit()
