"""Tickets router package (H2-02 Pass 4).

Split of the former monolithic ``routers/tickets.py`` into cohesive submodules.
The public surface is unchanged: ``main.py`` imports ``tickets.router`` and
mounts it at ``/api/v1`` exactly as before. The full route set is pinned by
``tests/ticketing/test_route_snapshot.py`` — do not change paths here.
"""
from fastapi import APIRouter

from . import (
    actions,
    collaboration,
    crud,
    files,
    pii,
    summary,
)

router = APIRouter()
router.include_router(crud.router)
router.include_router(actions.router)
router.include_router(files.router)
router.include_router(pii.router)
router.include_router(collaboration.router)
router.include_router(summary.router)

__all__ = ["router"]
