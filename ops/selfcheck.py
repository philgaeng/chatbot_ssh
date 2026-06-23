"""
Container healthcheck for the ops scheduler.

Exit 0 if the scheduler wrote a tick within the last 180s, else exit 1 so Docker
marks the container unhealthy and the host watchdog restarts it.

Run: python -m ops.selfcheck
"""
from __future__ import annotations

import datetime as dt
import sys

from ops.config import get_settings


def main() -> int:
    s = get_settings()
    try:
        with open(s.ops_status_file) as fh:
            ts = dt.datetime.fromisoformat(fh.read().strip())
        age = (dt.datetime.now(dt.timezone.utc) - ts).total_seconds()
        if age <= 180:
            return 0
        sys.stderr.write(f"ops tick stale: {age:.0f}s old\n")
        return 1
    except Exception as exc:  # pragma: no cover
        sys.stderr.write(f"ops selfcheck failed: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
