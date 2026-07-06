# Canonical Cleanup Sprint — Progress

> Update at **every commit**. Status: `todo` · `in_progress` · `blocked` · `review` · `done`.
> Definition: [README.md](README.md) · Evidence: [AUDIT_FINDINGS.md](AUDIT_FINDINGS.md) · **0 records → rebuild, don't reconcile.**

## Ticket status

| ID | Title | Status | Commits | Notes |
|---|---|---|---|---|
| CL-01 | Canonical `public.*` schema (squash + prune) | review | uncommitted (working tree) | Single squashed `pub000` baseline; 7 dead tables dropped + `events` excluded; 0 columns pruned (all ambiguous→kept, see `prune_audit.md`). Fresh migrate→seed→smoke green; non-integration pytest **195 passed / 0 failed**; 19 failures all pre-existing `@integration` ticketing-seed gaps (read `ticketing.*` only). |
| CL-02 | Remove legacy channels (accessible + gsheet) | todo | — | Independent; voice tables stay |
| CL-03 | Canonical config, env & deployment (one stack) | todo | — | Re-point chatbot before deleting :5002; preserves HR-01 fail-closed |

## Acceptance checklists

### CL-01 — Canonical public schema (squash + prune)
- [x] Live `pg_dump --schema-only` starting-point captured (read-only, `grievance_db` @ `pub007`); `prune_audit.md` lists dropped tables + per-column keep evidence (ambiguous → kept)
- [x] **Squash:** drifted `pub000..pub009` replaced by ONE canonical baseline (`pub000_public_core_baseline`, `down_revision=None`); `alembic_version_public` reset handled (fresh DBs start empty → run `pub000`; existing 0-record DBs rebuilt via `make reset_public_dev`); `ticketing`/`ops` untouched
- [x] Baseline creates 25 kept tables (24 live-kept + `seah_service_providers`) with **used columns only** (0 pruned), app types, `grievance_statuses` UPPERCASE vocab (+`archived`); excludes 7 dead tables + `events`; folds in used former-`pub008` archiving cols + `pub009` table; keeps `pgcrypto` ext + `keycloak` schema
- [x] App-startup DDL deleted from `base_manager.py` (`_create_tables`/`_create_indexes`/`recreate_db` + dead `migrate_grievance_timeline_column`/`migrate_to_enhanced_history_system` grievance_history migrate-and-drop) + `postgres_services.py` (`_ensure_seah_*` CREATEs; dead `grievance_vault_payloads` INSERT removed); seeds kept as `_seed_reference_data`. `grievance_categories_catalog.py`/`database_tables.py` had no CREATE/ALTER (data only). `grep CREATE TABLE backend/ ticketing/` → 0
- [x] Migrate-before-start: `scripts/database/init.py` runs the public Alembic stream before seeding; `03_operations.md` bring-up + `db_init` comment updated
- [x] Fresh empty DB → public+ticketing+ops migrate → **seed succeeds** (`import_locations_json` 837 locs + `mock_tickets --reset` both scenarios) → **pytest runs to completion** → **app smoke** (grievance write→read→status + hash col + archiving) green. Results: **326 passed / 19 failed / 6 skipped**; excluding `@integration`: **195 passed / 0 failed / 3 skipped**. Verdict: the 19 failures are ALL `pytest.mark.integration` (`test_officer_assignment`, `test_project_routing`, `test_ticket_uniqueness`, +`test_effective_role_keys`, `test_roles_crud`) that need the KL_ROAD→DOR project-actor org routing not seeded on a pristine DB; they read `ticketing.*` only and are unrelated to the public prune. The hardening "4 pre-existing failures" were measured in-container vs the long-lived `app_db` (before CL-01 the clean CI seed path died at `category_key`), so this is the first clean-path completion; 2 of those 4 reappear here, the rest are the same class of ticketing-seed gap
- [x] Self-consistency gate in CI (`scripts/ci/check_public_schema_baseline.sh` + committed `migrations/public/expected_public_schema.sql`); fresh-migration dump == committed baseline **verified locally**; `upgrade→downgrade→upgrade` clean; dead tables + `events` absent. **Real-CI run of the gate step pending (no gh access)**

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
| 2026-07-06 | CL-01 | **Future-Rasa note:** `public.events` (Rasa `SQLTrackerStore`, ~57k rows) is deliberately NOT created/dropped/managed by the public Alembic baseline — Rasa owns it. When Rasa is removed (owner-confirmed legacy), drop `events` + `events_id_seq` + `ix_events_sender_id` in that ticket. | Filed here; full Rasa removal is a separate future ticket |
| 2026-07-06 | CL-01 | **0 columns pruned** inside kept tables. After a column-by-column audit, every column is read via `SELECT *` (10 tables incl. `grievances`), written via dynamic `{field}_hash`/encrypt field-mapping (e.g. `complainant_full_name_hash`), or part of a cohesive used feature (archiving, vault refs, case_sensitivity). Ambiguous⇒keep per runbook. The real prune is the 7 dead tables + `events`. | Documented in `prune_audit.md`; no code referenced a dropped column |
| 2026-07-06 | CL-01 | **CI-green caveat (flag for orchestrator):** the 19 `@integration` pytest failures on a pristine DB are a *ticketing*-seed gap — `import_locations_json`+`mock_tickets --reset` don't create the KL_ROAD→DOR `implementing_agency` project actor that `resolve_ticket_organization` needs (conftest: "requires live DB + seed"). CI (`--maxfail=20`, no `-m` filter) will hit these until the ticketing seed creates that actor. Out of CL-01's `public.*` scope (these tests read `ticketing.*` only). | Flag for a ticketing-seed follow-up (seed the project actor in `mock_tickets`/`kl_road_standard`, or CI runs `-m "not integration"`) |
| 2026-07-06 | CL-01 | **`alembic_version_public` reset for existing DBs:** an existing DB stamped at the retired `pub007` can't `upgrade head` (revision gone). Since prod is 0-record, rebuild via `make reset_public_dev` (drops+recreates public schema incl. the version row, re-migrates to `pub000`). Fresh/CI DBs are unaffected. | Documented in `03_operations.md` rollback notes |
| — | — | Rasa legacy; `events` excluded from Alembic this sprint | Future ticket: full Rasa removal |
| — | — | 0 records confirmed → canonical rebuild + column prune; CL-03/CL-04 merged; keep one clean dev bypass | Specs rewritten to these calls |

## Sprint close checklist
- [ ] All 3 tickets `done`; hardening CI green end-to-end
- [ ] One convention per concept verified by grep (no old var/table/column/stack duplicates)
- [ ] Future Rasa-removal ticket filed
- [ ] Summary doc written; folder archived; sprints index updated
