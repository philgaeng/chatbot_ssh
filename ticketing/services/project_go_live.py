"""Go-live readiness checks for projects (§17 demo rules)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from ticketing.constants.assignment import COUNTRY_L1_FALLBACK_ROLE
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


def _has_officer_on_package(db: Session, *, package_id: str, grm_role_key: str) -> bool:
    return (
        db.execute(
            select(OfficerScope.user_id).where(
                OfficerScope.role_key == grm_role_key,
                OfficerScope.package_id == package_id,
            ).limit(1)
        ).scalar_one_or_none()
        is not None
    )


def _has_officer_on_project_wide(
    db: Session,
    *,
    project: Project,
    grm_role_key: str,
) -> bool:
    return (
        db.execute(
            select(OfficerScope.user_id)
            .where(
                OfficerScope.role_key == grm_role_key,
                OfficerScope.package_id.is_(None),
                or_(
                    OfficerScope.project_id == project.project_id,
                    OfficerScope.project_code == project.short_code,
                ),
            )
            .limit(1)
        ).scalar_one_or_none()
        is not None
    )


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
    from ticketing.services.workflow_routing import uncovered_classifications

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
            severity="warn",
            status="pass" if a1_ok else "warn",
            message="Default published workflow set"
            if a1_ok
            else "Mark exactly one workflow binding as Default (catch-all)",
            section="workflows",
        )
    )

    seah_bindings = [
        b for b in bindings
        if _workflow_published(db, b.workflow_id)
        and db.get(WorkflowDefinition, b.workflow_id)
        and (db.get(WorkflowDefinition, b.workflow_id).workflow_type or "").lower() == "seah"
    ]
    a2_ok = len(seah_bindings) > 0
    checks.append(
        GoLiveCheck(
            id="A2",
            label="SEAH workflow",
            group="routing",
            severity="warn",
            status="pass" if a2_ok else "warn",
            message="SEAH workflow binding configured" if a2_ok else "Add a SEAH workflow binding",
            section="workflows",
        )
    )

    missing_cls = uncovered_classifications(db, bindings)
    if missing_cls:
        checks.append(
            GoLiveCheck(
                id="A4",
                label="Classification coverage",
                group="routing",
                severity="warn",
                status="warn",
                message=f"Classifications not mapped to a non-default workflow: {', '.join(missing_cls[:5])}"
                + ("…" if len(missing_cls) > 5 else ""),
                section="workflows",
            )
        )

    # A3 Implementing agency (block for activation)
    routing_role = (pt.routing_org_role if pt else "implementing_agency")
    has_ia = _project_org_has_role(project, routing_role)
    checks.append(
        GoLiveCheck(
            id="A3",
            label="Implementing agency",
            group="routing",
            severity="block",
            status="pass" if has_ia else "fail",
            message=f"Assign an organization to role '{routing_role}'"
            if not has_ia
            else "Implementing agency assigned",
            section="actors",
        )
    )

    # B1 Required project actor slots
    if pt:
        required = required_project_role_keys(pt)
        missing = [k for k in required if not _project_org_has_role(project, k)]
        b1_ok = not missing
        checks.append(
            GoLiveCheck(
                id="B1",
                label="Required project actors",
                group="commercial",
                severity="warn",
                status="pass" if b1_ok else "warn",
                message="All required actors assigned"
                if b1_ok
                else f"Missing: {', '.join(missing)}",
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
                severity="warn",
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
                    severity="warn",
                    status="pass" if b3_ok else "warn",
                    message="Package contractor roles covered"
                    if b3_ok
                    else f"Missing: {', '.join(gaps[:5])}",
                    section="packages",
                )
            )

    # C1 L1 officer per package (or project-wide / country fallback)
    l1_role = _first_standard_step_role(db, project)
    l1_project_fallback = bool(l1_role and _has_project_l1_fallback(db, project, l1_role))
    l1_gaps = _packages_missing_role(
        db,
        project=project,
        packages=packages,
        grm_role_key=l1_role or "",
        project_wide_covers=l1_project_fallback,
    )
    c1_ok = bool(l1_role) and not l1_gaps
    checks.append(
        GoLiveCheck(
            id="C1",
            label="L1 officer coverage",
            group="officers",
            severity="block",
            status="pass" if c1_ok else ("fail" if l1_role else "warn"),
            message=(
                "Every package has an L1 officer (or project-wide L1 / country fallback)"
                if c1_ok
                else (
                    f"Add L1 ({l1_role}) for packages: {', '.join(l1_gaps[:5])}"
                    if l1_gaps
                    else "Link a standard workflow with an L1 step"
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
            label="L2 officer coverage",
            group="officers",
            severity="warn",
            status="pass" if c2_ok else ("warn" if l2_role else "info"),
            message=(
                "Every package has an L2 officer (or project-wide L2 fallback)"
                if c2_ok
                else (
                    f"Add L2 ({l2_role}) for packages: {', '.join(l2_gaps[:5])}"
                    if l2_gaps
                    else "Link a standard workflow with an L2 step"
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
                        or_(
                            OfficerScope.project_id == project.project_id,
                            OfficerScope.project_code == project.short_code,
                        ),
                    )
                    .limit(1)
                ).scalar_one_or_none()
                is not None
            )
        checks.append(
            GoLiveCheck(
                id="C4",
                label="SEAH L1 officer",
                group="officers",
                severity="warn",
                status="pass" if c4_ok else "warn",
                message="SEAH step-1 officer scoped to project" if c4_ok else "Add SEAH L1 officer scope on this project",
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
            severity="warn",
            status="pass" if d1_ok else "warn",
            message="At least one location linked" if d1_ok else "Link provinces, districts, or municipalities",
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
                        or_(
                            OfficerScope.project_id == project.project_id,
                            OfficerScope.project_code == project.short_code,
                        ),
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
                severity="warn",
                status="pass" if not f1_gaps else "warn",
                message=(
                    "SMS-enabled levels have officers with phones"
                    if not f1_gaps
                    else f"Add phones for SMS levels: {', '.join(f1_gaps[:5])}"
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
            severity="warn",
            status="pass" if e1_ok else "warn",
            message="Project name and short code set" if e1_ok else "Set name and short code",
            section=None,
        )
    )

    can_activate = not any(c.id == "A3" and c.status == "fail" for c in checks)
    can_accept = not any(c.id == "C1" and c.status == "fail" for c in checks)

    return GoLiveReport(checks=checks, can_activate=can_activate, can_accept_tickets=can_accept)


def activation_block_message(report: GoLiveReport) -> str | None:
    if report.can_activate:
        return None
    for c in report.checks:
        if c.id == "A3" and c.status == "fail":
            return c.message
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
