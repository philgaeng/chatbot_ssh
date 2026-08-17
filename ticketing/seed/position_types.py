# SPDX-License-Identifier: Apache-2.0

"""
Seed ~5 real DoR standard-track position types (OC-02, doc 16 §3.2).

Demonstrates the whole point of the matrix: two distinct titles ("Site Safeguards Focal
Person" and "Senior Divisional Engineer") that share ONE role
(`site_safeguards_focal_person`) — the position carries the title + reporting line, the
role carries the permissions/step bindings.

Idempotent + defensive: skips a position type whose `default_role_key` is not seeded
(so it never creates a dangling matrix ref) and skips ones that already exist. Owned by
DoR (`owner_organization_id="DOR"`) to exercise the org-scoped catalog. Caller commits.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.models.organization import Organization
from ticketing.models.position_type import PositionType
from ticketing.models.user import Role

logger = logging.getLogger(__name__)

# position_key, display_name, display_name_ne, allowed_unit_types, default_role_key,
# reports_to_position_key, reports_to_locus, visibility_mode
_DOR_POSITION_TYPES: list[dict] = [
    dict(
        position_key="pd_piu_safeguards_focal",
        display_name="PD/PIU Safeguards Focal Person",
        display_name_ne="आयोजना निर्देशक सुरक्षा फोकल व्यक्ति",
        allowed_unit_types=["directorate", "provincial_office"],
        default_role_key="pd_piu_safeguards_focal",
        reports_to_position_key=None,
        reports_to_locus=None,
        visibility_mode="direct_reports",
    ),
    dict(
        position_key="site_safeguards_focal",
        display_name="Site Safeguards Focal Person",
        display_name_ne="स्थल सुरक्षा फोकल व्यक्ति",
        allowed_unit_types=["division_office"],
        default_role_key="site_safeguards_focal_person",
        reports_to_position_key="pd_piu_safeguards_focal",
        reports_to_locus="parent_unit",
        visibility_mode="none",
    ),
    dict(
        position_key="senior_divisional_engineer",
        display_name="Senior Divisional Engineer",
        display_name_ne="वरिष्ठ डिभिजन इन्जिनियर",
        allowed_unit_types=["division_office"],
        # SDE acts as the site safeguards focal — same role, different title (the matrix in action).
        default_role_key="site_safeguards_focal_person",
        reports_to_position_key="pd_piu_safeguards_focal",
        reports_to_locus="parent_unit",
        visibility_mode="none",
    ),
    dict(
        position_key="grc_chair",
        display_name="GRC Chair",
        display_name_ne="गुनासो सुनुवाइ समिति अध्यक्ष",
        allowed_unit_types=["directorate"],
        default_role_key="grc_chair",
        reports_to_position_key=None,
        reports_to_locus=None,
        visibility_mode="none",
    ),
    dict(
        position_key="grc_member",
        display_name="GRC Member",
        display_name_ne="गुनासो सुनुवाइ समिति सदस्य",
        allowed_unit_types=["directorate"],
        default_role_key="grc_member",
        reports_to_position_key=None,
        reports_to_locus=None,
        visibility_mode="none",
    ),
]


def seed_position_types(db: Session) -> None:
    """Insert DoR standard-track position types. Idempotent; caller commits."""
    owner = "DOR" if db.get(Organization, "DOR") else None
    for spec in _DOR_POSITION_TYPES:
        key = spec["position_key"]
        if db.execute(
            select(PositionType).where(PositionType.position_key == key)
        ).scalar_one_or_none():
            continue  # already seeded
        role = db.execute(
            select(Role).where(Role.role_key == spec["default_role_key"])
        ).scalar_one_or_none()
        if role is None:
            logger.warning(
                "Skipping position type %s: default_role_key %s not in role catalog",
                key,
                spec["default_role_key"],
            )
            continue
        db.add(
            PositionType(
                position_key=key,
                display_name=spec["display_name"],
                display_name_ne=spec["display_name_ne"],
                allowed_unit_types=spec["allowed_unit_types"],
                reports_to_position_key=spec["reports_to_position_key"],
                reports_to_locus=spec["reports_to_locus"],
                default_role_key=spec["default_role_key"],
                visibility_mode=spec["visibility_mode"],
                workflow_track="standard",
                owner_organization_id=owner,
            )
        )
    db.flush()
