"""Effective role keys merge user_roles, officer_scopes, and admin_scopes."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from ticketing.api.dependencies import CurrentUser, enrich_user
from ticketing.models.officer_scope import OfficerScope
from ticketing.models.user import Role, UserRole
from ticketing.services.admin_access import load_effective_role_keys

pytestmark = pytest.mark.integration


def test_effective_role_keys_merges_user_roles_and_scopes(db):
    email = f"eff-{uuid.uuid4().hex[:8]}@grm.local"
    role_user = db.execute(
        select(Role).where(Role.role_key == "csc_officer")
    ).scalar_one_or_none()
    role_scope = db.execute(
        select(Role).where(Role.role_key == "site_safeguards_focal_person")
    ).scalar_one_or_none()
    if not role_user or not role_scope:
        pytest.skip("standard roles not seeded")

    db.add(
        UserRole(
            user_id=email,
            role_id=role_user.role_id,
            organization_id="NP_CTJ",
        )
    )
    db.add(
        OfficerScope(
            user_id=email,
            role_key="site_safeguards_focal_person",
            organization_id="NP_CTJ",
            project_code="52097003",
        )
    )
    db.commit()

    keys = load_effective_role_keys(db, email)
    assert "csc_officer" in keys
    assert "site_safeguards_focal_person" in keys


def test_enrich_user_prefers_db_over_stale_jwt(db):
    email = f"jwt-{uuid.uuid4().hex[:8]}@grm.local"
    role_scope = db.execute(
        select(Role).where(Role.role_key == "site_safeguards_focal_person")
    ).scalar_one_or_none()
    if not role_scope:
        pytest.skip("site_safeguards_focal_person not seeded")

    db.add(
        OfficerScope(
            user_id=email,
            role_key="site_safeguards_focal_person",
            organization_id="NP_CTJ",
            package_id=str(uuid.uuid4()),
        )
    )
    db.commit()

    user = CurrentUser(
        user_id=email,
        role_keys=["csc_officer"],
        organization_id="NP_CTJ",
    )
    enrich_user(db, user)
    assert "site_safeguards_focal_person" in user.role_keys
    assert user.role_keys == load_effective_role_keys(db, email)
