"""
Workflow step auto-assignment — role keys and field → country fallback mapping.

Field L1 officers match via district/municipality → province widening only.
`country_l1_fallback` is consulted only when no field L1 candidate exists.
"""
from __future__ import annotations

# Dedicated last-resort L1 role (country-wide scope, never in field/province pools).
COUNTRY_L1_FALLBACK_ROLE = "country_l1_fallback"

# Step assigned_role_key → country fallback role (None = no country tier).
STEP_ROLE_COUNTRY_FALLBACK: dict[str, str] = {
    "site_safeguards_focal_person": COUNTRY_L1_FALLBACK_ROLE,
}


def country_fallback_for_step_role(step_role_key: str) -> str | None:
    return STEP_ROLE_COUNTRY_FALLBACK.get(step_role_key)
