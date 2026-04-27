"use client";

/**
 * /m/tickets — Mobile all-tickets list (lighter version of desktop /tickets).
 * Links into /m/tickets/[id] thread screen.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { listTickets, type TicketListItem } from "@/lib/api";
import { useAuth } from "@/app/providers/AuthProvider";
import { urgencyDot, type SlaUrgency } from "@/lib/mobile-constants";

function TicketRow({ ticket }: { ticket: TicketListItem }) {
  const urgency: SlaUrgency = ticket.sla_breached ? "overdue" : "none";
  return (
    <Link
      href={`/m/tickets/${ticket.ticket_id}`}
      className={`flex items-center gap-3 px-4 py-3 border-b border-gray-100 last:border-0 active:bg-gray-50 ${
        ticket.is_seah ? "border-l-4 border-l-red-500" : ""
      }`}
    >
      <span className="text-base shrink-0">{urgencyDot(urgency)}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 mb-0.5">
          <span className="text-xs text-gray-400 font-mono truncate">{ticket.grievance_id}</span>
          {ticket.is_seah && (
            <span className="text-[10px] font-bold text-red-600 bg-red-50 px-1 rounded">🔒</span>
          )}
        </div>
        <div className="text-sm text-gray-800 truncate">
          {ticket.is_seah ? "[SEAH — restricted]" : (ticket.grievance_summary ?? "No summary")}
        </div>
        <div className="text-xs text-gray-400 mt-0.5">
          {ticket.status_code} · {ticket.location_code ?? ticket.organization_id}
        </div>
      </div>
      {ticket.unseen_event_count > 0 && (
        <span className="bg-red-500 text-white text-[10px] font-bold rounded-full min-w-[16px] h-4 flex items-center justify-center px-1 shrink-0">
          {ticket.unseen_event_count}
        </span>
      )}
      <span className="text-gray-300 shrink-0">›</span>
    </Link>
  );
}

export default function MobileAllTicketsPage() {
  const { isAuthenticated } = useAuth();
  const [tickets, setTickets] = useState<TicketListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  const load = useCallback(() => {
    if (!isAuthenticated) return;
    setLoading(true);
    listTickets({ page_size: 100 })
      .then((r) => { setTickets(r.items); setTotal(r.total); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [isAuthenticated]);

  useEffect(() => { load(); }, [load]);

  const filtered = search.trim()
    ? tickets.filter((t) =>
        t.grievance_id.toLowerCase().includes(search.toLowerCase()) ||
        (t.grievance_summary ?? "").toLowerCase().includes(search.toLowerCase())
      )
    : tickets;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex-shrink-0 bg-white border-b border-gray-200 px-4 pt-safe-top pb-2">
        <div className="flex items-center justify-between py-3">
          <h1 className="text-lg font-semibold text-gray-900">All Tickets</h1>
          <span className="text-xs text-gray-400">{total} total</span>
        </div>
        {/* Search */}
        <div className="relative mb-1">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">🔍</span>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search ID or summary…"
            className="w-full bg-gray-100 rounded-xl pl-8 pr-4 py-2 text-sm focus:outline-none"
          />
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto bg-white">
        {loading ? (
          <div className="flex items-center justify-center h-32 text-sm text-gray-400">Loading…</div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 gap-2">
            <span className="text-3xl">🔍</span>
            <span className="text-sm text-gray-400">No tickets found</span>
          </div>
        ) : (
          filtered.map((t) => <TicketRow key={t.ticket_id} ticket={t} />)
        )}
      </div>
    </div>
  );
}
