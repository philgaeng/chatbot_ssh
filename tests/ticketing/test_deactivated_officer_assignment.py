"""R3 (BUILD-REVIEW M2) — a soft-deactivated officer is out of the assignment pool AND
does not count toward go-live staffing coverage. The system assignment path never passes
through enrich_user, so the exclusion must live in _scope_candidates + the go-live predicates.
"""
from __future__ import annotations

import uuid

import pytest

from ticketing.engine.workflow_engine import _scope_candidates
from ticketing.services.officer_admin import _lifecycle_user_key, set_officer_active
from ticketing.services.project_go_live import _has_officer_on_project_wide

pytestmark = pytest.mark.integration

ROLE_L1 = "site_safeguards_focal_person"
UNSTAFFED_ROLE = "adb_hq_project"  # nobody is seeded on this role on KL Road


def _cleanup_onboarding(db, user_id):
    from ticketing.models.officer_onboarding import OfficerOnboarding
    ob = db.get(OfficerOnboarding, _lifecycle_user_key(user_id))
    if ob is not None:
        db.delete(ob)
    db.flush()


def test_deactivated_officer_excluded_from_scope_candidates(db, ctx):
    uid = f"deact-{uuid.uuid4().hex[:8]}@grm.local"
    ctx.add_scope(uid, role_key=ROLE_L1, location_code="P1_JHA_BIR", project_code="KL_ROAD")
    db.flush()

    def candidates():
        return _scope_candidates(
            role_key=ROLE_L1, organization_id="DOR",
            location_code="P1_JHA_BIR", project_code="KL_ROAD", db=db,
        )

    try:
        assert uid in candidates(), "active officer should be a candidate"
        set_officer_active(db, uid, False)
        db.flush()
        assert uid not in candidates(), "deactivated officer must not be a candidate"
        set_officer_active(db, uid, True)
        db.flush()
        assert uid in candidates(), "reactivated officer is a candidate again"
    finally:
        _cleanup_onboarding(db, uid)


def test_go_live_coverage_excludes_deactivated_officer(db, ctx, kl_road_project):
    """A level covered ONLY by a deactivated officer reports unstaffed (feeds C1/C5)."""
    uid = f"deact-cov-{uuid.uuid4().hex[:8]}@grm.local"
    ctx.add_scope(uid, role_key=UNSTAFFED_ROLE, location_code=None, project_code="KL_ROAD")
    db.flush()

    def covered():
        return _has_officer_on_project_wide(db, project=kl_road_project, grm_role_key=UNSTAFFED_ROLE)

    try:
        assert covered() is True, "active officer covers the level"
        set_officer_active(db, uid, False)
        db.flush()
        assert covered() is False, "deactivated-only coverage must report unstaffed"
        set_officer_active(db, uid, True)
        db.flush()
        assert covered() is True
    finally:
        _cleanup_onboarding(db, uid)
