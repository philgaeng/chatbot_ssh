"""GRM-119 — a workflow's resolution panel: its list, creating into it, editing an action.

Pins the rules of `services/resolution_authoring.py` through the API, with admins at DOR, at PD-ADB
(under DOR), at a sibling office under DOR, and at another ministry:

- changing a list needs the workflow's organization in reach — the track check alone is not enough;
- at most 8, and a create refused at 8 leaves **no** action row behind (actions are never deleted);
- a create never takes an owner: it belongs to the workflow's organization, or to its ministry for a
  *national* action (which needs the ministry in reach); a local action must count as an active shared
  action of its own ministry;
- editing needs the action's owner in reach and follows the same counts-as validation;
- *available* offers only what the workflow can use and does not already offer.

Everything is flushed, never committed: the router's commits are routed to `flush`.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from ticketing.api.dependencies import CurrentUser
from ticketing.constants.resolution import MAX_RESOLUTION_ACTIONS
from ticketing.models.base import SessionLocal
from ticketing.models.organization import Organization
from ticketing.models.resolution_action import ResolutionAction
from ticketing.models.workflow import WorkflowDefinition
from ticketing.services.admin_access import AdminScopeRow
from ticketing.services.resolution_catalog import create_action, selected_codes, set_workflow_actions
from tests.ticketing.conftest import ORG_DOR

pytestmark = pytest.mark.integration


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


def _org(db, name: str, parent: str | None) -> str:
    oid = f"RD_{name}_{_tag()}"
    db.add(Organization(organization_id=oid, name=f"GRM-119 {name}", parent_organization_id=parent))
    db.flush()
    return oid


@pytest.fixture
def orgs(db):
    other = _org(db, "MINISTRY", None)
    other_shared = create_action(db, code=f"TEST_{_tag()}", label="Customs refund", default_wording="x",
                                 owner_organization_id=other)
    return {"dor": ORG_DOR, "pd_adb": _org(db, "PDADB", ORG_DOR), "sibling": _org(db, "SIBLING", ORG_DOR),
            "other": other, "other_shared": other_shared.code}


def _workflow(db, owner: str, *, codes=(), sensitive=False) -> WorkflowDefinition:
    wf = WorkflowDefinition(workflow_id=str(uuid.uuid4()), workflow_key=f"RD_{_tag()}", display_name="GRM-119 test",
                            workflow_type="seah" if sensitive else "standard", owner_organization_id=owner,
                            status="draft")
    db.add(wf)
    db.flush()
    if codes:
        set_workflow_actions(db, wf, list(codes))
    return wf


def _admin(org: str | None) -> CurrentUser:
    if org is None:
        return CurrentUser(user_id="s@grm.local", role_keys=["super_admin"])
    return CurrentUser(user_id=f"a-{org}@grm.local", role_keys=[], admin_scopes=[AdminScopeRow(
        admin_scope_id=str(uuid.uuid4()), user_id=f"a-{org}@grm.local", role_key="org_admin", country_code="NP",
        project_id=None, organization_id=org, package_id=None, workflow_track="standard",
    )])


@pytest.fixture
def as_user(db, monkeypatch):
    from ticketing.api.dependencies import get_authenticated_user
    from ticketing.api.dependencies import get_db as api_get_db
    from ticketing.api.main import app
    from ticketing.models.base import get_db as base_get_db

    monkeypatch.setattr(db, "commit", db.flush)
    monkeypatch.setattr(db, "rollback", lambda: None)  # a refused request must not undo the fixture rows

    def _db():
        yield db

    app.dependency_overrides[api_get_db] = _db
    app.dependency_overrides[base_get_db] = _db

    def _as(user: CurrentUser) -> TestClient:
        app.dependency_overrides[get_authenticated_user] = lambda: user
        return TestClient(app)

    yield _as
    app.dependency_overrides.clear()


def _put(client, wf, codes):
    return client.put(f"/api/v1/workflows/{wf.workflow_id}/resolution-actions", json={"codes": codes})


def _new(client, wf, **body):
    return client.post(f"/api/v1/workflows/{wf.workflow_id}/resolution-actions/new",
                       json={"label": "Culvert cleared", "default_wording": "The culvert was cleared.", **body})


def _action_count(db) -> int:
    return db.execute(select(func.count()).select_from(ResolutionAction)).scalar_one()


# ── changing a list ─────────────────────────────────────────────────────────────────────────────

def test_changing_a_list_needs_the_workflows_organization_in_reach(db, orgs, as_user):
    pd_wf = _workflow(db, orgs["pd_adb"])
    dor_wf = _workflow(db, ORG_DOR)
    assert _put(as_user(_admin(orgs["pd_adb"])), pd_wf, ["CLASSIFIED"]).status_code == 200
    assert _put(as_user(_admin(orgs["pd_adb"])), dor_wf, ["CLASSIFIED"]).status_code == 403
    assert _put(as_user(_admin(orgs["sibling"])), pd_wf, ["CLASSIFIED"]).status_code == 403
    assert _put(as_user(_admin(ORG_DOR)), pd_wf, ["ACCEPTED_OTHER", "CLASSIFIED"]).status_code == 200
    assert selected_codes(db, pd_wf.workflow_id) == ["ACCEPTED_OTHER", "CLASSIFIED"]


def test_the_panel_tells_a_viewer_what_it_may_do(db, orgs, as_user):
    wf = _workflow(db, orgs["pd_adb"], codes=["CLASSIFIED"])
    mine = as_user(_admin(orgs["pd_adb"])).get(f"/api/v1/workflows/{wf.workflow_id}/resolution-actions").json()
    assert mine["can_change"] is True and mine["can_create_national"] is False and mine["max"] == MAX_RESOLUTION_ACTIONS
    assert mine["actions"][0]["code"] == "CLASSIFIED" and mine["actions"][0]["can_edit"] is False  # DOR's action
    assert {c["code"] for c in mine["national_choices"]} >= {"CLASSIFIED", "ROAD_REPAIRED"}
    dors = as_user(_admin(ORG_DOR)).get(f"/api/v1/workflows/{wf.workflow_id}/resolution-actions").json()
    assert dors["can_create_national"] is True and dors["actions"][0]["can_edit"] is True
    other = as_user(_admin(orgs["other"])).get(f"/api/v1/workflows/{wf.workflow_id}/resolution-actions").json()
    assert other["can_change"] is False


def test_a_sensitive_workflow_has_no_writable_panel(db, orgs, as_user):
    wf = _workflow(db, ORG_DOR, sensitive=True)
    assert _put(as_user(_admin(None)), wf, ["CLASSIFIED"]).status_code == 422
    assert _new(as_user(_admin(None)), wf, national=True).status_code == 422


# ── the limit ───────────────────────────────────────────────────────────────────────────────────

def test_at_most_eight_and_a_refused_create_leaves_nothing_behind(db, orgs, as_user):
    codes = ["CLASSIFIED", "DEMAND_REJECTED", "ACCEPTED_MONETARY", "ACCEPTED_RELOCATION", "ACCEPTED_OTHER",
             "ROAD_REPAIRED", "ROAD_MADE_SAFE", "ROAD_DUST_NOISE_CONTROLLED", "ROAD_NOT_PROJECT_ROAD"]
    wf = _workflow(db, ORG_DOR)
    client = as_user(_admin(ORG_DOR))
    assert _put(client, wf, codes).status_code == 422
    assert _put(client, wf, codes[:8]).status_code == 200
    before = _action_count(db)
    res = _new(client, wf)
    assert res.status_code == 422 and "at most 8" in res.text
    assert _action_count(db) == before


# ── creating ────────────────────────────────────────────────────────────────────────────────────

def test_a_local_action_must_count_as_a_shared_action_of_its_ministry(db, orgs, as_user):
    wf = _workflow(db, orgs["pd_adb"])
    client = as_user(_admin(orgs["pd_adb"]))
    local = create_action(db, code=f"TEST_{_tag()}", label="PD local", default_wording="x",
                          owner_organization_id=orgs["pd_adb"], counts_as_code="CLASSIFIED")
    before = _action_count(db)
    assert _new(client, wf).status_code == 422                                          # no counts-as
    assert _new(client, wf, counts_as_code=local.code).status_code == 422               # counts as a local one
    assert _new(client, wf, counts_as_code=orgs["other_shared"]).status_code == 422     # another ministry's
    assert _action_count(db) == before

    res = _new(client, wf, counts_as_code="ROAD_REPAIRED")
    assert res.status_code == 201, res.text
    created = next(a for a in res.json()["actions"] if a["label"] == "Culvert cleared")
    assert created["counts_as_label"] == "Hazard repaired"
    row = db.get(ResolutionAction, created["code"])
    assert row.owner_organization_id == orgs["pd_adb"] and row.counts_as_code == "ROAD_REPAIRED"
    assert selected_codes(db, wf.workflow_id)[-1] == created["code"]


def test_an_action_created_on_a_ministrys_own_workflow_is_shared(db, orgs, as_user):
    wf = _workflow(db, ORG_DOR)
    client = as_user(_admin(ORG_DOR))
    assert _new(client, wf, counts_as_code="CLASSIFIED").status_code == 422
    res = _new(client, wf, code="HANDPICKED_CODE")  # a code in the body is ignored
    assert res.status_code == 201, res.text
    code = res.json()["actions"][-1]["code"]
    assert code != "HANDPICKED_CODE" and code.startswith("CULVERT_CLEARED_")
    row = db.get(ResolutionAction, code)
    assert row.owner_organization_id == ORG_DOR and row.counts_as_code is None


def test_a_national_action_needs_the_ministry_in_reach(db, orgs, as_user):
    wf = _workflow(db, orgs["pd_adb"])
    assert _new(as_user(_admin(orgs["pd_adb"])), wf, national=True).status_code == 403
    res = _new(as_user(_admin(ORG_DOR)), wf, national=True)
    assert res.status_code == 201, res.text
    row = db.get(ResolutionAction, res.json()["actions"][-1]["code"])
    assert row.owner_organization_id == ORG_DOR and row.counts_as_code is None


# ── editing ─────────────────────────────────────────────────────────────────────────────────────

def test_editing_needs_the_actions_owner_in_reach(db, orgs, as_user):
    shared = create_action(db, code=f"TEST_{_tag()}", label="DOR shared", default_wording="x", owner_organization_id=ORG_DOR)
    _workflow(db, ORG_DOR, codes=[shared.code])
    _workflow(db, orgs["pd_adb"], codes=[shared.code])
    assert as_user(_admin(orgs["pd_adb"])).patch(f"/api/v1/resolution-actions/{shared.code}", json={"label": "x"}).status_code == 403
    res = as_user(_admin(ORG_DOR)).patch(f"/api/v1/resolution-actions/{shared.code}", json={"label": "DOR shared, reworded"})
    assert res.status_code == 200, res.text
    assert res.json()["label"] == "DOR shared, reworded" and res.json()["used_by_count"] == 2


def test_editing_what_an_action_counts_as_follows_the_same_rule(db, orgs, as_user):
    local = create_action(db, code=f"TEST_{_tag()}", label="PD local", default_wording="x",
                          owner_organization_id=orgs["pd_adb"], counts_as_code="CLASSIFIED")
    client = as_user(_admin(orgs["pd_adb"]))
    assert client.patch(f"/api/v1/resolution-actions/{local.code}", json={"counts_as_code": orgs["other_shared"]}).status_code == 422
    assert client.patch(f"/api/v1/resolution-actions/{local.code}", json={"counts_as_code": None}).status_code == 422
    ok = client.patch(f"/api/v1/resolution-actions/{local.code}", json={"counts_as_code": "ROAD_MADE_SAFE"})
    assert ok.status_code == 200 and ok.json()["counts_as_label"] == "Made safe — signs, barriers or traffic control"
    shared = create_action(db, code=f"TEST_{_tag()}", label="DOR shared", default_wording="x", owner_organization_id=ORG_DOR)
    assert as_user(_admin(ORG_DOR)).patch(f"/api/v1/resolution-actions/{shared.code}", json={"counts_as_code": "CLASSIFIED"}).status_code == 422


# ── available ───────────────────────────────────────────────────────────────────────────────────

def test_available_offers_only_what_the_workflow_can_use_and_does_not_offer(db, orgs, as_user):
    sibling_local = create_action(db, code=f"TEST_{_tag()}", label="Sibling local", default_wording="x",
                                  owner_organization_id=orgs["sibling"], counts_as_code="CLASSIFIED")
    wf = _workflow(db, orgs["pd_adb"], codes=["CLASSIFIED"])
    res = as_user(_admin(orgs["pd_adb"])).get(f"/api/v1/workflows/{wf.workflow_id}/resolution-actions/available")
    codes = {a["code"] for a in res.json()}
    assert "ROAD_REPAIRED" in codes
    assert "CLASSIFIED" not in codes
    assert sibling_local.code not in codes and orgs["other_shared"] not in codes
    q = as_user(_admin(orgs["pd_adb"])).get(f"/api/v1/workflows/{wf.workflow_id}/resolution-actions/available", params={"q": "hazard"})
    assert {a["code"] for a in q.json()} == {"ROAD_REPAIRED", "ROAD_NO_HAZARD_FOUND"}
