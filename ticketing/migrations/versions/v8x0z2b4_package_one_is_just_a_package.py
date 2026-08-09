# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""The first package is "Package 1" — a package like any other.

Philippe, 2026-08-09: *"I don't understand the name of the default package — it should be
package 1 by default and could be renamed obviously as well as a description added."*

`is_unnamed` was added five days earlier (`t6v8x0z2`) for the single-package project: the row
took the **project's** name and the card hid its code, name and description, showing
"Everywhere this project works" instead. Two problems, both visible the first time somebody
built a project with three packages:

  * the default name was the project's, which reads as a mistake next to "Package 2" and
    "Package 3";
  * hiding the fields meant the one package you are most likely to describe (chainage, scope)
    was the one you could not.

The concept is not worth a column. A package that is not split out is still a package, and
"Package 1" says so without inventing a display mode — so the flag goes, and with it the
"this project is not split into packages" checkbox it drove.

Existing rows keep their words where somebody chose them: only the ones still carrying the
flag are renamed, because those are exactly the ones nobody named.

Revision ID: v8x0z2b4
Revises: t6v8x0z2
Create Date: 2026-08-09
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "v8x0z2b4"
down_revision: Union[str, None] = "t6v8x0z2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The auto-created rows were named after their project and never shown. Name them.
    op.execute(
        """
        UPDATE ticketing.project_packages
        SET name = 'Package 1', updated_at = now()
        WHERE is_unnamed IS TRUE
        """
    )
    op.drop_column("project_packages", "is_unnamed", schema="ticketing")


def downgrade() -> None:
    # Comes back False everywhere: which rows were auto-created is not recoverable, and
    # guessing would re-hide a name somebody has since chosen.
    op.add_column(
        "project_packages",
        sa.Column("is_unnamed", sa.Boolean(), nullable=False, server_default=sa.false()),
        schema="ticketing",
    )
