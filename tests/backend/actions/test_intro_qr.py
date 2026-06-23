"""Characterization tests for the extracted intro payload + QR helpers."""

from backend.actions.services.intro import qr as intro_qr


def test_parse_introduce_payload_extracts_json():
    msg = '/introduce{"province":"Koshi","district":"Jhapa","t":"abc","flask_session_id":"s1"}'
    data = intro_qr.parse_introduce_payload(msg)
    assert data == {
        "province": "Koshi",
        "district": "Jhapa",
        "t": "abc",
        "flask_session_id": "s1",
    }


def test_parse_introduce_payload_no_json_returns_empty():
    assert intro_qr.parse_introduce_payload("/introduce") == {}
    assert intro_qr.parse_introduce_payload("") == {}


def test_parse_introduce_payload_malformed_returns_empty():
    assert intro_qr.parse_introduce_payload("/introduce{not json}") == {}


def test_resolve_qr_token_empty_when_no_token():
    assert intro_qr.resolve_qr_token(db_manager=None, token="") == {}


def test_resolve_qr_token_unresolved_scan(monkeypatch):
    monkeypatch.setattr(intro_qr, "fetch_qr_scan", lambda token: None)
    assert intro_qr.resolve_qr_token(db_manager=None, token="missing") == {}


def test_resolve_qr_token_builds_bundle(monkeypatch):
    monkeypatch.setattr(
        intro_qr,
        "fetch_qr_scan",
        lambda token: {
            "location_code": "LC1",
            "package_id": "P1",
            "label": "Package One",
            "project_code": "PR1",
        },
    )
    monkeypatch.setattr(
        intro_qr,
        "resolve_location_code_to_names",
        lambda db, code: {"province_name": "Koshi", "district_name": "Jhapa"},
    )
    bundle = intro_qr.resolve_qr_token(db_manager=object(), token="tok")
    assert bundle == {
        "qr_token": "tok",
        "package_id": "P1",
        "package_label": "Package One",
        "project_code": "PR1",
        "location_code": "LC1",
        "complainant_province": "Koshi",
        "complainant_district": "Jhapa",
    }
