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

If this project has script wrappers (for example `make test`, `just test`, or npm scripts), prefer those wrappers inside Docker.

### Local Frontend Testing (Nginx HTTP Override)

When testing the webchat locally, use the dev-only nginx override so `http://localhost` works without browser TLS/certificate issues.

1. Ensure local override files exist:
   - `docker-compose.override.yml`
   - `deployment/nginx/webchat_rest_local.conf`
2. Start/restart nginx with compose (override is auto-applied locally):
   - `docker compose up -d nginx`
3. Verify the webchat endpoint is served on HTTP and not redirected:
   - `curl -I http://localhost/rest-webchat/`
   - Expected: `HTTP/1.1 200 OK` (not `301` to `https://...`)
4. Use this local URL for browser testing:
   - `http://localhost/rest-webchat/`

Notes:
- Keep production TLS config in `deployment/nginx/webchat_rest_docker.conf` unchanged.
- Do not rely on local override files in production deploy workflows.

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

