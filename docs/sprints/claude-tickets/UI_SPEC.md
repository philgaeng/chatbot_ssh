# GRM Ticketing UI — Design Spec

> Companion to `TODO.md` and `PROGRESS.md`.
> Describes UI patterns, component behaviour, and layout decisions for `channels/ticketing-ui/`.
> Update this file when a new non-trivial UI pattern is added or changed.
> Last updated: 2026-04-27

---

## Contents

1. [Design philosophy](#1-design-philosophy)
2. [Mobile-first design](#2-mobile-first-design)
   - 2.1 Queue screen
   - 2.2 Thread screen — core mental model
   - 2.3 Role-highlighted bubbles
   - 2.4 Per-user thread filtering
   - 2.5 In-thread task assignment
   - 2.6 Data model for tasks
   - 2.7 Case viewers (watchers)
   - 2.8 @mention — addressing case participants
3. [Desktop layout](#3-desktop-layout)
   - 3.1 Three-zone layout
   - 3.2 Translation review panel
   - 3.3 Desktop improvements needed
4. [Shared patterns](#4-shared-patterns)
   - 4.1 User language preference
   - 4.2 SLA urgency colours
   - 4.3 SEAH visual treatment
   - 4.4 Badge counts
   - 4.5 Collapsible panels

---

## 1. Design philosophy

> "As simple as a chat in WhatsApp."

Most GRM officers are **field officers working on phones**. The primary interaction
is: open a case, read the history, add a note or complete a task, close the app.
The UI must support this in under 30 seconds, one-handed, on a mid-range Android.

**Core principles:**

| Principle | Rationale |
|---|---|
| Input bar always visible at the bottom | Officers never scroll to act |
| Primary CTA is context-aware | New ticket → Acknowledge; In-progress → Resolve / Escalate |
| Timeline IS the screen | No separate "notes" section — one thread like WhatsApp |
| Role-highlighted messages | Supervisor instructions must stand out immediately |
| Filter by person | In a busy case with many officers, find relevant messages fast |
| Tasks in-thread | Coordination happens in the thread, not in a separate task manager |
| Bottom sheet for destructive / secondary actions | Prevents accidental taps, keeps screen clean |
| No sidebar on mobile | Bottom tab bar — one thumb, natural reach zone |

**Relationship between mobile and desktop:**
- Same thread metaphor, same bubble vocabulary, same colours
- Desktop adds side panels (PII, findings, translations) and more detail
- An officer switching devices sees the same case, the same way

---

## 2. Mobile-first design

### 2.1 Queue screen (chat list)

```
┌────────────────────────────────┐
│  My Queue               🔔 3   │
│  ─────────────────────────     │
│  🔴 GRV-2025-003               │
│     Road widening damaged…     │
│     20h left  ·  L1  ·  Jhapa  │
│  ─────────────────────────     │
│  🟡 GRV-2025-001               │
│     Dust — children sick…      │
│     2d left  ·  L3 GRC         │
│  ─────────────────────────     │
│  🔒 GRV-2025-SEAH-001          │
│     [SEAH — restricted]        │
│     Active  ·  L1              │
│  ─────────────────────────     │
│                                │
│                                │
│  🏠 Queue   🔍 All   👤 Me     │  ← bottom tab bar
└────────────────────────────────┘
```

**Rules:**
- Urgency dot (🔴 🟡 🟢) is the leftmost visual — seen before reading anything
- Each row: ID + one-line summary + SLA remaining + level + location
- SEAH cases show 🔒 and no summary text (content restricted)
- Tap anywhere on a row to open the thread
- No sidebar — bottom tab bar: **Queue | All Tickets | Profile**
- Pull-to-refresh; no pagination (load more on scroll)

---

### 2.2 Thread screen — core mental model

**A ticket is a conversation thread.**

```
┌────────────────────────────────────┐
│  ←  GRV-2025-003          ⋮       │  ← header: back + overflow menu
│  📍 L1 · Jhapa · 20h left 🔴      │  ← sticky sub-header: always visible
│  ────────────────────────────────  │
│  [ All ][@you][@piu-l2][Tasks][⚙️] │  ← filter chips (scroll horizontally)
│  ────────────────────────────────  │
│                                    │
│        ─── Case opened ───         │  system pill
│        ─── Assigned to you ───     │  system pill
│                                    │
│  ┌──────────────────────────────┐  │
│  │ Road widening compensation   │  │  complainant summary card
│  │ Birtamod · Property Damage   │  │  (collapsible after first read)
│  └──────────────────────────────┘  │
│                                    │
│                                    │
│  ────────────────────────────────  │
│  ┌──────────────────────────┐  📎 │
│  │  Add a note…             │  ↑  │  ← compose bar, always at bottom
│  └──────────────────────────┘     │
│  [ ✅  Acknowledge — tap to start ]│  ← primary CTA, full width, context-aware
└────────────────────────────────────┘
```

**After acknowledged**, the CTA changes to:
```
│  [ 🏁 Resolve ]  [ 🔺 More actions ▾ ]  │
```

**"More actions" bottom sheet:**
```
│  ─────────────────────────  │
│  🔺  Escalate to L2 PIU     │
│  📋  Assign a task          │
│  🔒  Close without resolve  │
│  ─────────────────────────  │
│           Cancel            │
```

**Thread message types (rendered differently):**

| Type | Visual |
|---|---|
| System event (created, escalated…) | Centered pill, gray text, no bubble |
| Your note | Right-aligned blue bubble |
| Colleague note (same level) | Left-aligned gray bubble |
| Supervisor note | Left-aligned, **role-colour left border** |
| Task card | Full-width card with task type + assignee + complete button |
| Complainant summary | Collapsible card at top of thread |

---

### 2.3 Role-highlighted messages

Officers must immediately spot a supervisor instruction without reading every message.
Bubbles are differentiated by the **writer's role**, not their name.

```
│        ─── Escalated to L2 ───        │  system pill

│  ┌────────────────────────────────┐   │
│  │ Please document road damage    │   │  ← L2 supervisor note
│  │ at KM 12+500 with photos       │   │    amber left border (4px)
│  │ before the GRC hearing.        │   │    role badge below
│  └────────────────────────────────┘   │
│  🟠 L2 · mock-piu-l2  ·  10:02am     │

│                            ┌─────────────────────┐
│                            │ Done. Photos in the │  ← your note (right, blue)
│                            │ attachment below. ✓ │
│                            └─────────────────────┘
│                            You · 2:14pm

│  ┌────────────────────────────────┐   │
│  │ GRC convened for May 3rd.      │   │  ← GRC chair note
│  │ Attend at district office HQ.  │   │    purple left border
│  └────────────────────────────────┘   │
│  🟣 GRC Chair · mock-grc-chair        │
```

**Colour vocabulary (consistent across mobile and desktop):**

| Role | Left border colour | Label chip | Tailwind |
|---|---|---|---|
| You (current user) | — (right side) | "You" | `bg-blue-500` bubble |
| Peer officer (same level) | None | name only | `bg-gray-100` bubble |
| L2 supervisor / PIU | Amber | 🟠 L2 | `border-l-4 border-amber-400` |
| L3 GRC chair | Purple | 🟣 GRC | `border-l-4 border-purple-400` |
| ADB observer / HQ | Teal | 🔵 ADB | `border-l-4 border-teal-400` |
| SEAH officer | Red | 🔴 SEAH | `border-l-4 border-red-400` |
| System / automated | — (centered pill) | — | `text-gray-400 text-center` |

**Role → colour mapping lives in a single constant** (`ROLE_BUBBLE_STYLE`) shared by
mobile and desktop thread components. Changing it in one place changes both.

---

### 2.4 Per-user thread filtering

Long cases accumulate many messages from many officers. Officers need to find
"everything the supervisor told me" or "everything I've done" instantly.

**Filter chips — always visible above the thread:**

```
[ All ] [ 👤 You ] [ 🟠 @piu-l2 ] [ 🟣 @grc ] [ 📋 Tasks ] [ ⚙️ System ]
```

- Chips are generated dynamically from unique authors in the thread
- Active chip has a filled background; inactive is outlined
- **Tasks** chip: shows only task cards (hides all notes and system events)
- **System** chip: shows only auto-generated events (created, escalated, SLA breach)
- Tap a message author's name in the thread → auto-activates their filter chip
- Active filter shows `×` inside the chip to reset

**Implementation note:** filtering is purely client-side — the full event list is
already loaded. Filter chips do not trigger API calls.

---

### 2.5 In-thread task assignment

The most important coordination feature. Supervisors and senior officers frequently
need to delegate specific actions to field officers — just as they would in a
WhatsApp group, but structured and trackable.

**Who can assign tasks:** Any officer who can see the ticket (tasks are not restricted
to admins — an L2 officer can assign a task to their L1 officer).

**Assigning a task — bottom sheet:**

```
┌──────────────────────────────────────┐
│  📋 Assign task                      │
│  ──────────────────────────────────  │
│  Type                                │
│  ┌─────────┐ ┌──────────┐           │
│  │🚶 Site  │ │📞 Follow-│           │
│  │  Visit  │ │  up Call │           │
│  └─────────┘ └──────────┘           │
│  ┌─────────┐ ┌──────────┐           │
│  │📝 System│ │📸 Document│          │
│  │  Note   │ │ & Photo  │           │
│  └─────────┘ └──────────┘           │
│                                      │
│  Assign to                           │
│  [ mock-officer-site-l1 ▾ ]         │
│                                      │
│  Instructions (optional)             │
│  ┌──────────────────────────────┐   │
│  │ Document damage at KM 12+500 │   │
│  │ with photos                  │   │
│  └──────────────────────────────┘   │
│                                      │
│  Due date (optional)                 │
│  [ Tomorrow ▾ ]                      │
│                                      │
│  [ Assign Task ]                     │
└──────────────────────────────────────┘
```

**Task card in thread (pending state):**

```
┌──────────────────────────────────────┐
│  📋  SITE VISIT                      │  ← task type, bold
│  → @mock-officer-site-l1             │  ← assigned to
│  "Document road damage at KM 12+500  │
│   with photos before GRC hearing"    │
│  Due: 28 Apr · Assigned by @piu-l2   │
│                                      │
│  [ ✓  Mark Complete ]                │  ← visible only to assigned officer
└──────────────────────────────────────┘
```

**Task card — completed state:**

```
┌──────────────────────────────────────┐
│  ✅  SITE VISIT — Done               │  ← green header
│  @mock-officer-site-l1               │
│  Completed 26 Apr · 2:14pm           │
└──────────────────────────────────────┘
```

**Task types (pre-defined, admin-extensible later):**

| Key | Label | Icon |
|---|---|---|
| `SITE_VISIT` | Site Visit | 🚶 |
| `FOLLOW_UP_CALL` | Follow-up Call | 📞 |
| `SYSTEM_NOTE` | Add System Note | 📝 |
| `DOCUMENT_PHOTO` | Document & Photo | 📸 |

**Rules:**
- A task fires a `TASK_ASSIGNED` event (appears in thread at the right time)
- Completing it fires a `TASK_COMPLETED` event
- The assigned officer receives an unseen notification event (drives badge count)
- The **Tasks** filter chip shows all pending + completed task cards
- A pending task assigned to you also shows a small banner in the thread sub-header:
  `📋 1 task assigned to you`

---

### 2.6 Data model for tasks

New table `ticketing.ticket_tasks` (separate from events — allows querying
"all pending tasks for officer X" without scanning the full event log):

```sql
CREATE TABLE ticketing.ticket_tasks (
    task_id              VARCHAR(36) PRIMARY KEY,
    ticket_id            VARCHAR(36) NOT NULL REFERENCES ticketing.tickets,
    task_type            VARCHAR(32) NOT NULL,   -- SITE_VISIT | FOLLOW_UP_CALL | SYSTEM_NOTE | DOCUMENT_PHOTO
    assigned_to_user_id  VARCHAR(128) NOT NULL,
    assigned_by_user_id  VARCHAR(128) NOT NULL,
    description          TEXT,
    due_date             DATE,
    status               VARCHAR(16) NOT NULL DEFAULT 'PENDING',  -- PENDING | DONE | DISMISSED
    completed_at         TIMESTAMPTZ,
    completed_by_user_id VARCHAR(128),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**API:**
- `POST /api/v1/tickets/{id}/tasks` — assign a task (any officer)
- `POST /api/v1/tickets/{id}/tasks/{task_id}/complete` — mark done (assigned officer or admin)
- `GET  /api/v1/tickets/{id}/tasks` — list tasks for a ticket
- `GET  /api/v1/users/me/tasks` — all pending tasks assigned to current officer (across tickets)

**Timeline integration:**
The task assignment creates a `TASK_ASSIGNED` event in `ticketing.ticket_events`
with `payload = { task_id, task_type, assigned_to }`. The thread renders this event
as a task card (not a note bubble) by checking `event_type === "TASK_ASSIGNED"`.
`TASK_COMPLETED` similarly updates the card to the done state.

---

### 2.7 Case viewers (watchers)

A PM or L2 officer typically copies in several colleagues to follow a case closely — just
as they would in a WhatsApp group. These people are **viewers** (watchers) of the case.

**Who can add viewers:**
Any officer holding a senior role on the case — `pd_piu_safeguards_focal` (L2),
`grc_chair`, `grc_member`, SEAH officers, ADB observers, or admins.
The assigned officer at any level can also add viewers to their own case.

**What viewers can do:**
- Read all thread messages and case details ✓
- Post notes/messages (appear as left-aligned gray bubbles in the thread) ✓
- Use `@mention` to address specific participants or `@all` ✓

**What viewers cannot do:**
- Acknowledge / Escalate / Resolve / Close the ticket ✗
- Assign formal tasks ✗
- Add further viewers ✗ *(only the adding-eligible roles above)*

**Thread appearance:** Viewer bubbles use the same role-colour vocabulary. A viewer
with role `adb_hq_project` gets the teal bubble; a viewer with no special role gets a
plain gray bubble. The role badge shows below their bubble so the team always knows
who is speaking.

**Viewer added event:** `VIEWER_ADDED` system pill appears in the thread when a viewer is
added:  `─── @piu-assistant added as viewer ───`

**Data model:**

```sql
CREATE TABLE ticketing.ticket_viewers (
    viewer_id        VARCHAR(36) PRIMARY KEY,
    ticket_id        VARCHAR(36) NOT NULL REFERENCES ticketing.tickets,
    user_id          VARCHAR(128) NOT NULL,
    added_by_user_id VARCHAR(128) NOT NULL,
    added_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (ticket_id, user_id)
);
```

**API:**
- `POST   /api/v1/tickets/{id}/viewers`               — add a viewer (senior role / assigned officer)
- `DELETE /api/v1/tickets/{id}/viewers/{user_id}`      — remove a viewer
- `GET    /api/v1/tickets/{id}/viewers`               — list viewers (included in ticket detail)

Viewers list is embedded in `GET /api/v1/tickets/{id}` response as `viewers: TicketViewer[]`.

---

### 2.8 @mention — addressing case participants

Typing `@` in the compose bar opens an inline autocomplete listing everyone who has
access to the case: the assigned officer + all viewers.

```
┌──────────────────────────────────────┐
│  Add a note…                         │
│  @pi                                 │  ← user typed @pi
│  ─────────────────────────────────── │
│  🟠  @piu-l2             L2 PIU      │  ← dropdown above compose bar
│  👤  @piu-assistant      Viewer      │
└──────────────────────────────────────┘
```

**Behaviour:**
- `@` followed by characters → filter list of participants in real time
- Tap/click a name → inserts `@user_id` into the text at cursor position
- `@all` is always available at the top of the list — addresses all case participants
- Pressing Escape or moving the cursor off the `@word` closes the dropdown
- No API call on each keystroke — participants are already loaded in ticket detail

**`@all` semantics:**
- Notifies: assigned officer + all viewers of the case
- Creates a `MENTION` notification event per recipient (`seen=False`, drives unread badge)
- These events are **not rendered in the thread** — they only drive the badge counter

**Rendering in thread:**
```
│  ┌──────────────────────────────────────┐
│  │ @piu-l2 please review the attached  │  ← @mention rendered as
│  │ photos before the GRC hearing       │     blue highlighted span
│  └──────────────────────────────────────┘
│  👤  @piu-assistant  ·  2:14pm
```

`@username` spans are highlighted with `text-blue-600 font-medium` inline.
`@all` is rendered as `text-indigo-600 font-medium bg-indigo-50 rounded px-0.5`.

**Implementation note:**
Backend parses `@mentions` from NOTE text on save (simple regex). For each resolved
mention, a `MENTION` event is written with `assigned_to_user_id = mentioned_user`,
`seen = False`. The `@all` mention resolves to every viewer + the assigned officer.
`MENTION` event_type is in `NOTIFICATION_ONLY_EVENT_TYPES` — the frontend skips it
when rendering the thread but counts it for badges.

---

## 3. Desktop layout

### 3.1 Three-zone layout

Desktop is the **power view** — same thread vocabulary as mobile, richer side panels.

```
┌──────────────────────────┬──────────────┬─────────────────────┐
│  Thread                  │  Context     │  Translation Panel  │
│  (chat bubbles)          │  sidebar     │  (collapsible, 🌐)  │
│                          │              │                     │
│  Same bubble colours     │  Complainant │  320 px             │
│  Same filter chips       │  Findings    │  Toggle: T key      │
│  Same task cards         │  Attachments │  or button in       │
│                          │  Assignment  │  timeline header    │
│  [compose bar]           │              │                     │
│  [Resolve][Escalate▾]    │  Actions     │                     │
└──────────────────────────┴──────────────┴─────────────────────┘
```

**Key difference from current desktop implementation:**
- Actions moved to the **top** of the context sidebar (currently at the bottom — too far to scroll)
- Thread uses chat bubbles and filter chips (currently plain event list)
- Task cards render inline in the thread (not yet built)

**Right column order (top to bottom):**
1. Actions (primary — always visible without scroll)
2. Complainant (context for the action)
3. Assignment (quick admin)
4. Findings (supervisor/GRC only)
5. Attachments (secondary)

### 3.2 Translation review panel

Collapsible third zone. See full spec in [Section 4.1](#41-user-language-preference).

**Toggle:** `🌐 Review translations` button in timeline card header, or press `T`.
**Breakpoint:** visible as inline column at `lg:` (1024px+); fixed overlay on smaller screens.
**State:** persisted in `localStorage` key `grm_translation_panel_open`.

### 3.3 Desktop improvements needed (TODO)

These are known gaps from the current implementation, to fix before demo:

- [ ] Move Actions card to top of right column
- [ ] Make primary CTA full-width and context-aware (Acknowledge vs Resolve)
- [ ] Thread: convert plain event list to chat bubbles with role colours
- [ ] Thread: add filter chips
- [ ] Thread: render task cards (after task feature is built)
- [ ] Move "SEAH access" badge from page header to user profile area (top right)

---

## 4. Shared patterns

### 4.1 User language preference

**Data model:**
```
ticketing.organizations.default_language  VARCHAR(8)  DEFAULT 'ne'
ticketing.user_roles.preferred_language   VARCHAR(8)  DEFAULT NULL
```

**Effective language resolution:**
1. `user_roles.preferred_language` (personal override, if set)
2. `organizations.default_language` (org default)
3. `'en'` (hard fallback)

**Seeded defaults:** DOR → `'ne'` (Nepali-first), ADB → `'en'` (English-first).

**API:**
- `GET  /api/v1/users/me/preferences` → `{ effective_language, preferred_language, org_default_language }`
- `PATCH /api/v1/users/me/preferences` → `{ preferred_language: "en" | "ne" | null }`

**UI effect:**

| `effective_language` | Inline translation chip in thread | Translation panel |
|---|---|---|
| `en` | Shown | Available |
| `ne` | Hidden (original IS their language) | Available for verification |

**Settings page:** Settings → My Profile → Language (dropdown + reset to org default).

**Alembic migration:** `d2e8f4a1b093` — adds both columns, patches ADB → `'en'`.

---

### 4.2 SLA urgency colours

| Urgency | Condition | Tailwind classes |
|---|---|---|
| `overdue` | `sla_breached = true` | `bg-red-50 text-red-700` |
| `critical` | < 24 h remaining | `bg-orange-50 text-orange-700` |
| `warning` | < 3 d remaining | `bg-yellow-50 text-yellow-700` |
| `ok` | > 3 d remaining | `bg-green-50 text-green-700` |
| `none` | step has no SLA | *(no bar)* |

Used in: queue row urgency dot, thread sub-header, workflow card SLA bar.

---

### 4.3 SEAH visual treatment

- **Queue row:** `border-l-4 border-red-500` + `🔒 SEAH` badge; no summary text shown
- **Thread header:** `SeahBadge` component next to grievance ID
- **Access control:** `canSeeSeah` from `AuthProvider`; server also enforces 403

---

### 4.4 Badge counts

- **My Queue** and **Escalated** tabs: red filled dot with count when unseen events exist
- **Watching:** plain grey count — informational only
- **Resolved:** no badge
- **Pending tasks assigned to you:** `📋 N` badge on the Tasks filter chip in the thread

---

### 4.5 Collapsible panels

Any panel that a role-subset rarely needs should be collapsible, not hidden entirely.
Visible surface area scales with what the *current user* routinely needs.

| Panel | Default state | Who opens it |
|---|---|---|
| Translation Review | Closed | Bilingual officers checking AI accuracy |
| Findings card | Open | GRC / supervisor roles (hidden from L1/L2) |
| Attachments | Open | All officers |
| Complainant summary card (mobile) | Expanded on first open, collapsed after | All |

---

*Updated by Claude Code. Keep in sync with implemented components.*
