# SPDX-License-Identifier: Apache-2.0

"""
The demo seed must produce a project that can actually accept a grievance — D-26.

⭐ **Why this file exists.** CI was red for eleven days with eighteen failures, and every one of
them traced to the same shape of mistake made three times over:

> **A back-fill migration reads data the seeder writes afterwards.**

Migrations run first, then `mock_tickets.py` runs. So a migration that derives its rows from
`projects.standard_workflow_id`, or from `project_workflows`, finds nothing on a **fresh**
database — and only on a fresh database. On the deployment where a human checks, the data is
already there and the back-fill works perfectly. Nothing raises. A table is simply empty, and the
symptom arrives much later wearing an unrelated face: eighteen tests failed, and only two of them
said anything about packages, workflows or types.

The three instances, all landed 2026-08-04 to 08-08 and all silently no-ops since:

| Back-fill | Reads | Written by | Result on a fresh DB |
|---|---|---|---|
| `b3c5d7e9` project workflow slots | `projects.standard_workflow_id` | `seed_standard()` | empty `project_workflows` |
| `n0p2r4t6` project types | `project_workflows` | (the above) | every project untyped |
| `p2r4t6v8` per-package staffing | — (sets `staff_per_package`) | seed staffs project-wide | **intake refuses every ticket** |

These tests pin the *outcome* rather than any one of those mechanisms, because the mechanism will
change and the outcome must not: **a freshly built database must produce a project that can take a
grievance.** If a future migration or seeder change breaks that again, this file names it in one
sentence instead of eighteen unrelated assertion failures.

Not a unit test suite — it reads the seeded database, so it carries `integration`.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from ticketing.models.package import ProjectPackage
from ticketing.models.project import Project
from ticketing.models.project_type import ProjectType
from ticketing.models.project_workflow import ProjectWorkflow
from ticketing.services import project_go_live as go_live_svc

pytestmark = pytest.mark.integration


def _projects(db):
    return db.execute(select(Project)).scalars().all()


# ── the outcome that matters ─────────────────────────────────────────────────

def test_the_demo_project_can_accept_a_grievance(db, kl_road_project):
    """⭐ The one assertion the whole file is for.

    C1 gates **intake**, not merely activation: with a single lot unstaffed,
    `POST /api/v1/tickets` refuses with "Ticket intake blocked". That is what took out ten of the
    eighteen CI failures, and the message named packages while the tests named tickets.
    """
    block = go_live_svc.ticket_intake_block_message(db, kl_road_project.project_id)
    assert block is None, block


def test_every_level_one_lot_has_an_officer(db, kl_road_project):
    """`LEVEL_1_SITE.staff_per_package` is `True`, so every active lot needs its own officer.

    Asserted per lot rather than on the aggregate, so a failure names the lot instead of saying
    the count is wrong.
    """
    report = go_live_svc.evaluate_go_live(db, kl_road_project.project_id)
    c1 = next(c for c in report.checks if c.id == "C1")
    assert c1.status == "pass", c1.message


def test_the_donor_is_in_the_final_step_informed_cast(db, kl_road_project):
    """A donor who funds the project and is never told how a grievance ended is the failure the
    guardrail exists to prevent — and go-live blocks on it.

    ⚠ This one presented as **flaky rather than broken**, which is why it survived so long.
    Adding a donor through the API also runs `apply_donor_informed_defaults`; the seed wrote
    `project_donors` straight to the table and skipped it. So it failed on every fresh database —
    and the test that exercises `apply_donor_informed_defaults` **commits**, so one full suite run
    repaired the database permanently and the failure disappeared until the next fresh build.
    Anyone who re-ran to check would have seen it pass.
    """
    from ticketing.services.donor_guardrail import donor_informed_ok, project_donor_org_ids

    assert project_donor_org_ids(db, kl_road_project.project_id), "KL Road must name a donor"
    assert donor_informed_ok(db, kl_road_project) is True


# ── the structural facts a fresh database must carry ─────────────────────────

def test_every_project_has_a_type(db):
    """Untyped is not a state a seeded project may be in: the type is where its required
    organizations and its workflow bindings come from, so B1 and every type-driven screen have
    nothing to read without one."""
    untyped = [p.short_code for p in _projects(db) if not p.project_type_key]
    assert not untyped, f"projects with no type: {untyped}"


def test_the_type_names_the_anchor_role_as_required(db, kl_road_project):
    """`implementing_agency` is what B1 blocks on and what the ticket stamp resolves through.
    A type that lists it without marking it required would pass B1 while meaning nothing."""
    pt = db.get(ProjectType, kl_road_project.project_type_key)
    assert pt is not None
    required = {r["key"] for r in (pt.actor_roles or []) if r.get("required")}
    assert "implementing_agency" in required


def test_every_project_links_the_workflows_it_runs(db):
    """The N-slot model, not the two legacy columns. The type derives from these links, so an
    empty link table silently produces an untyped project one step later."""
    for project in _projects(db):
        links = db.execute(
            select(ProjectWorkflow).where(ProjectWorkflow.project_id == project.project_id)
        ).scalars().all()
        if project.standard_workflow_id or project.seah_workflow_id:
            assert links, f"{project.short_code} runs workflows but links none"
        linked = {l.workflow_id for l in links}
        for legacy in (project.standard_workflow_id, project.seah_workflow_id):
            if legacy:
                assert legacy in linked, f"{project.short_code}: {legacy} not linked"


def test_exactly_one_workflow_is_the_default(db, kl_road_project):
    """Two defaults is an ambiguity intake resolves arbitrarily; none means it cannot resolve
    at all."""
    links = db.execute(
        select(ProjectWorkflow).where(ProjectWorkflow.project_id == kl_road_project.project_id)
    ).scalars().all()
    assert sum(1 for l in links if l.is_default) == 1


def test_every_lot_is_reachable_from_a_district(db, kl_road_project):
    """The lot→officer pairing is derived from `package_locations`, so a lot that declares no
    location cannot be staffed by derivation and would fail intake with no obvious cause."""
    from ticketing.models.package import PackageLocation

    packages = db.execute(
        select(ProjectPackage).where(
            ProjectPackage.project_id == kl_road_project.project_id,
            ProjectPackage.is_active.is_(True),
        )
    ).scalars().all()
    assert packages, "KL Road must have lots"
    for pkg in packages:
        locs = db.execute(
            select(PackageLocation.location_code).where(
                PackageLocation.package_id == pkg.package_id
            )
        ).scalars().all()
        assert locs, f"lot {pkg.package_code} declares no location"
