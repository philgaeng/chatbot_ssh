"""Tests for invited → active onboarding sync from Keycloak state."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from ticketing.services.officer_admin import (
    activate_officer_onboarding,
    sync_officer_onboarding_status,
)


def test_sync_promotes_invited_when_keycloak_complete():
    db = MagicMock()
    ob = MagicMock()
    ob.status = "invited"
    db.get.return_value = ob

    with patch(
        "ticketing.services.officer_admin.keycloak_onboarding_complete",
        return_value=True,
    ):
        changed = sync_officer_onboarding_status(db, "philgaeng@gmail.com")

    assert changed is True
    assert ob.status == "active"


def test_sync_skips_when_still_pending_in_keycloak():
    db = MagicMock()
    ob = MagicMock()
    ob.status = "invited"
    db.get.return_value = ob

    with patch(
        "ticketing.services.officer_admin.keycloak_onboarding_complete",
        return_value=False,
    ):
        changed = sync_officer_onboarding_status(db, "anishshrestha.dor@gmail.com")

    assert changed is False
    assert ob.status == "invited"


def test_sync_skips_already_active():
    db = MagicMock()
    ob = MagicMock()
    ob.status = "active"
    db.get.return_value = ob

    with patch(
        "ticketing.services.officer_admin.keycloak_onboarding_complete",
    ) as kc_complete:
        changed = sync_officer_onboarding_status(db, "admin@grm.local")

    assert changed is False
    kc_complete.assert_not_called()


def test_activate_creates_row_when_missing():
    db = MagicMock()
    db.get.return_value = None

    with patch("ticketing.services.officer_admin.OfficerOnboarding") as ob_cls:
        changed = activate_officer_onboarding(db, "User@Example.com")

    assert changed is True
    ob_cls.assert_called_once()
    assert ob_cls.call_args.kwargs["user_id"] == "user@example.com"
    assert ob_cls.call_args.kwargs["status"] == "active"
