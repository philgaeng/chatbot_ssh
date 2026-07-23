"""R1 — SEAH leak lockdown (BUILD-REVIEW B1 + B2).

A non-SEAH identity must receive NOTHING that reveals a SEAH case, via ANY path:
the notification badge/panel endpoints, the @mention/@all loop, GRC convene, and the
step-tier viewer cast (whitelist, all tiers). SEAH-cleared identities are unaffected.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from ticketing.api.dependencies import CurrentUser, get_current_user, get_db
from ticketing.api.main import app
from ticketing.engine.escalation import _apply_step_tier_roles
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.ticket_viewer import TicketViewer
from ticketing.models.workflow import WorkflowDefinition, WorkflowStep
from ticketing.services.chart_behaviors import user_can_see_seah

pytestmark = pytest.mark.integration

ORG_DOR = "DOR"
LOC = "P1_JHA_BIR"


def _make_ticket(ctx, *, is_seah: bool, assigned_to: str) -> Ticket:
    wf = ctx.db.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.workflow_key == "KL_ROAD_STANDARD")
    ).scalar_one()
    step = ctx.db.execute(
        select(WorkflowStep).where(WorkflowStep.workflow_id == wf.workflow_id)
        .order_by(WorkflowStep.step_order).limit(1)
    ).scalar_one()
    t = Ticket(
        ticket_id=str(uuid.uuid4()),
        grievance_id=f"GRV-SEAHLEAK-{uuid.uuid4().hex[:8]}",
        grievance_summary="SEAH: complainant reports harassment — sensitive." if is_seah else "Dust on the road.",
        organization_id=ORG_DOR,
        location_code=LOC,
        project_code="KL_ROAD",
        current_workflow_id=wf.workflow_id,
        current_step_id=step.step_id,
        assigned_to_user_id=assigned_to,
        status_code="OPEN",
        is_seah=is_seah,
        is_deleted=False,
        sla_breached=False,
        priority="NORMAL",
    )
    ctx.db.add(t)
    ctx.db.flush()
    ctx.ticket_ids.append(t.ticket_id)
    return t


def _add_event(ctx, ticket: Ticket, user_id: str) -> TicketEvent:
    ev = TicketEvent(
        event_id=str(uuid.uuid4()),
        ticket_id=ticket.ticket_id,
        event_type="MENTION",
        note="test event",
        seen=False,
        assigned_to_user_id=user_id,
    )
    ctx.db.add(ev)
    ctx.db.flush()
    return ev


def _client(db, *, role_keys: list[str], user_id: str):
    def override_user():
        return CurrentUser(user_id=user_id, role_keys=role_keys)

    def override_db():
        yield db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


# ── the per-user SEAH-visibility helper ───────────────────────────────────────

def test_user_can_see_seah_helper(db, ctx):
    seah_uid = f"seah-{uuid.uuid4().hex[:8]}@grm.local"
    plain_uid = f"plain-{uuid.uuid4().hex[:8]}@grm.local"
    ctx.add_scope(seah_uid, role_key="seah_national_officer", location_code=LOC, project_code="KL_ROAD")
    ctx.add_scope(plain_uid, role_key="site_safeguards_focal_person", location_code=LOC, project_code="KL_ROAD")
    db.flush()
    assert user_can_see_seah(db, seah_uid) is True
    assert user_can_see_seah(db, plain_uid) is False


# ── notification endpoints (B1) ───────────────────────────────────────────────

def test_badge_and_notifications_hide_seah_from_non_seah_user(db, ctx):
    target = f"nonseah-{uuid.uuid4().hex[:8]}@grm.local"
    seah_t = _make_ticket(ctx, is_seah=True, assigned_to=target)
    _add_event(ctx, seah_t, target)
    db.flush()
    try:
        # Non-SEAH identity → the SEAH event is invisible (count 0, empty panel).
        client = _client(db, role_keys=["site_safeguards_focal_person"], user_id=target)
        badge = client.get("/api/v1/users/me/badge")
        assert badge.status_code == 200 and badge.json()["unseen_count"] == 0, badge.text
        notifs = client.get("/api/v1/users/me/notifications")
        assert notifs.status_code == 200
        ids = [i["grievance_id"] for i in notifs.json()["items"]]
        assert seah_t.grievance_id not in ids
        assert notifs.json()["total"] == 0
    finally:
        app.dependency_overrides.clear()

    try:
        # SEAH identity → the same event IS visible.
        client = _client(db, role_keys=["seah_national_officer"], user_id=target)
        badge = client.get("/api/v1/users/me/badge")
        assert badge.json()["unseen_count"] == 1, badge.text
        notifs = client.get("/api/v1/users/me/notifications")
        ids = [i["grievance_id"] for i in notifs.json()["items"]]
        assert seah_t.grievance_id in ids
    finally:
        app.dependency_overrides.clear()


def test_standard_ticket_notification_visible_to_non_seah(db, ctx):
    """Regression: a STANDARD event is unaffected by the SEAH filter."""
    target = f"std-{uuid.uuid4().hex[:8]}@grm.local"
    std_t = _make_ticket(ctx, is_seah=False, assigned_to=target)
    _add_event(ctx, std_t, target)
    db.flush()
    try:
        client = _client(db, role_keys=["site_safeguards_focal_person"], user_id=target)
        assert client.get("/api/v1/users/me/badge").json()["unseen_count"] == 1
        ids = [i["grievance_id"] for i in client.get("/api/v1/users/me/notifications").json()["items"]]
        assert std_t.grievance_id in ids
    finally:
        app.dependency_overrides.clear()


# ── step-tier viewer cast whitelist (B2) ──────────────────────────────────────

def _fake_step(*, informed, observer, supervisor) -> WorkflowStep:
    return WorkflowStep(
        step_id=str(uuid.uuid4()), workflow_id=str(uuid.uuid4()), step_order=99,
        step_key="TEST", display_name="Test", assigned_role_key="pd_piu_safeguards_focal",
        supervisor_role=supervisor, informed_roles=informed, observer_roles=observer,
    )


def _is_viewer(db, ticket_id, uid) -> bool:
    return db.execute(
        select(TicketViewer).where(TicketViewer.ticket_id == ticket_id, TicketViewer.user_id == uid)
    ).scalar_one_or_none() is not None


def test_apply_step_tier_roles_whitelists_seah_only_on_seah_ticket(db, ctx):
    seah_uid = f"seah-{uuid.uuid4().hex[:8]}@grm.local"
    grc_uid = f"grc-{uuid.uuid4().hex[:8]}@grm.local"
    obs_uid = f"obs-{uuid.uuid4().hex[:8]}@grm.local"
    # All scoped to the ticket's province so _scope_candidates would find them.
    ctx.add_scope(seah_uid, role_key="seah_national_officer", location_code="P1", project_code="KL_ROAD", includes_children=True)
    ctx.add_scope(grc_uid, role_key="grc_chair", location_code="P1", project_code="KL_ROAD", includes_children=True)
    ctx.add_scope(obs_uid, role_key="adb_national_project_director", location_code="P1", project_code="KL_ROAD", includes_children=True)
    db.flush()

    # non-SEAH roles in EVERY tier + one SEAH role in informed.
    step = _fake_step(
        informed=["seah_national_officer", "grc_chair"],
        observer=["adb_national_project_director"],
        supervisor="grc_chair",
    )
    seah_t = _make_ticket(ctx, is_seah=True, assigned_to="someone@grm.local")
    _apply_step_tier_roles(db, seah_t, step)
    db.flush()
    assert _is_viewer(db, seah_t.ticket_id, seah_uid) is True, "SEAH role must still be cast"
    assert _is_viewer(db, seah_t.ticket_id, grc_uid) is False, "non-SEAH informed/supervisor must be suppressed"
    assert _is_viewer(db, seah_t.ticket_id, obs_uid) is False, "non-SEAH observer must be suppressed"

    # On a STANDARD ticket the same non-SEAH roles ARE cast (no suppression).
    std_t = _make_ticket(ctx, is_seah=False, assigned_to="someone@grm.local")
    _apply_step_tier_roles(db, std_t, step)
    db.flush()
    assert _is_viewer(db, std_t.ticket_id, grc_uid) is True
    assert _is_viewer(db, std_t.ticket_id, obs_uid) is True
