# Canonical Cleanup Sprint — Progress

> Update at **every commit**. Status: `todo` · `in_progress` · `blocked` · `review` · `done`.
> Definition: [README.md](README.md) · Evidence: [AUDIT_FINDINGS.md](AUDIT_FINDINGS.md) · **0 records → rebuild, don't reconcile.**

## Ticket status

| ID | Title | Status | Commits | Notes |
|---|---|---|---|---|
| CL-01 | Canonical `public.*` schema (squash + prune) | todo | — | Unblocks CI backend-tests; independent of var names |
| CL-02 | Remove legacy channels (accessible + gsheet) | todo | — | Independent; voice tables stay |
| CL-03 | Canonical config, env & deployment (one stack) | todo | — | Re-point chatbot before deleting :5002; preserves HR-01 fail-closed |

## Acceptance checklists

### CL-01 — Canonical public schema (squash + prune)
- [ ] `schema_app.sql` starting-point captured; `prune_audit.md` lists every dropped column/table + non-use evidence (ambiguous → kept)
- [ ] **Squash:** drifted `pub000..pub009` replaced by ONE canonical baseline; `alembic_version_public` reset; `ticketing`/`ops` untouched
- [ ] Baseline creates the ~22 live tables with **used columns only**, app types, `grievance_statuses` UPPERCASE vocab; excludes 7 dead tables + `events`
- [ ] App-startup DDL deleted (`base_manager.py` + `grievance_categories_catalog.py` + `database_tables.py` + `postgres_services.py`); code reading pruned columns removed/kept per audit
- [ ] Migrate-before-start enforced in every bring-up path
- [ ] Fresh empty DB → migrations → **seed succeeds → pytest runs → app smoke** (submit→ticket intake) green; real results recorded (verdict on hardening "4 pre-existing failures" on a clean DB)
- [ ] Self-consistency gate in CI (fresh-migration dump == committed baseline); `upgrade→downgrade→upgrade` clean

### CL-02 — Remove legacy channels
- [ ] Exclusivity re-verified by grep; deleted `channels/accessible/`, `channels/monitoring-gsheet/`, `voice_grievance.py`, `backend/services/accessible/`, `gsheet.py`, `gsheet_monitoring_api.py`, `backend/api/app.py`
- [ ] `fastapi_app.py` un-wired (voice_grievance + gsheet routers gone; files.router + websocket + `/accessible-socket.io` KEPT)
- [ ] nginx `/gsheet-get-grievances` removed; `/accessible-socket.io` + voice-chunk KEPT
- [ ] `GSHEET_BEARER_TOKEN` + `.claudeignore` + docs cleaned (coordinate with CL-03's `.env.example`)
- [ ] App boots clean; **REST_webchat voice/socket/upload verified intact**; voice DB tables untouched

### CL-03 — Canonical config, env & deployment
- [ ] `APP_ENV` replaces `TICKETING_ENV`/`BACKEND_ENV`/`ENVIRONMENT` (grep → 0 old hits)
- [ ] `AUTH_MODE` (keycloak default; bypass only if `APP_ENV=dev`); HR-01 guards re-expressed, behavior identical; cleaned bypass surface kept, one-flag-driven
- [ ] Single `KEYCLOAK_ISSUER`; frontend `NEXT_PUBLIC_OIDC_ISSUER` + bypass flag derived
- [ ] `docker-compose.override.yml` deleted; one root `.env.example`; three old templates removed; `.gitignore` fixed
- [ ] `test_fail_closed_auth.py` + `_host_env.py` updated & green; prod refuses bypass; dev bypass works
- [ ] Chatbot `TICKETING_API_URL` re-pointed + intake round-trip verified (before deleting :5002)
- [ ] Compose: `grm_ui`:3001 + `ticketing_api`:5002 deleted; `_auth` promoted to canonical single ui/api; deployed sets `APP_ENV`/`AUTH_MODE=keycloak`
- [ ] Staging nginx main domain → auth UI/API; wsl conf reconciled; Makefile updated; `wsl-up`/`test-ticketing`/`wsl-seed` work
- [ ] Docs on single stack + canonical vars; demo-data purge noted as pending

## Deviations / findings log

| Date | Ticket | Deviation / finding | Action |
|---|---|---|---|
| — | — | Rasa legacy; `events` excluded from Alembic this sprint | Future ticket: full Rasa removal |
| — | — | 0 records confirmed → canonical rebuild + column prune; CL-03/CL-04 merged; keep one clean dev bypass | Specs rewritten to these calls |

## Sprint close checklist
- [ ] All 3 tickets `done`; hardening CI green end-to-end
- [ ] One convention per concept verified by grep (no old var/table/column/stack duplicates)
- [ ] Future Rasa-removal ticket filed
- [ ] Summary doc written; folder archived; sprints index updated
