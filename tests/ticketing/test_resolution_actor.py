"""GRM-117 — who took the action that resolved a case: the *Resolved by* of the manager's Excel.

Pins:

- "my office" is derived from the officer's positions (DESIGN §3.2.1), never their name;
- each kind — self, another organization, an outside body — stores the same four keys on both
  resolution events, with a label the server computes (a request cannot set it: no typed text reaches
  the Excel);
- the refusals: an unknown or inactive organization, an unknown outside body, an officer with several
  offices who chose none, a "self" office that is not the officer's;
- a case in a sensitive workflow records no actor, and refuses one;
- ticket detail offers the choices, and none on a sensitive workflow.

Rows are flushed, never committed — every test rolls back.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ticketing.api.schemas.ticket import TicketActionRequest
from ticketing.constants.resolution import RESOLUTION_EXTERNAL_ACTORS
from ticketing.engine.ticket_actions import ActionError, resolve
from ticketing.models.base import SessionLocal
from ticketing.models.officer_position import OfficerPosition
from ticketing.models.organization import Organization
from ticketing.models.position_type import PositionType
from ticketing.models.project import Project, ProjectOrganization
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.ticket_file import TicketFile
from ticketing.models.workflow import WorkflowDefinition, WorkflowStep
from ticketing.services.resolution_actor import resolve_self_offices
from tests.ticketing.conftest import (
    LOC_P1_JHA_BIR,
    ORG_DOR,
    PROJECT_KL_ROAD,
    WORKFLOW_SEAH_KEY,
    WORKFLOW_STANDARD_KEY,
)

pytestmark = pytest.mark.integration

ACTOR_KEYS = ("resolution_actor_kind", "resolution_actor_organization_id",
              "resolution_actor_external", "resolution_actor_label")


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def _tag() -> str:
    return uuid.uuid4().hex[:6].upper()


def _org(db, name: str, parent: str | None = ORG_DOR, *, active=True) -> str:
    oid = f"RB_{name}_{_tag()}"
    db.add(Organization(organization_id=oid, name=f"Office {name}", parent_organization_id=parent, is_active=active))
    db.flush()
    return oid


def _officer(db, *orgs: str, inactive: tuple[str, ...] = ()) -> str:
    user = f"rb-{uuid.uuid4().hex[:8]}@grm.local"
    position_type = db.execute(select(PositionType.position_type_id).limit(1)).scalar_one()
    for org in orgs:
        db.add(OfficerPosition(user_id=user, position_type_id=position_type, organization_id=org, is_active=True))
    for org in inactive:
        db.add(OfficerPosition(user_id=user, position_type_id=position_type, organization_id=org, is_active=False))
    db.flush()
    return user


def _kl_road(db) -> Project:
    return db.execute(select(Project).where(Project.short_code == PROJECT_KL_ROAD)).scalar_one()


def _link(db, org: str) -> None:
    db.add(ProjectOrganization(project_id=_kl_road(db).project_id, organization_id=org, org_role="contractor"))
    db.flush()


def _ticket(db, assignee: str, workflow_key: str = WORKFLOW_STANDARD_KEY) -> Ticket:
    wf = db.execute(select(WorkflowDefinition).where(WorkflowDefinition.workflow_key == workflow_key)).scalar_one()
    step = db.execute(
        select(WorkflowStep).where(WorkflowStep.workflow_id == wf.workflow_id).order_by(WorkflowStep.step_order).limit(1)
    ).scalar_one()
    t = Ticket(
        ticket_id=str(uuid.uuid4()), grievance_id=f"rb-{uuid.uuid4().hex[:12]}", organization_id=ORG_DOR,
        location_code=LOC_P1_JHA_BIR, project_code=PROJECT_KL_ROAD, project_id=_kl_road(db).project_id,
        current_workflow_id=wf.workflow_id, current_step_id=step.step_id, assigned_to_user_id=assignee,
        status_code="IN_PROGRESS", is_seah=workflow_key == WORKFLOW_SEAH_KEY, is_deleted=False,
        sla_breached=False, priority="NORMAL",
    )
    db.add(t)
    db.flush()
    db.add(TicketFile(file_id=str(uuid.uuid4()), ticket_id=t.ticket_id, file_name="site.jpg",
                      file_path=f"uploads/ticketing/{t.ticket_id}/site.jpg", file_type="image", file_size=1,
                      uploaded_by_user_id=assignee))
    db.flush()
    return t


class _Actor:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.role_keys = ["site_safeguards_focal_person"]

    @property
    def is_admin(self) -> bool:
        return False

    def matches_assignee(self, assignee_id):
        return assignee_id == self.user_id


@pytest.fixture(autouse=True)
def _no_backend_call(monkeypatch):
    monkeypatch.setattr("ticketing.engine.ticket_actions.update_grievance_status", lambda *a, **k: None)


def _resolve(db, ticket, **actor):
    category = None if ticket.is_seah else "ACCEPTED_OTHER"
    payload = TicketActionRequest(action_type="RESOLVE", resolution_category=category,
                                  note="The matter was dealt with as recorded here.", **actor)
    return resolve(db, ticket, _Actor(ticket.assigned_to_user_id), payload)


def _events(db, ticket) -> list[TicketEvent]:
    db.flush()  # SessionLocal has autoflush off
    return list(db.execute(
        select(TicketEvent).where(TicketEvent.ticket_id == ticket.ticket_id,
                                  TicketEvent.event_type.in_(("NOTE_ADDED", "RESOLVED")))
    ).scalars())


def _ids(offices) -> set[str]:
    return {o["organization_id"] for o in offices}


# ── "my office" ─────────────────────────────────────────────────────────────────────────────────

def test_one_position_is_my_office(db):
    office = _org(db, "JHAPA")
    user = _officer(db, office)
    assert _ids(resolve_self_offices(db, user, _ticket(db, user))) == {office}


def test_of_several_positions_the_one_on_the_case_wins(db):
    on_case, elsewhere = _org(db, "LINKED"), _org(db, "ELSEWHERE")
    _link(db, on_case)
    user = _officer(db, on_case, elsewhere)
    assert _ids(resolve_self_offices(db, user, _ticket(db, user))) == {on_case}


def test_a_position_above_a_linked_organization_counts_as_on_the_case(db):
    parent = _org(db, "PARENT")
    child = _org(db, "CHILD", parent)
    elsewhere = _org(db, "ELSEWHERE")
    _link(db, child)
    user = _officer(db, parent, elsewhere)
    assert _ids(resolve_self_offices(db, user, _ticket(db, user))) == {parent}


def test_several_positions_none_on_the_case_are_all_offered(db):
    a, b = _org(db, "A"), _org(db, "B")
    user = _officer(db, a, b)
    assert _ids(resolve_self_offices(db, user, _ticket(db, user))) == {a, b}


def test_no_position_falls_back_to_the_cases_organization_and_inactive_ones_are_ignored(db):
    gone = _org(db, "GONE")
    user = _officer(db, inactive=(gone,))
    assert resolve_self_offices(db, user, _ticket(db, user)) == [
        {"organization_id": ORG_DOR, "name": db.get(Organization, ORG_DOR).name}
    ]


# ── what RESOLVE records ────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("kind", ["self", "organization", "external"])
def test_each_kind_stores_the_four_keys_on_both_events(db, kind):
    office, other = _org(db, "MINE"), _org(db, "OTHER")
    user = _officer(db, office)
    ticket = _ticket(db, user)
    request, expected = {
        "self": ({}, ("self", office, None, "Office MINE")),
        "organization": ({"resolution_actor_kind": "organization", "resolution_actor_organization_id": other},
                         ("organization", other, None, "Office OTHER")),
        "external": ({"resolution_actor_kind": "external", "resolution_actor_external": "police"},
                     ("external", None, "police", "Police")),
    }[kind]
    _resolve(db, ticket, **request)
    events = _events(db, ticket)
    assert len(events) == 2
    for ev in events:
        assert tuple(ev.payload[k] for k in ACTOR_KEYS) == expected
    note = next(ev for ev in events if ev.event_type == "NOTE_ADDED").note
    assert f"\nResolved by: {expected[3]}\n" in note


def test_a_request_cannot_set_the_label(db):
    user = _officer(db, _org(db, "MINE"))
    ticket = _ticket(db, user)
    payload = TicketActionRequest(action_type="RESOLVE", resolution_category="ACCEPTED_OTHER",
                                  note="The matter was dealt with as recorded here.",
                                  resolution_actor_label="Mr Ram Bahadur, ward 4")  # not a field: dropped
    resolve(db, ticket, _Actor(user), payload)
    assert all(ev.payload["resolution_actor_label"] == "Office MINE" for ev in _events(db, ticket))


@pytest.mark.parametrize("case", ["unknown_org", "inactive_org", "unknown_external", "bad_kind",
                                  "several_offices_none_chosen", "self_not_mine"])
def test_refusals_name_the_field(db, case):
    a, b = _org(db, "A"), _org(db, "B")
    inactive = _org(db, "INACTIVE", active=False)
    user = _officer(db, a, b) if case in ("several_offices_none_chosen", "self_not_mine") else _officer(db, a)
    ticket = _ticket(db, user)
    request = {
        "unknown_org": {"resolution_actor_kind": "organization", "resolution_actor_organization_id": "NOPE"},
        "inactive_org": {"resolution_actor_kind": "organization", "resolution_actor_organization_id": inactive},
        "unknown_external": {"resolution_actor_kind": "external", "resolution_actor_external": "a neighbour"},
        "bad_kind": {"resolution_actor_kind": "someone"},
        "several_offices_none_chosen": {},
        "self_not_mine": {"resolution_actor_kind": "self", "resolution_actor_organization_id": ORG_DOR},
    }[case]
    with pytest.raises(ActionError) as exc:
        _resolve(db, ticket, **request)
    assert exc.value.status_code == 422
    assert "resolution_actor" in exc.value.detail


def test_an_officer_with_several_offices_chooses_one_of_them(db):
    a, b = _org(db, "A"), _org(db, "B")
    user = _officer(db, a, b)
    ticket = _ticket(db, user)
    _resolve(db, ticket, resolution_actor_kind="self", resolution_actor_organization_id=b)
    assert all(ev.payload["resolution_actor_organization_id"] == b for ev in _events(db, ticket))


# ── SEAH ────────────────────────────────────────────────────────────────────────────────────────

def test_a_seah_case_records_no_actor(db):
    user = _officer(db, _org(db, "SEAH"))
    ticket = _ticket(db, user, WORKFLOW_SEAH_KEY)
    _resolve(db, ticket)
    for ev in _events(db, ticket):
        assert not any(k in ev.payload for k in ACTOR_KEYS)
        if ev.event_type == "NOTE_ADDED":
            assert "Resolved by" not in ev.note


@pytest.mark.parametrize("request_", [{"resolution_actor_kind": "self"},
                                      {"resolution_actor_kind": "external", "resolution_actor_external": "police"},
                                      {"resolution_actor_organization_id": ORG_DOR}])
def test_a_seah_case_refuses_any_actor_field(db, request_):
    user = _officer(db, _org(db, "SEAH"))
    with pytest.raises(ActionError) as exc:
        _resolve(db, _ticket(db, user, WORKFLOW_SEAH_KEY), **request_)
    assert "does not record who took the action" in exc.value.detail


# ── ticket detail ───────────────────────────────────────────────────────────────────────────────

def _detail(db, monkeypatch, ticket) -> dict:
    from ticketing.api.dependencies import CurrentUser, get_authenticated_user
    from ticketing.api.dependencies import get_db as api_get_db
    from ticketing.api.main import app
    from ticketing.models.base import get_db as base_get_db

    monkeypatch.setattr(db, "commit", db.flush)
    monkeypatch.setattr("ticketing.api.routers.tickets.crud.fetch_grievance_row", lambda *a, **k: None)
    # Who may open a case is not under test here (a SEAH case is cast-only, even for super_admin) —
    # what its detail carries is.
    monkeypatch.setattr("ticketing.api.routers.tickets.crud.assert_ticket_visibility", lambda *a, **k: None)

    def _db():
        yield db

    app.dependency_overrides[api_get_db] = _db
    app.dependency_overrides[base_get_db] = _db
    app.dependency_overrides[get_authenticated_user] = lambda: CurrentUser(
        user_id=ticket.assigned_to_user_id, role_keys=["super_admin"])
    try:
        res = TestClient(app).get(f"/api/v1/tickets/{ticket.ticket_id}")
        assert res.status_code == 200, res.text
        return res.json()
    finally:
        app.dependency_overrides.clear()


def test_ticket_detail_offers_the_choices(db, monkeypatch):
    office, linked = _org(db, "MINE"), _org(db, "CONTRACTOR")
    _link(db, linked)
    user = _officer(db, office)
    body = _detail(db, monkeypatch, _ticket(db, user))
    assert body["resolution_self_offices"] == [{"organization_id": office, "name": "Office MINE"}]
    assert linked in {o["organization_id"] for o in body["resolution_office_suggestions"]}
    assert [a["key"] for a in body["resolution_external_actors"]] == [k for k, _ in RESOLUTION_EXTERNAL_ACTORS]


def test_ticket_detail_offers_nothing_on_a_seah_case(db, monkeypatch):
    user = _officer(db, _org(db, "SEAH"))
    body = _detail(db, monkeypatch, _ticket(db, user, WORKFLOW_SEAH_KEY))
    for key in ("resolution_options", "resolution_self_offices", "resolution_office_suggestions",
                "resolution_external_actors"):
        assert body[key] == [], key
