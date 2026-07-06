# Canonical Cleanup Sprint — Progress

> Update at **every commit**. Status: `todo` · `in_progress` · `blocked` · `review` · `done`.
> Definition: [README.md](README.md) · Evidence: [AUDIT_FINDINGS.md](AUDIT_FINDINGS.md) · **0 records → rebuild, don't reconcile.**

## Ticket status

| ID | Title | Status | Commits | Notes |
|---|---|---|---|---|
| CL-04 | Canonical config & env (`APP_ENV`/`AUTH_MODE`/issuer/`.env.example`) | todo | — | **First** — var scheme underpins CL-03 + CI |
| CL-01 | Canonical `public.*` schema (single Alembic baseline) | todo | — | Unblocks CI backend-tests; independent of CL-04 |
| CL-03 | Consolidate deployment to one Keycloak stack | todo | — | After CL-04; re-point chatbot before deleting :5002 |
| CL-02 | Remove legacy channels (accessible + gsheet) | todo | — | Independent; tables stay |

## Acceptance checklists

### CL-04 — Canonical config & env
- [ ] `APP_ENV` in shared settings replaces `TICKETING_ENV`/`BACKEND_ENV`/`ENVIRONMENT` (grep → 0 old hits)
- [ ] `AUTH_MODE` (keycloak default; bypass only if `APP_ENV=dev`); HR-01 fail-closed guards re-expressed on it, behavior identical
- [ ] Single `KEYCLOAK_ISSUER`; frontend `NEXT_PUBLIC_OIDC_ISSUER` + bypass flag derived (4-var tangle collapsed)
- [ ] `docker-compose.override.yml` deleted; config from a single `.env`
- [ ] One root `.env.example`; `env.local`/`env.grm.example`/`ticketing-ui/.env.local` removed
- [ ] Makefile + CI env + docs on canonical vars
- [ ] `test_fail_closed_auth.py` + `_host_env.py` updated & green; prod refuses bypass; dev bypass works

### CL-01 — Canonical public schema
- [ ] `schema_app.sql` canonical reference captured + normalizer committed
- [ ] One canonical public baseline (re-baseline/squash the drifted `pub000..pub009`); creates the ~22 live tables at the app's real shape; excludes the 7 dead tables + `events`; `grievance_statuses` UPPERCASE vocab
- [ ] App-startup DDL deleted from `base_manager.py` (+ `grievance_categories_catalog.py`, `database_tables.py`, `postgres_services.py`); only data-seeding remains
- [ ] Migrate-before-start enforced in every bring-up path
- [ ] Fresh empty DB → migrations → **seed succeeds → pytest runs**; real results recorded (verdict on the hardening "4 pre-existing failures" on a clean DB)
- [ ] Schema-diff gate in CI; `upgrade→downgrade→upgrade` clean

### CL-03 — Consolidate deployment
- [ ] Chatbot `TICKETING_API_URL` re-pointed + intake round-trip verified (before deleting :5002)
- [ ] Compose: `grm_ui`:3001 + `ticketing_api`:5002 deleted; `_auth` services promoted to canonical single ui/api; deployed sets `APP_ENV`/`AUTH_MODE=keycloak`
- [ ] Staging nginx main domain → auth UI/API; wsl conf reconciled
- [ ] Makefile services/ports/targets updated; `wsl-up`/`test-ticketing`/`wsl-seed` work
- [ ] Dev bypass intact via `AUTH_MODE`; no deployed build bypasses
- [ ] Docs on single stack; demo-data purge noted as pending

### CL-02 — Remove legacy channels
- [ ] Exclusivity re-verified by grep; deleted `channels/accessible/`, `channels/monitoring-gsheet/`, `voice_grievance.py`, `backend/services/accessible/`, `gsheet.py`, `gsheet_monitoring_api.py`, `backend/api/app.py`
- [ ] `fastapi_app.py` un-wired (voice_grievance + gsheet routers gone; files.router + websocket + `/accessible-socket.io` KEPT)
- [ ] nginx `/gsheet-get-grievances` removed; `/accessible-socket.io` + voice-chunk KEPT
- [ ] `GSHEET_BEARER_TOKEN` + `.claudeignore` + docs cleaned (coordinate with CL-04's `.env.example`)
- [ ] App boots clean; **REST_webchat voice/socket/upload verified intact**; voice DB tables untouched

## Deviations / findings log

| Date | Ticket | Deviation / finding | Action |
|---|---|---|---|
| — | — | Rasa legacy; `events` excluded from Alembic this sprint | Future ticket: full Rasa removal |
| — | — | 0 records confirmed → canonical rebuild (specs rewritten from reconcile→rebuild) | — |

## Sprint close checklist
- [ ] All 4 tickets `done`; hardening CI green end-to-end
- [ ] One convention per concept verified by grep (no old var/table/stack duplicates)
- [ ] Future Rasa-removal ticket filed
- [ ] Summary doc written; folder archived; sprints index updated
