"""H2-02 Pass 3 — direct engine tests for ticketing.engine.ticket_actions.

The officer-action logic used to live inside the ``perform_action`` router and could
only be reached through an HTTP request. Pass 3 moved each branch into an engine
function ``(db, ticket, actor, payload) -> ActionOutcome`` that raises the typed
``ActionError`` (never ``HTTPException``). These tests call every handler **directly**
— no TestClient, no router — proving the split is real: one happy-path call per action
plus the ActionError guard contract.

Everything runs inside one uncommitted transaction against the seeded DB and is rolled
back on teardown, so no rows persist. Run in-container:
  python -m pytest tests/ticketing/test_ticket_actions_unit.py -v
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from ticketing.api.schemas.ticket import TicketActionRequest
from ticketing.engine.ticket_actions import (
    ActionError,
    ActionOutcome,
    acknowledge,
    escalate,
    field_report,
    grc_convene,
    note,
    request_reassignment,
    resolve,
)
from ticketing.models.ticket import Ticket
from ticketing.models.ticket_file import TicketFile
from ticketing.models.workflow import WorkflowDefinition, WorkflowStep

from tests.ticketing.conftest import (
    LOC_P1_JHA_BIR,
    ORG_DOR,
    PROJECT_KL_ROAD,
    WORKFLOW_STANDARD_KEY,
)

pytestmark = pytest.mark.integration

L1_ROLE = "site_safeguards_focal_person"


class _Actor:
    """Minimal CurrentUser stand-in — only what the engine handlers touch."""

    def __init__(self, user_id: str, role_keys: list[str], is_admin: bool = False):
        self.user_id = user_id
        self.role_keys = list(role_keys)
        self._is_admin = is_admin

    @property
    def is_admin(self) -> bool:
        return self._is_admin

    def matches_assignee(self, assignee_id: str | None) -> bool:
        return assignee_id is not None and assignee_id == self.user_id


class _Env:
    """Builds seeded-workflow tickets that never commit (rolled back on teardown)."""

    def __init__(self, db):
        self.db = db
        wf = db.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.workflow_key == WORKFLOW_STANDARD_KEY
            )
        ).scalar_one()
        self.workflow_id = wf.workflow_id
        self.first_step = db.execute(
            select(WorkflowStep)
            .where(WorkflowStep.workflow_id == wf.workflow_id)
            .order_by(WorkflowStep.step_order)
            .limit(1)
        ).scalar_one()

    def ticket(self, *, assigned_to: str, status: str = "OPEN", is_seah: bool = False) -> Ticket:
        row = Ticket(
            ticket_id=str(uuid.uuid4()),
            grievance_id=f"unit-{uuid.uuid4().hex[:12]}",
            organization_id=ORG_DOR,
            location_code=LOC_P1_JHA_BIR,
            project_code=PROJECT_KL_ROAD,
            current_workflow_id=self.workflow_id,
            current_step_id=self.first_step.step_id,
            assigned_to_user_id=assigned_to,
            status_code=status,
            is_seah=is_seah,
            is_deleted=False,
            sla_breached=False,
            priority="NORMAL",
        )
        self.db.add(row)
        self.db.flush()
        return row

    def add_image(self, ticket: Ticket) -> None:
        self.db.add(
            TicketFile(
                file_id=str(uuid.uuid4()),
                ticket_id=ticket.ticket_id,
                file_name="site.jpg",
                file_path=f"uploads/ticketing/{ticket.ticket_id}/site.jpg",
                file_type="image",
                file_size=123,
                uploaded_by_user_id=ticket.assigned_to_user_id,
            )
        )
        self.db.flush()


@pytest.fixture
def env(db):
    e = _Env(db)
    try:
        yield e
    finally:
        db.rollback()


def _actor_for(ticket: Ticket) -> _Actor:
    return _Actor(ticket.assigned_to_user_id, [L1_ROLE])


# ── ACKNOWLEDGE ───────────────────────────────────────────────────────────────

def test_acknowledge_starts_the_case(env):
    ticket = env.ticket(assigned_to="unit-l1@grm.local")
    payload = TicketActionRequest(action_type="ACKNOWLEDGE", note="Taking ownership")

    outcome = acknowledge(env.db, ticket, _actor_for(ticket), payload)

    assert isinstance(outcome, ActionOutcome)
    assert outcome.event.event_type == "ACKNOWLEDGED"
    assert outcome.ticket.status_code == "IN_PROGRESS"
    assert outcome.event.new_status_code == "IN_PROGRESS"
    # no async side-effects on a plain acknowledge
    assert outcome.notify_complainant_text is None
    assert outcome.generate_findings is False


# ── NOTE ──────────────────────────────────────────────────────────────────────

def test_note_records_note_and_auto_acknowledges(env):
    ticket = env.ticket(assigned_to="unit-l1@grm.local")
    payload = TicketActionRequest(action_type="NOTE", note="Called complainant, no answer")

    outcome = note(env.db, ticket, _actor_for(ticket), payload)

    assert outcome.event.event_type == "NOTE_ADDED"
    assert (outcome.event.payload or {}).get("internal") is True
    # translation fires for the new note event
    assert outcome.translate_note_event_id == outcome.event.event_id
    # assigned actor engaging an OPEN ticket auto-starts the case
    assert outcome.ticket.status_code == "IN_PROGRESS"


def test_note_requires_note_text(env):
    ticket = env.ticket(assigned_to="unit-l1@grm.local")
    payload = TicketActionRequest(action_type="NOTE", note=None)

    with pytest.raises(ActionError) as exc:
        note(env.db, ticket, _actor_for(ticket), payload)
    assert exc.value.status_code == 422


# ── FIELD_REPORT ──────────────────────────────────────────────────────────────

def test_field_report_is_a_flagged_note(env):
    ticket = env.ticket(assigned_to="unit-l1@grm.local")
    payload = TicketActionRequest(action_type="FIELD_REPORT", note="Dust suppression not running")

    outcome = field_report(env.db, ticket, _actor_for(ticket), payload)

    assert outcome.event.event_type == "NOTE_ADDED"
    assert (outcome.event.payload or {}).get("is_field_report") is True
    assert outcome.translate_note_event_id == outcome.event.event_id


# ── ESCALATE ──────────────────────────────────────────────────────────────────

def test_escalate_advances_step_and_notifies(env):
    ticket = env.ticket(assigned_to="unit-l1@grm.local")
    env.add_image(ticket)
    original_step_id = ticket.current_step_id
    payload = TicketActionRequest(
        action_type="ESCALATE", escalation_notes="No progress on site, escalating to PIU"
    )

    outcome = escalate(env.db, ticket, _actor_for(ticket), payload)

    assert outcome.event.event_type == "ESCALATED"
    assert outcome.ticket.status_code == "ESCALATED"
    assert outcome.ticket.current_step_id != original_step_id  # moved to LEVEL_2_PIU
    assert outcome.notify_complainant_text is not None
    # OC-04 §5.5: the step the escalation came OFF is carried for post-commit notify
    assert outcome.supervisor_notify_from_step is not None
    assert outcome.supervisor_notify_from_step.step_id == original_step_id


def test_escalate_requires_image_attachment(env):
    ticket = env.ticket(assigned_to="unit-l1@grm.local")  # no image added
    payload = TicketActionRequest(action_type="ESCALATE", escalation_notes="ready")

    with pytest.raises(ActionError) as exc:
        escalate(env.db, ticket, _actor_for(ticket), payload)
    assert "image" in exc.value.detail.lower()


def test_escalate_requires_notes(env):
    ticket = env.ticket(assigned_to="unit-l1@grm.local")
    env.add_image(ticket)
    payload = TicketActionRequest(action_type="ESCALATE")  # no escalation_notes / note

    with pytest.raises(ActionError) as exc:
        escalate(env.db, ticket, _actor_for(ticket), payload)
    assert "escalation_notes" in exc.value.detail


# ── RESOLVE ───────────────────────────────────────────────────────────────────

def test_resolve_marks_resolved_and_schedules_summary(env):
    ticket = env.ticket(assigned_to="unit-l1@grm.local")
    env.add_image(ticket)
    payload = TicketActionRequest(
        action_type="RESOLVE",
        resolution_category="CLASSIFIED",
        note="Reviewed and classified; monitoring continues under the GRM.",
    )

    outcome = resolve(env.db, ticket, _actor_for(ticket), payload)

    assert outcome.event.event_type == "RESOLVED"
    assert outcome.ticket.status_code == "RESOLVED"
    assert outcome.generate_findings is True
    assert outcome.generate_resolved_summary is True
    assert outcome.translate_resolution_event_id is not None
    assert outcome.notify_complainant_text is not None


def test_resolve_rejects_unknown_category(env):
    ticket = env.ticket(assigned_to="unit-l1@grm.local")
    env.add_image(ticket)
    payload = TicketActionRequest(
        action_type="RESOLVE",
        resolution_category="NOT_A_CATEGORY",
        note="This text is plenty long enough to pass the note length gate.",
    )

    with pytest.raises(ActionError) as exc:
        resolve(env.db, ticket, _actor_for(ticket), payload)
    assert exc.value.status_code == 422


# ── REASSIGNMENT_REQUESTED ────────────────────────────────────────────────────

def test_request_reassignment_routes_to_supervisor(env):
    ticket = env.ticket(assigned_to="unit-l1@grm.local")
    payload = TicketActionRequest(
        action_type="REASSIGNMENT_REQUESTED", reassignment_reason_code="OUT_OF_LOCATION"
    )

    outcome = request_reassignment(env.db, ticket, _actor_for(ticket), payload)

    assert outcome.event.event_type == "REASSIGNMENT_REQUESTED"
    # step-1 supervisor role (pd_piu_safeguards_focal) is seeded → ticket routes to them
    assert outcome.ticket.assigned_to_user_id is not None
    assert outcome.ticket.assigned_to_user_id != "unit-l1@grm.local"
    assert outcome.assignment_notify is not None
    assert outcome.assignment_notify[2] == "reassign"


def test_request_reassignment_rejects_bad_reason(env):
    ticket = env.ticket(assigned_to="unit-l1@grm.local")
    payload = TicketActionRequest(
        action_type="REASSIGNMENT_REQUESTED", reassignment_reason_code="NONSENSE"
    )

    with pytest.raises(ActionError) as exc:
        request_reassignment(env.db, ticket, _actor_for(ticket), payload)
    assert exc.value.status_code == 422


# ── GRC_CONVENE ───────────────────────────────────────────────────────────────

def test_grc_convene_schedules_hearing(env):
    ticket = env.ticket(assigned_to="unit-grc@grm.local")
    payload = TicketActionRequest(action_type="GRC_CONVENE", note="Hearing on 2026-08-01")

    outcome = grc_convene(env.db, ticket, _Actor("unit-grc@grm.local", ["grc_chair"]), payload)

    assert outcome.event.event_type == "GRC_CONVENED"
    assert outcome.ticket.status_code == "GRC_HEARING_SCHEDULED"
