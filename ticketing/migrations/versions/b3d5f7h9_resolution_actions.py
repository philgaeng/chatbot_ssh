# SPDX-License-Identifier: Apache-2.0

# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""Resolution actions: a catalog owned by organizations, and each workflow's list from it (GRM-116).

Every case used to resolve from the same five hard-coded outcomes, whatever its workflow — a
road-hazard report and a SEAH case alike. A SEAH case was *forced* to pick one, including
"Complainant demand rejected".

**Nothing in the catalog is global** (owner's decision, Q-10): every action belongs to one
organization, and every workflow and template must belong to one too, or it could offer nothing. So,
in order:

1. **Every workflow and template with no organization gets its projects' ministry** — the top
   organization above the implementing agency of each project that uses it. Unused → the one ministry
   that implements projects, if there is exactly one. Used by two ministries' projects, or unused when
   several implement projects → **this migration stops and names the workflow**: a guess would hand
   one ministry's workflow to another. Workflows that already have an organization keep it. With no
   ministry at all (an empty database) nothing is assigned.
2. **Seed ten shared actions of that ministry** — today's five (codes and wording unchanged, so every
   historical ticket event still resolves to a label) and five for road works. On a database with no
   ministry the seed scripts create them instead (`kl_road_standard.py`). If **several** ministries
   implement projects, nothing is seeded: codes are platform-unique, so a second ministry's starter
   actions need codes of their own (`GRM-120`).
3. **Give each workflow its starting list**, when it belongs to that ministry or below:
   sensitive → nothing · bound **only** to the road-hazard menu → the road-works five · bound to it
   **and** to another route → the general five plus three road-works actions (8, the most a workflow
   holds) · anything else, templates included → the general five.

   ⚠ **Corrected 2026-09-15, after it ran on staging.** The rule was "bound to the road-hazard menu on
   ANY project → the road-works five". Staging's default standard workflow is also the road-hazard
   route on two projects, so it got road works only, and an ordinary grievance could no longer close
   as accepted or rejected. It was fixed there by hand to the list this rule now gives; production has
   not run this migration.

The seed rows are written out here rather than imported: a migration must say what it did on the
day it ran, whatever the application's constants say later.

Revision ID: b3d5f7h9
Revises: z2b4d6f8
Create Date: 2026-09-15
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3d5f7h9"
down_revision: Union[str, None] = "z2b4d6f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GENERAL = [
    ("CLASSIFIED", "Grievance classified",
     "This grievance has been reviewed and classified. No specific remedial action is required "
     "beyond continued monitoring under the project GRM procedure."),
    ("DEMAND_REJECTED", "Complainant demand rejected",
     "After investigation, the grievance was found not to be substantiated. The complainant's "
     "request is not accepted. The case is closed with this determination."),
    ("ACCEPTED_MONETARY", "Grievance accepted — monetary compensation",
     "The grievance is substantiated. Remedial action includes monetary compensation as agreed "
     "with the complainant / per contract and GRM procedure."),
    ("ACCEPTED_RELOCATION", "Grievance accepted — relocation",
     "The grievance is substantiated. Remedial action includes relocation / resettlement support "
     "as applicable under project safeguards."),
    ("ACCEPTED_OTHER", "Grievance accepted — other remedy",
     "The grievance is substantiated. Remedial action has been agreed (other than monetary "
     "compensation or relocation). Details are recorded below."),
]

ROAD_WORKS = [
    ("ROAD_REPAIRED", "Hazard repaired",
     "The reported hazard was inspected and repaired."),
    ("ROAD_MADE_SAFE", "Made safe — signs, barriers or traffic control",
     "The site was made safe with warning signs, barriers or traffic control. A permanent repair "
     "is planned."),
    ("ROAD_DUST_NOISE_CONTROLLED", "Dust or noise controlled",
     "The contractor was instructed to control dust or noise, for example by spraying water or "
     "limiting working hours."),
    ("ROAD_NOT_PROJECT_ROAD", "Not on a project road — passed on",
     "The location is not on a project road. The report was passed to the authority responsible "
     "for it."),
    ("ROAD_NO_HAZARD_FOUND", "No hazard found on inspection",
     "The site was inspected and no hazard was found."),
]


def _parents(bind) -> dict[str, str | None]:
    return dict(bind.execute(sa.text(
        "SELECT organization_id, parent_organization_id FROM ticketing.organizations"
    )).all())


def _ministry(parents: dict[str, str | None], org_id: str | None) -> str | None:
    """Top organization above ``org_id`` (itself if it has no parent). Cycle-guarded."""
    seen: set[str] = set()
    while org_id and org_id in parents and org_id not in seen:
        seen.add(org_id)
        if not parents[org_id]:
            return org_id
        org_id = parents[org_id]
    return None


# A workflow that serves road-hazard reports AND another route: the general five, then the road-works
# actions most road-hazard reports close with, up to the 8 a workflow can hold.
ROAD_WORKS_FOR_A_SHARED_WORKFLOW = ["ROAD_REPAIRED", "ROAD_MADE_SAFE", "ROAD_NO_HAZARD_FOUND"]


def starter_codes(*, sensitive: bool, road_hazard: bool, other_route: bool) -> list[str]:
    """Step 3's rule for one workflow: the codes of its starting list, in order."""
    if sensitive:
        return []
    general = [code for code, _label, _wording in GENERAL]
    if road_hazard and not other_route:
        return [code for code, _label, _wording in ROAD_WORKS]
    if road_hazard:
        return general + ROAD_WORKS_FOR_A_SHARED_WORKFLOW
    return general


def assign_workflow_organizations(bind) -> str | None:
    """Step 1. Returns the one ministry that implements projects, or None. Raises on ambiguity."""
    parents = _parents(bind)
    implementing = {
        m for m in (
            _ministry(parents, ia) for (ia,) in bind.execute(sa.text(
                "SELECT implementing_agency_org_id FROM ticketing.projects "
                "WHERE implementing_agency_org_id IS NOT NULL"
            )).all()
        ) if m
    }
    only_ministry = next(iter(implementing)) if len(implementing) == 1 else None

    ownerless = bind.execute(sa.text(
        "SELECT workflow_id, workflow_key FROM ticketing.workflow_definitions "
        "WHERE owner_organization_id IS NULL ORDER BY workflow_key"
    )).all()
    for workflow_id, workflow_key in ownerless:
        used_by = {
            m for m in (
                _ministry(parents, ia) for (ia,) in bind.execute(sa.text(
                    """
                    SELECT p.implementing_agency_org_id
                    FROM ticketing.project_workflows pw
                    JOIN ticketing.projects p ON p.project_id = pw.project_id
                    WHERE pw.workflow_id = :wid AND p.implementing_agency_org_id IS NOT NULL
                    """
                ), {"wid": workflow_id}).all()
            ) if m
        }
        if len(used_by) > 1:
            raise RuntimeError(
                f"Workflow {workflow_key} ({workflow_id}) is used by projects of several ministries "
                f"({', '.join(sorted(used_by))}); give it an organization by hand, then re-run."
            )
        owner = next(iter(used_by)) if used_by else only_ministry
        if owner is None:
            if len(implementing) > 1:
                raise RuntimeError(
                    f"Workflow {workflow_key} ({workflow_id}) is used by no project and several "
                    f"ministries implement projects ({', '.join(sorted(implementing))}); give it an "
                    "organization by hand, then re-run."
                )
            continue  # no ministry on this database at all — nothing to assign yet
        bind.execute(
            sa.text("UPDATE ticketing.workflow_definitions SET owner_organization_id = :o WHERE workflow_id = :w"),
            {"o": owner, "w": workflow_id},
        )
    return only_ministry


def upgrade() -> None:
    op.create_table(
        "resolution_actions",
        sa.Column("code", sa.String(64), primary_key=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("default_wording", sa.Text(), nullable=False),
        sa.Column(
            "owner_organization_id", sa.String(64),
            sa.ForeignKey("ticketing.organizations.organization_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "counts_as_code", sa.String(64),
            sa.ForeignKey("ticketing.resolution_actions.code", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("created_by_user_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="ticketing",
    )
    op.create_index(
        "idx_resolution_actions_owner_org", "resolution_actions", ["owner_organization_id"],
        schema="ticketing",
    )
    op.create_table(
        "workflow_resolution_actions",
        sa.Column(
            "workflow_id", sa.String(36),
            sa.ForeignKey("ticketing.workflow_definitions.workflow_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "code", sa.String(64),
            sa.ForeignKey("ticketing.resolution_actions.code", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        schema="ticketing",
    )
    op.create_index(
        "idx_workflow_resolution_actions_code", "workflow_resolution_actions", ["code"],
        schema="ticketing",
    )

    bind = op.get_bind()
    ministry = assign_workflow_organizations(bind)
    if ministry is None:
        return  # an empty database: the seed scripts create the actions and their workflows' lists

    insert_action = sa.text(
        "INSERT INTO ticketing.resolution_actions (code, label, default_wording, owner_organization_id, is_active) "
        "VALUES (:code, :label, :wording, :owner, TRUE)"
    )
    for code, label, wording in GENERAL + ROAD_WORKS:
        bind.execute(insert_action, {"code": code, "label": label, "wording": wording, "owner": ministry})

    parents = _parents(bind)
    workflows = bind.execute(
        sa.text(
            """
            SELECT w.workflow_id,
                   w.owner_organization_id,
                   lower(coalesce(w.workflow_type, '')) = 'seah' AS sensitive,
                   EXISTS (
                       SELECT 1 FROM ticketing.project_workflows pw
                       WHERE pw.workflow_id = w.workflow_id
                         AND pw.intake_route = 'road_hazard_grievance'
                   ) AS road_hazard,
                   EXISTS (
                       SELECT 1 FROM ticketing.project_workflows pw
                       WHERE pw.workflow_id = w.workflow_id
                         AND pw.intake_route IS DISTINCT FROM 'road_hazard_grievance'
                   ) AS other_route
            FROM ticketing.workflow_definitions w
            """
        )
    ).all()
    insert_selection = sa.text(
        "INSERT INTO ticketing.workflow_resolution_actions (workflow_id, code, sort_order) "
        "VALUES (:workflow_id, :code, :sort_order)"
    )
    for workflow_id, owner, sensitive, road_hazard, other_route in workflows:
        # Only a workflow of this ministry (or below it) can use this ministry's actions.
        if _ministry(parents, owner) != ministry:
            continue
        for i, code in enumerate(starter_codes(sensitive=sensitive, road_hazard=road_hazard, other_route=other_route)):
            bind.execute(
                insert_selection,
                {"workflow_id": workflow_id, "code": code, "sort_order": (i + 1) * 10},
            )


def downgrade() -> None:
    # Drops both tables. ⚠ Restores nothing an edit made: an action added or reworded after this ran
    # is gone. ⚠ **Leaves the workflow and template organizations step 1 assigned** — deliberately:
    # the previous release reads an owned workflow correctly (it only ever stamped owners), and
    # un-assigning would need a record of which ones this migration set, which it does not keep.
    # Ticket events keep their `resolution_category` codes and label snapshots; the previous
    # release reads the codes through its own hard-coded list, which knows only the general five.
    op.drop_index("idx_workflow_resolution_actions_code", table_name="workflow_resolution_actions", schema="ticketing")
    op.drop_table("workflow_resolution_actions", schema="ticketing")
    op.drop_index("idx_resolution_actions_owner_org", table_name="resolution_actions", schema="ticketing")
    op.drop_table("resolution_actions", schema="ticketing")
