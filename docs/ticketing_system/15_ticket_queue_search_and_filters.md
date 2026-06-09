# Ticket queue — search and filters (officer UI)

> **Status:** Implemented June 2026  
> **Screens:** Desktop `/queue` (primary), `/tickets` (all-tickets list)  
> **Audience:** Supervising officers (Supervisor tab, All Tickets) and field officers who need to narrow a long list

---

## 1) Problem

The queue shows role-tier tabs (Actor, Supervisor, High Priority, All Tickets) and three summary tiles (Action Needed, Due Today, Overdue) on the **Actor** tab only. Supervisors managing many cases cannot:

- Find a ticket by grievance ID, summary snippet, or assignee email
- Restrict by priority, overdue SLA, date filed, project, or package
- Share a consistent filter pattern with the standalone **All Tickets** page

Client-side search on `/tickets` only filtered the first 100 rows already loaded and ignored structured filters.

---

## 2) Goals

| Goal | Approach |
|------|----------|
| Fast lookup for supervisors | Server-side `q` search on grievance ID, summary, assignee |
| Operational triage | Filters: priority, overdue (SLA breached), date filed range, project, package |
| Same UX on queue + all-tickets | Shared `TicketListFiltersBar` component |
| Respect role scope | All filters apply **after** existing tab + jurisdiction gates in `GET /api/v1/tickets` |
| Mobile | v1 desktop only; mobile queue unchanged (follow-up) |

---

## 3) UI layout (desktop `/queue`)

Below the **summary tiles** and above the role tabs:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ [ Search…………………… ] [Priority▼] [SLA▼] [Project▼] [Package▼] [Clear]          │
│ Filed  [Today] [2d] [7d] [30d] [This month] [Custom…]                        │
└──────────────────────────────────────────────────────────────────────────────┘
  (Custom expands: [from] to [to] — click active chip again to clear)
```

- **Search:** debounced 300 ms; triggers API refetch
- **Priority:** placeholder label · NORMAL · HIGH · CRITICAL
- **SLA:** Overdue · On track → `sla_breached` query param
- **Filed chips:** Today · 2d · 7d · 30d · This month (toggle off on second click) · **Custom…** (from/to pickers)
- **Project / Package:** `project_code` + `package_id` (package enabled after project)
- **Clear:** resets all fields; does not change active tab or tile filter

Active filters show compact chips under the row.

Summary tiles and tab behaviour are **unchanged**. Tile filters (Action Needed / Due Today / Overdue) still apply client-side on the current result set.

---

## 4) API (`GET /api/v1/tickets`)

New optional query parameters (in addition to existing `tab`, `status_code`, `project_code`, etc.):

| Param | Type | Description |
|-------|------|-------------|
| `q` | string | Case-insensitive substring match on `grievance_id`, `grievance_summary`, `assigned_to_user_id` |
| `priority` | string | Exact match: `NORMAL`, `HIGH`, `CRITICAL` |
| `created_from` | date (`YYYY-MM-DD`) | `created_at >= start of day UTC` |
| `created_to` | date | `created_at < start of next day UTC` |
| `package_id` | UUID string | Match `ticketing.tickets.package_id` |

Existing `sla_breached`, `project_code`, `organization_id`, `location_code` remain available.

Pagination unchanged (`page`, `page_size` max 100).

---

## 5) Frontend modules

| Piece | Location |
|-------|----------|
| Filter bar UI | `channels/ticketing-ui/components/tickets/TicketListFiltersBar.tsx` |
| API client | `channels/ticketing-ui/lib/api.ts` — `TicketFilters` + `listTickets()` |
| Queue page | `channels/ticketing-ui/app/queue/page.tsx` |
| All tickets | `channels/ticketing-ui/app/tickets/page.tsx` |

---

## 6) Out of scope (v1)

- Saved filter presets / URL query sync
- Mobile `/m/queue` filter bar
- Full-text search on event notes or complainant PII
- Export filtered list from queue (use Reports)

---

## 7) Verification

1. Supervisor → **All Tickets** → search partial grievance ID → matching row only  
2. Priority **HIGH** + **Overdue** → subset respects both  
3. **Filed from** last 7 days → excludes older tickets  
4. Select project **KL_ROAD** → package dropdown populates → filter by package  
5. **Clear filters** restores full tab list  
6. API: `GET /api/v1/tickets?q=dust&priority=HIGH&sla_breached=true` returns expected count
