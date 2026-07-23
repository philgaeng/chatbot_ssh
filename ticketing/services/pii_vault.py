"""
PII masking helpers for the ticketing API broker.

Since T3-04 the grievance backend decrypts complainant PII server-side
(`get_grievance_by_id`), so `GET /api/grievance/{id}` returns plaintext and ticketing
holds no decryption key. This module no longer decrypts anything: it shapes the officer
card and the reveal payload, and it fails closed if ciphertext ever turns up.

History, because the shape here is otherwise puzzling: this module used to carry its own
pgcrypto decrypt (`decrypt_ciphertext` / `reveal_field`) using ticketing's own
DB_ENCRYPTION_KEY. That was a client-side workaround for a server-side omission — the
backend returned hex — and it is what made the "ticketing has a second PII path" reading
look true. It never had one: it decrypted a ciphertext already handed to it by the API.
T3-04 fixed the cause in `backend/services/database_services/grievance_manager.py` and
deleted the workaround. See docs/sprints/archive/2026-08_tier3_structural/03-pii-boundary-spec.md.
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# pgcrypto symmetric ciphertext stored as hex often starts with this prefix.
_CIPHERTEXT_HEX = re.compile(r"^[0-9a-f]{40,}$", re.IGNORECASE)

PII_FIELD_MAP: dict[str, str] = {
    "complainant_full_name": "complainant_name",
    "complainant_phone": "phone_number",
    "complainant_email": "email",
    "complainant_address": "address",
}


def looks_like_ciphertext(value: Any) -> bool:
    if value is None:
        return False
    if not isinstance(value, str):
        return False
    s = value.strip()
    if len(s) < 40:
        return False
    return bool(_CIPHERTEXT_HEX.match(s))


def scrub_pii_value(value: Any) -> Any:
    """
    Defense in depth — an assertion, not a masking behaviour.

    Before T3-04 this silently mapped ciphertext to None, which is how the review's
    prescribed order (drop ticketing's key first) would have produced "—" on every
    officer contact card with no error and no failing test.

    The backend now decrypts, so ciphertext reaching here means something upstream
    regressed: the backend stopped decrypting, or lost DB_ENCRYPTION_KEY. Fail closed —
    an officer must never be shown hex — but say so loudly rather than degrading in
    silence. The value itself is never logged.
    """
    if looks_like_ciphertext(value):
        logger.error(
            "pii_vault: ciphertext reached the officer card. Since T3-04 the backend "
            "decrypts server-side, so this means get_grievance_by_id stopped decrypting "
            "or the backend lost DB_ENCRYPTION_KEY. Returning None (fail closed)."
        )
        return None
    return value


def grievance_pii_masked(grievance: dict[str, Any]) -> dict[str, Any]:
    """Safe subset for default officer UI — never includes ciphertext."""
    return {
        "complainant_name": scrub_pii_value(grievance.get("complainant_full_name")),
        "phone_number": scrub_pii_value(grievance.get("complainant_phone")),
        "email": scrub_pii_value(grievance.get("complainant_email")),
        "address": scrub_pii_value(grievance.get("complainant_address")),
        "village": grievance.get("complainant_village"),
        "ward": grievance.get("complainant_ward"),
        "municipality": grievance.get("complainant_municipality"),
        "district": grievance.get("complainant_district"),
        "province": grievance.get("complainant_province"),
        "location_geo": grievance.get("location_geo"),
    }


def _officer_card_identity(value: Any) -> Any:
    """Normalise one identity field for the standard GRM card; placeholders => empty."""
    plain = scrub_pii_value(value)
    if plain is None:
        return None
    s = str(plain).strip()
    if not s or s.lower() in {"not provided", "unknown", "n/a", "na", "anonymous"}:
        return None
    return s


def grievance_pii_for_officer_card(
    grievance: dict[str, Any],
    *,
    mask_sensitive_contact: bool,
) -> dict[str, Any]:
    """
    Officer complainant card: standard GRM shows the contact fields as the backend
    returned them; SEAH keeps name/phone/email/address out of the default API (vault
    reveal only).
    """
    if mask_sensitive_contact:
        data = grievance_pii_masked(grievance)
        data["complainant_name"] = None
        data["phone_number"] = None
        data["email"] = None
        data["address"] = None
        return data

    return {
        "complainant_name": _officer_card_identity(grievance.get("complainant_full_name")),
        "phone_number": _officer_card_identity(grievance.get("complainant_phone")),
        "email": _officer_card_identity(grievance.get("complainant_email")),
        "address": _officer_card_identity(grievance.get("complainant_address")),
        "village": grievance.get("complainant_village"),
        "ward": grievance.get("complainant_ward"),
        "municipality": grievance.get("complainant_municipality"),
        "district": grievance.get("complainant_district"),
        "province": grievance.get("complainant_province"),
        "location_geo": grievance.get("location_geo"),
    }


def grievance_reveal_content(grievance: dict[str, Any]) -> dict[str, Any]:
    """
    Content for the time-limited reveal overlay.

    `grievance_description` is passed through unscrubbed: it is not one of the backend's
    ENCRYPTED_FIELDS (those are the four complainant contact columns) and is stored as
    plaintext, so it was never ciphertext to begin with — the old `reveal_field` call on
    it was always a no-op.
    """
    return {
        "grievance_description": grievance.get("grievance_description"),
        "complainant_name": scrub_pii_value(grievance.get("complainant_full_name")),
        "phone_number": scrub_pii_value(grievance.get("complainant_phone")),
        "email": scrub_pii_value(grievance.get("complainant_email")),
        "address": scrub_pii_value(grievance.get("complainant_address")),
    }
