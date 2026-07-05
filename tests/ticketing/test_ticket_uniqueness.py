"""HR-03: one active ticket per grievance_id.

Covers the partial unique index (uq_tickets_grievance_id_active WHERE is_deleted=false),
idempotent intake, the two-session race, and the migration's pre-flight dedup routine.

Requires a migrated + seeded ticketing schema (KL_ROAD workflow). Run in-container:
  python -m pytest tests/ticketing/test_ticket_uniqueness.py -v
"""
from __future__ import annotations

import importlib.util
import pathlib
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, func, select, text

from ticketing.api.dependencies import get_db, verify_api_key
from ticketing.api.main import app
from ticketing.api.schemas.ticket import TicketCreate
from ticketing.models.base import SessionLocal
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.workflow import WorkflowDefinition, WorkflowStep
from ticketing.services.ticket_intake import (
    DuplicateTicketError,
    create_or_refresh_ticket_from_intake,
    create_ticket_from_intake,
)

from tests.ticketing.conftest import LOC_P1_JHA_BIR, ORG_DOR, PROJECT_KL_ROAD

pytestmark = pytest.mark.integration

_UNIQUE_INDEX = "uq_tickets_grievance_id_active"


def _gid() -> str:
    return f"HR03-{uuid.uuid4().hex[:12]}"


def _payload(grievance_id: str, **overrides) -> TicketCreate:
    base = dict(
        grievance_id=grievance_id,
        organization_id=ORG_DOR,
        location_code=LOC_P1_JHA_BIR,
        project_code=PROJECT_KL_ROAD,
        priority="NORMAL",
        is_seah=False,
        grievance_summary="HR-03 uniqueness test",
    )
    base.update(overrides)
    return TicketCreate(**base)


def _active_count(db, grievance_id: str) -> int:
    return db.execute(
        select(func.count())
        .select_from(Ticket)
        .where(Ticket.grievance_id == grievance_id, Ticket.is_deleted.is_(False))
    ).scalar_one()


def _purge(grievance_ids: list[str]) -> None:
    """Hard-delete every ticket (any is_deleted state) for these grievance_ids."""
    if not grievance_ids:
        return
    s = SessionLocal()
    try:
        ids = [
            r[0]
            for r in s.execute(
                select(Ticket.ticket_id).where(Ticket.grievance_id.in_(grievance_ids))
            ).all()
        ]
        if ids:
            # ticket_events / viewers / episodes cascade on ticket delete.
            s.execute(delete(Ticket).where(Ticket.ticket_id.in_(ids)))
        s.commit()
    finally:
        s.close()


@pytest.fixture
def gids():
    """Track grievance_ids created by a test; hard-delete them on teardown."""
    tracked: list[str] = []
    yield tracked
    _purge(tracked)


# ── 1. Idempotent service: second intake returns the existing ticket ──────────

def test_create_or_refresh_second_call_returns_existing(db, gids):
    gid = _gid()
    gids.append(gid)

    ticket_a, created_a = create_or_refresh_ticket_from_intake(db, _payload(gid))
    db.commit()
    assert created_a is True

    ticket_b, created_b = create_or_refresh_ticket_from_intake(db, _payload(gid))
    db.commit()

    assert created_b is False
    assert ticket_b.ticket_id == ticket_a.ticket_id
    assert _active_count(db, gid) == 1


def test_create_primitive_raises_pointing_at_existing(db, gids):
    """The create-only primitive still refuses a duplicate — but names the survivor."""
    gid = _gid()
    gids.append(gid)

    ticket_a = create_ticket_from_intake(db, _payload(gid))
    db.commit()

    with pytest.raises(DuplicateTicketError) as exc_info:
        create_ticket_from_intake(db, _payload(gid))
    db.rollback()

    assert exc_info.value.ticket_id == ticket_a.ticket_id
    assert _active_count(db, gid) == 1


# ── 2. POST /api/v1/tickets twice → 201 then 200, same ticket_id ──────────────

def test_post_tickets_twice_is_idempotent(gids):
    gid = _gid()
    gids.append(gid)
    session = SessionLocal()

    def _override_db():
        try:
            yield session
        finally:
            pass  # closed in teardown below

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[verify_api_key] = lambda: "test-key"
    try:
        from fastapi.testclient import TestClient

        client = TestClient(app)
        body = _payload(gid).model_dump()

        r1 = client.post("/api/v1/tickets", json=body)
        assert r1.status_code == 201, r1.text
        tid1 = r1.json()["ticket_id"]

        r2 = client.post("/api/v1/tickets", json=body)
        assert r2.status_code == 200, r2.text
        tid2 = r2.json()["ticket_id"]

        assert tid1 == tid2
        assert _active_count(session, gid) == 1
    finally:
        app.dependency_overrides.clear()
        session.close()


# ── 3. Soft-deleted ticket does not block re-creation (partial predicate) ─────

def test_soft_deleted_ticket_does_not_block_recreation(db, gids):
    gid = _gid()
    gids.append(gid)

    first = create_ticket_from_intake(db, _payload(gid))
    db.commit()

    first.is_deleted = True
    db.commit()

    # A fresh active ticket for the same grievance_id is now allowed by the
    # partial unique index (predicate WHERE is_deleted = false).
    second = create_ticket_from_intake(db, _payload(gid))
    db.commit()

    assert second.ticket_id != first.ticket_id
    assert _active_count(db, gid) == 1  # only the non-deleted one counts


# ── 4. Two-session race → exactly one survivor, loser gets the winner ─────────

def test_two_session_race_yields_single_survivor(db, gids):
    gid = _gid()
    gids.append(gid)

    db_a = SessionLocal()
    db_b = SessionLocal()
    outcome: dict = {}

    try:
        # A inserts + flushes but does NOT commit yet — its row is held uncommitted.
        ticket_a = create_ticket_from_intake(db_a, _payload(gid))

        def _run_b():
            try:
                # B's guard read (READ COMMITTED) does not see A's uncommitted row, so
                # B proceeds to flush and its INSERT blocks on A's unique-index entry.
                create_ticket_from_intake(db_b, _payload(gid))
                db_b.commit()
                outcome["b"] = ("committed", None)
            except DuplicateTicketError as exc:
                db_b.rollback()
                outcome["b"] = ("duplicate", exc.ticket_id)
            except Exception as exc:  # pragma: no cover - surfaced in assertion
                db_b.rollback()
                outcome["b"] = ("error", repr(exc))

        worker = threading.Thread(target=_run_b)
        worker.start()
        time.sleep(0.5)  # let B reach its blocking INSERT
        db_a.commit()  # A wins; B's blocked INSERT now raises unique violation
        worker.join(timeout=15)

        assert not worker.is_alive(), "B thread did not finish (possible deadlock)"
        assert outcome["b"][0] == "duplicate", outcome["b"]
        assert outcome["b"][1] == ticket_a.ticket_id
        assert _active_count(db, gid) == 1
    finally:
        db_a.close()
        db_b.close()


# ── 5. Migration pre-flight dedup routine ─────────────────────────────────────

def _load_migration():
    path = (
        pathlib.Path(__file__).resolve().parents[2]
        / "ticketing/migrations/versions/h2j4l6n8_unique_active_ticket_per_grievance.py"
    )
    spec = importlib.util.spec_from_file_location("hr03_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _insert_ticket(db, grievance_id: str, *, created_at: datetime) -> str:
    wf = db.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.workflow_key == "KL_ROAD_STANDARD")
    ).scalar_one()
    step = db.execute(
        select(WorkflowStep)
        .where(WorkflowStep.workflow_id == wf.workflow_id)
        .order_by(WorkflowStep.step_order)
        .limit(1)
    ).scalar_one()
    ticket = Ticket(
        ticket_id=str(uuid.uuid4()),
        grievance_id=grievance_id,
        organization_id=ORG_DOR,
        location_code=LOC_P1_JHA_BIR,
        project_code=PROJECT_KL_ROAD,
        current_workflow_id=wf.workflow_id,
        current_step_id=step.step_id,
        status_code="OPEN",
        is_seah=False,
        is_deleted=False,
        sla_breached=False,
        priority="NORMAL",
        created_at=created_at,
    )
    db.add(ticket)
    db.flush()
    return ticket.ticket_id


def test_migration_dedup_keeps_oldest_and_soft_deletes_losers(db):
    """Simulate the pre-index duplicate state, run the dedup routine, assert the merge.

    The whole test runs in one uncommitted transaction. Postgres DDL is transactional,
    so the temporary DROP INDEX and every insert are rolled back in ``finally`` —
    leaving the shared schema untouched even if an assertion fails.
    """
    migration = _load_migration()
    gid = _gid()
    now = datetime.now(timezone.utc)

    try:
        # Temporarily remove the guard so two ACTIVE tickets can coexist.
        db.execute(text(f"DROP INDEX ticketing.{_UNIQUE_INDEX}"))

        older = _insert_ticket(db, gid, created_at=now - timedelta(hours=2))
        newer = _insert_ticket(db, gid, created_at=now - timedelta(minutes=5))
        db.flush()

        migration._dedup_active_tickets(db.connection())
        db.flush()
        db.expire_all()

        survivor = db.get(Ticket, older)
        loser = db.get(Ticket, newer)
        assert survivor.is_deleted is False
        assert loser.is_deleted is True
        assert _active_count(db, gid) == 1

        system_events = db.execute(
            select(TicketEvent).where(
                TicketEvent.ticket_id == older,
                TicketEvent.event_type == "SYSTEM",
            )
        ).scalars().all()
        assert len(system_events) == 1
        payload = system_events[0].payload or {}
        assert newer in (payload.get("soft_deleted_ticket_ids") or [])
    finally:
        db.rollback()  # undoes DROP INDEX + all inserts (transactional DDL)
