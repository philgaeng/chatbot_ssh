# Schema & Legacy Cleanup Sprint — Progress

> Update at **every commit** on a sprint branch. Status: `todo` · `in_progress` · `blocked` · `review` · `done`.
> Definition: [README.md](README.md) · Evidence: [AUDIT_FINDINGS.md](AUDIT_FINDINGS.md)

## Ticket status

| ID | Title | Status | Branch | Commits | Notes |
|---|---|---|---|---|---|
| CL-01 | Public schema single source of truth | todo | — | — | **First** — unblocks hardening CI (backend-tests seed step) |
| CL-02 | Remove legacy channels (accessible + gsheet) | todo | — | — | Independent; tables stay |
| CL-03 | Retire demo app / consolidate auth | todo | — | — | Re-point chatbot before deleting :5002 |

## Acceptance checklists

### CL-01 — Public schema truth
- [ ] Schema-diff harness written (normalizer + committed canonical `schema_app.sql` baseline)
- [ ] Reconciliation migration: +13 app-only tables, reconcile 7 drifted to live shape, drop 7 dead tables, exclude `events`
- [ ] `grievance_classification_taxonomy` handled data-preservingly (drop+recreate only when old `category_code` shape present; live `category_key` untouched)
- [ ] `grievance_statuses` standardized on live UPPERCASE vocab
- [ ] base_manager (+ other app-startup DDL) no longer creates/alters these tables
- [ ] Migrations guaranteed to run before app startup in every bring-up path
- [ ] Safe on a **copy of live grievance_db** (no data loss; only the 7 drops); row counts of kept tables unchanged
- [ ] Fresh CI path: migrations → **seed succeeds** → pytest runs; real pass/fail recorded (incl. the hardening "4 pre-existing failures" verdict on a clean DB)
- [ ] Schema-diff gate added to CI; `upgrade→downgrade→upgrade` clean

### CL-02 — Remove legacy channels
- [ ] Exclusivity re-verified by grep (nothing in REST_webchat/ticketing/orchestrator imports the delete set)
- [ ] Deleted: `channels/accessible/`, `channels/monitoring-gsheet/`, `voice_grievance.py`, `backend/services/accessible/`, `gsheet.py`, `gsheet_monitoring_api.py`, `backend/api/app.py`
- [ ] `fastapi_app.py` un-wired (voice_grievance + gsheet routers gone; files.router + websocket + `/accessible-socket.io` mount KEPT)
- [ ] nginx `/gsheet-get-grievances` removed; `/accessible-socket.io` + voice-chunk KEPT
- [ ] `GSHEET_BEARER_TOKEN` + `.claudeignore` + docs cleaned
- [ ] App boots clean; grep shows no live refs to removed modules
- [ ] **REST_webchat voice/socket/upload verified still working** (record live vs pending-human)
- [ ] DB tables `grievance_voice_recordings`/`grievance_transcriptions` NOT touched

### CL-03 — Retire demo / consolidate auth
- [ ] Chatbot `TICKETING_API_URL` re-pointed to consolidated API + intake round-trip verified (before deleting :5002)
- [ ] Compose: `grm_ui`:3001 + `ticketing_api`:5002 removed; `_auth` services promoted to canonical, `profiles:[auth]` dropped
- [ ] Staging nginx main domain → auth UI/API (mirrors prod); wsl conf reconciled
- [ ] Makefile services/ports/targets updated; `wsl-up`/`test-ticketing`/`wsl-seed` work
- [ ] Dev/CI bypass intact (`TICKETING_ENV=dev` local login works; `test_fail_closed_auth.py`/`_host_env.py` pass); no deployed build sets bypass
- [ ] Docs updated to single-stack + dev-only bypass
- [ ] Demo-data purge recorded as a pending data decision (not actioned)

## Deviations / findings log

| Date | Ticket | Deviation / finding | Action |
|---|---|---|---|
| — | — | Rasa is legacy (owner-confirmed); `events` excluded from Alembic this sprint | Future ticket: full Rasa removal — file separately |

## Sprint close checklist
- [ ] All 3 tickets `done`; hardening CI green end-to-end (the real reason CL-01 exists)
- [ ] Schema-diff gate protecting `public.*` in CI
- [ ] Future Rasa-removal ticket filed
- [ ] Summary doc written; folder archived; sprints index updated
