"""Who counts as the reassignment backstop (go-live R1).

R1 exists to kill one failure: a ticket bounced at a level nobody can move it off. The chain is
Dispatcher → Supervisor → Actor self-serve → **an administrator**, and the last link is the
guaranteed one.

**Widened 2026-08-09** (Philippe: *"I don't see the need for a project administrator as this is
100% managed in the admin section and whoever creates the project has indeed rights to
administrate it and can give rights to others"*). It used to ask for a `project_admin` row on
the project specifically — the *third* tier of the admin ladder. A project administered by an
`org_admin` whose subtree covers it, or by a `super_admin`, therefore had no reassigner as far
as go-live was concerned, and R1 demanded a row that granted authority those people already
had. A check that disagrees with the permission model is a false blocker, not a safety net.

The runtime resolver was widened in step: go-live accepting an authority that
`resolve_reassignment_authority` would not then find is the same bug pointing the other way.
"""
from __future__ import annotations

import pytest

from ticketing.services.reassignment import _project_admin_holder

pytestmark = pytest.mark.integration


def test_a_project_with_no_project_admin_row_still_has_a_backstop(db, kl_road_project):
    """The seeded demo has no `project_admin` **AdminScope** — its project admin is an officer
    scope — so before this change every seeded project failed R1's last link and leaned on a
    staffed supervisor to pass. The super_admin above it was always able to reassign."""
    refs = [kl_road_project.project_id, kl_road_project.short_code]
    assert _project_admin_holder(db, refs, kl_road_project) is not None


def test_go_live_r1_passes_on_the_seeded_project(db, kl_road_project):
    """The check itself, not just its helper — R1 is what the author sees, and it must agree."""
    from ticketing.services import project_go_live as go_live_svc

    report = go_live_svc.evaluate_go_live(db, kl_road_project.project_id)
    r1 = next((c for c in report.checks if c.id == "R1"), None)
    assert r1 is not None
    assert r1.status == "pass", r1.message


def test_no_project_refs_means_no_backstop(db):
    """An unanchored lookup must not wander into "some admin exists somewhere" — with no project
    to match, there is nothing to be the backstop *of*."""
    assert _project_admin_holder(db, [], None) is None
