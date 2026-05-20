"""
PII masking and vault decrypt helpers for the ticketing API broker.

The grievance GET endpoint may return pgcrypto hex ciphertext when fields were
not decrypted server-side. Officers must never see ciphertext in the default UI.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy import text

from ticketing.config.settings import get_settings
from ticketing.models.base import engine

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
    """Return None when value is vault ciphertext (UI shows a standard mask)."""
    if looks_like_ciphertext(value):
        return None
    return value


def decrypt_ciphertext(hex_value: str) -> str | None:
    """Decrypt a single pgcrypto hex field using DB_ENCRYPTION_KEY (same DB as chatbot)."""
    settings = get_settings()
    key = (settings.db_encryption_key or "").strip()
    if not key or not looks_like_ciphertext(hex_value):
        return None
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT pgp_sym_decrypt(decode(:ct, 'hex'), :key) AS decrypted"),
                {"ct": hex_value.strip(), "key": key},
            ).mappings().first()
        if not row:
            return None
        decrypted = row.get("decrypted")
        if decrypted is None:
            return None
        if isinstance(decrypted, memoryview):
            return decrypted.tobytes().decode("utf-8", errors="replace")
        if isinstance(decrypted, bytes):
            return decrypted.decode("utf-8", errors="replace")
        return str(decrypted)
    except Exception as exc:
        logger.warning("decrypt_ciphertext failed: %s", exc)
        return None


def reveal_field(value: Any) -> Any:
    """Plain text for vault reveal; decrypt ciphertext when possible."""
    if value is None:
        return None
    if isinstance(value, str) and looks_like_ciphertext(value):
        return decrypt_ciphertext(value) or None
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
    }


def grievance_reveal_content(grievance: dict[str, Any]) -> dict[str, Any]:
    """Decrypted content for time-limited reveal overlay."""
    return {
        "grievance_description": reveal_field(grievance.get("grievance_description")),
        "complainant_name": reveal_field(grievance.get("complainant_full_name")),
        "phone_number": reveal_field(grievance.get("complainant_phone")),
        "email": reveal_field(grievance.get("complainant_email")),
        "address": reveal_field(grievance.get("complainant_address")),
    }
