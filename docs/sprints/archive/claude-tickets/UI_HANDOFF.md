# UI Session Handoff — GRM Ticketing Frontend
> Self-contained brief for a Claude Code session focused on frontend UI work.
> No prior context needed. Read this file entirely before touching any code.

---

## What this project is

A Grievance Redress Mechanism (GRM) ticketing system for ADB road-infrastructure
projects in Nepal. Officers receive, process and escalate community grievances.

- **Backend API**: FastAPI at `http://localhost:5002` (ticketing service)
- **Frontend**: Next.js 16 app at `channels/ticketing-ui/`
- **Running via Docker**: `docker compose -f docker-compose.yml -f docker-compose.grm.yml up`
- **Frontend dev server**: `http://localhost:3001` (grm_ui container)

---

## Hard rule: never touch these paths

```
backend/          rasa_chatbot/      docker-compose.yml
channels/          (anything outside ticketing-ui/)
ticketing/         ← READ freely, but backend Python is handled in a separate session
requirements.txt
```

**Your work is 100% inside `channels/ticketing-ui/`.**

---

## Tech stack

- Next.js 16 (App Router, `"use client"` where needed)
- TypeScript strict
- Tailwind CSS v4 (no `tailwind.config.js` — uses `@import "tailwindcss"` in globals.css)
- No UI component library — everything is bespoke Tailwind
- Auth: AWS Cognito OIDC via `useAuth()` hook (`app/providers/AuthProvider.tsx`)
- API calls: `lib/api.ts` (typed fetch wrappers, base URL from `NEXT_PUBLIC_API_URL`)

---

## Routing architecture

Two shells share the same Next.js app:

| Path prefix | Shell | Device target |
|-------------|-------|---------------|
| `/m/*`      | `MobileShell` — `h-dvh`, bottom tab bar (Queue / All / Tasks) | Phone / narrow |
| everything else | `DesktopShell` — slate sidebar + top header | Desktop / wide |

`AppShell` in `components/AppShell.tsx` branches on `pathname.startsWith("/m")`.

**Thread screens** (`/m/tickets/[id]`) get `isThreadScreen=true` → no bottom tab bar
(the page owns its own sticky header + fixed compose footer).

---

## Current file map

```
channels/ticketing-ui/
  app/
    layout.tsx                     ← wraps everything in <AppShell>
    page.tsx                       ← root redirect → /queue
    providers/AuthProvider.tsx     ← Cognito + useAuth() hook

    # ── Desktop routes ──────────────────────────────────────
    queue/page.tsx                 ← Officer queue: tabs + summary tiles + ticket rows
    tickets/page.tsx               ← All tickets filterable list
    tickets/[id]/page.tsx          ← Desktop ticket detail (OLD STYLE — see TODO)
    escalated/page.tsx             ← Escalated tickets list
    reports/page.tsx               ← XLSX export
    settings/page.tsx              ← Admin settings (workflows, users, orgs)
    help/page.tsx                  ← Officer guide
    login/page.tsx                 ← Cognito login page
    auth/callback/page.tsx         ← OIDC callback handler

    # ── Mobile routes (/m/*) ─────────────────────────────────
    m/page.tsx                     ← redirect → /m/queue
    m/queue/page.tsx               ← Chat-list queue (urgency dots, SLA meta, SEAH badges)
    m/tickets/page.tsx             ← Searchable all-tickets list
    m/tickets/[id]/page.tsx        ← Thread screen (COMPLETE — reference implementation)
    m/tasks/page.tsx               ← My pending tasks across all tickets

  components/
    AppShell.tsx                   ← DesktopShell + MobileShell + root router
    ui/
      Badge.tsx                    ← StatusBadge, PriorityBadge, SeahBadge, UrgencyDot, CountBubble
      SlaCountdown.tsx             ← SLA timer component
      VaultReveal.tsx              ← RevealModal + RevealOverlay (SEAH-sensitive content)

  lib/
    api.ts                         ← All API calls + TypeScript interfaces
    mobile-constants.ts            ← ROLE_BUBBLE_STYLE, SYSTEM_EVENT_TYPES, TASK_EVENT_TYPES,
                                      NOTIFICATION_ONLY_EVENT_TYPES, systemEventLabel, urgencyDot
  app/globals.css                  ← Tailwind v4 + custom: h-dvh, pt-safe-top, pb-safe-bottom,
                                      safe-area-bottom, scrollbar-none
```

---

## The reference implementation you MUST read first

**`app/m/tickets/[id]/page.tsx`** is the gold-standard thread screen. It contains:

- `NoteText` — renders note with `@mention` tokens highlighted blue
- `NoteBubble` — role-colored left bubble or right blue bubble (mine)
- `SystemPill` — centered gray pill for status events
- `TaskCard` — amber/green task card with ✓ complete button
- `AssignTaskSheet` — bottom sheet for task assignment
- `MoreActionsSheet` — Escalate / Assign task / Close
- `ViewersBar` — sticky strip showing viewer @chips + Add button
- `AddViewerSheet` — officer search + direct-entry
- `FilterChips` — All / 👤 You / per-author / 📋 Tasks / ⚙️ System
- `SlaSubHeader` — urgency dot + step + time remaining
- `PrimaryCtaBar` — Acknowledge → Resolve + More ▾ (state-machine based)
- @mention compose bar with autocomplete popup (type `@` → shows participants)

Everything in `lib/mobile-constants.ts` is shared between mobile and desktop.

---

## Key constants in `lib/mobile-constants.ts`

```ts
SYSTEM_EVENT_TYPES   // → centered SystemPill (not a bubble)
TASK_EVENT_TYPES     // → TaskCard
NOTIFICATION_ONLY_EVENT_TYPES  // → skip rendering entirely (MENTION events)
ROLE_BUBBLE_STYLE    // role key → { bubbleCls, labelCls, emoji, label }
systemEventLabel()   // event_type + payload → human label for pill
```

---

## `lib/api.ts` — key interfaces

```ts
TicketDetail {
  ...                    // all ticket fields
  events: TicketEvent[]  // full thread
  viewers: TicketViewer[] // case watchers (NEW)
}

TicketEvent {
  event_type, note, payload
  actor_role             // role key at write time → bubble color
  case_sensitivity       // 'standard' | 'seah'
  summary_regen_required // bool
  created_by_user_id, created_at, seen
}

TicketViewer { viewer_id, user_id, added_by_user_id, added_at }
TicketTask   { task_id, task_type, assigned_to_user_id, status, due_date, ... }
```

Available API functions relevant to UI:
```ts
getTicket(id)             listTicketTasks(id)     listViewers(id)
performAction(id, body)   createTask(id, body)    addViewer(id, userId)
getSla(id)                completeTask(id, taskId) removeViewer(id, userId)
markSeen(id)              listMyTasks()
```

---

## TODO — what needs to be built / fixed

### Priority 1 — Desktop thread view (the main gap)

`app/tickets/[id]/page.tsx` currently renders events as a vertical timeline
with emoji icons (old style). It needs to be upgraded to match the mobile
thread exactly:

- Replace the timeline with **chat bubbles** (NoteBubble pattern)
- Add **SystemPill** for status events
- Add **TaskCard** for TASK_ASSIGNED / TASK_COMPLETED
- Add **FilterChips** (All / You / per-author / Tasks / System)
- Add **ViewersBar** strip in the sticky header area
- Add **@mention** autocomplete in the note-compose textarea
- Skip `NOTIFICATION_ONLY_EVENT_TYPES` events in render
- The action panel (Acknowledge / Escalate / Resolve / Close) stays on the
  right-hand column — the thread is the left/main column on desktop

Extract shared sub-components from the mobile page into
`components/thread/` so both desktop and mobile import them:

```
components/thread/
  NoteText.tsx          ← @mention highlighting
  NoteBubble.tsx        ← role-colored bubble (left) or blue (right)
  SystemPill.tsx        ← centered gray pill
  TaskCard.tsx          ← amber/green task card
  FilterChips.tsx       ← horizontal chip row
  ViewersBar.tsx        ← viewer strip + AddViewerSheet
  ComposeBar.tsx        ← textarea + send button + @mention popup
  SlaSubHeader.tsx      ← urgency dot + step name + time left
```

Then **refactor** `app/m/tickets/[id]/page.tsx` to import from `components/thread/`
instead of defining everything inline. The page becomes much shorter —
just state, data loading, and layout.

### Priority 2 — Mobile queue polish

`app/m/queue/page.tsx` — review against the spec:
- Three tabs: My Queue / All / Escalated
- Each ticket row: urgency dot 🔴🟡🟢, grievance_id, truncated summary,
  SLA meta ("2d left" or "Overdue"), SEAH badge if `is_seah`
- Tapping a row → `/m/tickets/[id]`
- Pull-to-refresh or a refresh button
- Empty state illustration when no tickets

### Priority 3 — Desktop queue polish

`app/queue/page.tsx` has tabs + SummaryTile + ticket rows. Check:
- Summary tiles: "Action Needed" / "Due Today" / "Overdue 🔴" counts
  (these require SLA data — can be approximated from `sla_breached` flag)
- Ticket row should show: urgency dot, grievance_id, summary, SLA countdown,
  SEAH badge, assigned officer name, unread badge from `unseen_event_count`
- Clicking a row → `/tickets/[id]`

### Priority 4 — Responsive / navigation polish

- Desktop sidebar is hidden on `< md`. On small screens the desktop layout
  has no nav at all. Add a hamburger / mobile-top-bar for `sm` breakpoint
  OR add a redirect in the root layout: if `window.innerWidth < 768` on
  first load, redirect to `/m/queue`. (UA-based redirect is handled by
  Nginx in production — don't duplicate server-side; do it client-side only
  for local dev convenience.)
- The `/m/*` bottom tab bar could use a notification count on the Queue tab
  (already wired — `unseenCount` in MobileShell).

### Priority 5 — Desktop settings page audit

`app/settings/page.tsx` — this is an admin page. At minimum:
- Workflows tab: list workflows, link to detail
- Users tab: list officers, invite button (POST /api/v1/users/invite)
- Orgs tab: list organizations + locations
- Make sure tabs are working and not just stubs

---

## Patterns to follow

### Loading states
```tsx
if (loading) return (
  <div className="flex items-center justify-center h-full min-h-[200px]">
    <div className="text-sm text-gray-400 animate-pulse">Loading…</div>
  </div>
);
```

### Error boundary
```tsx
if (error) return (
  <div className="flex flex-col items-center gap-3 py-16 text-sm text-gray-500">
    <span className="text-3xl">⚠️</span>
    <span>{error}</span>
    <button onClick={retry} className="text-blue-600">Retry</button>
  </div>
);
```

### Color system (match existing components)
- Primary action: `bg-blue-600 text-white`
- Destructive: `bg-red-600 text-white`
- Secondary: `bg-gray-100 text-gray-800`
- SEAH: `text-red-600 bg-red-50 border-red-200`
- Overdue: `text-red-700` | Warning: `text-yellow-700` | OK: `text-green-700`

### No hardcoded user IDs
Auth mock uses `user?.sub ?? "mock-super-admin"`. In production this is the
Cognito `sub` claim.

---

## Running locally

```bash
# In WSL at /home/philg/projects/nepal_chatbot_claude
docker compose -f docker-compose.yml -f docker-compose.grm.yml up -d

# Frontend hot-reload is via the grm_ui container (Next.js dev server)
# Access: http://localhost:3001
# API:    http://localhost:5002

# After Python changes only:
docker compose -f docker-compose.yml -f docker-compose.grm.yml build ticketing_api
docker compose -f docker-compose.yml -f docker-compose.grm.yml up -d ticketing_api

# Run migrations:
docker exec nepal_chatbot_claude-ticketing_api-1 \
  alembic -c ticketing/migrations/alembic.ini upgrade head
```

---

## Commit convention

```
feat: short present-tense description

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

Branch: `feature/grm-ticketing`. Never touch `main`.

---

## Where to start

1. Read `app/m/tickets/[id]/page.tsx` fully — this is your reference.
2. Read `lib/mobile-constants.ts` and `lib/api.ts` (the TicketDetail interface section).
3. Create `components/thread/` and extract the shared components.
4. Refactor the mobile thread page to import from `components/thread/`.
5. Build the desktop thread page using those same components.
6. Then move to Priority 2 → 3 → 4 → 5.
