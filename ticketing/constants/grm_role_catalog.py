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
    description: str
    permissions: list[str]


# Keys must stay aligned with workflow steps / assignments / CLAUDE.md role list.
GRM_ROLE_CATALOG: list[dict[str, Any]] = [
    {
        "role_key": "super_admin",
        "display_name": "Super Admin",
        "workflow_scope": "Both",
        "description": (
            "Full system access. Can manage all settings, users, and tickets."
        ),
        "permissions": ["*"],
    },
    {
        "role_key": "country_admin",
        "display_name": "Country Administrator",
        "workflow_scope": "Standard",
        "description": "Country-level administration (legacy seed role).",
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
        "workflow_scope": "Standard",
        "description": "Project-scoped administration (legacy seed role).",
        "permissions": [
            "tickets:read",
            "officers:assign",
            "notifications:configure",
            "settings:project",
        ],
    },
    {
        "role_key": "local_admin",
        "display_name": "Local Admin",
        "workflow_scope": "Standard",
        "description": (
            "Administrative access scoped to their organization and location."
        ),
        "permissions": ["tickets:read", "tickets:write", "users:manage", "settings:write"],
    },
    {
        "role_key": "site_safeguards_focal_person",
        "display_name": "Site Safeguards Focal Person",
        "workflow_scope": "Standard",
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
        "role_key": "pd_piu_safeguards_focal",
        "display_name": "PD / PIU Safeguards Focal",
        "workflow_scope": "Standard",
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
        "workflow_scope": "Standard",
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
        "workflow_scope": "Standard",
        "description": (
            "Level 3 — participates in GRC hearing. Receives hearing notifications."
        ),
        "permissions": ["tickets:read", "tickets:note"],
    },
    {
        "role_key": "adb_national_project_director",
        "display_name": "ADB National Project Director",
        "workflow_scope": "Standard",
        "description": "Observer — read-only oversight of standard GRM cases.",
        "permissions": ["tickets:read", "reports:read"],
    },
    {
        "role_key": "adb_hq_safeguards",
        "display_name": "ADB HQ Safeguards",
        "workflow_scope": "Standard",
        "description": "Observer — read-only oversight of standard GRM cases.",
        "permissions": ["tickets:read", "reports:read"],
    },
    {
        "role_key": "adb_hq_project",
        "display_name": "ADB HQ Project",
        "workflow_scope": "Standard",
        "description": "Observer — project oversight.",
        "permissions": ["tickets:read", "reports:read"],
    },
    {
        "role_key": "seah_national_officer",
        "display_name": "SEAH National Officer",
        "workflow_scope": "SEAH",
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
        "workflow_scope": "SEAH",
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
        "workflow_scope": "Both",
        "description": "Senior oversight — read-only access to both standard and SEAH cases.",
        "permissions": ["tickets:read", "reports:read", "seah:access"],
    },
]
