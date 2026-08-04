"""A project type with a LIVE project is frozen — edit by cloning (DECISION §8, amended 2026-08-04).

The rule stops one edit from re-configuring every project of a kind at once, and keeps the
answer to "what does this project run?" from changing underneath its officers. It is enforced
in the API, not by disabling a form: a disabled form is a suggestion.

Two deliberate holes, both added when back-filling types by migration made them necessary:

  • **Name and description are always editable.** A name is not configuration — and the
    migration names types "Type 1", "Type 2", which somebody must be able to fix.
  • **Only ACTIVE projects freeze a type.** A project not accepting grievances has no officers
    depending on its setup, so *deactivate → fix the type → reactivate* is the repair path.
    Reactivating re-runs go-live, so a broken setup cannot sneak back in.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from ticketing.api.routers.project_types import CONFIG_FIELDS, _require_editable


class _FakeDB:
    """Stands in for the session — the predicate only counts active projects."""

    def __init__(self, active: int):
        self._active = active

    def execute(self, *_a, **_k):
        outer = self

        class _R:
            def scalar_one(self):
                return outer._active

        return _R()


@pytest.mark.parametrize("field", CONFIG_FIELDS)
def test_config_is_frozen_while_a_project_is_live(field):
    with pytest.raises(HTTPException) as exc:
        _require_editable(_FakeDB(3), "construction_road", {field})
    assert exc.value.status_code == 409
    # the message must offer both ways out, or the author is simply stuck
    assert "Deactivate" in exc.value.detail and "template" in exc.value.detail


@pytest.mark.parametrize("field", ["label", "description"])
def test_renaming_is_always_allowed(field):
    """A name is not configuration. The back-fill migration names types "Type 1" — that has to
    be fixable without cloning a type that projects already run on."""
    assert field not in CONFIG_FIELDS
    _require_editable(_FakeDB(9), "migrated_type_1", {field})


@pytest.mark.parametrize("field", ["is_active", "sort_order"])
def test_availability_is_always_allowed(field):
    """Retiring a type from the New-project list changes nothing about projects using it."""
    _require_editable(_FakeDB(3), "construction_road", {field})


def test_config_change_allowed_when_no_project_is_live():
    """The case the back-fill depends on: types bound only to projects still being set up stay
    editable, so migrating does not freeze a half-configured project forever."""
    _require_editable(_FakeDB(0), "migrated_type_1", {"actor_roles"})


def test_message_names_how_many_projects_are_at_stake():
    with pytest.raises(HTTPException) as exc:
        _require_editable(_FakeDB(1), "t", {"actor_roles"})
    assert "1 active project uses" in exc.value.detail

    with pytest.raises(HTTPException) as exc:
        _require_editable(_FakeDB(12), "t", {"actor_roles"})
    assert "12 active projects use" in exc.value.detail


def test_mixed_payload_is_refused():
    """A PATCH touching availability AND configuration is a configuration change."""
    with pytest.raises(HTTPException):
        _require_editable(_FakeDB(2), "t", {"is_active", "actor_roles"})


def test_rename_alongside_config_is_still_refused():
    """Renaming is free, but it cannot be used as a wrapper to smuggle a config change."""
    with pytest.raises(HTTPException):
        _require_editable(_FakeDB(2), "t", {"label", "routing_org_role"})


# ── routing anchor order (DECISION-author-defined-slots §3.1) ─────────────────

class _Org:
    def __init__(self, organization_id: str, org_role: str):
        self.organization_id = organization_id
        self.org_role = org_role


class _Project:
    def __init__(self, orgs, legacy=None, type_key="t"):
        self.organizations = orgs
        self.implementing_agency_org_id = legacy
        self.project_type_key = type_key


def _resolve(monkeypatch, project, anchor_role="implementing_agency"):
    import ticketing.services.project_routing as pr

    monkeypatch.setattr(pr, "routing_org_role_for_project", lambda db, p: anchor_role)
    return pr._project_routing_org(None, project)


def test_anchor_comes_from_the_slot_the_author_designated(monkeypatch):
    """The type names WHICH role anchors the ticket, so a client's own word works."""
    p = _Project([_Org("ORG_WARD", "ward_office")], legacy="ORG_LEGACY")
    assert _resolve(monkeypatch, p, anchor_role="ward_office") == "ORG_WARD"


def test_slot_wins_over_the_legacy_field(monkeypatch):
    """The inversion itself: same project, both present, the slot decides."""
    p = _Project([_Org("ORG_SLOT", "implementing_agency")], legacy="ORG_LEGACY")
    assert _resolve(monkeypatch, p) == "ORG_SLOT"


def test_falls_back_to_the_legacy_field_when_the_slot_is_empty(monkeypatch):
    """Projects with no type — the back-fill skips those with no workflow links — and typed
    projects whose anchor slot is not filled yet must still route."""
    p = _Project([], legacy="ORG_LEGACY", type_key=None)
    assert _resolve(monkeypatch, p) == "ORG_LEGACY"


def test_returns_none_when_neither_exists(monkeypatch):
    assert _resolve(monkeypatch, _Project([], legacy=None)) is None
