"""Tests for Keycloak provisioning when appointing admin scopes."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ticketing.services.officer_admin import (
    officer_eligible_for_invite_resend,
    provision_admin_scope_keycloak,
)


@pytest.mark.parametrize(
    ("kc_user", "onboarding", "expected"),
    [
        (None, None, True),
        ({"enabled": True, "requiredActions": []}, "active", False),
        ({"enabled": True, "requiredActions": ["UPDATE_PASSWORD"]}, None, True),
        ({"enabled": False, "requiredActions": []}, None, True),
        (None, "invited", True),
    ],
)
def test_officer_eligible_for_invite_resend(kc_user, onboarding, expected):
    db = MagicMock()
    if onboarding:
        ob = MagicMock()
        ob.status = onboarding
        db.get.return_value = ob
    else:
        db.get.return_value = None

    with patch(
        "ticketing.services.officer_admin.keycloak_configured",
        return_value=kc_user is not None or onboarding != "invited",
    ), patch(
        "ticketing.services.officer_admin._keycloak_admin",
    ), patch(
        "ticketing.services.officer_admin._keycloak_find_user",
        return_value=kc_user,
    ):
        if onboarding == "invited":
            assert officer_eligible_for_invite_resend(db, "User@Example.com") is True
        else:
            assert officer_eligible_for_invite_resend(db, "user@example.com") is expected


def test_provision_admin_scope_creates_keycloak_user_when_missing():
    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = ["country_admin"]

    with patch(
        "ticketing.services.officer_admin.keycloak_configured",
        return_value=True,
    ), patch(
        "ticketing.services.officer_admin._keycloak_admin",
    ), patch(
        "ticketing.services.officer_admin._keycloak_find_user",
        return_value=None,
    ), patch(
        "ticketing.services.officer_admin.keycloak_create_user",
    ) as create_user, patch(
        "ticketing.services.officer_admin._upsert_officer_onboarding",
    ) as upsert_ob:
        status = provision_admin_scope_keycloak(
            db, "Anish@dor.gov.np", "country_admin", "DOR"
        )

    assert status == "invited"
    create_user.assert_called_once_with("anish@dor.gov.np", "country_admin", "DOR")
    upsert_ob.assert_called_once_with(db, "anish@dor.gov.np", "invited")


def test_provision_admin_scope_resends_for_pending_keycloak_user():
    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = ["country_admin"]
    kc_user = {"id": "kc-1", "enabled": True, "requiredActions": ["UPDATE_PASSWORD"]}

    with patch(
        "ticketing.services.officer_admin.keycloak_configured",
        return_value=True,
    ), patch(
        "ticketing.services.officer_admin._keycloak_admin",
    ), patch(
        "ticketing.services.officer_admin._keycloak_find_user",
        return_value=kc_user,
    ), patch(
        "ticketing.services.officer_admin._keycloak_send_or_create_setup_email",
    ) as send_setup:
        status = provision_admin_scope_keycloak(
            db, "anishshrestha.dor@gmail.com", "country_admin", "DOR"
        )

    assert status == "invited"
    send_setup.assert_called_once_with(
        db, "anishshrestha.dor@gmail.com", "country_admin", "DOR"
    )


def test_provision_admin_scope_skips_email_for_active_user():
    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = ["country_admin"]
    kc_user = {"id": "kc-1", "enabled": True, "requiredActions": []}

    with patch(
        "ticketing.services.officer_admin.keycloak_configured",
        return_value=True,
    ), patch(
        "ticketing.services.officer_admin._keycloak_admin",
    ), patch(
        "ticketing.services.officer_admin._keycloak_find_user",
        return_value=kc_user,
    ), patch(
        "ticketing.services.officer_admin.keycloak_update_user_attributes",
    ), patch(
        "ticketing.services.officer_admin.keycloak_resend_invite_email",
    ) as resend, patch(
        "ticketing.services.officer_admin._upsert_officer_onboarding",
    ) as upsert_ob:
        status = provision_admin_scope_keycloak(
            db, "anishshrestha.dor@gmail.com", "country_admin", "DOR"
        )

    assert status == "active"
    resend.assert_not_called()
    upsert_ob.assert_called_once_with(db, "anishshrestha.dor@gmail.com", "active")


def test_provision_admin_scope_force_invite_for_active_user():
    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = ["country_admin"]
    kc_user = {"id": "kc-1", "enabled": True, "requiredActions": []}

    with patch(
        "ticketing.services.officer_admin.keycloak_configured",
        return_value=True,
    ), patch(
        "ticketing.services.officer_admin._keycloak_admin",
    ), patch(
        "ticketing.services.officer_admin._keycloak_find_user",
        return_value=kc_user,
    ), patch(
        "ticketing.services.officer_admin._keycloak_send_or_create_setup_email",
    ) as send_setup:
        status = provision_admin_scope_keycloak(
            db,
            "anishshrestha.dor@gmail.com",
            "country_admin",
            "DOR",
            force_invite=True,
        )

    assert status == "invited"
    send_setup.assert_called_once()
