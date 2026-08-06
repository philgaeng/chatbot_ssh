"""Go-live readiness checks for projects (§17 demo rules)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql.elements import ColumnElement

from ticketing.constants.assignment import COUNTRY_L1_FALLBACK_ROLE
from ticketing.services.project_routing import project_ref_match_clause
from ticketing.models.officer_scope import OfficerScope
from ticketing.models.package import PackageLocation, PackageOrganization, ProjectPackage
from ticketing.models.project import Project, ProjectOrganization
from ticketing.models.project_type import ProjectType
from ticketing.models.workflow import WorkflowDefinition, WorkflowStep
from ticketing.services.keycloak_users import list_grm_officer_profiles
from ticketing.services.officer_messaging import get_officer_messaging, role_keys_at_level
from ticketing.services.project_types import (
    get_project_type,
    package_required_role_keys,
    required_project_role_keys,
)

CheckSeverity = Literal["block", "warn", "info"]
CheckStatus = Literal["pass", "warn", "fail", "info"]
CheckGroup = Literal["routing", "commercial", "officers", "geography", "metadata"]


def _officer_scope_for_project(project: Project) -> ColumnElement:
    from ticketing.models.officer_scope import OfficerScope

    return project_ref_match_clause(
        project_id_col=OfficerScope.project_id,
        project_code_col=OfficerScope.project_code,
        project=project,
    )


@dataclass
class GoLiveCheck:
    id: str
    label: str
    group: CheckGroup
    severity: CheckSeverity
    status: CheckStatus
    message: str
    section: str | None = None


@dataclass
class GoLiveReport:
    checks: list[GoLiveCheck]
    can_activate: bool
    can_accept_tickets: bool

    @property
    def summary(self) -> dict[str, int]:
        return {
            "pass": sum(1 for c in self.checks if c.status == "pass"),
            "warn": sum(1 for c in self.checks if c.status == "warn"),
            "fail": sum(1 for c in self.checks if c.status == "fail"),
        }


def _workflow_published(db: Session, workflow_id: str | None) -> bool:
    if not workflow_id:
        return False
    wf = db.get(WorkflowDefinition, workflow_id)
    return bool(wf and wf.status == "published")


def _step_role_at_order(db: Session, workflow_id: str | None, step_order: int) -> str | None:
    if not workflow_id:
        return None
    step = db.execute(
        select(WorkflowStep)
        .where(WorkflowStep.workflow_id == workflow_id)
        .order_by(WorkflowStep.step_order)
        .offset(step_order - 1)
        .limit(1)
    ).scalar_one_or_none()
    return step.assigned_role_key if step else None


def _first_standard_step_role(db: Session, project: Project) -> str | None:
    return _step_role_at_order(db, project.standard_workflow_id, 1)


def _second_standard_step_role(db: Session, project: Project) -> str | None:
    return _step_role_at_order(db, project.standard_workflow_id, 2)


def _first_standard_step_per_package(db: Session, project: Project) -> bool:
    """Is Level 1 staffed lot by lot? The level's own answer (`staff_per_package`)."""
    if not project.standard_workflow_id:
        return False
    step = db.execute(
        select(WorkflowStep)
        .where(WorkflowStep.workflow_id == project.standard_workflow_id)
        .order_by(WorkflowStep.step_order)
        .limit(1)
    ).scalar_one_or_none()
    return bool(step and step.staff_per_package)


def _any_active_officer(db: Session, user_ids) -> bool:
    """R3 (BUILD-REVIEW M2): a level is only "covered" by an officer who can still log in —
    a soft-deactivated officer does not count toward go-live staffing (C1/C5)."""
    from ticketing.services.officer_admin import officer_is_active

    return any(officer_is_active(db, uid) for uid in set(user_ids))


def _has_officer_on_package(db: Session, *, package_id: str, grm_role_key: str) -> bool:
    uids = db.execute(
        select(OfficerScope.user_id).where(
            OfficerScope.role_key == grm_role_key,
            OfficerScope.package_id == package_id,
        )
    ).scalars().all()
    return _any_active_officer(db, uids)


def _has_officer_on_project_wide(
    db: Session,
    *,
    project: Project,
    grm_role_key: str,
) -> bool:
    uids = db.execute(
        select(OfficerScope.user_id).where(
            OfficerScope.role_key == grm_role_key,
            OfficerScope.package_id.is_(None),
            _officer_scope_for_project(project),
        )
    ).scalars().all()
    return _any_active_officer(db, uids)


def _has_project_l1_fallback(db: Session, project: Project, l1_role: str) -> bool:
    """Project-wide L1 or country fallback covers every package."""
    if _has_officer_on_project_wide(db, project=project, grm_role_key=l1_role):
        return True
    return _has_officer_on_project_wide(
        db, project=project, grm_role_key=COUNTRY_L1_FALLBACK_ROLE
    )


def _packages_missing_role(
    db: Session,
    *,
    project: Project,
    packages: list[ProjectPackage],
    grm_role_key: str,
    project_wide_covers: bool,
) -> list[str]:
    if project_wide_covers or not grm_role_key:
        return []
    gaps: list[str] = []
    for pkg in packages:
        if _has_officer_on_package(db, package_id=pkg.package_id, grm_role_key=grm_role_key):
            continue
        gaps.append(pkg.package_code or pkg.package_id[:8])
    return gaps


def _project_org_has_role(project: Project, role_key: str) -> bool:
    return any(po.org_role == role_key for po in project.organizations)


def _slot_filled(db: Session, *, project: Project, type_row: ProjectType, role_key: str) -> bool:
    """Is the type's organization slot ``role_key`` filled on this project?

    Filled values live in ``project_organizations`` (doc 13 §2). The two **legacy reads**
    cover projects set up before the catalog came back: the accountable organization was kept
    on the project row as ``implementing_agency_org_id``, and donors in ``project_donors``.
    Neither is written any more; both are still true statements about the project, and without
    them this check would have blocked every pre-existing project on activation.
    """
    _ = type_row  # the catalog is the caller's; nothing here is slot-specific any more
    if _project_org_has_role(project, role_key):
        return True
    if role_key == "implementing_agency" and project.implementing_agency_org_id:
        return True
    if role_key == "donor":
        from ticketing.services.donor_guardrail import project_donor_org_ids

        return bool(project_donor_org_ids(db, project.project_id))
    return False


def _standard_level_gaps(
    db: Session,
    *,
    project: Project,
    packages: list[ProjectPackage],
) -> list[str]:
    """Standard-workflow levels with no scoped officer (DECISION §7 staffing gate).

    **Reads the level's own answer since 2026-08-04** (`workflow_steps.staff_per_package`,
    migration `p2r4t6v8`). Before that this had to guess: it accepted a project-wide officer OR
    full per-lot coverage for every level, because nothing said which the author intended. So a
    level meant to be staffed lot by lot passed with one project-wide officer, and a project-wide
    level was never asked for lots at all — the check was green either way and told you nothing.

    Now:
      • **per-lot level** — every active lot needs its own officer. A project-wide officer does
        not satisfy it (that is the point of marking the level per lot).
      • **project-wide level** — one project-wide officer. Lots are not asked about.

    Step 1 keeps the country L1 fallback either way — it exists so intake never dead-ends.
    """
    if not project.standard_workflow_id:
        return []
    steps = list(
        db.execute(
            select(WorkflowStep)
            .where(WorkflowStep.workflow_id == project.standard_workflow_id)
            .order_by(WorkflowStep.step_order)
        ).scalars().all()
    )
    def _covered(role: str, *, is_actor_l1: bool, per_package: bool) -> bool:
        # The country L1 fallback is an emergency net for *assignment* so intake never
        # dead-ends. It is not a staffing plan, so it does not answer a level the author said
        # is staffed lot by lot — that would put us straight back to guessing.
        if is_actor_l1 and not per_package and _has_officer_on_project_wide(
            db, project=project, grm_role_key=COUNTRY_L1_FALLBACK_ROLE
        ):
            return True
        if per_package:
            # The author said this level is staffed lot by lot, so every lot must have someone.
            # A project with no lots yet cannot satisfy it — that is a real gap, not a pass.
            if not packages:
                return False
            return not _packages_missing_role(
                db,
                project=project,
                packages=packages,
                grm_role_key=role,
                project_wide_covers=False,
            )
        return _has_officer_on_project_wide(db, project=project, grm_role_key=role)

    def _job_name(step, tier: str, role: str) -> str:
        """The author's name for the job, so the gap reads like the staffing screen."""
        label = ((step.tier_labels or {}).get(tier) or {}).get("label")
        return label or role

    gaps: list[str] = []
    for step in steps:
        # The actor is always required — a level with nobody to work it is not a level.
        role = step.assigned_role_key
        per_package = bool(getattr(step, "staff_per_package", False))
        if role and not _covered(role, is_actor_l1=step.step_order == 1, per_package=per_package):
            gaps.append(f"L{step.step_order} ({_job_name(step, 'actor', role)})")

        # Plus whichever non-actor jobs the workflow author marked mandatory (doc 12 §6.2).
        # `required_tiers` defaults to [] on every existing step, so this adds no gap until
        # an author opts in.
        for tier in step.required_tiers or []:
            if tier == "supervisor":
                tier_roles = [step.supervisor_role] if step.supervisor_role else []
            elif tier == "informed":
                tier_roles = list(step.informed_roles or [])
            elif tier == "observer":
                tier_roles = list(step.observer_roles or [])
            else:
                continue
            if not tier_roles:
                # Marked mandatory but no role bound — the workflow, not the project, is wrong.
                gaps.append(f"L{step.step_order} ({tier}: no role on the workflow)")
                continue
            if not any(_covered(r, is_actor_l1=False, per_package=per_package) for r in tier_roles):
                gaps.append(f"L{step.step_order} ({_job_name(step, tier, tier_roles[0])})")
    return gaps


def _package_has_role(db: Session, package_id: str, role_key: str) -> bool:
    row = db.execute(
        select(PackageOrganization.organization_id).where(
            PackageOrganization.package_id == package_id,
            PackageOrganization.org_role == role_key,
        ).limit(1)
    ).scalar_one_or_none()
    return row is not None


def evaluate_go_live(db: Session, project_id: str) -> GoLiveReport:
    project = db.execute(
        select(Project)
        .options(
            selectinload(Project.organizations),
            selectinload(Project.locations),
        )
        .where(Project.project_id == project_id)
    ).scalar_one_or_none()
    if not project:
        raise ValueError("Project not found")

    pt = get_project_type(db, project.project_type_key) if project.project_type_key else None
    checks: list[GoLiveCheck] = []

    from ticketing.services.project_workflows import list_project_workflows

    bindings = list_project_workflows(db, project_id)
    default_binding = next((b for b in bindings if b.is_default), None)
    a1_ok = bool(
        default_binding and _workflow_published(db, default_binding.workflow_id)
    )
    checks.append(
        GoLiveCheck(
            id="A1",
            label="Default workflow",
            group="routing",
            severity="block",
            status="pass" if a1_ok else "fail",
            message="Chosen"
            if a1_ok
            else "None chosen yet. The default is used when nothing else matches.",
            section="workflows",
        )
    )

    # A2 ("SEAH workflow configured") removed 2026-08-02 — DECISION-sensitive-workflows §1.3:
    # a sensitive workflow is optional, so its absence is not a finding. When a project does
    # link one, its levels are staffed like any other workflow's (A4 / C5).

    # "Classification coverage" (was also id="A4", colliding with doc 13 §7's A4 = required cast
    # tiers) removed 2026-08-02. A category no workflow claims goes to the **default** — that is
    # the default's whole job (doc 13 §5B.2) — so an uncovered category was never a finding, only
    # noise on every project that doesn't enumerate the whole catalog.

    # A3 (implementing agency set) and A5 (donor kept informed at the last level) were DELETED
    # 2026-08-04 — DECISION-author-defined-slots §7. Both hardcoded two organizations the
    # platform happened to know about; B1 below asks the same question in the author's own
    # words, for whatever organizations *their* type names. The donor guardrail is expressible
    # as the author marking that slot required and putting the role in the last level's
    # kept-informed job, which C5 then enforces (§4).
    #
    # B1 is a **blocker** and its catalog is the type's, so deleting A3/A5 does not open a gap:
    # a project cannot activate without the organizations its own type says it needs.
    if pt:
        required = required_project_role_keys(pt)
        labels = {
            str(e.get("key")): (e.get("label") or e.get("key"))
            for e in (pt.actor_roles or [])
            if e.get("key")
        }
        missing = [
            str(labels.get(k, k))
            for k in sorted(required)
            if not _slot_filled(db, project=project, type_row=pt, role_key=k)
        ]
        b1_ok = not missing
        checks.append(
            GoLiveCheck(
                id="B1",
                label="Partner organizations",
                group="commercial",
                severity="block",
                status="pass" if b1_ok else "fail",
                message="Every organization this project needs is named"
                if b1_ok
                else f"Name the organization for: {', '.join(missing)}",
                section="actors",
            )
        )
    else:
        # A legacy project created before types existed. Nothing names the organizations it
        # needs, so there is nothing to check — say so rather than pass silently. New projects
        # always have a type (POST /projects requires one).
        checks.append(
            GoLiveCheck(
                id="B1",
                label="Partner organizations",
                group="commercial",
                severity="info",
                status="info",
                message="This project has no type, so no organizations are required.",
                section="actors",
            )
        )

    packages = list(
        db.execute(
            select(ProjectPackage).where(
                ProjectPackage.project_id == project_id,
                ProjectPackage.is_active.is_(True),
            )
        ).scalars().all()
    )

    # B2 Package locations
    if packages:
        from sqlalchemy import func as sqlfunc

        missing_locs = []
        for pkg in packages:
            cnt = db.scalar(
                select(sqlfunc.count())
                .select_from(PackageLocation)
                .where(PackageLocation.package_id == pkg.package_id)
            ) or 0
            if cnt == 0:
                missing_locs.append(pkg.package_code or pkg.package_id[:8])
        b2_ok = not missing_locs
        checks.append(
            GoLiveCheck(
                id="B2",
                label="Package locations",
                group="commercial",
                severity="info",
                status="pass" if b2_ok else "warn",
                message="Every active package has locations"
                if b2_ok
                else f"No locations on: {', '.join(missing_locs)}",
                section="packages",
            )
        )

    # B3 Package required actors
    if pt and packages:
        pkg_roles = package_required_role_keys(pt)
        if pkg_roles:
            gaps = []
            for pkg in packages:
                for rk in pkg_roles:
                    if _package_has_role(db, pkg.package_id, rk):
                        continue
                    if _project_org_has_role(project, rk):
                        continue
                    gaps.append(f"{pkg.package_code or 'pkg'}:{rk}")
            b3_ok = not gaps
            checks.append(
                GoLiveCheck(
                    id="B3",
                    label="Package actors",
                    group="commercial",
                    severity="info",
                    status="pass" if b3_ok else "warn",
                    message="Package contractor roles covered"
                    if b3_ok
                    else f"Missing: {', '.join(gaps[:5])}",
                    section="packages",
                )
            )

    # C1 Level 1 staffed — and it also gates ticket intake, so it must agree with C5 exactly.
    # Which shape it asks for comes from the level itself (`staff_per_package`, 2026-08-04): per
    # lot ⇒ every active lot needs an officer; project-wide ⇒ one project-wide officer. The
    # country L1 fallback satisfies either, because it exists so intake never dead-ends.
    l1_role = _first_standard_step_role(db, project)
    l1_per_package = _first_standard_step_per_package(db, project)
    if l1_per_package:
        # Every active lot needs its own Level 1 officer, and a project with no lots at all
        # cannot satisfy a per-lot level.
        l1_gaps = _packages_missing_role(
            db,
            project=project,
            packages=packages,
            grm_role_key=l1_role or "",
            project_wide_covers=False,
        )
        c1_ok = bool(l1_role) and bool(packages) and not l1_gaps
    else:
        l1_gaps = []
        c1_ok = bool(l1_role) and _has_project_l1_fallback(db, project, l1_role)
    checks.append(
        GoLiveCheck(
            id="C1",
            label="Level 1 officers",
            group="officers",
            severity="block",
            status="pass" if c1_ok else ("fail" if l1_role else "warn"),
            message=(
                ("Every lot has a Level 1 officer" if l1_per_package else "Level 1 officer assigned")
                if c1_ok
                else (
                    f"Add a Level 1 officer ({l1_role}) for these lots: {', '.join(l1_gaps[:5])}"
                    if l1_gaps
                    else "This level is staffed for each lot — add a lot first"
                    if l1_role and l1_per_package and not packages
                    else f"Add a Level 1 officer ({l1_role})"
                    if l1_role
                    else "Add a workflow with a Level 1 to this project"
                )
            ),
            section="staffing",
        )
    )

    # C2 L2 officer per package (or project-wide) — warn; also used as assign fallback
    l2_role = _second_standard_step_role(db, project)
    l2_project_wide = bool(l2_role and _has_officer_on_project_wide(db, project=project, grm_role_key=l2_role))
    l2_gaps = _packages_missing_role(
        db,
        project=project,
        packages=packages,
        grm_role_key=l2_role or "",
        project_wide_covers=l2_project_wide,
    )
    c2_ok = bool(l2_role) and not l2_gaps
    checks.append(
        GoLiveCheck(
            id="C2",
            label="Level 2 officers",
            group="officers",
            severity="info",
            status="pass" if c2_ok else ("warn" if l2_role else "info"),
            message=(
                "Every lot has a Level 2 officer"
                if c2_ok
                else (
                    f"Add a Level 2 officer ({l2_role}) for these lots: {', '.join(l2_gaps[:5])}"
                    if l2_gaps
                    else "Add a workflow with a Level 2 to this project"
                )
            ),
            section="staffing",
        )
    )

    # R1 Reassignment authority (block; DESIGN-cast-model §3.4). Every standard step must
    # resolve to a reassignment authority so a bounced ticket never dead-ends — the chain is
    # Dispatcher → Supervisor → Actor self-serve → project_admin (guaranteed backstop). This
    # fails only when the project has no project_admin and no staffed Supervisor/Dispatcher.
    from ticketing.services.reassignment import step_has_reachable_reassigner

    r1_gaps: list[str] = []
    if project.standard_workflow_id:
        r1_steps = db.execute(
            select(WorkflowStep)
            .where(
                WorkflowStep.workflow_id == project.standard_workflow_id,
                WorkflowStep.is_deleted.is_(False),
            )
            .order_by(WorkflowStep.step_order)
        ).scalars().all()
        for st in r1_steps:
            if not step_has_reachable_reassigner(db, project=project, step=st):
                r1_gaps.append(st.display_name or st.step_key)
    r1_ok = not r1_gaps
    checks.append(
        GoLiveCheck(
            id="R1",
            label="Someone to reassign to",
            group="officers",
            severity="block",
            status="pass" if r1_ok else "fail",
            message=(
                "Every level has someone who can reassign a grievance"
                if r1_ok
                else (
                    "No one can reassign at: "
                    + ", ".join(r1_gaps[:5])
                    + " — staff a supervisor, or add a project administrator"
                )
            ),
            section="staffing",
        )
    )

    # C4 SEAH L1 (when seah workflow set)
    if project.seah_workflow_id:
        seah_l1 = _step_role_at_order(db, project.seah_workflow_id, 1)
        c4_ok = False
        if seah_l1:
            c4_ok = (
                db.execute(
                    select(OfficerScope.user_id)
                    .where(
                        OfficerScope.role_key == seah_l1,
                        _officer_scope_for_project(project),
                    )
                    .limit(1)
                ).scalar_one_or_none()
                is not None
            )
        checks.append(
            GoLiveCheck(
                id="C4",
                label="Sensitive workflow staffing",
                group="officers",
                severity="block",
                status="pass" if c4_ok else "fail",
                message="Level 1 officer assigned" if c4_ok else "Assign a Level 1 officer for this project",
                section="staffing",
            )
        )

    # C5 Every standard workflow level is staffed (block; DECISION §7). Stricter than
    # C1/C2 (which cover L1/L2 only) — go-live blocks if any escalation level has no
    # officer who could handle a ticket parked there.
    level_gaps = _standard_level_gaps(db, project=project, packages=packages)
    if project.standard_workflow_id:
        c5_ok = not level_gaps
        checks.append(
            GoLiveCheck(
                id="C5",
                label="All levels staffed",
                group="officers",
                severity="block",
                status="pass" if c5_ok else "fail",
                message=(
                    "Every level has an officer"
                    if c5_ok
                    else f"No officer at: {', '.join(level_gaps[:5])}"
                ),
                section="staffing",
            )
        )

    # D1 Project locations
    d1_ok = len(project.locations) > 0
    checks.append(
        GoLiveCheck(
            id="D1",
            label="Project locations",
            group="geography",
            severity="block",
            status="pass" if d1_ok else "fail",
            message="At least one location linked" if d1_ok else "Link the provinces, districts or municipalities this project covers",
            section="locations",
        )
    )

    # D2 QR tokens
    if packages:
        from ticketing.models.qr_token import QrToken
        missing_qr = []
        for pkg in packages:
            has_qr = db.execute(
                select(QrToken.token).where(QrToken.package_id == pkg.package_id).limit(1)
            ).scalar_one_or_none()
            if not has_qr:
                missing_qr.append(pkg.package_code or pkg.package_id[:8])
        checks.append(
            GoLiveCheck(
                id="D2",
                label="Package QR tokens",
                group="geography",
                severity="info",
                status="pass" if not missing_qr else "info",
                message="All packages have QR tokens"
                if not missing_qr
                else f"Optional: add QR for {', '.join(missing_qr[:5])}",
                section="packages",
            )
        )

    # F1 Officer SMS phone coverage (warn only)
    messaging = get_officer_messaging(db, project_id)
    f1_gaps: list[str] = []
    if messaging.sms_enabled and messaging.sms_levels:
        profiles = list_grm_officer_profiles()
        for level in sorted(messaging.sms_levels):
            role_keys = role_keys_at_level(db, project_id, level)
            if not role_keys:
                f1_gaps.append(f"L{level}")
                continue
            level_ok = False
            for role_key in role_keys:
                user_ids = db.execute(
                    select(OfficerScope.user_id).where(
                        OfficerScope.role_key == role_key,
                        _officer_scope_for_project(project),
                    )
                ).scalars().all()
                for uid in user_ids:
                    prof = profiles.get(uid.lower())
                    if prof and prof.phone_number.strip():
                        level_ok = True
                        break
                if level_ok:
                    break
            if not level_ok:
                f1_gaps.append(f"L{level}")
        checks.append(
            GoLiveCheck(
                id="F1",
                label="Officer SMS phones",
                group="officers",
                severity="info",
                status="pass" if not f1_gaps else "warn",
                message=(
                    "Officers on SMS levels have a phone number"
                    if not f1_gaps
                    else f"Add a phone number for officers at: {', '.join(f1_gaps[:5])}"
                ),
                section="messaging",
            )
        )

    # E1 Metadata
    e1_ok = bool(project.name.strip() and project.short_code.strip())
    checks.append(
        GoLiveCheck(
            id="E1",
            label="Name and code",
            group="metadata",
            severity="block",
            status="pass" if e1_ok else "fail",
            message="Name and short code set" if e1_ok else "Set the project name and short code",
            section=None,
        )
    )

    # Binary go-live (Q-GL-1/2, doc 13 §7): every check is a **Blocker** or **Optional** —
    # there is no middle "warning" that a user learns to ignore. Blockers are exactly doc 13
    # §7's table; everything else carries severity="info" and never stops activation.
    # A1/D1/E1/C4 were promoted 2026-08-04: they were documented Blockers shipping as warnings,
    # so a project with no default workflow and no locations could be activated.
    # A3/A5 → B1 the same day: the organization gate is now the type's own catalog (§7).
    _ACTIVATION_BLOCK_IDS = {"A1", "B1", "C1", "C4", "C5", "D1", "E1", "R1"}
    can_activate = not any(
        c.id in _ACTIVATION_BLOCK_IDS and c.status == "fail" for c in checks
    )
    can_accept = not any(c.id == "C1" and c.status == "fail" for c in checks)

    return GoLiveReport(checks=checks, can_activate=can_activate, can_accept_tickets=can_accept)


def activation_block_message(report: GoLiveReport) -> str | None:
    if report.can_activate:
        return None
    blocking = [
        c for c in report.checks
        if c.id in {"B1", "C5"} and c.status == "fail"
    ]
    if blocking:
        return "; ".join(c.message for c in blocking)
    return "Project cannot be activated until go-live requirements are met."


def ticket_intake_block_message(db: Session, project_id: str) -> str | None:
    report = evaluate_go_live(db, project_id)
    if report.can_accept_tickets:
        return None
    for c in report.checks:
        if c.id == "C1" and c.status == "fail":
            return (
                f"Ticket intake blocked: {c.message}. "
                "Fix officer staffing under Settings → Projects."
            )
    return "Ticket intake blocked: project is not ready for grievances."
