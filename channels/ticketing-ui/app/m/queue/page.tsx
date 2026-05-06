"use client";

/**
 * /m/queue — Mobile queue screen (chat-list style).
 * UI_SPEC.md §2.1
 */

import { useEffect, useMemo, useState, useCallback } from "react";
import Link from "next/link";
import { listTickets, getSla, type TicketListItem, type SlaStatus } from "@/lib/api";
import { useAuth } from "@/app/providers/AuthProvider";
import { urgencyDotCls, urgencyTextCls, type SlaUrgency } from "@/lib/mobile-constants";
import { SeahBadge, UrgencyDot } from "@/lib/icons";

// ── Helpers ───────────────────────────────────────────────────────────────────

function slaLabel(sla: SlaStatus | undefined, breached: boolean): string {
  if (breached) return "Overdue";
  if (!sla || sla.urgency === "none" || !sla.remaining_hours) return "Active";
  const h = sla.remaining_hours;
  if (h < 24) return `${Math.round(h)}h left`;
  return `${Math.round(h / 24)}d left`;
}

function stepLabel(ticket: TicketListItem): string {
  if (ticket.status_code === "RESOLVED") return "Resolved";
  if (ticket.status_code === "CLOSED") return "Closed";
  if (ticket.status_code === "ESCALATED") return "Escalated";
  if (ticket.status_code === "GRC_HEARING_SCHEDULED") return "L3 GRC";
  if (ticket.location_code) return ticket.location_code;
  return ticket.status_code;
}

// ── Single ticket row ─────────────────────────────────────────────────────────

function QueueRow({ ticket }: { ticket: TicketListItem }) {
  const [sla, setSla] = useState<SlaStatus | undefined>(undefined);

  useEffect(() => {
    getSla(ticket.ticket_id).then(setSla).catch(() => {});
  }, [ticket.ticket_id]);

  const urgency: SlaUrgency = ticket.sla_breached ? "overdue" : (sla?.urgency ?? "none");
  const timeCls = urgencyTextCls(urgency);
  const isSeah = ticket.is_seah;

  return (
    <Link
      href={`/m/tickets/${ticket.ticket_id}`}
      className={`flex items-center gap-3 px-4 py-3 active:bg-gray-50 border-b border-gray-100 last:border-0 ${
        isSeah ? "border-l-4 border-l-red-500" : ""
      }`}
    >
      {/* Urgency dot — leftmost, seen before reading anything (spec §2.1) */}
      <UrgencyDot urgency={urgency} className="w-2.5 h-2.5" />

      {/* Main content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 mb-0.5">
          <span className="text-xs text-gray-400 font-mono truncate">{ticket.grievance_id}</span>
          {isSeah && (
            <SeahBadge size="xs" />
          )}
          {ticket.unseen_event_count > 0 && (
            <span className="ml-auto flex-shrink-0 bg-red-500 text-white text-[10px] font-bold rounded-full min-w-[16px] h-4 flex items-center justify-center px-1">
              {ticket.unseen_event_count}
            </span>
          )}
        </div>

        {/* Summary text — hidden for SEAH */}
        <div className="text-sm text-gray-800 truncate">
          {isSeah ? "[SEAH — restricted]" : (ticket.grievance_summary ?? "No summary")}
        </div>

        {/* Meta line: SLA · level · location */}
        <div className={`text-xs mt-0.5 flex items-center gap-1.5 ${timeCls}`}>
          <span>{slaLabel(sla, ticket.sla_breached)}</span>
          <span className="text-gray-300">·</span>
          <span className="text-gray-400">{stepLabel(ticket)}</span>
          {ticket.location_code && (
            <>
              <span className="text-gray-300">·</span>
              <span className="text-gray-400 truncate">{ticket.location_code}</span>
            </>
          )}
        </div>
      </div>

      <span className="text-gray-300 shrink-0 text-lg">›</span>
    </Link>
  );
}

// ── Filter tabs ───────────────────────────────────────────────────────────────

type QueueFilter = "mine" | "all" | "escalated";

const FILTERS: { id: QueueFilter; label: string }[] = [
  { id: "mine",      label: "My Queue" },
  { id: "all",       label: "All" },
  { id: "escalated", label: "Escalated" },
];

// ── Page ──────────────────────────────────────────────────────────────────────

export default function MobileQueuePage() {
  const { isAuthenticated } = useAuth();
  const [filter, setFilter] = useState<QueueFilter>("mine");
  const [tickets, setTickets] = useState<TicketListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(
    (showRefresh = false) => {
      if (!isAuthenticated) return;
      if (showRefresh) setRefreshing(true); else setLoading(true);

      const params =
        filter === "mine"      ? { my_queue: true, page_size: 50 } :
        filter === "escalated" ? { status_code: "ESCALATED", page_size: 50 } :
        { page_size: 50 };

      listTickets(params)
        .then((r) => { setTickets(r.items); setTotal(r.total); })
        .catch(console.error)
        .finally(() => { setLoading(false); setRefreshing(false); });
    },
    [filter, isAuthenticated],
  );

  useEffect(() => { load(); }, [load]);

  // Summary stats for My Queue
  const actionNeeded = useMemo(
    () => filter === "mine" ? tickets.filter((t) => t.status_code === "OPEN" || t.unseen_event_count > 0).length : 0,
    [tickets, filter],
  );
  const overdue = useMemo(
    () => filter === "mine" ? tickets.filter((t) => t.sla_breached).length : 0,
    [tickets, filter],
  );

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex-shrink-0 bg-white px-4 pt-safe-top">
        <div className="flex items-center justify-between py-3">
          <h1 className="text-lg font-semibold text-gray-900">GRM Tickets</h1>
          <button
            onClick={() => load(true)}
            className={`text-sm text-blue-600 font-medium ${refreshing ? "opacity-50" : ""}`}
            disabled={refreshing}
          >
            {refreshing ? "↻" : "Refresh"}
          </button>
        </div>

        {/* Quick stats strip — only on My Queue */}
        {filter === "mine" && !loading && (
          <div className="flex gap-3 pb-2">
            {actionNeeded > 0 && (
              <div className="text-xs text-blue-700 bg-blue-50 rounded-full px-3 py-1 font-medium">
                {actionNeeded} action needed
              </div>
            )}
            {overdue > 0 && (
              <div className="text-xs text-red-700 bg-red-50 rounded-full px-3 py-1 font-medium">
                {overdue} overdue
              </div>
            )}
          </div>
        )}

        {/* Filter tabs */}
        <div className="flex border-b border-gray-200">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              className={`flex-1 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                filter === f.id
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-400"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Ticket list — scrollable */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center h-32 text-sm text-gray-400">
            Loading…
          </div>
        ) : tickets.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 gap-2">
            <span className="text-sm text-gray-400">No tickets in this view</span>
          </div>
        ) : (
          <div className="bg-white">
            {/* Count line */}
            <div className="px-4 py-2 text-xs text-gray-400 border-b border-gray-100">
              {total} ticket{total !== 1 ? "s" : ""}
            </div>
            {tickets.map((t) => <QueueRow key={t.ticket_id} ticket={t} />)}
          </div>
        )}
      </div>
    </div>
  );
}
