"""
T3-04 step 2 — `get_grievance_by_id` must decrypt server-side.

The defect the review misdiagnosed. It claimed ticketing had a second, unauthorised
path to PII and prescribed deleting ticketing's key. In fact there is only one fetch
path; what is split is *decryption responsibility*:

    get_grievance_by_id -> _parse_database_result   (base_manager.py) -> JSON parse only
    get_grievance_by_complainant_phone:537          -> _decrypt_sensitive_data -> plaintext

So `GET /api/grievance/{id}` hands out pgcrypto hex for the four ENCRYPTED_FIELDS, and
`ticketing/services/pii_vault.py` decrypts client-side to compensate — a client-side
workaround for a server-side omission, which is why ticketing needed DB_ENCRYPTION_KEY
at all. CLAUDE.md's "Grievance API … handles PII decryption" was aspirational, not true.

These tests use a **real pgcrypto round-trip** (encrypt with the manager's own key, then
read back through the manager) rather than a hand-written fake ciphertext. A fake would
prove only that some string changed; this proves the value the chatbot encrypted is the
value an API caller gets back.

Verified red pre-fix: `test_get_grievance_by_id_decrypts_complainant_fields` returns hex
ciphertext for all four fields on unmodified code.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.services.database_services.grievance_manager import GrievanceDbManager

PLAINTEXT = {
    "complainant_full_name": "Sita Rai",
    "complainant_phone": "+9779812345678",
    "complainant_email": "sita.rai@example.np",
    "complainant_address": "Ward 4, Birtamod, Jhapa",
}


@pytest.fixture(scope="module")
def manager() -> GrievanceDbManager:
    """
    The class the router actually instantiates (`grievance.py:36`). Note
    `postgres_services.DatabaseManager.get_grievance_by_id:795` merely delegates here,
    so this is the single place the fix has to land to cover both entry points.
    """
    return GrievanceDbManager()


@pytest.fixture(scope="module")
def encrypted_row(manager) -> dict:
    """
    A JOINed row shaped exactly like get_grievance_by_id's SELECT, with the four
    encrypted columns holding real pgcrypto ciphertext produced by the manager itself.
    """
    row = {
        "grievance_id": "B-GR-T304-DECRYPT",
        "grievance_description": "Dust from the road is making the children sick.",
        "complainant_district": "Jhapa",
        "party_role": "complainant",
        "is_primary_reporter": True,
    }
    row.update({field: manager._encrypt_field(value) for field, value in PLAINTEXT.items()})
    return row


def test_the_fixture_really_is_encrypted(encrypted_row):
    """
    Guard the guard. If _encrypt_field silently passed the value through (no key
    configured, say), every assertion below would be vacuous — the "decrypted" value
    would match because it was never encrypted.
    """
    for field, plain in PLAINTEXT.items():
        assert encrypted_row[field] != plain, f"{field} was never encrypted — fixture is vacuous"
        assert all(c in "0123456789abcdefABCDEF" for c in encrypted_row[field]), (
            f"{field} is not hex — the fixture is not pgcrypto ciphertext"
        )


def test_get_grievance_by_id_decrypts_complainant_fields(manager, encrypted_row):
    """
    THE fix's test. Verified red pre-fix: today the four fields come back as hex.

    execute_query is mocked so this exercises the decryption wiring on a known row
    without depending on (or mutating) seeded data. _decrypt_sensitive_data still does
    a real pgp_sym_decrypt against the database.
    """
    with patch.object(manager, "execute_query", return_value=[dict(encrypted_row)]):
        result = manager.get_grievance_by_id("B-GR-T304-DECRYPT")

    assert result is not None
    for field, expected in PLAINTEXT.items():
        assert result[field] == expected, (
            f"{field} was not decrypted server-side — API callers get ciphertext, which is "
            f"exactly what pii_vault.py exists to work around. Got: {result[field]!r}"
        )


def test_get_grievance_by_id_leaves_non_encrypted_fields_alone(manager, encrypted_row):
    """Decryption must not disturb the rest of the JOINed row."""
    with patch.object(manager, "execute_query", return_value=[dict(encrypted_row)]):
        result = manager.get_grievance_by_id("B-GR-T304-DECRYPT")

    assert result["grievance_id"] == "B-GR-T304-DECRYPT"
    assert result["grievance_description"] == "Dust from the road is making the children sick."
    assert result["complainant_district"] == "Jhapa"


def test_get_grievance_by_id_is_idempotent_on_plaintext(manager):
    """
    The blast-radius guard, and the most likely way this ticket breaks the chatbot.

    ~20 non-test callers read this method. If a row ever holds plaintext in an
    ENCRYPTED_FIELDS column (legacy rows, a fixture, a partially-migrated record),
    decrypting it must not corrupt or drop it. pgcrypto raises on non-hex input
    ("invalid hexadecimal digit"), which the manager catches and falls back from,
    returning the original value — so plaintext must survive a decrypt attempt intact.
    """
    plain_row = {"grievance_id": "B-GR-T304-PLAIN", **PLAINTEXT}

    with patch.object(manager, "execute_query", return_value=[dict(plain_row)]):
        result = manager.get_grievance_by_id("B-GR-T304-PLAIN")

    for field, expected in PLAINTEXT.items():
        assert result[field] == expected, (
            f"{field} was corrupted by decrypting already-plaintext data — this would "
            f"break callers that render it to the user"
        )


def test_get_grievance_core_by_id_needs_no_decryption(manager):
    """
    The fallback path (grievance_manager.py:181), checked rather than assumed per the
    spec. It reads `SELECT * FROM grievances`, and public.grievances carries none of
    the four ENCRYPTED_FIELDS columns (they live on public.complainants) — verified
    against the live schema. So it returns no encrypted fields and needs no treatment.
    """
    core_row = {
        "grievance_id": "B-GR-T304-CORE",
        "grievance_description": "narrative",
    }
    with patch.object(manager, "execute_query", return_value=[dict(core_row)]):
        result = manager.get_grievance_core_by_id("B-GR-T304-CORE")

    assert result == core_row
    for field in PLAINTEXT:
        assert field not in result, (
            f"{field} appeared in the core read — the fallback now returns complainant "
            f"columns and would need decrypting too"
        )
