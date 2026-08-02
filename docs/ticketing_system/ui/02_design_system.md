# Officer Portal — Design System

> **Status:** As-built, July 2026. Consolidated from `docs/sprints/archive/claude-tickets/UI_DESIGN_SYSTEM.md` (April 2026), reconciled with the thread redesign (`UI_HANDOFF_thread_redesign.md`) and current code in `channels/ticketing-ui/`.
> Applies to all new components in `channels/ticketing-ui/`.
> **On-screen wording (voice, plain language, glossary):** see [`05_ui_copy_style.md`](05_ui_copy_style.md) — the copy source of truth. This doc covers the *visual* system; that one covers *words*.

---

## 1. Icon library

**Lucide React** (`lucide-react` in `channels/ticketing-ui/package.json`). No other icon or UI library. Tailwind CSS v4 via `@tailwindcss/postcss` — no extra setup beyond `npm install`.

### Rule: never import from `lucide-react` directly

Always import semantic aliases from `@/lib/icons`:

```tsx
// Correct
import { IconQueue, IconEscalated, IconClose } from "@/lib/icons";

// Wrong — invisible dependencies, painful icon swaps
import { Inbox, TriangleAlert, X } from "lucide-react";
```

To add an icon: find the Lucide name, add a semantic alias export to `lib/icons.tsx`, import the alias.

*Known deviation:* a few thread components (`NoteBubble.tsx`, `FilterChips.tsx`, `SlaCountdown.tsx`) import Lucide names directly. Treat as tech debt; do not copy the pattern.

### Sizing convention

| Context | Size |
|---------|------|
| Sidebar nav | `size={18}` |
| Inline / button (pairs with `text-sm`) | `size={15}` |
| Tiny / badge / label prefix | `size={12}` |
| Event timeline dot | `size={14}` |

---

## 2. Colour palette

**5 hue families + gray/slate.** No other hues for new UI work.

| Family | Purpose | Tokens used |
|--------|---------|-------------|
| **Blue** | Primary actions, links, active states, info, case-owner bubbles | `blue-50…blue-800` |
| **Red** | Danger, SEAH, overdue SLA, destructive | `red-50…red-800` |
| **Amber** | Warning, escalated, SLA near-breach, authority/supervisor bubbles, field reports | `amber-50…amber-800` |
| **Green** | Success, resolved, ok SLA, resolution records | `green-50…green-700` |
| **Violet** | GRC-specific only (formal arbitration process) | `violet-50…violet-800` |
| **Gray** | Text, borders, surfaces, disabled | see WCAG table |
| **Slate** | Sidebar chrome only | `slate-300…slate-800` |

### Eliminated families

| Old | Replace with |
|-----|--------------|
| `orange-*` | `amber-*` |
| `yellow-*` | `amber-*` |
| `indigo-*` | `blue-*` or `violet-*` |
| `purple-*` | `violet-*` |
| `teal-*` | `blue-*` |
| `sky-*` | `blue-*` |

### Known deviations still in code (do not extend)

- `lib/mobile-constants.ts` `ROLE_BUBBLE_STYLE` still carries `purple-*`, `teal-*`, `emerald-*` classes. Since the 4-context bubble redesign these classes are effectively dormant — the map is used for **role label text** only — but the colour values predate the constrained palette.
- `NoteBubble.tsx` uses `emerald-*` for complainant bubbles and `sky-*` for call reports; `queue/page.tsx` tiles and `mobile-constants.ts` urgency helpers use `yellow-*`; the AI Findings header uses `indigo-*` (deliberate, §6). Reconcile toward the constrained palette when touching these files, or consciously admit emerald/sky as additional semantic families — do not mix both approaches.

---

## 3. WCAG AA text compliance

Grounded in the South/Central Asia UX research (see `01_ui_spec.md` §10): officers work on budget screens in glare — low-contrast gray is invisible.

| Token | Hex | Contrast on white | Use for |
|-------|-----|-------------------|---------|
| `text-gray-800` | #1F2937 | 9.7:1 ✅ | Primary headings, key values |
| `text-gray-700` | #374151 | 6.5:1 ✅ | Body text, section content |
| `text-gray-600` | #4B5563 | 5.9:1 ✅ | Secondary labels, metadata |
| `text-gray-500` | #6B7280 | 4.48:1 ⚠️ | Disabled fields, placeholders ONLY |
| `text-gray-400` | #9CA3AF | 2.8:1 ❌ | Decorative separators, disabled icons ONLY |

```
text-gray-600  ←  floor for any text that conveys information
text-gray-400  ←  purely decorative / placeholder only — never metadata
```

---

## 4. Semantic token file

`lib/design-tokens.ts` exports — use these instead of raw Tailwind colour classes in new components:

```ts
import {
  text,              // { heading, body, secondary, muted, sidebarLink, sidebarMuted }
  primary,           // blue tokens
  danger,            // red tokens
  warning,           // amber tokens
  success,           // green tokens
  grc,               // violet tokens
  STATUS_BADGE,      // { OPEN, IN_PROGRESS, ... } → { bg, text }
  STATUS_LABELS,     // { OPEN: "New", ... }
  PRIORITY_BADGE,    // { HIGH, SENSITIVE, SEAH, NORMAL } → { bg, text }
  SLA_DOT,           // { overdue, critical, warning, ok, none } → bg class
} from "@/lib/design-tokens";
```

### Status badges (as-built values)

| Status | Label | Colour |
|--------|-------|--------|
| OPEN | "New" | blue-100 / blue-800 |
| IN_PROGRESS | "In Progress" | blue-50 / blue-700 |
| ESCALATED | "Escalated" | amber-100 / amber-800 |
| GRC_HEARING_SCHEDULED | "GRC Hearing" | violet-100 / violet-800 |
| RESOLVED | "Resolved" | green-100 / green-800 |
| CLOSED | "Closed" | gray-100 / gray-700 |

### Priority badges

HIGH / SENSITIVE / SEAH → red-100 / red-800; NORMAL → gray-100 / gray-700.

### SLA urgency dots (`SLA_DOT`)

overdue `bg-red-500` · critical `bg-red-400` · warning `bg-amber-400` · ok `bg-green-400` · none `bg-gray-300`.
(The parallel `urgencyDotCls()` helper in `lib/mobile-constants.ts` uses `bg-yellow-400`/`bg-green-500` for warning/ok — converge on the tokens file when touched.)

---

## 5. Bubble colour vocabulary (thread)

The thread's colour system is **contextual, not role-based** — full spec in `01_ui_spec.md` §5. Design-system summary:

| Semantic | Colour |
|----------|--------|
| You | solid `blue-500`, white text, right-aligned |
| Case owner | `blue-50` + `border-blue-600` |
| Authority / supervisor | `amber-50` + `border-amber-500` |
| Viewer / other officer | `gray-50/100` + gray border |
| Complainant | `emerald-50` + `border-emerald-500` |
| Resolution record | `green-50` + `border-green-600` |
| Field report | `amber-50` + `border-amber-400` |
| Call report | `sky-50` + `border-sky-400` |

Every non-mine bubble carries a `border-l-4` accent — flat gray cards are indistinguishable on low-quality screens (research decision #3).

---

## 6. Section header pattern

```tsx
// Accessible — strong hierarchy, scannable at arm's length
<h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide border-l-[3px] border-blue-500 pl-3">
  Section Title
</h2>

// Fails WCAG AA on budget screens — do not use
<h2 className="text-xs text-gray-400 uppercase tracking-wide">Section Title</h2>
```

AI-generated sections (Findings) use a `border-indigo-400` left border instead of blue — a deliberate "AI content" signal distinct from user-action sections.

---

## 7. Icon usage in labels

```tsx
// Section headers with icon prefix
<h2 className="text-sm font-semibold text-blue-700 flex items-center gap-1.5">
  <IconFindings size={15} />Findings
</h2>

// Action buttons (icon left of text)
<button className="flex items-center gap-1.5 ...">
  <IconAcknowledge size={15} />Acknowledge
</button>

// Metadata labels (tiny icon)
<label className="text-xs font-semibold text-gray-600 flex items-center gap-1">
  <IconLock size={12} />Internal Note
</label>
```

---

## 8. No emoji as icons

Emoji render inconsistently across fonts/platforms (worst on Android and older Windows), cannot be sized or coloured to match the UI, and misalign with text. All UI chrome uses Lucide icons or coloured components:

| Emoji was | Replaced with |
|-----------|---------------|
| 🎫 📋 🔺 📊 ⚙️ ❓ 🔔 | `IconQueue` `IconAllTickets` `IconEscalated` `IconReports` `IconSettings` `IconHelp` `IconBell` |
| 🔒 | `IconLock` (SEAH badge) |
| ✅ 🏁 📝 💬 👤 | `IconAcknowledge` `IconResolve` `IconNote` `IconReply` `IconUser` |
| 🏛️ ⚖️ 📱 🌐 📄 🧠 📎 | `IconGrcConvene` `IconGrcDecide` `IconComplainantNotified` `IconTranslation` `IconReveal` `IconFindings` `IconAttachment` |
| 🔴 🟡 🟢 urgency dots | `UrgencyDot` component (coloured `rounded-full` span) |

**Update to the April rule:** the original exception that kept role emoji (🟢 L1, 🟠 L2, 🟣 GRC, 🔵 ADB, 🔴 SEAH) in the bubble system was **retired** — the as-built `ROLE_BUBBLE_STYLE` carries no emoji field and `systemEventLabel()` is documented "no emoji, pure text". Remaining literal emoji in code: the 🌐 prefix on inline translation strips in `NoteBubble.tsx` (minor, replace with `IconTranslation` when touched).
