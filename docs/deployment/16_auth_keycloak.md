# Auth — Keycloak (canonical auth ops doc)

**Status:** As-built, July 2026 — promoted and refreshed from `docs/sprints/archive/claude-tickets/AUTH_MIGRATION.md` (the Cognito→Keycloak migration notes). Keycloak is the identity provider **everywhere** (dev auth profile, AWS staging, DOR prod); Cognito is fully retired.
**Last updated:** 2026-09-15 — §1 *Sessions*: ⚠ **renewal fails by timing, so officers are signed out at about the hour** (measured: refresh token 30 min, access token 60 min — `GRM-111`); the decided target (D-012: 5-min access token, 30-min idle, 8-h max) recorded, not yet built. Earlier, 2026-09-14: §1 *Sessions*: **used refresh tokens are now revoked** (`GRM-105`) — a second use is refused and, measured on Keycloak, ends the whole session; renewal is serialised across tabs so an officer's own tabs cannot trip that; the rollout order (UI first, realm policy second) and `--token-policy-only` added. §5: the token-lifespan item updated. Earlier the same day: §1: new *Sessions* section — sign-in, renewal and sign-out all run on the server (`GRM-104`: browser renewal could never work for the confidential client, measured against a real Keycloak); the client table corrected (`ticketing-ui` is not how officers sign in); the security trade of server-side renewal and the missing refresh-token revocation (`GRM-105`) stated. §5: the false "rotation ON" claim corrected. Earlier: 2026-09-04 · ⚠ backfilled from git; not re-verified against the code

## 1. Architecture

Keycloak 26 (`quay.io/keycloak/keycloak:26.0.7`) runs as the `keycloak` compose service (profile `auth` in `docker-compose.grm.yml`), storing state in the **`keycloak` schema of `app_db`** — no extra database.

| Piece | Value |
|---|---|
| Realm | `grm` |
| Client `ticketing-ui` | public, PKCE. ⚠ **Not how officers sign in** — the browser redirect flow it serves is never started by the UI (corrected 2026-09-14, `GRM-104`). Its only live use is the front-channel sign-out fallback |
| Client `ticketing-api` | **confidential** — ⭐ **every officer session**: the email + password form signs in against it, and refresh and sign-out run against it **on the server**, where its secret lives. Also the JWKS validation target and service account; an audience mapper injects `ticketing-api` into access tokens |
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

### Sessions: sign-in, renewal, sign-out — all on the server (`GRM-104`, 2026-09-14)

**One rule: the browser never talks to Keycloak's token endpoint.** Every officer session is issued to
`ticketing-api`, a confidential client, and only the server holds its secret — so choosing the client
and supplying the credentials is the server's job at every step.

| Step | Browser calls (same-origin) | Server does |
|---|---|---|
| Sign in | `POST /api/v1/auth/login` | password grant as `ticketing-api` + secret |
| **Renew** | **`POST /api/v1/auth/refresh`** `{refresh_token}` | refresh grant as the client the token was issued to — secret only for `ticketing-api` |
| Sign out | `POST /api/v1/auth/logout` `{refresh_token}` | revokes as the issuing client; the browser falls back to Keycloak's logout page only if that is unconfirmed |

⛔ **Why renewal moved, and the cost of not knowing this.** Renewal used to run in the browser, posting
straight to Keycloak as `ticketing-ui` with no secret. For a token issued to `ticketing-api` that can
never work — **measured against a real Keycloak 2026-09-14:** `HTTP 400 invalid_grant: Invalid refresh
token. Token client and authorized client don't match`. So every officer was signed out when the
1-hour access token expired, for as long as password sign-in has existed. Sign-out had made and fixed
the identical mistake earlier; renewal was never given the same treatment. The server-side renewal was
then driven against the same Keycloak: new access token, new refresh token, and a second renewal with
the new one all succeed.

⚠ **Renewal refuses tokens for any other client** before Keycloak is asked. Sign-out forwards whatever
client a token names, because it only ends sessions; renewal *grants* tokens from an unauthenticated
endpoint, reading an unverified `azp`, so it accepts only `ticketing-api` and `ticketing-ui`.

⚠ **The security trade this makes, stated plainly.** Before, a stolen refresh token was useless on its
own — renewing it needed the server's secret. Now `/api/v1/auth/refresh` supplies that secret for
whoever presents the token, so **a leaked refresh token is a session for up to the SSO maximum (8 h)**.
That is what an 8-hour session *is*, and it is standard for this pattern. Its paired control — revoking
a refresh token once it has been used — was missing until `GRM-105`; see the next section.

⛔ **As built, officers are still signed out at about the hour — the session length below is the intent,
not the behaviour** (`GRM-111`, measured 2026-09-15 against a real Keycloak). A refresh token lives only
as long as the realm's **SSO idle timeout**, which `keycloak_setup.py` never sets, so Keycloak's default
applies: **30 minutes**. The access token lives **60 minutes**, and the UI renews it in its last minute —
by which point the refresh token expired half an hour earlier. Renewal therefore fails by timing
whatever the officer is doing: working in the app does not count as Keycloak activity, because the API
validates tokens itself.

**Decided target ([D-012](../DECISIONS.md#d-012--officer-sessions-a-5-minute-access-token-inside-a-30-minute-idle-window)),
not yet built:** access token **5 min**, idle **30 min**, maximum **8 h** — the access token must always be
shorter than the idle window. Until it ships, read *"up to 8 hours"* in this section as the target.

### Refresh-token rotation: one use per token (`GRM-105`, 2026-09-14)

The realm sets `revokeRefreshToken: true` and `refreshTokenMaxReuse: 0` (`keycloak_setup.py`,
`REVOKE_REFRESH_TOKEN` / `REFRESH_TOKEN_MAX_REUSE`). Before this, **a spent refresh token was accepted
again** — the setup script never set the flag, so every realm ran Keycloak's default, off.

⭐ **What Keycloak does with it — measured on a real Keycloak, not taken from its documentation:**

| Situation | Result |
|---|---|
| A spent refresh token is presented again | refused (`Maximum allowed refresh token reuse exceeded`) **and the whole session ends** — the newer token is refused too |
| Two renewals race with the same token | one succeeds, one is refused — **then the winner's token is refused as well**: every tab is signed out |
| A thief replays a stolen token after the officer renewed | the session ends for **both** |
| A thief renews first, then the officer renews | the officer is refused, and the thief's token dies with the session |

The last two rows are the point: **a replayed theft becomes a visible sign-out** instead of a second
session running quietly beside the real one. The server logs each refused reuse at `WARNING` —
*"a refresh token was reused … Possible replay of a stolen token, or a renewal race between tabs"* —
and never logs the token.

⚠ **The second row is why the officer UI serialises renewal across tabs.** Deduplicating inside a tab
(`refreshPromise`) is not enough once a second use ends the session. Every tab takes the Web Lock
`grm-token-renewal` before renewing; a tab that waited re-reads storage and, if another tab already
renewed, uses those tokens instead of spending the old one. A renewal that hangs gives the lock back
after 15 s. (`oidc-auth.ts` · `withRenewalLock`.)

⚠ **Residual, stated rather than hidden:** browsers without Web Locks — Safari before 15.4, Firefox
before 96, both 2022 — renew unlocked. There, two tabs renewing within one request's round trip still
end the session. A `localStorage` lease was considered and rejected: it is itself racy.

⛔ **Rollout order is not optional.** Applying the realm policy to users still running a UI **without**
the lock turns every two-tab renewal race into a sign-out of every tab. So, per realm:

1. Deploy the UI that carries the lock, and let open tabs pick it up (a reload, or the next sign-in).
2. Then apply the policy — **only** the policy, never the full setup run on a live realm, which also
   rewrites demo officers, SMTP, clients and the theme:

   ```bash
   docker compose … exec -T ticketing_api python -m ticketing.auth.keycloak_setup --token-policy-only
   ```

3. Verify: `admin/realms/grm` reports `revokeRefreshToken: true`, `refreshTokenMaxReuse: 0`.

**Not done, and logged:** tokens still live in `localStorage`, where any script on the page can read
them. Moving them to an `HttpOnly` cookie is the stronger control and a much larger change — logged
in the register as `GRM-109`.

**The issuer, where it is still needed** (the sign-out fallback): `NEXT_PUBLIC_OIDC_ISSUER` if a build
sets it; otherwise `${window.location.origin}/keycloak/realms/grm`. ⚠ CI-built images never set it
(`images.yml` passes only `NEXT_PUBLIC_AUTH_MODE`), which is why the fallback resolves from the origin.
Keycloak answers on every host nginx proxies `/keycloak/` for and keeps advertising its pinned issuer,
so backend validation is unaffected.

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
- [ ] **Token lifespans and rotation:** ⚠ **target (D-012): access 5 min, SSO idle 30 min, SSO max 8 h** — today access 1 h with Keycloak's default 30-min idle, which signs officers out at the hour (§1). Also: **a refresh token is good for one use** (`revokeRefreshToken: true`, `refreshTokenMaxReuse: 0`, `GRM-105`). Applied by `keycloak_setup --token-policy-only` — ⛔ **only after** the UI with the cross-tab renewal lock is deployed (§1 *Refresh-token rotation*). **Verify on the realm, do not assume:** until 2026-09-14 this line claimed "rotation ON" and the realm had it off.
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
