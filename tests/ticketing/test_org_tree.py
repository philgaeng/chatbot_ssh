"""OC-01 — org tree columns, subtree/cycle helpers, and CSV import.

Two layers (mirrors test_org_authz.py):
  - **pure** (no app, no DB, runs in CI): CSV parse + whole-file validation
    (domains, parent resolution, cycles, category inheritance, topo order), plus the
    gate matrix for the org-tree/import endpoints.
  - **integration** (``@pytest.mark.integration``, needs live DB + seed): the router —
    create/patch tree placement, reparent cycle guard, subtree filter, child-delete guard,
    and CSV import all-or-nothing + idempotency.
"""
from __future__ import annotations

import io
import uuid

import pytest
from fastapi import HTTPException

from ticketing.api.dependencies import CurrentUser
from ticketing.services.admin_access import (
    AdminScopeRow,
    SettingsAction,
    require_settings_write,
)
from ticketing.seed.org_import_core import parse_org_csv, plan_import
from ticketing.services.org_tree import (
    ORG_CATEGORIES,
    UNIT_TYPES,
    org_category_matches_unit_type,
)


# ══════════════════════════════════════════════════════════════════════════════
# Personas (plain objects — no DB)
# ══════════════════════════════════════════════════════════════════════════════

def _scope(role_key="country_admin", track="standard", project_id=None, user_id="a@grm.local"):
    return AdminScopeRow(
        admin_scope_id=str(uuid.uuid4()),
        user_id=user_id,
        role_key=role_key,
        country_code="NP",
        project_id=project_id,
        organization_id=None,
        package_id=None,
        workflow_track=track,
    )


def _super():
    return CurrentUser(user_id="s@grm.local", role_keys=["super_admin"])


def _country(track):
    return CurrentUser(
        user_id="c@grm.local", role_keys=[], admin_scopes=[_scope(track=track, user_id="c@grm.local")]
    )


def _project():
    return CurrentUser(
        user_id="p@grm.local",
        role_keys=[],
        admin_scopes=[_scope(role_key="project_admin", project_id="KL_ROAD", user_id="p@grm.local")],
    )


def _operational():
    return CurrentUser(user_id="o@grm.local", role_keys=["site_safeguards_focal_person"])


# name → (persona, may edit the org tree / run CSV import per doc 16 §7?)
_MATRIX = [
    ("super", _super(), True),
    ("country_standard", _country("standard"), True),
    ("country_seah", _country("seah"), False),
    ("project", _project(), False),
    ("operational", _operational(), False),
]


@pytest.mark.parametrize("name,user,allowed", _MATRIX)
def test_org_tree_and_import_gate(name, user, allowed):
    """Org-tree edits and CSV import share the MANAGE_ORG_STRUCTURE gate (doc 16 §7)."""
    if allowed:
        require_settings_write(user, SettingsAction.MANAGE_ORG_STRUCTURE)  # no raise
    else:
        with pytest.raises(HTTPException) as exc:
            require_settings_write(user, SettingsAction.MANAGE_ORG_STRUCTURE)
        assert exc.value.status_code == 403


# ══════════════════════════════════════════════════════════════════════════════
# Pure: category/unit alignment warning helper
# ══════════════════════════════════════════════════════════════════════════════

def test_category_unit_alignment_is_advisory():
    assert org_category_matches_unit_type("government", "division_office") is True
    assert org_category_matches_unit_type("third_party", "company") is True
    assert org_category_matches_unit_type("donor", "development_partner") is True
    # off-pattern (a division office under a contractor) — flagged, but not blocked
    assert org_category_matches_unit_type("third_party", "division_office") is False
    # nothing to check
    assert org_category_matches_unit_type(None, "company") is True
    assert org_category_matches_unit_type("government", None) is True


def test_domain_tuples_are_the_documented_sets():
    assert set(ORG_CATEGORIES) == {"government", "local_government", "donor", "third_party"}
    assert "division_office" in UNIT_TYPES and "development_partner" in UNIT_TYPES


# ══════════════════════════════════════════════════════════════════════════════
# Pure: parse + plan_import (whole-file validation)
# ══════════════════════════════════════════════════════════════════════════════

_GOOD_CSV = """\
organization_id,name,parent_organization_id,org_category,unit_type,country_code,territory_location_code,territory_includes_children,display_name_ne
MOPIT,Ministry of Physical Infra,,government,ministry,NP,,,भौतिक मन्त्रालय
DOR,Department of Roads,MOPIT,,department,NP,,,सडक विभाग
DOR_JHA,Jhapa Division Road Office,DOR,,division_office,NP,,,झापा
"""


def test_parse_normalizes_ids_and_fields():
    rows = parse_org_csv(_GOOD_CSV)
    assert [r.organization_id for r in rows] == ["MOPIT", "DOR", "DOR_JHA"]
    dor = rows[1]
    assert dor.parent_organization_id == "MOPIT"
    assert dor.unit_type == "department"
    assert dor.org_category is None  # omitted → inherited later


def test_parse_missing_required_column_raises():
    with pytest.raises(ValueError):
        parse_org_csv("name,unit_type\nDept,department\n")  # no organization_id column


def test_plan_valid_tree_orders_parents_first_and_inherits_category():
    plan = plan_import(parse_org_csv(_GOOD_CSV))
    assert plan.ok, plan.errors
    order = [r.organization_id for r in plan.ordered_rows]
    assert order.index("MOPIT") < order.index("DOR") < order.index("DOR_JHA")
    # children inherit the root's category
    assert plan.resolved_categories == {
        "MOPIT": "government",
        "DOR": "government",
        "DOR_JHA": "government",
    }


def test_plan_rejects_root_without_category():
    csv = "organization_id,name,parent_organization_id,org_category\nX,X Org,,\n"
    plan = plan_import(parse_org_csv(csv))
    assert not plan.ok
    assert any("requires an org_category" in e for e in plan.errors)


def test_plan_rejects_child_category_conflict():
    csv = (
        "organization_id,name,parent_organization_id,org_category\n"
        "ROOT,Root,,government\n"
        "KID,Kid,ROOT,donor\n"  # conflicts with inherited 'government'
    )
    plan = plan_import(parse_org_csv(csv))
    assert not plan.ok
    assert any("conflicts with inherited" in e for e in plan.errors)


def test_plan_rejects_duplicate_id():
    csv = (
        "organization_id,name,parent_organization_id,org_category\n"
        "DUP,First,,government\n"
        "DUP,Second,,government\n"
    )
    plan = plan_import(parse_org_csv(csv))
    assert not plan.ok
    assert any("duplicate organization_id" in e for e in plan.errors)


def test_plan_rejects_unknown_parent():
    csv = (
        "organization_id,name,parent_organization_id,org_category\n"
        "KID,Kid,GHOST,government\n"  # GHOST not in file, no external
    )
    plan = plan_import(parse_org_csv(csv))
    assert not plan.ok
    assert any("not found" in e for e in plan.errors)


def test_plan_rejects_invalid_domains():
    csv = (
        "organization_id,name,parent_organization_id,org_category,unit_type\n"
        "R,Root,,martian,spaceship\n"
    )
    plan = plan_import(parse_org_csv(csv))
    assert not plan.ok
    assert any("invalid org_category" in e for e in plan.errors)
    assert any("invalid unit_type" in e for e in plan.errors)


def test_plan_detects_cycle():
    csv = (
        "organization_id,name,parent_organization_id,org_category\n"
        "A,A,B,government\n"
        "B,B,A,government\n"
    )
    plan = plan_import(parse_org_csv(csv))
    assert not plan.ok
    assert any("cycle" in e.lower() for e in plan.errors)
    assert plan.ordered_rows == []  # nothing planned


def test_plan_self_parent_is_rejected():
    csv = "organization_id,name,parent_organization_id,org_category\nA,A,A,government\n"
    plan = plan_import(parse_org_csv(csv))
    assert not plan.ok
    assert any("its own parent" in e for e in plan.errors)


def test_plan_inherits_from_external_parent():
    # DOR already exists in the DB as a 'government' root; a new child inherits it.
    csv = "organization_id,name,parent_organization_id,org_category\nDOR_ILM,Ilam Office,DOR,\n"
    plan = plan_import(parse_org_csv(csv), external_org_categories={"DOR": "government"})
    assert plan.ok, plan.errors
    assert plan.resolved_categories["DOR_ILM"] == "government"


# ══════════════════════════════════════════════════════════════════════════════
# Integration — router + DB (needs live seeded DB)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def cleanup_orgs():
    """Track org ids created via the API and hard-delete them on teardown.

    The self-FK is ON DELETE SET NULL, so direct deletes don't need child-first ordering.
    """
    ids: list[str] = []
    yield ids
    from ticketing.models.base import SessionLocal
    from ticketing.models.organization import Organization

    s = SessionLocal()
    try:
        for oid in ids:
            obj = s.get(Organization, oid)
            if obj:
                s.delete(obj)
        s.commit()
    finally:
        s.close()


def _client(user):
    from fastapi.testclient import TestClient

    from ticketing.api.dependencies import get_authenticated_user, get_db
    from ticketing.api.main import app
    from ticketing.models.base import SessionLocal

    db = SessionLocal()

    def _db():
        yield db

    app.dependency_overrides[get_authenticated_user] = lambda: user
    app.dependency_overrides[get_db] = _db
    return app, TestClient(app), db


def _oid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:6].upper()}"


@pytest.mark.integration
def test_create_root_and_child_inherit_category(cleanup_orgs):
    app, client, db = _client(_super())
    try:
        root_id = _oid("OCROOT")
        cleanup_orgs.append(root_id)
        res = client.post(
            "/api/v1/organizations",
            json={"organization_id": root_id, "name": "OC Root", "org_category": "donor",
                  "unit_type": "development_partner"},
        )
        assert res.status_code == 201, res.text
        assert res.json()["org_category"] == "donor"

        kid_id = _oid("OCKID")
        cleanup_orgs.append(kid_id)
        res2 = client.post(
            "/api/v1/organizations",
            json={"organization_id": kid_id, "name": "OC Kid",
                  "parent_organization_id": root_id, "unit_type": "development_partner"},
        )
        assert res2.status_code == 201, res2.text
        assert res2.json()["org_category"] == "donor"  # inherited
        assert res2.json()["parent_organization_id"] == root_id
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.integration
def test_create_validations(cleanup_orgs):
    app, client, db = _client(_super())
    try:
        # bad unit_type
        assert client.post(
            "/api/v1/organizations",
            json={"name": "Bad Unit", "unit_type": "spaceship"},
        ).status_code == 422
        # nonexistent parent
        assert client.post(
            "/api/v1/organizations",
            json={"name": "Orphan", "parent_organization_id": "NO_SUCH_ORG"},
        ).status_code == 422
        # nonexistent territory
        assert client.post(
            "/api/v1/organizations",
            json={"name": "Bad Terr", "org_category": "government",
                  "territory_location_code": "NO_SUCH_LOC"},
        ).status_code == 422
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.integration
def test_reparent_cycle_is_blocked(cleanup_orgs):
    app, client, db = _client(_super())
    try:
        a, b = _oid("OCA"), _oid("OCB")
        cleanup_orgs.extend([a, b])
        client.post("/api/v1/organizations",
                    json={"organization_id": a, "name": "A", "org_category": "government"})
        client.post("/api/v1/organizations",
                    json={"organization_id": b, "name": "B", "parent_organization_id": a})
        # B is a descendant of A → making A report to B is a cycle
        res = client.patch(f"/api/v1/organizations/{a}", json={"parent_organization_id": b})
        assert res.status_code == 422, res.text
        assert "cycle" in res.text.lower()
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.integration
def test_reparent_cascades_category(cleanup_orgs):
    app, client, db = _client(_super())
    try:
        gov, donor, kid = _oid("OCGOV"), _oid("OCDON"), _oid("OCKID")
        cleanup_orgs.extend([gov, donor, kid])
        client.post("/api/v1/organizations",
                    json={"organization_id": gov, "name": "Gov", "org_category": "government"})
        client.post("/api/v1/organizations",
                    json={"organization_id": donor, "name": "Donor", "org_category": "donor"})
        client.post("/api/v1/organizations",
                    json={"organization_id": kid, "name": "Kid", "parent_organization_id": gov})
        # move the gov subtree (gov + kid) under the donor root → both become 'donor'
        res = client.patch(f"/api/v1/organizations/{gov}", json={"parent_organization_id": donor})
        assert res.status_code == 200, res.text
        assert res.json()["org_category"] == "donor"
        got = client.get(f"/api/v1/organizations?root_id={donor}&active_only=false").json()
        cats = {o["organization_id"]: o["org_category"] for o in got}
        assert cats.get(kid) == "donor"  # cascaded to the descendant
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.integration
def test_subtree_filter_and_tree_order(cleanup_orgs):
    app, client, db = _client(_super())
    try:
        root, mid, leaf = _oid("OCR"), _oid("OCM"), _oid("OCL")
        cleanup_orgs.extend([root, mid, leaf])
        client.post("/api/v1/organizations",
                    json={"organization_id": root, "name": "Root", "org_category": "government"})
        client.post("/api/v1/organizations",
                    json={"organization_id": mid, "name": "Mid", "parent_organization_id": root})
        client.post("/api/v1/organizations",
                    json={"organization_id": leaf, "name": "Leaf", "parent_organization_id": mid})
        got = client.get(
            f"/api/v1/organizations?root_id={root}&tree=true&active_only=false"
        ).json()
        ids = [o["organization_id"] for o in got]
        assert set(ids) == {root, mid, leaf}
        assert ids.index(root) < ids.index(mid) < ids.index(leaf)  # parents-before-children
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.integration
def test_delete_parent_with_children_blocked(cleanup_orgs):
    app, client, db = _client(_super())
    try:
        root, kid = _oid("OCDR"), _oid("OCDK")
        cleanup_orgs.extend([root, kid])
        client.post("/api/v1/organizations",
                    json={"organization_id": root, "name": "Root", "org_category": "government"})
        client.post("/api/v1/organizations",
                    json={"organization_id": kid, "name": "Kid", "parent_organization_id": root})
        res = client.delete(f"/api/v1/organizations/{root}")
        assert res.status_code == 409, res.text
        assert "child" in res.text.lower()
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.integration
def test_csv_import_all_or_nothing(cleanup_orgs):
    app, client, db = _client(_super())
    try:
        good, bad = _oid("OCIMPGOOD"), _oid("OCIMPBAD")
        cleanup_orgs.extend([good, bad])
        # second row references a nonexistent parent → whole file rejected
        csv = (
            "organization_id,name,parent_organization_id,org_category\n"
            f"{good},Good Root,,government\n"
            f"{bad},Bad Kid,GHOST_PARENT,\n"
        )
        res = client.post(
            "/api/v1/organizations/import",
            files={"file": ("orgs.csv", io.BytesIO(csv.encode()), "text/csv")},
        )
        assert res.status_code == 422, res.text
        # nothing written — the good row must not exist
        assert client.get(f"/api/v1/organizations?root_id={good}&active_only=false").json() == []
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.integration
def test_csv_import_happy_path_is_idempotent(cleanup_orgs):
    app, client, db = _client(_super())
    try:
        root, kid = _oid("OCIMPR"), _oid("OCIMPK")
        cleanup_orgs.extend([root, kid])
        csv = (
            "organization_id,name,parent_organization_id,org_category,unit_type\n"
            f"{root},Import Root,,donor,development_partner\n"
            f"{kid},Import Kid,{root},,development_partner\n"
        )
        files = {"file": ("orgs.csv", io.BytesIO(csv.encode()), "text/csv")}
        res = client.post("/api/v1/organizations/import", files=files)
        assert res.status_code == 200, res.text
        assert res.json()["organizations_upserted"] == 2
        got = client.get(f"/api/v1/organizations?root_id={root}&active_only=false").json()
        cats = {o["organization_id"]: o["org_category"] for o in got}
        assert cats == {root: "donor", kid: "donor"}
        # re-import updates (idempotent) — still 2, no duplicate error
        res2 = client.post(
            "/api/v1/organizations/import",
            files={"file": ("orgs.csv", io.BytesIO(csv.encode()), "text/csv")},
        )
        assert res2.status_code == 200, res2.text
        assert res2.json()["organizations_upserted"] == 2
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.integration
def test_csv_import_authz_blocks_project_admin():
    app, client, db = _client(_project())
    try:
        csv = "organization_id,name,parent_organization_id,org_category\nX,X,,government\n"
        res = client.post(
            "/api/v1/organizations/import",
            files={"file": ("orgs.csv", io.BytesIO(csv.encode()), "text/csv")},
        )
        assert res.status_code == 403, res.text
    finally:
        app.dependency_overrides.clear()
        db.close()
