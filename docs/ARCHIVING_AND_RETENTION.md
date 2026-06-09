# Archiving and retention policy

**Status:** Implemented (2026-06-08)  
**Last updated:** 2026-06-08  
**Applies to:** Resolved GRM grievances (standard + SEAH), chatbot `public.*` records, ticketing cases, file attachments

**Related:**

- [`docs/deployment/09_privacy.md`](deployment/09_privacy.md) — PII, SEAH, audit
- [`docs/services/04_file_processing_service.md`](services/04_file_processing_service.md) — attachment storage lifecycle
- [`docs/ticketing_system/02_ticketing_domain_and_settings.md`](ticketing_system/02_ticketing_domain_and_settings.md) — `ticketing.settings`
- [`docs/ticketing_system/08_ticket_resolution_and_case_summary.md`](ticketing_system/08_ticket_resolution_and_case_summary.md) — resolution timestamp
- [`docs/services/07_task_queue_service.md`](services/07_task_queue_service.md) — scheduled Celery jobs

---

## 1) Purpose

Move **resolved** grievances into an **archived** state after a configurable cooling period so that:

- Active officer queues stay focused on open work
- Evidence and audit history remain available for reporting and oversight
- Attachment storage can tier down to cheaper object-storage classes
- PII access stays logged and role-gated (not deleted in v1)

Archiving is **soft retirement**, not deletion.

---

## 2) Locked decisions (implementers must not guess)

These rules are **fixed for v1**. Do not infer alternatives at implementation time.

| # | Question | **Locked answer** |
|---|----------|-------------------|
| L1 | Which timestamp is “resolved”? | **`ticketing.ticket_events`** where `event_type = 'RESOLVED'` → **`created_at`** (authoritative). Pair ticket ↔ grievance by **`grievance_id`**. Mirror **`public.grievances`** to status **`ARCHIVED`** only when the archive job runs (via grievance API), not at resolve time. |
| L2 | Reopened after resolve? | If `status_code` leaves **`RESOLVED`** / **`CLOSED`**, the case is **not eligible**. Clear **`is_archived`** / **`archived_at`** on ticket and grievance if set. Recompute year **N** from the **latest** `RESOLVED` event only when the ticket is again **`RESOLVED`** or **`CLOSED`**. |
| L3 | `CLOSED` vs `RESOLVED`? | **Treat identically** for archiving eligibility. |
| L4 | SEAH tickets? | **Same formula and defaults as standard** in v1. Optional override: settings field **`seah_years_before_archiving`** (int ≥ 1 when set) replaces `years_before_archiving` for tickets where **`is_seah = true`**. When `null`, use global `years_before_archiving`. |
| L5 | Already archived? | Job is **idempotent**: skip any row with **`is_archived = true`** or **`archived_at IS NOT NULL`** (ticket and grievance). |
| L6 | Missed run on 2 January? | Job runs **daily**. Archive all cases where **`today >= archive_eligible_date`** (catch-up). No separate manual “Jan 2 only” gate beyond the eligibility date. |

**Resolution timestamp fallback (only when L1 event missing):** use `ticketing.ticket_resolved_summaries.resolved_at`; if still missing, **do not archive** — log warning and skip row (never guess from filing date).

---

## 3) Eligibility

### 3.1 Which cases archive

| Criterion | Rule |
|-----------|------|
| Ticket status | **`RESOLVED`** or **`CLOSED`** (see L3) |
| Grievance | Set to **`ARCHIVED`** when archive job succeeds (see L1) |
| SEAH | See L4 |
| Already archived | See L5 |
| Reopened | See L2 |

### 3.2 Resolution year **N**

**N** = calendar year of the resolution timestamp (L1) in timezone **`Asia/Kathmandu`**.

Use the **latest** `RESOLVED` event `created_at` per `ticket_id` when multiple events exist (backfill / re-resolve).

### 3.3 Archive date formula (locked)

Settings parameter **`years_before_archiving`** (integer, **minimum 1**).

> If a grievance is resolved in year **N**, it becomes eligible for archiving on **2 January**, year **N + 1 + years_before_archiving**.

Examples (`years_before_archiving = 1`):

| Resolved at (Kathmandu) | N | Archive eligible from |
|-------------------------|---|------------------------|
| 2026-03-15 | 2026 | **2028-01-02** |
| 2026-12-31 | 2026 | **2028-01-02** |
| 2027-01-01 | 2027 | **2029-01-02** |

Examples (`years_before_archiving = 2`):

| Resolved at | N | Archive eligible from |
|-------------|---|------------------------|
| 2026-08-01 | 2026 | **2029-01-02** |

**Job behaviour:** See **L6** — daily run; `today >= archive_eligible_date`.

---

## 4) Configuration (`ticketing.settings`)

**Key:** `archiving_policy`  
**Write access:** `super_admin` only (same class as `report_limits`).

### 4.1 JSON schema

```json
{
  "enabled": true,
  "years_before_archiving": 1,
  "archive_run_month": 1,
  "archive_run_day": 2,
  "timezone": "Asia/Kathmandu",
  "attachment_tier_on_archive": "cold",
  "allow_complainant_download_when_archived": false,
  "seah_years_before_archiving": null
}
```

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `enabled` | boolean | `true` | Master switch; job no-ops when `false` |
| `years_before_archiving` | int | `1` | **Min 1** — used in formula §3.3 |
| `archive_run_month` | int | `1` | January |
| `archive_run_day` | int | `2` | 2nd — used for documentation/eligibility anchor; job still runs daily |
| `timezone` | string | `Asia/Kathmandu` | For year **N** extraction |
| `attachment_tier_on_archive` | string | `"cold"` | `none` \| `cold` \| `glacier` — see §5 |
| `allow_complainant_download_when_archived` | boolean | `false` | Chatbot / public download paths |
| `seah_years_before_archiving` | int \| null | `null` | See **L4** — when set, min 1; overrides global value for SEAH tickets only |

**Validation (API):** reject `years_before_archiving < 1`; reject invalid month/day; log change in `ticketing.admin_audit_log`.

**UI:** Extend Settings → System config (super_admin JSON), same pattern as `report_limits`.

---

## 5) Data model changes (to implement)

### 5.1 Ticketing (`ticketing/migrations/`)

| Table | Columns |
|-------|---------|
| `ticketing.tickets` | `archived_at TIMESTAMPTZ NULL`, `is_archived BOOLEAN NOT NULL DEFAULT false` |
| `ticketing.ticket_events` | Optional: `CASE_ARCHIVED` event (or reuse `NOTE_ADDED` with payload flag) |

Indexes: `(is_archived, status_code)` for queue filters.

### 5.2 Public / chatbot (`migrations/public/`)

| Table | Columns |
|-------|---------|
| `public.grievances` | `archived_at TIMESTAMPTZ NULL`, `is_archived BOOLEAN NOT NULL DEFAULT false` **or** status code `ARCHIVED` in `grievance_status` reference data |
| `public.file_attachments` | `storage_tier VARCHAR(16) DEFAULT 'active'`, `archived_at TIMESTAMPTZ NULL`, `storage_key TEXT NULL` (S3 key after move) |

Add `ARCHIVED` to grievance status seed if using status code instead of boolean.

**No** cross-schema FKs. Archive job updates ticketing first, then calls **grievance API** for `public.grievances` (integration boundary per CLAUDE.md).

### 5.3 What is retained (never deleted in v1)

| Artifact | Retained |
|----------|----------|
| `ticket_events`, resolution record, resolved summary | Yes |
| `ticket_resolved_summaries` | Yes |
| Quarterly report rows / export history | Yes — archived cases remain in historical reports |
| `file_attachments` metadata row | Yes |
| Object storage blob | Yes — tier/move, not delete |
| PII in `complainants` / vault | Yes — tighter reveal policy |

---

## 6) Attachments — consequences

See also [`docs/services/04_file_processing_service.md`](services/04_file_processing_service.md) §7.

| Tier (`attachment_tier_on_archive`) | Behaviour |
|-------------------------------------|-----------|
| **`none`** | Archive case flags only; blobs stay at current path/key (v1 minimal) |
| **`cold`** (recommended) | Copy/move object to `archive/{grievance_id}/{file_id}.jpg`; update `storage_key`, `storage_tier = 'archive'`; optional delete active key after successful copy |
| **`glacier`** | S3 lifecycle transition on `archive/` prefix (ops runbook); restore latency acceptable for audit only |

| Access surface | Active case | Archived case |
|----------------|-------------|---------------|
| Officer **My Queue / All Active** | Normal | **Hidden** |
| Officer **Archived** search (super_admin / local_admin) | — | Read-only case + attachments |
| Officer download attachment | Allowed | Allowed with audit log |
| Complainant chatbot status / download | Allowed | **Denied** (unless `allow_complainant_download_when_archived`) |
| New uploads to `grievance_id` | Allowed | **Rejected** with clear error |
| Ticketing escalate/resolve gates | Normal | N/A (already resolved) |

**Officer ticket files API** (`GET /tickets/{id}/files`, download): return **403** or empty list when archived unless caller has `can_view_archived` (super_admin + local_admin v1).

---

## 7) Scheduled job

| Item | Value |
|------|-------|
| Task name | `archive_eligible_grievances_task` |
| Scheduler | Celery Beat — **daily** (e.g. 03:00 `Asia/Kathmandu`) |
| Owner | `ticketing/tasks/` or `backend/task_queue/` — prefer **ticketing** Celery app (`grm_celery`) for ticket-centric logic |
| Idempotency | Per `ticket_id`: skip if `is_archived` |
| Steps | 1) Load `archiving_policy` 2) Select eligible tickets 3) Archive ticket row 4) Grievance API status 5) Tier attachments 6) Emit `CASE_ARCHIVED` event 7) Audit log |

**Dry-run mode (settings or env):** log counts without writes — for prod first run.

---

## 8) API and UI impact

| Area | Change |
|------|--------|
| `ticketing/api/routers/tickets.py` | Queue/list endpoints: `is_archived = false` default filter |
| `ticketing/api/routers/settings.py` | Validate + upsert `archiving_policy`; super_admin only |
| `channels/ticketing-ui` | System config JSON defaults; optional “Archived cases” admin list (post-v1) |
| `backend/api/routers/files.py` | Block upload if grievance archived |
| `backend/api/routers/grievance` | `ARCHIVED` status; status-check utterances |
| Reports | Include archived cases in **historical** quarterly exports by resolution year |

---

## 9) Security and privacy

- Archiving **does not** purge PII — aligns with [`docs/deployment/09_privacy.md`](deployment/09_privacy.md).
- **Reveal contact** on archived cases: super_admin only v1; all reveals audited.
- SEAH archived cases: same attachment tier rules; access still `can_see_seah` gated.
- **Legal hold** (future): `legal_hold = true` on ticket skips archive job.

---

## 10) Out of scope (v1)

- Hard delete of grievances, PII, or blobs
- Automatic Glacier restore workflow
- Complainant-facing “your case was archived” notification (optional later)
- Per-project or per-organization retention overrides (except SEAH override field)

---

## 11) Verification checklist

- [ ] **L1:** eligibility uses latest `RESOLVED` event `created_at` (Kathmandu year **N**)
- [ ] **L2:** ticket moved out of `RESOLVED`/`CLOSED` clears archive flags; new **N** from latest resolve
- [ ] **L3:** `CLOSED` ticket archives on same schedule as `RESOLVED`
- [ ] **L4:** SEAH uses `seah_years_before_archiving` when set, else global
- [ ] **L5:** second job run skips already-archived rows
- [ ] **L6:** case eligible 2028-01-02 archives on 2028-01-03 if job was down on Jan 2
- [ ] `years_before_archiving = 1`, resolved 2026-06-01 → eligible 2028-01-02, not before 2028-01-01
- [ ] Reopened ticket resets eligibility
- [ ] Archived ticket absent from My Queue
- [ ] Archived attachment: officer with admin can download; complainant cannot
- [ ] Upload to archived `grievance_id` returns 4xx
- [ ] Job idempotent on second run
- [ ] Settings change writes `admin_audit_log`
- [ ] `enabled: false` skips all writes

---

## 12) Implementation pointer

Agent prompt: [`docs/sprints/June5/agents/archiving-retention.md`](sprints/June5/agents/archiving-retention.md)
