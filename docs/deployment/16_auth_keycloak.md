# Auth — Keycloak (canonical auth ops doc)

**Status:** As-built, July 2026 — promoted and refreshed from `docs/sprints/archive/claude-tickets/AUTH_MIGRATION.md` (the Cognito→Keycloak migration notes). Keycloak is the identity provider **everywhere** (dev auth profile, AWS staging, DOR prod); Cognito is fully retired.
**Last updated:** 2026-09-16 — §3: ✅ **setup emails now reach the inbox** — verified on staging at an Infomaniak and an `adb.org` mailbox (`GRM-133`, closed). §4a: **every single-setting realm flag now has a make target** (`GRM-137`), and an unrecognised flag is now **refused** rather than falling through to the full bootstrap (`GRM-138`, measured by doing it to staging), and `--smtp-only` was added so a live realm's mailbox can change without the full run. Also §1, §3: **the realm now uses a `grm` email theme** (a plain-language setup email, `GRM-133`); **a mail scanner opening a setup link does not use it up** (measured, `GRM-134`), and the auto-continue script now JS-escapes its URL; `--theme-only` added. The sender is still the personal address until the owner copies production's mail credentials (`info@grm-chatbot-nepal.org`). Earlier, 2026-09-15 — §3: ⚠ **setup emails are delivered, but filed as spam** (measured on staging, `GRM-133`), and a Microsoft link scanner opens their link first (`GRM-134`, effect unmeasured). Earlier the same day, §3: ⛔ **invited accounts no longer get a password** (`GRM-131`, measured: the documented demo password, given to every invitee, let anyone who knew the email take the account); a refused setup email removes the new account; `--clear-invite-passwords` repairs existing realms. Also §3: **the invite redirect must be on the `ticketing-ui` client's allowed list, or Keycloak sends no email** (`GRM-130`, measured on staging); the setup script now always allows the host's own invite address, and `--clients-only` applies that to a live realm. §5 redirect-URI item updated. Earlier the same day: §1 *Sessions*: **D-012 built (`GRM-111`)** — the setup script now writes a 5-min access token and an explicit 30-min idle window, the order is pinned by a test, the idle behaviour was measured on Keycloak, and officers get a warning before the idle window ends a session; rollout step and §5 item updated. Earlier the same day: §1 *Sessions*: ⚠ **renewal fails by timing, so officers are signed out at about the hour** (measured: refresh token 30 min, access token 60 min — `GRM-111`); the decided target (D-012: 5-min access token, 30-min idle, 8-h max) recorded, not yet built. Earlier, 2026-09-14: §1 *Sessions*: **used refresh tokens are now revoked** (`GRM-105`) — a second use is refused and, measured on Keycloak, ends the whole session; renewal is serialised across tabs so an officer's own tabs cannot trip that; the rollout order (UI first, realm policy second) and `--token-policy-only` added. §5: the token-lifespan item updated. Earlier the same day: §1: new *Sessions* section — sign-in, renewal and sign-out all run on the server (`GRM-104`: browser renewal could never work for the confidential client, measured against a real Keycloak); the client table corrected (`ticketing-ui` is not how officers sign in); the security trade of server-side renewal and the missing refresh-token revocation (`GRM-105`) stated. §5: the false "rotation ON" claim corrected. Earlier: 2026-09-04 · ⚠ backfilled from git; not re-verified against the code

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
| Themes | `deployment/keycloak/themes/grm/` (mounted read-only into the container): `login/` skips the actions page; `email/` is the plain-language officer setup email. Realm: `loginTheme` and `emailTheme` = `grm`, applied alone by `keycloak_setup --theme-only`. A Keycloak running `start` caches themes until restarted |
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

### Session length: a 5-minute access token inside a 30-minute idle window (`GRM-111`, D-012)

| Setting (`keycloak_setup.py`) | Value | What it means for an officer |
|---|---|---|
| `accessTokenLifespan` | **5 min** | a working officer renews every few minutes, on their next request |
| `ssoSessionIdleTimeout` | **30 min** | a session with no renewal for 30 minutes ends |
| `ssoSessionMaxLifespan` | **8 h** | the longest anyone stays signed in, working or not |

⭐ **The order of the numbers is the policy** ([D-012](../DECISIONS.md#d-012--officer-sessions-a-5-minute-access-token-inside-a-30-minute-idle-window)).
A refresh token lives only as long as the idle window, and the UI renews on the officer's next request
once the access token is within 60 s of its end (`lib/api.ts`). So the access token **must end well
inside the idle window**, or renewal is attempted with a refresh token that has already expired.
`tests/ticketing/test_keycloak_token_policy.py` pins the order as well as the values.

⛔ **Why this section exists.** Until `GRM-111` the setup script never set the idle timeout, so
Keycloak's default 30 minutes ran beside a **60-minute** access token. The refresh token died half an
hour before the token it existed to renew, and **every officer was signed out at about the hour,
whatever they were doing**. Working in the app does not count as Keycloak activity, because the API
validates tokens itself; only a renewal does.

**Measured on Keycloak 2026-09-15**, on a throwaway realm with the timers scaled down (access 20 s,
idle 60 s):

- A renewal after the access token expired, inside the idle window, returned `200`.
- A renewal after the idle window returned `400 invalid_grant` *"Token is not active"*.
- The refresh token's own `exp` was the idle deadline.

⚠ **The idle window counts from the last renewal, not the last click.** Renewal happens at most every
5 minutes, so a session ends between about 25 and 30 minutes after the officer's last request.
**Typing does not call the server.** An officer writing a long note would be signed out
mid-sentence, and their *Send* refused.

So the UI warns first (`components/SessionIdleWarning.tsx`, rules in `lib/auth/idle-warning.ts`):

- **Two minutes before the deadline**, a banner counts down with *Stay signed in*. The deadline is the
  stored refresh token's `exp`, read once a second with no request. A renewal in another tab moves it.
- **If the deadline passes**, the banner says so and leaves the page alone, so an unsent draft can
  still be copied. *Sign in again* goes to sign-in.
- **If the 8-hour maximum is reached**, renewing cannot move the deadline, and the banner says the
  session has reached its limit.
- ⚠ **The banner never renews by itself.** Only the officer's click renews. A timer that renewed would
  keep an unattended session alive for 8 hours, which is exactly the risk the idle window closes on a
  shared office computer. No page polls the API indefinitely either: the only interval polls stop after
  30–45 attempts.
- *Driven in a browser* against a Keycloak-mode build with planted tokens: no banner 25 minutes out, a
  countdown at 90 seconds, *ended* after a refused renewal, and *Sign in again* clears the tokens. The
  e2e suite runs in bypass mode, where the banner is compiled out, so this is not in CI.

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
   make keycloak-token-policy       # local · aws-keycloak-token-policy · prod-keycloak-token-policy
   ```

3. Verify: `admin/realms/grm` reports `revokeRefreshToken: true`, `refreshTokenMaxReuse: 0`,
   `accessTokenLifespan: 300`, `ssoSessionIdleTimeout: 1800`, `ssoSessionMaxLifespan: 28800`. The same
   command applies the session lengths (`GRM-111`). They need no UI change to work, since renewal was
   already request-driven, but the idle warning ships with the UI.

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
2. Ticketing creates the Keycloak user with required action **`UPDATE_PASSWORD` only** (password-only invite — no profile interstitial) and **no password at all**, then sends the execute-actions email via realm SMTP. Invite/action-token links are valid **7 days** (`ACTION_TOKEN_ADMIN_LIFESPAN`). If Keycloak refuses the email, the account just created is deleted, so a failed invite leaves nothing behind.
   ⛔ **Never give an invitee a password, temporary or not** (`GRM-131`). Until 2026-09-15 every invitee got the documented demo password as a temporary one. Measured on Keycloak: its browser login accepts a temporary password and lets whoever typed it choose the new one, so knowing an invited officer's email was enough to take the account. With no password, that login is refused and only the email link can set one. Re-sending setup to an account that never finished it also removes any password on it.
3. The custom `grm` login theme auto-continues past Keycloak's "Perform the following actions" page (via `actionUri`) and, after password set, redirects to the officer UI login via `KEYCLOAK_INVITE_REDIRECT_URI`.
   **Theme gotcha:** `info.ftl` must prefer `actionUri` over `pageRedirectUri` — both exist at flow start; preferring `pageRedirectUri` sends officers to login *before* they set a password.
   ✅ **Delivery verified on staging, 2026-09-16** (`GRM-133`, closed). Setup emails reach the **inbox** at both an Infomaniak mailbox and an **`adb.org`** one — the second being the case that matters, since ADB are the recipients and a corporate filter is the hard test. On 2026-09-15 the same email went to **Spam**. Two things changed together: ✅ Keycloak's default template (*Update Your Account*) was replaced by the `grm` email theme, subject *Set your password for GRM Ticketing*; ✅ the sender moved off a shared personal address to **`info@grm-chatbot-nepal.org`** (Infomaniak; SPF and DMARC already set), which is now in `secrets.enc.env` and on staging.

   ⚠ **Which of the two fixed it is unmeasured** — they landed together, and separating them would need a deliberate A/B nobody needs. Do not assume either alone is sufficient.

   ⛔ **Production has had neither.** It runs `00f13230`, which predates the template, and its realm has never been given the theme or a verifying send. Until it is, tell a new officer on production to check Spam.
   ✅ **Mail link scanners do not break the link** (`GRM-134`, measured on a local realm with Mailpit). Microsoft's scanner opens setup links within seconds (seen on staging), and the auto-continue takes it to the password form. The officer can still open the same link, set a password and reach the GRM login.
4. On successful `UPDATE_PASSWORD`, the Keycloak event webhook (`ticketing/services/keycloak_webhook.py`) flips `ticketing.officer_onboarding.status` → `active`, so the UI's *Invited* status is accurate.
5. Resend: `POST /api/v1/users/{user_id}/resend-invite`. This also repairs Keycloak users created with `email=null` (a known bug that makes setup links fail with "Invalid email address").

Env for invites:

```env
SMTP_SERVER=... SMTP_PORT=587 SMTP_USERNAME=... SMTP_PASSWORD=... SMTP_FROM=... SMTP_FROM_DISPLAY=GRM Ticketing
KEYCLOAK_INVITE_CLIENT_ID=ticketing-ui
KEYCLOAK_INVITE_REDIRECT_URI=https://grm-chatbot.dor.gov.np/login   # dev: http://localhost:3001/login
```

⚠ **Keycloak sends no email when the redirect is not allowed.** `KEYCLOAK_INVITE_REDIRECT_URI` must match
the `ticketing-ui` client's `redirectUris`, or every appointment and resend fails with
`400 Invalid redirect uri` (`GRM-130`: on staging the UI had moved to `nepal-gms-chatbot.facets-ai.com`
and the client still named only the old `grm-auth.` subdomain). `keycloak_setup` writes `UI_ORIGINS`
**plus the origin of this host's own `KEYCLOAK_INVITE_REDIRECT_URI`**, so a run on the host always
allows its own address. On a live realm, apply only that:

```bash
docker compose … exec -T ticketing_api python -m ticketing.auth.keycloak_setup --clients-only
```

The invite preflight (`GET /api/v1/users/invite/preflight`) reports a refused redirect before a send.

**Realms with accounts invited before `GRM-131`** still carry the demo password on every account that
has not finished setup. Remove those passwords per realm, after the deploy. The command logs counts
only, never usernames, and changes nothing without `--apply`. Demo officers are skipped.

```bash
docker compose … exec -T ticketing_api python -m ticketing.auth.keycloak_setup --clear-invite-passwords          # count
docker compose … exec -T ticketing_api python -m ticketing.auth.keycloak_setup --clear-invite-passwords --apply  # remove
```

An officer who was told the demo password as a workaround then needs **Send setup email**.

Notes: `$` in SMTP passwords must be `$$` in `env.local` (Compose escaping). The realm shares the same SMTP relay as the Messaging API ([`../services/05_messaging_service.md`](../services/05_messaging_service.md)). On DOR prod the Keycloak JVM runs with `-Djava.net.preferIPv4Stack=true` (no IPv6 route to the mail provider). After theme changes: `docker compose ... --profile auth up -d --force-recreate keycloak`.

## 4. Demo officer accounts

Canonical source: **`ticketing/constants/demo_officers.py`** (`keycloak_demo_officers()`), seeded by `keycloak_setup`. All `@grm.local`, temporary password `GrmDemo2026!`, forced password change on first login. Includes `admin@grm.local` (super_admin), country/project admins, L1 site officers, L2 PIU, GRC chair/members, `seah@grm.local` / `seah-hq@grm.local`, `adb@grm.local`. Do **not** hardcode these emails elsewhere — import from the constants module. Demo accounts must not exist on DOR prod (`scripts/ops/prod_sync_remove_mock_data.sql` strips them during prod DB sync).

## 4a. Changing one realm setting on a live host

⛔ **Never run the bootstrap against staging or production.** `keycloak-setup` is idempotent, but
"idempotent" means it rewrites everything back to what the code says — including **demo officers**,
every client and the token policy. On a live realm that is not a no-op, it is a reset.

Each setting therefore has its own target, on each host. Prefix with `aws-` for staging or `prod-`
for DOR production; unprefixed is the local WSL stack.

| Target | Applies | Use when |
| --- | --- | --- |
| `keycloak-smtp` | realm mail settings | the sending mailbox changed |
| `keycloak-themes` | login + email themes | the setup-email template changed |
| `keycloak-clients` | redirect + post-logout URIs | the UI hostname changed |
| `keycloak-token-policy` | token lifespans | after the UI carrying the renewal lock is deployed (§3) |
| `keycloak-clear-invite-passwords` | removes passwords from accounts still awaiting setup | `GRM-131`; **counts only** unless `APPLY=1` |

```bash
make aws-keycloak-smtp                              # staging: point the realm at the new mailbox
make prod-keycloak-themes                           # production: pick up a new email template
make aws-keycloak-clear-invite-passwords            # count first — changes nothing
make aws-keycloak-clear-invite-passwords APPLY=1    # then apply
```

⚠ **`keycloak-themes` is not enough on its own.** Keycloak caches themes until it restarts, and the
theme files reach the host with the deploy, not with this target. After changing a template,
recreate the container as well — and note `keycloak` is **not** in `AWS_DEPLOY_SERVICES`, so a
normal deploy leaves it running:

```bash
docker compose --env-file env.local -f docker-compose.yml -f docker-compose.aws.yml \
  -f docker-compose.grm.yml --profile auth up -d --force-recreate --no-deps keycloak
```

⛔ **Deploy the host before you run one of these.** The flag has to exist in the image the host is
running. Until `GRM-138`, an unrecognised flag matched no dispatch in `main()` and fell through to
the **full bootstrap** — so running `make aws-keycloak-smtp` against a host one deploy behind reset
the realm and logged `Keycloak realm setup complete`. That is measured, not hypothetical: it
happened to staging on 2026-09-16, which is why the guard exists. The guard only helps once the
host runs an image that *has* the guard, so for any host still behind, order still matters:
**deploy, then apply.**

> **Why these exist (`GRM-137`, 2026-09-16).** The script had grown `--token-policy-only`,
> `--clients-only` and `--theme-only` precisely so a live realm could be changed one setting at a
> time — and none of them had a make target, so each was reachable only by hand-writing a
> `docker exec` against a container named by hand. `--smtp-only` did not exist at all, so the
> documented way to change staging's sender was the full run. **A safety valve nobody can reach
> is not a safety valve**; the flags existed and the ergonomics pointed at the dangerous path.

## 5. Production hardening checklist

- [ ] **Production mode:** `start` instead of `start-dev` for the keycloak service.
- [ ] **Hostname:** set `KC_HOSTNAME_URL` / `KC_HTTP_RELATIVE_PATH` per Pattern B; `KC_PROXY_HEADERS=xforwarded` behind nginx.
- [ ] **Admin password:** strong `KEYCLOAK_ADMIN_PASSWORD` in `env.local` (never the `admin` default).
- [ ] **Webhook secret:** strong `KEYCLOAK_WEBHOOK_SECRET`, matching the event-listener extension config.
- [ ] **Realm SMTP configured** and invite email tested (`scripts/ops/test-smtp.sh`).
- [ ] **Redirect URIs:** the host's own `KEYCLOAK_INVITE_REDIRECT_URI` origin is allowed automatically. Add any other hostname the UI is served on to `UI_ORIGINS` in `keycloak_setup.py`. Then run `keycloak_setup --clients-only` and read `ticketing-ui`'s `redirectUris` back (§3).
- [ ] **Token lifespans and rotation:** **access 5 min, SSO idle 30 min, SSO max 8 h** (D-012, `GRM-111`), written by the setup script. ⚠ A realm that has not had `--token-policy-only` since `GRM-111` still runs a 1-h access token with Keycloak's default 30-min idle, which signs officers out at the hour (§1 *Session length*). Also: **a refresh token is good for one use** (`revokeRefreshToken: true`, `refreshTokenMaxReuse: 0`, `GRM-105`). Applied by `keycloak_setup --token-policy-only` — ⛔ **only after** the UI with the cross-tab renewal lock is deployed (§1 *Refresh-token rotation*). **Verify on the realm, do not assume:** until 2026-09-14 this line claimed "rotation ON" and the realm had it off.
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
