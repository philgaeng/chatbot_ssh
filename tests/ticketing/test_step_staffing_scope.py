"""A level says whether it is staffed once for the project, or package by package.

`workflow_steps.staff_per_package` (migration `p2r4t6v8`, decided 2026-08-04). The **workflow
author** sets it, so a project built from a type inherits it and has no switch of its own.

Why it exists: before, go-live's staffing checks had to guess. They accepted *either* a
project-wide officer *or* full per-package coverage for every level, because nothing recorded which
the author meant. A level intended to be staffed package by package therefore passed with one
project-wide officer, and a project-wide level was never asked about packages — green either way,
and telling you nothing. These tests pin the two shapes apart.
"""
from __future__ import annotations

from contextlib import contextmanager

import pytest

from ticketing.services import project_go_live as go_live_svc

pytestmark = pytest.mark.integration


def _l1(db, project):
    from sqlalchemy import select

    from ticketing.models.workflow import WorkflowStep

    return db.execute(
        select(WorkflowStep)
        .where(WorkflowStep.workflow_id == project.standard_workflow_id)
        .order_by(WorkflowStep.step_order)
        .limit(1)
    ).scalar_one()


def _check(db, project, check_id):
    report = go_live_svc.evaluate_go_live(db, project.project_id)
    return next(c for c in report.checks if c.id == check_id)


@contextmanager
def _l1_scope(db, project, per_package: bool):
    """Run the body with KL Road's Level 1 set one way, then put it back.

    Both scopes are *set* rather than inherited (2026-08-07). These tests used to read whatever
    the demo database happened to say — one asserted "KL Road staffs Level 1 project-wide" as a
    standing fact. It is not a fact, it is a checkbox: an admin ticked **Staffed for each package**
    in the UI and three tests went red without a line of code changing. A test that asserts a
    value a user is invited to edit is testing the database's mood.
    """
    step = _l1(db, project)
    saved = step.staff_per_package
    try:
        step.staff_per_package = per_package
        db.flush()
        yield step
    finally:
        step.staff_per_package = saved
        db.flush()


def test_default_is_project_wide():
    """Every step predates the column, so the default has to preserve what they did — asserted
    on the column, which is what the migration back-filled, not on a row anyone can edit."""
    from ticketing.models.workflow import WorkflowStep

    assert WorkflowStep.__table__.c.staff_per_package.default.arg is False
    assert WorkflowStep(workflow_id="x", step_order=1).staff_per_package in (False, None)


def test_a_project_wide_level_passes_on_one_officer(db, kl_road_project):
    """KL Road has packages with no per-package officer. With Level 1 declared project-wide, its one
    project-wide officer is a complete answer."""
    with _l1_scope(db, kl_road_project, per_package=False):
        assert _check(db, kl_road_project, "C1").status == "pass"
        assert _check(db, kl_road_project, "C5").status == "pass"


def test_a_per_lot_level_is_not_satisfied_by_a_project_wide_officer(db, kl_road_project):
    """The whole point. Same staffing as the passing case above — only the level's own answer
    changed — and now the checks name the packages that need somebody."""
    with _l1_scope(db, kl_road_project, per_package=True):
        c1 = _check(db, kl_road_project, "C1")
        assert c1.status == "fail" and c1.severity == "block"
        assert "packages" in c1.message

        c5 = _check(db, kl_road_project, "C5")
        assert c5.status == "fail"


def test_the_country_fallback_cannot_answer_a_per_lot_level():
    """The country L1 fallback is an emergency net for *assignment* so intake never dead-ends.
    Letting it answer a per-package level would put the check straight back to guessing, so the
    fallback branch is reachable only when the level is project-wide.

    Asserted on the source rather than by staffing a fallback officer: `_any_active_officer`
    resolves against the identity provider, so a fabricated officer would make the test pass
    for the wrong reason.
    """
    import inspect

    src = inspect.getsource(go_live_svc._standard_level_gaps)
    assert "if is_actor_l1 and not per_package" in src
