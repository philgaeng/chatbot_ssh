# Queue Summary Tiles — Current Logic & Issues

**Status: BROKEN — needs a decision before fixing**
**File:** `channels/ticketing-ui/app/queue/page.tsx` (tile useMemo blocks, lines ~197–208)

---

## What the tiles currently calculate

All three tiles read from `actorTickets` — the list of tickets in the Actor tab,
fetched once on mount (`tab=actor, page_size=50`). They are pure frontend calculations
over the list items already loaded. No separate API call.

### Action Needed
```ts
actorTickets.filter(t => t.status_code === "OPEN" || t.unseen_event_count > 0).length
```
Counts tickets that are **OPEN status** (displayed as "New") **OR** have at least one
unread notification event for the current user.

### Due Today
```ts
actorTickets.filter(t => !t.sla_breached && t.step_started_at !== null).length
```
Counts tickets where **the SLA clock has been started** (officer acknowledged)
**AND** the DB `sla_breached` flag is false.

### Overdue
```ts
actorTickets.filter(t => t.sla_breached).length
```
Counts tickets where the DB `sla_breached` flag is `true`.

---

## Why the numbers are wrong

### Problem 1 — Due Today does not check the 24-hour window

The filter `!sla_breached && step_started_at !== null` means:
> "Any ticket I have acknowledged and that hasn't been flagged as breached yet."

This has **nothing to do with 24 hours**. It catches every acknowledged ticket
that is still within SLA — whether the deadline is tomorrow, next week, or next month.
That is why Due Today (4) can be larger than Action Needed (3).

`TicketListItem` does **not** include `resolution_time_days` or `sla_deadline_at`,
so the frontend cannot compute the actual deadline from the list alone.

### Problem 2 — Action Needed misses IN_PROGRESS and ESCALATED

`status_code === "OPEN"` only catches tickets in OPEN/New state.
Tickets that are IN_PROGRESS or ESCALATED and assigned to the officer
are skipped by the status check.
They are only counted if they happen to have an unread event.

### Problem 3 — Overdue uses a stale DB flag

The `sla_breached` column is only set to `true` when:
- The Celery SLA watchdog runs (every 15 min), **or**
- The officer manually escalates

The SLA countdown shown in each ticket row (`SlaCountdown` component) fetches
**live** from `GET /tickets/{id}/sla` — a real-time calculation.

So the row can show "Overdue -22h" while `sla_breached = false` in the DB,
causing the tile to show 1 overdue while 3 rows visually show red overdue times.

### Problem 4 — Logical impossibility

The correct relationship must hold:

```
Action Needed ≥ Due Today + Overdue
```

Because "Due Today" and "Overdue" should both be subsets of "Action Needed".
Currently: Action Needed (3) < Due Today (4) — **mathematically impossible**.

---

## What fields are available in TicketListItem today

```ts
ticket_id, grievance_id, grievance_summary,
status_code,         // "OPEN" | "IN_PROGRESS" | "ESCALATED" | "RESOLVED" | "CLOSED" | ...
priority,            // "NORMAL" | "HIGH" | "CRITICAL"
is_seah,
organization_id, location_code, project_code,
assigned_to_user_id,
sla_breached,        // DB flag — stale, updated by watchdog/escalation only
step_started_at,     // datetime SLA clock started (null = not acknowledged yet)
created_at,
unseen_event_count   // unseen notification events for current user on this ticket
```

**Not available in list:** `resolution_time_days`, `sla_deadline_at`, `response_time_hours`
(these require `GET /tickets/{id}/sla` per ticket — too expensive to call for 50 rows).

---

## Options for the fix

### Option A — Add `sla_deadline_at` to TicketListItem (recommended)

Backend change: in `list_tickets`, for each ticket, compute and include:
```python
sla_deadline_at = step_started_at + timedelta(days=step.resolution_time_days)
# null if step_started_at is None or step has no resolution_time_days
```

Frontend tiles become:
```ts
const now = Date.now();
const in24h = now + 24 * 60 * 60 * 1000;

overdue    = actorTickets.filter(t => t.sla_deadline_at && new Date(t.sla_deadline_at) < now).length
dueToday   = actorTickets.filter(t => t.sla_deadline_at && new Date(t.sla_deadline_at) >= now
                                   && new Date(t.sla_deadline_at) <= in24h).length
actionNeeded = actorTickets.filter(t => !["RESOLVED","CLOSED"].includes(t.status_code)).length
```

This gives the correct logical relationship:
- Action Needed = all active tickets (broadest)
- Due Today = active tickets, deadline within 24h (subset)
- Overdue = active tickets, deadline already passed (subset)
- Due Today + Overdue ≤ Action Needed ✓

**Cost:** One JOIN to workflow_steps in the list query per ticket (can be done as a single SQL join, not N+1).

---

### Option B — Server-side stats endpoint

Add `GET /api/v1/queue/stats` returning precomputed counts server-side:
```json
{
  "action_needed": 4,
  "due_today": 2,
  "overdue": 3
}
```

Frontend fetches this once on mount separately from the ticket list.
Cleanest separation of concerns; slightly more network overhead (one extra call).

---

### Option C — Redefine tiles without deadline data (quick fix, imprecise)

Keep existing data, redefine semantics to something the current data can actually express:

| Tile | New definition | Filter |
|------|---------------|--------|
| **Action Needed** | Active tickets not yet resolved/closed | `!["RESOLVED","CLOSED"].includes(status_code)` |
| **SLA Running** | Tickets I've acknowledged, SLA clock ticking | `step_started_at !== null && !sla_breached` |
| **Overdue** | SLA flagged as breached (refreshes every 15 min) | `sla_breached === true` |

Fast to implement, no backend change. But "Due Today" is gone — replaced by
"SLA Running" which is less useful as a warning.

---

## Recommended decision

**Option A** — add `sla_deadline_at` to TicketListItem. It fixes all three
problems at once, gives the tiles real meaning, and makes the relationship
Action Needed ≥ Due Today + Overdue guaranteed by construction.

Please review and mark your preferred approach so the fix can be implemented.
