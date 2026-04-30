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
  /** Emoji shown before the role label */
  emoji: string;
  /** Short human-readable role label */
  label: string;
}

export const ROLE_BUBBLE_STYLE: Record<string, RoleBubbleStyle> = {
  site_safeguards_focal_person:  { bubbleCls: "bg-green-50  border-l-4 border-green-400", labelCls: "text-green-700",  emoji: "🟢", label: "L1 Officer" },
  pd_piu_safeguards_focal:       { bubbleCls: "bg-amber-50  border-l-4 border-amber-400", labelCls: "text-amber-700",  emoji: "🟠", label: "L2 PIU" },
  grc_chair:                     { bubbleCls: "bg-purple-50 border-l-4 border-purple-400",labelCls: "text-purple-700", emoji: "🟣", label: "GRC Chair" },
  grc_member:                    { bubbleCls: "bg-purple-50 border-l-4 border-purple-300",labelCls: "text-purple-600", emoji: "🟣", label: "GRC" },
  adb_national_project_director: { bubbleCls: "bg-teal-50   border-l-4 border-teal-400",  labelCls: "text-teal-700",   emoji: "🔵", label: "ADB" },
  adb_hq_safeguards:             { bubbleCls: "bg-teal-50   border-l-4 border-teal-400",  labelCls: "text-teal-700",   emoji: "🔵", label: "ADB HQ" },
  adb_hq_project:                { bubbleCls: "bg-teal-50   border-l-4 border-teal-400",  labelCls: "text-teal-700",   emoji: "🔵", label: "ADB" },
  adb_hq_exec:                   { bubbleCls: "bg-teal-50   border-l-4 border-teal-400",  labelCls: "text-teal-700",   emoji: "🔵", label: "ADB Exec" },
  seah_national_officer:         { bubbleCls: "bg-red-50    border-l-4 border-red-400",   labelCls: "text-red-700",    emoji: "🔴", label: "SEAH" },
  seah_hq_officer:               { bubbleCls: "bg-red-50    border-l-4 border-red-400",   labelCls: "text-red-700",    emoji: "🔴", label: "SEAH HQ" },
  super_admin:                   { bubbleCls: "bg-slate-100 border-l-4 border-slate-400", labelCls: "text-slate-700",  emoji: "⚙️", label: "Admin" },
  local_admin:                   { bubbleCls: "bg-slate-100 border-l-4 border-slate-400", labelCls: "text-slate-700",  emoji: "⚙️", label: "Admin" },
  system:                        { bubbleCls: "",                                          labelCls: "text-gray-400",   emoji: "",   label: "System" },
};

/** Fallback for unknown roles */
export const DEFAULT_BUBBLE_STYLE: RoleBubbleStyle = {
  bubbleCls: "bg-gray-100 border-l-4 border-gray-400",
  labelCls: "text-gray-600",
  emoji: "👤",
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

export const TASK_TYPES = [
  { key: "SITE_VISIT",      label: "Site Visit",       icon: "🚶" },
  { key: "FOLLOW_UP_CALL",  label: "Follow-up Call",   icon: "📞" },
  { key: "SYSTEM_NOTE",     label: "Add System Note",  icon: "📝" },
  { key: "DOCUMENT_PHOTO",  label: "Document & Photo", icon: "📸" },
] as const;

export type TaskTypeKey = (typeof TASK_TYPES)[number]["key"];

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

/** Human-readable labels for system event pills. */
export function systemEventLabel(eventType: string, payload?: Record<string, unknown> | null): string {
  switch (eventType) {
    case "CREATED":               return "Case opened";
    case "ACKNOWLEDGED":          return "Acknowledged — case in progress";
    case "ESCALATED":             return `Escalated${payload?.to_step_key ? ` → ${payload.to_step_key}` : ""}`;
    case "ASSIGNED":              return `Assigned to ${payload?.new_assigned ?? "officer"}`;
    case "PRIORITY_CHANGED":      return `Priority changed to ${payload?.new_priority ?? "—"}`;
    case "RESOLVED":              return "✅ Case resolved";
    case "CLOSED":                return "🔒 Case closed";
    case "GRC_CONVENED":          return `GRC hearing convened${payload?.hearing_date ? ` — ${payload.hearing_date}` : ""}`;
    case "GRC_DECIDED":           return `GRC decision: ${payload?.decision ?? "recorded"}`;
    case "SLA_BREACH_FINAL_STEP": return "⚠️ SLA breached at final level — manual intervention required";
    case "REVEAL_ORIGINAL":       return `🔍 Original statement ${payload?.granted ? "viewed" : "access denied"}`;
    case "REVEAL_ORIGINAL_CLOSED":return "🔍 Reveal session closed";
    case "VIEWER_ADDED":          return `👁 ${payload?.added_user_id ?? "Officer"} added as viewer`;
    case "VIEWER_REMOVED":        return `👁 ${payload?.removed_user_id ?? "Officer"} removed from viewers`;
    case "COMPLAINANT_UPDATED":   return `✏️ Complainant info updated (${(payload?.fields_changed as string[] | undefined)?.join(", ") ?? "fields"})`;
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

export function urgencyDot(urgency: SlaUrgency): string {
  switch (urgency) {
    case "overdue":  return "🔴";
    case "critical": return "🔴";
    case "warning":  return "🟡";
    case "ok":       return "🟢";
    default:         return "⚪";
  }
}

export function urgencyTextCls(urgency: SlaUrgency): string {
  switch (urgency) {
    case "overdue":  return "text-red-700";
    case "critical": return "text-orange-600";
    case "warning":  return "text-yellow-700";
    case "ok":       return "text-green-700";
    default:         return "text-gray-400";
  }
}
