"""
Upsert GRM roles from ticketing.constants.grm_role_catalog.

Used by kl_road_standard.seed_roles() and any full-environment seed.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.constants.grm_role_catalog import GRM_ROLE_CATALOG
from ticketing.models.user import Role

logger = logging.getLogger(__name__)


def _uuid() -> str:
    return str(uuid.uuid4())


def upsert_grm_roles(db: Session) -> None:
    """Create or update Role rows from the canonical catalog (idempotent)."""
    for entry in GRM_ROLE_CATALOG:
        rk = entry["role_key"]
        existing = db.execute(select(Role).where(Role.role_key == rk)).scalar_one_or_none()
        perms = entry.get("permissions") or []
        desc = entry.get("description")
        wf = entry.get("workflow_scope")
        jmode = entry.get("jurisdiction_mode")
        dname = entry["display_name"]
        rkind = entry.get("role_kind") or (
            "admin" if rk in ("super_admin", "country_admin", "project_admin") else "operational"
        )
        rorigin = entry.get("role_origin", "system")
        if existing:
            existing.display_name = dname
            existing.permissions = perms
            existing.description = desc
            existing.workflow_scope = wf
            existing.role_kind = rkind
            existing.role_origin = rorigin
            if jmode:
                existing.jurisdiction_mode = jmode
            logger.info("  = role updated from catalog: %s", rk)
        else:
            db.add(
                Role(
                    role_id=_uuid(),
                    role_key=rk,
                    display_name=dname,
                    permissions=perms,
                    description=desc,
                    workflow_scope=wf,
                    jurisdiction_mode=jmode,
                    role_kind=rkind,
                    role_origin=rorigin,
                )
            )
            logger.info("  + role from catalog: %s", rk)
    db.flush()
