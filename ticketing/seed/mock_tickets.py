# SPDX-License-Identifier: Apache-2.0

"""
Mock tickets for May 10 demo.

Demo scenario 1 — Standard GRM:
  Dust / health complaint along KL Road (L1 → L2 → L3 in progress)

Demo scenario 2 — SEAH:
  Harassment by construction worker (L1 investigation in progress)

Also seeds a few supporting tickets to make the queue look realistic.

Run full seed (workflows + tickets):
  python -m ticketing.seed.mock_tickets

Reset and re-seed:
  python -m ticketing.seed.mock_tickets --reset
"""
from __future__ import annotations

import logging
import sys
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ticketing.models.base import SessionLocal
from ticketing.models.officer_scope import OfficerScope
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.user import UserRole
from ticketing.constants.demo_officers import (
    DEMO_OFFICER_SPECS,
    LEGACY_OFFICER_ID_MAP,
    OFFICER_ADMIN,
    OFFICER_ADB,
    OFFICER_COUNTRY_ADMIN_SEAH,
    OFFICER_COUNTRY_ADMIN_STD,
    OFFICER_GRC_CHAIR,
    OFFICER_GRC_MEMBER_1,
    OFFICER_GRC_MEMBER_2,
    OFFICER_PROJECT_ADMIN,
    OFFICER_PIU_L2,
    OFFICER_PIU_L2_2,
    OFFICER_PIU_L2_3,
    OFFICER_SEAH_HQ,
    OFFICER_SEAH_NATIONAL,
    OFFICER_SITE_L1,
    OFFICER_SITE_L1_2,
    OFFICER_SITE_L1_3,
    OFFICER_SITE_L1_4,
)
from ticketing.seed.kl_road_seah import (
    STEP_SEAH_L1_ID,
    STEP_SEAH_L2_ID,
    WORKFLOW_SEAH_ID,
    seed_seah,
)
from ticketing.seed.kl_road_standard import (
    LOC_JHAPA_CODE,
    LOC_MORANG_CODE,
    LOC_PROVINCE1_CODE,
    LOC_SUNSARI_CODE,
    ORG_ADB_ID,
    ORG_DOR_ID,
    STEP_L1_ID,
    STEP_L2_ID,
    STEP_L3_ID,
    STEP_L4_ID,
    WORKFLOW_STANDARD_ID,
    seed_standard,
)

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ago(days: int = 0, hours: int = 0) -> datetime:
    return _now() - timedelta(days=days, hours=hours)


def _id() -> str:
    return str(uuid.uuid4())


# ── Officer user IDs = Keycloak emails (see ticketing.constants.demo_officers) ─


def migrate_legacy_officer_user_ids(db: Session) -> None:
    """Rename legacy mock-* user_ids to @grm.local emails (idempotent)."""
    for old_id, new_id in LEGACY_OFFICER_ID_MAP.items():
        _migrate_one_officer_user_id(db, old_id, new_id)
    db.flush()


def _migrate_one_officer_user_id(db: Session, old_id: str, new_id: str) -> None:
    if old_id == new_id:
        return
    from sqlalchemy import delete, select, update

    has_old = db.execute(
        select(UserRole.user_id).where(UserRole.user_id == old_id).limit(1)
    ).scalar_one_or_none()
    has_new = db.execute(
        select(UserRole.user_id).where(UserRole.user_id == new_id).limit(1)
    ).scalar_one_or_none()
    if not has_old and not has_new:
        return

    if has_old and has_new:
        db.execute(delete(UserRole).where(UserRole.user_id == old_id))
        db.execute(delete(OfficerScope).where(OfficerScope.user_id == old_id))
        from ticketing.models.officer_onboarding import OfficerOnboarding
        db.execute(delete(OfficerOnboarding).where(OfficerOnboarding.user_id == old_id))
    elif has_old:
        db.execute(update(UserRole).where(UserRole.user_id == old_id).values(user_id=new_id))
        db.execute(update(OfficerScope).where(OfficerScope.user_id == old_id).values(user_id=new_id))

    if not has_old:
        return

    for col_name in (
        "assigned_to_user_id",
        "complainant_reply_owner_id",
        "created_by_user_id",
        "updated_by_user_id",
    ):
        db.execute(
            update(Ticket)
            .where(getattr(Ticket, col_name) == old_id)
            .values(**{col_name: new_id})
        )

    for col_name in (
        "assigned_to_user_id",
        "created_by_user_id",
        "old_assigned_to",
        "new_assigned_to",
    ):
        db.execute(
            update(TicketEvent)
            .where(getattr(TicketEvent, col_name) == old_id)
            .values(**{col_name: new_id})
        )

    from ticketing.models.ticket_viewer import TicketViewer
    from ticketing.models.ticket_task import TicketTask
    from ticketing.models.officer_onboarding import OfficerOnboarding

    db.execute(update(TicketViewer).where(TicketViewer.user_id == old_id).values(user_id=new_id))
    db.execute(update(TicketViewer).where(TicketViewer.added_by_user_id == old_id).values(added_by_user_id=new_id))
    db.execute(update(TicketTask).where(TicketTask.assigned_to_user_id == old_id).values(assigned_to_user_id=new_id))
    db.execute(update(TicketTask).where(TicketTask.assigned_by_user_id == old_id).values(assigned_by_user_id=new_id))
    db.execute(update(TicketTask).where(TicketTask.completed_by_user_id == old_id).values(completed_by_user_id=new_id))
    if not (has_old and has_new):
        db.execute(update(OfficerOnboarding).where(OfficerOnboarding.user_id == old_id).values(user_id=new_id))

    logger.info("Migrated officer user_id %s → %s", old_id, new_id)


def seed_mock_officers(db: Session) -> None:
    """Assign GRM roles — user_id matches Keycloak login email."""
    migrate_legacy_officer_user_ids(db)
    from sqlalchemy import select
    from ticketing.models.user import Role as RoleModel

    def _get_role_id(role_key: str) -> str | None:
        r = db.execute(
            select(RoleModel).where(RoleModel.role_key == role_key)
        ).scalar_one_or_none()
        return r.role_id if r else None

    assignments = [
        (spec.email, spec.role_key, spec.organization_id, spec.user_role_location)
        for spec in DEMO_OFFICER_SPECS
    ]

    for user_id, role_key, org_id, loc_code in assignments:
        role_id = _get_role_id(role_key)
        if not role_id:
            logger.warning("  ! role not found: %s — skipping %s", role_key, user_id)
            continue
        # Check if already assigned
        existing = db.execute(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == role_id,
                UserRole.organization_id == org_id,
            )
        ).scalar_one_or_none()
        if not existing:
            ur = UserRole(
                user_id=user_id,
                role_id=role_id,
                organization_id=org_id,
                location_code=loc_code,
            )
            db.add(ur)
            logger.info("  + officer role: %s → %s @ %s", user_id, role_key, org_id)
        else:
            logger.info("  = officer role already assigned: %s → %s", user_id, role_key)
    db.flush()


def seed_admin_scopes(db: Session) -> None:
    """Scoped admin assignments for demo matrix (org_admin / project_admin)."""
    from sqlalchemy import select

    from ticketing.models.admin_scope import AdminScope

    specs = [
        (OFFICER_COUNTRY_ADMIN_STD, "org_admin", "NP", None, "standard", OFFICER_ADMIN),
        (OFFICER_COUNTRY_ADMIN_SEAH, "org_admin", "NP", None, "seah", OFFICER_ADMIN),
        (OFFICER_PROJECT_ADMIN, "project_admin", None, "KL_ROAD", "standard", OFFICER_COUNTRY_ADMIN_STD),
    ]
    for user_id, role_key, country, project_id, track, created_by in specs:
        existing = db.execute(
            select(AdminScope).where(
                AdminScope.user_id == user_id,
                AdminScope.role_key == role_key,
                AdminScope.workflow_track == track,
                AdminScope.project_id == project_id,
            )
        ).scalar_one_or_none()
        if existing:
            continue
        db.add(
            AdminScope(
                user_id=user_id,
                role_key=role_key,
                country_code=country,
                project_id=project_id,
                workflow_track=track,
                created_by_user_id=created_by,
            )
        )
        logger.info("  + admin_scope: %s → %s track=%s", user_id, role_key, track)
    db.flush()


def seed_project_workflow_links(db: Session) -> None:
    """Link each project to the workflows it runs — the N-slot model, not the two legacy columns.

    ⚠ **Third instance of the same root cause.** `project_workflows` arrived with migration
    `b3c5d7e9`, which back-fills it from `projects.standard_workflow_id` / `seah_workflow_id`.
    Those columns are set by `seed_standard()` / `seed_seah()`, which run **after** migrations —
    so on a fresh database the back-fill selected zero rows, the link table stayed empty, and
    `seed_project_types()` (which derives a type from these links, exactly as its own back-fill
    does) then had nothing to derive from.

    The pattern is worth naming, because it will recur: **a back-fill migration that reads data
    the seeder writes afterwards is a no-op on every fresh database, and only on fresh
    databases.** It works perfectly in the place people look — an existing deployment — and
    fails silently in CI and on a new developer's first `make wsl-up`. Nothing errors; a table is
    simply empty, and the symptom surfaces later as something unrelated.
    """
    from sqlalchemy import select

    from ticketing.constants.workflow_routing import (
        SEED_SAFEGUARDS_INTAKE_ROUTE,
        SEED_SEAH_CLASSIFICATIONS,
        SEED_SEAH_INTAKE_ROUTE,
    )
    from ticketing.models.project import Project
    from ticketing.models.project_workflow import ProjectWorkflow
    from ticketing.models.workflow import WorkflowDefinition

    for project in db.execute(select(Project)).scalars().all():
        slots = [
            (project.standard_workflow_id, "Safeguards GRM", SEED_SAFEGUARDS_INTAKE_ROUTE, [], True, 10),
            (project.seah_workflow_id, "SEAH", SEED_SEAH_INTAKE_ROUTE, list(SEED_SEAH_CLASSIFICATIONS), False, 40),
        ]
        for workflow_id, label, intake_route, classifications, is_default, sort_order in slots:
            if not workflow_id:
                continue
            existing = db.execute(
                select(ProjectWorkflow).where(
                    ProjectWorkflow.project_id == project.project_id,
                    ProjectWorkflow.workflow_id == workflow_id,
                )
            ).scalar_one_or_none()
            if existing:
                continue
            wf = db.get(WorkflowDefinition, workflow_id)
            db.add(
                ProjectWorkflow(
                    project_id=project.project_id,
                    workflow_id=workflow_id,
                    display_label=(wf.display_name if wf and wf.display_name else label),
                    classifications=classifications,
                    intake_route=intake_route,
                    is_default=is_default,
                    sort_order=sort_order,
                )
            )
            logger.info("  + workflow link: %s → %s (%s)", project.short_code, label, intake_route)
    db.flush()


def seed_project_types(db: Session) -> None:
    """Give every seeded project a type — because on a fresh database nothing else will.

    ⚠ **This is the fix for a whole class of CI failure, not a nicety.** `project_types` arrived
    on 2026-08-04 with a back-fill migration (`n0p2r4t6`) that derives a type from the workflows
    a project already runs. Its very first statement is
    `FROM ticketing.projects p JOIN ticketing.project_workflows pw`, and it returns immediately
    when that join is empty.

    On any **existing** deployment the join was full and the back-fill worked. On a **fresh**
    database — which is what CI builds every run, and what a new developer builds on day one —
    the order is inverted: migrations run first, and `project_workflows` rows are created
    afterwards by `seed_standard()` / `seed_seah()`. So the back-fill saw nothing, returned, and
    every project came out untyped. Eight tests failed on that alone, and the messages pointed
    at a migration that had in fact behaved exactly as designed.

    The type is **derived**, not hard-coded, deliberately: it is built from the project's own
    workflows and the organization roles actually named on it, by the same rules the migration
    uses. A hard-coded literal here would be a second source of truth that drifts from
    `seed_standard()` the first time a workflow changes, and would make CI exercise a shape no
    real deployment has.
    """
    from sqlalchemy import select

    from ticketing.models.project import Project, ProjectOrganization
    from ticketing.models.project_type import ProjectType
    from ticketing.models.project_workflow import ProjectWorkflow

    ANCHOR_ROLE = "implementing_agency"

    projects = db.execute(select(Project)).scalars().all()
    for project in projects:
        if project.project_type_key:
            continue

        links = db.execute(
            select(ProjectWorkflow)
            .where(ProjectWorkflow.project_id == project.project_id)
            .order_by(ProjectWorkflow.sort_order)
        ).scalars().all()
        if not links:
            # Same rule as the migration: no workflows, no template to infer. A project in this
            # state is not something the seed should invent a type for.
            logger.info("  = no workflows for %s — skipping type", project.short_code)
            continue

        bindings = [
            {
                "display_label": l.display_label,
                "workflow_id": str(l.workflow_id),
                "is_default": bool(l.is_default),
                "classifications": list(l.classifications or []),
                "intake_route": l.intake_route,
                "sort_order": l.sort_order or 0,
            }
            for l in links
        ]

        # The roles the project actually names, plus the anchor — which is required whether or
        # not anyone has filled it yet, because that is what B1 exists to say.
        named = db.execute(
            select(ProjectOrganization.org_role).where(
                ProjectOrganization.project_id == project.project_id,
                ProjectOrganization.org_role.isnot(None),
            )
        ).scalars().all()
        keys = sorted({r for r in named if r} | {ANCHOR_ROLE})

        type_key = f"{project.short_code.lower()}_standard"
        db.add(
            ProjectType(
                type_key=type_key,
                label=f"{project.name} template",
                description=(
                    "Seeded from the workflows and organizations this project already runs — "
                    "the same derivation the back-fill migration performs on a database that "
                    "has them. Rename it when a human knows what this kind of project is called."
                ),
                standard_workflow_id=project.standard_workflow_id,
                seah_workflow_id=project.seah_workflow_id,
                routing_org_role=ANCHOR_ROLE,
                actor_roles=[
                    {
                        "key": k,
                        "label": k.replace("_", " ").capitalize(),
                        "description": "",
                        "required": k == ANCHOR_ROLE,
                        "required_package": False,
                        "scope": "project",
                    }
                    for k in keys
                ],
                workflow_bindings=bindings,
                owner_organization_id=None,
                is_active=True,
                sort_order=10,
            )
        )
        # Flush before pointing the project at it: SQLAlchemy orders the projects UPDATE ahead
        # of the project_types INSERT otherwise, and fk_projects_project_type rejects it.
        db.flush()
        project.project_type_key = type_key
        logger.info(
            "  + project type %s for %s (%d workflows, roles: %s)",
            type_key, project.short_code, len(bindings), ", ".join(keys),
        )
    db.flush()


def seed_donor_informed_defaults(db: Session) -> None:
    """Put the donor in the final step's "Kept informed" cast — the way adding a donor does.

    ⚠ **Fourth instance of the same root cause, wearing different clothes.** Here it is not a
    back-fill migration but a **service-layer side effect the seed skipped**: naming a donor on a
    project is not just a row in `project_donors`. `POST`ing one through
    `api/routers/locations.py` also calls `apply_donor_informed_defaults`, which adds the
    `donor_*` tiers to the last standard step's informed cast — because a donor who funds the
    project and is never told how a grievance ended is the failure the guardrail exists to
    prevent, and go-live blocks on it.

    The seed writes `project_donors` straight to the table, so that side effect never ran and
    `donor_informed_ok` was False on every freshly built database. It read as flaky rather than
    broken: the test that exercises `apply_donor_informed_defaults` **commits**, so once any full
    suite had run once, the database was permanently repaired and the failure vanished until the
    next fresh build.

    Calling the real service rather than writing the roles here is the point — a literal list of
    donor tiers in the seed is a second definition of "which tiers count as a donor", and it would
    be wrong the first time that list changed.
    """
    from sqlalchemy import select

    from ticketing.models.project import Project
    from ticketing.services.donor_guardrail import apply_donor_informed_defaults

    for project in db.execute(select(Project)).scalars().all():
        added = apply_donor_informed_defaults(db, project)
        if added:
            logger.info("  + donor informed cast on %s: %s", project.short_code, ", ".join(added))
    db.flush()


def _l1_package_scopes(db: Session, role_key: str) -> list[dict]:
    """One Level 1 officer per lot — because `LEVEL_1_SITE.staff_per_package` is `True`.

    ⚠ **The second half of the same staleness.** A workflow level has said whether it is staffed
    once for the project or lot by lot since 2026-08-04 (`p2r4t6v8`), and KL Road's Level 1 says
    lot by lot. Go-live check C1 gates **ticket intake**, so an unstaffed lot does not merely warn
    — `POST /api/v1/tickets` refuses with "Add a Level 1 officer for these packages: 01, 02, 03,
    04, 05". Ten tests failed on that, and none of them was about packages.

    Derived from `package_locations` rather than a hand-written lot→officer table: the officers
    are already scoped by district, the lots already declare which districts they run through, so
    the pairing is a lookup, not a decision. A hard-coded table would be wrong the first time a
    lot's alignment changed, and wrong silently.

    These rows are **additive**. The district-scoped rows stay exactly as they were, because
    `_scope_candidates` tries the package path first and falls back to the project-wide one, and
    the @integration assignment tests rank on those. Adding a package row must not take an
    officer out of the pool for a ticket that has no package.
    """
    from sqlalchemy import select

    from ticketing.models.package import PackageLocation, ProjectPackage

    # district → the L1 officers already covering it, in seed order
    by_district: dict[str, list[str]] = {}
    for user_id, loc in (
        (OFFICER_SITE_L1, LOC_MORANG_CODE),
        (OFFICER_SITE_L1_2, LOC_JHAPA_CODE),
        (OFFICER_SITE_L1_3, LOC_SUNSARI_CODE),
        (OFFICER_SITE_L1_4, LOC_MORANG_CODE),
    ):
        by_district.setdefault(loc, []).append(user_id)

    rows = db.execute(
        select(ProjectPackage.package_id, ProjectPackage.package_code, PackageLocation.location_code)
        .join(PackageLocation, PackageLocation.package_id == ProjectPackage.package_id)
        .order_by(ProjectPackage.package_code)
    ).all()

    scopes: list[dict] = []
    claimed: set[str] = set()
    for package_id, package_code, location_code in rows:
        if package_id in claimed:
            continue  # a lot spanning two districts is staffed once, by the first
        officers = by_district.get(location_code)
        if not officers:
            continue
        # Spread the lots over the officers who cover that district, so no one holds all of them.
        user_id = officers[len(claimed) % len(officers)]
        claimed.add(package_id)
        scopes.append(
            dict(
                user_id=user_id,
                role_key=role_key,
                organization_id=ORG_DOR_ID,
                location_code=location_code,
                project_code="KL_ROAD",
                package_id=package_id,
                includes_children=True,
            )
        )
        logger.info("  + L1 lot %s → %s (%s)", package_code, user_id, location_code)

    uncovered = {r[1] for r in rows} - {r[1] for r in rows if r[0] in claimed}
    if uncovered:
        # Loud, because a silently unstaffed lot is exactly the failure this function exists to
        # prevent, and it presents as an unrelated intake error much later.
        logger.warning(
            "  ! no Level 1 officer for lot(s) %s — ticket intake will refuse them",
            ", ".join(sorted(uncovered)),
        )
    return scopes


def seed_mock_officer_scopes(db: Session) -> None:
    """
    Seed OfficerScope rows so auto_assign_officer() can match live tickets.

    Each row = "officer X acts as role Y for tickets in (org, location, project)".
    Uses project_code (string) which is what _scope_candidates() queries.

    includes_children=True: officer covers the scoped location AND all its
    descendant locations (e.g. province → districts → municipalities).
    """
    from sqlalchemy import select

    def STD(step_key: str, tier: str) -> str:
        from ticketing.seed.kl_road_standard import _slot

        return _slot(step_key, tier)

    def SEAH(step_key: str, tier: str) -> str:
        from ticketing.seed.kl_road_seah import _slot as seah_slot

        return seah_slot(step_key, tier)

    scopes = [
        # Project admin: KL Road project setup (province-wide)
        dict(user_id=OFFICER_PROJECT_ADMIN, role_key="project_admin",
             organization_id=ORG_DOR_ID, location_code=LOC_PROVINCE1_CODE,
             project_code="KL_ROAD", includes_children=True),

        # L1 site officers — one primary district each (+ L1-4 also Morang for load balance)
        dict(user_id=OFFICER_SITE_L1, role_key=STD("LEVEL_1_SITE", "actor"),
             organization_id=ORG_DOR_ID, location_code=LOC_MORANG_CODE,
             project_code="KL_ROAD", includes_children=True),
        dict(user_id=OFFICER_SITE_L1_2, role_key=STD("LEVEL_1_SITE", "actor"),
             organization_id=ORG_DOR_ID, location_code=LOC_JHAPA_CODE,
             project_code="KL_ROAD", includes_children=True),
        dict(user_id=OFFICER_SITE_L1_3, role_key=STD("LEVEL_1_SITE", "actor"),
             organization_id=ORG_DOR_ID, location_code=LOC_SUNSARI_CODE,
             project_code="KL_ROAD", includes_children=True),
        dict(user_id=OFFICER_SITE_L1_4, role_key=STD("LEVEL_1_SITE", "actor"),
             organization_id=ORG_DOR_ID, location_code=LOC_MORANG_CODE,
             project_code="KL_ROAD", includes_children=True),

        # L2 PIU: Province 1 + all children (three officers for load balancing)
        # PIU focals hold two jobs: supervisor of L1 and actor of L2. Under one shared key that
        # was a single row and an ambiguity; per-slot keys make it two honest rows.
        dict(user_id=OFFICER_PIU_L2, role_key=STD("LEVEL_1_SITE", "supervisor"),
             organization_id=ORG_DOR_ID, location_code=LOC_PROVINCE1_CODE,
             project_code="KL_ROAD", includes_children=True),
        dict(user_id=OFFICER_PIU_L2_2, role_key=STD("LEVEL_1_SITE", "supervisor"),
             organization_id=ORG_DOR_ID, location_code=LOC_PROVINCE1_CODE,
             project_code="KL_ROAD", includes_children=True),
        dict(user_id=OFFICER_PIU_L2_3, role_key=STD("LEVEL_1_SITE", "supervisor"),
             organization_id=ORG_DOR_ID, location_code=LOC_PROVINCE1_CODE,
             project_code="KL_ROAD", includes_children=True),
        # …and the same three as actors of L2, the level they own.
        dict(user_id=OFFICER_PIU_L2, role_key=STD("LEVEL_2_PIU", "actor"),
             organization_id=ORG_DOR_ID, location_code=LOC_PROVINCE1_CODE,
             project_code="KL_ROAD", includes_children=True),
        dict(user_id=OFFICER_PIU_L2_2, role_key=STD("LEVEL_2_PIU", "actor"),
             organization_id=ORG_DOR_ID, location_code=LOC_PROVINCE1_CODE,
             project_code="KL_ROAD", includes_children=True),
        dict(user_id=OFFICER_PIU_L2_3, role_key=STD("LEVEL_2_PIU", "actor"),
             organization_id=ORG_DOR_ID, location_code=LOC_PROVINCE1_CODE,
             project_code="KL_ROAD", includes_children=True),

        # GRC chair: Province 1 level
        dict(user_id=OFFICER_GRC_CHAIR, role_key=STD("LEVEL_3_GRC", "actor"),
             organization_id=ORG_DOR_ID, location_code=LOC_PROVINCE1_CODE,
             project_code="KL_ROAD", includes_children=True),

        # GRC members: Province 1 level
        dict(user_id=OFFICER_GRC_MEMBER_1, role_key=STD("LEVEL_3_GRC", "informed"),
             organization_id=ORG_DOR_ID, location_code=LOC_PROVINCE1_CODE,
             project_code="KL_ROAD", includes_children=True),
        dict(user_id=OFFICER_GRC_MEMBER_2, role_key=STD("LEVEL_3_GRC", "informed"),
             organization_id=ORG_DOR_ID, location_code=LOC_PROVINCE1_CODE,
             project_code="KL_ROAD", includes_children=True),

        # SEAH national: Province 1 + all children (covers Sunsari etc.)
        dict(user_id=OFFICER_SEAH_NATIONAL, role_key=SEAH("SEAH_LEVEL_1_NATIONAL", "actor"),
             organization_id=ORG_DOR_ID, location_code=LOC_PROVINCE1_CODE,
             project_code="KL_ROAD", includes_children=True),

        # SEAH HQ: no location = sees all DOR SEAH tickets across KL_ROAD
        # (organization_id=DOR because all tickets are owned by DOR, the executing agency)
        dict(user_id=OFFICER_SEAH_HQ, role_key=SEAH("SEAH_LEVEL_1_NATIONAL", "supervisor"),
             organization_id=ORG_DOR_ID, location_code=None,
             project_code="KL_ROAD", includes_children=False),
        dict(user_id=OFFICER_SEAH_HQ, role_key=SEAH("SEAH_LEVEL_2_HQ", "actor"),
             organization_id=ORG_DOR_ID, location_code=None,
             project_code="KL_ROAD", includes_children=False),

        # ADB observer: no location = observes all DOR standard tickets
        # (organization_id=DOR because tickets belong to the executing agency, not the donor)
        dict(user_id=OFFICER_ADB, role_key=STD("LEVEL_3_GRC", "supervisor"),
             organization_id=ORG_DOR_ID, location_code=None,
             project_code="KL_ROAD", includes_children=False),
        dict(user_id=OFFICER_ADB, role_key=STD("LEVEL_4_LEGAL", "actor"),
             organization_id=ORG_DOR_ID, location_code=None,
             project_code="KL_ROAD", includes_children=False),

        # Super admin: no location, no project = global scope
        dict(user_id=OFFICER_ADMIN, role_key="super_admin",
             organization_id=ORG_DOR_ID, location_code=None,
             project_code=None, includes_children=False),
    ]

    # Level 1 is staffed lot by lot, so the district rows above are not the whole answer —
    # see _l1_package_scopes for why intake refuses without these.
    scopes += _l1_package_scopes(db, STD("LEVEL_1_SITE", "actor"))

    for s in scopes:
        existing = db.execute(
            select(OfficerScope).where(
                OfficerScope.user_id        == s["user_id"],
                OfficerScope.role_key       == s["role_key"],
                OfficerScope.organization_id == s["organization_id"],
                OfficerScope.location_code  == s["location_code"],
                OfficerScope.project_code   == s["project_code"],
                # Without this, a lot-scoped row looks identical to the district-scoped row it
                # sits beside and would never be created — the seeder would report success and
                # leave intake blocked.
                OfficerScope.package_id     == s.get("package_id"),
            )
        ).scalar_one_or_none()
        if not existing:
            db.add(OfficerScope(**s))
            logger.info("  + scope: %s → %s @ %s / %s / %s",
                        s["user_id"], s["role_key"], s["organization_id"],
                        s["location_code"], s["project_code"])
        else:
            logger.info("  = scope already exists: %s → %s", s["user_id"], s["role_key"])
    db.flush()


def _make_ticket(
    grievance_id: str,
    workflow_id: str,
    step_id: str | None,
    is_seah: bool,
    status_code: str,
    priority: str,
    location_code: str,
    project_code: str,
    summary: str,
    categories: str,
    grievance_location: str,
    assigned_to: str | None,
    created_days_ago: int,
    sla_breached: bool = False,
    complainant_id: str | None = None,
    session_id: str | None = None,
) -> Ticket:
    created_at = _ago(days=created_days_ago)
    return Ticket(
        ticket_id=_id(),
        grievance_id=grievance_id,
        complainant_id=complainant_id,
        session_id=session_id,
        chatbot_id="nepal_grievance_bot",
        grievance_summary=summary,
        grievance_categories=categories,
        grievance_location=grievance_location,
        country_code="NP",
        organization_id=ORG_DOR_ID,
        location_code=location_code,
        project_code=project_code,
        status_code=status_code,
        current_workflow_id=workflow_id,
        current_step_id=step_id,
        priority=priority,
        is_seah=is_seah,
        assigned_to_user_id=assigned_to,
        sla_breached=sla_breached,
        is_deleted=False,
        step_started_at=_ago(days=created_days_ago - 1),
        created_at=created_at,
        updated_at=created_at,
    )


def _event(
    ticket: Ticket,
    event_type: str,
    days_ago: int,
    note: str | None = None,
    old_status: str | None = None,
    new_status: str | None = None,
    step_id: str | None = None,
    old_assigned: str | None = None,
    new_assigned: str | None = None,
    created_by: str | None = None,
    seen: bool = True,
    notify_user_id: str | None = None,
) -> TicketEvent:
    ts = _ago(days=days_ago)
    return TicketEvent(
        event_id=_id(),
        ticket_id=ticket.ticket_id,
        event_type=event_type,
        old_status_code=old_status,
        new_status_code=new_status,
        old_assigned_to=old_assigned,
        new_assigned_to=new_assigned,
        workflow_step_id=step_id,
        note=note,
        payload=None,
        seen=seen,
        assigned_to_user_id=notify_user_id,
        created_by_user_id=created_by,
        created_at=ts,
    )


def seed_mock_tickets(db: Session) -> None:
    """
    Seed demo scenario tickets.

    Scenario 1: Dust / health complaint — currently at L3 (GRC)
    Scenario 2: SEAH harassment — currently at L1 investigation
    Plus 5 supporting tickets at various stages for a realistic queue.
    """

    # ── Scenario 1: Dust / health complaint (at GRC, L3) ─────────────────────
    t_dust = _make_ticket(
        grievance_id="GRV-2025-001",
        workflow_id=WORKFLOW_STANDARD_ID,
        step_id=STEP_L3_ID,
        is_seah=False,
        status_code="IN_PROGRESS",  # GRC chair has acknowledged (last event); ready for CONVENE
        priority="HIGH",
        location_code=LOC_MORANG_CODE,
        project_code="KL_ROAD",
        summary="Dust from road construction is entering homes, children are falling sick. Contractor has not implemented any dust suppression measures despite multiple complaints.",
        categories="Environmental Impact, Health and Safety",
        grievance_location="Urlabari, Morang District, Province 1",
        assigned_to=OFFICER_GRC_CHAIR,
        created_days_ago=14,
        sla_breached=False,
        complainant_id="CPL-2025-001",
        session_id="session-demo-dust-001",
    )
    db.add(t_dust)

    dust_events = [
        _event(t_dust, "CREATED", 14, new_status="OPEN", step_id=STEP_L1_ID,
               created_by="system", note="Ticket created from grievance GRV-2025-001"),
        _event(t_dust, "ASSIGNED", 14, new_assigned=OFFICER_SITE_L1, step_id=STEP_L1_ID,
               created_by=OFFICER_ADMIN, notify_user_id=OFFICER_SITE_L1, seen=False),
        _event(t_dust, "ACKNOWLEDGED", 13, old_status="OPEN", new_status="IN_PROGRESS",
               step_id=STEP_L1_ID, created_by=OFFICER_SITE_L1,
               note="Visited site. Confirmed dust issue. Notified contractor CSC."),
        _event(t_dust, "ESCALATED", 11, old_status="IN_PROGRESS", new_status="ESCALATED",
               step_id=STEP_L2_ID, created_by=OFFICER_SITE_L1,
               note="Contractor failed to act after 2 days. Auto-escalated to L2 PD/PIU.",
               notify_user_id=OFFICER_PIU_L2, seen=False),
        _event(t_dust, "ACKNOWLEDGED", 10, old_status="ESCALATED", new_status="IN_PROGRESS",
               step_id=STEP_L2_ID, created_by=OFFICER_PIU_L2,
               note="Reviewing L1 findings. Meeting with contractor scheduled."),
        _event(t_dust, "ESCALATED", 7, old_status="IN_PROGRESS", new_status="ESCALATED",
               step_id=STEP_L3_ID, created_by=OFFICER_PIU_L2,
               note="Contractor disputes findings. Contractor-PIU disagreement unresolved after 7 days. Escalating to GRC.",
               notify_user_id=OFFICER_GRC_CHAIR, seen=False),
        _event(t_dust, "ACKNOWLEDGED", 6, old_status="ESCALATED", new_status="IN_PROGRESS",
               step_id=STEP_L3_ID, created_by=OFFICER_GRC_CHAIR,
               note="GRC hearing convened for May 3. All GRC members notified.",
               notify_user_id=OFFICER_GRC_MEMBER_1, seen=False),
        _event(t_dust, "NOTE_ADDED", 3, step_id=STEP_L3_ID, created_by=OFFICER_GRC_MEMBER_1,
               note="Technical assessment confirms dust levels exceed WHO guidelines. Wet-spray twice daily would suffice."),
    ]
    for e in dust_events:
        db.add(e)

    # ── Scenario 2: SEAH harassment (at L1, investigation) ───────────────────
    t_seah = _make_ticket(
        grievance_id="GRV-2025-SEAH-001",
        workflow_id=WORKFLOW_SEAH_ID,
        step_id=STEP_SEAH_L1_ID,
        is_seah=True,
        status_code="IN_PROGRESS",
        priority="HIGH",
        location_code=LOC_SUNSARI_CODE,
        project_code="KL_ROAD",
        summary="Complainant reports verbal harassment and inappropriate physical contact by a construction worker at the road site.",
        categories="SEAH – Harassment",
        grievance_location="Inaruwa, Sunsari District, Province 1",
        assigned_to=OFFICER_SEAH_NATIONAL,
        created_days_ago=5,
        sla_breached=False,
        complainant_id="CPL-2025-SEAH-001",
        session_id="session-demo-seah-001",
    )
    db.add(t_seah)

    seah_events = [
        _event(t_seah, "CREATED", 5, new_status="OPEN", step_id=STEP_SEAH_L1_ID,
               created_by="system", note="SEAH ticket created — restricted access"),
        _event(t_seah, "ASSIGNED", 5, new_assigned=OFFICER_SEAH_NATIONAL,
               step_id=STEP_SEAH_L1_ID, created_by=OFFICER_ADMIN,
               notify_user_id=OFFICER_SEAH_NATIONAL, seen=False),
        _event(t_seah, "ACKNOWLEDGED", 4, old_status="OPEN", new_status="IN_PROGRESS",
               step_id=STEP_SEAH_L1_ID, created_by=OFFICER_SEAH_NATIONAL,
               note="Contacted complainant confidentially. Safe accommodation arranged. Investigation opened."),
        _event(t_seah, "NOTE_ADDED", 3, step_id=STEP_SEAH_L1_ID, created_by=OFFICER_SEAH_NATIONAL,
               note="Worker identified from site roster. Supervisor interviewed. Incident corroborated by witness."),
        _event(t_seah, "NOTE_ADDED", 2, step_id=STEP_SEAH_L1_ID, created_by=OFFICER_SEAH_NATIONAL,
               note="Complainant requests formal police referral. Escalating to SEAH HQ for authorization."),
    ]
    for e in seah_events:
        db.add(e)

    # ── Supporting tickets: realistic queue ───────────────────────────────────

    # T3: L1 new, unacknowledged (shows red NEW badge)
    # Location = Morang district (P1_MOR) — within Site L1's scope
    t3 = _make_ticket(
        grievance_id="GRV-2025-003",
        workflow_id=WORKFLOW_STANDARD_ID,
        step_id=STEP_L1_ID,
        is_seah=False,
        status_code="OPEN",
        priority="NORMAL",
        location_code=LOC_MORANG_CODE,
        project_code="KL_ROAD",
        summary="Road widening has damaged boundary wall of residential property. Owner requesting compensation.",
        categories="Property Damage, Compensation",
        grievance_location="Biratnagar, Morang District, Province 1",
        assigned_to=OFFICER_SITE_L1,
        created_days_ago=1,
        complainant_id="CPL-2025-003",
    )
    db.add(t3)
    db.add(_event(t3, "CREATED", 1, new_status="OPEN", step_id=STEP_L1_ID, created_by="system"))
    db.add(_event(t3, "ASSIGNED", 1, new_assigned=OFFICER_SITE_L1, step_id=STEP_L1_ID,
                  notify_user_id=OFFICER_SITE_L1, seen=False))

    # T4: escalated to L2 — waiting for PIU acknowledgment (shows Escalated tab + badge)
    t4 = _make_ticket(
        grievance_id="GRV-2025-004",
        workflow_id=WORKFLOW_STANDARD_ID,
        step_id=STEP_L2_ID,
        is_seah=False,
        status_code="ESCALATED",  # Awaiting PIU L2 acknowledgment
        priority="HIGH",
        location_code=LOC_MORANG_CODE,
        project_code="KL_ROAD",
        summary="Blasting noise during nighttime hours is disturbing village residents and livestock. Contractor violating project environmental covenants.",
        categories="Environmental Impact, Noise Pollution",
        grievance_location="Biratnagar outskirts, Morang District",
        assigned_to=OFFICER_PIU_L2,
        created_days_ago=8,
        sla_breached=False,
        complainant_id="CPL-2025-004",
    )
    db.add(t4)
    db.add(_event(t4, "CREATED", 8, new_status="OPEN", step_id=STEP_L1_ID, created_by="system"))
    db.add(_event(t4, "ACKNOWLEDGED", 7, old_status="OPEN", new_status="IN_PROGRESS",
                  step_id=STEP_L1_ID, created_by=OFFICER_SITE_L1,
                  note="Conducted site inspection. Night blasting confirmed. Escalating to PIU."))
    db.add(_event(t4, "ESCALATED", 5, old_status="IN_PROGRESS", new_status="ESCALATED",
                  step_id=STEP_L2_ID, created_by=OFFICER_SITE_L1,
                  notify_user_id=OFFICER_PIU_L2, seen=False))

    # T5: Resolved (shows historical view)
    t5 = _make_ticket(
        grievance_id="GRV-2025-002",
        workflow_id=WORKFLOW_STANDARD_ID,
        step_id=STEP_L1_ID,
        is_seah=False,
        status_code="RESOLVED",
        priority="NORMAL",
        location_code=LOC_SUNSARI_CODE,
        project_code="KL_ROAD",
        summary="Access road to farm blocked by construction material stockpile for 3 days.",
        categories="Access Disruption",
        grievance_location="Dharan, Sunsari District, Province 1",
        assigned_to=OFFICER_SITE_L1,
        created_days_ago=20,
        complainant_id="CPL-2025-002",
    )
    db.add(t5)
    db.add(_event(t5, "CREATED", 20, new_status="OPEN", created_by="system"))
    db.add(_event(t5, "ACKNOWLEDGED", 19, old_status="OPEN", new_status="IN_PROGRESS",
                  created_by=OFFICER_SITE_L1))
    db.add(_event(t5, "RESOLVED", 17, old_status="IN_PROGRESS", new_status="RESOLVED",
                  created_by=OFFICER_SITE_L1,
                  note="Contractor removed stockpile within 24 hours. Complainant confirmed access restored."))

    # T6: SLA breached at L1 — shows overdue indicator
    # Location = Morang district (P1_MOR) — within Site L1's scope and appears in their queue
    t6 = _make_ticket(
        grievance_id="GRV-2025-005",
        workflow_id=WORKFLOW_STANDARD_ID,
        step_id=STEP_L1_ID,
        is_seah=False,
        status_code="OPEN",
        priority="NORMAL",
        location_code=LOC_MORANG_CODE,
        project_code="KL_ROAD",
        summary="Culvert installation is blocking irrigation channel serving 12 farms. Crops at risk.",
        categories="Agricultural Impact, Water Access",
        grievance_location="Urlabari, Morang District, Province 1",
        assigned_to=OFFICER_SITE_L1,
        created_days_ago=4,
        sla_breached=True,  # SLA of 2 days breached
        complainant_id="CPL-2025-005",
    )
    db.add(t6)
    db.add(_event(t6, "CREATED", 4, new_status="OPEN", step_id=STEP_L1_ID, created_by="system"))
    db.add(_event(t6, "ASSIGNED", 4, new_assigned=OFFICER_SITE_L1,
                  notify_user_id=OFFICER_SITE_L1, seen=False))

    db.flush()
    logger.info("  + scenario 1 (dust): GRV-2025-001 at L3 GRC")
    logger.info("  + scenario 2 (SEAH): GRV-2025-SEAH-001 at L1 investigation")
    logger.info("  + supporting tickets: GRV-2025-002 through GRV-2025-005")


def seed_default_settings(db: Session) -> None:
    """Upsert default settings rows (safe to run multiple times)."""
    from ticketing.models.settings import Settings

    ORG_ROLES = [
        {"key": "project_owner",         "label": "Project Owner",                          "description": "Government agency that owns and executes the project (e.g. DOR)"},
        {"key": "donor",                  "label": "Donor / Lender",                         "description": "Multilateral or bilateral financing institution (e.g. ADB)"},
        {"key": "executing_agency",       "label": "Executing Agency",                       "description": "Central ministry or agency responsible for project oversight"},
        {"key": "implementing_agency",    "label": "Implementing Agency",                    "description": "PD/PIU or other unit responsible for day-to-day implementation"},
        {"key": "main_contractor",        "label": "Main Contractor",                        "description": "Primary civil works contractor"},
        {"key": "subcontractor_t1",       "label": "Subcontractor (Tier 1)",                 "description": "First-tier subcontractor to the main contractor"},
        {"key": "subcontractor_t2",       "label": "Subcontractor (Tier 2)",                 "description": "Second-tier subcontractor"},
        {"key": "supervision_consultant", "label": "CSC – Construction Supervision Consultant", "description": "Independent consultant supervising construction quality"},
        {"key": "specialized_consultant", "label": "Specialized Consultant",                 "description": "Safeguards, environment, social, or other specialist consultant"},
    ]

    existing = db.get(Settings, "org_roles")
    if existing is None:
        db.add(Settings(key="org_roles", value=ORG_ROLES))
        logger.info("Seeded org_roles setting (%d roles)", len(ORG_ROLES))
    else:
        existing.value = ORG_ROLES
        logger.info("Updated org_roles setting (%d roles)", len(ORG_ROLES))

    from ticketing.services.grievance_categories_catalog import SETTING_KEY, load_default_catalog

    existing_categories = db.get(Settings, SETTING_KEY)
    if existing_categories is None:
        catalog = load_default_catalog()
        db.add(Settings(key=SETTING_KEY, value=catalog))
        logger.info(
            "Seeded grievance_categories setting (%d categories)",
            len(catalog["categories"]),
        )


def seed_all(reset: bool = False) -> None:
    """Full seed: workflows + officers + mock tickets."""
    db = SessionLocal()
    try:
        if reset:
            logger.info("Reset mode: truncating transactional data (structural data preserved)...")
            # Wipe only the *transactional / assignment* data that accumulates and is
            # re-seeded (tickets + their children via CASCADE, officer/admin scopes, roster
            # roles, officer positions). PRESERVE all STRUCTURAL data — workflows, projects,
            # packages, project_workflows, organizations, roles, position_types — plus the
            # imported geodata: the seeders upsert those idempotently, and several are
            # *migration-seeded* (packages, project_workflows) with no seeder to re-create
            # them, so a blanket TRUNCATE would leave them permanently empty. CASCADE covers
            # ticket child tables; RESTART IDENTITY resets sequences.
            from sqlalchemy import text as _sql_text

            transactional = [
                "tickets",           # → ticket_events / tasks / viewers / files / episodes (CASCADE)
                "officer_scopes",
                "admin_scopes",
                "user_roles",
                "officer_positions",
            ]
            db.execute(
                _sql_text(
                    "TRUNCATE TABLE "
                    + ", ".join(f"ticketing.{t}" for t in transactional)
                    + " RESTART IDENTITY CASCADE"
                )
            )
            db.commit()
            logger.info("Reset complete (transactional data wiped; structure preserved).")

        # Seed workflows (each is idempotent)
        seed_standard(db)
        seed_seah(db)

        # …then the type, which is derived from them. Order matters: the back-fill migration
        # runs before any of this exists, which is exactly why it produced nothing.
        logger.info("Seeding project workflow links...")
        seed_project_workflow_links(db)
        logger.info("Seeding project types...")
        seed_project_types(db)
        logger.info("Seeding donor informed defaults...")
        seed_donor_informed_defaults(db)

        # Seed mock officers, scopes, and tickets
        logger.info("Seeding mock officers...")
        seed_mock_officers(db)
        logger.info("Seeding admin scopes...")
        seed_admin_scopes(db)
        logger.info("Seeding mock officer scopes...")
        seed_mock_officer_scopes(db)
        logger.info("Seeding mock tickets (demo scenarios)...")
        seed_mock_tickets(db)

        # Seed default settings (idempotent — upsert)
        logger.info("Seeding default settings...")
        seed_default_settings(db)

        db.commit()
        logger.info("All seed data committed successfully.")

    except Exception:
        db.rollback()
        logger.exception("Seed FAILED — rolled back")
        raise
    finally:
        db.close()


def seed_officers_only() -> None:
    """Upsert demo officer roles + scopes without touching tickets or workflows."""
    db = SessionLocal()
    try:
        logger.info("Seeding mock officers (roles only)...")
        seed_mock_officers(db)
        logger.info("Seeding admin scopes...")
        seed_admin_scopes(db)
        logger.info("Seeding mock officer scopes...")
        seed_mock_officer_scopes(db)
        db.commit()
        logger.info("Officer seed committed successfully.")
    except Exception:
        db.rollback()
        logger.exception("Officer seed FAILED — rolled back")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if "--officers-only" in sys.argv:
        seed_officers_only()
    else:
        reset = "--reset" in sys.argv
        seed_all(reset=reset)
