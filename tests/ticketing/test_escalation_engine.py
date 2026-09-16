"""HR-04: SLA watchdog crash-safety + concurrency-safety.

First tests for ticketing.engine.escalation. Exercises the savepoint-per-ticket
isolation, the FOR-UPDATE-SKIP-LOCKED candidate selection, and double-run idempotence
against a real Postgres DB (the concurrency case needs two live sessions — no sqlite).

Uses a throwaway workflow (3 SLA'd steps, final step also SLA'd) so behaviour does not
depend on seed specifics. Run in-container:
  python -m pytest tests/ticketing/test_escalation_engine.py -v
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from ticketing.api.dependencies import CurrentUser, get_authenticated_user, get_db
from ticketing.api.main import app
from ticketing.api.ticket_access import assert_ticket_visibility
from ticketing.engine import escalation as escalation_mod
from ticketing.engine import ticket_actions
from ticketing.engine.escalation import (
    convene_grc,
    get_tickets_needing_escalation,
    run_sla_check,
)
from ticketing.models.base import SessionLocal
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.ticket_file import TicketFile
from ticketing.models.ticket_overdue_episode import TicketOverdueEpisode
from ticketing.models.ticket_viewer import TicketViewer
from ticketing.models.workflow import WorkflowDefinition, WorkflowStep

from tests.ticketing.conftest import (
    LOC_P1_JHA_BIR,
    LOC_P1_MOR,
    ORG_DOR,
    PROJECT_KL_ROAD,
    ROLE_L1,
    WORKFLOW_SEAH_KEY,
    WORKFLOW_STANDARD_KEY,
)

pytestmark = pytest.mark.integration


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Hr04Env:
    """Throwaway workflow + breached tickets, with guaranteed teardown."""

    def __init__(self, db):
        self.db = db
        self.workflow_id = str(uuid.uuid4())
        self.step_ids: list[str] = []
        self.ticket_ids: list[str] = []
        self.step1: WorkflowStep
        self.step2: WorkflowStep
        self.step_final: WorkflowStep

    def setup(self) -> "Hr04Env":
        wf = WorkflowDefinition(
            workflow_id=self.workflow_id,
            workflow_key=f"HR04_TEST_{uuid.uuid4().hex[:8]}",
            display_name="HR-04 test workflow",
            workflow_type="standard",
            status="published",
        )
        self.db.add(wf)

        def _step(order: int, key: str, sla: int | None) -> WorkflowStep:
            s = WorkflowStep(
                step_id=str(uuid.uuid4()),
                workflow_id=self.workflow_id,
                step_order=order,
                step_key=key,
                display_name=key,
                assigned_role_key=ROLE_L1,
                resolution_time_days=sla,
                supervisor_role=None,
                informed_roles=[],
                observer_roles=[],
            )
            self.db.add(s)
            self.step_ids.append(s.step_id)
            return s

        self.step1 = _step(10, "HR04_L1", 1)
        self.step2 = _step(20, "HR04_L2", 1)
        self.step_final = _step(30, "HR04_FINAL", 1)
        self.db.commit()
        return self

    def make_breached_ticket(self, step: WorkflowStep) -> Ticket:
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            grievance_id=f"HR04-{uuid.uuid4().hex[:12]}",
            organization_id=ORG_DOR,
            location_code=LOC_P1_JHA_BIR,
            project_code=PROJECT_KL_ROAD,
            current_workflow_id=self.workflow_id,
            current_step_id=step.step_id,
            status_code="IN_PROGRESS",
            assigned_to_user_id=None,
            step_started_at=_now() - timedelta(days=5),  # SLA (1 day) long past
            sla_breached=False,
            is_seah=False,
            is_deleted=False,
            priority="NORMAL",
        )
        self.db.add(ticket)
        self.db.commit()
        self.ticket_ids.append(ticket.ticket_id)
        return ticket

    def cleanup(self) -> None:
        s = SessionLocal()
        try:
            if self.ticket_ids:
                s.execute(delete(Ticket).where(Ticket.ticket_id.in_(self.ticket_ids)))
            if self.step_ids:
                s.execute(delete(WorkflowStep).where(WorkflowStep.step_id.in_(self.step_ids)))
            s.execute(
                delete(WorkflowDefinition).where(
                    WorkflowDefinition.workflow_id == self.workflow_id
                )
            )
            s.commit()
        finally:
            s.close()


@pytest.fixture
def hr04(db):
    env = Hr04Env(db).setup()
    try:
        yield env
    finally:
        env.cleanup()


def _escalated_events(db, ticket_id: str) -> int:
    return db.execute(
        select(func.count())
        .select_from(TicketEvent)
        .where(TicketEvent.ticket_id == ticket_id, TicketEvent.event_type == "ESCALATED")
    ).scalar_one()


def _events_of_type(db, ticket_id: str, event_type: str) -> int:
    return db.execute(
        select(func.count())
        .select_from(TicketEvent)
        .where(TicketEvent.ticket_id == ticket_id, TicketEvent.event_type == event_type)
    ).scalar_one()


# ── 1. Breach → escalate (step advances, event written, assignee resolved) ────

def test_sla_breach_escalates_in_one_transaction(hr04):
    ticket = hr04.make_breached_ticket(hr04.step1)

    summary = run_sla_check(hr04.db)
    assert summary["escalated"] == 1
    assert summary["errors"] == 0

    hr04.db.expire_all()
    fresh = hr04.db.get(Ticket, ticket.ticket_id)
    assert fresh.current_step_id == hr04.step2.step_id
    assert fresh.status_code == "ESCALATED"
    assert _escalated_events(hr04.db, ticket.ticket_id) == 1
    # Step 2 role is a seeded field role for this location → assignment resolves.
    assert fresh.assigned_to_user_id is not None


# ── 2. Final-step breach → no crash, terminal event, step unchanged ───────────

def test_final_step_breach_marks_but_does_not_advance(hr04):
    ticket = hr04.make_breached_ticket(hr04.step_final)

    summary = run_sla_check(hr04.db)
    assert summary["final_step_breach"] == 1
    assert summary["escalated"] == 0
    assert summary["errors"] == 0

    hr04.db.expire_all()
    fresh = hr04.db.get(Ticket, ticket.ticket_id)
    assert fresh.current_step_id == hr04.step_final.step_id  # unchanged
    assert _events_of_type(hr04.db, ticket.ticket_id, "SLA_BREACH_FINAL_STEP") == 1
    assert _escalated_events(hr04.db, ticket.ticket_id) == 0


# ── 3. Mid-loop failure isolation ─────────────────────────────────────────────

def test_mid_loop_failure_isolates_bad_ticket(hr04, monkeypatch):
    """Reproduces the exact silent-corruption mode and proves the savepoint kills it.

    #2 crashes AFTER advancing its step but BEFORE the ESCALATED event — while #1 and #3
    escalate cleanly and drive the outer commit. Pre-fix (no savepoint) that commit also
    persisted #2's half-escalation (step advanced, no audit event, no assignee). With the
    per-ticket savepoint, #2's partial state is rolled back and only #1/#3 persist.
    """
    from ticketing.engine.workflow_engine import get_next_step

    t1 = hr04.make_breached_ticket(hr04.step1)
    t_bad = hr04.make_breached_ticket(hr04.step1)
    t3 = hr04.make_breached_ticket(hr04.step1)

    real_escalate = escalation_mod.escalate_ticket

    def _crash_after_mutation(ticket, db, **kwargs):
        if ticket.ticket_id == t_bad.ticket_id:
            nxt = get_next_step(ticket, db)
            ticket.current_step_id = nxt.step_id  # advance the step ...
            ticket.status_code = "ESCALATED"
            ticket.sla_breached = False
            raise RuntimeError("crash after step mutation, before event")  # ... then die
        return real_escalate(ticket, db, **kwargs)

    monkeypatch.setattr(escalation_mod, "escalate_ticket", _crash_after_mutation)

    summary = run_sla_check(hr04.db)
    assert summary["escalated"] == 2
    assert summary["errors"] == 1

    hr04.db.expire_all()
    # The two healthy tickets fully escalated (and their commit fired).
    for good in (t1, t3):
        fresh = hr04.db.get(Ticket, good.ticket_id)
        assert fresh.current_step_id == hr04.step2.step_id
        assert fresh.status_code == "ESCALATED"
        assert _escalated_events(hr04.db, good.ticket_id) == 1

    # The failing ticket is completely untouched — the sibling commit did NOT persist a
    # step-advanced ticket with no audit event (the pre-fix corruption).
    bad = hr04.db.get(Ticket, t_bad.ticket_id)
    assert bad.current_step_id == hr04.step1.step_id
    assert bad.status_code == "IN_PROGRESS"
    assert _escalated_events(hr04.db, t_bad.ticket_id) == 0
    assert bad.current_overdue_episode_id is None  # breach episode also rolled back


# ── 4. No partial state (throw between step mutation and event write) ──────────

def test_no_partial_state_when_escalation_throws(hr04, monkeypatch):
    ticket = hr04.make_breached_ticket(hr04.step1)

    # auto_assign runs AFTER current_step_id/status are mutated but BEFORE the
    # ESCALATED event is written — force the crash exactly there.
    def _boom(*args, **kwargs):
        raise RuntimeError("crash after step mutation, before event")

    monkeypatch.setattr(escalation_mod, "auto_assign_for_workflow_step", _boom)

    summary = run_sla_check(hr04.db)
    assert summary["escalated"] == 0
    assert summary["errors"] == 1

    hr04.db.expire_all()
    fresh = hr04.db.get(Ticket, ticket.ticket_id)
    # Savepoint rollback ⇒ step, status and SLA flag are exactly as before.
    assert fresh.current_step_id == hr04.step1.step_id
    assert fresh.status_code == "IN_PROGRESS"
    assert fresh.sla_breached is False
    assert fresh.current_overdue_episode_id is None
    assert _escalated_events(hr04.db, ticket.ticket_id) == 0


# ── 5. Double-run idempotence ─────────────────────────────────────────────────

def test_double_run_escalates_exactly_once(hr04):
    ticket = hr04.make_breached_ticket(hr04.step1)

    first = run_sla_check(hr04.db)
    second = run_sla_check(hr04.db)

    assert first["escalated"] == 1
    # After the first escalation step_started_at resets ⇒ no longer a candidate.
    assert second["escalated"] == 0

    hr04.db.expire_all()
    assert _escalated_events(hr04.db, ticket.ticket_id) == 1


# ── 6. Concurrency: a row locked elsewhere is SKIP-LOCKED by the watchdog ─────

def test_locked_ticket_is_skipped_not_blocked(hr04):
    ticket = hr04.make_breached_ticket(hr04.step1)

    locker = SessionLocal()
    watchdog = SessionLocal()
    try:
        # Session A grabs the row lock (as the manual ESCALATE path now does).
        locked = locker.execute(
            select(Ticket).where(Ticket.ticket_id == ticket.ticket_id).with_for_update()
        ).scalar_one()
        assert locked.ticket_id == ticket.ticket_id

        # Session B's watchdog must NOT see the locked row (SKIP LOCKED) and must not block.
        candidates = get_tickets_needing_escalation(watchdog)
        assert ticket.ticket_id not in {t.ticket_id for t in candidates}

        summary = run_sla_check(watchdog)
        assert summary["escalated"] == 0
    finally:
        watchdog.rollback()
        watchdog.close()
        locker.rollback()
        locker.close()

    # Lock released and never escalated — ticket is still on its original step.
    hr04.db.expire_all()
    fresh = hr04.db.get(Ticket, ticket.ticket_id)
    assert fresh.current_step_id == hr04.step1.step_id
    assert _escalated_events(hr04.db, ticket.ticket_id) == 0


# ══════════════════════════════════════════════════════════════════════════════
# H2-07 — escalation coverage on the SEEDED KL Road workflows
# ══════════════════════════════════════════════════════════════════════════════
# HR-04 above uses a throwaway generic workflow. These extend coverage to the real
# seeded workflows: multi-level chains with role-based assignee resolution, SEAH-track
# isolation, manual-then-auto interleaving at the API layer, and the per-transition
# notification mechanism.
#
# Seeded roles → officers (ticketing/constants/demo_officers.py, scoped in seed/mock_tickets.py):
_L2_OFFICERS = {"l2-piu@grm.local", "l2-piu-2@grm.local", "l2-piu-3@grm.local"}
_L3_OFFICERS = {"grc-chair@grm.local"}
_L1_OFFICER = "l1-officer@grm.local"       # site_safeguards_focal_person, P1_MOR
_SEAH_L1_OFFICER = "seah@grm.local"        # seah_national_officer, P1
_SEAH_OFFICERS = {"seah@grm.local", "seah-hq@grm.local"}  # every seeded SEAH-capable user

_BREACH_DAYS = 400  # older than any seeded SLA (max 15d) → guaranteed breach at any level


class ChainEnv:
    """Tickets created on the *seeded* KL Road workflows, with fresh-session teardown of
    every dependent row (events, viewers, files, overdue episodes)."""

    def __init__(self, db):
        self.db = db
        self.ticket_ids: list[str] = []

    def _step(self, workflow_key: str, step_key: str) -> WorkflowStep:
        wf = self.db.execute(
            select(WorkflowDefinition).where(WorkflowDefinition.workflow_key == workflow_key)
        ).scalar_one()
        return self.db.execute(
            select(WorkflowStep).where(
                WorkflowStep.workflow_id == wf.workflow_id,
                WorkflowStep.step_key == step_key,
            )
        ).scalar_one()

    def make_ticket(self, workflow_key, step_key, *, is_seah, assigned_to, location_code, breached=True):
        step = self._step(workflow_key, step_key)
        started = _now() - timedelta(days=_BREACH_DAYS) if breached else _now()
        t = Ticket(
            ticket_id=str(uuid.uuid4()),
            grievance_id=f"H207-{uuid.uuid4().hex[:12]}",
            organization_id=ORG_DOR,
            location_code=location_code,
            project_code=PROJECT_KL_ROAD,
            current_workflow_id=step.workflow_id,
            current_step_id=step.step_id,
            status_code="IN_PROGRESS",
            assigned_to_user_id=assigned_to,
            step_started_at=started,
            sla_breached=False,
            is_seah=is_seah,
            is_deleted=False,
            priority="NORMAL",
        )
        self.db.add(t)
        self.db.commit()
        self.ticket_ids.append(t.ticket_id)
        return t

    def ack_and_breach(self, ticket) -> None:
        """Simulate the next-level officer acknowledging (ESCALATED→IN_PROGRESS, clock set)
        and the new SLA then breaching — so the watchdog re-selects the ticket. The watchdog
        candidate query excludes ESCALATED, so a real chain needs an ACK between transitions."""
        ticket.status_code = "IN_PROGRESS"
        ticket.step_started_at = _now() - timedelta(days=_BREACH_DAYS)
        ticket.sla_breached = False
        self.db.add(ticket)
        self.db.commit()

    def add_image(self, ticket) -> None:
        self.db.add(TicketFile(
            file_id=str(uuid.uuid4()), ticket_id=ticket.ticket_id, file_name="site.jpg",
            file_path="x/site.jpg", file_type="image", file_size=1, uploaded_by_user_id="system",
        ))
        self.db.commit()

    def cleanup(self) -> None:
        if not self.ticket_ids:
            return
        s = SessionLocal()
        try:
            ids = self.ticket_ids
            s.execute(delete(TicketEvent).where(TicketEvent.ticket_id.in_(ids)))
            s.execute(delete(TicketViewer).where(TicketViewer.ticket_id.in_(ids)))
            s.execute(delete(TicketFile).where(TicketFile.ticket_id.in_(ids)))
            s.execute(delete(TicketOverdueEpisode).where(TicketOverdueEpisode.ticket_id.in_(ids)))
            s.execute(delete(Ticket).where(Ticket.ticket_id.in_(ids)))
            s.commit()
        finally:
            s.close()


@pytest.fixture
def chain(db):
    env = ChainEnv(db)
    try:
        yield env
    finally:
        env.cleanup()


def _current_step_key(db, ticket_id: str) -> str:
    row = db.execute(
        select(WorkflowStep.step_key)
        .select_from(Ticket)
        .join(WorkflowStep, WorkflowStep.step_id == Ticket.current_step_id)
        .where(Ticket.ticket_id == ticket_id)
    ).scalar_one()
    return row


# ── H2-07.1 — full L1→L2→L3 chain, correct assignees, then GRC convene + resolve ──

def test_full_standard_chain_assignees_events_and_lifecycle(chain):
    db = chain.db
    t = chain.make_ticket(
        WORKFLOW_STANDARD_KEY, "LEVEL_1_SITE",
        is_seah=False, assigned_to=_L1_OFFICER, location_code=LOC_P1_MOR,
    )

    # L1 → L2 (breach; role-based auto-assign to a seeded PIU officer)
    assert run_sla_check(db)["escalated"] == 1
    db.expire_all()
    t = db.get(Ticket, t.ticket_id)
    assert _current_step_key(db, t.ticket_id) == "LEVEL_2_PIU"
    assert t.status_code == "ESCALATED"
    assert t.assigned_to_user_id in _L2_OFFICERS
    assert _escalated_events(db, t.ticket_id) == 1

    # L2 → L3 (ack at L2 first so the watchdog re-selects it)
    chain.ack_and_breach(t)
    assert run_sla_check(db)["escalated"] == 1
    db.expire_all()
    t = db.get(Ticket, t.ticket_id)
    assert _current_step_key(db, t.ticket_id) == "LEVEL_3_GRC"
    assert t.assigned_to_user_id in _L3_OFFICERS
    assert _escalated_events(db, t.ticket_id) == 2  # events accumulate in order

    # GRC convene at L3 — status-only, does NOT advance the step
    convene_grc(t, db, note="Hearing scheduled",
                convened_by_user_id="grc-chair@grm.local", actor_role="grc_chair")
    db.commit()
    db.expire_all()
    t = db.get(Ticket, t.ticket_id)
    assert t.status_code == "GRC_HEARING_SCHEDULED"
    assert _current_step_key(db, t.ticket_id) == "LEVEL_3_GRC"
    assert _events_of_type(db, t.ticket_id, "GRC_CONVENED") == 1

    # Resolve at L3 (needs an image; backend status push is non-fatal)
    chain.add_image(t)
    actor = CurrentUser(user_id="grc-chair@grm.local", role_keys=["grc_chair"])
    payload = SimpleNamespace(
        resolution_category="CLASSIFIED",
        note="Contractor required to wet-spray the road twice daily.",
    )
    ticket_actions.resolve(db, t, actor, payload)
    db.commit()
    db.expire_all()
    t = db.get(Ticket, t.ticket_id)
    assert t.status_code == "RESOLVED"
    assert _events_of_type(db, t.ticket_id, "RESOLVED") == 1
    # No spurious extra escalations across the whole lifecycle.
    assert _escalated_events(db, t.ticket_id) == 2


# ── H2-07.2 — SEAH escalation stays inside the SEAH workflow + SEAH-only visibility ──

def test_seah_escalation_isolated_to_seah_track(chain):
    db = chain.db
    t = chain.make_ticket(
        WORKFLOW_SEAH_KEY, "SEAH_LEVEL_1_NATIONAL",
        is_seah=True, assigned_to=_SEAH_L1_OFFICER, location_code=LOC_P1_MOR,
    )

    assert run_sla_check(db)["escalated"] == 1
    db.expire_all()
    t = db.get(Ticket, t.ticket_id)

    # Advanced WITHIN the SEAH workflow to its L2 step — never into a standard step.
    assert _current_step_key(db, t.ticket_id) == "SEAH_LEVEL_2_HQ"
    # Isolation invariant: the assignee is a SEAH officer (or unassigned when no dedicated
    # L2 SEAH officer is in scope — here the L1 SEAH officer is retained) — NEVER a standard
    # officer. _SEAH_OFFICERS = every seeded SEAH-capable user for this workflow.
    assert t.assigned_to_user_id is None or t.assigned_to_user_id in _SEAH_OFFICERS

    # No standard-role viewer was cast (SEAH steps have empty informed/observer + the
    # engine's SEAH whitelist) — every viewer must be a SEAH-eligible user.
    viewers = db.execute(
        select(TicketViewer.user_id).where(TicketViewer.ticket_id == t.ticket_id)
    ).scalars().all()
    assert all(v in _SEAH_OFFICERS for v in viewers), f"SEAH ticket leaked to non-SEAH viewer: {viewers}"

    # Access wall (HR-02 dependency): a standard-role officer cannot see the escalated
    # SEAH ticket; a SEAH officer can.
    from fastapi import HTTPException

    standard = CurrentUser(user_id="l1-officer@grm.local", role_keys=["site_safeguards_focal_person"])
    with pytest.raises(HTTPException) as exc:
        assert_ticket_visibility(db, t, standard)
    assert exc.value.status_code == 403

    seah_officer = CurrentUser(user_id="seah-hq@grm.local", role_keys=["seah_hq_officer"])
    assert_ticket_visibility(db, t, seah_officer)  # must not raise


# ── H2-07.3 — manual ESCALATE (API) then watchdog does NOT double-advance ─────

def _api_escalate(ticket_id: str, persona: CurrentUser) -> int:
    """Manual ESCALATE via TestClient with `persona` injected, on its own session."""
    sess = SessionLocal()

    def _u():
        return persona

    def _d():
        try:
            yield sess
        finally:
            sess.close()

    app.dependency_overrides[get_authenticated_user] = _u
    app.dependency_overrides[get_db] = _d
    try:
        client = TestClient(app)
        resp = client.post(
            f"/api/v1/tickets/{ticket_id}/actions",
            json={"action_type": "ESCALATE", "escalation_notes": "Manual escalation (H2-07 test)."},
        )
        return resp.status_code
    finally:
        app.dependency_overrides.clear()


def test_manual_then_auto_no_double_advance(chain):
    db = chain.db
    t = chain.make_ticket(
        WORKFLOW_STANDARD_KEY, "LEVEL_1_SITE",
        is_seah=False, assigned_to=_L1_OFFICER, location_code=LOC_P1_MOR,
    )
    chain.add_image(t)  # manual ESCALATE requires an image attachment

    # Officer manually escalates via the API → L1 advances to L2, step clock resets.
    persona = CurrentUser(user_id=_L1_OFFICER, role_keys=["site_safeguards_focal_person"])
    status = _api_escalate(t.ticket_id, persona)
    assert status == 200, f"manual ESCALATE should succeed (got {status})"

    db.expire_all()
    t = db.get(Ticket, t.ticket_id)
    assert _current_step_key(db, t.ticket_id) == "LEVEL_2_PIU"
    assert t.status_code == "ESCALATED"
    assert _escalated_events(db, t.ticket_id) == 1

    # The watchdog running in the same window must NOT re-advance it: status is ESCALATED
    # and step_started_at was reset to NULL → it is not a breach candidate.
    assert run_sla_check(db)["escalated"] == 0
    db.expire_all()
    t = db.get(Ticket, t.ticket_id)
    assert _current_step_key(db, t.ticket_id) == "LEVEL_2_PIU"  # still L2, not L3
    assert _escalated_events(db, t.ticket_id) == 1              # exactly one transition


# ── H2-07.4 — one notification per transition (per-path mechanism) ────────────

def test_watchdog_transition_notifies_new_assignee_in_app(chain):
    """The batch watchdog path notifies the NEW officer via the in-app badge — the ESCALATED
    TicketEvent carries notify_user_id (stored in TicketEvent.assigned_to_user_id) = the new
    assignee, unseen — exactly one per transition. (The watchdog path emits no Celery task;
    that is only the manual/API path — see the next test.)"""
    db = chain.db
    t = chain.make_ticket(
        WORKFLOW_STANDARD_KEY, "LEVEL_1_SITE",
        is_seah=False, assigned_to=_L1_OFFICER, location_code=LOC_P1_MOR,
    )
    assert run_sla_check(db)["escalated"] == 1
    db.expire_all()
    t = db.get(Ticket, t.ticket_id)

    esc_events = db.execute(
        select(TicketEvent).where(
            TicketEvent.ticket_id == t.ticket_id, TicketEvent.event_type == "ESCALATED"
        )
    ).scalars().all()
    assert len(esc_events) == 1
    ev = esc_events[0]
    assert ev.assigned_to_user_id == t.assigned_to_user_id  # notified officer = new assignee
    assert ev.assigned_to_user_id in _L2_OFFICERS
    assert ev.seen is False  # unseen badge


def test_manual_escalate_enqueues_one_assignment_notification(chain, monkeypatch):
    """The manual/API escalate path enqueues exactly one assignment-notification Celery task
    per transition (via enqueue_assignment_notifications → notify_assignment.delay)."""
    from ticketing.api.routers.tickets import actions as actions_router

    calls: list[tuple] = []
    monkeypatch.setattr(
        actions_router, "enqueue_assignment_notifications",
        lambda *a, **k: calls.append((a, k)),
    )

    db = chain.db
    t = chain.make_ticket(
        WORKFLOW_STANDARD_KEY, "LEVEL_1_SITE",
        is_seah=False, assigned_to=_L1_OFFICER, location_code=LOC_P1_MOR,
    )
    chain.add_image(t)

    persona = CurrentUser(user_id=_L1_OFFICER, role_keys=["site_safeguards_focal_person"])
    assert _api_escalate(t.ticket_id, persona) == 200

    assert len(calls) == 1, f"expected exactly one assignment notification, got {len(calls)}"
    # Enqueued for the NEW (L2) assignee, tagged as an escalation.
    db.expire_all()
    t = db.get(Ticket, t.ticket_id)
    _args, kwargs = calls[0]
    assert kwargs.get("event") == "escalation"
    assert _args[1] in _L2_OFFICERS  # (ticket_id, assigned_to_user_id, step_id, ...)
