"use client";

import { useEffect, useState } from "react";
import { Clock } from "lucide-react";
import { getSla, type SlaStatus, type SlaUrgency } from "@/lib/api";

const URGENCY_CLASS: Record<SlaUrgency, string> = {
  overdue:  "text-red-600 font-semibold",
  critical: "text-red-500 font-semibold",
  warning:  "text-yellow-600",
  ok:       "text-green-600",
  none:     "text-gray-400",
};

function formatHours(h: number | null): string {
  if (h === null) return "—";
  const abs = Math.abs(h);
  const sign = h < 0 ? "-" : "";
  if (abs < 24) return `${sign}${abs.toFixed(0)}h`;
  const d = Math.floor(abs / 24);
  const rem = Math.round(abs % 24);
  return `${sign}${d}d${rem ? ` ${rem}h` : ""}`;
}

interface Props {
  ticketId: string;
  /** If you already have the SLA data, pass it to skip the fetch */
  initial?: SlaStatus;
  className?: string;
}

export function SlaCountdown({ ticketId, initial, className = "" }: Props) {
  const [sla, setSla] = useState<SlaStatus | null>(initial ?? null);

  useEffect(() => {
    if (initial) return;
    getSla(ticketId).then(setSla).catch(() => {});
  }, [ticketId, initial]);

  if (!sla || sla.urgency === "none") {
    return <span className={`text-xs text-gray-400 ${className}`}>No SLA</span>;
  }

  const cls = URGENCY_CLASS[sla.urgency];
  const label = sla.breached
    ? `Overdue ${formatHours(sla.remaining_hours)}`
    : `${formatHours(sla.remaining_hours)} left`;

  return (
    <span className={`text-xs flex items-center gap-1 ${cls} ${className}`}>
      <Clock size={12} strokeWidth={2} />
      <span>{label}</span>
    </span>
  );
}
