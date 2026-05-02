/**
 * Shared constants for the mobile-first thread UI (UI_SPEC.md §2.3).
 * Used by both /m/* routes and the desktop thread view.
 */

// ── Role → bubble style mapping ───────────────────────────────────────────────
// Changing this file changes every bubble in both mobile and desktop.

export interface RoleBubbleStyle {
  /** Tailwind classes for left border + background on left-side bubbles */
  bubbleCls: string;
  /** Tailwind color for the role label chip */
  labelCls: string;
  /** Short human-readable role label */
  label: string;
}

export const ROLE_BUBBLE_STYLE: Record<string, RoleBubbleStyle> = {
  site_safeguards_focal_person:  { bubbleCls: "bg-green-50  border-l-4 border-green-400", labelCls: "text-green-700",  label: "L1 Officer" },
  pd_piu_safeguards_focal:       { bubbleCls: "bg-amber-50  border-l-4 border-amber-400", labelCls: "text-amber-700",  label: "L2 PIU" },
  grc_chair:                     { bubbleCls: "bg-purple-50 border-l-4 border-purple-400",labelCls: "text-purple-700", label: "GRC Chair" },
  grc_member:                    { bubbleCls: "bg-purple-50 border-l-4 border-purple-300",labelCls: "text-purple-600", label: "GRC" },
  adb_national_project_director: { bubbleCls: "bg-teal-50   border-l-4 border-teal-400",  labelCls: "text-teal-700",   label: "ADB" },
  adb_hq_safeguards:             { bubbleCls: "bg-teal-50   border-l-4 border-teal-400",  labelCls: "text-teal-700",   label: "ADB HQ" },
  adb_hq_project:                { bubbleCls: "bg-teal-50   border-l-4 border-teal-400",  labelCls: "text-teal-700",   label: "ADB" },
  adb_hq_exec:                   { bubbleCls: "bg-teal-50   border-l-4 border-teal-400",  labelCls: "text-teal-700",   label: "ADB Exec" },
  seah_national_officer:         { bubbleCls: "bg-red-50    border-l-4 border-red-400",   labelCls: "text-red-700",    label: "SEAH" },
  seah_hq_officer:               { bubbleCls: "bg-red-50    border-l-4 border-red-400",   labelCls: "text-red-700",    label: "SEAH HQ" },
  super_admin:                   { bubbleCls: "bg-slate-100 border-l-4 border-slate-400", labelCls: "text-slate-700",  label: "Admin" },
  local_admin:                   { bubbleCls: "bg-slate-100 border-l-4 border-slate-400", labelCls: "text-slate-700",  label: "Admin" },
  system:                        { bubbleCls: "",                                          labelCls: "text-gray-400",   label: "System" },
  complainant:                   { bubbleCls: "bg-emerald-50 border-l-4 border-emerald-500", labelCls: "text-emerald-700", label: "Complainant" },
};

/** Fallback for unknown roles */
export const DEFAULT_BUBBLE_STYLE: RoleBubbleStyle = {
  bubbleCls: "bg-gray-100 border-l-4 border-gray-400",
  labelCls: "text-gray-600",
  label: "Officer",
};

export function getRoleBubbleStyle(actorRole: string | null | undefined): RoleBubbleStyle {
  if (!actorRole) return DEFAULT_BUBBLE_STYLE;
  return ROLE_BUBBLE_STYLE[actorRole] ?? DEFAULT_BUBBLE_STYLE;
}

// ── Authority roles (supervisors / higher authority) ─────────────────────────

export const AUTHORITY_ROLES = new Set([
  "pd_piu_safeguards_focal",
  "grc_chair", "grc_member",
  "adb_national_project_director", "adb_hq_safeguards", "adb_hq_project", "adb_hq_exec",
  "seah_hq_officer",
  "super_admin", "local_admin",
]);

// ── Task types ────────────────────────────────────────────────────────────────
// icon = Lucide icon name — rendered by TaskTypeIcon in lib/icons.tsx
// hash = shortcut trigger in the ComposeBar # command palette

export const TASK_TYPES = [
  { key: "SITE_VISIT",        label: "Inspection visit",    icon: "MapPin",        hash: "inspect" },
  { key: "DOCUMENT_PHOTO",    label: "Site photo required", icon: "Camera",        hash: "photo"   },
  { key: "FOLLOW_UP_CALL",    label: "Call complainant",    icon: "Phone",         hash: "call"    },
  { key: "SYSTEM_NOTE",       label: "Field report",        icon: "FileText",      hash: "report"  },
  { key: "ESCALATION_REVIEW", label: "Escalation review",   icon: "ClipboardList", hash: "review"  },
] as const;

export type TaskTypeKey = (typeof TASK_TYPES)[number]["key"];

// ── # command palette ─────────────────────────────────────────────────────────
// Shown when the officer types # in the ComposeBar.
// Two groups separated by a divider:
//   "task"   — creates a TicketTask assigned to the current user
//   "report" — switches compose bar to report mode (submits as FIELD_REPORT action)
//   "action" — performs an immediate ticket action (ESCALATE)
//   "assign" — triggers @mention autocomplete to pick the assignee

export type HashCommandKind = "task" | "report" | "action" | "assign";

export interface HashCommand {
  hash: string;
  label: string;
  icon: string;
  kind: HashCommandKind;
  /** task key (kind=task only) */
  taskKey?: string;
  /** backend action_type (kind=action only) */
  action?: string;
}

export const HASH_COMMANDS: HashCommand[] = [
  // ── Task shortcuts (creates TicketTask assigned to self) ──
  { hash: "inspect",  label: "Inspection visit",    icon: "MapPin",        kind: "task",   taskKey: "SITE_VISIT"        },
  { hash: "photo",    label: "Site photo required",  icon: "Camera",        kind: "task",   taskKey: "DOCUMENT_PHOTO"    },
  { hash: "call",     label: "Call complainant",     icon: "Phone",         kind: "task",   taskKey: "FOLLOW_UP_CALL"    },
  { hash: "review",   label: "Escalation review",    icon: "ClipboardList", kind: "task",   taskKey: "ESCALATION_REVIEW" },
  // ── Direct actions ────────────────────────────────────────
  { hash: "report",   label: "Write field report",   icon: "FileText",      kind: "report"                              },
  { hash: "escalate", label: "Escalate ticket",       icon: "ArrowUpCircle", kind: "action", action: "ESCALATE"           },
  { hash: "assign",   label: "Assign ticket to…",     icon: "UserCheck",     kind: "assign"                              },
];

// ── Event type classification ─────────────────────────────────────────────────

/** Events that render as a centered system pill (not a bubble). */
export const SYSTEM_EVENT_TYPES = new Set([
  "CREATED", "ACKNOWLEDGED", "ESCALATED", "ASSIGNED", "PRIORITY_CHANGED",
  "RESOLVED", "CLOSED", "GRC_CONVENED", "GRC_DECIDED", "SLA_BREACH_FINAL_STEP",
  "REVEAL_ORIGINAL", "REVEAL_ORIGINAL_CLOSED", "VIEWER_ADDED", "VIEWER_REMOVED",
  "COMPLAINANT_UPDATED",
]);

/** Events that render as a task card in-thread. */
export const TASK_EVENT_TYPES = new Set(["TASK_ASSIGNED", "TASK_COMPLETED", "TASK_DISMISSED"]);

/**
 * Notification-only events: counted for unread badge but NOT rendered in the thread.
 * (MENTION events are stored in ticket_events but are purely notification signals.)
 */
export const NOTIFICATION_ONLY_EVENT_TYPES = new Set(["MENTION"]);

/** Inbound complainant messages — rendered as a distinct emerald bubble. */
export const COMPLAINANT_EVENT_TYPES = new Set(["COMPLAINANT_MESSAGE"]);

/** Human-readable labels for system event pills — no emoji, pure text. */
export function systemEventLabel(eventType: string, payload?: Record<string, unknown> | null): string {
  switch (eventType) {
    case "CREATED":               return "Case opened";
    case "ACKNOWLEDGED":          return "Acknowledged — case in progress";
    case "ESCALATED":             return `Escalated${payload?.to_step_key ? ` → ${payload.to_step_key}` : ""}`;
    case "ASSIGNED":              return `Assigned to ${payload?.new_assigned ?? "officer"}`;
    case "PRIORITY_CHANGED":      return `Priority changed to ${payload?.new_priority ?? "—"}`;
    case "RESOLVED":              return "Case resolved";
    case "CLOSED":                return "Case closed";
    case "GRC_CONVENED":          return `GRC hearing convened${payload?.hearing_date ? ` — ${payload.hearing_date}` : ""}`;
    case "GRC_DECIDED":           return `GRC decision: ${payload?.decision ?? "recorded"}`;
    case "SLA_BREACH_FINAL_STEP": return "SLA breached at final level — manual intervention required";
    case "REVEAL_ORIGINAL":       return `Original statement ${payload?.granted ? "viewed" : "access denied"}`;
    case "REVEAL_ORIGINAL_CLOSED":return "Reveal session closed";
    case "VIEWER_ADDED":          return `${payload?.added_user_id ?? "Officer"} added as viewer`;
    case "VIEWER_REMOVED":        return `${payload?.removed_user_id ?? "Officer"} removed from viewers`;
    case "COMPLAINANT_UPDATED":   return `Complainant info updated (${(payload?.fields_changed as string[] | undefined)?.join(", ") ?? "fields"})`;
    default:                      return eventType.replace(/_/g, " ").toLowerCase();
  }
}

// ── Workflow step short labels ────────────────────────────────────────────────

const STEP_SHORT_LABEL: Record<string, string> = {
  LEVEL_1_SITE:          "L1 Site",
  LEVEL_2_PIU:           "L2 PIU",
  LEVEL_3_GRC:           "L3 GRC",
  LEVEL_4_LEGAL:         "L4 Legal",
  SEAH_LEVEL_1_NATIONAL: "SEAH L1",
  SEAH_LEVEL_2_HQ:       "SEAH L2",
};

/** Short human label derived from step_key. Falls back to a cleaned version of the key. */
export function stepShortLabel(stepKey: string): string {
  return STEP_SHORT_LABEL[stepKey] ?? stepKey.replace(/_/g, " ").replace(/LEVEL (\d)/, "L$1");
}

// ── SLA urgency helpers ───────────────────────────────────────────────────────

export type SlaUrgency = "overdue" | "critical" | "warning" | "ok" | "none";

/**
 * Returns a Tailwind `bg-*` class for a 2×2 rounded urgency dot.
 * Render as: <span className={`w-2 h-2 rounded-full inline-block ${urgencyDotCls(u)}`} />
 */
export function urgencyDotCls(urgency: SlaUrgency): string {
  switch (urgency) {
    case "overdue":  return "bg-red-500";
    case "critical": return "bg-red-400";
    case "warning":  return "bg-yellow-400";
    case "ok":       return "bg-green-500";
    default:         return "bg-gray-300";
  }
}

/** @deprecated Use urgencyDotCls instead */
export const urgencyDot = urgencyDotCls;

export function urgencyTextCls(urgency: SlaUrgency): string {
  switch (urgency) {
    case "overdue":  return "text-red-700";
    case "critical": return "text-orange-600";
    case "warning":  return "text-yellow-700";
    case "ok":       return "text-green-700";
    default:         return "text-gray-400";
  }
}
