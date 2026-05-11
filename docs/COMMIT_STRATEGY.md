# Commit Strategy: Dev Branch + Docker Validation

This document defines the standard development and commit workflow for this repository.

Primary goals:
- Keep `main` stable and releasable.
- Validate behavior in Docker before merging.
- Keep commits small, focused, and reviewable.

## Branching Rules

- `main` is protected and should not receive direct feature work.
- Create a short-lived branch for every change:
  - `feat/<short-description>`
  - `fix/<short-description>`
  - `chore/<short-description>`
  - `docs/<short-description>`
- Rebase or merge latest `main` into your branch regularly for long-running work.

## Standard Day-to-Day Flow

1. Sync local `main`:
   - `git checkout main`
   - `git pull origin main`
2. Create a working branch:
   - `git checkout -b feat/<short-description>`
3. Implement changes locally.
4. Build and run with Docker.
5. Run tests/checks in container.
6. Commit in small logical units.
7. Push branch and open PR to `main`.
8. Merge only after review + CI is green.

## Startup Bootstrap Workflow (Dev/Integration)

When starting from a fresh or reset DB volume, use one deterministic order so chatbot + ticketing stay aligned.

1. Ensure the target branch is checked out and up to date:
   - `git checkout main`
   - `git pull --ff-only origin main`
2. Rebuild backend image before migrations (ensures newest Alembic files are in container):
   - `docker compose build backend`
3. Apply migrations:
   - `python -m alembic -c migrations/public/alembic.ini upgrade head`
   - `python -m alembic -c ticketing/migrations/alembic.ini upgrade head`
4. Seed ticketing locations from JSON (repo-standard source):
   - `python -m ticketing.seed.import_locations_json --country NP --en backend/dev-resources/location_dataset/en_cleaned.json --ne backend/dev-resources/location_dataset/ne_cleaned.json --max-level 3`
5. Seed workflows/mock data:
   - `python -m ticketing.seed.mock_tickets --reset`
6. Start/restart stack:
   - `docker compose -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml up -d --build`

Notes:
- If `public` core tables are missing, run `docker compose --profile init run --rm db_init` once, then re-run step 3.
- Prefer JSON location import in this repository; CSV import requires an explicit `--csv` path and may not exist in every deployment.
- If running init/migration commands inside containers, do not use `localhost` as DB host in container env. Use the compose DB service host (typically `db`) so `db_init` and Alembic can connect.

### Runtime context rule (host vs container)

Use one context consistently for each bootstrap run:

1. **Host/Python context** (commands run from your shell with local Python):
   - DB host may be `localhost` when port-forwarded/exposed locally.
2. **Container context** (`docker compose run/exec ...`):
   - DB host must be compose service name (usually `db`), never `localhost`.

Mixing contexts without switching DB host is a common cause of bootstrap failures.

### Known migration recovery (public baseline mismatch)

If public Alembic fails with errors similar to:

- `column "status_name" of relation "task_statuses" does not exist`

do this sequence:

1. Confirm DB host matches runtime context (rule above).
2. Run one-time bootstrap init:
   - `docker compose --profile init run --rm db_init`
3. Re-run migrations in order:
   - `python -m alembic -c migrations/public/alembic.ini upgrade head`
   - `python -m alembic -c ticketing/migrations/alembic.ini upgrade head`
4. Continue with location seed + mock seed + compose up.

## Docker-First Validation

Developers should validate in containerized environment before committing when possible.

Typical commands (adapt to service names in `docker-compose.yml`):
- Build and run services:
  - `docker compose up --build -d`
- Run tests inside app container:
  - `docker compose exec app pytest`
  - or `docker compose exec app npm test`
- One-off test run:
  - `docker compose run --rm app pytest`
- View logs when debugging:
  - `docker compose logs -f app`
- Stop services after validation:
  - `docker compose down`

Container DB connectivity check (before migration commands):

- `docker compose exec db pg_isready -U <db_user> -d <db_name>`

If this fails, fix DB/container networking first before running Alembic.

If this project has script wrappers (for example `make test`, `just test`, or npm scripts), prefer those wrappers inside Docker.

### Local Frontend Testing (Nginx HTTP Override)

When testing the webchat locally, use the dev-only nginx override so `http://localhost` works without browser TLS/certificate issues.

1. Ensure local compose uses:
   - `docker-compose.yml`
   - `deployment/nginx/webchat_rest_compose_wsl.conf`
2. Start/restart nginx with compose:
   - `docker compose up -d nginx`
3. Verify the webchat endpoint is served on HTTP and not redirected:
   - `curl -I http://127.0.0.1:8080/rest-webchat/`
   - Expected: `HTTP/1.1 200 OK` (not `301` to `https://...`)
4. Use this local URL for browser testing:
   - `http://127.0.0.1:8080/rest-webchat/`

> Host port for the local nginx is **`8080`** (`docker-compose.yml` publishes `8080:80` because host `:80` is often taken).

Notes:
- Keep AWS TLS compose config in `deployment/nginx/webchat_rest_compose_aws.conf` and `docker-compose.aws.yml`.
- Do not use AWS TLS override files for local WSL testing.

## QR Token Scan Flow (local + production)

The webchat reads `?t=<token>` from its URL on session start, calls the
ticketing API to resolve the token, pre-fills package / project / district /
province slots, and forwards `package_id` when the grievance is submitted.
A QR sticker on a contractor package decodes to one such URL.

### End-to-end pieces

| Piece | Where |
|---|---|
| Webchat reads `t` from `URLSearchParams` | `channels/REST_webchat/app.js` (`getUrlParams`) and `channels/webchat/app.js` |
| Token forwarded inside `/introduce` payload | same files (`introducePayload.t`) |
| Action server resolves token + sets slots | `backend/actions/generic_actions.py` (`ActionIntroduce`) |
| Scan API call | `backend/actions/utils/ticketing_dispatch.py` → `fetch_qr_scan()` |
| `location_code` → district + province name lookup | `backend/shared_functions/location_mapping.py` (`resolve_location_code_to_names`) |
| Welcome variant when `package_label` is set | `action_main_menu` utterance index `3` |
| `package_id` forwarded to ticketing on submit | `backend/actions/action_submit_grievance.py` (both standard + SEAH) calling `dispatch_ticket(package_id=…)` |
| Public scan endpoint | `ticketing/api/routers/scan.py` → `GET /api/v1/scan/{token}` |
| QR base URL config | `ticketing/config/settings.py` → `chatbot_webchat_url` (env: `CHATBOT_WEBCHAT_URL`) |
| Migration | `ticketing/migrations/versions/l2m4o6q8s0_qr_tokens_and_ticket_package.py` |

The slots set when a token resolves: `qr_token`, `package_id`, `package_label`,
`project_code`, `location_code`, `complainant_district`, `complainant_province`.

### `CHATBOT_WEBCHAT_URL` — base URL for printable QR codes

The Settings UI's "Generate QR" action returns a `scan_url` of the form
`{CHATBOT_WEBCHAT_URL}?t={token}`. Set this env var to the public hostname +
path that serves the webchat in your environment. The token row itself is
host-agnostic — only the printed QR URL changes.

| Environment | `CHATBOT_WEBCHAT_URL` |
|---|---|
| Local WSL (chatbot stack) | `http://127.0.0.1:8080/rest-webchat/` |
| AWS today (no `grm.facets-ai.com` DNS yet) | `https://nepal-gms-chatbot.facets-ai.com/rest-webchat/` |
| Code default (planned hostname) | `https://grm.facets-ai.com/chat` |

Override path:
1. Edit `env.local` (one line: `CHATBOT_WEBCHAT_URL=…`).
2. Restart only `ticketing_api`:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.grm.yml \
     up -d --force-recreate --no-deps ticketing_api
   ```
3. Verify pydantic loaded the override:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.grm.yml \
     exec -T ticketing_api python -c \
     "from ticketing.config.settings import get_settings; print(get_settings().chatbot_webchat_url)"
   ```

The chatbot side does **not** need this env var — it reads `?t=` from whatever
URL it was opened with and calls `TICKETING_API_URL` (default
`http://ticketing_api:5002`) for the scan.

### Required data: every QR-eligible package needs a location row

`GET /api/v1/scan/{token}` returns `422 {"detail":"package_has_no_location"}`
if the linked package has no rows in `ticketing.package_locations`. The
chatbot's `fetch_qr_scan()` treats anything that isn't a `200` (404, 410, 422,
network error) as "no usable token" and falls through to the standard
district/province questions — submission still succeeds but the QR pre-fill
is silently lost. Watch the action server logs for
`⚠️ QR scan returned unexpected status` to spot 422s.

When creating a package via the Settings UI, **add at least one location**
(e.g. Jhapa / `NP_D004`) before generating QR tokens. To check an existing
package:

```bash
docker compose -f docker-compose.yml -f docker-compose.grm.yml \
  exec -T db psql -U user -d app_db -c "
    SELECT p.package_code, p.name, COUNT(pl.location_code) AS n_locations
    FROM ticketing.project_packages p
    LEFT JOIN ticketing.package_locations pl ON pl.package_id = p.package_id
    GROUP BY p.package_code, p.name
    ORDER BY n_locations;"
```

Any row with `n_locations = 0` is a future scan-422.

### Local end-to-end test recipe

```bash
# 1. Bring up the full stack (chatbot + ticketing)
make compose_docker_wsl_full

# 2. Apply migrations + seed
make migrate_ticketing
docker compose -f docker-compose.yml -f docker-compose.grm.yml \
  exec -T ticketing_api python -m ticketing.seed.mock_tickets --reset

# 3. In the Settings UI (http://127.0.0.1:3001/settings):
#    - open Packages → pick or create a package
#    - confirm at least one location is attached
#    - click "Generate QR" → copy the token (e.g. a3f9b2c1)

# 4. Sanity-check the scan endpoint
curl -s http://127.0.0.1:5002/api/v1/scan/<token> | jq

# 5. Open the webchat with the token
#    http://127.0.0.1:8080/rest-webchat/?t=<token>
#    → welcome message should read:
#      "You are reaching out from <Lot label>, <District> District."
#    → district/province questions are skipped
#    → submitted ticket carries package_id (verify in /api/v1/tickets)
```

Bad / expired / missing tokens are non-fatal: the welcome falls back to the
plain "What would you like to do?" prompt and the user is asked the
geography questions as today.

## Commit Guidelines

- Commit only related changes together.
- Keep commits small enough to review quickly.
- Use clear, intention-revealing messages.
- Avoid mixing refactors with behavior changes unless required.
- Do not include secrets (`.env`, credentials, tokens).

Recommended commit style:
- `feat: add fallback handler for missing intent`
- `fix: prevent duplicate ticket creation on retry`
- `chore: update docker compose healthcheck`
- `docs: add commit strategy and docker workflow`

## Pull Request Expectations

Every PR to `main` should include:
- Short summary of the change.
- Why the change is needed.
- How it was tested (commands + result).
- Risks and rollback notes when relevant.

PRs should be:
- Focused in scope.
- Backed by passing tests/checks.
- Updated with latest `main` before merge if required by CI.

## Agent Execution Checklist

Agents working in this repository should follow this sequence:

1. Confirm current branch with `git status`.
2. If on `main`, create a new branch before editing.
3. Make targeted code changes.
4. Run project checks/tests (prefer Docker path).
5. Ensure only intended files are staged.
6. Write a clear commit message reflecting intent.
7. Open/prepare PR against `main` (do not force-push to `main`).

## Safety Rules

- Never force-push to `main`.
- Never bypass required checks without explicit approval.
- Never rewrite shared branch history unless explicitly coordinated.
- If unrelated dirty changes exist, avoid modifying or reverting them.

## Quick Command Reference

```bash
git checkout main
git pull origin main
git checkout -b feat/example-change

# develop...
docker compose up --build -d
docker compose exec app pytest

git add <files>
git commit -m "feat: concise intent-focused message"
git push -u origin feat/example-change
```

