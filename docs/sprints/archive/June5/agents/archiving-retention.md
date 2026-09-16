# Agent prompt — Archiving and retention

You are implementing the **resolved-case archiving** policy: scheduled job, settings JSON, DB flags, queue filters, and attachment tiering per the locked formula.

---

## Read first

1. **`docs/ARCHIVING_AND_RETENTION.md`** — canonical policy (formula, attachments, checklist)
2. `docs/ticketing_system/02_ticketing_domain_and_settings.md` — settings store
3. `docs/ticketing_system/08_ticket_resolution_and_case_summary.md` — `RESOLVED` event timestamp
4. `ticketing/api/routers/tickets.py` — resolve flow, list/filter queries
5. `ticketing/api/routers/settings.py` — `report_limits` validation pattern
6. `ticketing/clients/grievance_api.py` — status updates to chatbot backend
7. `backend/api/routers/files.py` — upload guard for archived grievances
8. `docs/services/04_file_processing_service.md` — §7 attachments
9. `CLAUDE.md` — no `ticketing.*` → `public.*` SQL joins; use grievance API

---

## Mission

| # | Deliverable |
|---|-------------|
| 1 | `ticketing.settings` key **`archiving_policy`** with validation (super_admin) |
| 2 | Alembic: `ticketing.tickets` — `is_archived`, `archived_at` |
| 3 | Alembic **public**: `grievances` + `file_attachments` archive columns (or `ARCHIVED` status seed) |
| 4 | Service: `ticketing/services/archiving.py` — eligibility date, select candidates, archive one ticket |
| 5 | Celery task + Beat schedule: **`archive_eligible_grievances_task`** (daily) |
| 6 | Ticket list/queue APIs: default `is_archived = false` |
| 7 | File upload: reject if grievance archived |
| 8 | Grievance API: set archived status via existing client |
| 9 | Attachment tier **`cold`**: move/copy to `archive/` prefix when S3 configured; **`none`** mode if local only |
| 10 | Settings UI: default JSON in System config tab (super_admin) |
| 11 | Tests: eligibility formula, idempotency, queue filter |

---

## Locked decisions (§2 — do not change)

Implement **`docs/ARCHIVING_AND_RETENTION.md` §2** rules **L1–L6** exactly:

| ID | Rule |
|----|------|
| L1 | Resolved time = latest `ticket_events` `RESOLVED.created_at`; grievance `ARCHIVED` only on job success |
| L2 | Reopen clears `is_archived` / `archived_at`; new **N** from latest resolve when back in `RESOLVED`/`CLOSED` |
| L3 | `CLOSED` = `RESOLVED` for eligibility |
| L4 | SEAH same defaults; optional `seah_years_before_archiving` override |
| L5 | Idempotent skip if already archived |
| L6 | Daily job; `today >= archive_eligible_date` (Jan 2 catch-up) |

**Formula:**

```
N = calendar year (Asia/Kathmandu) of resolution timestamp (L1)
archive_eligible_date = January 2, year (N + 1 + years_before_archiving)
years_before_archiving >= 1
```

If no `RESOLVED` event and no `ticket_resolved_summaries.resolved_at` → **skip row**, log warning (do not archive).

---

## You may edit

- `ticketing/migrations/versions/*.py` — ticketing columns only
- `migrations/public/versions/*.py` — public grievance + file_attachments columns
- `ticketing/services/archiving.py` (new)
- `ticketing/tasks/` — archive task (or `grm_celery` task module)
- `ticketing/api/routers/settings.py`, `tickets.py`
- `ticketing/models/ticket.py`
- `ticketing/clients/grievance_api.py` — archive status call if missing
- `backend/api/routers/files.py` — archived grievance upload guard
- `backend/config/database_tables.py` or status seed — `ARCHIVED` grievance status if needed
- `channels/ticketing-ui/app/settings/page.tsx` — `archiving_policy` JSON block
- `tests/ticketing/test_archiving*.py`
- `docs/ARCHIVING_AND_RETENTION.md` — implementation notes only if shipped behaviour differs

---

## Do not edit

- `backend/orchestrator/`, `backend/actions/` (unless user extends chatbot copy for status-check)
- Cross-schema SQL joins from ticketing into `public.*`
- Hard delete of grievances, PII, or S3 objects

---

## Implementation order

### Phase A — Schema + settings

1. Migration `ticketing`: `is_archived`, `archived_at` on `tickets`.
2. Migration `public`: `file_attachments.storage_tier`, `archived_at`, `storage_key`; grievance `is_archived` / `archived_at` or `ARCHIVED` status.
3. `archiving_policy` defaults in seed or settings API; validate `years_before_archiving >= 1`.
4. Register key in `SUPER_ADMIN_ONLY_KEYS` (or equivalent) in `settings.py`.

### Phase B — Core logic

```python
def archive_eligible_date(resolved_at: datetime, years_before_archiving: int, tz: str) -> date: ...
def select_eligible_tickets(db, policy, as_of: date) -> list[Ticket]: ...
def archive_ticket(db, ticket, policy) -> ArchiveResult: ...
```

`archive_ticket`:

1. Set `ticket.is_archived`, `ticket.archived_at`
2. `POST` grievance status `ARCHIVED` via `grievance_api`
3. For each `file_attachments` row: tier per `attachment_tier_on_archive`
4. Insert `ticket_events` payload `{ "event_type": "CASE_ARCHIVED", ... }` or documented equivalent
5. `admin_audit_log` summary row

### Phase C — Scheduler

- Celery Beat entry: daily 03:00 Asia/Kathmandu
- Env `ARCHIVING_DRY_RUN=true` for first prod run (log only)

### Phase D — API + UI guards

- Ticket queues: filter archived out
- `GET /tickets/{id}/files` + download: respect archived + role
- `POST /upload-files`: 409 if grievance archived
- Settings UI JSON editor with defaults from spec §3.1

---

## Attachment tier v1

| `attachment_tier_on_archive` | Implement |
|------------------------------|-----------|
| `none` | DB flags only — **ship this first** if S3 move not ready |
| `cold` | Copy to `archive/{grievance_id}/...`; update `storage_key` |
| `glacier` | Document only + S3 lifecycle tag; optional stub |

---

## Tests (minimum)

```python
def test_archive_eligible_date_2026_resolved_years_1():
    # resolved 2026-06-15 Kathmandu → eligible 2028-01-02

def test_not_eligible_before_date(): ...

def test_archive_job_idempotent(): ...

def test_queue_excludes_archived(): ...
```

---

## Progress protocol

Update `docs/sprints/June5/PROGRESS.md` → subsection **Archiving and retention**.

| Item | Status |
|------|--------|
| Settings `archiving_policy` | |
| Ticketing migration | |
| Public migration | |
| `archiving.py` + Celery task | |
| Queue/upload guards | |
| Settings UI JSON | |
| Tests | |
| Prod dry-run | |

---

## Definition of done

- [ ] Policy JSON readable/writable by super_admin
- [ ] **L1–L6** behaviour matches `docs/ARCHIVING_AND_RETENTION.md` §2
- [ ] Formula matches §3.3 examples
- [ ] Daily job archives eligible resolved tickets only
- [ ] Archived tickets hidden from default officer queues
- [ ] Upload blocked for archived grievance_id
- [ ] Attachments: metadata retained; tier `none` or `cold` implemented and documented
- [ ] No hard deletes
- [ ] PROGRESS.md updated

---

## Report back

1. Migrations applied (ticketing + public versions)
2. Sample eligibility calculation for one mock ticket
3. Dry-run log line count from one job execution
4. S3 vs local path for attachment tier
