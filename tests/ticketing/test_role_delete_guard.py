"""SH-5 — role delete guard counts tier references (OC-06 F15).

_role_usage_counts (used by DELETE /roles to 409 an in-use role) previously counted a
step only via assigned_role_key, so a role held only as supervisor/informed/observer
could be deleted and orphan those references. It now counts all four tiers.

Integration-only: exercised against the seeded KL_ROAD workflows. The keys are the per-slot
ones (2026-08-09) — each (step, tier) slot owns its key, so "supervisor-only" and
"informed-only" are now literally true of a key rather than a property of an operational role
that happened to appear in one field.
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
    # Held as supervisor of L2 and nothing else — the old guard counted only assigned_role_key.
    steps, _ = _role_usage_counts(db, "wf:KL_ROAD_STANDARD:LEVEL_2_PIU:supervisor")
    assert steps >= 1


def test_informed_only_role_is_counted(db):
    # Appears only in LEVEL_3_GRC informed_roles.
    steps, _ = _role_usage_counts(db, "wf:KL_ROAD_STANDARD:LEVEL_3_GRC:informed")
    assert steps >= 1


def test_assigned_role_still_counted(db):
    steps, _ = _role_usage_counts(db, "wf:KL_ROAD_STANDARD:LEVEL_1_SITE:actor")
    assert steps >= 1


def test_unreferenced_role_counts_zero(db):
    steps, officers = _role_usage_counts(db, "totally_unused_role_xyz")
    assert steps == 0
    assert officers == 0
