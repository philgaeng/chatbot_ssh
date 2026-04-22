import { type SlaUrgency } from "@/lib/api";

// ── Status badge ──────────────────────────────────────────────────────────────

const STATUS_STYLES: Record<string, string> = {
  OPEN:                   "bg-blue-100 text-blue-800",
  IN_PROGRESS:            "bg-yellow-100 text-yellow-800",
  ESCALATED:              "bg-orange-100 text-orange-800",
  GRC_HEARING_SCHEDULED:  "bg-purple-100 text-purple-800",
  RESOLVED:               "bg-green-100 text-green-800",
  CLOSED:                 "bg-gray-100 text-gray-600",
};
const STATUS_LABELS: Record<string, string> = {
  OPEN:                   "New",
  IN_PROGRESS:            "In Progress",
  ESCALATED:              "Escalated",
  GRC_HEARING_SCHEDULED:  "GRC Hearing",
  RESOLVED:               "Resolved",
  CLOSED:                 "Closed",
};

export function StatusBadge({ code }: { code: string }) {
  const cls = STATUS_STYLES[code] ?? "bg-gray-100 text-gray-600";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {STATUS_LABELS[code] ?? code}
    </span>
  );
}

// ── Priority badge ────────────────────────────────────────────────────────────

const PRI_STYLES: Record<string, string> = {
  HIGH:      "bg-red-100 text-red-700",
  SENSITIVE: "bg-red-100 text-red-700",
  NORMAL:    "bg-gray-100 text-gray-600",
};

export function PriorityBadge({ priority }: { priority: string }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${PRI_STYLES[priority] ?? "bg-gray-100 text-gray-600"}`}>
      {priority}
    </span>
  );
}

// ── SEAH badge ────────────────────────────────────────────────────────────────

export function SeahBadge() {
  return (
    <span className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded text-xs font-bold bg-red-600 text-white">
      🔒 SEAH
    </span>
  );
}

// ── SLA urgency dot ───────────────────────────────────────────────────────────

const URGENCY_DOT: Record<SlaUrgency, string> = {
  overdue:  "bg-red-500",
  critical: "bg-red-400",
  warning:  "bg-yellow-400",
  ok:       "bg-green-400",
  none:     "bg-gray-300",
};

export function UrgencyDot({ urgency }: { urgency: SlaUrgency }) {
  return <span className={`inline-block w-2.5 h-2.5 rounded-full ${URGENCY_DOT[urgency]}`} />;
}

// ── Notification count bubble ─────────────────────────────────────────────────

export function CountBubble({ count, red = false }: { count: number; red?: boolean }) {
  if (count === 0) return null;
  return (
    <span className={`ml-1.5 inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1 rounded-full text-xs font-bold text-white ${red ? "bg-red-500" : "bg-gray-500"}`}>
      {count > 99 ? "99+" : count}
    </span>
  );
}
