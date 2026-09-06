# SPDX-License-Identifier: Apache-2.0

"""Fill officer-staffing gaps on active projects — additively, never by resetting.

**Why this exists.** `ticketing.seed.mock_tickets --reset` is the only tool that made the
go-live staffing checks pass, and it does so by wiping and re-seeding: it takes the projects,
organizations and users with it. On a development database that carries real local setup, that
is not an acceptable price for a green test run. This script closes the same gaps by *adding
rows*, so an environment that has drifted can be repaired without losing what is in it.

**What it does, and what it will never do.**

* It **inserts** `ticketing.officer_scopes` rows, and nothing else.
* It **never** updates or deletes an existing row, never touches a project, package,
  organization or ticket, and never calls Keycloak. There is no identity to create: officers
  are `user_id` strings here, and the identity provider owns the account.
* It is **idempotent** — a second run inserts nothing.
* It is **dry-run by default**. `--apply` writes.

⭐ **It asks the go-live checks whether a gap exists rather than reimplementing them.** The
coverage rule is subtle — a level declares `staff_per_package`, and a project-wide scope
deliberately does *not* satisfy a per-package level (`project_go_live.py`, C1) — and a second
copy of that rule in a seed script would drift from the one the product enforces. So this
imports `_has_officer_on_package` / `_has_officer_on_project_wide` and trusts them. If the
product's definition of "covered" changes, this script changes with it, for free.

Run it in the container (`docs/deployment/DOCKER.md`); host runs are for reading:

    docker exec nepal_chatbot-backend-1 python -m ticketing.seed.ensure_officer_coverage
    docker exec nepal_chatbot-backend-1 python -m ticketing.seed.ensure_officer_coverage --apply
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.models.base import SessionLocal
from ticketing.models.officer_scope import OfficerScope
from ticketing.models.package import ProjectPackage
from ticketing.models.project import Project
from ticketing.models.workflow import WorkflowStep
from ticketing.services.officer_admin import officer_is_active
from ticketing.services.project_go_live import (
    _has_officer_on_package,
    _has_officer_on_project_wide,
)


@dataclass
class Gap:
    project: str
    role_key: str
    package_code: str | None      # None → the gap is project-wide
    package_id: str | None
    donor: str | None             # an officer already holding this role, or None
    donor_scope: OfficerScope | None


def _steps_for(db: Session, project: Project) -> list[WorkflowStep]:
    ids = [w for w in (project.standard_workflow_id, project.seah_workflow_id) if w]
    if not ids:
        return []
    return list(
        db.execute(
            select(WorkflowStep)
            .where(WorkflowStep.workflow_id.in_(ids))
            .order_by(WorkflowStep.workflow_id, WorkflowStep.step_order)
        ).scalars()
    )


def _donors_for(db: Session, role_key: str, project: Project) -> list[OfficerScope]:
    """Every ACTIVE officer already holding this role, preferring this project's own.

    A donor is how the script stays additive: the new row copies the officer's organization
    and location, so it grants no jurisdiction the officer did not already have — it only
    states the package the product now requires to be named explicitly.

    ⚠ Returns a LIST, and the caller rotates through it, because assignment ranks candidates
    by active ticket load (`workflow_engine`). Putting every package on the first officer
    would be *sufficient* for the go-live check and wrong for everything downstream of it —
    a single officer holding all five packages skews every assignment decision after.
    """
    rows = list(
        db.execute(select(OfficerScope).where(OfficerScope.role_key == role_key)).scalars()
    )
    scoped = [r for r in rows if r.project_id == project.project_id
              or (r.project_code and r.project_code == project.short_code)]
    pool, seen = [], set()
    for candidate in (scoped or rows):
        if candidate.user_id in seen or not officer_is_active(db, candidate.user_id):
            continue
        seen.add(candidate.user_id)
        pool.append(candidate)
    return pool


def find_gaps(db: Session) -> list[Gap]:
    gaps: list[Gap] = []
    projects = list(db.execute(select(Project).where(Project.is_active.is_(True))).scalars())
    for project in projects:
        packages = [
            p for p in db.execute(
                select(ProjectPackage).where(
                    ProjectPackage.project_id == project.project_id,
                    ProjectPackage.is_active.is_(True),
                )
            ).scalars()
        ]
        for step in _steps_for(db, project):
            role = step.assigned_role_key
            pool = _donors_for(db, role, project)
            if step.staff_per_package:
                turn = 0
                for pkg in packages:
                    if _has_officer_on_package(db, package_id=pkg.package_id, grm_role_key=role):
                        continue
                    donor = pool[turn % len(pool)] if pool else None
                    turn += 1
                    gaps.append(Gap(project.short_code, role, pkg.package_code,
                                    pkg.package_id, donor.user_id if donor else None, donor))
            else:
                if _has_officer_on_project_wide(db, project=project, grm_role_key=role):
                    continue
                donor = pool[0] if pool else None
                gaps.append(Gap(project.short_code, role, None, None,
                                donor.user_id if donor else None, donor))
    return gaps


def fill(db: Session, gaps: list[Gap]) -> int:
    written = 0
    for g in gaps:
        if g.donor_scope is None:
            continue
        d = g.donor_scope
        db.add(OfficerScope(
            user_id=d.user_id,
            role_key=g.role_key,
            organization_id=d.organization_id,
            location_code=d.location_code,
            project_id=d.project_id,
            project_code=d.project_code,
            package_id=g.package_id,
            includes_children=d.includes_children,
        ))
        written += 1
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true",
                    help="write the rows (default: report only)")
    args = ap.parse_args()

    with SessionLocal() as db:
        gaps = find_gaps(db)
        if not gaps:
            print("✔ every staffed level on every active project is covered — nothing to add.")
            return 0

        fillable = [g for g in gaps if g.donor_scope is not None]
        orphans = [g for g in gaps if g.donor_scope is None]

        print(f"{len(gaps)} staffing gap(s) on active projects:\n")
        for g in gaps:
            where = f"package {g.package_code}" if g.package_code else "project-wide"
            who = f"→ copy scope from {g.donor}" if g.donor else "→ ⚠ NO officer holds this role"
            print(f"  {g.project:<10} {where:<14} {g.role_key}\n             {who}")

        if orphans:
            print(f"\n⚠ {len(orphans)} gap(s) have no officer to copy from. This script does not")
            print("  invent officers — identity lives in Keycloak, and an account created here")
            print("  would be a user nobody can log in as. Add them through the officer admin UI.")

        if not args.apply:
            print(f"\nDry run. {len(fillable)} row(s) would be inserted. Re-run with --apply.")
            return 0

        written = fill(db, fillable)
        db.commit()
        print(f"\n✔ inserted {written} officer_scopes row(s). Nothing else was modified.")

        remaining = find_gaps(db)
        print(f"  re-checked: {len(remaining)} gap(s) left"
              + (" — all fillable gaps are closed." if len(remaining) == len(orphans) else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
