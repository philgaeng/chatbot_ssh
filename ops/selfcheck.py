# SPDX-License-Identifier: Apache-2.0

"""
Container healthcheck for the ops scheduler.

Exit 0 only if BOTH are true, else exit 1 so Docker marks the container unhealthy and
the host watchdog restarts it:

  1. the scheduler wrote a tick within the last 180s, and
  2. the database is reachable with the credentials this container actually holds.

⚠ (2) was added 2026-08-24, and the reason is the whole point of this file. Between
2026-08-21 and 2026-08-24 the ops container could not authenticate to Postgres at all —
253 consecutive failures, every report row `n/a` — and it reported `healthy` the entire
time, because ticking and connecting are different things and only the first was checked.
A healthcheck that cannot fail when the service is useless is decoration.

Compose allows 3 consecutive failures at 60s intervals, so a transient database blip does
not flap the container; a credential that no longer works does.

Run: python -m ops.selfcheck
"""
from __future__ import annotations

import datetime as dt
import sys

from ops.config import get_settings


def _tick_is_fresh(s) -> bool:
    with open(s.ops_status_file) as fh:
        ts = dt.datetime.fromisoformat(fh.read().strip())
    age = (dt.datetime.now(dt.timezone.utc) - ts).total_seconds()
    if age <= 180:
        return True
    sys.stderr.write(f"ops tick stale: {age:.0f}s old\n")
    return False


def _database_is_reachable() -> bool:
    """Prove the credentials work. Imported lazily so a config error still reports unhealthy."""
    from sqlalchemy import text

    from ops.db import session_scope

    with session_scope() as db:
        db.execute(text("SELECT 1"))
    return True


def main() -> int:
    s = get_settings()
    try:
        if not _tick_is_fresh(s):
            return 1
    except Exception as exc:  # pragma: no cover
        sys.stderr.write(f"ops selfcheck failed (tick): {exc}\n")
        return 1

    try:
        _database_is_reachable()
    except Exception as exc:
        # The failure that hid for three days. Name the role, because the message a
        # responder needs is "which credential", not "something went wrong".
        sys.stderr.write(
            f"ops selfcheck failed (database, role={s.ops_db_user}): "
            f"{type(exc).__name__}: {exc}\n"
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
