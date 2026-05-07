"""Tests for QR-token / ticketing scan integration in the chatbot intake flow.

Covers:
- fetch_qr_scan() — happy path, 404/410 fallthrough, network error
- resolve_location_code_to_names() — district + parent province resolution
- dispatch_ticket() — package_id is forwarded in the POST payload
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.actions.utils.ticketing_dispatch import dispatch_ticket, fetch_qr_scan
from backend.shared_functions.location_mapping import resolve_location_code_to_names


def _stub_response(status_code: int, body):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    resp.text = str(body)
    return resp


# ---------------------------------------------------------------------------
# fetch_qr_scan
# ---------------------------------------------------------------------------

def test_fetch_qr_scan_returns_parsed_payload_on_200():
    payload = {
        "project_code": "KL_ROAD",
        "package_id": "SHEP-OCB-KL-01",
        "location_code": "NP_D004",
        "label": "Lot 1 — Kakarbhitta to Sitapur",
    }
    with patch(
        "backend.actions.utils.ticketing_dispatch.requests.get",
        return_value=_stub_response(200, payload),
    ) as mock_get:
        result = fetch_qr_scan("a3f9b2c1")

    assert result == payload
    assert mock_get.call_args.args[0].endswith("/api/v1/scan/a3f9b2c1")


def test_fetch_qr_scan_returns_none_on_404():
    with patch(
        "backend.actions.utils.ticketing_dispatch.requests.get",
        return_value=_stub_response(404, {"detail": "invalid_token"}),
    ):
        assert fetch_qr_scan("badtoken") is None


def test_fetch_qr_scan_returns_none_on_410():
    with patch(
        "backend.actions.utils.ticketing_dispatch.requests.get",
        return_value=_stub_response(410, {"detail": "invalid_token"}),
    ):
        assert fetch_qr_scan("expired") is None


def test_fetch_qr_scan_returns_none_on_network_error():
    with patch(
        "backend.actions.utils.ticketing_dispatch.requests.get",
        side_effect=RuntimeError("boom"),
    ):
        assert fetch_qr_scan("anything") is None


@pytest.mark.parametrize("bad_token", [None, "", "   ", "x" * 65, 123])
def test_fetch_qr_scan_short_circuits_invalid_token(bad_token):
    with patch(
        "backend.actions.utils.ticketing_dispatch.requests.get"
    ) as mock_get:
        result = fetch_qr_scan(bad_token)
    assert result is None
    mock_get.assert_not_called()


def test_fetch_qr_scan_normalizes_sentinel_values():
    payload = {
        "project_code": "",
        "package_id": "NOT_PROVIDED",
        "location_code": "NP_D004",
        "label": "Lot 1",
    }
    with patch(
        "backend.actions.utils.ticketing_dispatch.requests.get",
        return_value=_stub_response(200, payload),
    ):
        result = fetch_qr_scan("a3f9b2c1")
    assert result == {
        "project_code": None,
        "package_id": None,
        "location_code": "NP_D004",
        "label": "Lot 1",
    }


# ---------------------------------------------------------------------------
# resolve_location_code_to_names
# ---------------------------------------------------------------------------

class _LocationDb:
    def __init__(self, rows):
        self._rows = rows

    def execute_query(self, query, params, operation=None):
        return self._rows


def test_resolve_location_code_to_names_district_and_province():
    db = _LocationDb([
        {
            "location_code": "NP_D004",
            "parent_location_code": "NP_P1",
            "level_number": 2,
            "name": "Jhapa",
            "parent_name": "Koshi",
            "parent_code": "NP_P1",
        }
    ])
    out = resolve_location_code_to_names(db, "NP_D004")
    assert out == {
        "district_code": "NP_D004",
        "district_name": "Jhapa",
        "province_code": "NP_P1",
        "province_name": "Koshi",
    }


def test_resolve_location_code_to_names_province_only():
    db = _LocationDb([
        {
            "location_code": "NP_P1",
            "parent_location_code": None,
            "level_number": 1,
            "name": "Koshi",
            "parent_name": None,
            "parent_code": None,
        }
    ])
    out = resolve_location_code_to_names(db, "NP_P1")
    assert out["province_code"] == "NP_P1"
    assert out["province_name"] == "Koshi"
    assert out["district_code"] is None
    assert out["district_name"] is None


def test_resolve_location_code_to_names_unknown_code():
    db = _LocationDb([])
    out = resolve_location_code_to_names(db, "NP_X999")
    assert out == {
        "district_code": None,
        "district_name": None,
        "province_code": None,
        "province_name": None,
    }


def test_resolve_location_code_to_names_swallows_db_errors():
    class _Boom:
        def execute_query(self, *args, **kwargs):
            raise RuntimeError("db down")

    out = resolve_location_code_to_names(_Boom(), "NP_D004")
    assert out["district_code"] is None
    assert out["province_code"] is None


def test_resolve_location_code_to_names_handles_empty_input():
    db = _LocationDb([{"location_code": "x"}])
    out = resolve_location_code_to_names(db, "")
    assert out["district_code"] is None
    assert out["province_code"] is None


# ---------------------------------------------------------------------------
# dispatch_ticket forwards package_id
# ---------------------------------------------------------------------------

def test_dispatch_ticket_forwards_package_id():
    with patch(
        "backend.actions.utils.ticketing_dispatch.requests.post",
        return_value=_stub_response(200, {"ticket_id": "TKT-1"}),
    ) as mock_post:
        dispatch_ticket(
            grievance_id="GRV-001",
            complainant_id="C1",
            session_id="S1",
            is_seah=False,
            priority="NORMAL",
            location_code="NP_D004",
            project_code="KL_ROAD",
            grievance_summary="dust",
            package_id="SHEP-OCB-KL-01",
        )

    assert mock_post.call_count == 1
    body = mock_post.call_args.kwargs["json"]
    assert body["package_id"] == "SHEP-OCB-KL-01"
    assert body["project_code"] == "KL_ROAD"
    assert body["location_code"] == "NP_D004"


def test_dispatch_ticket_omits_package_id_when_absent():
    with patch(
        "backend.actions.utils.ticketing_dispatch.requests.post",
        return_value=_stub_response(200, {"ticket_id": "TKT-2"}),
    ) as mock_post:
        dispatch_ticket(
            grievance_id="GRV-002",
            complainant_id="C2",
            session_id="S2",
            is_seah=False,
            priority="NORMAL",
            location_code=None,
            project_code="KL_ROAD",
            grievance_summary=None,
        )

    body = mock_post.call_args.kwargs["json"]
    assert body["package_id"] is None
