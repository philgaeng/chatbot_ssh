/**
 * design-tokens.ts — GRM UI constrained color palette.
 *
 * RULE: import semantic tokens from here. Never scatter raw Tailwind color
 * classes like `text-orange-600` or `bg-indigo-100` across files — it
 * creates the sprawl we are fixing.
 *
 * ── Palette (5 hue families + gray/slate for chrome) ─────────────────────────
 *
 *   BLUE    Primary actions, active states, primary links, info
 *   RED     Danger, SEAH, overdue SLA, destructive
 *   AMBER   Warning, escalated, supervisor context, pending
 *   GREEN   Success, resolved, ok SLA
 *   VIOLET  GRC-specific (special legal/arbitration process)
 *   GRAY    All text, borders, surfaces (WCAG-compliant floors below)
 *   SLATE   Sidebar chrome only
 *
 * ── WCAG AA compliance ────────────────────────────────────────────────────────
 *
 *   NEVER use text-gray-400 (#9CA3AF) for informational text — contrast 2.8:1
 *   NEVER use text-gray-500 (#6B7280) for informational text — contrast 4.48:1 (fails)
 *   FLOOR: text-gray-600 (#4B5563) = 5.9:1  ✓  muted/secondary labels
 *   BODY:  text-gray-700 (#374151) = 6.5:1  ✓  default body text, section headers
 *   MAIN:  text-gray-800 (#1F2937) = 9.7:1  ✓  primary headings
 *   text-gray-400/500 ONLY for: placeholder, decorative separator, disabled state
 *
 * ── Eliminated hue families ───────────────────────────────────────────────────
 *
 *   orange-*  → amber-* (same semantic intent, one family)
 *   yellow-*  → amber-* (same semantic intent, one family)
 *   indigo-*  → blue-* or violet-* depending on context
 *   purple-*  → violet-* (more distinctive for GRC, cleaner)
 *   teal-*    → blue-*
 *   sky-*     → blue-*
 */

// ── Text ──────────────────────────────────────────────────────────────────────

export const text = {
  /** Primary headings: 9.7:1 contrast */
  heading:       "text-gray-800",
  /** Body / section content: 6.5:1 */
  body:          "text-gray-700",
  /** Secondary labels (muted but accessible): 5.9:1 */
  secondary:     "text-gray-600",
  /** Decorative / placeholder / disabled ONLY — not for informational text */
  muted:         "text-gray-400",
  /** Sidebar link inactive */
  sidebarLink:   "text-slate-300",
  /** Sidebar label muted */
  sidebarMuted:  "text-slate-400",
} as const;

// ── Semantic color roles ──────────────────────────────────────────────────────

/** Primary: actions, links, active states */
export const primary = {
  text:          "text-blue-700",
  textLight:     "text-blue-600",
  bg:            "bg-blue-600",
  bgHover:       "hover:bg-blue-700",
  bgLight:       "bg-blue-50",
  bgMid:         "bg-blue-100",
  border:        "border-blue-600",
  borderLight:   "border-blue-200",
  borderAccent:  "border-blue-500",
  ring:          "focus:ring-blue-400",
} as const;

/** Danger: SEAH, overdue SLA, destructive actions */
export const danger = {
  text:          "text-red-700",
  textStrong:    "text-red-800",
  bg:            "bg-red-600",
  bgHover:       "hover:bg-red-700",
  bgLight:       "bg-red-50",
  bgMid:         "bg-red-100",
  border:        "border-red-600",
  borderLight:   "border-red-200",
  borderAccent:  "border-red-400",
} as const;

/** Warning: escalated tickets, SLA near-breach, pending states, supervisor context */
export const warning = {
  text:          "text-amber-700",
  textStrong:    "text-amber-800",
  bg:            "bg-amber-600",
  bgHover:       "hover:bg-amber-700",
  bgLight:       "bg-amber-50",
  bgMid:         "bg-amber-100",
  border:        "border-amber-500",
  borderLight:   "border-amber-200",
} as const;

/** Success: resolved, ok SLA, positive status */
export const success = {
  text:          "text-green-700",
  bg:            "bg-green-600",
  bgHover:       "hover:bg-green-700",
  bgLight:       "bg-green-50",
  bgMid:         "bg-green-100",
  border:        "border-green-500",
  borderLight:   "border-green-200",
} as const;

/** GRC-specific: hearing scheduled, arbitration, formal process */
export const grc = {
  text:          "text-violet-700",
  bg:            "bg-violet-600",
  bgHover:       "hover:bg-violet-700",
  bgLight:       "bg-violet-50",
  bgMid:         "bg-violet-100",
  border:        "border-violet-500",
  borderLight:   "border-violet-200",
} as const;

// ── Status badge colors (semantic map used by StatusBadge component) ──────────

export const STATUS_BADGE: Record<string, { bg: string; text: string }> = {
  OPEN:                   { bg: "bg-blue-100",   text: "text-blue-800"   },
  IN_PROGRESS:            { bg: "bg-blue-50",    text: "text-blue-700"   },
  ESCALATED:              { bg: "bg-amber-100",  text: "text-amber-800"  },
  GRC_HEARING_SCHEDULED:  { bg: "bg-violet-100", text: "text-violet-800" },
  RESOLVED:               { bg: "bg-green-100",  text: "text-green-800"  },
  CLOSED:                 { bg: "bg-gray-100",   text: "text-gray-700"   },
} as const;

export const STATUS_LABELS: Record<string, string> = {
  OPEN:                   "New",
  IN_PROGRESS:            "In Progress",
  ESCALATED:              "Escalated",
  GRC_HEARING_SCHEDULED:  "GRC Hearing",
  RESOLVED:               "Resolved",
  CLOSED:                 "Closed",
} as const;

// ── Priority badge colors ─────────────────────────────────────────────────────

export const PRIORITY_BADGE: Record<string, { bg: string; text: string }> = {
  HIGH:      { bg: "bg-red-100",   text: "text-red-800"   },
  SENSITIVE: { bg: "bg-red-100",   text: "text-red-800"   },
  SEAH:      { bg: "bg-red-100",   text: "text-red-800"   },
  NORMAL:    { bg: "bg-gray-100",  text: "text-gray-700"  },
} as const;

// ── SLA urgency dot colors ────────────────────────────────────────────────────

export const SLA_DOT: Record<string, string> = {
  overdue:  "bg-red-500",
  critical: "bg-red-400",
  warning:  "bg-amber-400",
  ok:       "bg-green-400",
  none:     "bg-gray-300",
} as const;
