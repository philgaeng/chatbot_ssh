"""A project type cannot be **offered** without naming an organization.

Decided 2026-08-08 (Philippe), after building a project on a type that named none: the project's
**Organizations** section opened to a dead end — *"This project's type does not name any
organizations yet"* — with no way forward, while the go-live rail showed that section **green**
(nothing required, so nothing missing, so B1 passed vacuously).

The cost is not cosmetic. `services/org_reach.py` decides who sees a grievance in reports from
the organizations named on its project, so a project on such a type has grievances that reach
nobody at all.

**The first attempt guarded the wrong gate and broke authoring entirely.** It refused to *create*
a type with no organizations — but types are authored empty on purpose: `ProjectTypesTab` posts
`actor_roles: []`, `is_active: false`, then says "Set it up, then turn it on". So no new type
could be created at all, and the 422 arrived rendered in the success colour, which is how it
reached the user as *"I was not able to create a new type"* rather than as an error.
`test_a_type_can_start_empty` had said exactly this, and was overridden instead of read.

The gate is **being offered**: an empty type may exist and be worked on; it may not be chosen for
a project until it names someone. That is where the harm starts, and it is the last moment the
author is still looking at the type.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from ticketing.api.routers.project_types import (
    _require_organizations_to_offer,
    _validate_config,
)

ROLE = {"key": "implementing_agency", "label": "Implementing Agency"}


def test_a_type_may_be_created_and_worked_on_while_empty():
    """The regression that broke authoring. A new type has no organizations yet — that is the
    normal first second of its life, not an error."""
    _require_organizations_to_offer([], offered=False)
    _validate_config(None, actor_roles=[], workflow_bindings=[])


def test_an_empty_type_cannot_be_turned_on():
    with pytest.raises(HTTPException) as exc:
        _require_organizations_to_offer([], offered=True)
    assert exc.value.status_code == 422
    # Says what to do, in the author's terms — no field names, no codes (ui/05 §2.5).
    assert "at least one organization" in str(exc.value.detail).lower()


def test_one_organization_is_enough_to_turn_it_on():
    _require_organizations_to_offer([ROLE], offered=True)
