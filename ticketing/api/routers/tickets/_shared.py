# SPDX-License-Identifier: Apache-2.0

"""Shared helpers for the tickets router package.

Small, cross-cutting utilities used by more than one submodule of the split
``routers/tickets`` package (H2-02 Pass 4). Kept dependency-light (stdlib +
``ticketing.api.dependencies`` only) so every submodule can import it without
an import cycle.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from ticketing.api.dependencies import CurrentUser

logger = logging.getLogger(__name__)


def _enqueue_celery(task, *args, **kwargs) -> None:
    """Queue a Celery job without failing the HTTP response if Redis is down."""
    try:
        task.delay(*args, **kwargs)
    except Exception as exc:
        logger.warning("Celery enqueue failed (non-fatal): %s", exc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


def _actor_role(current_user: CurrentUser) -> Optional[str]:
    """Snapshot the first role key at write time for audit correlation."""
    return current_user.role_keys[0] if getattr(current_user, "role_keys", None) else None
