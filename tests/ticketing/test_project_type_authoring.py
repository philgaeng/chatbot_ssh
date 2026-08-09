"""Authoring a project type — the checks that stop a template from being incoherent.

DECISION-author-defined-slots §3.1 / doc 14 §4. A type names the organizations a project must
have and the workflows it runs. What must hold or the projects built from it break in ways
nobody sees until go-live:

  • organization roles are named and unique;
  • the workflow set has exactly one default, the default is never a sensitive workflow, every
    other one names a chatbot menu, and a category belongs to one workflow.

Plus the authoring gate itself: `super_admin` anywhere, `org_admin` inside its own subtree,
and nobody edits the shared (global) templates but the platform administrator.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from ticketing.api.routers.project_types import (
    _require_authority,
    _validate_config,
    _validate_owner,
)

pytestmark = pytest.mark.integration


ROLE_IA = {
    "key": "implementing_agency",
    "label": "Implementing Agency",
    "description": "",
    "required": True,
    "required_package": False,
    "scope": "project",
}
ROLE_WARD = {
    "key": "ward_office",
    "label": "Ward Office",
    "description": "",
    "required": False,
    "required_package": False,
    "scope": "project",
}


class _Workflow:
    def __init__(self, workflow_type="standard"):
        self.workflow_type = workflow_type


def _patch_workflows(monkeypatch, **by_id):
    """Stand in for the published-workflow lookup so these stay pure-unit."""
    import ticketing.services.project_workflows as pw

    monkeypatch.setattr(pw, "validate_workflow_binding", lambda db, wid: by_id[wid])


def _binding(label, wid, *, default=False, route="new_grievance", categories=None):
    return {
        "display_label": label,
        "workflow_id": wid,
        "is_default": default,
        "classifications": categories or [],
        "intake_route": None if default else route,
        "sort_order": 10,
    }


# ── the organization catalog ──────────────────────────────────────────────────
#
# No entry is special. The `routing_org_role` anchor — "which of these is the grievance recorded
# against?" — was retired 2026-08-04 (DECISION-organization-membership): every organization
# named on a project sees its grievances, so there is nothing to designate.


def test_a_type_cannot_start_empty():
    """**Reversed 2026-08-08** (Philippe). This asserted the opposite — that a new type may have
    no organizations and the author adds them later — and "later" turned out to be never: a type
    saved empty produced a project whose Organizations section was a dead end, while the go-live
    rail called that section green (nothing required, so nothing missing, so B1 passed).

    The rule and its reasoning live in `test_package_is_the_only_coverage`'s sibling,
    `test_project_type_needs_an_organization.py`; asserted here too because this is the file
    someone reads when changing type authoring.
    """
    with pytest.raises(HTTPException) as exc:
        _validate_config(None, actor_roles=[], workflow_bindings=[])
    assert exc.value.status_code == 422


def test_duplicate_roles_are_refused():
    with pytest.raises(HTTPException) as exc:
        _validate_config(
            None,
            actor_roles=[ROLE_WARD, dict(ROLE_WARD)],
            workflow_bindings=[],
        )
    assert exc.value.status_code == 422
    assert "Ward Office" in exc.value.detail


def test_a_role_needs_a_name():
    with pytest.raises(HTTPException):
        _validate_config(
            None,
            actor_roles=[{"key": "x", "label": "  "}],
            workflow_bindings=[],
        )


# ── the workflow set ──────────────────────────────────────────────────────────

def test_exactly_one_default(monkeypatch):
    _patch_workflows(monkeypatch, w1=_Workflow(), w2=_Workflow())
    with pytest.raises(HTTPException) as exc:
        _validate_config(
            None,
            actor_roles=[ROLE_IA],
            workflow_bindings=[_binding("A", "w1", default=True), _binding("B", "w2", default=True)],
        )
    assert "exactly one" in exc.value.detail.lower()


def test_the_default_cannot_be_sensitive(monkeypatch):
    """The default takes every grievance that matches nothing else. If it were sensitive, all of
    them would land where only its cast can see them (DECISION-sensitive-workflows §1.2)."""
    _patch_workflows(monkeypatch, seah=_Workflow("seah"))
    with pytest.raises(HTTPException) as exc:
        _validate_config(
            None,
            actor_roles=[ROLE_IA],
            workflow_bindings=[_binding("Sensitive", "seah", default=True)],
        )
    assert "sensitive" in exc.value.detail.lower()


def test_a_non_default_workflow_needs_a_chatbot_menu(monkeypatch):
    _patch_workflows(monkeypatch, w1=_Workflow(), w2=_Workflow())
    with pytest.raises(HTTPException) as exc:
        _validate_config(
            None,
            actor_roles=[ROLE_IA],
            workflow_bindings=[
                _binding("Default", "w1", default=True),
                {**_binding("Hazards", "w2"), "intake_route": None},
            ],
        )
    assert "chatbot menu" in exc.value.detail.lower()


def test_a_category_belongs_to_one_workflow(monkeypatch):
    _patch_workflows(monkeypatch, w1=_Workflow(), w2=_Workflow(), w3=_Workflow())
    with pytest.raises(HTTPException) as exc:
        _validate_config(
            None,
            actor_roles=[ROLE_IA],
            workflow_bindings=[
                _binding("Default", "w1", default=True),
                _binding("Hazards", "w2", categories=["Environmental"]),
                _binding("Land", "w3", categories=["Environmental"]),
            ],
        )
    assert "Environmental" in exc.value.detail


def test_a_valid_set_passes(monkeypatch):
    _patch_workflows(monkeypatch, w1=_Workflow(), w2=_Workflow("seah"))
    _validate_config(
        None,
        actor_roles=[ROLE_IA],
        workflow_bindings=[
            _binding("General grievances", "w1", default=True),
            _binding("Sensitive", "w2", route="seah_intake", categories=["Gender"]),
        ],
    )


# ── who may author (§3.1) ─────────────────────────────────────────────────────

class _User:
    def __init__(self, role_keys=(), scopes=()):
        self.role_keys = list(role_keys)
        self.admin_scopes = list(scopes)


class _Scope:
    def __init__(self, organization_id, role_key="org_admin", workflow_track="standard"):
        self.organization_id = organization_id
        self.role_key = role_key
        self.workflow_track = workflow_track


def _reach(monkeypatch, ids):
    import ticketing.api.routers.project_types as mod

    monkeypatch.setattr(mod, "admin_org_scope_ids", lambda db, user, track=None: ids)


def test_super_admin_authors_anywhere(monkeypatch):
    _require_authority(None, _User(["super_admin"]), None)
    _require_authority(None, _User(["super_admin"]), "SOMEONE_ELSE")


def test_org_admin_authors_inside_its_subtree(monkeypatch):
    _reach(monkeypatch, {"DOR", "DOR_EAST"})
    _require_authority(None, _User(scopes=[_Scope("DOR")]), "DOR_EAST")


def test_org_admin_cannot_author_another_organizations_type(monkeypatch):
    _reach(monkeypatch, {"DOR"})
    with pytest.raises(HTTPException) as exc:
        _require_authority(None, _User(scopes=[_Scope("DOR")]), "MOPIT")
    assert exc.value.status_code == 403
    assert "template" in exc.value.detail  # names the way out


def test_a_shared_template_belongs_to_the_platform(monkeypatch):
    """A global type is offered to every organization — one org_admin must not be able to
    re-configure what everyone else is offered."""
    _reach(monkeypatch, {"DOR"})
    with pytest.raises(HTTPException) as exc:
        _require_authority(None, _User(scopes=[_Scope("DOR")]), None)
    assert exc.value.status_code == 403


def test_country_wide_org_admin_is_unbounded(monkeypatch):
    """A legacy org_admin scope with no organization node administers the whole tree."""
    _reach(monkeypatch, None)
    _require_authority(None, _User(scopes=[_Scope(None)]), "ANY")


def test_a_non_admin_is_refused(monkeypatch):
    with pytest.raises(HTTPException) as exc:
        _require_authority(None, _User(), "DOR")
    assert exc.value.status_code == 403


# ── the catalog a project reads (doc 13 §2) ───────────────────────────────────

def test_project_reads_its_types_catalog(db, kl_road_project):
    """The organization vocabulary is the **type's**, not a per-project copy — that is the half
    of the July decision that survived: no per-project catalog, because that is how vocabularies
    drift."""
    from ticketing.services.project_actor_roles import effective_role_catalog
    from ticketing.services.project_types import get_project_type

    pt = get_project_type(db, kl_road_project.project_type_key)
    catalog = effective_role_catalog(db, kl_road_project.project_id)

    assert {e["key"] for e in catalog} == {r["key"] for r in pt.actor_roles}
    # No entry is privileged — the anchor concept is gone.
    assert all("is_routing_anchor" not in e for e in catalog)


# ── who may own a template (2026-08-04) ───────────────────────────────────────
#
# A template belongs to a body that runs or funds projects, at the top two levels of the org
# tree — a ministry, one of its departments, a donor. Not a contractor: there are dozens of
# them, they are named *by* a project, and an owner picker listing 50 of them is unusable.


class _OrgRow:
    def __init__(self, name, category):
        self.name = name
        self.org_category = category


def _owner_env(monkeypatch, *, org, depth):
    """A session that returns `org`, and a tree that reports it at `depth`."""
    import ticketing.services.org_tree as tree

    monkeypatch.setattr(
        tree, "ancestor_org_ids", lambda db, oid, include_self=True: set(range(depth))
    )

    class _DB:
        def get(self, _model, _oid):
            return org

    return _DB()


def test_a_department_may_own_a_template(monkeypatch):
    db = _owner_env(monkeypatch, org=_OrgRow("Department of Roads", "government"), depth=2)
    _validate_owner(db, "DOR")


def test_a_donor_may_own_a_template(monkeypatch):
    db = _owner_env(monkeypatch, org=_OrgRow("Asian Development Bank", "donor"), depth=1)
    _validate_owner(db, "ADB")


def test_a_contractor_may_not(monkeypatch):
    db = _owner_env(monkeypatch, org=_OrgRow("Gamma Ltd", "third_party"), depth=1)
    with pytest.raises(HTTPException) as exc:
        _validate_owner(db, "CONS_1")
    assert exc.value.status_code == 422
    assert "runs or funds projects" in exc.value.detail


def test_a_deep_office_may_not(monkeypatch):
    """A division office is where officers sit, not where templates are authored."""
    db = _owner_env(monkeypatch, org=_OrgRow("Jhapa Division Office", "government"), depth=3)
    with pytest.raises(HTTPException) as exc:
        _validate_owner(db, "DOR_JHAPA")
    assert exc.value.status_code == 422
    assert "too deep" in exc.value.detail


def test_shared_with_everyone_is_always_allowed(monkeypatch):
    _validate_owner(None, None)
