import { type SlaUrgency } from "@/lib/api";
import { STATUS_BADGE, STATUS_LABELS, PRIORITY_BADGE, SLA_DOT } from "@/lib/design-tokens";
import { IconLock } from "@/lib/icons";

// ── Status badge ──────────────────────────────────────────────────────────────

export function StatusBadge({ code }: { code: string }) {
  const { bg, text } = STATUS_BADGE[code] ?? { bg: "bg-gray-100", text: "text-gray-700" };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${bg} ${text}`}>
      {STATUS_LABELS[code] ?? code}
    </span>
  );
}

// ── Priority badge ────────────────────────────────────────────────────────────

export function PriorityBadge({ priority }: { priority: string }) {
  const { bg, text } = PRIORITY_BADGE[priority] ?? { bg: "bg-gray-100", text: "text-gray-700" };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${bg} ${text}`}>
      {priority}
    </span>
  );
}

// ── SEAH badge ────────────────────────────────────────────────────────────────

export function SeahBadge() {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-bold bg-red-600 text-white">
      <IconLock size={10} />
      SEAH
    </span>
  );
}

// ── SLA urgency dot ───────────────────────────────────────────────────────────

export function UrgencyDot({ urgency }: { urgency: SlaUrgency }) {
  return (
    <span
      className={`inline-block w-2.5 h-2.5 rounded-full shrink-0 ${SLA_DOT[urgency] ?? "bg-gray-300"}`}
      aria-label={urgency}
    />
  );
}

// ── Notification count bubble ─────────────────────────────────────────────────

export function CountBubble({ count, red = false }: { count: number; red?: boolean }) {
  if (count === 0) return null;
  return (
    <span
      className={`ml-1.5 inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1 rounded-full text-xs font-bold text-white ${
        red ? "bg-red-500" : "bg-gray-600"
      }`}
    >
      {count > 99 ? "99+" : count}
    </span>
  );
}
