# Officer Portal — UI Specification (As-built)

> **Status:** As-built, July 2026. Consolidated from `docs/sprints/archive/claude-tickets/UI_SPEC.md` (2026-04-27), `UI_HANDOFF_thread_redesign.md` (2026-04-28/29) and `UI_REVIEW.md` (P1-A…P1-G), verified against `channels/ticketing-ui/` code.
> Anything marked **[SPECCED, NOT IMPLEMENTED]** or **[SUPERSEDED]** is called out explicitly. §11 lists all known spec-vs-code deviations.

---

## 1. Stack, auth, routes

- **Stack:** Next.js 16 (App Router) / React 19 / TypeScript / Tailwind CSS v4 (`@tailwindcss/postcss`). Icons: Lucide via `lib/icons.tsx` aliases (see `02_design_system.md`).
- **Auth:** Keycloak OIDC with PKCE — `lib/auth/oidc-auth.ts` (drop-in replacement for the earlier Cognito client), session/roles exposed by `app/providers/AuthProvider.tsx` (`isAdmin`, `canSeeSeah`, bypass-auth role switcher for demos).

### Routes (verified against `app/`)

| Route | Purpose |
|-------|---------|
| `/` | Redirects to `/queue` (`app/page.tsx`) |
| `/queue` | Desktop queue — tabs + summary tiles (primary landing) |
| `/tickets` | All-tickets list with shared filter bar |
| `/tickets/[id]` | Desktop ticket detail (thread + info column) |
| `/tickets/[id]/closure` | Closure flow for a ticket |
| `/escalated` | Escalated list — **exists but is not linked from the sidebar** (legacy route) |
| `/reports` | Reports; plus public token views `/reports/public/[token]`, `/reports/view/[token]` |
| `/qr-codes` | QR code generation for intake |
| `/settings` | Admin settings (admin-only nav item; label becomes "Project setup" for non-super/country admins) |
| `/help` | Officer guide |
| `/account` | Own account page |
| `/login`, `/login/reset-password`, `/auth/callback` | Auth (public routes) |
| `/closure/[token]` | Public complainant closure confirmation (public route prefix) |
| `/m`, `/m/queue`, `/m/tickets`, `/m/tickets/[id]`, `/m/tasks` | Mobile app (§7) |

### Mobile/desktop switching (`lib/mobile-routes.ts`)

- Breakpoint: viewports ≤ **767 px** (`MOBILE_MAX_WIDTH_PX`) use `/m/*`; UA sniffing helper also available.
- Bidirectional path mapping: `/queue ↔ /m/queue`, `/tickets ↔ /m/tickets`, `/tickets/[id] ↔ /m/tickets/[id]`; `/m/tasks → /queue` on desktop.
- Same case, same thread vocabulary on both form factors — desktop adds side panels and detail.

### Navigation (as-built, `components/AppShell.tsx`)

- **Desktop sidebar:** Tickets (`/queue`, action badge) · — · Reports · QR Codes · — · Settings (admin only) · Help.
  **[SUPERSEDED]** The original sidebar plan (My Queue / All Tickets / Escalated / GRC / Reports / Settings / Help) was collapsed into a single **Tickets** entry; escalation and GRC access happen via queue tabs/filters, not nav items.
- **Mobile bottom tab bar:** **Queue | All | Tasks** (`/m/queue`, `/m/tickets`, `/m/tasks`).
  **[SUPERSEDED]** UI_SPEC §2.1 showed `Queue | All | Profile`; the third tab is Tasks, not Profile.

---

## 2. Design philosophy

> "As simple as a chat in WhatsApp."

Most GRM officers are field officers on mid-range Android phones. Primary interaction: open a case, read the history, add a note or complete a task, close the app — under 30 seconds, one-handed.

| Principle | Rationale |
|---|---|
| Compose bar always visible at the bottom | Officers never scroll to act |
| Primary CTA is context-aware | New → Acknowledge; in-progress → Resolve / Escalate |
| Timeline IS the screen | One thread; no separate "notes" section |
| Context-highlighted bubbles | Supervisor instructions stand out immediately (§5) |
| Semantic thread filters | Find "what the supervisor said" fast (§5.4) |
| Tasks in-thread | Coordination happens in the thread, not a separate task manager |
| Bottom sheet for secondary/destructive actions | Prevents accidental taps |
| No sidebar on mobile | Bottom tab bar, thumb reach zone |

---

## 3. Desktop queue (`app/queue/page.tsx`)

### 3.1 Tabs (as-built — participation-tier model, not the old status tabs)

**[SUPERSEDED]** The original My Queue / Watching / Escalated / Resolved tabs were replaced by **participation-tier tabs** driven by the `tab` query param of `GET /api/v1/tickets`:

| Tab | `tab=` | Badge | Visibility | Meaning |
|-----|--------|-------|------------|---------|
| Actor | `actor` | red count | always | I'm the action owner or have a pending task |
| Supervisor | `supervisor` | grey count | hidden when empty | Tickets I supervise at the next level |
| Informed | `informed` | grey count | hidden when empty | Tickets I've been added to as an informed member |
| Observer | `observer` | none | hidden when empty | Read-only watching |
| High Priority | `high_priority` | red count | always | HIGH/CRITICAL priority or SLA-breached |
| All Tickets | `all` | none | always | Everything visible to my role |

Tab totals are fetched with `page_size=1` probes; conditional tabs disappear at zero.

### 3.2 Summary tiles (as-built — resolves `queue-tile-logic.md`)

The April sprint doc `docs/sprints/archive/claude-tickets/queue-tile-logic.md` froze at "BROKEN — needs a decision" with Options A/B/C. **Option A landed, extended with task due dates.** Full rule in `15_ticket_queue_search_and_filters.md` Appendix A. Summary:

- Backend `GET /api/v1/tickets` list items now include `sla_deadline_at` (= `step_started_at` + `step.resolution_time_days`, computed in `ticketing/api/routers/tickets.py`) and `my_earliest_task_due_at` (earliest pending task due date for the requesting user).
- Frontend `effectiveDeadline(t)` = the earlier of the two.
- Tiles, computed client-side over the Actor tab (fetched `page_size=100` on mount):
  - **Action Needed** = actor tickets with `status_code ∉ {RESOLVED, CLOSED}`
  - **Due Today** = subset with `now ≤ effectiveDeadline ≤ now + 24 h` (yellow when > 0)
  - **Overdue** = subset with `effectiveDeadline < now` (red when > 0)
- Invariant `Action Needed ≥ Due Today + Overdue` holds by construction.
- Tiles are click-to-filter toggles: clicking a tile filters the list (switching to Actor tab if needed); clicking again clears. Active filter shows a dismissible chip.

### 3.3 Ticket rows and sorting

- Row: urgency dot · grievance ID (mono) · intake-route badge · "Needs assignment" hint (admins, when unassigned) · status badge · priority badge · summary line · location/project · live SLA countdown · assignee (lg+) · unseen-event count bubble · chevron.
- Rows sort by category — `overdue → due_today → high_priority → other` — then closest effective deadline first.
- Row urgency dot derives from `effectiveDeadline` (deadline-based, not the stale `sla_breached` flag); the SLA column uses the live `SlaCountdown` component (§8).

### 3.4 Search and filters

Shared `TicketListFiltersBar` (search `q`, priority, SLA, filed-date chips, project, package) sits between the tiles and the tabs; server-side filtering. Spec: `docs/ticketing_system/15_ticket_queue_search_and_filters.md`.

---

## 4. Mobile app (`/m/*`) — as-built

New since the April spec; documented from code.

- **`/m/queue`** (`app/m/queue/page.tsx`) — chat-list style queue per UI_SPEC §2.1: urgency dot leftmost, grievance ID + one-line summary + SLA remaining ("20h left" / "2d left" / "Overdue" / "Active") + step/location label. Per-row SLA fetched live via `getSla`. Pull-to-refresh implemented. Filters via `MobileTicketFiltersSheet` (bottom sheet) instead of the desktop filter bar. SEAH rows show the lock badge treatment (§9).
- **`/m/tickets`** — all-tickets list (mobile equivalent of `/tickets`).
- **`/m/tickets/[id]`** — mobile thread screen: sticky `SlaSubHeader` (SLA strip + `WorkflowMiniStepper`), filter chips, thread (same shared components as desktop, §5), always-visible `ComposeBar`, context-aware primary CTA + "More actions" bottom sheet.
- **`/m/tasks`** — "My pending tasks across all tickets" via `GET /api/v1/users/me/tasks`; complete tasks inline, tap through to the ticket thread.
- **`MobileAppHeader`** — shared mobile header component.

### Workflow mini-stepper (P1-G, implemented)

`WorkflowMiniStepper` in `components/thread/SlaSubHeader.tsx`: shows preceding + current + next + last step with `···` ellipsis when last is not adjacent to next. Short labels via `stepShortLabel(step_key)` in `lib/mobile-constants.ts` (`LEVEL_1_SITE` → "L1 Site", `SEAH_LEVEL_1_NATIONAL` → "SEAH L1", …). Dot styles: completed = filled, current = filled + ring + bold label, future = empty circle.

---

## 5. Ticket thread

Shared components in `components/thread/`, used by both `/tickets/[id]` and `/m/tickets/[id]`:

| File | Purpose |
|------|---------|
| `NoteBubble.tsx` | Message bubble — 4-context colour system (§5.1) + special bubble types (§5.2) |
| `SystemPill.tsx` | Centered pill for system events |
| `TaskCard.tsx` | In-thread task card + `AssignTaskSheet` |
| `FilterChips.tsx` | Semantic filter chip bar (§5.4) |
| `ComposeBar.tsx` | Note input with @mention autocomplete + `#` command palette (§5.5) |
| `NoteText.tsx` | @mention highlighting in note text |
| `SlaSubHeader.tsx` | SLA countdown strip + `WorkflowMiniStepper` |
| `ViewersBar.tsx` | Viewer avatar row + add/remove sheet (tiered, §6.2) |
| `GrievanceThreadCard.tsx` | Original grievance summary card |
| `EscalationFormCard.tsx`, `FieldReportComposeCard.tsx`, `CallReportComposeCard.tsx`, `ReassignmentRequestCard.tsx` | Structured in-thread forms (post-April additions) |

### 5.1 4-context bubble colour system (source of truth)

**[SUPERSEDED]** UI_SPEC §2.3's role→colour table (amber = L2, purple = GRC, teal = ADB, red = SEAH borders) was replaced in the April 28–29 thread redesign. **Colour now encodes the author's relationship to this case, not their role title.** Role identity still appears in the label under the bubble.

As-built in `components/thread/NoteBubble.tsx`:

| Context | Who | Visual |
|---------|-----|--------|
| **You (current user)** | `isMine` | Right-aligned `bg-blue-500 text-white`, no border |
| **Case owner** | author `=== assigned_to_user_id` | `bg-blue-50 border-l-4 border-blue-600`, bold blue label |
| **Authority / supervisor** | role ∈ `AUTHORITY_ROLES` | `bg-amber-50 border-l-4 border-amber-500`, bold amber label |
| **Viewer / observer** | author in `viewerIds` | `bg-gray-50 border-l-4 border-gray-300`, gray label |
| **Other officer** | default | `bg-gray-100 border-l-4 border-gray-400`, gray label |

`AUTHORITY_ROLES` (exported from `lib/mobile-constants.ts`, duplicated locally in `NoteBubble.tsx`): `pd_piu_safeguards_focal`, `grc_chair`, `grc_member`, all `adb_*` roles, `seah_hq_officer`, `super_admin`, `local_admin`.

Bubble labels also carry a **tier badge** (Spec 12 tier model): "Actor" (blue) when author is the assignee, "Informed" (purple) from `viewerTiers`; observers get no badge.

`ROLE_BUBBLE_STYLE` in `lib/mobile-constants.ts` still exists but is used only to resolve the **role label text** ("L2 PIU", "GRC Chair", "ADB HQ", …) under bubbles; its colour classes are legacy (see `02_design_system.md` §Known deviations).

### 5.2 Special bubble types (as-built additions)

| Type | Visual |
|------|--------|
| Complainant message (`COMPLAINANT_MESSAGE`) | Left-aligned `bg-emerald-50 border-l-4 border-emerald-500`; optional intent badge: Withdraw request (red) / Amendment (blue) / Additional info (emerald); inline English translation strip when `payload.translation_en` differs |
| Resolution record | `bg-green-50 border-l-4 border-green-600`, "Resolution record" byline |
| Field report | `bg-amber-50 border-l-4 border-amber-400`, "Field report" byline |
| Call report | `bg-sky-50 border-l-4 border-sky-400`, "Call report" byline |
| Inline translation | Officer bubbles show `payload.translation_en` as an italic strip below the note |

### 5.3 System pills and event classification (`lib/mobile-constants.ts`)

- `SYSTEM_EVENT_TYPES` render as centered pills — no bubble, **no emoji, pure text** labels via `systemEventLabel()`: CREATED, ACKNOWLEDGED, ESCALATED, ASSIGNED, PRIORITY_CHANGED, RESOLVED (with resolution-category labels), CLOSED, GRC_CONVENED, GRC_DECIDED, SLA_BREACH_FINAL_STEP, REVEAL_ORIGINAL(_CLOSED), VIEWER_ADDED/REMOVED, COMPLAINANT_UPDATED, REASSIGNMENT_REQUESTED, TIER_CHANGED, REPLY_OWNER_CHANGED.
- `THREAD_TASK_EVENT_TYPES` (`TASK_ASSIGNED`, `TASK_DISMISSED`) render as task cards; `TASK_COMPLETED` updates the assignment card in place.
- `NOTIFICATION_ONLY_EVENT_TYPES` (`MENTION`, `TASK_COMPLETED`) are counted for unread badges but never rendered.

### 5.4 Thread filter chips (as-built — semantic, not per-author)

**[SUPERSEDED]** UI_SPEC §2.4's dynamically-generated per-author chips + System chip were replaced by **semantic categories** (`components/thread/FilterChips.tsx`):

```
All | You | Case owner | Supervisor | Observers | Tasks (pending-count badge) | Complainant (count badge)
```

- Owner = `assigned_to_user_id`; Supervisor = `AUTHORITY_ROLES`; Observers = `viewerIds`.
- Each conditional chip appears **only when matching events exist**. No "System" chip — system pills are always visible.
- Filtering is purely client-side (events already loaded); tapping the active chip clears it.
- Rationale: "Case owner / Supervisor / Observers" maps to the organisational hierarchy officers already understand (§10).

### 5.5 Compose bar: @mention + `#` command palette

**@mention** (UI_SPEC §2.8, implemented): typing `@` opens inline autocomplete over case participants (assigned officer + viewers) with `@all` on top; no API call per keystroke. Backend parses mentions from note text on save and writes a `MENTION` event per recipient (`seen=false`, badge-only). `@username` spans are highlighted by `NoteText.tsx`.

**`#` command palette** (as-built addition, `HASH_COMMANDS` in `lib/mobile-constants.ts`): typing `#` in the ComposeBar offers:

| Command | Effect |
|---------|--------|
| `#inspect` | Assign inspection visit (SITE_VISIT task, `@me` default or `@officer`) |
| `#call` | Call complainant → structured call report card |
| `#escalate` | Immediate ESCALATE action |
| `#reassign` | Ask for reassignment (reason-coded request card) |
| `#assign` | Assign ticket to… (triggers @mention picker) |

---

## 6. Tasks and viewers

### 6.1 Tasks

- **Data model:** `ticketing.ticket_tasks` per UI_SPEC §2.6 (task_id, ticket_id, task_type, assigned_to/by, description, due_date, status PENDING|DONE|DISMISSED, …).
- **API (as-built, `ticketing/api/routers/tasks.py`):** `POST /api/v1/tickets/{id}/tasks`, `POST /api/v1/tickets/{id}/tasks/{task_id}/complete`, `GET /api/v1/tickets/{id}/tasks`, `GET /api/v1/users/me/tasks`.
- **Assignable task types (as-built, `TASK_TYPES`):** `SITE_VISIT` ("Inspection visit") and `FOLLOW_UP_CALL` ("Call complainant") only.
  **[SUPERSEDED]** The original four types shrank: `SYSTEM_NOTE` is legacy (displayed as "Field report" when encountered), `DOCUMENT_PHOTO` was dropped — photo documentation happens inside the field-report flow.
- Task cards render in-thread (pending → complete-in-place); pending tasks assigned to you badge the Tasks filter chip and feed the Actor tab / tile deadlines (`my_earliest_task_due_at`).
- Any officer who can see the ticket can assign a task.

### 6.2 Viewers → two-tier model

**[SUPERSEDED]** The single "viewer" concept (UI_SPEC §2.7) evolved into a **two-tier viewer model** ("Spec 12 tier model" in code):

- **Informed** — actively copied-in members (purple accents); can post notes and be @mentioned.
- **Observer** — read-only watchers (gray/blue accents).

`ViewersBar.tsx` renders separate add flows/labels per tier ("Add to Informed" / "Add Observer"). Tier changes emit `TIER_CHANGED` system pills; adds/removes emit `VIEWER_ADDED`/`VIEWER_REMOVED`. Tiers drive the queue's Informed/Observer tabs (§3.1) and the bubble tier badge (§5.1). Viewers API: `ticketing/api/routers/viewers.py`.

---

## 7. Desktop ticket detail (`app/tickets/[id]/page.tsx`)

As-built layout (per the April 28–29 redesign; supersedes the P1-F wireframe's exact column spans):

- **Compact 2-row top bar:** row 1 = back · grievance ID · SEAH badge · action buttons (Acknowledge / Resolve / Escalate / Close) flush right; row 2 = org · location · created · SLA badge · step name · Reply / Task / Assign / Translate toggles flush right. Reply and Assign expand **inline below the top bar** — no always-on panels.
- **Main area:** `grid grid-cols-5` — **thread column `col-span-2`** (left, 40%): FilterChips → ViewersBar → scrollable bubble thread → ComposeBar; **info column `col-span-3`** (right, 60%): Workflow status → Tasks (hidden if none) → Original Grievance → AI Findings (indigo left-border accent, regenerate button) → two-up grid: Complainant card (with PII reveal + edit sheet) + Attachments (complainant files read + officer uploads).
- **ComposeBar is the single note interface** (P1-C: the old Internal Note textarea was removed).
- **Translation review panel:** collapsible third zone, toggled from the header; open-state persisted in `localStorage["grm_translation_panel_open"]`.
- `AssignTaskSheet`: centered modal on desktop, bottom sheet on mobile (P1-D).

---

## 8. SLA colour rules

Urgency scale (`SlaUrgency` in `lib/mobile-constants.ts` / `lib/api.ts`): `overdue | critical | warning | ok | none`.

| Urgency | Meaning | Dot (`SLA_DOT` / `urgencyDotCls`) | Text |
|---------|---------|------|------|
| overdue | deadline passed / breached | `bg-red-500` | `text-red-700` (countdown `text-red-600`) |
| critical | < 24 h remaining | `bg-red-400` | `text-orange-600` (countdown `text-red-500`) |
| warning | < 3 d remaining | `bg-yellow-400` (tokens: `bg-amber-400`) | `text-yellow-700` |
| ok | > 3 d | `bg-green-500` (tokens: `bg-green-400`) | `text-green-700` |
| none | no SLA on step | `bg-gray-300` | `text-gray-400` ("No SLA") |

- `SlaCountdown` (`components/ui/SlaCountdown.tsx`) fetches **live** from `GET /api/v1/tickets/{id}/sla` per row (accepts `initial` to skip the fetch) and formats `-22h` / `3d 4h left` / `Overdue -2d`.
- Queue tiles and row sorting use the **precomputed `sla_deadline_at`** from the list payload instead (see §3.2) — the stale `sla_breached` DB flag is no longer the tile source.
- Used in: queue row dot, thread `SlaSubHeader`, workflow card SLA bar.

---

## 9. SEAH visual treatment

- **Queue row:** red left border (`border-l-4 border-red-500`) + `SeahBadge` (Lucide lock icon, red); **no summary text shown** on mobile rows (content restricted).
- **Thread header:** `SeahBadge` next to the grievance ID.
- **Access control:** `canSeeSeah` from `AuthProvider` (SEAH roles or admin with `seah` workflow track); the server independently enforces 403 — the badge is cosmetic, filtering happens at the DB query level.
- Same queue pages as standard tickets — not a separate route.

---

## 10. Accessibility & South/Central Asia UX research

Recorded from `UI_HANDOFF_thread_redesign.md` (April 2026) — the durable rationale behind the design system's contrast/hierarchy rules.

**Target users:** rural and peri-urban government field officers in Nepal, India, Uzbekistan — mid-career civil servants, not tech-native, on mid-range Androids or shared desktop PCs, often low-bandwidth, dusty/low-brightness/sunlit screens.

**Key finding — "quiet" design fails this audience.** Low-contrast gray labels, borderless cards and generous whitespace are optimised for Retina screens in offices:

- `text-gray-400` (#9CA3AF) fails WCAG AA (~2.8:1 on white; minimum 4.5:1) — invisible in glare or on budget screens. `text-gray-700` (~6.5:1) is the floor for informational text.
- South Asian government UI conventions (NIC India, e-governance portals) train users to scan for **strong hierarchy**: bold headers, coloured borders, explicit dividers. Uzbek government portals follow the same pattern (blue/amber status coding, clear table borders).

**Decisions taken:**

1. Section headers: `text-sm font-semibold text-gray-700 uppercase tracking-wide border-l-[3px] border-blue-500 pl-3` — scannable at arm's length (replaced `text-xs text-gray-400`).
2. AI Findings uses an `border-indigo-400` left border to signal "AI-generated" without a label.
3. Every non-mine bubble carries a `border-l-4` accent — a wall of flat gray cards is indistinguishable at a glance, especially on OLED.
4. Filter chip semantics follow civil-service hierarchy ("Case owner / Supervisor / Observers") rather than generic "Officer".
5. Role emoji (🟢/🟠/🟣/🔵/🔴) were initially retained for cross-literacy recognition, but were **later removed** in favour of text labels + Lucide icons (see `02_design_system.md` — the as-built `ROLE_BUBBLE_STYLE` carries no emoji; system pill labels are pure text).

**Other shared patterns:**

- **Collapsible panels:** panels a role-subset rarely needs are collapsible, not hidden — Translation Review (default closed), Findings (open, supervisor/GRC), Attachments (open), mobile complainant summary card (expanded first open, collapsed after).
- **Language preference:** effective language = `user_roles.preferred_language` → `organizations.default_language` → `en`; DOR seeds `ne`, ADB `en`. `GET/PATCH /api/v1/users/me/preferences` (implemented — `lib/api.ts`). English-preference users see inline translation strips; Nepali users see originals with the panel available for verification.

---

## 11. Spec-vs-code deviations (summary)

| Sprint-spec claim | As-built reality |
|---|---|
| UI_SPEC §2.3 role→colour bubble table (`ROLE_BUBBLE_STYLE` as the bubble system) | Replaced by the 4-context system (§5.1); `ROLE_BUBBLE_STYLE` survives for label text only, with legacy colours |
| Queue tabs My Queue / Watching / Escalated / Resolved (+ CLAUDE.md sidebar) | Participation-tier tabs: Actor / Supervisor / Informed / Observer / High Priority / All Tickets (§3.1) |
| Tile logic "BROKEN — needs decision" (`queue-tile-logic.md`) | Resolved — Option A + task-due extension (§3.2; 15_… Appendix A) |
| Mobile bottom tabs `Queue | All | Profile` | `Queue | All | Tasks` |
| Per-author filter chips + System chip | Semantic chips: You / Case owner / Supervisor / Observers / Tasks / Complainant; no System chip |
| 4 task types (incl. SYSTEM_NOTE, DOCUMENT_PHOTO) | 2 assignable types (SITE_VISIT, FOLLOW_UP_CALL); SYSTEM_NOTE legacy-rendered, DOCUMENT_PHOTO dropped |
| Single "viewer" tier | Two tiers: Informed + Observer (§6.2) |
| Emoji as icons (🔴🟡🟢 dots, 🔒, role chips) | Lucide icons + coloured dot components; no emoji in UI chrome (exception: 🌐 prefix on inline translation strips in `NoteBubble.tsx`) |
| P1-F grid `lg:col-span-2 / 1` with WorkflowStepper above thread | `grid-cols-5` with thread `col-span-2` / info `col-span-3`; workflow status card in info column; stepper lives in `SlaSubHeader` |
| Desktop 3-zone diagram with actions at bottom of context sidebar | 2-row top bar with actions top-right + inline expanding Reply/Assign panels (§7) |
| `/escalated` as a primary nav destination | Route exists but unlinked from nav |
| P1-G open question (stepper compression < 375 px) | Still open — stepper always shows labels |
