# SPDX-License-Identifier: Apache-2.0
"""
The grm Keycloak themes: the officer setup email (`GRM-133`) and the login auto-continue (`GRM-134`).

**`GRM-133`, measured on staging 2026-09-15:** through the same relay, sender and mailbox, a plain email
reached the inbox and Keycloak's default setup email (*Update Your Account* / *"Your administrator has
just requested that you update your … account"*) was filed as spam. The realm now uses a `grm` email
theme. Its wording is pinned here so the default cannot come back unnoticed, and so the link and expiry
placeholders stay in the text.

**`GRM-134`, measured on a local realm 2026-09-15** (Mailpit, throwaway users, deleted): a link scanner
that opens the setup link and runs the theme's script, reaching the password form, does **not** use
the link up. The officer then opens the same link, sets a password and is forwarded to the GRM login.
The same measurement found the script HTML-escaping its URL: in a `<script>`, `&amp;` is literal, so
Keycloak received `amp;client_id` / `amp;tab_id` (also visible in staging's nginx log). The escaping is
pinned below.
"""
from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

from ticketing.auth import keycloak_setup as ks

THEME = Path(__file__).resolve().parents[2] / "deployment" / "keycloak" / "themes" / "grm"
KEYCLOAK_DEFAULT_SUBJECT = "Update Your Account"


def _email_messages() -> dict[str, str]:
    out = {}
    for line in (THEME / "email" / "messages" / "messages_en.properties").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            out[key] = value
    return out


def test_the_email_theme_extends_keycloaks() -> None:
    assert (THEME / "email" / "theme.properties").read_text().strip() == "parent=keycloak"


def test_the_setup_email_is_not_keycloaks_default() -> None:
    msgs = _email_messages()
    assert msgs["executeActionsSubject"] != KEYCLOAK_DEFAULT_SUBJECT
    for key in ("executeActionsBody", "executeActionsBodyHtml"):
        assert "Your administrator has just requested" not in msgs[key]


def test_the_setup_email_keeps_the_link_and_how_long_it_works() -> None:
    """{0} is the link, {4} the expiry ("7 days"). Lose {0} and the email cannot be acted on."""
    msgs = _email_messages()
    for key in ("executeActionsBody", "executeActionsBodyHtml"):
        assert "{0}" in msgs[key] and "{4}" in msgs[key], key
    assert 'href="{0}"' in msgs["executeActionsBodyHtml"]


def test_the_auto_continue_script_js_escapes_its_url() -> None:
    info = (THEME / "login" / "info.ftl").read_text(encoding="utf-8")
    scripts = re.findall(r"<script>(window\..*?)</script>", info, re.S)
    assert len(scripts) == 2, "actionUri and pageRedirectUri each have an auto-continue"
    for script in scripts:
        assert re.fullmatch(r'window\.location\.replace\("\$\{\w+\?js_string\?no_esc\}"\);', script.strip()), script


def test_setup_puts_the_realm_on_both_grm_themes() -> None:
    admin = MagicMock()
    ks.setup_realm_login_theme(admin)
    admin.update_realm.assert_called_once_with(ks.REALM, {"loginTheme": "grm", "emailTheme": "grm"})


def test_theme_only_changes_nothing_else() -> None:
    admin = MagicMock()
    with patch.object(ks, "_realm_admin", return_value=admin), patch.object(
        ks, "get_settings", return_value=MagicMock(keycloak_admin_url="http://keycloak:8080")
    ), patch.object(ks, "_master_admin") as master:
        ks.main(["--theme-only"])

    assert [c.args[1] for c in admin.update_realm.call_args_list] == [{"loginTheme": "grm", "emailTheme": "grm"}]
    admin.update_client.assert_not_called()
    admin.create_user.assert_not_called()
    master.assert_not_called()
