"""
Canonical GRM officer role definitions — single source for seed + UI metadata.

`workflow_scope`: Standard | SEAH | Both (admin UI grouping / filters).
Permissions remain lists of capability strings checked by the backend.
"""

from __future__ import annotations

from typing import Any, TypedDict


class GrmRoleCatalogEntry(TypedDict, total=False):
    role_key: str
    display_name: str
    workflow_scope: str
    jurisdiction_mode: str
    description: str
    permissions: list[str]


# Keys must stay aligned with workflow steps / assignments / CLAUDE.md role list.
GRM_ROLE_CATALOG: list[dict[str, Any]] = [
    {
        "role_key": "super_admin",
        "display_name": "Super Admin",
        "workflow_scope": "Both",
        "jurisdiction_mode": "global",
        "role_kind": "admin",
        "role_origin": "system",
        "description": (
            "Full system access. Can manage all settings, users, and tickets."
        ),
        "permissions": ["*"],
    },
    {
        "role_key": "org_admin",
        "display_name": "Organization Administrator",
        "workflow_scope": "Both",
        "jurisdiction_mode": "country",
        "role_kind": "admin",
        "role_origin": "system",
        "description": (
            "Org-subtree admin (any depth) — authors the catalog; workflow track is set "
            "on the admin_scopes assignment (doc 11 §2.2)."
        ),
        "permissions": [
            "tickets:read",
            "projects:manage",
            "locations:manage",
            "workflows:manage",
            "users:invite",
            "settings:write",
        ],
    },
    {
        "role_key": "project_admin",
        "display_name": "Project Administrator",
        "workflow_scope": "Both",
        "role_kind": "admin",
        "role_origin": "system",
        "description": "Project-tier delegate — workflow track is set on admin_scopes assignment.",
        "permissions": [
            "tickets:read",
            "officers:assign",
            "notifications:configure",
            "settings:project",
            "users:invite",
        ],
    },
    {
        "role_key": "officer_admin",
        "display_name": "Officer Administrator",
        "workflow_scope": "Both",
        "jurisdiction_mode": "field",
        "role_kind": "admin",
        "role_origin": "system",
        "description": (
            "Narrowest admin — invite / modify / revoke officers only, within scope "
            "(doc 11 §2.3b); track is set on the admin_scopes assignment."
        ),
        "permissions": [
            "tickets:read",
            "users:invite",
        ],
    },
    {
        "role_key": "local_admin",
        "display_name": "Local Admin",
        "workflow_scope": "Standard",
        # Legacy admin key — superseded by the org_admin/project_admin/officer_admin ladder
        # (doc 11; demo_officers.OFFICER_LOCAL_ADMIN now aliases country-admin). It is NOT in
        # ADMIN_ROLE_KEYS, but it is still honored as an admin everywhere in the authz layer
        # (admin_access.is_*_admin, ticket_access, tickets crud/viewers/summary admin sets), so
        # it must be role_kind="admin". Left unset it defaulted to "operational" and leaked into
        # the operational role pickers (position default_role, quarterly-report recipients).
        "role_kind": "admin",
        "role_origin": "system",
        "description": (
            "Legacy admin — access scoped to their organization and location. "
            "Superseded by org_admin; retained only to honor existing grants."
        ),
        "permissions": ["tickets:read", "tickets:write", "users:manage", "settings:write"],
    },
    {
        "role_key": "site_safeguards_focal_person",
        "display_name": "Site Safeguards Focal Person",
        "actor_category": "government",
        "workflow_scope": "Standard",
        "archetype": "field_actor",
        "description": (
            "Level 1 officer — first point of contact for standard grievances."
        ),
        "permissions": [
            "tickets:read",
            "tickets:acknowledge",
            "tickets:note",
            "tickets:resolve",
        ],
    },
    {
        "role_key": "country_l1_fallback",
        "display_name": "Country L1 Fallback Officer",
        "actor_category": "government",
        "workflow_scope": "Standard",
        "archetype": "field_actor",
        "jurisdiction_mode": "country",
        "description": (
            "Last-resort L1 assignee when no district- or province-scoped site "
            "safeguards officer matches. Scoped country-wide; never competes in "
            "the normal geographic pool."
        ),
        "permissions": [
            "tickets:read",
            "tickets:acknowledge",
            "tickets:note",
            "tickets:resolve",
        ],
    },
    {
        "role_key": "pd_piu_safeguards_focal",
        "display_name": "PD / PIU Safeguards Focal",
        "actor_category": "government",
        "workflow_scope": "Standard",
        "archetype": "supervisor",
        "description": "Level 2 officer — receives escalations from L1.",
        "permissions": [
            "tickets:read",
            "tickets:acknowledge",
            "tickets:note",
            "tickets:escalate",
            "tickets:resolve",
        ],
    },
    {
        "role_key": "grc_chair",
        "display_name": "GRC Chair",
        "actor_category": "government",
        "workflow_scope": "Standard",
        "archetype": "grc_committee",
        "description": (
            "Level 3 — convenes GRC hearing and records the committee decision."
        ),
        "permissions": [
            "tickets:read",
            "tickets:acknowledge",
            "tickets:note",
            "tickets:escalate",
            "tickets:resolve",
            "grc:convene",
            "grc:decide",
        ],
    },
    {
        "role_key": "grc_member",
        "display_name": "GRC Member",
        "actor_category": "government",
        "workflow_scope": "Standard",
        "archetype": "grc_member",
        "description": (
            "Level 3 — participates in GRC hearing. Receives hearing notifications."
        ),
        "permissions": ["tickets:read", "tickets:note"],
    },
    {
        "role_key": "adb_national_project_director",
        "display_name": "ADB National Project Director",
        "actor_category": "donor",
        "workflow_scope": "Standard",
        "archetype": "observer",
        "jurisdiction_mode": "country",
        "description": "Observer — read-only oversight of standard GRM cases.",
        "permissions": ["tickets:read", "reports:read"],
    },
    {
        "role_key": "adb_hq_safeguards",
        "display_name": "ADB HQ Safeguards",
        "actor_category": "donor",
        "workflow_scope": "Standard",
        "archetype": "observer",
        "jurisdiction_mode": "country",
        "description": "Observer — read-only oversight of standard GRM cases.",
        "permissions": ["tickets:read", "reports:read"],
    },
    {
        "role_key": "adb_hq_project",
        "display_name": "ADB HQ Project",
        "actor_category": "donor",
        "workflow_scope": "Standard",
        "archetype": "observer",
        "jurisdiction_mode": "country",
        "description": "Observer — project oversight.",
        "permissions": ["tickets:read", "reports:read"],
    },
    # Donor observer/informed tier (doc 13 / DECISION 2026-07-10 §3). Generalizes the
    # legacy adb_* observers. Kept informed on the STANDARD track's final step only —
    # never cast on a SEAH case (ticketing.models.user.DONOR_ROLES).
    {
        "role_key": "donor_consultant",
        "display_name": "Donor — Consultant",
        "actor_category": "donor",
        "workflow_scope": "Standard",
        "archetype": "observer",
        "jurisdiction_mode": "country",
        "description": (
            "Donor-side consultant — read-only oversight; kept informed on final "
            "escalation of standard cases for the funded project."
        ),
        "permissions": ["tickets:read", "reports:read"],
    },
    {
        "role_key": "donor_national",
        "display_name": "Donor — National Officer",
        "actor_category": "donor",
        "workflow_scope": "Standard",
        "archetype": "observer",
        "jurisdiction_mode": "country",
        "description": (
            "Donor national officer — read-only oversight; kept informed on final "
            "escalation of standard cases for the funded project."
        ),
        "permissions": ["tickets:read", "reports:read"],
    },
    {
        "role_key": "donor_hq",
        "display_name": "Donor — HQ",
        "actor_category": "donor",
        "workflow_scope": "Standard",
        "archetype": "observer",
        "jurisdiction_mode": "country",
        "description": (
            "Donor HQ officer — read-only oversight; kept informed on final escalation "
            "of standard cases for the funded project."
        ),
        "permissions": ["tickets:read", "reports:read"],
    },
    {
        "role_key": "seah_national_officer",
        "display_name": "SEAH National Officer",
        "actor_category": "government",
        "workflow_scope": "SEAH",
        "archetype": "seah_handler",
        "description": (
            "Level 1 SEAH officer — handles SEAH cases. Invisible to standard officers."
        ),
        "permissions": [
            "tickets:read",
            "tickets:acknowledge",
            "tickets:note",
            "tickets:escalate",
            "tickets:resolve",
            "seah:access",
        ],
    },
    {
        "role_key": "seah_hq_officer",
        "display_name": "SEAH HQ Officer",
        "actor_category": "government",
        "workflow_scope": "SEAH",
        "archetype": "seah_handler",
        "description": "Level 2 SEAH officer — receives SEAH escalations.",
        "permissions": [
            "tickets:read",
            "tickets:acknowledge",
            "tickets:note",
            "tickets:escalate",
            "tickets:resolve",
            "seah:access",
        ],
    },
    {
        "role_key": "adb_hq_exec",
        "display_name": "ADB HQ Executive",
        "actor_category": "donor",
        "workflow_scope": "Both",
        "archetype": "observer",
        "jurisdiction_mode": "country",
        "description": "Senior oversight — read-only access to both standard and SEAH cases.",
        "permissions": ["tickets:read", "reports:read", "seah:access"],
    },
]
