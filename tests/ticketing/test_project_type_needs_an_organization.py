"""A project type must name at least one organization.

Decided 2026-08-08 (Philippe), after saving a type that named none and then meeting the
consequence four screens later: the project built from it opened its **Organizations** section
to a dead end — *"This project's type does not name any organizations yet"* — with no way
forward from there. Worse, the go-live rail showed that section **green**: nothing was required,
so nothing was missing, so the check passed. Vacuously true and, on screen, a lie.

The cost is not cosmetic. `services/org_reach.py` decides who sees a grievance in reports from
the organizations named on its project, so a project whose type names none has grievances that
reach nobody at all.

Caught where the type is authored, like "no name, no save" on workflow jobs — not on the project
that merely displays the symptom.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from ticketing.api.routers.project_types import _validate_config


def test_a_type_that_names_no_organization_is_refused():
    with pytest.raises(HTTPException) as exc:
        _validate_config(None, actor_roles=[], workflow_bindings=[])
    assert exc.value.status_code == 422
    # The message says what to do, in the author's terms — no field names, no codes (ui/05 §2.5).
    assert "at least one organization" in str(exc.value.detail).lower()


def test_one_organization_is_enough():
    _validate_config(
        None,
        actor_roles=[{"key": "implementing_agency", "label": "Implementing Agency"}],
        workflow_bindings=[],
    )


def test_renaming_an_existing_empty_type_is_still_allowed():
    """The guard fires only when the catalog is being *set*.

    A PATCH that touches just the name falls back to the stored (empty) list, and a frozen type
    in use keeps its name editable on purpose (DECISION-author-defined-slots §8). Enforcing on
    that path would make an already-empty type unrenamable — taking away the one repair its
    author still has.
    """
    _validate_config(None, actor_roles=[], workflow_bindings=[], require_actor_roles=False)
