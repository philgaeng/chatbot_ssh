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
MAPPERS: list[dict[str, Any]] = [
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
    if any(r["realm"] == REALM for r in realms):
        logger.info("Realm '%s' already exists — skipping", REALM)
        return
    master.create_realm({
        "realm": REALM,
        "enabled": True,
        "displayName": "GRM Ticketing",
        "ssoSessionMaxLifespan": 28800,    # 8h
        "accessTokenLifespan": 3600,        # 1h
        "bruteForceProtected": True,
    })
    logger.info("Created realm '%s'", REALM)


def _get_client_uuid(admin: KeycloakAdmin, client_id: str) -> str | None:
    clients = admin.get_clients(query={"clientId": client_id, "exact": "true"})
    return clients[0]["id"] if clients else None


def setup_clients(admin: KeycloakAdmin) -> str:
    """Create ticketing-ui and ticketing-api clients. Returns ticketing-ui internal UUID."""
    # ticketing-ui — public, PKCE
    ui_uuid = _get_client_uuid(admin, CLIENT_UI)
    if ui_uuid:
        logger.info("Client '%s' already exists", CLIENT_UI)
    else:
        admin.create_client({
            "clientId": CLIENT_UI,
            "publicClient": True,
            "standardFlowEnabled": True,
            "directAccessGrantsEnabled": False,
            "implicitFlowEnabled": False,
            "serviceAccountsEnabled": False,
            "redirectUris": [
                "http://localhost:3001/*",
                "https://grm.stage.facets-ai.com/*",
                "https://grm.facets-ai.com/*",
            ],
            "webOrigins": ["+"],
            "attributes": {
                "pkce.code.challenge.method": "S256",
                "access.token.lifespan": "3600",
                "post.logout.redirect.uris": (
                    "http://localhost:3001/login"
                    "##https://grm.stage.facets-ai.com/login"
                    "##https://grm.facets-ai.com/login"
                ),
            },
        })
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
        found = admin.get_users(query={"username": officer["username"], "exact": "true"})
        if found:
            logger.info("User '%s' already exists — skipping", officer["username"])
            continue
        try:
            admin.create_user({
                "username": officer["username"],
                "email": officer["email"],
                "firstName": officer["firstName"],
                "lastName": officer["lastName"],
                "enabled": True,
                "emailVerified": True,
                "attributes": {
                    "grm_roles": officer["grm_roles"],
                    "organization_id": officer["organization_id"],
                },
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
    ui_uuid = setup_clients(grm)
    setup_token_mappers(grm, ui_uuid)
    setup_demo_users(grm)
    logger.info("Keycloak realm setup complete.")


if __name__ == "__main__":
    main()
