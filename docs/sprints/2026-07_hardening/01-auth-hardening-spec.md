# HR-01 / HR-02 — Auth Hardening (fail-closed + ticket access gates)

> Workstream A · Branch `hardening/hr-01-02-auth` · Sequential: HR-01 then HR-02.
> Evidence source: [`docs/reviews/devils_advocate_codebase.md`](../../reviews/devils_advocate_codebase.md) §2.1–2.2. Line numbers are as of `integration/seah-claude`, July 2026 — re-locate before editing.

---

## 1. HR-01 — Fail-closed auth

### Problem (verified)

A single missing env var silently disables authentication:

| Site | Behavior today |
|---|---|
| `ticketing/api/dependencies.py:175-183` | `keycloak_issuer` unset ⇒ **every request** authenticates as a `super_admin` demo officer |
| `ticketing/api/dependencies.py:66-69` | `TICKETING_SECRET_KEY` unset ⇒ webhook/API-key check disabled with only a log warning |
| `ticketing/api/dependencies.py:206-213` | `x-internal-user-id` + static `x-api-key` ⇒ arbitrary user, **default role `super_admin`** |
| `backend/api/routers/grievance.py:86` | empty configured key list ⇒ API-key check skipped entirely |

### Change

1. Introduce one explicit switch: `TICKETING_ENV` (values `dev` | `staging` | `production`; default **`production`**) in `ticketing/config/settings.py`. Reuse the existing pydantic-settings pattern; also read it in `backend` config for the grievance-API fix (mirror var `BACKEND_ENV`, or share one `APP_ENV` — pick one, document in the code).
2. **Startup guard** (fail at boot, not per-request): in `ticketing/api/main.py` app startup, if env is not `dev` and any of `keycloak_issuer`, `ticketing_secret_key` is unset → raise `RuntimeError` with a message naming the missing var. Same guard for the grievance API's key list in `backend/api/fastapi_app.py`.
3. Per-request hard-fail as defense in depth: the demo-officer fallback and the skip-check branches become `if settings.ticketing_env == "dev": ... else: raise HTTPException(503, "auth not configured")`.
4. Header-identity path (`x-internal-user-id`): default role becomes **least privilege** (no roles) instead of `super_admin`; callers that need more must send an explicit, validated role claim. Grep for internal callers first (`grievance_sync`, dispatch) and preserve their actual needs.
5. Compose/dev ergonomics: set `TICKETING_ENV=dev` in `docker-compose.override.yml` and document in `docs/deployment/DOCKER.md` + `env.local` template. **Do not** set it in `docker-compose.grm.yml`, `aws`, or `prod` files.
6. Update `docs/deployment/13_security.md`: add a "Fail-closed guarantees" section listing exactly what refuses to start/serve when unconfigured.

### Tests (acceptance)

New file `tests/ticketing/test_fail_closed_auth.py`:
- [ ] `TICKETING_ENV=production` + no `keycloak_issuer` ⇒ app startup raises (use `TestClient` context / lifespan).
- [ ] `TICKETING_ENV=production` + issuer set + no `TICKETING_SECRET_KEY` ⇒ startup raises.
- [ ] `TICKETING_ENV=dev` + nothing set ⇒ startup OK, demo fallback works (existing behavior preserved for local dev).
- [ ] Per-request: with env forced to `production` and deps monkeypatched past startup, unauthenticated request ⇒ 401/503, **never** a demo super_admin.
- [ ] Header-identity without explicit role ⇒ no admin capability (assert a super_admin-only endpoint returns 403).
- [ ] Backend grievance API: empty key list in non-dev ⇒ requests rejected (new test in `tests/` mirroring existing grievance API tests).

### Manual verification
- [ ] `docker compose -f docker-compose.yml -f docker-compose.grm.yml up` **without** Keycloak env vars: `ticketing_api` container exits with the clear error, does not serve.
- [ ] Local dev flow (`TICKETING_ENV=dev`, bypass UI) still works end-to-end.

---

## 2. HR-02 — `require_ticket_access` dependency

### Problem (verified)

Per-ticket authorization is copy-pasted per endpoint and three endpoints skipped parts of it:

| Endpoint | Missing today |
|---|---|
| `GET /attachments/{file_id}` (`tickets.py:2114-2130`) | any authenticated user — **no SEAH gate, no scope/viewer check** |
| `GET /files/{file_id}` (`tickets.py:1949-1984`) | streams chatbot files from `public.file_attachments` with only an archived check |
| `GET /tickets/{id}/pii` (`tickets.py:2137-2187`) | SEAH checked, **jurisdiction/scope not checked** — any officer can pull PII for any standard ticket by ID |

Reference behavior (the correct gate set) already exists in `get_ticket` (`tickets.py:748-777`) and `list_tickets` (`tickets.py:525-557`): SEAH filter + scope filter + assignment/viewer visibility.

### Change

1. New module `ticketing/api/ticket_access.py` with a FastAPI dependency factory:
   ```python
   async def require_ticket_access(ticket_id, db, current_user) -> Ticket
   ```
   Single source of truth for: ticket exists (404) → SEAH gate (`ticket.is_seah and not current_user.can_see_seah` ⇒ 403) → scope/jurisdiction (reuse `scope_ticket_filter` / the `get_ticket` logic) → assignment/viewer/admin visibility. Return the loaded `Ticket` so endpoints don't re-query.
2. For file endpoints keyed by `file_id`, resolve file → owning ticket first, then run the same dependency logic (`require_file_access(file_id)` wrapping the ticket check). Chatbot-submitted files in `public.file_attachments` map to the ticket via `grievance_id` — resolve through the ticket, 404 if no owning ticket is visible.
3. Apply to **all** per-ticket endpoints in `tickets.py` (~15: detail, patch, actions, notes, files list/upload/download, attachments, pii, reveal, resolved-summary, tasks, viewers, messages). Replace the inline copy-pasted checks — behavior must be identical for the already-correct endpoints (assert via tests before/after).
4. Do **not** change `list_tickets` (query-level filtering stays as is).
5. PII endpoint additionally keeps its SEAH-mask rules from TP-15 (standard decrypted / SEAH masked) — this ticket only adds the missing scope gate, it does not alter masking.

### Tests (acceptance)

New file `tests/ticketing/test_ticket_access_matrix.py` — parametrized authz matrix, the mechanical guard against this whole bug class:
- Personas (fixtures): SEAH officer, in-scope standard officer (assigned), in-scope officer (not assigned, not viewer), out-of-scope officer, informed/observer viewer, super_admin.
- Endpoints under test: at minimum `GET /tickets/{id}`, `GET /tickets/{id}/pii`, `GET /files/{file_id}`, `GET /attachments/{file_id}`, `POST /tickets/{id}/actions` (NOTE), `GET /tickets/{id}/events`.
- [ ] SEAH ticket × non-SEAH personas ⇒ 403/404 on **every** endpoint (including both file endpoints — the regression this ticket fixes).
- [ ] Standard ticket × out-of-scope officer ⇒ 403/404 on detail, PII, files.
- [ ] Standard ticket × in-scope assigned officer ⇒ 200 everywhere.
- [ ] Observer/informed tier ⇒ read endpoints 200, mutating endpoints 403.
- [ ] super_admin ⇒ 200 everywhere.
- [ ] No-regression: run the existing ticketing test suite; zero failures.

### Manual verification
- [ ] As a seeded standard officer in the UI, open a SEAH file URL directly (copy a `file_id` from the DB) ⇒ 403/404.
- [ ] Reveal-contact flow still works for authorized personas (it layers on top of this gate).
