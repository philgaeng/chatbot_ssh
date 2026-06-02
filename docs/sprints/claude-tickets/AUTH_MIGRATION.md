# Auth Migration: AWS Cognito → Keycloak

## Why Keycloak

Keycloak 26 is a self-hosted OIDC/OAuth2 provider that replaces AWS Cognito.
It runs as a single Docker container alongside the existing stack and stores its
state in the same Postgres instance (`keycloak` schema inside `app_db`).
No AWS account needed for deployment — works on any server.

---

## Quick Start (local development)

```bash
# 1. Start the full stack including Keycloak
docker compose -f docker-compose.yml -f docker-compose.grm.yml up -d

# 2. Wait for Keycloak to be healthy (~60 s on first boot)
docker compose -f docker-compose.yml -f docker-compose.grm.yml ps keycloak

# 3. Set up the grm realm, clients, mappers, and demo users (idempotent)
docker compose -f docker-compose.yml -f docker-compose.grm.yml exec ticketing_api \
  python -m ticketing.auth.keycloak_setup

# 4. Verify OIDC discovery
curl -s http://localhost:8080/realms/grm/.well-known/openid-configuration | python3 -m json.tool | grep issuer

# 5. Get a token and hit the API
TOKEN=$(curl -s -X POST http://localhost:8080/realms/grm/protocol/openid-connect/token \
  -d "client_id=ticketing-ui&grant_type=password&username=admin@grm.local&password=GrmDemo2026!" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
curl http://localhost:5002/api/v1/tickets -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -10
```

Keycloak Admin UI: http://localhost:8080 — `admin` / `admin` (or `$KEYCLOAK_ADMIN_PASSWORD`).

---

## Dev Bypass (no Keycloak required)

Leave `KEYCLOAK_ISSUER` empty (the default) — the backend returns `mock-super-admin`.
Set `NEXT_PUBLIC_BYPASS_AUTH=true` — the frontend skips OIDC entirely.

Both are the defaults in `docker-compose.grm.yml`, so existing dev workflows are unaffected.

---

## Demo Officer Accounts

Created by `keycloak_setup.py`. All have temporary password `GrmDemo2026!` and
are required to change it on first login.

| Email | Role | Org |
|---|---|---|
| admin@grm.local | super_admin | DOR |
| l1-officer@grm.local | site_safeguards_focal_person | DOR |
| l2-piu@grm.local | pd_piu_safeguards_focal | DOR |
| grc-chair@grm.local | grc_chair | DOR |
| seah@grm.local | seah_national_officer | DOR |
| adb@grm.local | adb_hq_safeguards | ADB |

---

## Migrating Existing Cognito Users

If you have officers already in the Cognito pool:

```bash
# 1. Export from Cognito (requires AWS CLI configured)
aws cognito-idp list-users \
  --user-pool-id <COGNITO_GRM_USER_POOL_ID> \
  --query 'Users[*].{username:Username,email:Attributes[?Name==`email`]|[0].Value,grm_roles:Attributes[?Name==`custom:grm_roles`]|[0].Value,org:Attributes[?Name==`custom:organization_id`]|[0].Value}' \
  --output json > cognito_users.json

# 2. For each user, call the invite endpoint (or add them to DEMO_OFFICERS in keycloak_setup.py)
curl -X POST http://localhost:5002/api/v1/users/invite \
  -H 'Content-Type: application/json' \
  -H 'x-internal-user-id: mock-super-admin' \
  -H 'x-internal-role: super_admin' \
  -d '{"email":"officer@example.com","role_key":"grc_member","organization_id":"DOR"}'
```

---

## Production Hardening Checklist

Before going to staging / production:

- [ ] **Switch Keycloak to production mode**: change `command: start-dev` → `start` in docker-compose.grm.yml
- [ ] **Set hostname**: add `KC_HOSTNAME=grm.facets-ai.com` (or behind reverse proxy with `KC_PROXY=edge`)
- [ ] **Change admin password**: set `KEYCLOAK_ADMIN_PASSWORD` to something strong in the environment
- [ ] **Configure SMTP** for email verification and password reset:
  ```
  KC_SMTP_HOST=email-smtp.ap-southeast-1.amazonaws.com
  KC_SMTP_PORT=587
  KC_SMTP_FROM=noreply@grm.facets-ai.com
  KC_SMTP_USER=<SES SMTP user>
  KC_SMTP_PASSWORD=<SES SMTP password>
  KC_SMTP_STARTTLS=true
  ```
- [ ] **Update redirect URIs** in `keycloak_setup.py` when deploying to a new domain, then re-run the setup script.
- [ ] **Set token lifespans** in the `grm` realm:
  - Access token: 1 hour (already set by setup script)
  - Refresh token: 8 hours (Keycloak Admin UI → Realm Settings → Tokens)
  - SSO session: 8 hours
- [ ] **Enable brute-force protection**: already enabled by setup script
- [ ] **Enable refresh token rotation**: Keycloak Admin UI → Realm Settings → Tokens → Revoke refresh token = ON
- [ ] **Verify JWKS caching**: backend caches JWKS for 5 min (`ticketing/auth/keycloak_jwt.py`). Rotate signing keys in Keycloak Admin UI if needed.
- [ ] **Multi-country**: consider one `grm` realm with per-user `country_code` attribute, or separate realms per country if data isolation is required.

---

## JWT Claim Mapping

Keycloak emits the same custom claim names as Cognito — no changes to business logic:

| Attribute | JWT claim | Where used |
|---|---|---|
| `grm_roles` user attribute | `custom:grm_roles` | `dependencies.py` → `CurrentUser.role_keys` |
| `organization_id` user attribute | `custom:organization_id` | `dependencies.py` → `CurrentUser.organization_id` |
| `location_code` user attribute | `custom:location_code` | `dependencies.py` → `CurrentUser.location_code` |
| Keycloak `sub` | `sub` | `CurrentUser.user_id` |

Mappers are configured on the `ticketing-ui` client by `keycloak_setup.py`.
