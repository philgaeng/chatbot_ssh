"""H2-03 — authorization matrix extension.

Broadens the HR-02 per-ticket matrix (``test_ticket_access_matrix.py``) into three
systematic sweeps on the *split* ``routers/tickets`` package + the admin routers:

  Part 1 — **All action types × personas** on ``POST /tickets/{id}/actions``.
           Locks the two authz layers for every action in ``VALID_ACTIONS``:
             * ``require_ticket_access`` (SEAH wall + jurisdiction scope), and
             * ``perform_action``'s assignment guard (only the assignee/admin may
               change status; NOTE/FIELD_REPORT stay open to any reader).
  Part 2 — **Admin-surface endpoints × admin ladder** (super / org / project /
           officer / non-admin), asserted against the documented matrix in
           ``docs/ticketing_system/11_roles_and_permissions.md`` §2/§4. Spec-vs-code
           divergences are ``xfail``-ed with the discrepancy recorded in the sprint
           PROGRESS (never codified as correct).
  Part 3 — **Unauthenticated sweep** over every published route (``app.openapi()``
           — this app nests routers, so ``app.routes`` is not flat). With real
           Keycloak auth (bypass off) every protected route must answer 401/403 to a
           request with no token; the known-public + API-key set is skipped.

One seeded fixture set, no per-case reseeding (deny probes are pre-mutation; the few
allow probes that mutate use a throwaway ticket). Runs well under the 2-minute budget.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from fastapi import HTTPException

from ticketing.api import dependencies as deps
from ticketing.api import main as main_mod
from ticketing.api.dependencies import CurrentUser, get_authenticated_user, get_db
from ticketing.api.main import app
from ticketing.config.settings import TicketingSettings
from ticketing.services.admin_access import AdminScopeRow, SettingsAction, require_settings_write
from ticketing.models.base import SessionLocal
from ticketing.models.officer_scope import OfficerScope
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.ticket_viewer import TicketViewer
from ticketing.models.workflow import WorkflowDefinition, WorkflowStep

pytestmark = pytest.mark.integration

# ── stable seed constants (match kl_road_standard / kl_road_seah) ────────────
ORG_DOR = "DOR"
PROJECT_KL_ROAD = "KL_ROAD"
ROLE_L1 = "site_safeguards_focal_person"
ROLE_SEAH = "seah_national_officer"
LOC_TICKET = "P1_JHA_BIR"
LOC_SCOPE = "P1_JHA"
WORKFLOW_STANDARD_KEY = "KL_ROAD_STANDARD"
WORKFLOW_SEAH_KEY = "KL_ROAD_SEAH"

U_SUPER = "xmatrix-super@grm.local"
U_SEAH = "xmatrix-seah@grm.local"
U_ASSIGNED = "xmatrix-l1-assigned@grm.local"
U_UNASSIGNED = "xmatrix-l1-inscope@grm.local"
U_VIEWER = "xmatrix-viewer@grm.local"
U_OUT = "xmatrix-out@grm.local"

# Per-ticket personas (Part 1) — mirror the HR-02 set.
PERSONAS: dict[str, CurrentUser] = {
    "super_admin": CurrentUser(user_id=U_SUPER, role_keys=["super_admin"]),
    "seah_officer": CurrentUser(user_id=U_SEAH, role_keys=[ROLE_SEAH]),
    "in_scope_assigned": CurrentUser(user_id=U_ASSIGNED, role_keys=[ROLE_L1]),
    "in_scope_unassigned": CurrentUser(user_id=U_UNASSIGNED, role_keys=[ROLE_L1]),
    "viewer_informed": CurrentUser(user_id=U_VIEWER, role_keys=[ROLE_L1]),
    "out_of_scope": CurrentUser(user_id=U_OUT, role_keys=[ROLE_L1]),
}

# Personas with per-ticket access to the STANDARD (assigned) ticket.
STANDARD_ACCESS = {"super_admin", "in_scope_assigned", "in_scope_unassigned", "viewer_informed"}
# Personas with per-ticket access to the SEAH ticket.
SEAH_ACCESS = {"super_admin", "seah_officer"}

# perform_action taxonomy (keep in sync with actions.py).
ALL_ACTIONS = [
    "ACKNOWLEDGE", "ESCALATE", "RESOLVE", "NOTE",
    "FIELD_REPORT", "GRC_CONVENE", "REASSIGNMENT_REQUESTED",
]
ASSIGNMENT_REQUIRED = {"ACKNOWLEDGE", "ESCALATE", "RESOLVE", "GRC_CONVENE", "REASSIGNMENT_REQUESTED"}
EXEMPT_ACTIONS = {"NOTE", "FIELD_REPORT"}  # any reader may file these


def _new_id() -> str:
    return str(uuid.uuid4())


def _action_body(action: str) -> dict:
    """Minimal body that gets each action *past* request validation to the authz layer."""
    body: dict = {"action_type": action}
    if action in ("NOTE", "FIELD_REPORT"):
        body["note"] = "authz matrix probe"
    if action == "ESCALATE":
        body["escalation_notes"] = "authz matrix probe"
    if action == "REASSIGNMENT_REQUESTED":
        body["reassignment_reason_code"] = "OTHER"
        body["reassignment_notes"] = "authz matrix probe"
    return body


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
        grievance_id=f"xmatrix-grv-{uuid.uuid4().hex[:10]}",
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
def action_env():
    """Standard (assigned to U_ASSIGNED) + SEAH (assigned to U_SEAH) tickets, plus the
    scopes/viewer that give the in-scope personas access. Torn down after the module."""
    db = SessionLocal()
    tickets: list[str] = []
    scopes: list[str] = []
    try:
        std = _make_ticket(db, WORKFLOW_STANDARD_KEY, is_seah=False, assigned_to=U_ASSIGNED)
        seah = _make_ticket(db, WORKFLOW_SEAH_KEY, is_seah=True, assigned_to=U_SEAH)
        tickets += [std.ticket_id, seah.ticket_id]

        for uid in (U_ASSIGNED, U_UNASSIGNED):
            scopes.append(_make_scope(db, uid, location_code=LOC_SCOPE, project_code=PROJECT_KL_ROAD).scope_id)
        scopes.append(
            _make_scope(db, U_OUT, location_code="P2_PAR_BIR", project_code="XMATRIX_OTHER").scope_id
        )
        db.add(TicketViewer(
            viewer_id=_new_id(), ticket_id=std.ticket_id, user_id=U_VIEWER,
            added_by_user_id="system", tier="informed",
        ))
        db.commit()
        yield {"std_tid": std.ticket_id, "seah_tid": seah.ticket_id}
    finally:
        db.execute(delete(TicketEvent).where(TicketEvent.ticket_id.in_(tickets)))
        db.execute(delete(TicketViewer).where(TicketViewer.ticket_id.in_(tickets)))
        if scopes:
            db.execute(delete(OfficerScope).where(OfficerScope.scope_id.in_(scopes)))
        db.execute(delete(Ticket).where(Ticket.ticket_id.in_(tickets)))
        db.commit()
        db.close()


def _action_call(persona: CurrentUser, tid: str, action: str) -> int:
    db = SessionLocal()

    def _u():
        return persona

    def _d():
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_authenticated_user] = _u
    app.dependency_overrides[get_db] = _d
    try:
        client = TestClient(app)
        resp = client.post(f"/api/v1/tickets/{tid}/actions", json=_action_body(action))
        return resp.status_code
    finally:
        app.dependency_overrides.clear()


# ── Part 1a — the ticket-access wall applies to EVERY action ─────────────────

@pytest.mark.parametrize("action", ALL_ACTIONS)
def test_action_denied_out_of_scope_standard(action_env, action):
    """An out-of-scope officer is walled off from every action on a standard ticket
    (require_ticket_access fires before perform_action — pre-mutation 403)."""
    status = _action_call(PERSONAS["out_of_scope"], action_env["std_tid"], action)
    assert status == 403, f"out_of_scope must be DENIED {action} on standard (got {status})"


@pytest.mark.parametrize("action", ALL_ACTIONS)
@pytest.mark.parametrize(
    "persona_name",
    [p for p in PERSONAS if p not in SEAH_ACCESS],
)
def test_action_denied_non_seah_on_seah(action_env, persona_name, action):
    """Every non-SEAH persona is walled off from every action on a SEAH ticket."""
    status = _action_call(PERSONAS[persona_name], action_env["seah_tid"], action)
    assert status == 403, f"{persona_name} must be DENIED {action} on SEAH (got {status})"


# ── Part 1b — assignment guard: only the assignee/admin changes status ────────

@pytest.mark.parametrize("action", sorted(ASSIGNMENT_REQUIRED))
@pytest.mark.parametrize("persona_name", ["in_scope_unassigned", "viewer_informed"])
def test_assignment_required_denies_non_assignee(action_env, action, persona_name):
    """An in-scope but non-assigned officer (incl. an informed viewer) may NOT perform a
    status-changing action on someone else's ticket — 403 from the assignment guard,
    before any mutation."""
    status = _action_call(PERSONAS[persona_name], action_env["std_tid"], action)
    assert status == 403, (
        f"{persona_name} must be DENIED assignment-required {action} (got {status})"
    )


@pytest.mark.parametrize("action", sorted(EXEMPT_ACTIONS))
@pytest.mark.parametrize("persona_name", ["in_scope_unassigned", "viewer_informed"])
def test_exempt_actions_open_to_any_reader(action_env, action, persona_name):
    """NOTE and FIELD_REPORT are exempt from the assignment guard: any officer who can
    SEE the ticket may annotate it. Not an authz denial (may mutate → events cleaned up
    with the module ticket)."""
    status = _action_call(PERSONAS[persona_name], action_env["std_tid"], action)
    assert status not in (401, 403), (
        f"{persona_name} should be ALLOWED to file {action} (got {status})"
    )


# ── Part 1c — allow path: the assignee and an admin get past the guard ────────

@pytest.mark.parametrize("persona_name", ["in_scope_assigned", "super_admin"])
def test_acknowledge_allowed_for_assignee_and_admin(persona_name):
    """The assigned officer and super_admin pass the guard on ACKNOWLEDGE (admin bypass /
    assignee match). Fresh throwaway ticket so the status change can't leak into the
    shared module fixture. Deeper happy-paths (escalate/resolve/GRC) live in the
    escalation suite — here we only prove the guard's allow branch."""
    db = SessionLocal()
    tid = None
    try:
        std = _make_ticket(db, WORKFLOW_STANDARD_KEY, is_seah=False, assigned_to=U_ASSIGNED)
        db.commit()
        tid = std.ticket_id
    finally:
        db.close()
    try:
        status = _action_call(PERSONAS[persona_name], tid, "ACKNOWLEDGE")
        assert status not in (401, 403), (
            f"{persona_name} should be ALLOWED to ACKNOWLEDGE (got {status})"
        )
    finally:
        clean = SessionLocal()
        try:
            clean.execute(delete(TicketEvent).where(TicketEvent.ticket_id == tid))
            clean.execute(delete(TicketViewer).where(TicketViewer.ticket_id == tid))
            clean.execute(delete(Ticket).where(Ticket.ticket_id == tid))
            clean.commit()
        finally:
            clean.close()


# ══════════════════════════════════════════════════════════════════════════════
# Part 2 — admin-surface × admin ladder
# ══════════════════════════════════════════════════════════════════════════════
# Personas cover the 4-tier ladder + a non-admin. Built in-memory (the predicates read
# role_keys / admin_scopes — no DB), following tests/ticketing/test_admin_ladder.py.

def _admin_scope(role_key, *, track="standard", organization_id=None, project_id=None, uid):
    return AdminScopeRow(
        admin_scope_id=str(uuid.uuid4()), user_id=uid, role_key=role_key,
        country_code="NP", project_id=project_id, organization_id=organization_id,
        package_id=None, workflow_track=track,
    )


LADDER: dict[str, CurrentUser] = {
    "super": CurrentUser(user_id="x-super@grm.local", role_keys=["super_admin"]),
    "org_std": CurrentUser(
        user_id="x-orgstd@grm.local", role_keys=[],
        admin_scopes=[_admin_scope("org_admin", track="standard", organization_id=ORG_DOR, uid="x-orgstd@grm.local")],
    ),
    "org_seah": CurrentUser(
        user_id="x-orgseah@grm.local", role_keys=[],
        admin_scopes=[_admin_scope("org_admin", track="seah", organization_id=ORG_DOR, uid="x-orgseah@grm.local")],
    ),
    "project": CurrentUser(
        user_id="x-proj@grm.local", role_keys=[],
        admin_scopes=[_admin_scope("project_admin", track="standard", project_id=PROJECT_KL_ROAD, uid="x-proj@grm.local")],
    ),
    "officer": CurrentUser(
        user_id="x-officer@grm.local", role_keys=[],
        admin_scopes=[_admin_scope("officer_admin", track="standard", uid="x-officer@grm.local")],
    ),
    "non_admin": CurrentUser(user_id="x-non@grm.local", role_keys=[ROLE_L1]),
}

# (action, track, allowed personas) — encodes docs/ticketing_system/11 §2/§4:
#   platform settings → super only; create project → super + org (any track);
#   org tree / operational-role authoring / workflow authoring → super + org on that track;
#   invite officers → every admin tier; project management → super + org + project;
#   SEAH settings → super + org(seah).
_SETTINGS_MATRIX = [
    (SettingsAction.PLATFORM_SETTINGS, None, {"super"}),
    (SettingsAction.CREATE_PROJECT, None, {"super", "org_std", "org_seah"}),
    (SettingsAction.MANAGE_ORG_STRUCTURE, None, {"super", "org_std"}),
    (SettingsAction.MANAGE_WORKFLOWS, "standard", {"super", "org_std"}),
    (SettingsAction.MANAGE_WORKFLOWS, "seah", {"super", "org_seah"}),
    (SettingsAction.INVITE_OFFICERS, None, {"super", "org_std", "org_seah", "project", "officer"}),
    (SettingsAction.CREATE_OPERATIONAL_ROLE, "standard", {"super", "org_std"}),
    (SettingsAction.MANAGE_SEAH_SETTINGS, None, {"super", "org_seah"}),
    (SettingsAction.MANAGE_PROJECT, None, {"super", "org_std", "org_seah", "project"}),
]
_SETTINGS_IDS = [f"{a.value}|{t or 'none'}" for a, t, _ in _SETTINGS_MATRIX]


@pytest.mark.parametrize("action,track,allowed", _SETTINGS_MATRIX, ids=_SETTINGS_IDS)
@pytest.mark.parametrize("persona_name", list(LADDER))
def test_admin_ladder_settings_matrix(persona_name, action, track, allowed):
    """The admin ladder's capability gate (``require_settings_write``) matches the
    documented matrix for every tier × capability. Divergences from the spec are
    xfail-ed elsewhere / logged in PROGRESS — this asserts the intended matrix."""
    persona = LADDER[persona_name]
    if persona_name in allowed:
        require_settings_write(persona, action, track=track)  # must not raise
    else:
        with pytest.raises(HTTPException) as exc:
            require_settings_write(persona, action, track=track)
        assert exc.value.status_code == 403


def _admin_client(persona: CurrentUser) -> TestClient:
    def _u():
        return persona

    def _d():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_authenticated_user] = _u
    app.dependency_overrides[get_db] = _d
    return TestClient(app)


@pytest.mark.parametrize("persona_name", list(LADDER))
def test_invite_route_wires_admin_guard(persona_name):
    """POST /users/invite is gated by ``require_admin`` (is_any_admin): every admin tier
    passes the guard (empty body then 422), only a non-admin is 403. ``require_admin`` is a
    Depends, so it fires before body validation — no invite side effects."""
    try:
        status = _admin_client(LADDER[persona_name]).post("/api/v1/users/invite", json={}).status_code
    finally:
        app.dependency_overrides.clear()
    if persona_name == "non_admin":
        assert status == 403, f"non-admin must be 403 on invite (got {status})"
    else:
        assert status != 403, f"{persona_name} should pass require_admin (got {status})"


@pytest.fixture(scope="module")
def kl_road_project_id() -> str:
    from ticketing.models.project import Project

    db = SessionLocal()
    try:
        return db.execute(
            select(Project).where(Project.short_code == PROJECT_KL_ROAD)
        ).scalar_one().project_id
    finally:
        db.close()


def test_project_metadata_patch_requires_admin(kl_road_project_id):
    """authz-gaps-h2-03 #3 (fixed): editing a project is super/org/project-admin only
    (doc 11 §2.3/§4). A non-admin officer must get 403; an allowed tier passes the gate.
    Empty body = no-op (nothing mutates)."""
    try:
        denied = _admin_client(LADDER["non_admin"]).patch(
            f"/api/v1/projects/{kl_road_project_id}", json={}
        ).status_code
        allowed = _admin_client(LADDER["project"]).patch(
            f"/api/v1/projects/{kl_road_project_id}", json={}
        ).status_code
    finally:
        app.dependency_overrides.clear()
    assert denied == 403, f"non-admin must be 403 (got {denied})"
    assert allowed != 403, f"project_admin must pass the MANAGE_PROJECT gate (got {allowed})"


def test_delete_custom_role_requires_operational_role_admin():
    """authz-gaps-h2-03 #2 (fixed): deleting a custom/operational role needs the same
    catalog-authoring permission as creating it (super or org_admin on the role's track).
    A non-admin — and even a mere officer_admin — must be 403, and the role must survive."""
    from ticketing.models.user import Role

    db = SessionLocal()
    role = Role(
        role_key=f"authz-del-{uuid.uuid4().hex[:8]}",
        display_name="Authz delete probe",
        workflow_scope="STANDARD",
        role_kind="operational",
        role_origin="custom",
    )
    db.add(role)
    db.commit()
    role_id = role.role_id
    db.close()

    try:
        for persona in ("non_admin", "officer"):
            try:
                status = _admin_client(LADDER[persona]).delete(
                    f"/api/v1/roles/{role_id}"
                ).status_code
            finally:
                app.dependency_overrides.clear()
            assert status == 403, f"{persona} must be 403 deleting a custom role (got {status})"

        check = SessionLocal()
        try:
            assert check.get(Role, role_id) is not None, "role must survive the denied deletes"
        finally:
            check.close()
    finally:
        cleanup = SessionLocal()
        try:
            r = cleanup.get(Role, role_id)
            if r:
                cleanup.delete(r)
                cleanup.commit()
        finally:
            cleanup.close()


@pytest.mark.parametrize("persona_name", ["org_std", "org_seah", "project", "officer", "non_admin"])
def test_platform_settings_super_only_at_route(persona_name):
    """PUT /settings/{super-only key} rejects every non-super tier — the inline
    ``require_settings_write(PLATFORM_SETTINGS)`` fires (403) before any write. 'org_roles'
    ∈ SUPER_ADMIN_ONLY_KEYS. super is covered by the predicate matrix (would write)."""
    try:
        status = _admin_client(LADDER[persona_name]).put(
            "/api/v1/settings/org_roles", json={"value": {}}
        ).status_code
    finally:
        app.dependency_overrides.clear()
    assert status == 403, f"{persona_name} must be denied platform settings (got {status})"


# ══════════════════════════════════════════════════════════════════════════════
# Part 3 — unauthenticated sweep
# ══════════════════════════════════════════════════════════════════════════════

# Real Keycloak posture (bypass OFF): a request with no token must be refused by the
# auth dependency (401), never resolved to the dev mock super_admin.
_PROD_AUTH = TicketingSettings(
    app_env="production",
    auth_mode="keycloak",
    keycloak_issuer="http://kc/realms/grm",
    ticketing_secret_key="sweep-secret",
)

# Public / non-JWT routes to skip (spec §2 known-public set + the API-key intake pair).
# Skipped by exact (method, path) or path predicate because every router mounts at /api/v1.
_APIKEY_ROUTES = {
    ("POST", "/api/v1/tickets"),                         # verify_api_key (chatbot intake)
    ("POST", "/api/v1/tickets/{ticket_id}/inbound"),     # verify_api_key (complainant follow-up)
}


def _is_public(method: str, path: str) -> bool:
    if path == "/health":
        return True
    if path.startswith("/api/v1/auth/"):          # login / password reset — establish auth
        return True
    if path.startswith("/api/v1/scan/"):          # public QR scan (mgmt qr-token routes are NOT here)
        return True
    if path.startswith("/api/v1/public/"):        # public closure / report by token
        return True
    if "webhook" in path:                         # keycloak webhook — its own shared secret
        return True
    if (method, path) in _APIKEY_ROUTES:
        return True
    return False


# authz-gaps-h2-03 #1 — the remaining intentionally-public reads on the locations/projects
# router: geography reference data + static import templates. The project-CONFIG reads
# (projects, projects/{id}, and every project sub-resource) were locked to
# `get_authenticated_user` on 2026-07-15, so they are no longer here. The sweep asserts
# `served ⊆ this set`: it fails if a NEW unauthenticated endpoint appears, and it would fail
# if any project-config read regressed to public.
_KNOWN_UNAUTH_READS = {
    ("GET", "/api/v1/countries"),
    ("GET", "/api/v1/locations"),
    ("GET", "/api/v1/locations/import/template.csv"),
    ("GET", "/api/v1/locations/import/template.json"),
    ("GET", "/api/v1/locations/{location_code}"),
}


@pytest.fixture
def prod_auth(monkeypatch):
    monkeypatch.setattr(main_mod, "get_settings", lambda: _PROD_AUTH)
    monkeypatch.setattr(deps, "get_settings", lambda: _PROD_AUTH)
    yield


def _protected_routes() -> list[tuple[str, str]]:
    schema = app.openapi()
    out: list[tuple[str, str]] = []
    for path, ops in schema.get("paths", {}).items():
        for method in ops:
            m = method.upper()
            if m not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
                continue
            if _is_public(m, path):
                continue
            out.append((m, path))
    return sorted(set(out))


def _concretize(path: str) -> str:
    while "{" in path:
        path = path[:path.index("{")] + "sweep" + path[path.index("}") + 1:]
    return path


def test_unauthenticated_sweep_no_new_holes(prod_auth):
    """Under real Keycloak auth, a request with no token must be refused (401/403) by
    every protected route — except the quarantined, already-known unauthenticated reads
    in ``_KNOWN_UNAUTH_READS``. A NEW unauthenticated endpoint fails this test."""
    routes = _protected_routes()
    assert routes, "sweep found no protected routes — openapi introspection changed?"
    served: set[tuple[str, str]] = set()
    with TestClient(app) as client:
        for method, path in routes:
            body = {} if method in ("POST", "PUT", "PATCH") else None
            resp = client.request(method, _concretize(path), json=body)
            if resp.status_code not in (401, 403):
                served.add((method, path))
    new_holes = served - _KNOWN_UNAUTH_READS
    assert not new_holes, (
        "NEW unauthenticated endpoint(s) — protected routes must return 401/403 with no "
        "token:\n  " + "\n  ".join(f"{m} {p}" for m, p in sorted(new_holes))
    )


def test_sweep_positive_control(prod_auth):
    """Guard against the sweep silently becoming a no-op: representative protected
    endpoints (a ticket read, an admin mutation) really do 401 with no token."""
    with TestClient(app) as client:
        assert client.get("/api/v1/tickets").status_code == 401
        assert client.post("/api/v1/users/invite", json={}).status_code == 401
        assert client.post("/api/v1/admin-scopes", json={}).status_code == 401
