# SPDX-License-Identifier: Apache-2.0

# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""Back-fill project types from the workflows projects already run.

Every project is untyped and `ticketing.project_types` is empty, so nothing consumes the
template model that DECISION-author-defined-slots builds on — the type-driven screens have
nothing to render and go-live's B1 never runs. This gives every project a type derived from
what it *already* does, so the new model has data from day one.

Method: group projects by the set of workflows they run (workflow_id + is_default +
intake_route + classifications, order-independent). One type per distinct set, named
"Type 1", "Type 2" … — deliberately dull, because names are editable even on a type with live
projects (§8) and only a human knows whether this is "ADB-funded road" or "Municipal road".

What it does NOT do, on purpose:

  • **`actor_roles` mark only the routing anchor required.** Everything else is optional, so no
    project is thrown into a blocked state by its own migration. An author tightens it later.
  • **`owner_organization_id` stays NULL** (= global, offered to everyone). Guessing the
    top-level organization from an implementing agency would be wrong as often as right;
    an author sets it when they mean it.
  • **Projects with no workflow rows are skipped.** There is no template to infer.

Revision ID: n0p2r4t6
Revises: l8n0p2r4
Create Date: 2026-08-04
"""
from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n0p2r4t6"
down_revision: Union[str, None] = "l8n0p2r4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TYPE_KEY_PREFIX = "migrated_type_"


def _as_list(value) -> list:
    """`classifications` is JSON in Postgres but may arrive as str on some drivers."""
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return []
    return list(value) if isinstance(value, list) else []


def upgrade() -> None:
    conn = op.get_bind()

    rows = conn.execute(sa.text("""
        SELECT p.project_id,
               p.implementing_agency_org_id,
               pw.workflow_id,
               pw.display_label,
               pw.is_default,
               pw.intake_route,
               pw.classifications,
               pw.sort_order
          FROM ticketing.projects p
          JOIN ticketing.project_workflows pw ON pw.project_id = p.project_id
         WHERE p.project_type_key IS NULL
         ORDER BY p.project_id, pw.sort_order
    """)).mappings().all()
    if not rows:
        return

    by_project: dict[str, list[dict]] = {}
    for r in rows:
        by_project.setdefault(r["project_id"], []).append(dict(r))

    # Signature: the set of workflows a project runs, order-independent so two projects that
    # listed the same workflows in a different order share one type.
    def signature(links: list[dict]) -> tuple:
        return tuple(sorted(
            (
                str(l["workflow_id"]),
                bool(l["is_default"]),
                l["intake_route"] or "",
                ",".join(sorted(_as_list(l["classifications"]))),
            )
            for l in links
        ))

    groups: dict[tuple, list[str]] = {}
    for project_id, links in by_project.items():
        groups.setdefault(signature(links), []).append(project_id)

    # Organization roles actually in use across the group, so the catalog reflects reality.
    org_roles = conn.execute(sa.text("""
        SELECT DISTINCT project_id, org_role
          FROM ticketing.project_organizations
         WHERE org_role IS NOT NULL AND org_role <> ''
    """)).mappings().all()
    roles_by_project: dict[str, set[str]] = {}
    for r in org_roles:
        roles_by_project.setdefault(r["project_id"], set()).add(r["org_role"])

    for i, (sig, project_ids) in enumerate(sorted(groups.items(), key=lambda kv: str(kv[0])), start=1):
        type_key = f"{TYPE_KEY_PREFIX}{i}"
        sample = by_project[project_ids[0]]

        bindings = [
            {
                "display_label": l["display_label"],
                "workflow_id": str(l["workflow_id"]),
                "is_default": bool(l["is_default"]),
                "classifications": _as_list(l["classifications"]),
                "intake_route": l["intake_route"],
                "sort_order": l["sort_order"] or 0,
            }
            for l in sorted(sample, key=lambda x: x["sort_order"] or 0)
        ]

        # The anchor stays whatever routing already resolves through, and is the ONLY role the
        # migration marks required — see the module docstring.
        anchor = "implementing_agency"
        keys: set[str] = {anchor}
        for pid in project_ids:
            keys |= roles_by_project.get(pid, set())

        actor_roles = [
            {
                "key": k,
                "label": k.replace("_", " ").title(),
                "description": "",
                "required": k == anchor,
                "required_package": False,
                "scope": "project",
            }
            for k in sorted(keys)
        ]

        default_wf = next((b["workflow_id"] for b in bindings if b["is_default"]), None)

        conn.execute(
            sa.text("""
                INSERT INTO ticketing.project_types (
                    type_key, label, description, standard_workflow_id, seah_workflow_id,
                    routing_org_role, actor_roles, workflow_bindings, owner_organization_id,
                    is_active, sort_order, created_at, updated_at
                ) VALUES (
                    :type_key, :label, :description, :standard_workflow_id, NULL,
                    :routing_org_role, CAST(:actor_roles AS json), CAST(:bindings AS json), NULL,
                    TRUE, :sort_order, NOW(), NOW()
                )
            """),
            {
                "type_key": type_key,
                "label": f"Type {i}",
                "description": "Created from the workflows these projects already run. Rename it.",
                "standard_workflow_id": default_wf,
                "routing_org_role": anchor,
                "actor_roles": json.dumps(actor_roles),
                "bindings": json.dumps(bindings),
                "sort_order": i * 10,
            },
        )

        conn.execute(
            sa.text("""
                UPDATE ticketing.projects
                   SET project_type_key = :type_key
                 WHERE project_id = ANY(:ids)
            """),
            {"type_key": type_key, "ids": project_ids},
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE ticketing.projects
           SET project_type_key = NULL
         WHERE project_type_key LIKE :pattern
    """), {"pattern": f"{TYPE_KEY_PREFIX}%"})
    conn.execute(sa.text("""
        DELETE FROM ticketing.project_types WHERE type_key LIKE :pattern
    """), {"pattern": f"{TYPE_KEY_PREFIX}%"})
