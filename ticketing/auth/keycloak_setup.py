"""
Idempotent Keycloak realm setup for GRM ticketing.

Run once after Keycloak starts:
    docker compose -f docker-compose.yml -f docker-compose.grm.yml exec ticketing_api \\
        python -m ticketing.auth.keycloak_setup

Safe to re-run — every operation checks before creating.
"""
from __future__ import annotations

import logging
import sys
from typing import Any

from keycloak import KeycloakAdmin, KeycloakOpenIDConnection
from keycloak.exceptions import KeycloakGetError, KeycloakPostError

from ticketing.config.settings import get_settings

logger = logging.getLogger(__name__)

REALM = "grm"
CLIENT_UI = "ticketing-ui"   # public, PKCE, browser
CLIENT_API = "ticketing-api"  # confidential, for JWKS endpoint + service account

DEMO_OFFICERS: list[dict[str, str]] = [
    {
        "username": "admin@grm.local",
        "email": "admin@grm.local",
        "firstName": "GRM",
        "lastName": "Admin",
        "grm_roles": "super_admin",
        "organization_id": "DOR",
    },
    {
        "username": "l1-officer@grm.local",
        "email": "l1-officer@grm.local",
        "firstName": "Site",
        "lastName": "Officer L1",
        "grm_roles": "site_safeguards_focal_person",
        "organization_id": "DOR",
    },
    {
        "username": "l2-piu@grm.local",
        "email": "l2-piu@grm.local",
        "firstName": "PIU",
        "lastName": "Officer L2",
        "grm_roles": "pd_piu_safeguards_focal",
        "organization_id": "DOR",
    },
    {
        "username": "grc-chair@grm.local",
        "email": "grc-chair@grm.local",
        "firstName": "GRC",
        "lastName": "Chair",
        "grm_roles": "grc_chair",
        "organization_id": "DOR",
    },
    {
        "username": "seah@grm.local",
        "email": "seah@grm.local",
        "firstName": "SEAH",
        "lastName": "Officer",
        "grm_roles": "seah_national_officer",
        "organization_id": "DOR",
    },
    {
        "username": "adb@grm.local",
        "email": "adb@grm.local",
        "firstName": "ADB",
        "lastName": "Safeguards",
        "grm_roles": "adb_hq_safeguards",
        "organization_id": "ADB",
    },
]

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
            "ssoSessionMaxLifespan": 28800,    # 8h
            "accessTokenLifespan": 3600,        # 1h
            "bruteForceProtected": True,
        })
        logger.info("Created realm '%s'", REALM)
    else:
        logger.info("Realm '%s' already exists — skipping create", REALM)


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
    profile = admin.connection.raw_get(f"/admin/realms/{REALM}/users/profile").json()
    if profile.get("unmanagedAttributePolicy") == "ENABLED":
        logger.info("User profile unmanagedAttributePolicy already ENABLED")
        return
    profile["unmanagedAttributePolicy"] = "ENABLED"
    resp = admin.connection.raw_put(
        f"/admin/realms/{REALM}/users/profile",
        data=json.dumps(profile),
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"Failed to update user profile policy: {resp.status_code} {resp.text}")
    logger.info("User profile unmanagedAttributePolicy set to ENABLED")


def _get_client_uuid(admin: KeycloakAdmin, client_id: str) -> str | None:
    # python-keycloak 7.1.1's get_clients() takes no args and returns all clients;
    # filter by clientId in Python rather than relying on server-side query.
    for client in admin.get_clients():
        if client.get("clientId") == client_id:
            return client["id"]
    return None


def setup_clients(admin: KeycloakAdmin) -> str:
    """Create ticketing-ui and ticketing-api clients. Returns ticketing-ui internal UUID.

    Idempotent: re-runs update the existing client's redirectUris and
    post.logout.redirect.uris so adding a new deployment hostname only needs
    a code change + re-run of this script.
    """
    redirect_uris = [
        "http://localhost:3001/*",
        "http://localhost:3002/*",
        "https://nepal-gms-chatbot.facets-ai.com/grm-auth/*",
        "https://grm.stage.facets-ai.com/*",
        "https://grm.facets-ai.com/*",
    ]
    # Keycloak stores post-logout URIs as a '##'-joined string, not a list.
    post_logout_uris = "##".join([
        "http://localhost:3001/login",
        "http://localhost:3002/login",
        "https://nepal-gms-chatbot.facets-ai.com/grm-auth/login",
        "https://grm.stage.facets-ai.com/login",
        "https://grm.facets-ai.com/login",
    ])
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

    # ticketing-api — confidential, service account for JWKS
    api_uuid = _get_client_uuid(admin, CLIENT_API)
    if api_uuid:
        logger.info("Client '%s' already exists", CLIENT_API)
    else:
        admin.create_client({
            "clientId": CLIENT_API,
            "publicClient": False,
            "standardFlowEnabled": False,
            "directAccessGrantsEnabled": False,
            "serviceAccountsEnabled": True,
            "clientAuthenticatorType": "client-secret",
        })
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


def setup_demo_users(admin: KeycloakAdmin) -> None:
    for officer in DEMO_OFFICERS:
        # Keycloak's REST API stores attributes as list[str] per key. Passing
        # bare strings silently sets attributes=None — which then leaves the
        # token mappers with nothing to emit (no custom:grm_roles claim).
        attributes = {
            "grm_roles":       [officer["grm_roles"]],
            "organization_id": [officer["organization_id"]],
        }
        # python-keycloak's get_users takes a positional dict, not query= kw.
        found = admin.get_users({"username": officer["username"], "exact": "true"})
        if found:
            # Update the attributes on every run — earlier runs of this script
            # may have created users with attributes=None. This re-attaches
            # them so the token mappers can populate the claims.
            user_id = found[0]["id"]
            admin.update_user(user_id, {"attributes": attributes})
            logger.info("User '%s' attributes refreshed", officer["username"])
            continue
        try:
            admin.create_user({
                "username": officer["username"],
                "email": officer["email"],
                "firstName": officer["firstName"],
                "lastName": officer["lastName"],
                "enabled": True,
                "emailVerified": True,
                "attributes": attributes,
                "credentials": [{"type": "password", "value": "GrmDemo2026!", "temporary": True}],
                "requiredActions": ["UPDATE_PASSWORD"],
            })
            logger.info("Created user '%s'", officer["username"])
        except KeycloakPostError as exc:
            if exc.response_code == 409:
                logger.info("User '%s' already exists (race) — skipping", officer["username"])
            else:
                raise


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    settings = get_settings()
    if not settings.keycloak_admin_url:
        logger.error("KEYCLOAK_ADMIN_URL not configured — cannot connect")
        sys.exit(1)

    logger.info("Connecting to Keycloak at %s", settings.keycloak_admin_url)
    master = _master_admin()
    setup_realm(master)

    grm = _realm_admin()
    setup_user_profile_policy(grm)
    ui_uuid = setup_clients(grm)
    setup_token_mappers(grm, ui_uuid)
    setup_demo_users(grm)
    logger.info("Keycloak realm setup complete.")


if __name__ == "__main__":
    main()
