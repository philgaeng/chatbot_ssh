"""Province-level fallback when no officer matches ticket district/municipality."""

from ticketing.engine.workflow_engine import (
    _province_code_for_location,
    _scope_candidates,
    auto_assign_officer,
)
from ticketing.models.base import SessionLocal


def test_province_code_for_jhapa_municipality():
    db = SessionLocal()
    try:
        assert _province_code_for_location("P1_JHA_BIR", db) == "P1"
    finally:
        db.close()


def test_jhapa_ticket_falls_back_to_morang_l1_in_db():
    """With only mock-officer-site-l1 scoped to P1_MOR, a P1_JHA_BIR ticket still gets an assignee."""
    db = SessionLocal()
    try:
        candidates = _scope_candidates(
            "site_safeguards_focal_person",
            "DOR",
            "P1_JHA_BIR",
            "KL_ROAD",
            db,
        )
        assert "mock-officer-site-l1" in candidates

        assigned = auto_assign_officer(
            "site_safeguards_focal_person",
            "DOR",
            "P1_JHA_BIR",
            "KL_ROAD",
            db,
        )
        assert assigned == "mock-officer-site-l1"
    finally:
        db.close()
