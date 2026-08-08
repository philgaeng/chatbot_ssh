# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""Every project has at least one package, and coverage is declared there.

Decided 2026-08-08 (Philippe): *"we create first the package — a project with one package is
like a project without package"*. A package has four attributes: code, name, description,
locations. Coverage stops being declared twice.

**Why.** `project_locations` and `package_locations` were two parallel declarations of where a
project works, and only one of them routed anything: officer resolution goes location →
*package* → officer scope (`engine/workflow_engine.py`, branch C).
`services/project_routing.py` even carries the comment that location→package resolution there is
"reserved, unused today". Nothing read `project_locations` except its own CRUD and go-live's D1,
which asserted the list was non-empty. Predictably the two drifted — on staging, one project had
5 packages and 0 project locations, another had 2 project locations and 0 package locations.
Nobody keeps a second copy in sync when only the first one matters.

**What this does.**
  1. `is_unnamed` on a package — the single-package project. The row still needs a code and a
     name (routing and the unique constraint depend on them), so they are filled from the
     project; the flag only says the screen should not ask for them. A project with one package
     then looks like a project with no packages, which is the point.
  2. Back-fills a package for every project that has none, taking the project's own name.
  3. Moves `project_locations` into that package **only where the project has exactly one
     package** — with two or more, which one inherits a district is a guess, and guessing
     mis-routes grievances silently.

`ticketing.project_locations` is **left in place**, unread. Dropping a table with rows in it is
not something to bundle into a behaviour change; the cleanup is logged in
`docs/sprints/followups/`.

Revision ID: t6v8x0z2
Revises: r4t6v8x0
Create Date: 2026-08-08
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "t6v8x0z2"
down_revision: Union[str, None] = "r4t6v8x0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "project_packages",
        sa.Column("is_unnamed", sa.Boolean(), nullable=False, server_default=sa.false()),
        schema="ticketing",
    )

    # 1. A package for every project that has none. `is_unnamed` because nobody chose these
    #    words — the project's own name stands in until someone splits the project up.
    op.execute(
        """
        INSERT INTO ticketing.project_packages
            (package_id, project_id, package_code, name, description,
             is_active, is_unnamed, created_at, updated_at)
        SELECT gen_random_uuid()::text, p.project_id, '01', p.name, NULL,
               TRUE, TRUE, now(), now()
        FROM ticketing.projects p
        WHERE NOT EXISTS (
            SELECT 1 FROM ticketing.project_packages pk WHERE pk.project_id = p.project_id
        )
        """
    )

    # 2. Coverage moves to the package — only where there is exactly one, so nothing is guessed.
    #    ON CONFLICT: a location already on the package is already the answer.
    op.execute(
        """
        INSERT INTO ticketing.package_locations (package_id, location_code)
        SELECT pk.package_id, pl.location_code
        FROM ticketing.project_locations pl
        JOIN ticketing.project_packages pk ON pk.project_id = pl.project_id
        WHERE (
            SELECT count(*) FROM ticketing.project_packages pk2
            WHERE pk2.project_id = pl.project_id
        ) = 1
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    # The back-filled packages are deliberately NOT removed: by the time anyone downgrades,
    # locations and officer scopes may hang off them, and deleting one cascades to both.
    op.drop_column("project_packages", "is_unnamed", schema="ticketing")
