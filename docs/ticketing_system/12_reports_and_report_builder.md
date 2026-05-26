# Reports — operational dashboard and report builder

**Status:** Implemented (2026-05-25) — see §11 locked decisions  
**Related:** [00_ticketing_decisions.md](00_ticketing_decisions.md) (quarterly XLSX), [04_ticketing_schema.md](04_ticketing_schema.md), [11_ticket_resolution_and_case_summary.md](11_ticket_resolution_and_case_summary.md) (`resolution_category`), [Escalation_rules.md](Escalation_rules.md)  
**UI:** `channels/ticketing-ui/app/reports/page.tsx`  
**API today:** `GET /api/v1/reports/export` (`ticketing/api/routers/reports.py`) — date range + optional `organization_id`, fixed columns, XLSX only.

This document defines:

1. **Operational report** — filtered list of **all complaints** in scope, split into four sections (Resolved / High / Overdue / Others).
2. **Report builder** — user-selected columns (pivot-table *feel*, not full OLAP).
3. **API and export** shapes for backend + UI.
4. **Open questions** — must be answered before implementation (§8).

---

## 1. Goals

| Goal | Detail |
|------|--------|
| **Who** | Officers with report access (see §8.1); admins and observer/senior roles at minimum. |
| **What** | One screen to **review** grievances in a period and **export** the same dataset (XLSX; CSV optional). |
| **Scope** | All tickets matching filters — **open, escalated, and resolved** (not queue-only “active”). |
| **Not in v1** | Scheduled email (stays Celery quarterly task), cross-ticket aggregations/charts, saved report templates in DB (optional v1.1). |

**Relationship to existing quarterly export**

- Keep `GET /api/v1/reports/export` for backward-compatible **flat quarterly** download (can widen columns later).
- Add **`GET /api/v1/reports/query`** (JSON) and **`POST /api/v1/reports/build`** (custom columns) as described below.

---

## 2. Reports page — layout

### 2.1 Filters (toolbar)

| Filter | Control | API param | Notes |
|--------|---------|-----------|-------|
| **Period** | Presets + custom range | `date_from`, `date_to` | Presets: This month, Last month, This quarter, Last quarter, YTD, Custom. **Default:** current calendar quarter (matches today’s Reports page). |
| **Project** | Multi-select | `project_id[]` | From `GET /api/v1/projects` (scoped to user org where applicable). |
| **Package** | Multi-select (depends on project) | `package_id[]` | From `GET /api/v1/projects/{id}/packages`. Empty = all packages in selected projects. |
| **Location** | Multi-select tree or flat list | `location_code[]` | From existing locations API; optional “include child locations” (§8.3). |

**Not in v1 filter bar (unless decided in §8):** organization (use officer scope instead), workflow, SEAH instance toggle (see §8.2), officer assignee.

**Apply behaviour:** “Apply filters” refetches all sections; changing period does not auto-apply until Apply (or debounced auto-apply — product choice §8.4).

### 2.2 Summary strip (optional, recommended)

Above the four sections, show **counts** for the filtered population:

- Total complaints  
- Resolved · High · Overdue · Others (same rules as §3)  
- Optional: % resolved, median days open  

Counts must use the **same bucket rules** as the tables so officers trust the numbers.

### 2.3 Four sections (stacked tables)

Each section is a **collapsible card** with:

- Title + count badge  
- Sortable table (default sort: complaint date descending)  
- “Export this section” (XLSX sheet or filtered CSV)  
- Row click → ticket detail (`/tickets/{ticket_id}`)

| Section | Intended meaning (proposed) | Row inclusion rule |
|---------|----------------------------|-------------------|
| **Resolved** | Closed grievances in period | `status_code IN ('RESOLVED', 'CLOSED')` **and** complaint date in period (§8.5). |
| **High** | Priority or SLA stress (active pipeline) | `priority IN ('HIGH', 'CRITICAL')` **OR** `sla_breached = true` (aligns with queue `high_priority` tab). **Exclude** rows already in Resolved unless §8.6 says otherwise. |
| **Overdue** | Past SLA deadline (active pipeline) | `sla_deadline_at < now()` **OR** `sla_breached = true` (aligns with queue “Overdue” tile: deadline in the past). **Exclude** Resolved unless §8.6. |
| **Others** | Remaining complaints in filtered set | In filtered population, **not** placed in Resolved, High, or Overdue (mutually exclusive buckets — §8.6). |

**Suggested extra columns** (beyond §4 core fields) for scanability:

| Column | Source |
|--------|--------|
| Reference | `grievance_id` |
| Summary (truncated) | `grievance_summary` |
| Project / Package | `projects.name`, `packages.label` via `project_id`, `package_id` |
| Location | `grievance_location` or location translation |
| Assignee | `assigned_to_user_id` → display name from roster |
| SLA countdown | computed `sla_status` (same as queue) |

### 2.4 Page-level actions

- **Export all (XLSX)** — one workbook, **four sheets** named Resolved / High / Overdue / Others, same columns as on screen.  
- **Open report builder** — navigates to tab or drawer §5.  
- Link to **Settings → Report schedule** (existing quarterly email copy).

### 2.5 Quarterly report plan (implemented)

**Rule:** up to **3 saved reports per role per calendar quarter** (`2026-Q1`). Enforced when `local_admin` saves — not a Celery throttle.

| Setting key | Purpose |
|-------------|---------|
| `quarterly_report_assignments` | List of `{ id, quarter_key, role_key, name, template, active }` |
| `report_schedule` | `day_of_month` only (send on 5th of Jan/Apr/Jul/Oct) |
| `report_limits` | `max_reports_per_role_per_quarter` (default 3), `allowed_recipient_roles`, export caps |

**Workflow**

1. **Reports** — build overview or pivot; **Save for quarterly email** → pick quarter + one or more roles (each role uses one slot).
2. **Settings → Quarterly reports** — review plan per role (`2/3`), delete slots, set send day.
3. **Settings → Advanced (JSON)** (`super_admin`) — change `max_reports_per_role_per_quarter` if needed.
4. **Celery** — for the completed quarter, sends **one email per assignment** to all officers with that role (same report to multiple roles = separate saves / separate emails per role).

API: `GET /api/v1/reports/quarterly-plan`, `POST /api/v1/reports/quarterly-assignments`, `DELETE …/{id}`, `PUT /api/v1/reports/quarterly-schedule`.

---

## 3. Bucket assignment (overlapping sections — locked)

A ticket may appear in **more than one** section. Tags:

```
if status in (RESOLVED, CLOSED) and created_at in period:
    tags += resolved
if status not in (RESOLVED, CLOSED):
    if overdue (sla_breached or deadline < now):
        tags += overdue
    if priority in (HIGH, CRITICAL) or is_seah or overdue:
        tags += high
    if not high and not overdue:
        tags += other
```

**Rationale:** Resolved is separate; active **High** includes SEAH and overdue cases; **Overdue** remains its own section for SLA focus (overlap with High allowed per §8.5 Q13).

---

## 4. Standard row fields (operational report)

These are the **default columns** for all four sections and the **palette** for the report builder.

| Field key | Label | Type | Computation / source |
|-----------|-------|------|----------------------|
| `complaint_date` | Date of complaint | date | `tickets.created_at` (date part, UTC or org TZ — §8.7) |
| `grievance_id` | Reference no. | string | `tickets.grievance_id` |
| `high_yn` | High (Y/N) | enum Y/N | Y if `priority IN ('HIGH','CRITICAL')` |
| `escalated_yn` | Escalated (Y/N) | enum Y/N | Y if **ever** `event_type = 'ESCALATED'` OR `status_code = 'ESCALATED'` at query time — §8.8 |
| `overdue_yn` | Overdue (Y/N) | enum Y/N | Y if `sla_breached` OR `sla_deadline_at < now` (for open tickets); for resolved, Y if **ever** breached at resolve — §8.8 |
| `stage` | Stage | string | Current step **display name** (`workflow_steps.name` or level label), e.g. “L1 — Site Safeguards” |
| `stage_level` | Level | string | Optional: step `level_order` or `step_key` |
| `complaint_category` | Complaint category | string | `grievance_categories` (cached text; may be comma-separated) |
| `days_in_stage` | Days in current stage | int | `floor(now - step_started_at)` days; if null, `floor(now - created_at)` — §8.9 |
| `total_days` | Total days | int | Open: `floor(now - created_at)`; Resolved: `floor(resolved_at - created_at)` — §8.9 |
| `resolution_category` | Resolution category | string | From latest `RESOLVED` / resolution record `payload.resolution_category` → label via `resolution_category_label()`; blank if not resolved |
| `status_code` | Status | string | `tickets.status_code` |
| `priority` | Priority | string | `tickets.priority` |
| `project_name` | Project | string | Join `ticketing.projects` |
| `package_label` | Package | string | Join `ticketing.packages` |
| `location_display` | Location | string | Translation / `grievance_location` |
| `organization_id` | Organization | string | `tickets.organization_id` |
| `is_seah` | Instance | string | `Standard` / `SEAH` |
| `sla_breached` | SLA breached (Y/N) | enum Y/N | `tickets.sla_breached` |
| `assigned_officer` | Assigned officer | string | Roster display name |
| `grievance_summary` | Summary | string | Truncated for UI (e.g. 120 chars), full in export |

**Period filter semantics (proposed default):** include tickets whose **`created_at`** falls in `[date_from, date_to]` inclusive. Option to filter by **resolved date** for Resolved section only — §8.5.

---

## 5. Report builder (pivot table)

### 5.1 UX concept

Two modes on the Reports page (tabs):

1. **Overview** — §2 four-section tables.  
2. **Pivot table** — Excel / Google Sheets style pivot editor:

| Zone | Purpose |
|------|---------|
| **Filters** | Dimension + allowed values (comma-separated) — limits rows before pivot |
| **Rows** | Category fields down the left (e.g. Project, Stage) |
| **Columns** | Category fields across the top (e.g. Complaint category) |
| **Values** | Measure + aggregation: **Count**, **Sum**, **Average**, **Max**, **Min** |

**Dimensions** (categories): project, package, location, stage, status, priority, High/Escalated/Overdue Y/N, SEAH instance, etc.

**Measures** (numeric): `total_days`, `days_in_stage`. **Count** uses `ticket_id` (number of complaints).

Preview renders a crosstab: row labels × column groups × each value spec. A **Grand total** row is appended when row dimensions are set.

### 5.3 Builder API

**`POST /api/v1/reports/build`**

Request body (pivot):

```json
{
  "date_from": "2026-01-01",
  "date_to": "2026-03-31",
  "pivot": {
    "rows": ["project_name"],
    "columns": ["complaint_category"],
    "values": [
      { "field": "ticket_id", "agg": "count" },
      { "field": "total_days", "agg": "avg" }
    ],
    "filters": { "status_code": ["OPEN", "ESCALATED"] }
  },
  "format": "json"
}
```

- `format`: `json` (preview) | `xlsx` (download).  
- Response `json`: `{ "columns": [...], "rows": [ { ... } ], "total": N, "grouped": bool }`.  
- Same auth, SEAH visibility, and officer scope rules as `GET /tickets`.

---

## 6. API — operational query

**`GET /api/v1/reports/query`**

Query params: same filters as §2.1 + optional `bucket=resolved|high|overdue|other` (omit = all buckets in one payload).

Response:

```json
{
  "filters": { "date_from": "...", "date_to": "...", "project_ids": [], ... },
  "summary": {
    "total": 42,
    "resolved": 10,
    "high": 5,
    "overdue": 3,
    "other": 24
  },
  "sections": {
    "resolved": { "items": [ /* ReportRow */ ], "total": 10 },
    "high": { "items": [ ... ], "total": 5 },
    "overdue": { "items": [ ... ], "total": 3 },
    "other": { "items": [ ... ], "total": 24 }
  }
}
```

`ReportRow` — flat dict keyed by §4 field keys; server-side computation in `ticketing/services/report_rows.py` (new module) to avoid duplicating logic in router and Celery.

**Performance:** single SQL query with joins (projects, packages, steps, optional event subquery for `escalated_yn`); bucket assignment in Python; paginate **per section** if any section > 500 rows (§8.10).

---

## 7. Implementation plan (ordered)

| Step | Work |
|------|------|
| 1 | Answer §8 questions; lock bucket + period rules. |
| 2 | `report_rows.py` + `GET /reports/query` + extend export to 4-sheet XLSX. |
| 3 | Rewrite `reports/page.tsx`: filters (projects/packages/locations), four sections, export. |
| 4 | Builder tab + `POST /reports/build` (json + xlsx). |
| 5 | Help page + `PROGRESS.md` / `TODO.md` updates. |

**Frontend dependencies:** reuse `listProjects`, `listPackages`, `listLocations` from `lib/api.ts`; add `queryReport`, `buildReport`.

**Backend dependencies:** resolution labels exist; `escalated_yn` may need `EXISTS` on `ticket_events`; resolved timestamp from latest `RESOLVED` event.

---

## 8. Open questions (need product answers)

Please answer by number (copy/paste is fine). Implementation should not start until **8.1, 8.5, 8.6, 8.8** are decided.

### 8.1 Access control  2

1. Which roles can open **Reports**? All logged-in officers, or only `super_admin`, `local_admin`, observers (`adb_*`), and GRC — exclude L1 field officers?  
2. Should report data respect **the same jurisdiction scopes** as the queue (`OfficerScope`), or can admins see **all org tickets** when filters are empty?  
3. **SEAH:** include SEAH tickets only for `seah_*` roles (mirror queue), with a explicit **“Include SEAH cases”** checkbox for dual-role admins?

### 8.2 Period and population  4,5 YES, 6 NO

4. Filter tickets by **`created_at` only**, or also offer **“Resolved in period”** for the Resolved section (resolved event date)?  
5. Include tickets **created before** the period but **still open** during the period (snapshot / “open as of end date”), or strictly **created in period** only?  
6. Include **soft-deleted** tickets? (Proposed: **no**.) NO

### 8.3 Locations and packages 7. yes. 8, yes, 9. ok

7. If a **parent location** is selected, include tickets in **child** locations automatically?  
8. If **no project** is selected, default to **all projects the user can see** or require at least one project?  
9. Tickets with **null `package_id`** (walk-in / phone): always listed under “(No package)”?

### 8.4 UX behaviour 10. auto apply, 11 - 25, 12- scroll

10. **Auto-apply** filters on change, or **Apply** button only?  
11. Default **page size** per section: 25, 50, or 100?  
12. Show **four sections on one scroll** or **tabs** per section?

### 8.5 Bucket rules (critical) - 13 overlap for high and overdue, 14 yes

13. Confirm **mutually exclusive** buckets per §3, or allow overlap (e.g. High + Overdue)?  
14. For **Resolved** section: include only tickets resolved in period, or **any ticket created in period** that is now resolved (even if resolved after period)?  
15. **Others** — should it include **resolved** tickets that don’t fit Resolved section timing (if 14 is split)?

### 8.6 “High” definition High is high priority + overdue + seah

16. Is **High** strictly `priority HIGH/CRITICAL`, or also **SENSITIVE** priority / SEAH flag? 
17. Should **sla_breached** put a ticket in **Overdue** only, or also count as **High** (current §3 puts breach in Overdue first)?

### 8.7–8.9 Field semantics - Country timezone in that case Nepal

18. **Timezone** for dates and day counts: UTC, Nepal (Asia/Kathmandu), or user preference?  
19. **`escalated_yn`:** ever escalated in lifetime, currently `ESCALATED` status, or escalated **during filtered period**?  ever escalated
20. **`overdue_yn`:** current SLA state only, or **ever** overdue before resolve?  overdue at once
21. **`days_in_stage`:** calendar days or **business days** (excluding weekends/holidays)?  calendar
22. **`stage`:** step **name**, **level number** (L1–L4), or **role** assigned at step? step name

### 8.10 Report builder

23. Is **group-by + count** enough for v1, or do you need **averages** (e.g. avg `total_days`) in the first release?  we need basic functions as well
24. Should builders **save/share templates** (named presets), or stateless each session?  yes
25. Max export row count (e.g. **5,000**) before async email job? ok - 100

### 8.11 Categories and resolution

26. **`complaint_category`:** use raw `grievance_categories` string, or split/normalize to first category code?  we need to normalize
27. If resolution record spec ([11](11_ticket_resolution_and_case_summary.md)) is **not merged yet**, show `resolution_category` from `RESOLVED` event payload only?

### 8.12 Quarterly export

28. Replace existing single-sheet export with **four-sheet** layout, or keep quarterly flat and add new endpoints only?  four sheet layout 
29. Should quarterly **scheduled** email use the same column set as §4? yes

---

## 9. Suggested defaults (if you want to defer decisions)

Use these when answers are silent:

| Topic | Default |
|-------|---------|
| Access | Same scope as queue; admins see all in org; SEAH gated by role |
| Period | `created_at` in range; all statuses |
| Buckets | Mutually exclusive per §3 |
| High | `HIGH` / `CRITICAL` priority only |
| Escalated | Ever had `ESCALATED` event |
| Overdue | Current: `sla_breached` OR past `sla_deadline_at` |
| Days | Calendar days, UTC |
| Builder v1 | Flat table + optional `group_by` with count |
| Export cap | 2,000 rows synchronous; above → “narrow filters” message |

---

## 11. Locked product decisions (answers recorded in §8)

| Topic | Decision |
|-------|----------|
| Access | Same **OfficerScope** as queue (§8.1 → Q2) |
| Period | **created_at** in range **or** still open if created before period (Q4–5 YES); soft-deleted excluded (Q6 NO) |
| Resolved section | Created in period and status RESOLVED/CLOSED (Q14 yes) |
| Sections | **Overlap** allowed: High and Overdue both list same ticket when applicable (Q13) |
| High | HIGH/CRITICAL **or** SEAH **or** overdue (§8.6) |
| Locations | Parent selection includes **descendants** (Q7) |
| Projects | Empty selection = **all visible** projects (Q8) |
| Packages | Null package → **(No package)** (Q9) |
| UX | **Auto-apply** filters; **page size 100**; **one scroll** for four sections (Q10–12) |
| Timezone | **Asia/Kathmandu** for dates and day counts (Q18) |
| escalated_yn | **Ever** escalated (Q19) |
| overdue_yn | Current breach / past deadline (Q20 “at once” → active overdue flag) |
| Days | **Calendar** days (Q21) |
| Stage | Step **display name** (Q22) |
| Builder | **count**, **avg/sum total_days**; templates saved in **browser localStorage** (Q23–24) |
| Export cap | **100 rows** per sheet/export (Q25) |
| Categories | **Normalized** first token (Q26) |
| Quarterly | **Four-sheet** XLSX, same §4 columns (Q28–29) |

---

## 10. Document history

| Date | Change |
|------|--------|
| 2026-05-25 | Initial spec from product request (operational sections + report builder). |
| 2026-05-25 | Product answers in §8; backend + UI implemented. |
