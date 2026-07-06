# Audit findings — schema & legacy cleanup

> Read-only audit run July 2026 (three parallel investigations) that scoped this sprint. Evidence base for all three tickets — implementers should trust this and re-verify with grep before editing (line numbers drift). DB inspected: the live native chatbot DB `grievance_db` (Postgres :5432, user `nepal_grievance_admin`), `alembic_version_public = pub007` (pub008/pub009 unapplied).

---

## 1. Public schema — dual ownership is the root cause

`public.*` is co-owned by two DDL sources that have drifted:
- **App-startup DDL:** `backend/services/database_services/base_manager.py` (creates 22 tables via `CREATE TABLE IF NOT EXISTS`), plus `ticketing/services/grievance_categories_catalog.py`, `backend/config/database_tables.py`, `backend/services/database_services/postgres_services.py`.
- **Alembic public stream:** `migrations/public/versions/*.py` (`pub000`…`pub009`).

CI runs migrations only ⇒ builds a schema the app/seed can't use ⇒ the `Seed KL Road` CI step dies (`grievance_classification_taxonomy.category_key does not exist`) before pytest runs.

### 1a. Tables that exist ONLY in app-startup DDL (13 — must be ADDED to Alembic, kept)
`field_names`, `grievance_classification_statuses`, `grievance_transcriptions`, `grievance_translations`, `grievance_voice_recordings`, `office_management`, `office_municipality_ward`, `office_user`, `processing_statuses`, `projects`, `reference_grm_office_in_charge`, `reference_municipality_villages`, `seah_contact_points`. All live (non-zero rows except the voice tables which are low). `seah_contact_points` also has DDL in `postgres_services.py`.

### 1b. Drift cases — table in BOTH sources, columns disagree (7 of 9 co-defined tables)
Reconcile each **to the live / base_manager shape** (that's what prod runs):

| Table | Drift |
|---|---|
| `grievance_classification_taxonomy` | **MAJOR** — base_manager PK `category_key` + 14 bilingual cols; `pub000` PK `category_code` + 7 generic cols. Different PK, no column overlap. Live = base_manager shape. |
| `grievance_statuses` | `pub000` has `updated_at` (live lacks it) **and conflicting seed vocab**: `pub000` seeds 4 lowercase (`received/in_progress/resolved/closed`); base_manager/`database_tables.py` seed 7 UPPERCASE (`SUBMITTED/UNDER_EVALUATION/ESCALATED/…`). Live has **11 rows = both coexisting**. Pick the live/UPPERCASE vocab. |
| `task_statuses` | Dual-mutated: base_manager full cols; `pub000` minimal + `ALTER ADD status_name`. Live = union. |
| `tasks` | `pub000` adds `metadata JSONB`; base_manager/live lacks it. |
| `file_attachments` | base_manager/live has `id` surrogate PK + `client_metadata`; `pub000` lacks both. |
| `grievance_status_history` | base_manager/live has extra `change_type` + `field_changes`; `pub000` lacks them. |
| `task_entities` | `pub000` has `id BIGSERIAL PK`; base_manager/live has no `id`. |

`complainants` and `grievances` align once later migrations (`pub003/04` vault cols, `pub007` geo) are counted.

### 1c. Dead tables → DROP (product-owner confirmed)
| Table | rows | Evidence |
|---|---|---|
| `grievance_history` | 0 | `base_manager.py` `DROP TABLE IF EXISTS grievance_history CASCADE` at startup (:1033, :1960); data migrated into `grievance_status_history`. Only stale ref in `database_tables.py`. |
| `users` | 0 | No creator in either source, no reader; sole ref is a drop-list in `scripts/database/init.py`. Orphan. |
| `contact_info` | 0 | Created only by `pub002`; no app SQL (the `'contact_info'` strings found are a Celery op-key, not the table). |
| `resource_persons` | 0 | Created only by `pub002`; zero code refs. |
| `grievance_reveal_sessions` | 0 | `pub003` SEAH vault-audit foundation, **never wired** — real reveal-audit logs `REVEAL_ORIGINAL` into `ticketing.*`. Only other ref: a DELETE in `scripts/ops/prod_sync_remove_mock_data.sql`. |
| `grievance_sensitive_access_audit` | 0 | Same as above (`pub003`, unwired). |
| `grievance_vault_payloads` | 0 | `pub003`; single writer `postgres_services.py:727` (INSERT only), no data. Abandoned with the trio. |

### 1d. Keep but EXCLUDE from Alembic (external-owned)
- `events` (57,107 rows) — Rasa `SQLTrackerStore`, Rasa-owned schema. **Rasa is legacy** (owner-confirmed) but removing it is a *separate future cleanup* — for this sprint, exclude `events` from the Alembic-managed set and leave Rasa alone. Add a note flagging the future Rasa-removal.
- `alembic_version_public` — Alembic infra.

---

## 2. Legacy channels — removal-safety map

⚠️ **Naming trap:** components named "accessible"/"voice" are REST_webchat's LIVE infra. Do NOT delete by name.

### 2a. `channels/accessible/`
Standalone static HTML/JS voice-first frontend. **Not** in any compose/nginx/Makefile (`.claudeignore:19`); `socket.js` hardcodes a prod origin. Exclusively-serving backend:
- `backend/api/routers/voice_grievance.py` (routes `/accessible-file-upload`, `/submit-grievance`, `/grievance-status/{id}`).
- `backend/services/accessible/` (whole dir: `voice_grievance.py`, `voice_grievance_helpers.py`, `voice_grievance_orchestration.py`) — imported only by that router + dead `backend/api/app.py`.

### 2b. `channels/monitoring-gsheet/`
A Google Apps Script (runs in Sheets, `.claudeignore:22`). Backend:
- `backend/api/routers/gsheet.py` (`GET /gsheet-get-grievances`, bearer `GSHEET_BEARER_TOKEN`) — **already dead**: calls `db_manager.gsheet.get_grievances_for_gsheet` which has no definition (AttributeError at runtime).
- `backend/api/gsheet_monitoring_api.py` (Flask blueprint, only wired in dead `app.py`).

### 2c. SAFE TO DELETE (used only by these two legacy channels)
`channels/accessible/`, `channels/monitoring-gsheet/`, `backend/api/routers/voice_grievance.py`, `backend/services/accessible/`, `backend/api/routers/gsheet.py`, `backend/api/gsheet_monitoring_api.py`, `backend/api/app.py` (dead Flask rollback artifact — not launched; only `uvicorn backend.api.fastapi_app:app` runs).

### 2d. MUST STAY — shared with REST_webchat (the naming trap)
| Component | Why it's live |
|---|---|
| Socket.IO app + `app.mount("/accessible-socket.io", …)` (`fastapi_app.py:128`, `websocket_fastapi.py`, `websocket_utils.py`) | REST_webchat `app.js:517-519` connects `/accessible-socket.io`; `files.py:771-790` emits webchat status through it. |
| Voice-chunk upload — `/upload-voice-chunk`, `/upload-voice-complete` (`files.py:390,492`) + `file_server_core` chunk methods | REST_webchat recording button (`modules/voiceNote.js`, `voiceChunkUpload.js`, `config.js:25-26`); nginx proxies both. |
| File tasks `process_file_upload_task`, `process_batch_files_task` (`registered_tasks.py:118,184`) | Shared by all webchat/file uploads. |
| Transcription task + service + tables — `transcribe_audio_file_task` (`registered_tasks.py:391`), `LLM_services.transcribe_audio_file`, tables `grievance_voice_recordings`/`grievance_transcriptions` | Webchat voice re-enable path (proto currently defers transcription; keep it). |
| `files.router`, `/upload-files`, `/create-grievance`, `/generate-ids` | General webchat APIs. |

### 2e. Config/wiring cleanup
- `backend/api/fastapi_app.py`: drop `voice_grievance` + `gsheet` from import (`:45`) and their `include_router` (`:122,123`). **KEEP** `files.router` (`:120`), websocket imports (`:46`), `/accessible-socket.io` mount (`:128`).
- nginx (`deployment/nginx/webchat_rest_compose_{wsl,prod,prod.tls,aws}.conf`): remove `location /gsheet-get-grievances`. **KEEP** `/accessible-socket.io`, `/upload-voice-chunk`, `/upload-voice-complete`.
- Env `GSHEET_BEARER_TOKEN` (`gsheet.py:16`, `gsheet_monitoring_api.py:14`, `backend/utils/env.grm.example`, `docs/deployment/12_environment_urls.md`, `deployment_environment_urls.*.yaml`).
- `.claudeignore:19,22`. Docs (optional): `docs/services/08_gsheet_monitoring_service.md`, `docs/deployment/06_integrations.md`, `04_backend.md:58-60`, `README.md:76`, `docs/README.md:67`, CLAUDE.md service-boundary lines.
- **Tables stay:** `grievance_voice_recordings`/`grievance_transcriptions` are shared voice infra — NOT dropped by channel removal.

---

## 3. Demo app = the no-Keycloak bypass stack

`docker-compose.grm.yml:3-9` labels it "Demo stack (bypass auth, no Keycloak)":

| | Demo/bypass | Real Keycloak |
|---|---|---|
| UI | `grm_ui` :3001, `NEXT_PUBLIC_BYPASS_AUTH:"true"` (`:298-327`) | `grm_ui_auth` :3002, `profiles:[auth]` (`:329-371`) |
| API | `ticketing_api` :5002, `KEYCLOAK_ISSUER:""` (`:127-174`) | `ticketing_api_auth` :5003, `profiles:[auth]` (`:373+`) |
| Login | "Continue to demo queue", no password (`app/login/page.tsx:122-137`) | email+password OIDC |
| Identity | dev-bypass → `BYPASS_DEFAULT_OFFICER` super_admin (`dependencies.py:182-198`, HR-01-gated to dev) + `grm_bypass_user` cookie → `x-internal-*` headers (`app/api/v1/[...path]/route.ts:49-72`) | Keycloak JWT |

**Double-duty risk:** `ticketing_api` :5002 is also the chatbot's ticket-intake target (`ticketing_dispatch.py:20` `TICKETING_API_URL=http://ticketing_api:5002`; `create_ticket` uses `verify_api_key`, independent of bypass) and the `make test-ticketing` container (`Makefile:446`).

**Environment state:** prod already retired the demo UI (`grm_ui profiles:[demo]`, `PROD_DEPLOY_SERVICES` excludes it; prod nginx fronts auth UI). **AWS staging still fronts the demo** — `webchat_rest_compose_aws.conf` routes the main domain `/queue`,`/grm/`,`/ticketing/` → `grm_ui:3001`; auth UI only on `grm-auth.` subdomain. Local `wsl-up` runs both.

**Bypass surface (frontend):** `app/login/page.tsx:15,122-137`; `AuthProvider.tsx` (`grm_bypass_user` cookie, `fallbackBypassToken`, `bypassRoster`, `switchBypassUser`); `components/AppShell.tsx:45-90` + `MobileAppHeader.tsx:12-40` role switchers; `app/api/v1/[...path]/route.ts:49-72`.
**Bypass surface (backend):** `dependencies.py:23,182-198,221-236` dev-bypass branch + `BYPASS_DEFAULT_OFFICER` + `x-internal-user-id` path (already fail-closed outside dev via HR-01).

**Keycloak readiness:** real path confirmed working (`docs/deployment/16_auth_keycloak.md` "as-built, Keycloak everywhere"; OIDC client, `keycloak_jwt.py`, `make keycloak-setup`, prod serves it exclusively).

**Demo accounts:** `@grm.local` officers (`demo_officers.py`, `mock_tickets.py`) are **also seeded into real Keycloak** (`keycloak_setup.py:34,416`) — purging them from deployed envs is a separate data decision, not part of removing bypass code.

---

## 4. Config / env sprawl (canonicalization evidence)

**Context that unlocks a clean rebuild:** prod is **not live — 0 real records**. Breaking changes (rename/drop env vars, collapse stacks, re-baseline the DB) are safe; no backward-compat or data migration needed.

**Compose files (5):** `docker-compose.yml` (chatbot base), `docker-compose.grm.yml` (GRM/ticketing services — carries the demo/auth split), `docker-compose.override.yml` (only job: inject `BACKEND_ENV=dev`), `docker-compose.prod.yml`, `docker-compose.aws.yml`.
**Env templates (3):** `env.local` (gitignored dev), `backend/utils/env.grm.example`, `channels/ticketing-ui/.env.local`.
**Same concept, multiple spellings (the "mess"):**
- **Env mode:** `TICKETING_ENV` (×5) + `BACKEND_ENV` (×8) + stray `ENVIRONMENT` (×2) — three names for one idea.
- **Keycloak issuer:** `KEYCLOAK_ISSUER` (×10, backend) + `NEXT_PUBLIC_OIDC_ISSUER` (×10, frontend) — two hand-maintained names for one realm.
- **Dev bypass:** a 4-variable tangle — `NEXT_PUBLIC_BYPASS_AUTH` (×23) + `KEYCLOAK_ISSUER=""` + `TICKETING_ENV=dev` + `BACKEND_ENV=dev`.
- **Chatbot→ticketing:** `TICKETING_API_URL` (×16), pinned to the demo `:5002`.

**Canonical target (CL-03 + CL-04):** one `APP_ENV` (`dev`/`staging`/`production`); one `AUTH_MODE` (`keycloak` default; `bypass` honored only when `APP_ENV=dev`); one `KEYCLOAK_ISSUER` (frontend `NEXT_PUBLIC_` value derived, not hand-kept); one deployed Keycloak stack; `docker-compose.yml` base + `grm` overlay (single stack) + `prod`/`aws` deploy overlays, **no** `override.yml`/demo split; one committed `.env.example`. Fail-closed security preserved (prod can never bypass).
