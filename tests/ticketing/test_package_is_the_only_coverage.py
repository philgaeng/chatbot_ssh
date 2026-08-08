"""Coverage is declared on packages, and nowhere else.

Decided 2026-08-08 (Philippe): *"we create first the package — a project with one package is
like a project without package"*, and a package is code + name + description + locations.

**What this replaces.** `project_locations` and `package_locations` were two parallel
declarations of where a project works, and only one of them routed: officer resolution goes
location → *package* → officer scope (`engine/workflow_engine.py`, branch C). Go-live's D1
asserted `project_locations` was non-empty; nothing else read it. So the two drifted, and D1
gave a green light based on the copy that routed nothing — on staging one project had 5 packages
and 0 project locations (D1 would have blocked a working project), another had 2 project
locations and no package coverage at all (D1 passed a project no grievance could reach).

D1 is gone. **B2 inherited its blocking role**, which is the part worth pinning: deleting a
blocker without promoting its replacement would leave activation ungated on location entirely.

Migration `t6v8x0z2`.
"""
from __future__ import annotations

import pytest

from ticketing.models.package import ProjectPackage
from ticketing.services import project_go_live as go_live_svc


# ── No database needed ────────────────────────────────────────────────────────

def test_a_package_is_named_by_default():
    """Every package that existed before the column was one somebody named, so the default has
    to be False or the migration would have silently hidden every existing package's name."""
    assert ProjectPackage.__table__.c.is_unnamed.default.arg is False


def test_an_unnamed_package_answers_with_its_name_not_its_code():
    """`is_unnamed` means the screen never showed a code, so a go-live message that named one
    would point at a string the author cannot find. It says the project's name instead."""
    unnamed = ProjectPackage(project_id="p", package_code="01", name="KL Road", is_unnamed=True)
    assert go_live_svc._package_label(unnamed) == "KL Road"

    named = ProjectPackage(project_id="p", package_code="02", name="Bridge works", is_unnamed=False)
    assert go_live_svc._package_label(named) == "02"


# ── Against the demo database ─────────────────────────────────────────────────

@pytest.mark.integration
def test_project_locations_no_longer_gate_activation(db, kl_road_project):
    """D1 is not merely passing — it is absent. A check that still ran and still passed would
    keep the dead table load-bearing, which is exactly what this change removes."""
    report = go_live_svc.evaluate_go_live(db, kl_road_project.project_id)
    assert not [c for c in report.checks if c.id == "D1"]


@pytest.mark.integration
def test_a_package_with_no_districts_blocks_go_live(db, kl_road_project):
    """B2 was advisory while D1 carried the coverage gate. With D1 gone it has to block, or a
    project can activate with a package no grievance can route into."""
    from ticketing.models.package import PackageLocation

    pkg = ProjectPackage(
        project_id=kl_road_project.project_id,
        package_code="ZZ",
        name="Package with nowhere to work",
        is_active=True,
    )
    db.add(pkg)
    db.flush()
    try:
        report = go_live_svc.evaluate_go_live(db, kl_road_project.project_id)
        b2 = next(c for c in report.checks if c.id == "B2")
        assert b2.severity == "block"
        assert b2.status == "fail"
        assert "ZZ" in b2.message
        assert not report.can_activate

        # And it clears the moment the package says where it works.
        db.add(PackageLocation(package_id=pkg.package_id, location_code="P1_JHA"))
        db.flush()
        b2_after = next(
            c for c in go_live_svc.evaluate_go_live(db, kl_road_project.project_id).checks
            if c.id == "B2"
        )
        assert b2_after.status == "pass"
    finally:
        db.rollback()
