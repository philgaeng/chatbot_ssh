"""
Default jurisdiction mode per GRM role (how officer scopes are validated and matched).

- field: at least one of project, package, or location (default for implementers)
- country: organization only — all projects where that org is a project actor
- global: organization only — all tickets (super_admin catalog default; admins bypass filters)
"""

from __future__ import annotations

JURISDICTION_FIELD = "field"
JURISDICTION_COUNTRY = "country"
JURISDICTION_GLOBAL = "global"

VALID_JURISDICTION_MODES = frozenset({JURISDICTION_FIELD, JURISDICTION_COUNTRY, JURISDICTION_GLOBAL})

# Default when ticketing.roles.jurisdiction_mode is null (seed backfill uses these).
ROLE_JURISDICTION_DEFAULTS: dict[str, str] = {
    "super_admin": JURISDICTION_GLOBAL,
    "country_admin": JURISDICTION_COUNTRY,
    "local_admin": JURISDICTION_FIELD,
    "adb_national_project_director": JURISDICTION_COUNTRY,
    "country_l1_fallback": JURISDICTION_COUNTRY,
    "adb_hq_safeguards": JURISDICTION_COUNTRY,
    "adb_hq_project": JURISDICTION_COUNTRY,
    "adb_hq_exec": JURISDICTION_COUNTRY,
}


def default_jurisdiction_mode(role_key: str) -> str:
    return ROLE_JURISDICTION_DEFAULTS.get(role_key, JURISDICTION_FIELD)


def resolve_jurisdiction_mode(role_key: str, stored: str | None) -> str:
    if stored and stored in VALID_JURISDICTION_MODES:
        return stored
    return default_jurisdiction_mode(role_key)


def is_country_or_global_mode(mode: str) -> bool:
    return mode in (JURISDICTION_COUNTRY, JURISDICTION_GLOBAL)
