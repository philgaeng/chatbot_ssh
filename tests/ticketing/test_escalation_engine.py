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

import pytest
from sqlalchemy import delete, func, select

from ticketing.engine import escalation as escalation_mod
from ticketing.engine.escalation import (
    escalate_ticket,
    get_tickets_needing_escalation,
    run_sla_check,
)
from ticketing.models.base import SessionLocal
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.workflow import WorkflowDefinition, WorkflowStep

from tests.ticketing.conftest import LOC_P1_JHA_BIR, ORG_DOR, PROJECT_KL_ROAD, ROLE_L1

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
