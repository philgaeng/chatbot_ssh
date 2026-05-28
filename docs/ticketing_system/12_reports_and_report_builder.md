# Reports — operational dashboard, summary, pivot, and quarterly plan

**Status:** Overview + Pivot + Quarterly email **implemented** (2026-05-26). **Summary tab (ADB Project Director)** — specified §12, not yet built.  
**Related:** [00_ticketing_decisions.md](00_ticketing_decisions.md) (quarterly XLSX), [04_ticketing_schema.md](04_ticketing_schema.md), [11_ticket_resolution_and_case_summary.md](11_ticket_resolution_and_case_summary.md) (`resolution_category`), [Escalation_rules.md](Escalation_rules.md)  
**UI:** `channels/ticketing-ui/app/reports/page.tsx`  
**Backend:** `ticketing/services/report_rows.py`, `pivot_table.py`, `quarterly_assignments.py`, `quarterly_library.py`, `report_limits.py`  
**API:** `ticketing/api/routers/reports.py`

This document defines:

1. **Operational report (Overview tab)** — filtered lists in four sections (Resolved / High / Overdue / Others).
2. **Summary tab (§12)** — quarterly matrix + charts for ADB Project Director (planned).
3. **Pivot table tab** — Excel-style crosstab builder.
4. **Quarterly email tab** — saved report library + role assignments (max 3 per role per quarter).
5. **API and export** shapes for backend + UI.
6. **Open questions** — §8 (answered); §13 Summary **fully answered** (2026-05-26).

---

## 1. Goals

| Goal | Detail |
|------|--------|
| **Who** | Officers with report access (same **OfficerScope** as queue); quarterly plan + library: **`local_admin`** (and `super_admin`). |
| **What** | Review grievances, export XLSX, build pivots, plan quarterly emails, and (§12) executive summary for ADB. |
| **Scope** | All tickets matching filters — open, escalated, and resolved. |
| **Implemented** | Overview, Pivot, Quarterly email tab, report library, Celery dispatch per assignment, export rate limits. |
| **Not yet** | Summary XLSX/PDF export, async large exports. |

**Tab order (Reports page)**

| # | Tab | Audience | Status |
|---|-----|----------|--------|
| 1 | **Overview** | All report viewers | ✅ |
| 2 | **Summary** | ADB / senior oversight (§12) | 🔲 Planned |
| 3 | **Pivot table** | Analysts / admins | ✅ |
| 4 | **Quarterly email** | `local_admin` only | ✅ |

**Relationship to existing quarterly export**

- `GET /api/v1/reports/export` — four-sheet overview XLSX (backward compatible).
- `GET /api/v1/reports/query`, `POST /api/v1/reports/build` — operational + pivot.
- Quarterly **email** uses **assignments** from library (§2.5), not a single global template.

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
- Row click → **Resolved** section: case closure summary (`/tickets/{ticket_id}/closure`, §11). Other sections: ticket detail (`/tickets/{ticket_id}`).

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

**Rule:** up to **3 saved reports per role per calendar quarter** (`2026-Q1`). Enforced when `local_admin` saves an assignment — not a Celery throttle.

| Setting key | Purpose |
|-------------|---------|
| `quarterly_report_library` | Named report definitions `{ id, name, template }` (overview or pivot + filters) |
| `quarterly_report_assignments` | Scheduled sends: `{ id, quarter_key, role_key, name, template, active }` |
| `report_schedule` | `day_of_month` only (send on 5th of Jan/Apr/Jul/Oct) |
| `report_limits` | `max_reports_per_role_per_quarter` (default 3), `allowed_recipient_roles`, export caps (`super_admin` JSON) |

**Workflow (two steps)**

1. **Overview / Pivot** — **Save to report library** (name + template; no roles).
2. **Quarterly email tab** — table of scheduled reports (name → roles); **Add** picks library report + roles for a quarter; Settings tab shows same plan + send day.

**Celery:** for the completed quarter, **one email per assignment** to all officers with that role (one XLSX attachment each).

**API**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/reports/quarterly-plan?quarter_key=` | Plan table + limits |
| GET/POST/DELETE | `/api/v1/reports/quarterly-library` | Report definitions |
| POST/DELETE | `/api/v1/reports/quarterly-assignments` | Assign library report to role(s) |
| PUT | `/api/v1/reports/quarterly-schedule` | Send day of month |
| GET/PUT | `/api/v1/settings/report_limits` | Caps (`super_admin` only) |

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

## 5. Report builder (Pivot table tab)

### 5.1 UX concept

Reports page tabs (see §1): **Overview** → **Summary (§12)** → **Pivot table** → **Quarterly email**.

**Pivot table** — Excel / Google Sheets style pivot editor:

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
| Quarterly email | **Library** + **assignments**; max **3 reports per role per quarter**; `local_admin` manages; Celery one email per assignment |
| Pivot templates | Browser **localStorage** for personal presets; library in **DB** for quarterly |

---

## 12. Summary tab — ADB Project Director quarterly view (planned)

**Audience:** Same as Overview — **all report viewers** within **OfficerScope** (§13.1). SEAH tickets included when the viewer’s role can see SEAH (§13.1).

**Purpose:** One executive screen for the quarterly review the ADB Project Director expects: matrix counts by project × package, plus charts for complaints **closed during the selected period(s)**.

**Tab position:** Reports page tab **#2**, between **Overview** and **Pivot table** (§1).

### 12.1 Filters (Summary-specific toolbar)

Separate from Overview filters (Summary tab has its own controls).

| Filter | Control | Notes |
|--------|---------|-------|
| **Project** | Single-select dropdown | Required default: first visible project (KL Road). **Single-select only** (§13.2). |
| **Province** | Single-select dropdown | **Province level only** in v1 (no district/municipality picker). Filters tickets whose `location_code` is in that province or descendants. Applies to **matrix and charts** (§13.5 Q11). |
| **Time** | Multi-select **quarters** and/or **years** | Examples: `2025-Q4`, `2026-Q1`, `2026` (whole calendar year = four quarters). **Union** of all selected quarters + years (§13.2). Max **4** quarters in one view (§13.6). |
| **Package** | Multi-select dropdown | Optional; filters **both** matrix rows and charts when set (§13.5 Q11). When empty, all packages for the project. |

**Quarter key format:** `YYYY-Qn` (same as quarterly email plan).  
**Year selection:** expands to Q1–Q4 of that calendar year for aggregation.

**Apply:** Auto-apply on change (consistent with Overview §11).

### 12.2 Layout (split pane)

```
┌─────────────────────────────────────┬──────────────────────────┐
│  Summary matrix (table)             │  Charts (closed in period)│
│  Rows: project, package             │  Filter: project, package │
│  Columns: metric groups (§12.3)     │  §12.4                    │
└─────────────────────────────────────┴──────────────────────────┘
```

- **Left (~55%):** scrollable matrix; sticky header row for column groups.
- **Right (~45%):** stacked charts; scroll independently on narrow viewports (stack vertically on mobile).

### 12.3 Matrix — rows and columns

**Rows (hierarchical)**

| Row level | Source |
|-----------|--------|
| **Project** | `projects.name` — one row group per project in scope (typically one: KL Road) |
| **Package** | Child rows under project: `packages.name` or `(No package)` |

**Columns — two complaint populations**

The matrix must distinguish tickets that are **still open and overdue** during the selected quarter(s) from tickets **closed during** the selected quarter(s), including those filed in an earlier quarter.

#### Block A — Open pipeline (snapshot at end of each selected quarter)

| Column group | Definition |
|--------------|------------|
| **Overdue, still open** | Open at **quarter_end** with an active **overdue episode** covering that instant (§13 Q7/Q14 — `ticketing.ticket_overdue_episodes`). Count per row. |

If multiple quarters are selected, show **one sub-column per quarter** under this group (e.g. `2025-Q4`, `2026-Q1`), each using that quarter’s **last day 23:59:59 Nepal** as the snapshot time.

#### Block B — Closed during selected quarter(s)

For each selected quarter `Q`, include tickets where **`resolved_at` falls in Q** (Nepal calendar dates), regardless of `created_at`.

Sub-columns under **Closed in {Q}**:

| Sub-group | Definition |
|-----------|------------|
| **Closed on time** | Resolved in Q and **never** SLA-breached during the case lifetime (§13.3 Q6). UI shows a short **info tooltip** defining this. |
| **Closed overdue** | Resolved in Q and **ever** breached SLA before/during the case (§13.3 Q6). |

Under each of on-time / overdue, split by **max level reached** before resolution (highest `step_order` **before** the `RESOLVED` event — §13.4 Q9):

| Level bucket | Source |
|--------------|--------|
| **L1** | Max `workflow_steps.step_order` = 1 |
| **L2** | Max level = 2 |
| **L3** | Max level = 3 |
| **L4+** | Max level ≥ 4 (GRC / extra steps — §13.4 Q8: **all** level buckets) |

**No** resolution-category sub-columns in the matrix — category breakdown **only** in pie chart #5 (§13 Q17).

**Proposed column header hierarchy (example for one quarter)**

```
                    │ Closed 2026-Q1                          │ Open at end 2026-Q1
                    │ On time      │ Overdue                   │
                    │ L1 │ L2 │ L3 │ L1 │ L2 │ L3 │ … by resolution … │ Overdue open
Package A           │  2 │  1 │  0 │  0 │  1 │  0 │ …                 │  3
```

**Cell values:** integer counts (complaints). Empty = 0.

### 12.4 Charts (right panel)

**Population:** complaints **resolved** in the **union** of selected quarters/years (same as Block B), after project + optional package chart filters.

| # | Chart | Type | Series / slices |
|---|-------|------|-----------------|
| 1 | **Resolved by month** | Bar (stacked or grouped) | X = month, last **12 months rolling from today** (§13.5 Q10). **One series per package**. Y = count resolved. Same province/package filters as matrix. |
| 2 | **Overdue share** | Pie | On time vs closed overdue (lifetime breach rule §13.3). **Count + % on hover** (§13.5 Q12). |
| 3 | **Escalated share** | Pie | Ever escalated vs never. Count + % on hover. |
| 4 | **Max level reached** | Pie | L1 / L2 / L3 / L4+. Count + % on hover. |
| 5 | **Resolution by category** | Pie | Five standard categories. Count + % on hover. |

Charts 2–5 use the same filtered resolved set. Chart 1 uses the 12-month window (may include months outside selected quarters).

**Library:** lightweight chart component in UI (e.g. Recharts) — no server-side image generation in v1.

### 12.5 API (proposed)

**`GET /api/v1/reports/summary`**

Query params:

- `project_id` (required)
- `province_code` or `location_code` (province root)
- `quarter_keys` — comma-separated `2026-Q1,2026-Q2`
- `years` — comma-separated `2025,2026` (optional; merged with quarters)
- `chart_package_ids` — optional comma list for chart filter

Response:

```json
{
  "filters": { ... },
  "matrix": {
    "column_groups": [ /* nested header metadata */ ],
    "rows": [
      {
        "project_id": "...",
        "project_name": "KL Road",
        "package_id": "...",
        "package_name": "Lot 1",
        "cells": { "open_overdue_2026-Q1": 3, "closed_2026-Q1_on_time_L1_cat_x": 2, ... }
      }
    ]
  },
  "charts": {
    "resolved_by_month": [ { "month": "2025-06", "package_id": "...", "count": 4 } ],
    "pies": {
      "overdue_vs_ontime": [ { "label": "On time", "value": 12 }, ... ],
      "escalated": [ ... ],
      "max_level": [ ... ],
      "resolution_category": [ ... ]
    }
  }
}
```

**Export (later):** `GET /api/v1/reports/summary/export?format=xlsx` — matrix sheet + chart data sheet; PDF optional post-demo.

### 12.6 Backend module (proposed)

- `ticketing/services/report_summary.py` — quarter date ranges, snapshot overdue logic, max-level-at-resolve, aggregation for matrix + chart payloads.
- Reuse row loading from `report_rows.py` where possible; **open overdue at quarter-end** reads `ticket_overdue_episodes` (§13 Q7/Q14, §14).

### 12.7 Access and limits

- **View:** same roles as Overview (§8.1, §13.1).
- **Export:** XLSX matrix + chart data; row cap in `report_limits` (same pattern as Overview — default **100**, super_admin via Advanced JSON §13.6 Q15).
- **Quarterly email:** Summary may be saved to report library as `kind: summary` (§13.7 Q16).

---

## 13. Summary tab — product answers

Recorded **2026-05-26**. **All Summary questions locked** — build may proceed (Summary UI after §14 schema + writers land, or in parallel with migration).

### 13.1 Access — locked

| # | Question | Answer |
|---|----------|--------|
| 1 | Who can open Summary? | **All report viewers** (same OfficerScope as Overview). |
| 2 | Include SEAH tickets? | **Yes**, when the viewer’s role can see SEAH tickets. |

### 13.2 Filters — locked

| # | Question | Answer |
|---|----------|--------|
| 3 | Project selector | **Single-select** only. |
| 4 | Location selector | **Province** only in v1 (no district/municipality dropdown). |
| 5 | Years + quarters together | **Union** of all selected periods. |
| 13 | Max quarters at once | **4**. |

### 13.3 Closed complaints — locked

| # | Question | Answer |
|---|----------|--------|
| 6 | “Closed on time” means… | **Never** SLA-breached during the **entire case** (any auto-escalation from SLA, `sla_breached` ever true, or `SLA_BREACH_*` event before resolve). |
| 6b | UI | Show an **info icon / tooltip** on the matrix: *“On time = resolved without any SLA breach during the case.”* |
| 9 | Max level for splits | Highest `step_order` reached **before** the `RESOLVED` event (resolve step excluded). |

**Implementation note (Q6):** **Closed overdue** if any row in `ticketing.ticket_overdue_episodes` for the ticket (or legacy `SLA_BREACH_*` / `SLA_AUTO` events before episodes exist). **Closed on time** only when no episode ended before `resolved_at`.

### 13.4 Max level buckets — locked

| # | Question | Answer |
|---|----------|--------|
| 8 | Level columns | **L1, L2, L3, and L4+** (all buckets in KL + GRC workflow). |

### 13.5 Charts — locked

| # | Question | Answer |
|---|----------|--------|
| 10 | 12-month bar chart anchor | **Rolling from today** (not from latest selected quarter end). |
| 11 | Province / package filters | Apply to **matrix and all charts**. |
| 12 | Pie labels | Slice labels show **count**; **percentage on hover** (tooltip). |

### 13.6 Export and settings — locked

| # | Question | Answer |
|---|----------|--------|
| 15 | Summary export cap | **Yes** — same mechanism as Overview (`report_limits`, default **100** rows; super_admin edits Advanced JSON). |

### 13.7 Quarterly email — locked

| # | Question | Answer |
|---|----------|--------|
| 16 | Quarterly library | **Yes** — add `kind: summary` to report library + assignments (same slot rules as overview/pivot). |

### 13.8 Open overdue — locked (Q7 + Q14)

| # | Question | Answer |
|---|----------|--------|
| 7 | How to know “open and overdue at quarter-end”? | **Persist overdue episodes at breach time** (§14) — not event replay, not today’s `sla_breached` alone. |
| 14 | Accuracy | **Accurate** from stored episodes; optional one-time **backfill** from events for demo tickets missing episodes. |

**Product rationale (2026-05-26):** When SLA is missed, capture immediately: overdue flag, **stage** (`workflow_step_id` / `step_order`), **officer in charge** (`assigned_to_user_id`), and **days overdue** (increments until escalate, step change, or resolve). Escalation must **not** erase the fact the ticket was overdue at the previous level — today `sla_breached` resets on manual escalate and `step_started_at` clears on any escalate, so ticket-row-only tracking loses history.

### 13.9 Matrix categories — locked (Q17)

| # | Question | Answer |
|---|----------|--------|
| 17 | Resolution category columns in matrix? | **`pies only`** — matrix shows level totals (L1–L4+); resolution category breakdown **only** in pie chart #5. |

---

## 13.10 Locked decisions table (build from this)

| Topic | Decision |
|-------|----------|
| Access | All report viewers; SEAH when role allows |
| Project | Single-select |
| Province | Province only; applies to matrix + charts |
| Period | Union; max 4 quarters |
| Closed on time | No overdue **episode** before resolve; tooltip in UI |
| Closed overdue | ≥1 overdue episode (or legacy SLA event) before resolve |
| Max level | L1–L3 + L4+; highest step **before** resolve |
| Open overdue snapshot | `ticket_overdue_episodes` covering `quarter_end` (§14) |
| Queue mirror | `tickets.current_overdue_episode_id`; days on read from `started_at` |
| `days_overdue` column | Final value at `ended_at` only; watchdog does not increment |
| Category columns | **Pies only** (not in matrix) |
| Chart window | 12 months rolling from today |
| Pies | Count + % on hover |
| Export cap | `report_limits` (default 100) |
| Quarterly library | `kind: summary` supported |

---

## 14. SLA overdue episodes (platform — required for Summary + audit)

**Status:** **Implemented** (2026-05-26). Migration `x9y1z3a5`; writers in `overdue_episodes.py`, `escalation.py`, `tickets.py`. Schema detail in [04_ticketing_schema.md](04_ticketing_schema.md) §2.1a.

### 14.1 Why not only `tickets.sla_breached`?

| Today | Problem |
|-------|---------|
| `sla_breached` on escalate | Set `True` only for `SLA_AUTO`; **manual** escalate sets `False` — breach can disappear from the row. |
| `step_started_at` cleared on escalate | SLA clock resets; **no row-level history** of overdue at L1 when case is now at L2. |
| Summary quarter-end | Cannot answer “how many open + overdue on 31 Mar?” from current columns. |

### 14.2 Table: `ticketing.ticket_overdue_episodes`

Append-only **episode** per overdue stint at a workflow step. **Source of truth** for Summary, “closed on time”, and audit.

| Column | Type | Notes |
|--------|------|-------|
| `episode_id` | UUID PK | |
| `ticket_id` | FK → `ticketing.tickets` | |
| `workflow_step_id` | UUID | Step where SLA was missed |
| `step_order` | int | Denormalized for L1/L2/L3/L4+ reports |
| `assigned_to_user_id` | string | Officer in charge **when breach started** |
| `assigned_role_id` | UUID nullable | Role at breach |
| `started_at` | timestamptz | First moment overdue (deadline crossed or `SLA_AUTO` / watchdog) |
| `ended_at` | timestamptz nullable | Set on escalate, resolve, close, or ACK that starts new step clock |
| `end_reason` | enum string | `ESCALATED` \| `RESOLVED` \| `CLOSED` \| `ACKNOWLEDGED` \| `STEP_CHANGED` |
| `days_overdue` | int nullable | **Final value only** — set when `ended_at` is written (calendar days `started_at` → `ended_at`). **NULL** while episode is open. |
| `triggered_by` | string | `SLA_WATCHDOG` \| `SLA_AUTO_ESCALATE` \| `MANUAL_DETECT` (future) |

Index: `(ticket_id, ended_at)` for open-episode lookups; `(ticket_id, started_at)` for Summary quarter overlap.

### 14.2.1 Ticket mirror: `ticketing.tickets.current_overdue_episode_id`

**Locked:** nullable FK → `ticket_overdue_episodes.episode_id`.

| Rule | Behavior |
|------|----------|
| Set | Same DB transaction as `INSERT` open episode (watchdog / breach detect). |
| Clear | Same transaction as `ended_at` on that episode (escalate, resolve, close, ACK). |
| Meaning | Points at the **open** episode, if any. `NULL` = not overdue now. |
| Queue / API | **Overdue now** = `current_overdue_episode_id IS NOT NULL`. **Days overdue (display)** = calendar days from linked `started_at` to now — **computed on read**, not stored on `tickets`. |
| Reports / Summary | Use **episodes**, not this FK (historical quarters need `ended_at` / overlap queries). |

Do **not** add `overdue_days_current` on `tickets`. Do **not** increment `days_overdue` on the watchdog while the episode is open.

**`sla_breached` (legacy):** Keep column for now; new code should treat **open episode** as authoritative for overdue UI. Long-term: set `sla_breached` in the same transaction as open/close episode, or deprecate for display.

### 14.2.2 Writers (single code path)

1. **SLA watchdog** (`ticketing/engine/escalation.py`) — on breach: `INSERT` episode if none open for this ticket+step; set `tickets.current_overdue_episode_id`. **Do not** update `days_overdue` each run.
2. **Escalate** (auto or manual) — set `ended_at`, `end_reason=ESCALATED`, **`days_overdue`** = calendar days for that stint; clear `current_overdue_episode_id`; open new episode only if still overdue at new step after ACK.
3. **Resolve / close** — end open episode (final `days_overdue`), clear FK.
4. **Acknowledge** at new step — end episode if SLA clock restarts; clear FK.

**Optional later:** periodic refresh of `days_overdue` on **open** episodes **only** if product needs `ORDER BY days_overdue` in SQL at large scale; not required for v1.

### 14.2.3 Display rules (locked)

| Surface | Rule |
|---------|------|
| My Queue / Overdue tab | Filter via `current_overdue_episode_id IS NOT NULL` (or join episode for `started_at`). |
| SLA badge / countdown | Existing SLA deadline UI unchanged; overdue **stint** label uses episode `started_at`. |
| Ticket list API | Include `overdue_days_display` = computed from open episode `started_at` (Nepal calendar days or UTC per existing SLA convention). |
| Summary / export | Episodes table only. |

### 14.3 Queries

| Use case | Query |
|----------|--------|
| Summary — open at end of Q | Ticket open at `quarter_end` AND ∃ episode with `started_at ≤ quarter_end` AND (`ended_at` IS NULL OR `ended_at > quarter_end`) |
| Closed on time | No episode with `started_at < resolved_at` |
| Closed overdue | Any episode before resolve |
| Officer accountability | Filter episodes by `assigned_to_user_id` + `step_order` |

### 14.4 Backfill

One-off script: from `ticket_events` (`ESCALATED`/`SLA_BREACH_*`, payloads with `triggered_by`) seed episodes for demo tickets; mark `source=backfill` in payload JSON if needed.

### 14.5 Implementation order

1. Alembic: `ticket_overdue_episodes` + `tickets.current_overdue_episode_id`  
2. SQLAlchemy models + writers (watchdog, escalate, resolve, ACK)  
3. Ticket list / queue API: `overdue_days_display` from episode `started_at`  
4. Backfill demo tickets from events  
5. `report_summary.py` + Summary UI  
6. Optional: episode rows on case timeline (read-only)

---

## 10. Document history

| Date | Change |
|------|--------|
| 2026-05-25 | Initial spec from product request (operational sections + report builder). |
| 2026-05-25 | Product answers in §8; Overview + pivot backend/UI implemented. |
| 2026-05-26 | Quarterly email: library + assignments tab; report_limits; API table §2.5. |
| 2026-05-26 | **Summary tab (§12)** specified; §13 complete; §14 overdue episodes; Q17 pies only. |
| 2026-05-26 | §14 locked: `current_overdue_episode_id` mirror; `days_overdue` at end only; display days computed on read. |
