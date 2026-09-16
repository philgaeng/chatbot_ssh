"""
T3-06 step 2 — read audit for GET /api/grievance/{id}.

Before this, `grep -il audit backend/` returned exactly one file and there was no
read-audit anywhere: a successful grievance read left no trace. base_manager's
log_grievance_change is write-only.

The level assertions are the point of this file, not ceremony. LOG_LEVEL=INFO is the
deployed default (env.local:23), so a .debug audit record would be invisible in
production — which is exactly how grievance_manager.py:172 already fails to be a
trail. Every test here pins the audit at the level it must survive.
"""

import json
import logging
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.api.fastapi_app import app
from backend.api.routers.grievance import _principal_for_key

AUDIT_LOGGER = "audit.grievance_read"
DEPLOYED_LEVEL = logging.INFO  # env.local:23

GRIEVANCE = {"grievance_id": "B-GR-AUDIT-TEST", "grievance_summary": "s"}

# The GET requires x-api-key since T3-06 step 3. Pin a key and send it so these
# assert auditing rather than auth, and stay deterministic regardless of ambient
# config — un-pinned they pass on a host via the env.local dev bypass but 401 in CI.
KEY = "audit-test-key"
AUTH = {"x-api-key": KEY}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def keyed():
    with patch.dict("os.environ", {"TICKETING_SECRET_KEY": KEY, "MESSAGING_API_KEY": ""}):
        yield


def _audit_records(caplog):
    out = []
    for rec in caplog.records:
        if rec.name != AUDIT_LOGGER:
            continue
        out.append(json.loads(rec.getMessage().split(" ", 1)[1]))
    return out


def test_successful_read_emits_audit_at_deployed_level(client, caplog):
    """A disclosed grievance must leave a record that survives LOG_LEVEL=INFO."""
    with caplog.at_level(DEPLOYED_LEVEL, logger=AUDIT_LOGGER):
        with patch(
            "backend.api.routers.grievance.grievance_manager.get_grievance_by_id",
            return_value=GRIEVANCE,
        ), patch(
            "backend.api.routers.grievance.grievance_manager.get_grievance_status_history",
            return_value=[],
        ), patch(
            "backend.api.routers.grievance.grievance_manager.get_grievance_files",
            return_value=[],
        ), patch(
            "backend.api.routers.grievance.grievance_manager.get_grievance_status",
            return_value=None,
        ):
            r = client.get("/api/grievance/B-GR-AUDIT-TEST", headers=AUTH)

    assert r.status_code == 200
    records = _audit_records(caplog)
    assert len(records) == 1
    assert records[0]["grievance_id"] == "B-GR-AUDIT-TEST"
    assert records[0]["outcome"] == "success"
    assert records[0]["at"]


def test_audit_record_is_not_debug_level(client, caplog):
    """
    The regression this guards: an audit emitted at DEBUG is silently absent in
    prod. Capture at INFO only — a DEBUG record would not appear.
    """
    with caplog.at_level(DEPLOYED_LEVEL, logger=AUDIT_LOGGER):
        with patch(
            "backend.api.routers.grievance.grievance_manager.get_grievance_by_id",
            return_value=None,
        ):
            client.get("/api/grievance/B-GR-MISSING", headers=AUTH)

    records = [r for r in caplog.records if r.name == AUDIT_LOGGER]
    assert records, "no audit record emitted at the deployed LOG_LEVEL=INFO"
    assert all(r.levelno >= DEPLOYED_LEVEL for r in records)


def test_audit_carries_caller_identity(client, caplog):
    """
    'Someone read GRV-x' is not an audit trail. The principal must be in the record.
    """
    with patch.dict("os.environ", {"TICKETING_SECRET_KEY": "sekret-key"}):
        with caplog.at_level(DEPLOYED_LEVEL, logger=AUDIT_LOGGER):
            with patch(
                "backend.api.routers.grievance.grievance_manager.get_grievance_by_id",
                return_value=None,
            ):
                client.get(
                    "/api/grievance/B-GR-MISSING", headers={"x-api-key": "sekret-key"}
                )

    assert _audit_records(caplog)[0]["principal"] == "ticketing"


def test_audit_never_contains_the_api_key(client, caplog):
    """The trail records who called, never the secret they called with."""
    with patch.dict("os.environ", {"TICKETING_SECRET_KEY": "super-secret-value"}):
        with caplog.at_level(DEPLOYED_LEVEL, logger=AUDIT_LOGGER):
            with patch(
                "backend.api.routers.grievance.grievance_manager.get_grievance_by_id",
                return_value=None,
            ):
                client.get(
                    "/api/grievance/B-GR-MISSING",
                    headers={"x-api-key": "super-secret-value"},
                )

    for rec in caplog.records:
        assert "super-secret-value" not in rec.getMessage()


def test_not_found_read_is_audited(client, caplog):
    """A probe for a grievance that does not exist is still an access attempt."""
    with caplog.at_level(DEPLOYED_LEVEL, logger=AUDIT_LOGGER):
        with patch(
            "backend.api.routers.grievance.grievance_manager.get_grievance_by_id",
            return_value=None,
        ):
            r = client.get("/api/grievance/B-GR-NOPE", headers=AUTH)

    assert r.status_code == 404
    assert _audit_records(caplog)[0]["outcome"] == "not_found"


def test_failed_read_is_audited(client, caplog):
    """An error path must not swallow the record — a 500 is still an attempt."""
    with caplog.at_level(DEPLOYED_LEVEL, logger=AUDIT_LOGGER):
        with patch(
            "backend.api.routers.grievance.grievance_manager.get_grievance_by_id",
            side_effect=RuntimeError("db down"),
        ):
            r = client.get("/api/grievance/B-GR-BOOM", headers=AUTH)

    assert r.status_code == 500
    assert _audit_records(caplog)[0]["outcome"] == "error"


@pytest.mark.parametrize(
    "env, key, expected",
    [
        ({"TICKETING_SECRET_KEY": "tkt"}, "tkt", "ticketing"),
        ({"MESSAGING_API_KEY": "msg"}, "msg", "messaging"),
        ({"TICKETING_SECRET_KEY": "tkt"}, "wrong", "unrecognized-key"),
        ({"TICKETING_SECRET_KEY": "tkt"}, None, "anonymous"),
        ({"TICKETING_SECRET_KEY": "tkt"}, "   ", "anonymous"),
    ],
)
def test_principal_resolution(env, key, expected):
    with patch.dict("os.environ", env, clear=True):
        assert _principal_for_key(key) == expected


def test_non_ascii_key_does_not_raise():
    """
    hmac.compare_digest raises TypeError on non-ASCII *str*, and x-api-key is
    caller-controlled (Starlette decodes headers as latin-1). Comparing as bytes
    keeps this a clean "unrecognized-key" instead of a 500. Verified red: with
    str comparison this raises TypeError.
    """
    with patch.dict("os.environ", {"TICKETING_SECRET_KEY": "ascii-key"}, clear=True):
        assert _principal_for_key("café") == "unrecognized-key"
        assert _principal_for_key("ключ") == "unrecognized-key"


def test_non_ascii_configured_key_does_not_raise():
    """The mirror case: a non-ASCII key in the environment must not crash either."""
    with patch.dict("os.environ", {"TICKETING_SECRET_KEY": "café-key"}, clear=True):
        assert _principal_for_key("café-key") == "ticketing"
        assert _principal_for_key("other") == "unrecognized-key"


def test_unset_key_does_not_match_empty_header():
    """
    An unconfigured env var must not make every caller look like 'ticketing'.
    Empty-vs-empty is the classic way a key check silently passes.
    """
    with patch.dict("os.environ", {"TICKETING_SECRET_KEY": ""}, clear=True):
        assert _principal_for_key("") == "anonymous"
        assert _principal_for_key("anything") == "unrecognized-key"
