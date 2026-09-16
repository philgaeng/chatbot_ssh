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
        _require_editable(_FakeDB(2), "t", {"label", "actor_roles"})


# ── the ticket's organization stamp (DECISION-organization-membership, 2026-08-04) ───────
#
# `routing_org_role` is retired. It used to designate WHICH named organization a grievance was
# reported under, which meant one organization owned the grievance and every other organization
# on the project owned nothing. Reporting is membership now (`services/org_reach.py`), and this
# stamp is descriptive only: `tickets.organization_id` is NOT NULL and rides along in a few
# payloads, so it still needs a stable, predictable value.


class _Org:
    def __init__(self, organization_id: str, org_role: str):
        self.organization_id = organization_id
        self.org_role = org_role


class _Project:
    def __init__(self, orgs, legacy=None, type_key="t"):
        self.organizations = orgs
        self.implementing_agency_org_id = legacy
        self.project_type_key = type_key


def _resolve(monkeypatch, project, required=()):
    """Resolve with a stubbed catalog — the roles the author marked REQUIRED, in order."""
    import ticketing.services.project_routing as pr

    monkeypatch.setattr(pr, "_required_role_order", lambda db, p: list(required))
    return pr._primary_org_for_project(None, project)


def test_stamp_follows_the_first_required_role(monkeypatch):
    """Required, not merely listed. The back-fill migration writes catalog keys alphabetically,
    so "first listed" on a migrated type is `donor` — an accident of sorting. `required` is the
    author saying every project of this kind must have this one."""
    p = _Project([_Org("ORG_CONTRACTOR", "contractor"), _Org("ORG_WARD", "ward_office")])
    assert _resolve(monkeypatch, p, required=["ward_office"]) == "ORG_WARD"


def test_stamp_falls_back_to_any_named_organization(monkeypatch):
    """A project whose type requires roles nobody filled still has organizations on it."""
    p = _Project([_Org("ORG_ANY", "some_other_role")])
    assert _resolve(monkeypatch, p, required=["ward_office"]) == "ORG_ANY"


def test_stamp_falls_back_to_the_legacy_field(monkeypatch):
    """Pre-types projects kept their accountable organization on the project row."""
    p = _Project([], legacy="ORG_LEGACY", type_key=None)
    assert _resolve(monkeypatch, p) == "ORG_LEGACY"


def test_returns_none_when_neither_exists(monkeypatch):
    assert _resolve(monkeypatch, _Project([], legacy=None)) is None
