"use client";

/**
 * /m/tickets — Mobile all-tickets list (lighter version of desktop /tickets).
 * Links into /m/tickets/[id] thread screen.
 */

import { useCallback, useEffect, useState } from "react";
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
import { type SlaUrgency } from "@/lib/mobile-constants";
import { UrgencyDot, IntakeRouteBadge } from "@/lib/icons";
import { Search } from "lucide-react";
import { MobileAppHeader } from "@/components/mobile/MobileAppHeader";
import { MobileTicketFiltersSheet } from "@/components/mobile/MobileTicketFiltersSheet";

function TicketRow({ ticket }: { ticket: TicketListItem }) {
  const urgency: SlaUrgency = ticket.sla_breached ? "overdue" : "none";
  return (
    <Link
      href={`/m/tickets/${ticket.ticket_id}`}
      className="flex items-center gap-3 px-4 py-3 border-b border-gray-100 last:border-0 active:bg-gray-50"
    >
      <UrgencyDot urgency={urgency} className="w-2.5 h-2.5" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 mb-0.5">
          <span className="text-xs text-gray-400 font-mono truncate">{ticket.grievance_id}</span>
          <IntakeRouteBadge intakeRoute={ticket.intake_route} size="xs" />
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
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState("");
  const [listFilters, setListFilters] = useState<TicketListFilterValues>(EMPTY_TICKET_LIST_FILTERS);
  const [filtersOpen, setFiltersOpen] = useState(false);

  const filtersActive = ticketListFiltersActive(listFilters) || !!search.trim();

  const load = useCallback(
    (showRefresh = false) => {
      if (!isAuthenticated) return;
      if (showRefresh) setRefreshing(true);
      else setLoading(true);

      const apiFilters = ticketListFiltersToApi(listFilters);
      if (search.trim() && !apiFilters.q) {
        apiFilters.q = search.trim();
      }

      listTickets({ ...apiFilters, page_size: 100 })
        .then((r) => {
          setTickets(r.items);
          setTotal(r.total);
        })
        .catch(console.error)
        .finally(() => {
          setLoading(false);
          setRefreshing(false);
        });
    },
    [isAuthenticated, listFilters, search],
  );

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="flex flex-col h-full">
      <MobileAppHeader
        title="All Tickets"
        onRefresh={() => load(true)}
        refreshing={refreshing}
        showFilterButton
        filtersActive={filtersActive}
        onOpenFilters={() => setFiltersOpen(true)}
        trailing={<span className="text-xs text-gray-400 px-1">{total}</span>}
      />

      <MobileTicketFiltersSheet
        open={filtersOpen}
        values={listFilters}
        onChange={setListFilters}
        onClose={() => setFiltersOpen(false)}
        onApply={() => load()}
      />

      <div className="flex-shrink-0 bg-white border-b border-gray-200 px-4 pb-2">
        <div className="relative">
          <Search size={14} strokeWidth={2} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") load();
            }}
            placeholder="Quick search ID or summary…"
            className="w-full bg-gray-100 rounded-xl pl-8 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto bg-white">
        {loading ? (
          <div className="flex items-center justify-center h-32 text-sm text-gray-400">Loading…</div>
        ) : tickets.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 gap-2">
            <Search size={32} strokeWidth={1.25} className="text-gray-200" />
            <span className="text-sm text-gray-400">No tickets found</span>
          </div>
        ) : (
          tickets.map((t) => <TicketRow key={t.ticket_id} ticket={t} />)
        )}
      </div>
    </div>
  );
}
