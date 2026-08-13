# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""Every package has a QR token.

Philippe, 2026-08-09: *"the QR are not generated automatically… the QR should be generated when
we create the packages"*.

They were created **lazily**, and only by the QR codes page: listing tokens auto-creates the
missing ones as a side effect. A package created and never looked at there simply had none, so
go-live's D2 said "Optional: add QR for 01, 02" and its "Fix →" jumped to **Packages** — a
screen with no QR anything, because QR codes live on their own page. Nothing was broken enough
to block, which is why it sat there looking unfinished.

`create_package` and the project's first package now mint the token at creation. This gives one
to everything created before that.

The token value is generated in Python (`secrets.token_hex(8)`, `models/qr_token.py`), so this
does it in a loop rather than one INSERT…SELECT — there are tens of packages, not thousands, and
matching the application's generator matters more than the round trips.

Revision ID: z2b4d6f8
Revises: x0z2b4d6
Create Date: 2026-08-09
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "z2b4d6f8"
down_revision: Union[str, None] = "x0z2b4d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from ticketing.models.qr_token import _token

    bind = op.get_bind()
    missing = bind.execute(
        sa.text(
            """
            SELECT pk.package_id
            FROM ticketing.project_packages pk
            WHERE NOT EXISTS (
                SELECT 1 FROM ticketing.qr_tokens q
                WHERE q.package_id = pk.package_id AND q.is_active IS TRUE
            )
            """
        )
    ).scalars().all()

    for package_id in missing:
        bind.execute(
            sa.text(
                """
                INSERT INTO ticketing.qr_tokens (token, package_id, is_active, created_at)
                VALUES (:token, :package_id, TRUE, now())
                """
            ),
            {"token": _token(), "package_id": package_id},
        )


def downgrade() -> None:
    # Deliberately empty. Which tokens this created is not recorded, and a printed QR code that
    # stops resolving is worse than a spare row — the code is already on a signboard by then.
    pass
