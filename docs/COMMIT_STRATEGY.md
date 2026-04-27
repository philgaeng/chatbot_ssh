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
   - `curl -I http://localhost/rest-webchat/`
   - Expected: `HTTP/1.1 200 OK` (not `301` to `https://...`)
4. Use this local URL for browser testing:
   - `http://localhost/rest-webchat/`

Notes:
- Keep AWS TLS compose config in `deployment/nginx/webchat_rest_compose_aws.conf` and `docker-compose.aws.yml`.
- Do not use AWS TLS override files for local WSL testing.

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

