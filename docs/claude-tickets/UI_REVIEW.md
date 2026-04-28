# UI Review — Design Proposals & Open Questions

> Claude proposes. Philippe decides. Nothing is coded until the relevant section is marked **✅ approved** or revised.

---

## Design direction (locked)

- **Mobile is primary.** Desktop is derived from mobile, not the other way around.
- The mobile thread screen (`/m/tickets/[id]`) is the gold standard.

---

## Priority 1 — Desktop thread view + shared `components/thread/`

### ✅ P1-A · Shared component split — APPROVED

8 components to `components/thread/`. `PrimaryCtaBar`, `MoreActionsSheet` stay mobile-only.
`AssignTaskSheet` → `components/thread/` (centered modal on desktop, bottom sheet on mobile).

---

### ✅ P1-B · Desktop left column — APPROVED

Thread card with FilterChips + ViewersBar + 60vh scrollable body + ComposeBar.
`WorkflowStepper` moves to left column above thread (replaces old Workflow card).

---

### ✅ P1-C · Internal Note — APPROVED: Option A

Remove Internal Note textarea from ActionPanel. ComposeBar is the single note interface.

---

### ✅ P1-D · AssignTaskSheet — APPROVED: Option A

`AssignTaskSheet` → `components/thread/`. Desktop: centered modal. Mobile: bottom sheet.

---

### ✅ P1-E · Escalate/Close on desktop — APPROVED

Stays in ActionPanel. No change.

---

### ✅ P1-F · Desktop page layout — APPROVED

```
┌─────────────────────────────────────────────────────────────────────┐
│  TOP ROW                                                            │
│  ┌──────────────────────────────┐  ┌──────────────────────────────┐ │
│  │  Ticket header               │  │  Actions                     │ │
│  │  grievance_id · SEAH badge   │  │  [✅ Acknowledge]            │ │
│  │  status · priority · dates   │  │  [🔺 Escalate] [🏁 Resolve] │ │
│  │                              │  │  [GRC Convene / Decide]      │ │
│  │                              │  │  [Reply to complainant]      │ │
│  │                              │  │  [Assign officer]            │ │
│  │                              │  │  [Reassign to teammate]      │ │
│  └──────────────────────────────┘  └──────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│  MAIN AREA (two columns)                                            │
│  ┌──────────────────────────────┐  ┌──────────────────────────────┐ │
│  │  LEFT  (lg:col-span-2)      │  │  RIGHT  (lg:col-span-1)      │ │
│  │                              │  │                              │ │
│  │  WorkflowStepper             │  │  Original Grievance          │ │
│  │  FilterChips                 │  │  (summary, categories, loc)  │ │
│  │  ViewersBar                  │  │  ──────────────────────────  │ │
│  │  ── thread ──                │  │  🧠 Findings (AI summary)   │ │
│  │  bubbles / pills / tasks     │  │  ──────────────────────────  │ │
│  │  ── compose ──               │  │  Complainant                 │ │
│  │  ComposeBar                  │  │  (name, phone reveal, etc)   │ │
│  └──────────────────────────────┘  │  ──────────────────────────  │ │
│                                    │  Attachments                 │ │
│                                    └──────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

- "Grievance Summary" card → renamed **"Original Grievance"**
- All actions (Acknowledge, Escalate, Resolve, Close, Reply, Assign, Reassign) in top-right card
- AssignPanel + ReassignPanel folded into the top-right Actions card

---

### ✅ P1-G · Mobile workflow stepper — APPROVED

**Algorithm:** show preceding + current + next + last. Ellipsis (···) when last is not adjacent to next.

```
Steps array:  [S0, S1, S2, S3, S4, S5, S6]
At idx 0:     S0(current) — S1(next) ··· S6(last)
At idx 2:     S1(prev) — S2(current) — S3(next) ··· S6(last)
At idx 5:     S4(prev) — S5(current) — S6(next=last)   ← no ellipsis
At idx 6:     S5(prev) — S6(current=last)
```

Ellipsis rule: show `···` connector between next and last only when `lastIdx - nextIdx > 1`.

**Labels:** short derived from `step_key` — e.g. `LEVEL_1_SITE` → "L1 Site", `LEVEL_3_GRC` → "L3 GRC", `SEAH_LEVEL_1_NATIONAL` → "SEAH L1". A `stepShortLabel(step_key)` helper goes in `mobile-constants.ts`.

**Dot styles:**
- Completed (idx < current): filled blue ●, solid connecting line
- Current: filled blue ● with ring, bold label
- Next / future: empty circle ○, gray label
- Last (if future): empty circle ○, gray label, dashed connector from next

**Placement:** between SLA strip and filter chips (sticky header area).

→ **Remaining open question:** On very small screens (375px) 4 visible nodes may be tight.
Should the stepper compress to icon-only (no labels) below a breakpoint, or always show labels?

---

## Priority 2 — Mobile queue polish

*(Will add proposals once P1 is fully coded)*

---

## Priority 3 — Desktop queue polish

*(Will add proposals once P1 is fully coded)*

---

## Priority 4 — Responsive / navigation polish

*(Will add proposals once P1 is fully coded)*

---

## Priority 5 — Desktop settings page audit

*(Will add proposals once P1 is fully coded)*
