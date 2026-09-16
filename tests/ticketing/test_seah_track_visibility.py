"""Track-derived SEAH visibility (DESIGN-cast-model §3.1 re-key).

Integration (live seeded DB): SEAH access is derived from being cast on a SEAH-track workflow
— the seeded named SEAH roles AND synthetic per-step-tier keys minted for a SEAH workflow are
recognized; standard roles are not (isolation preserved).
"""
from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from ticketing.api.dependencies import CurrentUser
from ticketing.services.admin_access import can_see_seah_extended
from ticketing.services.seah_visibility import seah_track_role_keys, user_is_seah_track_member

pytestmark = pytest.mark.integration


# The seeded SEAH workflow's slots. Named operational roles (`seah_national_officer`) stopped
# appearing on steps on 2026-08-09: each (step, tier) slot owns its key now, because a key shared
# by two slots made cast assignments ambiguous. Track membership is still "cast on a SEAH-track
# workflow" — it is the keys that changed, not the rule.
SEAH_L1_ACTOR = "wf:KL_ROAD_SEAH:SEAH_LEVEL_1_NATIONAL:actor"
SEAH_L2_ACTOR = "wf:KL_ROAD_SEAH:SEAH_LEVEL_2_HQ:actor"
STD_L1_ACTOR = "wf:KL_ROAD_STANDARD:LEVEL_1_SITE:actor"


def test_seeded_seah_roles_are_track_members(db):
    keys = seah_track_role_keys(db)
    # The seeded KL_ROAD_SEAH workflow casts these on its steps.
    assert SEAH_L1_ACTOR in keys
    assert SEAH_L2_ACTOR in keys
    # Standard slots are NOT SEAH-track (isolation).
    assert STD_L1_ACTOR not in keys
    assert "grc_chair" not in keys


def test_user_is_seah_track_member(db):
    assert user_is_seah_track_member(db, [SEAH_L1_ACTOR]) is True
    assert user_is_seah_track_member(db, [STD_L1_ACTOR]) is False
    assert user_is_seah_track_member(db, []) is False


def test_can_see_seah_via_track_member_flag():
    # The flag (computed at enrich time) grants SEAH visibility on its own.
    u = CurrentUser(user_id="x@grm.local", role_keys=[])
    u.seah_track_member = True
    assert can_see_seah_extended(u) is True
    u2 = CurrentUser(user_id="y@grm.local", role_keys=["site_safeguards_focal_person"])
    assert can_see_seah_extended(u2) is False


def test_synthetic_seah_key_is_a_track_member(db):
    """A synthetic per-step-tier key minted for a SEAH workflow is SEAH-track (so its holder,
    staffed via the cast, gains SEAH visibility — the gap the re-key closes)."""
    from ticketing.models.base import SessionLocal
    from ticketing.models.workflow import WorkflowDefinition, WorkflowStep
    from ticketing.services.cast_staffing import set_step_tier_keys

    s = SessionLocal()
    wf_key = f"SEAH_TEST_{uuid.uuid4().hex[:6].upper()}"
    wf = WorkflowDefinition(workflow_key=wf_key, display_name="SEAH Test", workflow_type="seah",
                            status="published")
    s.add(wf); s.flush()
    step = WorkflowStep(workflow_id=wf.workflow_id, step_order=1, step_key="L1",
                        display_name="SEAH L1", assigned_role_key="", informed_roles=[], observer_roles=[])
    set_step_tier_keys(s, wf, step, supervisor=False, participants=False, observers=False)
    s.add(step); s.commit()
    actor_key = step.assigned_role_key
    try:
        assert actor_key.startswith("wf:")
        assert user_is_seah_track_member(s, [actor_key]) is True
    finally:
        from ticketing.models.user import Role, UserRole
        s.execute(sa.delete(WorkflowStep).where(WorkflowStep.workflow_id == wf.workflow_id))
        obj = s.get(WorkflowDefinition, wf.workflow_id)
        if obj:
            s.delete(obj)
        like = f"wf:{wf_key}:%"
        rids = [r.role_id for r in s.execute(sa.select(Role).where(Role.role_key.like(like))).scalars().all()]
        if rids:
            s.execute(sa.delete(UserRole).where(UserRole.role_id.in_(rids)))
            s.execute(sa.delete(Role).where(Role.role_id.in_(rids)))
        s.commit()
        s.close()
