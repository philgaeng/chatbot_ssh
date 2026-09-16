"""Sensitive (SEAH) workflows — access is cast membership, nothing else.

Pins `DECISION-sensitive-workflows.md` (2026-08-02): administering a sensitive workflow is not
a reason to read its grievances. These tests exist to fail loudly if an admin, oversight, or
"convenience" branch is ever put back into the case-access path.

The split under test:
  can_see_seah_extended(user)            → may open sensitive grievances    — CAST ONLY
  can_configure_sensitive_workflows(u)   → may administer sensitive workflows — admins, no reads
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from ticketing.api.dependencies import CurrentUser
from ticketing.services.admin_access import (
    AdminScopeRow,
    can_configure_sensitive_workflows,
    can_see_seah_extended,
)


def _scope(**kwargs) -> AdminScopeRow:
    defaults = dict(
        admin_scope_id="s1",
        user_id="u@grm.local",
        role_key="org_admin",
        country_code="NP",
        project_id=None,
        organization_id=None,
        package_id=None,
        workflow_track="seah",
    )
    defaults.update(kwargs)
    return AdminScopeRow(**defaults)


# ── Case access: cast only ───────────────────────────────────────────────────

def test_super_admin_cannot_see_sensitive_cases():
    """The branch that mattered most. `super_admin` administers everything and reads no
    sensitive case; break-glass is to staff themselves onto the workflow (audited)."""
    user = CurrentUser(user_id="root@grm.local", role_keys=["super_admin"])
    assert can_see_seah_extended(user) is False


def test_oversight_role_cannot_see_sensitive_cases():
    """`adb_hq_exec` is senior read-only oversight of *standard* work. Donor staff who need
    sensitive cases are cast on the workflow (observer tier) like anyone else."""
    user = CurrentUser(user_id="exec@adb.org", role_keys=["adb_hq_exec"])
    assert can_see_seah_extended(user) is False


def test_admin_on_the_sensitive_track_cannot_see_sensitive_cases():
    """The configure/read split: this admin sets up sensitive workflows and staffs them, and
    still sees none of their grievances."""
    user = CurrentUser(
        user_id="seahadmin@grm.local",
        role_keys=["org_admin"],
        admin_scopes=[_scope(workflow_track="seah")],
    )
    assert can_see_seah_extended(user) is False
    assert can_configure_sensitive_workflows(user) is True


def test_cast_member_sees_sensitive_cases():
    user = CurrentUser(user_id="officer@grm.local", role_keys=[])
    user.seah_track_member = True  # set at enrich time from the workflow's step cast
    assert can_see_seah_extended(user) is True


def test_named_sensitive_officer_roles_still_see_cases():
    """Legacy fast-path: these roles are only ever held by SEAH officers and the seeded SEAH
    workflow casts them, so this is cast membership by another name (DECISION §7)."""
    for key in ("seah_national_officer", "seah_hq_officer"):
        assert can_see_seah_extended(CurrentUser(user_id="o@grm.local", role_keys=[key])) is True


def test_standard_officer_sees_nothing_sensitive():
    user = CurrentUser(user_id="l1@grm.local", role_keys=["site_safeguards_focal_person"])
    assert can_see_seah_extended(user) is False
    assert can_configure_sensitive_workflows(user) is False


# ── Configure: admins keep the catalog ───────────────────────────────────────

def test_super_admin_can_configure_sensitive_workflows():
    """Without this the admin catalog breaks: nobody could author a sensitive workflow."""
    assert can_configure_sensitive_workflows(
        CurrentUser(user_id="root@grm.local", role_keys=["super_admin"])
    ) is True


def test_standard_track_admin_cannot_configure_sensitive_workflows():
    user = CurrentUser(
        user_id="stdadmin@grm.local",
        role_keys=["org_admin"],
        admin_scopes=[_scope(workflow_track="standard")],
    )
    assert can_configure_sensitive_workflows(user) is False


# ── PII disclosure ───────────────────────────────────────────────────────────

class _FakeTicket:
    def __init__(self, is_seah: bool):
        self.is_seah = is_seah


def test_pii_endpoints_refuse_a_non_cast_admin():
    """Stated at the endpoint that discloses PII, not only in the shared access dependency —
    and it is the only gate on this path while the backend's reveal policy does not exist
    (DECISION §4)."""
    from ticketing.api.routers.tickets.pii import _require_sensitive_cast

    admin = CurrentUser(user_id="root@grm.local", role_keys=["super_admin"])
    with pytest.raises(HTTPException) as exc:
        _require_sensitive_cast(_FakeTicket(is_seah=True), admin)
    assert exc.value.status_code == 403

    # …and lets the cast through, and never blocks a standard ticket.
    officer = CurrentUser(user_id="o@grm.local", role_keys=["seah_national_officer"])
    _require_sensitive_cast(_FakeTicket(is_seah=True), officer)
    _require_sensitive_cast(_FakeTicket(is_seah=False), admin)


# ── Routing: a sensitive workflow is never the catch-all ─────────────────────

@pytest.mark.integration
def test_a_sensitive_workflow_cannot_be_the_default(db):
    """Otherwise every grievance matching nothing else lands where only the cast can see it."""
    import sqlalchemy as sa

    from ticketing.models.project import Project
    from ticketing.models.workflow import WorkflowDefinition
    from ticketing.services.project_workflows import replace_project_workflows

    project = db.execute(sa.select(Project).limit(1)).scalars().first()
    if project is None:
        pytest.skip("no project seeded")
    wf = db.execute(
        sa.select(WorkflowDefinition).where(
            sa.func.lower(WorkflowDefinition.workflow_type) == "seah",
            WorkflowDefinition.status == "published",
            WorkflowDefinition.is_template.is_(False),
        ).limit(1)
    ).scalars().first()
    if wf is None:
        pytest.skip("no published sensitive workflow seeded")

    with pytest.raises(HTTPException) as exc:
        replace_project_workflows(
            db,
            project,
            [{
                "display_label": f"bad-default-{uuid.uuid4().hex[:6]}",
                "workflow_id": wf.workflow_id,
                "is_default": True,
            }],
        )
    assert exc.value.status_code == 422
    assert "sensitive" in str(exc.value.detail).lower()
    db.rollback()


# ── Go-live: a sensitive workflow is optional ────────────────────────────────

@pytest.mark.integration
def test_go_live_no_longer_asks_for_a_sensitive_workflow(db):
    """A2 removed — a project needs no sensitive workflow, so its absence is not a finding."""
    import sqlalchemy as sa

    from ticketing.models.project import Project
    from ticketing.services.project_go_live import evaluate_go_live

    project = db.execute(sa.select(Project).limit(1)).scalars().first()
    if project is None:
        pytest.skip("no project seeded")
    report = evaluate_go_live(db, project.project_id)
    assert "A2" not in {c.id for c in report.checks}
