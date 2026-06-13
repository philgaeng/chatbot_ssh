"""
Migrate ticketing.locations (Nepal NP) from legacy NP_* PKs to canonical P1/P1_* codes.

Runs from Alembic revision q9r7s1u3 only (or manually after that revision's schema).
Uses raw SQL — not ORM models — so it stays valid when later migrations add columns.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session, sessionmaker

from ticketing.constants.nepal_canonical_locations import plan_np_legacy_to_canonical_renames

log = logging.getLogger(__name__)

_REF_TABLES = (
    "ticketing.workflow_assignments",
    "ticketing.officer_scopes",
    "ticketing.user_roles",
    "ticketing.tickets",
    "ticketing.project_locations",
    "ticketing.package_locations",
)


def _location_exists(session: Session, location_code: str) -> bool:
    row = session.execute(
        text(
            "SELECT 1 FROM ticketing.locations WHERE location_code = :code LIMIT 1"
        ),
        {"code": location_code},
    ).first()
    return row is not None


def _migrate_ticketing_np_locations_session(session: Session) -> int:
    loc_rows = session.execute(
        text(
            """
            SELECT location_code, country_code, level_number, parent_location_code, source_id
            FROM ticketing.locations
            WHERE country_code = :country_code
            """
        ),
        {"country_code": "NP"},
    ).mappings().all()
    if not loc_rows:
        log.info("No NP locations in DB — skipping canonical migration.")
        return 0

    has_legacy = any(
        (row["location_code"] or "").startswith("NP_")
        or not _looks_canonical(row["location_code"])
        for row in loc_rows
    )
    if not has_legacy:
        log.info("NP locations already use canonical codes — skipping.")
        return 0

    codes_np = [row["location_code"] for row in loc_rows]
    tr_rows = session.execute(
        text(
            """
            SELECT location_code, lang_code, name
            FROM ticketing.location_translations
            WHERE location_code IN :codes
            """
        ).bindparams(bindparam("codes", expanding=True)),
        {"codes": codes_np},
    ).mappings().all()
    loc_dicts: list[dict[str, Any]] = [
        {
            "location_code": row["location_code"],
            "country_code": row["country_code"],
            "level_number": row["level_number"],
            "parent_location_code": row["parent_location_code"],
            "source_id": row["source_id"],
        }
        for row in loc_rows
    ]
    trans_dicts = [
        {"location_code": t["location_code"], "lang_code": t["lang_code"], "name": t["name"]}
        for t in tr_rows
    ]

    rename = plan_np_legacy_to_canonical_renames(loc_dicts, trans_dicts)
    pairs = [(o, n) for o, n in rename.items() if o != n]
    if not pairs:
        return 0

    level_map = {row["location_code"]: row["level_number"] for row in loc_rows}
    pairs.sort(key=lambda on: (-level_map.get(on[0], 0), on[0]))

    done = 0
    for old, new in pairs:
        if not _location_exists(session, old):
            continue
        if _location_exists(session, new):
            log.warning("Canonical migration: skip %s → %s (target already exists)", old, new)
            continue

        session.execute(
            text(
                """
                INSERT INTO ticketing.locations
                  (location_code, country_code, level_number, parent_location_code,
                   source_id, is_active, created_at, updated_at)
                SELECT :new_code, country_code, level_number, parent_location_code,
                       source_id, is_active, created_at, NOW()
                FROM ticketing.locations WHERE location_code = :old_code
                """
            ),
            {"new_code": new, "old_code": old},
        )

        session.execute(
            text(
                "UPDATE ticketing.location_translations SET location_code = :new_code "
                "WHERE location_code = :old_code"
            ),
            {"new_code": new, "old_code": old},
        )

        for tbl in _REF_TABLES:
            session.execute(
                text(
                    f"UPDATE {tbl} SET location_code = :new_code "
                    f"WHERE location_code = :old_code"  # noqa: S608
                ),
                {"new_code": new, "old_code": old},
            )

        session.execute(
            text(
                "UPDATE ticketing.locations SET parent_location_code = :new_code "
                "WHERE parent_location_code = :old_code"
            ),
            {"new_code": new, "old_code": old},
        )

        session.execute(
            text("DELETE FROM ticketing.locations WHERE location_code = :old_code"),
            {"old_code": old},
        )
        done += 1
        log.info("Canonical location PK: %s → %s", old, new)

    return done


def _looks_canonical(code: str | None) -> bool:
    c = (code or "").strip()
    return (
        len(c) >= 2
        and c[0] == "P"
        and c[1].isdigit()
        and not c.startswith("NP_")
    )


def migrate(bind: Any) -> int:
    """
    Run migration using a SQLAlchemy engine or connection-like *bind*.
    Returns number of location PK swaps performed (renamed rows).
    """
    SessionCls = sessionmaker(bind=bind, class_=Session, autoflush=False, autocommit=False)
    session = SessionCls()
    try:
        n = _migrate_ticketing_np_locations_session(session)
        session.commit()
        return n
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from ticketing.models.base import SessionLocal

    s = SessionLocal()
    try:
        n = _migrate_ticketing_np_locations_session(s)
        s.commit()
        print(f"Migrated {n} location PK(s) to canonical form.")
    except Exception as exc:
        s.rollback()
        raise exc
    finally:
        s.close()
