"""SH-2 — workflow step role validation (OC-06 F2).

Step role references (assigned / supervisor / informed / observer) must resolve to an
existing role whose workflow_scope matches the workflow track.

The core logic is unit-tested with a fake session so it runs in CI and does NOT depend
on the DB seed carrying scopes (the current dev seed leaves workflow_scope NULL). A
single integration smoke proves the real SQLAlchemy query path.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from ticketing.models.user import Role
from ticketing.services.role_scope import role_scope_matches_track, validate_step_roles


# --- predicate matrix (CI) ---

@pytest.mark.parametrize(
    "scope,track,ok",
    [
        ("Standard", "standard", True),
        ("Standard", "seah", False),
        ("SEAH", "seah", True),
        ("SEAH", "standard", False),
        ("Both", "standard", True),
        ("Both", "seah", True),
        (None, "standard", True),   # unscoped role valid on any track (mirrors list_roles)
        (None, "seah", True),
    ],
)
def test_role_scope_matches_track(scope, track, ok):
    assert role_scope_matches_track(scope, track) is ok


# --- validate_step_roles logic (CI, via a fake session) ---

class _FakeResult:
    def __init__(self, roles):
        self._roles = roles

    def scalars(self):
        return self

    def all(self):
        return self._roles


class _FakeDB:
    """Returns the given in-memory Role rows for any select — no real DB needed."""

    def __init__(self, roles):
        self._roles = roles

    def execute(self, _stmt):
        return _FakeResult(self._roles)


def _role(key, scope):
    return Role(role_key=key, workflow_scope=scope, role_kind="operational")


def test_valid_standard_binding_passes():
    db = _FakeDB([_role("sfp", "Standard")])
    validate_step_roles(db, workflow_type="standard", assigned_role_key="sfp")  # no raise


def test_seah_workflow_accepts_seah_and_both():
    db = _FakeDB([_role("seah_off", "SEAH"), _role("exec", "Both")])
    validate_step_roles(
        db, workflow_type="seah", assigned_role_key="seah_off", supervisor_role="exec"
    )  # no raise


def test_nonexistent_role_rejected():
    db = _FakeDB([])  # catalog empty → key not found
    with pytest.raises(HTTPException) as exc:
        validate_step_roles(db, workflow_type="standard", assigned_role_key="ghost")
    assert exc.value.status_code == 422
    assert "does not exist" in exc.value.detail


def test_wrong_track_assigned_rejected():
    db = _FakeDB([_role("seah_off", "SEAH")])
    with pytest.raises(HTTPException) as exc:
        validate_step_roles(db, workflow_type="standard", assigned_role_key="seah_off")
    assert exc.value.status_code == 422
    assert "track" in exc.value.detail.lower()


def test_wrong_track_supervisor_rejected():
    db = _FakeDB([_role("sfp", "Standard"), _role("seah_off", "SEAH")])
    with pytest.raises(HTTPException) as exc:
        validate_step_roles(
            db, workflow_type="standard", assigned_role_key="sfp", supervisor_role="seah_off"
        )
    assert exc.value.status_code == 422
    assert "supervisor" in exc.value.detail.lower()


def test_wrong_track_informed_role_rejected():
    db = _FakeDB([_role("sfp", "Standard"), _role("seah_off", "SEAH")])
    with pytest.raises(HTTPException) as exc:
        validate_step_roles(
            db, workflow_type="standard", assigned_role_key="sfp", informed_roles=["seah_off"]
        )
    assert exc.value.status_code == 422
    assert "informed" in exc.value.detail.lower()


def test_empty_refs_are_noop():
    db = _FakeDB([])
    validate_step_roles(db, workflow_type="standard", assigned_role_key="")  # draft step
    validate_step_roles(
        db, workflow_type="standard", assigned_role_key=None, informed_roles=[], observer_roles=[]
    )


# --- real DB query path (integration) ---

@pytest.mark.integration
def test_real_db_query_path():
    """Proves the select-by-key path against the live catalog: a real role passes, a
    made-up key 422s. (Scope enforcement is covered by the CI unit tests above; the
    current dev seed leaves workflow_scope NULL, so it can't exercise wrong-track here.)"""
    from ticketing.models.base import SessionLocal

    db = SessionLocal()
    try:
        validate_step_roles(
            db, workflow_type="standard", assigned_role_key="site_safeguards_focal_person"
        )
        with pytest.raises(HTTPException) as exc:
            validate_step_roles(db, workflow_type="standard", assigned_role_key="no_such_role_xyz")
        assert exc.value.status_code == 422
    finally:
        db.close()
