"""Authoring a project type — the checks that stop a template from being incoherent.

DECISION-author-defined-slots §3.1 / doc 14 §4. A type names the organizations a project must
have and says **which** of them a grievance is recorded against. Two things must hold or the
projects built from it are broken in ways nobody sees until go-live:

  • the anchor is one of the type's own organization roles — not a key from somewhere else;
  • the workflow set has exactly one default, and the default is never a sensitive workflow.

Plus the authoring gate itself: `super_admin` anywhere, `org_admin` inside its own subtree,
and nobody edits the shared (global) templates but the platform administrator.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from ticketing.api.routers.project_types import _require_authority, _validate_config

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


# ── the anchor must exist in the type's own catalog ───────────────────────────

def test_anchor_must_be_one_of_the_types_own_roles():
    with pytest.raises(HTTPException) as exc:
        _validate_config(
            None, actor_roles=[ROLE_IA], routing_org_role="ward_office", workflow_bindings=[]
        )
    assert exc.value.status_code == 422
    # plain language, no field names (ui/05 §2.5)
    assert "recorded against" in exc.value.detail


def test_anchor_is_accepted_when_it_names_a_real_role():
    _validate_config(
        None, actor_roles=[ROLE_IA, ROLE_WARD], routing_org_role="ward_office", workflow_bindings=[]
    )


def test_empty_catalog_does_not_force_an_anchor():
    """A type starts empty — the author names organizations before choosing the anchor."""
    _validate_config(None, actor_roles=[], routing_org_role="implementing_agency", workflow_bindings=[])


def test_duplicate_roles_are_refused():
    with pytest.raises(HTTPException) as exc:
        _validate_config(
            None,
            actor_roles=[ROLE_WARD, dict(ROLE_WARD)],
            routing_org_role="ward_office",
            workflow_bindings=[],
        )
    assert exc.value.status_code == 422
    assert "Ward Office" in exc.value.detail


def test_a_role_needs_a_name():
    with pytest.raises(HTTPException):
        _validate_config(
            None,
            actor_roles=[{"key": "x", "label": "  "}],
            routing_org_role="x",
            workflow_bindings=[],
        )


# ── the workflow set ──────────────────────────────────────────────────────────

def test_exactly_one_default(monkeypatch):
    _patch_workflows(monkeypatch, w1=_Workflow(), w2=_Workflow())
    with pytest.raises(HTTPException) as exc:
        _validate_config(
            None,
            actor_roles=[],
            routing_org_role="x",
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
            actor_roles=[],
            routing_org_role="x",
            workflow_bindings=[_binding("Sensitive", "seah", default=True)],
        )
    assert "sensitive" in exc.value.detail.lower()


def test_a_non_default_workflow_needs_a_chatbot_menu(monkeypatch):
    _patch_workflows(monkeypatch, w1=_Workflow(), w2=_Workflow())
    with pytest.raises(HTTPException) as exc:
        _validate_config(
            None,
            actor_roles=[],
            routing_org_role="x",
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
            actor_roles=[],
            routing_org_role="x",
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
        routing_org_role="implementing_agency",
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
    anchor = [e for e in catalog if e["is_routing_anchor"]]
    assert len(anchor) == 1 and anchor[0]["key"] == pt.routing_org_role
