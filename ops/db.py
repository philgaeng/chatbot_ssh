"""
DB engine/session for the ops monitor (connects as scoped `ops_app` role).

Helpers to record health-check results to ops.system_health_checks. All writes
go through the scoped role; a write attempt against ticketing.*/public.* will be
denied by Postgres grants (that's intentional — see spec 12 §3 item 9).
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ops.config import get_settings
from ops.models import DependencyFinding, SystemHealthCheck  # noqa: F401

logger = logging.getLogger("ops.db")

_settings = get_settings()
engine = create_engine(_settings.database_url, pool_pre_ping=True, pool_size=3, max_overflow=5)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def session_scope() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def record_check(
    check_name: str,
    status: str,
    *,
    value: Optional[dict] = None,
    message: Optional[str] = None,
) -> None:
    """Persist a single health-check result. Never raises (monitoring must not crash)."""
    try:
        with session_scope() as db:
            db.add(
                SystemHealthCheck(
                    check_name=check_name,
                    status=status,
                    value_json=value,
                    message=message,
                )
            )
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to record check %s: %s", check_name, exc)
