"""SH-5 — role delete guard counts tier references (OC-06 F15).

_role_usage_counts (used by DELETE /roles to 409 an in-use role) previously counted a
step only via assigned_role_key, so a role held only as supervisor/informed/observer
could be deleted and orphan those references. It now counts all four tiers.

Integration-only: exercised against the seeded KL_ROAD workflows, where
adb_national_project_director is a supervisor-only role and grc_member is informed-only.
"""
from __future__ import annotations

import pytest

from ticketing.api.routers.users import _role_usage_counts

pytestmark = pytest.mark.integration


@pytest.fixture
def db():
    from ticketing.models.base import SessionLocal

    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def test_supervisor_only_role_is_counted(db):
    # supervisor on LEVEL_2_PIU, never an assigned role — the old guard missed it.
    steps, _ = _role_usage_counts(db, "adb_national_project_director")
    assert steps >= 1


def test_informed_only_role_is_counted(db):
    # appears only in LEVEL_3_GRC informed_roles.
    steps, _ = _role_usage_counts(db, "grc_member")
    assert steps >= 1


def test_assigned_role_still_counted(db):
    steps, _ = _role_usage_counts(db, "site_safeguards_focal_person")
    assert steps >= 1


def test_unreferenced_role_counts_zero(db):
    steps, officers = _role_usage_counts(db, "totally_unused_role_xyz")
    assert steps == 0
    assert officers == 0
