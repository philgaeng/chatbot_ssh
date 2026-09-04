# Auth — Keycloak (canonical auth ops doc)

**Status:** As-built, July 2026 — promoted and refreshed from `docs/sprints/archive/claude-tickets/AUTH_MIGRATION.md` (the Cognito→Keycloak migration notes). Keycloak is the identity provider **everywhere** (dev auth profile, AWS staging, DOR prod); Cognito is fully retired.
**Last updated:** 2026-08-24 · ⚠ backfilled from git 2026-09-04; not re-verified against the code

## 1. Architecture

Keycloak 26 (`quay.io/keycloak/keycloak:26.0.7`) runs as the `keycloak` compose service (profile `auth` in `docker-compose.grm.yml`), storing state in the **`keycloak` schema of `app_db`** — no extra database.

| Piece | Value |
|---|---|
| Realm | `grm` |
| Client `ticketing-ui` | public, PKCE, browser login for the officer UI |
| Client `ticketing-api` | confidential; JWKS validation target + service account. An audience mapper injects `ticketing-api` into `aud` so the backend's `jwt.decode(audience="ticketing-api")` accepts tokens |
| Claim mappers | user attributes → `custom:grm_roles`, `custom:organization_id`, `custom:location_code` (Cognito-compatible names — business logic unchanged); `sub` → `CurrentUser.user_id` |
| JWT validation | `ticketing/auth/keycloak_jwt.py` — JWKS fetched via Docker DNS, cached 5 min |
| Setup script | `python -m ticketing.auth.keycloak_setup` (**idempotent**: realm, clients, mappers, token lifespans, realm SMTP, login theme, demo officers). Run via `make keycloak-setup` |
| Login theme | `deployment/keycloak/themes/grm/` (mounted read-only into the container) |
| Webhook | Keycloak HTTP event-listener → `POST /api/v1/webhooks/keycloak` on the ticketing API (`http://ticketing_api:5002/api/v1/webhooks/keycloak`), header `X-Keycloak-Webhook-Secret: $KEYCLOAK_WEBHOOK_SECRET` |

### One API + one UI, mode driven by `AUTH_MODE` (CL-03)

There is exactly **one** ticketing API and **one** officer UI; their auth behaviour is
selected by `AUTH_MODE` — not by running a second `_auth` instance. The old
`ticketing_api_auth` (:5003) / `grm_ui_auth` (:3002) demo-vs-auth split is **gone**; ports
5003 and 3002 no longer exist.

| Instance | Port (host = internal) | `AUTH_MODE=bypass` (dev only) | `AUTH_MODE=keycloak` (default) |
|---|---|---|---|
| `ticketing_api` | 5002 | Backend returns a mock super-admin — honoured **only** when `APP_ENV=dev` | Real Keycloak JWT validated against JWKS |
| `grm_ui` | 3001 | UI built with `NEXT_PUBLIC_AUTH_MODE=bypass` → "Continue to demo queue" | UI built with `NEXT_PUBLIC_AUTH_MODE=keycloak` + derived `NEXT_PUBLIC_OIDC_ISSUER` → email+password login |

`AUTH_MODE=keycloak` is the default; bypass is honoured **only** when `APP_ENV=dev`
(production can never bypass — see [`13_security.md`](13_security.md) §2.1). Keycloak is the
only profile-gated service (`profiles: [auth]`) — `make wsl-auth` / `--profile auth` bring
it up; the admin UI is at `http://localhost:18080` (`admin` / `$KEYCLOAK_ADMIN_PASSWORD`).
The frontend resolves its mode through a single module,
`channels/ticketing-ui/lib/auth/runtime-config.ts` (reads `NEXT_PUBLIC_AUTH_MODE`, which
mirrors `AUTH_MODE`).

### Hostname patterns (the `iss`-claim trap)

The browser-facing issuer URL is baked into tokens' `iss` claim and **must match** what the backend validates:

- **Pattern A (local direct port):** `KC_HOSTNAME_URL=http://localhost:18080`, `KEYCLOAK_ISSUER=http://localhost:18080/realms/grm`, JWKS fetched internally at `http://keycloak:8080/realms/grm/protocol/openid-connect/certs`.
- **Pattern B (single host behind nginx, DOR prod):** `KC_HOSTNAME_URL=https://grm-chatbot.dor.gov.np/keycloak`, `KC_HTTP_RELATIVE_PATH=/keycloak`, `KC_PROXY_HEADERS=xforwarded`, `KEYCLOAK_ISSUER=https://grm-chatbot.dor.gov.np/keycloak/realms/grm`, internal JWKS `http://keycloak:8080/keycloak/realms/grm/...`. AWS staging uses the `grm-auth.nepal-gms-chatbot.facets-ai.com` subdomain variant (see `deployment/nginx/webchat_rest_compose_aws.conf`).

## 2. Quick start (local auth stack)

Real Keycloak locally: set `AUTH_MODE=keycloak` **and** `KEYCLOAK_ISSUER` in `env.local`
first (dev defaults to `AUTH_MODE=bypass`), then rebuild via `make wsl-auth` — it brings up
Keycloak (`--profile auth`) alongside the single `ticketing_api` (:5002) / `grm_ui` (:3001).

```bash
make wsl-auth            # keycloak :18080 + ticketing_api :5002 + grm_ui :3001 (AUTH_MODE=keycloak)
make wsl-keycloak-ps     # wait until healthy (~60-90 s first boot)
make keycloak-setup      # bootstrap grm realm (idempotent; needs SMTP_* in env.local for invites)

# Verify OIDC discovery
curl -s http://localhost:18080/realms/grm/.well-known/openid-configuration | python3 -m json.tool | grep issuer

# Password-grant token smoke test
TOKEN=$(curl -s -X POST http://localhost:18080/realms/grm/protocol/openid-connect/token \
  -d "client_id=ticketing-ui&grant_type=password&username=admin@grm.local&password=GrmDemo2026!" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
curl http://localhost:5002/api/v1/tickets -H "Authorization: Bearer $TOKEN" | head -c 300
```

Dev bypass (no Keycloak): keep `APP_ENV=dev AUTH_MODE=bypass` in `env.local` (the compose
defaults) and run `make wsl-up` — the same single :3001/:5002 stack, no Keycloak container.

## 3. Officer invite flow (as-built)

1. Admin creates the officer in the ticketing UI → `POST /api/v1/users/invite` (role, org, location).
2. Ticketing creates the Keycloak user with required action **`UPDATE_PASSWORD` only** (password-only invite — no profile interstitial) and sends the execute-actions email via realm SMTP. Invite/action-token links are valid **7 days** (`ACTION_TOKEN_ADMIN_LIFESPAN`).
3. The custom `grm` login theme auto-continues past Keycloak's "Perform the following actions" page (via `actionUri`) and, after password set, redirects to the officer UI login via `KEYCLOAK_INVITE_REDIRECT_URI`.
   **Theme gotcha:** `info.ftl` must prefer `actionUri` over `pageRedirectUri` — both exist at flow start; preferring `pageRedirectUri` sends officers to login *before* they set a password.
4. On successful `UPDATE_PASSWORD`, the Keycloak event webhook (`ticketing/services/keycloak_webhook.py`) flips `ticketing.officer_onboarding.status` → `active`, so the UI's *Invited* status is accurate.
5. Resend: `POST /api/v1/users/{user_id}/resend-invite`. This also repairs Keycloak users created with `email=null` (a known bug that makes setup links fail with "Invalid email address").

Env for invites:

```env
SMTP_SERVER=... SMTP_PORT=587 SMTP_USERNAME=... SMTP_PASSWORD=... SMTP_FROM=... SMTP_FROM_DISPLAY=GRM Ticketing
KEYCLOAK_INVITE_CLIENT_ID=ticketing-ui
KEYCLOAK_INVITE_REDIRECT_URI=https://grm-chatbot.dor.gov.np/login   # dev: http://localhost:3001/login
```

Notes: `$` in SMTP passwords must be `$$` in `env.local` (Compose escaping). The realm shares the same SMTP relay as the Messaging API ([`../services/05_messaging_service.md`](../services/05_messaging_service.md)). On DOR prod the Keycloak JVM runs with `-Djava.net.preferIPv4Stack=true` (no IPv6 route to the mail provider). After theme changes: `docker compose ... --profile auth up -d --force-recreate keycloak`.

## 4. Demo officer accounts

Canonical source: **`ticketing/constants/demo_officers.py`** (`keycloak_demo_officers()`), seeded by `keycloak_setup`. All `@grm.local`, temporary password `GrmDemo2026!`, forced password change on first login. Includes `admin@grm.local` (super_admin), country/project admins, L1 site officers, L2 PIU, GRC chair/members, `seah@grm.local` / `seah-hq@grm.local`, `adb@grm.local`. Do **not** hardcode these emails elsewhere — import from the constants module. Demo accounts must not exist on DOR prod (`scripts/ops/prod_sync_remove_mock_data.sql` strips them during prod DB sync).

## 5. Production hardening checklist

- [ ] **Production mode:** `start` instead of `start-dev` for the keycloak service.
- [ ] **Hostname:** set `KC_HOSTNAME_URL` / `KC_HTTP_RELATIVE_PATH` per Pattern B; `KC_PROXY_HEADERS=xforwarded` behind nginx.
- [ ] **Admin password:** strong `KEYCLOAK_ADMIN_PASSWORD` in `env.local` (never the `admin` default).
- [ ] **Webhook secret:** strong `KEYCLOAK_WEBHOOK_SECRET`, matching the event-listener extension config.
- [ ] **Realm SMTP configured** and invite email tested (`scripts/ops/test-smtp.sh`).
- [ ] **Redirect URIs:** update in `keycloak_setup.py` for the new domain, re-run `keycloak-setup`.
- [ ] **Token lifespans:** access 1 h, SSO/refresh 8 h (setup script applies access; verify realm settings), refresh-token rotation ON.
- [ ] **Brute-force protection:** enabled by the setup script — verify in realm settings.
- [ ] ⭐ **Event storage:** applied by the setup script (`setup_realm_event_logging` — login + admin events, 90-day expiration). **Verify, do not assume**, and re-run `make keycloak-setup` on every environment:
      ```bash
      docker exec <db-container> psql -U user -d app_db -tAc \
        "SELECT events_enabled, admin_events_enabled, events_expiration FROM keycloak.realm WHERE name='grm';"
      ```
      Keycloak defaults **both to off**, and nothing recorded a single login on any environment before
      2026-08-24. It went unnoticed for months because the daily ops report queries `keycloak.event_entity`
      (`ops/reports.py:45,55`) and an empty table reads as a quiet day. **Nothing is recoverable retroactively** —
      an environment where this is off has no authentication evidence for an incident.
      See [`19_incident_response.md`](19_incident_response.md) §5.
- [ ] **JWKS/key rotation:** backend caches JWKS 5 min; rotate signing keys in the admin UI if compromised.
- [ ] **Backups:** the `keycloak` schema rides along with `app_db` dumps (`scripts/ops/backup_db.sh`) — no separate export needed, but a realm JSON export before upgrades is cheap insurance.
- [ ] **Multi-country (future):** one `grm` realm + per-user `country_code` attribute, or realm-per-country if isolation is required.

## 6. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| UI login loops or backend 401 `Invalid issuer` | `iss` mismatch — `KC_HOSTNAME_URL` + `/realms/grm` must equal `KEYCLOAK_ISSUER` exactly (scheme + path) |
| Discovery doc returns `http://` URLs behind TLS | `KC_PROXY_HEADERS=xforwarded` missing |
| Invite link → "Invalid email address" | Keycloak user has `email=null` — use resend-invite (repairs the record) |
| Invite lands on login page before password set | Theme regression: `info.ftl` preferring `pageRedirectUri` (see §3) |
| Officer stuck at "Invited" after setting password | Webhook not delivered — check event-listener config + `KEYCLOAK_WEBHOOK_SECRET`, `docker compose logs ticketing_api` |
| Keycloak unhealthy | Health endpoint is on management port 9000 (`/health/ready`), prefixed by `KC_HTTP_RELATIVE_PATH`; first boot can take 90 s |
