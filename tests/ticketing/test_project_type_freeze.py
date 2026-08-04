"""A project type in use is frozen — edit by cloning (DECISION-author-defined-slots §8).

The rule exists so one edit cannot re-configure every project of a kind at once, and so the
answer to "what does this project run?" never changes underneath its officers. It is enforced
in the API rather than by disabling a form: a disabled form is a suggestion.

What is deliberately still allowed on a bound type: `is_active` and `sort_order`. Retiring a
type from the New-project list is availability, not configuration.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from ticketing.api.routers.project_types import CONFIG_FIELDS, _require_unbound


class _FakeDB:
    """Stands in for the session — `_require_unbound` only counts bound projects."""

    def __init__(self, count: int):
        self._count = count

    def execute(self, *_a, **_k):
        outer = self

        class _R:
            def scalar_one(self):
                return outer._count

        return _R()


@pytest.mark.parametrize("field", CONFIG_FIELDS)
def test_every_config_field_is_frozen_when_bound(field):
    with pytest.raises(HTTPException) as exc:
        _require_unbound(_FakeDB(3), "construction_road", {field})
    assert exc.value.status_code == 409
    assert "template" in exc.value.detail  # points the author at the way out


@pytest.mark.parametrize("field", ["is_active", "sort_order"])
def test_availability_fields_stay_editable_when_bound(field):
    """Retiring a bound type from the New-project list must keep working — it changes nothing
    about the projects already running on it."""
    _require_unbound(_FakeDB(3), "construction_road", {field})


def test_config_change_allowed_when_no_project_uses_it():
    _require_unbound(_FakeDB(0), "draft_type", {"actor_roles"})


def test_message_names_the_number_of_projects_at_stake():
    """The author must see the blast radius they are being protected from."""
    with pytest.raises(HTTPException) as exc:
        _require_unbound(_FakeDB(1), "t", {"label"})
    assert "1 project" in exc.value.detail and "1 projects" not in exc.value.detail

    with pytest.raises(HTTPException) as exc:
        _require_unbound(_FakeDB(12), "t", {"label"})
    assert "12 projects" in exc.value.detail


def test_mixed_payload_is_refused():
    """A PATCH that touches availability AND configuration is a configuration change."""
    with pytest.raises(HTTPException):
        _require_unbound(_FakeDB(2), "t", {"is_active", "actor_roles"})
