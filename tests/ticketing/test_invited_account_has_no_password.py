# SPDX-License-Identifier: Apache-2.0
"""
An invited officer's account can only be claimed through the setup email (`GRM-131`).

**Measured on Keycloak 2026-09-15** (local realm, throwaway users, deleted after): an account created
the way `keycloak_create_user` created every invitee — enabled, `UPDATE_PASSWORD` pending, a
*temporary* password — accepts that password on Keycloak's browser login, shows the set-a-new-password
form, saves what the typist enters and redirects to the officer UI with an auth code. The temporary
password was the documented demo one, so knowing an invitee's email was enough to take the account
before they did. The same login against an account with **no** password: *Invalid username or password*.

Also measured on staging the same day: an invite whose email Keycloak refused (`GRM-130`) left that
account behind, enabled, with no ticketing row pointing at it.

These pin: no password on a new account; the account removed when its email fails; a re-sent setup
strips a password the officer never chose, and only then; and the clean-up for accounts that exist.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from ticketing.auth import keycloak_setup as ks
from ticketing.services import officer_admin as oa

EMAIL = "new.officer@dor.gov.np"
PENDING = ["UPDATE_PASSWORD"]


def _admin(credentials: list[dict] | None = None) -> MagicMock:
    admin = MagicMock()
    admin.get_credentials.return_value = credentials or []
    return admin


def _patched(admin: MagicMock, found):
    return (
        patch.object(oa, "_keycloak_admin", return_value=admin),
        patch.object(oa, "_keycloak_find_user", side_effect=found if callable(found) else lambda *_: found),
        patch.object(oa, "_keycloak_invite_email_options", return_value=("ticketing-ui", "http://localhost:3002/login")),
    )


def test_a_new_account_is_created_without_a_password() -> None:
    admin = _admin()
    p1, p2, p3 = _patched(admin, {"id": "kc-1", "email": EMAIL, "enabled": True})
    with p1, p2, p3:
        oa.keycloak_create_user(EMAIL, "org_admin", "DOR")

    payload = admin.create_user.call_args.args[0]
    assert "credentials" not in payload, "an invitee's first password is set through the email, never by us"
    assert payload["requiredActions"] == PENDING
    admin.send_update_account.assert_called_once()
    admin.delete_user.assert_not_called()


def test_the_invite_api_takes_no_password() -> None:
    from ticketing.api.routers.users import OfficerInviteRequest

    assert "temp_password" not in OfficerInviteRequest.model_fields


def test_a_refused_email_leaves_no_account_behind() -> None:
    admin = _admin()
    admin.send_update_account.side_effect = Exception('400: b\'{"errorMessage":"Invalid redirect uri."}\'')
    p1, p2, p3 = _patched(admin, {"id": "kc-new", "email": EMAIL, "enabled": True})
    with p1, p2, p3, pytest.raises(HTTPException) as caught:
        oa.keycloak_create_user(EMAIL, "org_admin", "DOR")

    admin.delete_user.assert_called_once_with("kc-new")
    assert caught.value.status_code == 503


def test_an_account_that_already_existed_is_never_deleted() -> None:
    """The delete is for the account this call created — not a disabled one it is bringing back."""
    admin = _admin([{"id": "cred-old", "type": "password"}])
    admin.create_user.side_effect = Exception("409: User exists with same username")
    admin.send_update_account.side_effect = Exception("SMTP down")
    p1, p2, p3 = _patched(admin, {"id": "kc-old", "email": EMAIL, "enabled": False})
    with p1, p2, p3, pytest.raises(HTTPException):
        oa.keycloak_create_user(EMAIL, "org_admin", "DOR")

    admin.delete_user.assert_not_called()


def test_a_returning_disabled_account_loses_its_old_password() -> None:
    admin = _admin([{"id": "cred-old", "type": "password"}, {"id": "otp-1", "type": "otp"}])
    admin.create_user.side_effect = Exception("409: User exists with same username")
    p1, p2, p3 = _patched(admin, {"id": "kc-old", "email": EMAIL, "enabled": False})
    with p1, p2, p3:
        oa.keycloak_create_user(EMAIL, "org_admin", "DOR")

    admin.delete_credential.assert_called_once_with("kc-old", "cred-old")
    update = admin.update_user.call_args.kwargs["payload"]
    assert "credentials" not in update
    admin.send_update_account.assert_called_once()


def _resend(kc_user: dict, admin: MagicMock) -> None:
    with patch.object(oa, "keycloak_configured", return_value=True), patch.object(
        oa, "keycloak_invite_preflight", return_value={"ok": True}
    ), patch.object(oa, "_keycloak_admin", return_value=admin), patch.object(
        oa, "_keycloak_find_user", return_value=kc_user
    ), patch.object(
        oa, "_keycloak_invite_email_options", return_value=("ticketing-ui", "http://localhost:3002/login")
    ):
        oa.keycloak_resend_invite_email(EMAIL)


def test_resending_setup_strips_a_password_the_officer_never_chose() -> None:
    """⭐ How accounts invited before the fix get repaired one by one — `adangelo…` on staging."""
    admin = _admin([{"id": "cred-demo", "type": "password"}])
    _resend({"id": "kc-1", "email": EMAIL, "enabled": True, "requiredActions": PENDING}, admin)

    admin.delete_credential.assert_called_once_with("kc-1", "cred-demo")
    admin.send_update_account.assert_called_once()


def test_resending_setup_to_an_officer_who_finished_setup_keeps_their_password() -> None:
    """Their password is their own; the email only asks them to change it."""
    admin = _admin([{"id": "cred-own", "type": "password"}])
    _resend({"id": "kc-1", "email": EMAIL, "enabled": True, "requiredActions": []}, admin)

    admin.delete_credential.assert_not_called()
    admin.send_update_account.assert_called_once()


def _realm(users: list[dict], creds: dict[str, list[dict]]) -> MagicMock:
    admin = MagicMock()
    admin.get_users.return_value = users
    admin.get_credentials.side_effect = lambda uid: creds.get(uid, [])
    return admin


REALM_USERS = [
    {"id": "u-exposed", "username": "invited@dor.gov.np", "requiredActions": PENDING},
    {"id": "u-nopass", "username": "invited-after-fix@dor.gov.np", "requiredActions": PENDING},
    {"id": "u-active", "username": "active@dor.gov.np", "requiredActions": []},
    {"id": "u-demo", "username": ks.DEMO_OFFICERS[0]["username"], "requiredActions": PENDING},
]
REALM_CREDS = {
    "u-exposed": [{"id": "c1", "type": "password"}],
    "u-active": [{"id": "c2", "type": "password"}],
    "u-demo": [{"id": "c3", "type": "password"}],
}


def test_the_clean_up_counts_without_changing_anything_by_default() -> None:
    admin = _realm(REALM_USERS, REALM_CREDS)
    counts = ks.clear_invite_passwords(admin, apply=False)

    assert counts == {"setup_pending": 2, "with_password": 1, "cleared": 0, "demo_skipped": 1}
    admin.delete_credential.assert_not_called()


def test_the_clean_up_clears_only_pending_non_demo_accounts() -> None:
    admin = _realm(REALM_USERS, REALM_CREDS)
    counts = ks.clear_invite_passwords(admin, apply=True)

    assert counts["cleared"] == 1
    admin.delete_credential.assert_called_once_with("u-exposed", "c1")


def test_the_clean_up_logs_no_usernames(caplog: pytest.LogCaptureFixture) -> None:
    admin = _realm(REALM_USERS, REALM_CREDS)
    with patch.object(ks, "_realm_admin", return_value=admin), patch.object(
        ks, "get_settings", return_value=MagicMock(keycloak_admin_url="http://keycloak:8080")
    ), caplog.at_level("INFO"):
        ks.main(["--clear-invite-passwords"])

    assert "@" not in caplog.text.replace("http://keycloak:8080", "")
    admin.delete_credential.assert_not_called()
