# SPDX-License-Identifier: Apache-2.0

"""
Idempotent Keycloak realm setup for GRM ticketing.

Run once after Keycloak starts:
    docker compose -f docker-compose.yml -f docker-compose.grm.yml exec ticketing_api \\
        python -m ticketing.auth.keycloak_setup

Safe to re-run — every operation checks before creating.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any
from urllib.parse import urlsplit

from keycloak import KeycloakAdmin, KeycloakOpenIDConnection
from keycloak.exceptions import KeycloakGetError, KeycloakPostError

from ticketing.config.settings import get_settings
from ticketing.constants.demo_officers import keycloak_demo_officers

logger = logging.getLogger(__name__)

REALM = "grm"
CLIENT_UI = "ticketing-ui"   # public, PKCE, browser
CLIENT_API = "ticketing-api"  # confidential, for JWKS endpoint + service account

# Realm token lifespans (seconds) — D-012. Officer invite emails use actionTokenGeneratedByAdminLifespan.
# ⚠ THE ORDER IS THE POLICY: access token < idle window, with room for the UI's renewal lead
# (`isAccessTokenExpiringSoon(token, 60)` in lib/api.ts). A refresh token lives only as long as the
# idle window, and the UI renews on the officer's next request near the access token's end — so an
# access token that outlives the idle window can never be renewed. Until `GRM-111` the realm ran a
# 60-min access token inside Keycloak's DEFAULT 30-min idle window (this file never set it), and every
# officer was signed out at about the hour whatever they did. Measured on Keycloak 2026-09-15 with the
# timers scaled down: renewal after the access token expired, inside the idle window → 200; after the
# idle window → 400 "Token is not active".
SSO_SESSION_MAX_LIFESPAN = 28800  # 8h — the longest an officer stays signed in, working or not
SSO_SESSION_IDLE_TIMEOUT = 1800  # 30 min without a renewal ends the session (shared office computers)
ACCESS_TOKEN_LIFESPAN = 300  # 5 min — so a working officer renews every few minutes
ACTION_TOKEN_ADMIN_LIFESPAN = 604800  # 7d — execute-actions / resend-invite links

# Refresh-token rotation (`GRM-105`). A refresh token is good for ONE renewal; presenting it again is
# refused. ⚠ Measured on Keycloak 2026-09-14: a refused reuse ENDS THE WHOLE SESSION, not just that
# token — so a stolen token replayed after the officer renewed (or before) signs BOTH out, which is
# the property we want: a theft becomes visible instead of running alongside the real session.
# ⚠ The same fact makes two tabs renewing at once end the session for every tab. The officer UI
# serialises renewal across tabs (`navigator.locks` in `oidc-auth.ts`), and that build MUST be
# deployed before this policy is applied to a realm — see 16_auth_keycloak.md § Sessions.
REVOKE_REFRESH_TOKEN = True
REFRESH_TOKEN_MAX_REUSE = 0

# Security-event retention (seconds). Keycloak stores **no** login or admin events unless the realm
# asks for it, and both default to off — so nothing was recorded, and a login that happened before
# this was switched on cannot be recovered. The ops daily report already queried
# `keycloak.event_entity` for officer logins and login failures (`ops/reports.py:45,55`), which means
# it reported 0 rather than "not recorded" for as long as storage was off.
# 90 days: long enough that a disclosure arriving weeks later is still investigable (backups roll at
# 14), short enough to stay data-minimising. The retention decision in
# `docs/dpg/privacy-assessment.md` §5.1 may override it.
EVENTS_EXPIRATION = 7776000  # 90d

DEMO_OFFICERS: list[dict[str, str]] = keycloak_demo_officers()

# Token mappers: emit Cognito-compatible claim names so the rest of the code
# (frontend TokenPayload, backend get_current_user) requires zero changes.
# Also injects `ticketing-api` into the access token's `aud` claim so the
# backend's jose.jwt.decode(audience="ticketing-api", ...) accepts the token.
MAPPERS: list[dict[str, Any]] = [
    {
        "name": "audience-ticketing-api",
        "protocol": "openid-connect",
        "protocolMapper": "oidc-audience-mapper",
        "consentRequired": False,
        "config": {
            "included.client.audience": "ticketing-api",
            "id.token.claim": "false",
            "access.token.claim": "true",
            "userinfo.token.claim": "false",
        },
    },
    {
        "name": "grm_roles",
        "protocol": "openid-connect",
        "protocolMapper": "oidc-usermodel-attribute-mapper",
        "consentRequired": False,
        "config": {
            "user.attribute": "grm_roles",
            "claim.name": "custom:grm_roles",
            "jsonType.label": "String",
            "id.token.claim": "true",
            "access.token.claim": "true",
            "userinfo.token.claim": "true",
            "multivalued": "false",
        },
    },
    {
        "name": "organization_id",
        "protocol": "openid-connect",
        "protocolMapper": "oidc-usermodel-attribute-mapper",
        "consentRequired": False,
        "config": {
            "user.attribute": "organization_id",
            "claim.name": "custom:organization_id",
            "jsonType.label": "String",
            "id.token.claim": "true",
            "access.token.claim": "true",
            "userinfo.token.claim": "true",
            "multivalued": "false",
        },
    },
    {
        "name": "location_code",
        "protocol": "openid-connect",
        "protocolMapper": "oidc-usermodel-attribute-mapper",
        "consentRequired": False,
        "config": {
            "user.attribute": "location_code",
            "claim.name": "custom:location_code",
            "jsonType.label": "String",
            "id.token.claim": "true",
            "access.token.claim": "true",
            "userinfo.token.claim": "true",
            "multivalued": "false",
        },
    },
    {
        "name": "phone_number",
        "protocol": "openid-connect",
        "protocolMapper": "oidc-usermodel-attribute-mapper",
        "consentRequired": False,
        "config": {
            "user.attribute": "phone_number",
            "claim.name": "custom:phone_number",
            "jsonType.label": "String",
            "id.token.claim": "true",
            "access.token.claim": "true",
            "userinfo.token.claim": "true",
            "multivalued": "false",
        },
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _master_admin() -> KeycloakAdmin:
    settings = get_settings()
    conn = KeycloakOpenIDConnection(
        server_url=settings.keycloak_admin_url.rstrip("/") + "/",
        username="admin",
        password=settings.keycloak_admin_password,
        realm_name="master",
        user_realm_name="master",
        verify=True,
    )
    return KeycloakAdmin(connection=conn)


def _realm_admin() -> KeycloakAdmin:
    """Admin scoped to the grm realm (same credentials, different realm context)."""
    settings = get_settings()
    conn = KeycloakOpenIDConnection(
        server_url=settings.keycloak_admin_url.rstrip("/") + "/",
        username="admin",
        password=settings.keycloak_admin_password,
        realm_name=REALM,
        user_realm_name="master",
        verify=True,
    )
    return KeycloakAdmin(connection=conn)


# ── Setup steps ───────────────────────────────────────────────────────────────

def setup_realm(master: KeycloakAdmin) -> None:
    realms = master.get_realms()
    if not any(r["realm"] == REALM for r in realms):
        master.create_realm({
            "realm": REALM,
            "enabled": True,
            "displayName": "GRM Ticketing",
            "ssoSessionMaxLifespan": SSO_SESSION_MAX_LIFESPAN,
            "ssoSessionIdleTimeout": SSO_SESSION_IDLE_TIMEOUT,
            "accessTokenLifespan": ACCESS_TOKEN_LIFESPAN,
            "actionTokenGeneratedByAdminLifespan": ACTION_TOKEN_ADMIN_LIFESPAN,
            "revokeRefreshToken": REVOKE_REFRESH_TOKEN,
            "refreshTokenMaxReuse": REFRESH_TOKEN_MAX_REUSE,
            "bruteForceProtected": True,
        })
        logger.info("Created realm '%s'", REALM)
    else:
        logger.info("Realm '%s' already exists — skipping create", REALM)


def setup_realm_token_lifespans(admin: KeycloakAdmin) -> None:
    """Apply the realm's token policy: lifespans (incl. 7-day invite links) and refresh-token rotation.

    ⚠ It used to set lifespans only, so a realm created before rotation was added kept Keycloak's
    default — `revokeRefreshToken` OFF — however often this ran. Updating is what reaches an
    existing realm; the create payload alone never would. ⚠ The idle timeout was never set either, and
    that default is what signed officers out at the hour (`GRM-111`).
    """
    admin.update_realm(
        REALM,
        {
            "ssoSessionMaxLifespan": SSO_SESSION_MAX_LIFESPAN,
            "ssoSessionIdleTimeout": SSO_SESSION_IDLE_TIMEOUT,
            "accessTokenLifespan": ACCESS_TOKEN_LIFESPAN,
            "actionTokenGeneratedByAdminLifespan": ACTION_TOKEN_ADMIN_LIFESPAN,
            "revokeRefreshToken": REVOKE_REFRESH_TOKEN,
            "refreshTokenMaxReuse": REFRESH_TOKEN_MAX_REUSE,
        },
    )
    logger.info(
        "Realm '%s' token policy updated (access=%ss, sso idle=%ss, sso max=%ss, admin invite link=%ss, "
        "revoke refresh token=%s, max reuse=%s)",
        REALM,
        ACCESS_TOKEN_LIFESPAN,
        SSO_SESSION_IDLE_TIMEOUT,
        SSO_SESSION_MAX_LIFESPAN,
        ACTION_TOKEN_ADMIN_LIFESPAN,
        REVOKE_REFRESH_TOKEN,
        REFRESH_TOKEN_MAX_REUSE,
    )


def setup_realm_event_logging(admin: KeycloakAdmin) -> None:
    """Persist login and admin events — the evidence a breach investigation reads.

    `enabledEventTypes` is deliberately left unset, which stores every type: a responder cannot
    know in advance which event turns out to matter.
    """
    admin.update_realm(
        REALM,
        {
            "eventsEnabled": True,
            "eventsExpiration": EVENTS_EXPIRATION,
            "adminEventsEnabled": True,
            "adminEventsDetailsEnabled": True,
        },
    )
    logger.info(
        "Realm '%s' event storage enabled (login + admin, expiration=%ss)",
        REALM,
        EVENTS_EXPIRATION,
    )


def setup_realm_smtp(admin: KeycloakAdmin) -> None:
    """Configure grm realm email (required for officer invite execute-actions emails)."""
    from ticketing.auth.keycloak_smtp import (
        SMTP_SETUP_HINT,
        missing_smtp_env_fields,
        resolved_keycloak_smtp_config,
    )

    smtp = resolved_keycloak_smtp_config()
    if not smtp:
        missing = ", ".join(missing_smtp_env_fields()) or "SMTP_*"
        logger.warning("Keycloak realm SMTP not configured — missing: %s. %s", missing, SMTP_SETUP_HINT)
        return
    admin.update_realm(REALM, {"smtpServer": smtp})
    logger.info(
        "Realm '%s' SMTP configured (host=%s from=%s)",
        REALM,
        smtp["host"],
        smtp["from"],
    )


def setup_realm_login_theme(admin: KeycloakAdmin) -> None:
    """GRM login + email themes (`deployment/keycloak/themes/grm`).

    Login: skip the execute-actions interstitial; link back to the officer UI login.
    Email: a plain-language setup email. Keycloak's default ("Update Your Account") was filed as
    spam on staging (GRM-133).
    """
    admin.update_realm(REALM, {"loginTheme": "grm", "emailTheme": "grm"})
    logger.info("Realm '%s' login and email themes set to 'grm'", REALM)


def setup_user_profile_policy(admin: KeycloakAdmin) -> None:
    """Enable unmanaged attribute storage.

    Keycloak 24+ uses the User Profile feature, which silently DROPS any
    attribute not declared in the profile schema. Without this, our seeded
    `grm_roles` / `organization_id` user attributes vanish at create time
    and the token mappers find nothing to emit. Setting policy to ENABLED
    permits arbitrary attributes — safe for the GRM use case where we
    control all token mappers.
    """
    import json
    # NB: no leading slash — `raw_get` urljoins onto `server_url`. A leading
    # slash discards any path prefix (e.g. `/keycloak` in Pattern B), causing
    # the request to land on `http://keycloak:8080/admin/...` which 404s with
    # an empty body and breaks .json() parsing downstream.
    profile = admin.connection.raw_get(f"admin/realms/{REALM}/users/profile").json()
    if profile.get("unmanagedAttributePolicy") == "ENABLED":
        logger.info("User profile unmanagedAttributePolicy already ENABLED")
        return
    profile["unmanagedAttributePolicy"] = "ENABLED"
    resp = admin.connection.raw_put(
        f"admin/realms/{REALM}/users/profile",
        data=json.dumps(profile),
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"Failed to update user profile policy: {resp.status_code} {resp.text}")
    logger.info("User profile unmanagedAttributePolicy set to ENABLED")


def setup_officer_phone_profile(admin: KeycloakAdmin) -> None:
    """Declare officer-editable attributes on the Keycloak user profile."""
    import json

    profile = admin.connection.raw_get(f"admin/realms/{REALM}/users/profile").json()
    attrs: list[dict[str, Any]] = list(profile.get("attributes") or [])

    declarations: list[dict[str, Any]] = [
        {
            "name": "phone_number",
            "displayName": "Phone number",
            "validations": {"length": {"min": 8, "max": 20}},
            "permissions": {"view": ["admin", "user"], "edit": ["admin", "user"]},
            "multivalued": False,
        },
        {
            "name": "job_title",
            "displayName": "Job title / position",
            "validations": {"length": {"max": 120}},
            "permissions": {"view": ["admin", "user"], "edit": ["admin", "user"]},
            "multivalued": False,
        },
    ]

    changed = False
    existing_by_name = {a.get("name"): a for a in attrs}
    for decl in declarations:
        name = decl["name"]
        if name in existing_by_name:
            existing = existing_by_name[name]
            if existing.get("required"):
                existing.pop("required", None)
                changed = True
                logger.info("User profile %s attribute no longer required at login", name)
            continue
        attrs.append(decl)
        changed = True
        logger.info("User profile %s attribute added", name)

    if not changed:
        return

    profile["attributes"] = attrs
    resp = admin.connection.raw_put(
        f"admin/realms/{REALM}/users/profile",
        data=json.dumps(profile),
    )
    if resp.status_code >= 300:
        raise RuntimeError(
            f"Failed to update user profile attributes: {resp.status_code} {resp.text}"
        )


def _get_client_uuid(admin: KeycloakAdmin, client_id: str) -> str | None:
    # python-keycloak 7.1.1's get_clients() takes no args and returns all clients;
    # filter by clientId in Python rather than relying on server-side query.
    for client in admin.get_clients():
        if client.get("clientId") == client_id:
            return client["id"]
    return None


# Hosts the officer UI is served from. `ticketing-ui` allows redirects back to these (and to nothing
# else), which the invite email needs: Keycloak refuses to send it when `KEYCLOAK_INVITE_REDIRECT_URI`
# is not allowed — `400 Invalid redirect uri`, and no email.
# ⚠ Staging's UI moved to the apex `nepal-gms-chatbot.facets-ai.com` while this list still named only
# the old `grm-auth.` subdomain, so every appoint/resend there failed (measured 2026-09-15). That is
# why `_ui_origins()` also allows this host's own configured invite address: the env that picks the
# redirect is the same env that allows it, and a new hostname cannot drift out of this list again.
UI_ORIGINS = [
    "http://localhost:3001",
    "http://localhost:3002",
    # EC2: dedicated auth subdomain (Pattern B). Avoids Next.js basePath
    # surgery and keeps the demo UI at the original hostname intact.
    "https://grm-auth.nepal-gms-chatbot.facets-ai.com",
    "https://nepal-gms-chatbot.facets-ai.com",
    "https://grm-chatbot.dor.gov.np",
    "https://grm.stage.facets-ai.com",
    "https://grm.facets-ai.com",
]


def _ui_origins() -> list[str]:
    """`UI_ORIGINS` plus the origin of this deployment's `KEYCLOAK_INVITE_REDIRECT_URI`."""
    origins = list(UI_ORIGINS)
    parsed = urlsplit((get_settings().keycloak_invite_redirect_uri or "").strip())
    if parsed.scheme in ("http", "https") and parsed.netloc:
        own = f"{parsed.scheme}://{parsed.netloc}"
        if own not in origins:
            origins.append(own)
    return origins


def redirect_uri_allowed(uri: str, allowed: list[str]) -> bool:
    """Keycloak's rule for an absolute redirect: an exact match, or a prefix match on a `*` pattern."""
    return any(
        uri.startswith(pattern[:-1]) if pattern.endswith("*") else uri == pattern
        for pattern in allowed
    )


def _post_logout_redirect_uris() -> str:
    """Keycloak stores post-logout URIs as a '##'-joined string, not a list."""
    return "##".join(f"{origin}/login" for origin in _ui_origins())


def setup_clients(admin: KeycloakAdmin) -> str:
    """Create ticketing-ui and ticketing-api clients. Returns ticketing-ui internal UUID.

    Idempotent: re-runs update the existing client's redirectUris and
    post.logout.redirect.uris. This host's own invite address is always allowed; another
    hostname needs a `UI_ORIGINS` entry + a re-run (`--clients-only` on a live realm).
    """
    redirect_uris = [f"{origin}/*" for origin in _ui_origins()]
    post_logout_uris = _post_logout_redirect_uris()
    ui_payload = {
        "clientId": CLIENT_UI,
        "publicClient": True,
        "standardFlowEnabled": True,
        "directAccessGrantsEnabled": False,
        "implicitFlowEnabled": False,
        "serviceAccountsEnabled": False,
        "redirectUris": redirect_uris,
        "webOrigins": ["+"],
        "attributes": {
            "pkce.code.challenge.method": "S256",
            "access.token.lifespan": "3600",
            "post.logout.redirect.uris": post_logout_uris,
        },
    }

    ui_uuid = _get_client_uuid(admin, CLIENT_UI)
    if ui_uuid:
        admin.update_client(ui_uuid, ui_payload)
        logger.info("Client '%s' updated (redirect + post-logout URIs synced)", CLIENT_UI)
    else:
        admin.create_client(ui_payload)
        ui_uuid = _get_client_uuid(admin, CLIENT_UI)
        logger.info("Created client '%s' (uuid=%s)", CLIENT_UI, ui_uuid)

    # ticketing-api — confidential; ROPC for in-app login + service account for JWKS
    # Password login issues tokens with azp=ticketing-api; logout must allow the
    # same post_logout_redirect_uri on that client (not only ticketing-ui).
    api_payload = {
        "clientId": CLIENT_API,
        "publicClient": False,
        "standardFlowEnabled": False,
        "directAccessGrantsEnabled": True,
        "serviceAccountsEnabled": True,
        "clientAuthenticatorType": "client-secret",
        "attributes": {
            "post.logout.redirect.uris": post_logout_uris,
        },
    }
    api_uuid = _get_client_uuid(admin, CLIENT_API)
    if api_uuid:
        admin.update_client(api_uuid, api_payload)
        logger.info("Client '%s' updated (direct access grants enabled)", CLIENT_API)
    else:
        admin.create_client(api_payload)
        api_uuid = _get_client_uuid(admin, CLIENT_API)
        logger.info("Created client '%s'", CLIENT_API)

    return ui_uuid  # type: ignore[return-value]


def setup_token_mappers(admin: KeycloakAdmin, ui_uuid: str) -> None:
    existing = {m["name"] for m in admin.get_mappers_from_client(ui_uuid)}
    for mapper in MAPPERS:
        if mapper["name"] in existing:
            logger.info("Mapper '%s' already exists — skipping", mapper["name"])
        else:
            admin.add_mapper_to_client(ui_uuid, payload=mapper)
            logger.info("Created mapper '%s'", mapper["name"])


def delete_password_credentials(admin: KeycloakAdmin, user_id: str) -> int:
    """Remove every password on an account; the setup email then sets the only one. Returns the count."""
    removed = 0
    for cred in admin.get_credentials(user_id):
        if cred.get("type") == "password":
            admin.delete_credential(user_id, cred["id"])
            removed += 1
    return removed


def clear_invite_passwords(admin: KeycloakAdmin, *, apply: bool) -> dict[str, int]:
    """GRM-131 clean-up for accounts invited before the fix.

    An account still waiting on `UPDATE_PASSWORD` never had a password its officer chose; before
    2026-09-15 it carried the documented demo password, which Keycloak's browser login accepts and
    then lets the typist replace (measured). Demo officers are left alone — their password is the
    point of them, and production strips them. Reports counts only: no usernames reach the log.
    """
    demo = {o["username"] for o in DEMO_OFFICERS}
    counts = {"setup_pending": 0, "with_password": 0, "cleared": 0, "demo_skipped": 0}
    for user in admin.get_users({}):
        if "UPDATE_PASSWORD" not in (user.get("requiredActions") or []):
            continue
        if user.get("username") in demo:
            counts["demo_skipped"] += 1
            continue
        counts["setup_pending"] += 1
        if not any(c.get("type") == "password" for c in admin.get_credentials(user["id"])):
            continue
        counts["with_password"] += 1
        if apply:
            delete_password_credentials(admin, user["id"])
            counts["cleared"] += 1
    return counts


def _demo_user_payload(officer: dict[str, str], attributes: dict[str, list[str]]) -> dict[str, Any]:
    return {
        "username": officer["username"],
        "email": officer["email"],
        "firstName": officer["firstName"],
        "lastName": officer["lastName"],
        "enabled": True,
        "emailVerified": True,
        "attributes": attributes,
        "requiredActions": [],
    }


def setup_demo_users(admin: KeycloakAdmin) -> None:
    canonical = {o["username"] for o in DEMO_OFFICERS}
    for legacy_username in ("mock-officer-site-l1@grm.local",):
        if legacy_username in canonical:
            continue
        found = admin.get_users({"username": legacy_username, "exact": "true"})
        if found:
            admin.delete_user(found[0]["id"])
            logger.info("Removed legacy Keycloak user '%s'", legacy_username)

    for officer in DEMO_OFFICERS:
        attributes = {
            "grm_roles":       [officer["grm_roles"]],
            "organization_id": [officer["organization_id"]],
            "phone_number":    ["9800000001"],
            "job_title":       ["Demo Officer"],
        }
        if officer.get("location_code"):
            attributes["location_code"] = [officer["location_code"]]
        found = admin.get_users({"username": officer["username"], "exact": "true"})
        if found:
            user_id = found[0]["id"]
            admin.update_user(user_id, _demo_user_payload(officer, attributes))
            logger.info("User '%s' profile and attributes refreshed", officer["username"])
            continue
        try:
            admin.create_user({
                **_demo_user_payload(officer, attributes),
                "credentials": [{"type": "password", "value": "GrmDemo2026!", "temporary": True}],
                "requiredActions": ["UPDATE_PASSWORD"],
            })
            logger.info("Created user '%s'", officer["username"])
        except KeycloakPostError as exc:
            if exc.response_code == 409:
                logger.info("User '%s' already exists (race) — skipping", officer["username"])
            elif exc.response_code == 400 and "error-person-name-invalid-character" in str(exc):
                logger.warning(
                    "User '%s' skipped — Keycloak rejected first/last name (%s / %s): %s",
                    officer["username"],
                    officer["firstName"],
                    officer["lastName"],
                    exc,
                )
            else:
                raise


# ── Entry point ───────────────────────────────────────────────────────────────

# Every flag main() understands. ⚠ The list is not decoration — see the guard in main().
KNOWN_FLAGS = frozenset({
    "--token-policy-only",
    "--clients-only",
    "--theme-only",
    "--smtp-only",
    "--clear-invite-passwords",
    "--apply",
})


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    args = sys.argv[1:] if argv is None else argv

    # ⛔ Refuse an unrecognised flag instead of falling through to the full bootstrap.
    #
    # Measured 2026-09-16 (GRM-138), by doing it: `--smtp-only` was run against a staging host
    # whose image predated the flag. Every `if "--x" in args` missed, execution reached the
    # bottom, and the FULL run rewrote demo officers, clients, token policy and the user profile
    # on a live realm — reporting success. The blast radius of a typo, or of a target that is one
    # deploy ahead of its host, was a realm reset announced as "setup complete".
    unknown = [a for a in args if a.startswith("-") and a not in KNOWN_FLAGS]
    if unknown:
        logger.error(
            "Unknown option(s): %s. Refusing to continue — an unrecognised flag would otherwise "
            "fall through to the FULL bootstrap, which rewrites demo officers, clients and token "
            "policy. If this host is behind, deploy it first. Known flags: %s",
            ", ".join(unknown),
            ", ".join(sorted(KNOWN_FLAGS)),
        )
        sys.exit(2)

    settings = get_settings()
    if not settings.keycloak_admin_url:
        logger.error("KEYCLOAK_ADMIN_URL not configured — cannot connect")
        sys.exit(1)

    logger.info("Connecting to Keycloak at %s", settings.keycloak_admin_url)
    if "--token-policy-only" in args:
        # ⭐ For a live realm. The full run also refreshes demo officers, SMTP, clients and the
        # theme — none of which a token-policy change should touch on staging or production.
        setup_realm_token_lifespans(_realm_admin())
        logger.info("Token policy applied; nothing else was changed.")
        return
    if "--clients-only" in args:
        # For a live realm whose UI hostname changed: redirect + post-logout URIs, nothing else.
        grm = _realm_admin()
        setup_clients(grm)
        ui_uuid = _get_client_uuid(grm, CLIENT_UI)
        if ui_uuid:
            logger.info("%s redirectUris now: %s", CLIENT_UI, grm.get_client(ui_uuid).get("redirectUris"))
        logger.info("Clients applied; nothing else was changed.")
        return
    if "--theme-only" in args:
        # Login + email themes on a live realm. The theme files must already be on the host
        # (bind-mounted); a Keycloak running `start` caches themes until it restarts.
        setup_realm_login_theme(_realm_admin())
        logger.info("Themes applied; nothing else was changed.")
        return
    if "--smtp-only" in args:
        # Realm mail settings on a live realm. The full run below would also rewrite demo
        # officers, clients and token policy — none of which changing a mailbox should touch.
        # Added 2026-09-16: staging moved off a personal sender and this was the one setting
        # with no single-setting door, so the alternative was the full run (GRM-137).
        setup_realm_smtp(_realm_admin())
        logger.info("Realm SMTP applied; nothing else was changed.")
        return
    if "--clear-invite-passwords" in args:
        # GRM-131. Without --apply this only counts, so an operator sees the size first.
        apply = "--apply" in args
        counts = clear_invite_passwords(_realm_admin(), apply=apply)
        logger.info(
            "Accounts waiting on setup: %(setup_pending)s · holding a password: %(with_password)s · "
            "cleared: %(cleared)s · demo officers skipped: %(demo_skipped)s",
            counts,
        )
        if not apply and counts["with_password"]:
            logger.info("Nothing was changed. Re-run with --apply to remove those passwords.")
        return
    master = _master_admin()
    setup_realm(master)

    grm = _realm_admin()
    setup_realm_token_lifespans(grm)
    setup_realm_event_logging(grm)
    setup_realm_smtp(grm)
    setup_realm_login_theme(grm)
    setup_user_profile_policy(grm)
    setup_officer_phone_profile(grm)
    ui_uuid = setup_clients(grm)
    setup_token_mappers(grm, ui_uuid)
    api_uuid = _get_client_uuid(grm, CLIENT_API)
    if api_uuid:
        setup_token_mappers(grm, api_uuid)
    setup_demo_users(grm)
    logger.info("Keycloak realm setup complete.")


if __name__ == "__main__":
    main()
