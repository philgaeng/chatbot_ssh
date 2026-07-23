"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  EMPTY_TICKET_LIST_FILTERS,
  listTickets,
  ticketListFiltersActive,
  ticketListFiltersToApi,
  type TicketListFilterValues,
  type TicketListItem,
} from "@/lib/api";
import { useAuth } from "@/app/providers/AuthProvider";
import { StatusBadge, PriorityBadge, IntakeRouteBadge, UrgencyDot, CountBubble } from "@/components/ui/Badge";
import { SlaCountdown } from "@/components/ui/SlaCountdown";
import { ErrorCard } from "@/components/ui/ErrorCard";
import { TicketListFiltersBar } from "@/components/tickets/TicketListFiltersBar";

function TicketRow({ ticket }: { ticket: TicketListItem }) {
  const urgency = ticket.sla_breached ? "overdue" : "ok";
  return (
    <Link
      href={`/tickets/${ticket.ticket_id}`}
      className="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 transition border-b border-gray-100 last:border-0"
    >
      <UrgencyDot urgency={urgency} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-gray-400 font-mono">{ticket.grievance_id}</span>
          <IntakeRouteBadge intakeRoute={ticket.intake_route} />
          <StatusBadge code={ticket.status_code} />
          <PriorityBadge priority={ticket.priority} />
        </div>
        <div className="text-sm text-gray-700 mt-0.5 truncate">
          {ticket.grievance_summary ?? "No summary"}
        </div>
        <div className="text-xs text-gray-400 mt-0.5">
          {[ticket.location_code, ticket.project_code].filter(Boolean).join(" · ")}
        </div>
      </div>
      <div className="shrink-0 w-28 text-right">
        <SlaCountdown ticketId={ticket.ticket_id} />
      </div>
      <div className="hidden lg:block shrink-0 w-36 text-xs text-gray-400 truncate text-right">
        {ticket.assigned_to_user_id ?? "—"}
      </div>
      <div className="shrink-0">
        <CountBubble count={ticket.unseen_event_count} red />
      </div>
      <span className="text-gray-300 shrink-0">›</span>
    </Link>
  );
}

export default function AllTicketsPage() {
  const { isAuthenticated } = useAuth();
  const [tickets, setTickets] = useState<TicketListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const seqRef = useRef(0);
  const [filters, setFilters] = useState<TicketListFilterValues>(EMPTY_TICKET_LIST_FILTERS);
  const [debouncedQ, setDebouncedQ] = useState("");

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedQ(filters.q), 300);
    return () => window.clearTimeout(t);
  }, [filters.q]);

  const apiFilters = useMemo(
    () => ticketListFiltersToApi({ ...filters, q: debouncedQ }),
    [filters, debouncedQ],
  );

  function load() {
    if (!isAuthenticated) return;
    const seq = ++seqRef.current;
    setLoading(true);
    setError(null);
    listTickets({ page_size: 100, ...apiFilters })
      .then((r) => {
        if (seq !== seqRef.current) return; // stale response — a newer load has started
        setTickets(r.items);
        setTotal(r.total);
      })
      .catch((e) => {
        if (seq !== seqRef.current) return;
        console.error(e);
        setError(e instanceof Error ? e.message : "Couldn't load tickets.");
      })
      .finally(() => {
        if (seq === seqRef.current) setLoading(false);
      });
  }

  useEffect(load, [isAuthenticated, apiFilters]);

  return (
    <div className="p-6">
      <div className="mb-2">
        <h1 className="text-xl font-semibold text-gray-800">All Tickets</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          {ticketListFiltersActive(filters)
            ? `${total} ticket${total !== 1 ? "s" : ""} matching filters`
            : `${total} ticket${total !== 1 ? "s" : ""} total`}
        </p>
      </div>

      <TicketListFiltersBar
        values={filters}
        onChange={setFilters}
        onClear={() => setFilters(EMPTY_TICKET_LIST_FILTERS)}
      />

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-400 text-sm">Loading…</div>
        ) : error ? (
          <ErrorCard message="Couldn't load tickets." onRetry={load} />
        ) : tickets.length === 0 ? (
          <div className="p-8 text-center text-gray-400 text-sm">
            {ticketListFiltersActive(filters) ? "No tickets match your filters." : "No tickets found."}
          </div>
        ) : (
          <div>
            <div className="flex items-center gap-3 px-4 py-2 bg-gray-50 border-b border-gray-200 text-xs text-gray-500 font-medium">
              <div className="w-2.5" />
              <div className="flex-1">Ticket</div>
              <div className="shrink-0 w-28 text-right">SLA</div>
              <div className="hidden lg:block shrink-0 w-36 text-right">Assigned</div>
              <div className="shrink-0 w-6" />
              <div className="shrink-0 w-4" />
            </div>
            {tickets.map((t) => <TicketRow key={t.ticket_id} ticket={t} />)}
          </div>
        )}
      </div>
    </div>
  );
}
