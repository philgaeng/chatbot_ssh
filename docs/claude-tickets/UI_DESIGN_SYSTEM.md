# UI Design System — GRM Ticketing

**Session:** April 29, 2026  
**Branch:** `feature/grm-ticketing`  
**Status:** Applied to all existing pages. Use for all new components.

---

## Icon Library

**Lucide React v1.14** — installed in `channels/ticketing-ui/package.json`.

### Rule: Never import from `lucide-react` directly

Always import from `@/lib/icons`:

```tsx
// ✅ Correct
import { IconQueue, IconEscalated, IconClose } from "@/lib/icons";

// ❌ Wrong — creates invisible dependencies and makes icon swaps painful
import { Inbox, TriangleAlert, X } from "lucide-react";
```

### Sizing convention

| Context | Size |
|---------|------|
| Sidebar nav | `size={18}` |
| Inline / button | `size={15}` — pairs with `text-sm` |
| Tiny / badge / label prefix | `size={12}` |
| Event timeline dot | `size={14}` |

### Adding a new icon

1. Find the right Lucide name in `node_modules/lucide-react/dist/lucide-react.d.ts`
2. Add a semantic alias export to `lib/icons.ts`
3. Import the alias from components

```ts
// lib/icons.ts — add your export here, never at the call site
export { Building2 as IconBuilding } from "lucide-react";
```

---

## Color Palette

**5 hue families + gray/slate.** No other hues allowed for new UI work.

| Family | Purpose | Tokens used |
|--------|---------|-------------|
| **Blue** | Primary actions, links, active states, info | `blue-50` `blue-100` `blue-200` `blue-600` `blue-700` `blue-800` |
| **Red** | Danger, SEAH, overdue SLA, destructive | `red-50` `red-100` `red-200` `red-400` `red-500` `red-600` `red-700` `red-800` |
| **Amber** | Warning, escalated, SLA near-breach, supervisor | `amber-50` `amber-100` `amber-200` `amber-600` `amber-700` `amber-800` |
| **Green** | Success, resolved, ok SLA | `green-50` `green-100` `green-200` `green-600` `green-700` |
| **Violet** | GRC-specific only (formal arbitration process) | `violet-50` `violet-100` `violet-200` `violet-600` `violet-700` `violet-800` |
| **Gray** | Text, borders, surfaces, disabled | See WCAG table below |
| **Slate** | Sidebar chrome only | `slate-300` `slate-400` `slate-600` `slate-700` `slate-800` |

### Eliminated families

| Old | Replace with |
|-----|-------------|
| `orange-*` | `amber-*` |
| `yellow-*` | `amber-*` |
| `indigo-*` | `blue-*` or `violet-*` |
| `purple-*` | `violet-*` |
| `teal-*` | `blue-*` |
| `sky-*` | `blue-*` |

---

## WCAG AA Text Compliance

| Token | Hex | Contrast on white | Use for |
|-------|-----|-------------------|---------|
| `text-gray-800` | #1F2937 | **9.7:1** ✅ | Primary headings, key values |
| `text-gray-700` | #374151 | **6.5:1** ✅ | Body text, section content |
| `text-gray-600` | #4B5563 | **5.9:1** ✅ | Secondary labels, metadata, muted-but-informational |
| `text-gray-500` | #6B7280 | 4.48:1 ⚠️ | Disabled fields, placeholder text ONLY |
| `text-gray-400` | #9CA3AF | 2.8:1 ❌ | Decorative separators, disabled icons ONLY |

### Rule

```
text-gray-600  ←  floor for any text that conveys information
text-gray-400  ←  purely decorative / placeholder only — never metadata
```

### Migration note for existing code

Global search and replace in VS Code / Cursor:
- `text-gray-400` → `text-gray-600` (then review: keep only for truly decorative elements)
- `text-gray-500` on informational text → `text-gray-600`

---

## Semantic Token File

`lib/design-tokens.ts` exports:

```ts
import {
  text,              // { heading, body, secondary, muted, sidebarLink, sidebarMuted }
  primary,           // blue tokens
  danger,            // red tokens
  warning,           // amber tokens
  success,           // green tokens
  grc,               // violet tokens
  STATUS_BADGE,      // { OPEN, IN_PROGRESS, ESCALATED, ... } → { bg, text }
  STATUS_LABELS,     // { OPEN: "New", ... }
  PRIORITY_BADGE,    // { HIGH, SENSITIVE, SEAH, NORMAL } → { bg, text }
  SLA_DOT,           // { overdue, critical, warning, ok, none } → bg class
} from "@/lib/design-tokens";
```

Use these in new components instead of raw Tailwind color classes.

---

## Status Badge Mapping

| Status | Color family | Rationale |
|--------|-------------|-----------|
| OPEN | Blue | New, actionable |
| IN_PROGRESS | Blue (lighter) | Ongoing, still primary |
| ESCALATED | Amber | Warning — needs attention |
| GRC_HEARING_SCHEDULED | Violet | Special process |
| RESOLVED | Green | Complete |
| CLOSED | Gray | Archived |

---

## Section Header Pattern

Per South/Central Asia UX research (`UI_HANDOFF_thread_redesign.md`):

```tsx
// ✅ Accessible — strong hierarchy, scannable at arm's length
<h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide border-l-[3px] border-blue-500 pl-3">
  Section Title
</h2>

// ❌ Fails WCAG AA on budget screens
<h2 className="text-xs text-gray-400 uppercase tracking-wide">
  Section Title
</h2>
```

---

## Icon Usage in Labels

```tsx
// Section headers with icon prefix (add visual anchor)
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

## Do Not Use Emoji as Icons

Emoji rendering varies across fonts, platforms, and browsers — especially problematic on Android and older Windows. They also cannot be sized precisely, cannot be colored to match the UI, and create alignment issues with text.

| Emoji was | Replace with |
|-----------|-------------|
| 🎫 | `<IconQueue />` |
| 📋 | `<IconAllTickets />` |
| 🔺 | `<IconEscalated />` |
| 📊 | `<IconReports />` |
| ⚙️ | `<IconSettings />` |
| ❓ | `<IconHelp />` |
| 🔔 | `<IconBell />` |
| 🔒 | `<IconLock />` |
| ✅ | `<IconAcknowledge />` |
| 🏁 | `<IconResolve />` |
| 📝 | `<IconNote />` |
| 💬 | `<IconReply />` |
| 👤 | `<IconUser />` |
| 🏛️ | `<IconGrcConvene />` |
| ⚖️ | `<IconGrcDecide />` |
| 📱 | `<IconComplainantNotified />` |
| ⚠️ | `<IconEscalated />` |
| 🌐 | `<IconTranslation />` |
| 📄 | `<IconReveal />` |
| 🧠 | `<IconFindings />` |
| 📎 | `<IconAttachment />` |

**Exception:** Role emoji (🟢 L1, 🟠 L2, 🟣 GRC, 🔵 ADB, 🔴 SEAH) in the bubble color system (`lib/mobile-constants.ts`) are retained intentionally — they encode role identity, render identically across literacy levels, and are part of the 4-context design spec.

---

## Files Changed in This Session

| File | Change |
|------|--------|
| `package.json` | Added `lucide-react: ^1.14.0` |
| `lib/icons.ts` | **NEW** — centralized icon exports (semantic aliases) |
| `lib/design-tokens.ts` | **NEW** — constrained color palette + semantic maps |
| `components/AppShell.tsx` | Nav emoji → Lucide; `text-gray-400` → `text-gray-600` |
| `components/ui/Badge.tsx` | Uses design-tokens; `yellow/orange/purple` → `amber/violet`; Lucide lock in SEAH badge |
| `components/ui/VaultReveal.tsx` | Modal/overlay emoji → Lucide |
| `app/queue/page.tsx` | `text-gray-400` metadata → `text-gray-600`; arrow emoji → `<IconChevronRight />` |
| `app/tickets/[id]/page.tsx` | EVENT_ICON emoji map → Lucide component map; action buttons emoji → Lucide; all `text-gray-400` informational text fixed |
