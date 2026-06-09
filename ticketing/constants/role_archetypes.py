"""
Operational role archetype templates — pre-fill permissions for custom roles.

Admin-only capability strings must never appear on operational roles.
"""

from __future__ import annotations

ADMIN_ONLY_PERMISSIONS = frozenset({
    "*",
    "settings:write",
    "projects:manage",
    "locations:manage",
    "workflows:manage",
    "users:invite",
    "users:manage",
    "settings:project",
    "officers:assign",
    "notifications:configure",
})

ARCHETYPE_PERMISSIONS: dict[str, list[str]] = {
    "field_actor": [
        "tickets:read",
        "tickets:acknowledge",
        "tickets:note",
        "tickets:resolve",
    ],
    "supervisor": [
        "tickets:read",
        "tickets:acknowledge",
        "tickets:note",
        "tickets:escalate",
        "tickets:resolve",
    ],
    "grc_committee": [
        "tickets:read",
        "tickets:acknowledge",
        "tickets:note",
        "tickets:escalate",
        "tickets:resolve",
        "grc:convene",
        "grc:decide",
    ],
    "grc_member": [
        "tickets:read",
        "tickets:note",
    ],
    "observer": [
        "tickets:read",
        "reports:read",
    ],
    "seah_handler": [
        "tickets:read",
        "tickets:acknowledge",
        "tickets:note",
        "tickets:escalate",
        "tickets:resolve",
        "seah:access",
    ],
    "custom": [],
}

ARCHETYPE_LABELS: dict[str, str] = {
    "field_actor": "Field actor (L1-style)",
    "supervisor": "Supervisor (L2 / oversight)",
    "grc_committee": "GRC committee chair",
    "grc_member": "GRC member",
    "observer": "Observer (read-only)",
    "seah_handler": "SEAH handler",
    "custom": "Custom (pick permissions)",
}

SEAH_FORBIDDEN_ON_SEAH_ADMIN = frozenset({"grc:convene", "grc:decide"})


def list_archetypes() -> list[dict[str, str]]:
    return [
        {"key": key, "label": ARCHETYPE_LABELS[key]}
        for key in ARCHETYPE_PERMISSIONS
    ]


def permissions_for_archetype(archetype: str, *, workflow_scope: str = "Standard") -> list[str]:
    if archetype not in ARCHETYPE_PERMISSIONS:
        raise ValueError(f"Unknown archetype: {archetype}")
    perms = list(ARCHETYPE_PERMISSIONS[archetype])
    if workflow_scope == "SEAH" and archetype != "custom":
        if "seah:access" not in perms:
            perms.append("seah:access")
        perms = [p for p in perms if p not in SEAH_FORBIDDEN_ON_SEAH_ADMIN]
    return perms


def validate_operational_permissions(permissions: list[str]) -> None:
    leaked = sorted(set(permissions) & ADMIN_ONLY_PERMISSIONS)
    if leaked:
        raise ValueError(
            f"Operational roles cannot include admin permissions: {', '.join(leaked)}"
        )


def slugify_role_key(display_name: str) -> str:
    import re

    s = re.sub(r"[^a-z0-9]+", "_", display_name.lower()).strip("_")
    if not s or not s[0].isalpha():
        s = f"role_{s}" if s else "custom_role"
    return s[:64]
