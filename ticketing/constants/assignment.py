# SPDX-License-Identifier: Apache-2.0

"""
Workflow step auto-assignment — role keys and field → country fallback mapping.

Field L1 officers match via district/municipality → province widening only.
`country_l1_fallback` is consulted only when no field L1 candidate exists.
"""
from __future__ import annotations

# Dedicated last-resort L1 role (country-wide scope, never in field/province pools).
COUNTRY_L1_FALLBACK_ROLE = "country_l1_fallback"

# Step assigned_role_key → country fallback role (None = no country tier).
#
# Keyed on whatever the **step** holds, which changed on 2026-08-09: each (step, tier) slot now
# owns its key, so the seeded Level 1 actor is `wf:KL_ROAD_STANDARD:LEVEL_1_SITE:actor`. The
# named role stays mapped as well — it is what a database still carries before migration
# `x0z2b4d6` runs, and what any workflow authored the old way still uses. Both mean the same
# thing here: a Level 1 with nobody in range falls back to the country officer so intake never
# dead-ends.
STEP_ROLE_COUNTRY_FALLBACK: dict[str, str] = {
    "site_safeguards_focal_person": COUNTRY_L1_FALLBACK_ROLE,
    "wf:KL_ROAD_STANDARD:LEVEL_1_SITE:actor": COUNTRY_L1_FALLBACK_ROLE,
}


def country_fallback_for_step_role(step_role_key: str) -> str | None:
    return STEP_ROLE_COUNTRY_FALLBACK.get(step_role_key)
