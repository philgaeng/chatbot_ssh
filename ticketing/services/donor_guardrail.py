"""
Project participants & the donor last-step-informed guardrail.

doc 13 / DECISION 2026-07-10 §3 + OC-04 §5.6. Three thin helpers over the new
participant structures (``projects.implementing_agency_org_id`` + ``project_donors``):

* **implementing agency** — the single accountable org (routing + reporting anchor). Must
  be a ``government``/``local_government`` org. ``validate_implementing_agency`` enforces
  that; routing prefers this field over the legacy ``org_role='implementing_agency'`` link.
* **donor guardrail** — when a project has ≥1 donor, the final *standard*-track step's
  "Kept informed" cast must contain ≥1 ``donor_*`` role, so donor staff are notified on
  final escalation. ``donor_informed_ok`` is the go-live predicate;
  ``apply_donor_informed_defaults`` auto-populates the cast (admin may trim to ≥1).
* **SEAH leak-proofing** lives in ``ticketing.engine.escalation._apply_step_tier_roles``
  (donor tiers are never cast on a SEAH ticket). This module governs the *standard* track
  only — it never touches the SEAH workflow.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.models.organization import Organization
from ticketing.models.project import Project, ProjectDonor, ProjectOrganization
from ticketing.models.user import DONOR_ROLES
from ticketing.models.workflow import WorkflowStep

# Categories permitted as the implementing agency (the signing ministry).
IA_ALLOWED_CATEGORIES = ("government", "local_government")


def implementing_agency_org_id(db: Session, project: Project) -> Optional[str]:
    """The project's implementing agency org id.

    Prefers the dedicated field (doc 13); falls back to the legacy
    ``org_role='implementing_agency'`` link during the expand phase so routing keeps
    working for projects created before this field existed.
    """
    if project.implementing_agency_org_id:
        return project.implementing_agency_org_id
    for po in project.organizations:
        if po.org_role == "implementing_agency":
            return po.organization_id
    return None


def validate_implementing_agency(db: Session, org_id: Optional[str]) -> None:
    """Raise ``ValueError`` unless ``org_id`` is a government/local_government org.

    ``None`` is allowed (the field is defaulted elsewhere; an unset IA folds into the
    staffing go-live gate). A donor/third_party org is rejected — a contractor or funder
    can never be the accountable agency.
    """
    if not org_id:
        return
    org = db.get(Organization, org_id)
    if org is None:
        raise ValueError(f"Implementing agency org '{org_id}' does not exist")
    if org.org_category not in IA_ALLOWED_CATEGORIES:
        raise ValueError(
            "Implementing agency must be a government or local-government organization "
            f"(got category '{org.org_category}')"
        )


def validate_donor_org(db: Session, org_id: str) -> None:
    """Raise ``ValueError`` unless ``org_id`` is an existing ``donor``-category org."""
    org = db.get(Organization, org_id)
    if org is None:
        raise ValueError(f"Organization '{org_id}' does not exist")
    if org.org_category != "donor":
        raise ValueError(
            "Only a donor-category organization can be added as a project donor "
            f"(got category '{org.org_category}')"
        )


def project_donor_org_ids(db: Session, project_id: str) -> list[str]:
    """Org ids of every donor on the project (category ``donor``); [] when none."""
    return list(
        db.execute(
            select(ProjectDonor.organization_id).where(
                ProjectDonor.project_id == project_id
            )
        ).scalars().all()
    )


def project_has_donor(db: Session, project_id: str) -> bool:
    return len(project_donor_org_ids(db, project_id)) > 0


def _standard_steps(db: Session, project: Project) -> list[WorkflowStep]:
    if not project.standard_workflow_id:
        return []
    return list(
        db.execute(
            select(WorkflowStep)
            .where(WorkflowStep.workflow_id == project.standard_workflow_id)
            .order_by(WorkflowStep.step_order)
        ).scalars().all()
    )


def last_standard_step(db: Session, project: Project) -> Optional[WorkflowStep]:
    """The highest-``step_order`` step of the project's standard workflow (the final
    escalation level), or ``None`` if no standard workflow / no steps."""
    steps = _standard_steps(db, project)
    return steps[-1] if steps else None


def donor_informed_role_keys(step: Optional[WorkflowStep]) -> list[str]:
    """The ``donor_*`` role keys currently in a step's informed cast."""
    if step is None:
        return []
    return [rk for rk in (step.informed_roles or []) if rk in DONOR_ROLES]


def donor_informed_ok(db: Session, project: Project) -> bool:
    """Go-live predicate: True unless a donor is present but the final standard step's
    "Kept informed" cast has no ``donor_*`` role. Vacuously true with no donors."""
    if not project_has_donor(db, project.project_id):
        return True
    return len(donor_informed_role_keys(last_standard_step(db, project))) >= 1


def apply_donor_informed_defaults(db: Session, project: Project) -> list[str]:
    """Auto-populate the final standard step's "Kept informed" cast with the donor tiers
    (config-time; admin may later trim to ≥1). Idempotent. No-op when there are no donors
    or no standard workflow. Returns the donor role keys added this call.

    Does **not** commit — the caller owns the transaction.
    """
    if not project_has_donor(db, project.project_id):
        return []
    step = last_standard_step(db, project)
    if step is None:
        return []
    existing = list(step.informed_roles or [])
    added = [rk for rk in sorted(DONOR_ROLES) if rk not in existing]
    if added:
        step.informed_roles = existing + added
        db.add(step)
    return added
