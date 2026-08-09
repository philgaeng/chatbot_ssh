"""
Canonical demo officer identities for GRM proto.

Rule: Keycloak username == ticketing.user_id == email (@grm.local).
Used by Keycloak realm setup, DB seed, and migration from legacy mock-* IDs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# ── Canonical emails (import these instead of hardcoding strings) ─────────────

OFFICER_ADMIN = "admin@grm.local"
OFFICER_COUNTRY_ADMIN_STD = "country-admin@grm.local"
OFFICER_COUNTRY_ADMIN_SEAH = "country-admin-seah@grm.local"
OFFICER_PROJECT_ADMIN = "project-admin@grm.local"
# Deprecated alias — migrated to org_admin
OFFICER_LOCAL_ADMIN = OFFICER_COUNTRY_ADMIN_STD
OFFICER_SITE_L1 = "l1-officer@grm.local"
OFFICER_SITE_L1_2 = "l1-officer-2@grm.local"
OFFICER_SITE_L1_3 = "l1-officer-3@grm.local"
OFFICER_SITE_L1_4 = "l1-officer-4@grm.local"
OFFICER_PIU_L2 = "l2-piu@grm.local"
OFFICER_PIU_L2_2 = "l2-piu-2@grm.local"
OFFICER_PIU_L2_3 = "l2-piu-3@grm.local"
OFFICER_GRC_CHAIR = "grc-chair@grm.local"
OFFICER_GRC_MEMBER_1 = "grc-member-1@grm.local"
OFFICER_GRC_MEMBER_2 = "grc-member-2@grm.local"
OFFICER_SEAH_NATIONAL = "seah@grm.local"
OFFICER_SEAH_HQ = "seah-hq@grm.local"
OFFICER_ADB = "adb@grm.local"

# Dev bypass default when no cookie is set (:3001)
BYPASS_DEFAULT_OFFICER = OFFICER_ADMIN

# Legacy proto IDs → email (idempotent migration on seed)
LEGACY_OFFICER_ID_MAP: dict[str, str] = {
    "mock-super-admin": OFFICER_ADMIN,
    "mock-officer-site-l1": OFFICER_SITE_L1,
    "mock-officer-site-l1@grm.local": OFFICER_SITE_L1,
    "mock-officer-piu-l2": OFFICER_PIU_L2,
    "mock-officer-grc-chair": OFFICER_GRC_CHAIR,
    "mock-officer-grc-member-1": OFFICER_GRC_MEMBER_1,
    "mock-officer-grc-member-2": OFFICER_GRC_MEMBER_2,
    "mock-officer-seah-national": OFFICER_SEAH_NATIONAL,
    "mock-officer-seah-hq": OFFICER_SEAH_HQ,
    "mock-officer-adb-observer": OFFICER_ADB,
    "local_admin_mock_1@grm.local": OFFICER_COUNTRY_ADMIN_STD,
    "local-admin@grm.local": OFFICER_COUNTRY_ADMIN_STD,
}


@dataclass(frozen=True)
class DemoOfficerSpec:
    email: str
    first_name: str
    last_name: str
    role_key: str
    organization_id: str
    user_role_location: Optional[str] = None
    keycloak_location: Optional[str] = None


# KL Road seed locations (import lazily in seed to avoid circular imports)
# P1_MOR, P1 (province 1) — match kl_road_standard seed codes.


# Slot keys, not operational roles (2026-08-09). A demo officer is staffed into a specific
# (step, tier) slot; the operational roles they *also* hold — permissions, tracks — are seeded
# separately. One key naming two slots is what made staffing ambiguous, so these name slots.
SLOT_L1_ACTOR = "wf:KL_ROAD_STANDARD:LEVEL_1_SITE:actor"
SLOT_L1_SUPERVISOR = "wf:KL_ROAD_STANDARD:LEVEL_1_SITE:supervisor"
SLOT_L3_ACTOR = "wf:KL_ROAD_STANDARD:LEVEL_3_GRC:actor"
SLOT_L3_SUPERVISOR = "wf:KL_ROAD_STANDARD:LEVEL_3_GRC:supervisor"
SLOT_L3_INFORMED = "wf:KL_ROAD_STANDARD:LEVEL_3_GRC:informed"
SLOT_SEAH_L1_ACTOR = "wf:KL_ROAD_SEAH:SEAH_LEVEL_1_NATIONAL:actor"
SLOT_SEAH_L1_SUPERVISOR = "wf:KL_ROAD_SEAH:SEAH_LEVEL_1_NATIONAL:supervisor"

DEMO_OFFICER_SPECS: tuple[DemoOfficerSpec, ...] = (
    DemoOfficerSpec(
        OFFICER_ADMIN, "GRM", "Admin", "super_admin", "DOR",
    ),
    DemoOfficerSpec(
        OFFICER_COUNTRY_ADMIN_STD, "Country", "Admin Standard", "org_admin", "DOR",
        user_role_location="P1", keycloak_location="P1",
    ),
    DemoOfficerSpec(
        OFFICER_COUNTRY_ADMIN_SEAH, "Country", "Admin SEAH", "org_admin", "DOR",
        user_role_location="P1", keycloak_location="P1",
    ),
    DemoOfficerSpec(
        OFFICER_PROJECT_ADMIN, "Project", "Admin", "project_admin", "DOR",
        user_role_location="P1", keycloak_location="P1",
    ),
    DemoOfficerSpec(
        OFFICER_SITE_L1, "Site", "Officer L1", SLOT_L1_ACTOR, "DOR",
        user_role_location="P1_MOR", keycloak_location="P1_MOR",
    ),
    DemoOfficerSpec(
        OFFICER_SITE_L1_2, "Site", "Officer L1-2", SLOT_L1_ACTOR, "DOR",
        user_role_location="P1_JHA", keycloak_location="P1_JHA",
    ),
    DemoOfficerSpec(
        OFFICER_SITE_L1_3, "Site", "Officer L1-3", SLOT_L1_ACTOR, "DOR",
        user_role_location="P1_SUN", keycloak_location="P1_SUN",
    ),
    DemoOfficerSpec(
        OFFICER_SITE_L1_4, "Site", "Officer L1-4", SLOT_L1_ACTOR, "DOR",
        user_role_location="P1_MOR", keycloak_location="P1_MOR",
    ),
    DemoOfficerSpec(
        OFFICER_PIU_L2, "PIU", "Officer L2", SLOT_L1_SUPERVISOR, "DOR",
        user_role_location="P1",
    ),
    DemoOfficerSpec(
        OFFICER_PIU_L2_2, "PIU", "Officer L2-2", SLOT_L1_SUPERVISOR, "DOR",
        user_role_location="P1",
    ),
    DemoOfficerSpec(
        OFFICER_PIU_L2_3, "PIU", "Officer L2-3", SLOT_L1_SUPERVISOR, "DOR",
        user_role_location="P1",
    ),
    DemoOfficerSpec(
        OFFICER_GRC_CHAIR, "GRC", "Chair", SLOT_L3_ACTOR, "DOR",
        user_role_location="P1",
    ),
    DemoOfficerSpec(
        OFFICER_GRC_MEMBER_1, "GRC", "Member 1", SLOT_L3_INFORMED, "DOR",
        user_role_location="P1",
    ),
    DemoOfficerSpec(
        OFFICER_GRC_MEMBER_2, "GRC", "Member 2", SLOT_L3_INFORMED, "DOR",
        user_role_location="P1",
    ),
    DemoOfficerSpec(
        OFFICER_SEAH_NATIONAL, "SEAH", "Officer", SLOT_SEAH_L1_ACTOR, "DOR",
        user_role_location="P1",
    ),
    DemoOfficerSpec(
        OFFICER_SEAH_HQ, "SEAH", "HQ Officer", SLOT_SEAH_L1_SUPERVISOR, "ADB",
    ),
    DemoOfficerSpec(
        OFFICER_ADB, "ADB", "Safeguards", SLOT_L3_SUPERVISOR, "ADB",
    ),
)


def keycloak_demo_officers() -> list[dict[str, str]]:
    """Payload shape for ticketing.auth.keycloak_setup."""
    rows: list[dict[str, str]] = []
    for spec in DEMO_OFFICER_SPECS:
        row: dict[str, str] = {
            "username": spec.email,
            "email": spec.email,
            "firstName": spec.first_name,
            "lastName": spec.last_name,
            "grm_roles": spec.role_key,
            "organization_id": spec.organization_id,
        }
        if spec.keycloak_location:
            row["location_code"] = spec.keycloak_location
        rows.append(row)
    return rows
