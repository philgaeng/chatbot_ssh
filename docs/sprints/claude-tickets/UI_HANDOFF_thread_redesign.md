# UI Handoff — Thread Redesign & South/Central Asia Design Research

**Branch:** `feature/grm-ticketing`  
**Sessions:** April 28–29, 2026  
**Scope:** Desktop ticket detail page, shared thread components, mobile filter chips

---

## What Was Built

### New shared components — `channels/ticketing-ui/components/thread/`

All components are used by both `/tickets/[id]` (desktop) and `/m/tickets/[id]` (mobile).

| File | Purpose |
|------|---------|
| `NoteBubble.tsx` | Message bubble with 4-context color system (see below) |
| `FilterChips.tsx` | Horizontal scrollable chip bar — semantic, not per-author |
| `SystemPill.tsx` | Centered pill for system events (escalation, resolution, etc.) |
| `TaskCard.tsx` | In-thread task card + `AssignTaskSheet` bottom sheet |
| `ComposeBar.tsx` | Note input with @mention autocomplete |
| `SlaSubHeader.tsx` | SLA countdown strip + `WorkflowMiniStepper` |
| `ViewersBar.tsx` | Viewer avatar row + add/remove viewer sheet |
| `NoteText.tsx` | Renders note text with @mention highlighting |

### Desktop `/tickets/[id]` — full redesign

**Layout:** `flex flex-col h-full` root → compact 2-row top bar → `grid grid-cols-5` main area.

- **Top bar row 1:** Back ← | grievance_id | SEAH badge | action buttons (Acknowledge / Resolve / Escalate / Close) flush right
- **Top bar row 2:** org · location · created · SLA badge · step name | Reply / Task / Assign / Translate toggles flush right
- **Expandable panels:** Reply (textarea + Send) and Assign (officer select + Save) expand inline below the top bar — no always-on columns
- **Grid 2/5 + 3/5:** Thread column (left 40%) + Info column (right 60%)
- **Info column order:** Workflow status → Tasks (hidden if none) → Original Grievance (full width) → AI Findings (full width) → `grid grid-cols-2`: Complainant card + Attachments

### Mobile `/m/tickets/[id]` — filter chip update

Filter chips changed from per-author dynamic list + System to **5 semantic categories**:

```
All | 👤 You | 🔵 Case owner | 🟠 Supervisor | 👁 Observers | 📋 Tasks
```

- Each chip appears **only when matching events exist** in the thread
- Filter logic: owner = `assigned_to_user_id`, supervisor = `AUTHORITY_ROLES`, observers = `viewerIds`
- "System" chip removed entirely from mobile (system pills are always visible in the thread)

---

## 4-Context Bubble Color System (`NoteBubble.tsx`)

Color encodes **case relationship**, not role title. Role identity is still shown in the label.

| Context | Who | Visual |
|---------|-----|--------|
| **Case owner** | `created_by_user_id === assigned_to_user_id` | `bg-blue-50 border-l-4 border-blue-600` + bold blue label |
| **Authority / supervisor** | role in `AUTHORITY_ROLES` | `bg-amber-50 border-l-4 border-amber-500` + bold amber label |
| **Viewer / observer** | `user_id` in `viewerIds` set | `bg-gray-50 border-l-4 border-gray-300` + gray label |
| **Other officer** | default | `bg-gray-100 border-l-4 border-gray-400` + gray label |
| **Current user (you)** | `isMine === true` | Right-aligned `bg-blue-500 text-white` bubble, no border |

`AUTHORITY_ROLES` is exported from `lib/mobile-constants.ts` and shared by `FilterChips`, `NoteBubble`, and both page components.

---

## South / Central Asia UX Research Findings

### Target users
Rural and peri-urban government field officers in Nepal, India, and Uzbekistan. Typically:
- Mid-career civil servants, not tech-native
- Using Android phones (mid-range) or shared desktop PCs
- Often in low-bandwidth or intermittent connectivity
- Screens may be dusty, low brightness, or viewed in sunlight

### Key finding: "quiet" design fails this audience

Modern Western design trends (low-contrast gray labels, no borders, generous whitespace) are optimized for high-DPI Retina screens in well-lit offices. For our users:

- **`text-gray-400` (#9CA3AF) fails WCAG AA** — contrast ratio ~2.8:1 against white (minimum is 4.5:1). Section headers in this color are invisible in glare or on budget screens.
- **`text-gray-700` (#374151) passes at ~6.5:1** — use this as the floor for all informational text.
- South Asian government UI conventions (NIC India, e-governance portals) use **strong visual hierarchy**: bold headers, colored borders, explicit section dividers. Users are trained to scan for these.
- Uzbekistan government portals follow a similar pattern — blue/amber color coding for status, clear table borders.

### Design decisions taken

1. **Section headers:** Changed from `text-xs text-gray-400 uppercase` to `text-sm font-semibold text-gray-700 uppercase tracking-wide border-l-[3px] border-blue-500 pl-3`. The left-border accent is scannable at arm's length and survives low contrast.

2. **AI Findings section:** Uses `border-indigo-400` left border to signal "AI-generated" without a label — distinct from the blue used for user-action sections.

3. **Bubble borders:** Every non-mine bubble has a `border-l-4` accent. Without it, a wall of gray `bg-gray-100` cards is indistinguishable at a glance — especially on OLED screens that crush dark grays.

4. **Emoji in labels:** Kept role emoji (🟢 L1, 🟠 L2, 🟣 GRC, 🔵 ADB, 🔴 SEAH) — emoji are universally recognized across literacy levels and languages, and render identically regardless of font.

5. **Filter chip semantics:** "Case owner / Supervisor / Observers" maps directly to the organizational hierarchy these officers understand. "Officer" (the old label) meant nothing without context; role hierarchy means everything in South Asian civil service culture.

---

## Key Constants & Where They Live

```ts
// lib/mobile-constants.ts
AUTHORITY_ROLES     // Set<string> — roles above L1, used by FilterChips + NoteBubble
ROLE_BUBBLE_STYLE   // Record<role, {bubbleCls, labelCls, emoji, label}>
DEFAULT_BUBBLE_STYLE
getRoleBubbleStyle(actorRole)
SYSTEM_EVENT_TYPES  // renders as SystemPill, never NoteBubble
TASK_EVENT_TYPES    // renders as TaskCard
NOTIFICATION_ONLY_EVENT_TYPES  // MENTION — counted but never rendered
```

---

## Known Gaps / Next Steps

| Priority | Item |
|----------|------|
| P2 | Mobile queue page (`/m/queue`) — urgency dots, SLA meta, SEAH badge, pull-to-refresh |
| P3 | Desktop queue page (`/queue`) — same content, sidebar layout |
| P4 | Responsive / navigation polish |
| P5 | Desktop settings page audit |
| Tech debt | `WorkflowMiniStepper` only receives `ticket.current_step` (one step). Needs full step list from workflow API to show the complete escalation path. |
| Tech debt | `mentionParticipants` in desktop page uses raw user IDs as labels — needs display name resolution from users API. |

---

## Commit Log (this work)

```
b2a9e82  fix(ui): move viewerIds before filteredEvents to fix TS declaration order
9f3be8c  feat(ui): semantic filter chips — Case owner, Supervisor, Observers
c1d3866  feat(ui): desktop ticket detail redesign + 4-context bubble colors
31b5bed  feat(ui): extract shared thread components + desktop layout redesign
```
