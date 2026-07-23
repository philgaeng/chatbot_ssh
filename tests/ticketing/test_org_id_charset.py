"""SH-6 — organization_id is ASCII-only, consistently on both paths (OC-06 F1).

str.isalnum() is True for Devanagari, so the old derivation minted Devanagari ids
(e.g. 'NP_सव') while the explicit-id sanitize did the same. Ids are now ASCII-only;
Nepali lives in the org name / display_name_ne. A pure-Devanagari name derives to empty,
so the server asks for an explicit (ASCII) id instead of minting a non-ASCII one.
"""
from __future__ import annotations

import pytest

from ticketing.utils.organization_identifier import (
    ascii_alnum,
    slug_core_from_name,
    suggested_organization_id,
)


# --- derivation logic (CI) ---

def test_ascii_alnum_drops_non_ascii():
    assert ascii_alnum("सडक") == ""
    assert ascii_alnum("NP_सव2", keep_underscore=True) == "NP_2"
    assert ascii_alnum("NP_सव2") == "NP2"          # underscore dropped when not kept
    assert ascii_alnum("Road-Dept", keep_underscore=True) == "RoadDept"


def test_pure_devanagari_name_derives_empty():
    assert slug_core_from_name("सडक विभाग") == ""
    assert suggested_organization_id("सडक विभाग", "NP") == ""


def test_ascii_name_derives_ascii_id():
    sid = suggested_organization_id("Department of Roads", "NP")
    assert sid and sid.isascii() and sid.isupper()   # e.g. NP_DOR


def test_mixed_name_uses_ascii_part_only():
    sid = suggested_organization_id("सडक DOR", "NP")
    assert sid and sid.isascii()
    assert "DOR" in sid


# --- route policy (integration) ---

@pytest.mark.integration
def test_create_org_rejects_devanagari_id_paths():
    from fastapi.testclient import TestClient

    from ticketing.api.dependencies import CurrentUser, get_authenticated_user, get_db
    from ticketing.api.main import app
    from ticketing.models.base import SessionLocal

    db = SessionLocal()

    def _db():
        yield db

    app.dependency_overrides[get_authenticated_user] = lambda: CurrentUser(
        user_id="s@grm.local", role_keys=["super_admin"]
    )
    app.dependency_overrides[get_db] = _db
    try:
        client = TestClient(app)
        # derived path: a pure-Devanagari name can't derive an ASCII id → 400 (ask for explicit)
        res = client.post("/api/v1/organizations", json={"name": "सडक विभाग", "country_code": "NP"})
        assert res.status_code == 400, res.text
        # explicit path: a Devanagari id sanitizes to empty → 400 (no NP_सव minted)
        res2 = client.post(
            "/api/v1/organizations", json={"name": "Road Dept", "organization_id": "सडक"}
        )
        assert res2.status_code == 400, res2.text
    finally:
        app.dependency_overrides.clear()
        db.close()
