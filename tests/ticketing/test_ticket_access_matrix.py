"""HR-02 — per-ticket authorization matrix.

The mechanical guard against the file/PII authz bug class: for every persona × every
per-ticket / per-file endpoint, assert the access decision made by
``require_ticket_access`` / ``require_file_access`` (`ticketing/api/ticket_access.py`).

Personas (built on the seed role catalog + KL Road standard/SEAH workflows):
  super_admin, SEAH officer (assigned), in-scope assigned officer, in-scope but
  unassigned officer, informed-tier viewer, out-of-scope officer.

Key acceptance (spec §2):
  * SEAH ticket × non-cast persona ⇒ denied on EVERY endpoint (incl. both file endpoints —
    the regression this ticket fixes) — and since 2026-08-02 that includes `super_admin`.
  * Standard ticket × out-of-scope officer ⇒ denied on detail / pii / files.
  * In-scope assigned / viewer / super_admin ⇒ allowed (standard tickets).
"""
from __future__ import annotations

import os
import tempfile
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from ticketing.api.dependencies import CurrentUser, get_authenticated_user, get_db
from ticketing.api.main import app
from ticketing.models.base import SessionLocal
from ticketing.models.officer_scope import OfficerScope
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.ticket_file import TicketFile
from ticketing.models.ticket_viewer import TicketViewer
from ticketing.models.workflow import WorkflowDefinition, WorkflowStep

pytestmark = pytest.mark.integration

# ── stable constants (match kl_road_standard / kl_road_seah seed) ────────────
ORG_DOR = "DOR"
PROJECT_KL_ROAD = "KL_ROAD"
ROLE_L1 = "site_safeguards_focal_person"
ROLE_SEAH = "seah_national_officer"
LOC_TICKET = "P1_JHA_BIR"     # Birtamod, Jhapa (child of P1_JHA)
LOC_SCOPE = "P1_JHA"          # Jhapa district — parent covers the ticket location
WORKFLOW_STANDARD_KEY = "KL_ROAD_STANDARD"
WORKFLOW_SEAH_KEY = "KL_ROAD_SEAH"

# ── persona user_ids ─────────────────────────────────────────────────────────
U_SUPER = "matrix-super@grm.local"
U_SEAH = "matrix-seah@grm.local"
U_ASSIGNED = "matrix-l1-assigned@grm.local"
U_UNASSIGNED = "matrix-l1-inscope@grm.local"
U_VIEWER = "matrix-viewer@grm.local"
U_OUT = "matrix-out-of-scope@grm.local"

PERSONAS: dict[str, CurrentUser] = {
    "super_admin": CurrentUser(user_id=U_SUPER, role_keys=["super_admin"]),
    "seah_officer": CurrentUser(user_id=U_SEAH, role_keys=[ROLE_SEAH]),
    "in_scope_assigned": CurrentUser(user_id=U_ASSIGNED, role_keys=[ROLE_L1]),
    "in_scope_unassigned": CurrentUser(user_id=U_UNASSIGNED, role_keys=[ROLE_L1]),
    "viewer_informed": CurrentUser(user_id=U_VIEWER, role_keys=[ROLE_L1]),
    "out_of_scope": CurrentUser(user_id=U_OUT, role_keys=[ROLE_L1]),
}

# endpoint specs. {tid} = ticket id, {fid} = officer file id on that ticket.
ENDPOINTS = [
    {"name": "detail", "method": "GET", "path": "/api/v1/tickets/{tid}"},
    {"name": "pii", "method": "GET", "path": "/api/v1/tickets/{tid}/pii"},
    {"name": "files_list", "method": "GET", "path": "/api/v1/tickets/{tid}/files"},
    {"name": "attachments_list", "method": "GET", "path": "/api/v1/tickets/{tid}/attachments"},
    {"name": "sla", "method": "GET", "path": "/api/v1/tickets/{tid}/sla"},
    {"name": "attachment_download", "method": "GET", "path": "/api/v1/attachments/{fid}"},
    {
        "name": "action_note",
        "method": "POST",
        "path": "/api/v1/tickets/{tid}/actions",
        "json": {"action_type": "NOTE", "note": "matrix access probe"},
    },
]

# Access decision per persona for a STANDARD ticket vs a SEAH ticket.
STANDARD_ALLOW = {"super_admin", "in_scope_assigned", "in_scope_unassigned", "viewer_informed"}
# DECISION-sensitive-workflows §3 (2026-08-02): `super_admin` was removed from this set. Access
# to a sensitive case is cast membership on its workflow and nothing else — no admin tier, no
# oversight role. A super_admin who needs one staffs themselves onto the workflow, which is an
# audited assignment. See tests/ticketing/test_sensitive_workflow_access.py.
SEAH_ALLOW = {"seah_officer"}


def _new_id() -> str:
    return str(uuid.uuid4())


def _make_ticket(db, workflow_key: str, *, is_seah: bool, assigned_to: str) -> Ticket:
    wf = db.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.workflow_key == workflow_key)
    ).scalar_one()
    step = db.execute(
        select(WorkflowStep)
        .where(WorkflowStep.workflow_id == wf.workflow_id)
        .order_by(WorkflowStep.step_order)
        .limit(1)
    ).scalar_one()
    row = Ticket(
        ticket_id=_new_id(),
        grievance_id=f"matrix-grv-{uuid.uuid4().hex[:10]}",
        organization_id=ORG_DOR,
        location_code=LOC_TICKET,
        project_code=PROJECT_KL_ROAD,
        current_workflow_id=wf.workflow_id,
        current_step_id=step.step_id,
        assigned_to_user_id=assigned_to,
        status_code="OPEN",
        is_seah=is_seah,
        is_deleted=False,
        sla_breached=False,
        priority="NORMAL",
    )
    db.add(row)
    db.flush()
    return row


def _make_officer_file(db, ticket_id: str, disk_path: str) -> TicketFile:
    tf = TicketFile(
        file_id=_new_id(),
        ticket_id=ticket_id,
        file_name="probe.txt",
        file_path=disk_path,
        file_type="document",
        file_size=os.path.getsize(disk_path),
        uploaded_by_user_id="system",
    )
    db.add(tf)
    db.flush()
    return tf


def _make_scope(db, user_id: str, *, location_code: str, project_code: str) -> OfficerScope:
    row = OfficerScope(
        scope_id=_new_id(),
        user_id=user_id,
        role_key=ROLE_L1,
        organization_id=ORG_DOR,
        location_code=location_code,
        project_code=project_code,
        includes_children=True,
    )
    db.add(row)
    db.flush()
    return row


@pytest.fixture(scope="module")
def matrix_env():
    """Create standard + SEAH tickets, scopes, viewer, officer files; tear down after."""
    db = SessionLocal()
    tmpdir = tempfile.mkdtemp(prefix="matrix-files-")
    disk_file = os.path.join(tmpdir, "probe.txt")
    with open(disk_file, "w", encoding="utf-8") as fh:
        fh.write("probe")

    created_tickets: list[str] = []
    created_scopes: list[str] = []
    try:
        std = _make_ticket(db, WORKFLOW_STANDARD_KEY, is_seah=False, assigned_to=U_ASSIGNED)
        seah = _make_ticket(db, WORKFLOW_SEAH_KEY, is_seah=True, assigned_to=U_SEAH)
        created_tickets += [std.ticket_id, seah.ticket_id]

        std_file = _make_officer_file(db, std.ticket_id, disk_file)
        seah_file = _make_officer_file(db, seah.ticket_id, disk_file)

        # Scopes: in-scope personas cover the standard ticket's district; out-of-scope
        # points at a different project so ticket_matches_scope fails outright.
        for uid in (U_ASSIGNED, U_UNASSIGNED):
            created_scopes.append(
                _make_scope(db, uid, location_code=LOC_SCOPE, project_code=PROJECT_KL_ROAD).scope_id
            )
        created_scopes.append(
            _make_scope(db, U_OUT, location_code="P2_PAR_BIR", project_code="MATRIX_OTHER_PROJ").scope_id
        )

        # Informed-tier viewer on the STANDARD ticket only.
        db.add(TicketViewer(
            viewer_id=_new_id(),
            ticket_id=std.ticket_id,
            user_id=U_VIEWER,
            added_by_user_id="system",
            tier="informed",
        ))
        db.commit()

        yield {
            "std_tid": std.ticket_id,
            "std_fid": std_file.file_id,
            "seah_tid": seah.ticket_id,
            "seah_fid": seah_file.file_id,
        }
    finally:
        # events created by NOTE probes, then files/viewers/scopes/tickets
        db.execute(delete(TicketEvent).where(TicketEvent.ticket_id.in_(created_tickets)))
        db.execute(delete(TicketFile).where(TicketFile.ticket_id.in_(created_tickets)))
        db.execute(delete(TicketViewer).where(TicketViewer.ticket_id.in_(created_tickets)))
        if created_scopes:
            db.execute(delete(OfficerScope).where(OfficerScope.scope_id.in_(created_scopes)))
        db.execute(delete(Ticket).where(Ticket.ticket_id.in_(created_tickets)))
        db.commit()
        db.close()
        try:
            os.remove(disk_file)
            os.rmdir(tmpdir)
        except OSError:
            pass


def _call(persona: CurrentUser, endpoint: dict, tid: str, fid: str) -> int:
    db = SessionLocal()

    def _override_user():
        return persona

    def _override_db():
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_authenticated_user] = _override_user
    app.dependency_overrides[get_db] = _override_db
    try:
        client = TestClient(app)
        url = endpoint["path"].format(tid=tid, fid=fid)
        resp = client.request(endpoint["method"], url, json=endpoint.get("json"))
        return resp.status_code
    finally:
        app.dependency_overrides.clear()


def _decision(status_code: int) -> str:
    if status_code == 403:
        return "DENY"
    if status_code in (401, 404):
        # 404 only expected for genuinely-missing resources — not used for access here.
        return "OTHER"
    return "ALLOW"


@pytest.mark.parametrize("persona_name", list(PERSONAS))
@pytest.mark.parametrize("endpoint", ENDPOINTS, ids=lambda e: e["name"])
def test_standard_ticket_access(matrix_env, persona_name, endpoint):
    persona = PERSONAS[persona_name]
    status = _call(persona, endpoint, matrix_env["std_tid"], matrix_env["std_fid"])
    if persona_name in STANDARD_ALLOW:
        assert status not in (401, 403, 404), (
            f"{persona_name} should ACCESS standard {endpoint['name']} (got {status})"
        )
    else:
        assert status == 403, (
            f"{persona_name} must be DENIED standard {endpoint['name']} (got {status})"
        )


@pytest.mark.parametrize("persona_name", list(PERSONAS))
@pytest.mark.parametrize("endpoint", ENDPOINTS, ids=lambda e: e["name"])
def test_seah_ticket_access(matrix_env, persona_name, endpoint):
    persona = PERSONAS[persona_name]
    status = _call(persona, endpoint, matrix_env["seah_tid"], matrix_env["seah_fid"])
    if persona_name in SEAH_ALLOW:
        assert status not in (401, 403, 404), (
            f"{persona_name} should ACCESS SEAH {endpoint['name']} (got {status})"
        )
    else:
        # The regression fix: every non-SEAH persona is walled off, including the two
        # file endpoints that previously skipped the SEAH gate.
        assert status == 403, (
            f"{persona_name} must be DENIED SEAH {endpoint['name']} (got {status})"
        )


def test_seah_file_endpoints_blocked_for_standard_officer(matrix_env):
    """Focused assertion of the exact review finding: an in-scope STANDARD officer
    cannot pull a SEAH ticket's officer attachment by file_id."""
    status = _call(
        PERSONAS["in_scope_assigned"], ENDPOINTS[5], matrix_env["seah_tid"], matrix_env["seah_fid"]
    )
    assert status == 403


def test_super_admin_downloads_file(matrix_env):
    """super_admin passes the gate and the file streams (200)."""
    status = _call(
        PERSONAS["super_admin"], ENDPOINTS[5], matrix_env["std_tid"], matrix_env["std_fid"]
    )
    assert status == 200
