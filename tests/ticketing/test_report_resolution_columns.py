"""GRM-118 — the Excel says what was done and who did it, and nothing that names a person.

Pins the three report keys and what they show per case:

- `resolution_category` — header *Resolution action*: the snapshot label (catalog label for older events);
- `resolution_actor` — *Resolved by*: the actor snapshot; `Not recorded` for a standard case resolved
  before GRM-117; blank until resolved; **blank on every SEAH row**;
- `resolution_action_national` — *Resolution action (national)*: the shared action a code counts as,
  read through the **current** catalog; blank until resolved and on SEAH rows;

plus where each key may appear (the public share gets neither new key; the national one is not a
default column), the pivot, the quarterly workbook headers, and that typed resolution text never
reaches a report column.

Rows are flushed, never committed — every test rolls back.
"""
from __future__ import annotations

import io
import uuid

import openpyxl
import pytest
from sqlalchemy import select

from ticketing.api.schemas.ticket import TicketActionRequest
from ticketing.engine.ticket_actions import resolve
from ticketing.models.base import SessionLocal
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.ticket_file import TicketFile
from ticketing.models.workflow import WorkflowDefinition, WorkflowStep
from ticketing.services.pivot_table import build_pivot_table
from ticketing.services.report_rows import (
    ALL_DATA_EXPORT_COLUMNS,
    DEFAULT_REPORT_COLUMNS,
    FIELD_LABELS,
    GROUP_BY_KEYS,
    PUBLIC_REPORT_COLUMNS,
    _fetch_auxiliary_maps,
    build_report_row,
    build_xlsx_workbook,
)
from ticketing.services.resolution_catalog import create_action, set_workflow_actions
from tests.ticketing.conftest import (
    LOC_P1_JHA_BIR,
    ORG_DOR,
    PROJECT_KL_ROAD,
    WORKFLOW_SEAH_KEY,
    WORKFLOW_STANDARD_KEY,
)

pytestmark = pytest.mark.integration

NAME_IN_TEXT = "Ram Bahadur Thapa"


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture(autouse=True)
def _no_backend_call(monkeypatch):
    monkeypatch.setattr("ticketing.engine.ticket_actions.update_grievance_status", lambda *a, **k: None)


class _Actor:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.role_keys = ["site_safeguards_focal_person"]

    @property
    def is_admin(self) -> bool:
        return False

    def matches_assignee(self, assignee_id):
        return assignee_id == self.user_id


def _workflow(db, key: str) -> WorkflowDefinition:
    return db.execute(select(WorkflowDefinition).where(WorkflowDefinition.workflow_key == key)).scalar_one()


def _ticket(db, workflow_key: str = WORKFLOW_STANDARD_KEY, workflow: WorkflowDefinition | None = None) -> Ticket:
    wf = workflow or _workflow(db, workflow_key)
    step = db.execute(
        select(WorkflowStep).where(WorkflowStep.workflow_id == wf.workflow_id).order_by(WorkflowStep.step_order).limit(1)
    ).scalar_one_or_none()
    t = Ticket(
        ticket_id=str(uuid.uuid4()), grievance_id=f"rc-{uuid.uuid4().hex[:12]}", organization_id=ORG_DOR,
        location_code=LOC_P1_JHA_BIR, project_code=PROJECT_KL_ROAD, current_workflow_id=wf.workflow_id,
        current_step_id=step.step_id if step else None, assigned_to_user_id=f"rc-{uuid.uuid4().hex[:6]}@grm.local",
        status_code="IN_PROGRESS", is_seah=(wf.workflow_type or "").lower() == "seah", is_deleted=False,
        sla_breached=False, priority="NORMAL",
    )
    db.add(t)
    db.flush()
    db.add(TicketFile(file_id=str(uuid.uuid4()), ticket_id=t.ticket_id, file_name="site.jpg",
                      file_path=f"uploads/ticketing/{t.ticket_id}/site.jpg", file_type="image", file_size=1,
                      uploaded_by_user_id=t.assigned_to_user_id))
    db.flush()
    return t


def _resolve(db, ticket, category, **actor) -> Ticket:
    resolve(db, ticket, _Actor(ticket.assigned_to_user_id), TicketActionRequest(
        action_type="RESOLVE", resolution_category=category,
        note=f"Met {NAME_IN_TEXT} of ward 4; payment agreed.", **actor,
    ))
    db.flush()
    return ticket


def _resolved_before_the_lane(db, ticket, payload: dict) -> Ticket:
    """A RESOLVED event as written before GRM-116/117: a code and nothing else."""
    db.add(TicketEvent(ticket_id=ticket.ticket_id, event_type="RESOLVED", payload=payload, seen=True))
    ticket.status_code = "RESOLVED"
    db.flush()
    return ticket


def _row(db, ticket) -> dict:
    db.flush()
    aux = _fetch_auxiliary_maps(db, [ticket])
    from datetime import date
    return build_report_row(
        ticket, step_map=aux[0], project_names=aux[1], package_labels=aux[2], resolved_at_map=aux[3],
        escalated_ids=aux[4], resolution_cat_map=aux[5], resolution_extra_map=aux[6],
        date_from=date(2026, 1, 1), date_to=date(2026, 12, 31),
    )


def _cells(row: dict) -> tuple[str, str, str]:
    return row["resolution_category"], row["resolution_actor"], row["resolution_action_national"]


# ── what each row shows ─────────────────────────────────────────────────────────────────────────

def test_a_case_resolved_by_an_outside_body(db):
    t = _resolve(db, _ticket(db), "ACCEPTED_OTHER", resolution_actor_kind="external", resolution_actor_external="police")
    assert _cells(_row(db, t)) == ("Grievance accepted — other remedy", "Police", "Grievance accepted — other remedy")


def test_an_open_case_is_blank(db):
    assert _cells(_row(db, _ticket(db))) == ("", "", "")


def test_a_standard_case_resolved_before_the_lane_says_not_recorded(db):
    t = _resolved_before_the_lane(db, _ticket(db), {"resolution_category": "DEMAND_REJECTED"})
    assert _cells(_row(db, t)) == ("Complainant demand rejected", "Not recorded", "Complainant demand rejected")


def test_a_seah_case_resolved_before_the_lane_keeps_its_old_label_and_nothing_else(db):
    t = _resolved_before_the_lane(db, _ticket(db, WORKFLOW_SEAH_KEY), {"resolution_category": "DEMAND_REJECTED"})
    assert _cells(_row(db, t)) == ("Complainant demand rejected", "", "")


def test_a_seah_case_resolved_now_is_blank_everywhere(db):
    t = _resolve(db, _ticket(db, WORKFLOW_SEAH_KEY), None)
    assert _cells(_row(db, t)) == ("", "", "")


def test_the_snapshot_label_wins_over_the_current_catalog(db):
    t = _resolved_before_the_lane(db, _ticket(db), {
        "resolution_category": "ACCEPTED_OTHER", "resolution_category_label": "What the officer saw that day",
        "resolution_actor_label": "Jhapa Division Road Office",
    })
    assert _cells(_row(db, t))[:2] == ("What the officer saw that day", "Jhapa Division Road Office")


def test_a_local_action_is_counted_nationally_under_its_shared_action_and_follows_a_correction(db):
    # A workflow of DOR that offers a local action of an office under DOR.
    from ticketing.models.organization import Organization
    office = f"RC_OFFICE_{uuid.uuid4().hex[:6].upper()}"
    db.add(Organization(organization_id=office, name="RC office", parent_organization_id=ORG_DOR))
    wf = WorkflowDefinition(workflow_id=str(uuid.uuid4()), workflow_key=f"RC_{uuid.uuid4().hex[:8]}",
                            display_name="RC workflow", workflow_type="standard", owner_organization_id=office,
                            status="draft")
    db.add(wf)
    db.flush()
    local = create_action(db, code=f"TEST_{uuid.uuid4().hex[:6].upper()}", label="Culvert cleared",
                          default_wording="Culvert cleared.", owner_organization_id=office, counts_as_code="ROAD_REPAIRED")
    set_workflow_actions(db, wf, [local.code])
    t = _resolve(db, _ticket(db, workflow=wf), local.code)

    assert _cells(_row(db, t))[0] == "Culvert cleared"
    assert _cells(_row(db, t))[2] == "Hazard repaired"
    local.counts_as_code = "ROAD_MADE_SAFE"  # an admin corrects what it counts as
    db.flush()
    assert _cells(_row(db, t))[2] == "Made safe — signs, barriers or traffic control"
    assert _cells(_row(db, t))[0] == "Culvert cleared"  # the row still says what the officer chose


# ── where the keys appear ───────────────────────────────────────────────────────────────────────

def test_headers_and_column_sets():
    assert FIELD_LABELS["resolution_category"] == "Resolution action"
    assert FIELD_LABELS["resolution_actor"] == "Resolved by"
    assert FIELD_LABELS["resolution_action_national"] == "Resolution action (national)"
    i = DEFAULT_REPORT_COLUMNS.index("resolution_category")
    assert DEFAULT_REPORT_COLUMNS[i + 1] == "resolution_actor"
    assert "resolution_action_national" not in DEFAULT_REPORT_COLUMNS
    assert {"resolution_actor", "resolution_action_national"} <= set(ALL_DATA_EXPORT_COLUMNS)
    assert {"resolution_actor", "resolution_action_national"} <= GROUP_BY_KEYS


def test_the_public_share_gains_neither_key():
    # Pinned so that adding either to a public link is a visible decision, not a drive-by edit.
    assert "resolution_actor" not in PUBLIC_REPORT_COLUMNS
    assert "resolution_action_national" not in PUBLIC_REPORT_COLUMNS


def test_typed_resolution_text_never_reaches_a_report_column(db):
    t = _resolve(db, _ticket(db), "ACCEPTED_OTHER", resolution_actor_kind="external", resolution_actor_external="police")
    row = _row(db, t)
    for key in ALL_DATA_EXPORT_COLUMNS:
        assert NAME_IN_TEXT not in str(row.get(key, "")), key


def test_the_pivot_counts_cases_by_who_took_the_action(db):
    rows = [
        _row(db, _resolve(db, _ticket(db), "ACCEPTED_OTHER", resolution_actor_kind="external", resolution_actor_external="police")),
        _row(db, _resolve(db, _ticket(db), "CLASSIFIED", resolution_actor_kind="external", resolution_actor_external="police")),
        _row(db, _resolve(db, _ticket(db), "CLASSIFIED", resolution_actor_kind="external", resolution_actor_external="court")),
    ]
    out = build_pivot_table(rows, row_dims=["resolution_actor"], col_dims=[],
                            value_specs=[{"field": "ticket_id", "agg": "count"}])
    counts = {r["resolution_actor"]: r[next(k for k in r if k != "resolution_actor")] for r in out["rows"]}
    assert counts["Police"] == 2 and counts["Court"] == 1


def test_the_quarterly_workbook_carries_both_headers():
    data = build_xlsx_workbook({"resolved": [], "high": [], "overdue": [], "other": []}, DEFAULT_REPORT_COLUMNS)
    wb = openpyxl.load_workbook(io.BytesIO(data))
    headers = [c.value for c in wb["Resolved"][1]]
    assert "Resolution action" in headers and "Resolved by" in headers
    assert headers.index("Resolved by") == headers.index("Resolution action") + 1
