"use client";

/**
 * /m/queue — Mobile queue screen (chat-list style).
 * UI_SPEC.md §2.1
 */

import { useEffect, useMemo, useState, useCallback } from "react";
import Link from "next/link";
import {
  EMPTY_TICKET_LIST_FILTERS,
  listTickets,
  getSla,
  ticketListFiltersActive,
  ticketListFiltersToApi,
  type TicketListFilterValues,
  type TicketListItem,
  type SlaStatus,
} from "@/lib/api";
import { useAuth } from "@/app/providers/AuthProvider";
import { urgencyTextCls, type SlaUrgency } from "@/lib/mobile-constants";
import { IntakeRouteBadge, UrgencyDot } from "@/lib/icons";
import { MobileAppHeader } from "@/components/mobile/MobileAppHeader";
import { MobileTicketFiltersSheet } from "@/components/mobile/MobileTicketFiltersSheet";

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
      className="flex items-center gap-3 px-4 py-3 active:bg-gray-50 border-b border-gray-100 last:border-0"
    >
      <UrgencyDot urgency={urgency} className="w-2.5 h-2.5" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 mb-0.5">
          <span className="text-xs text-gray-400 font-mono truncate">{ticket.grievance_id}</span>
          <IntakeRouteBadge intakeRoute={ticket.intake_route} size="xs" />
          {ticket.unseen_event_count > 0 && (
            <span className="ml-auto flex-shrink-0 bg-red-500 text-white text-[10px] font-bold rounded-full min-w-[16px] h-4 flex items-center justify-center px-1">
              {ticket.unseen_event_count}
            </span>
          )}
        </div>
        <div className="text-sm text-gray-800 truncate">
          {isSeah ? "[SEAH — restricted]" : (ticket.grievance_summary ?? "No summary")}
        </div>
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

type QueueFilter = "mine" | "all" | "escalated";

const FILTERS: { id: QueueFilter; label: string }[] = [
  { id: "mine", label: "My Queue" },
  { id: "all", label: "All" },
  { id: "escalated", label: "Escalated" },
];

export default function MobileQueuePage() {
  const { isAuthenticated } = useAuth();
  const [filter, setFilter] = useState<QueueFilter>("mine");
  const [listFilters, setListFilters] = useState<TicketListFilterValues>(EMPTY_TICKET_LIST_FILTERS);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [tickets, setTickets] = useState<TicketListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const filtersActive = ticketListFiltersActive(listFilters);

  const load = useCallback(
    (showRefresh = false) => {
      if (!isAuthenticated) return;
      if (showRefresh) setRefreshing(true);
      else setLoading(true);

      const tabParams =
        filter === "mine" ? { tab: "actor" as const } :
        filter === "escalated" ? { status_code: "ESCALATED" } :
        {};

      listTickets({
        ...tabParams,
        ...ticketListFiltersToApi(listFilters),
        page_size: 50,
      })
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
    [filter, isAuthenticated, listFilters],
  );

  useEffect(() => {
    load();
  }, [load]);

  const actionNeeded = useMemo(
    () => (filter === "mine" ? tickets.filter((t) => t.status_code === "OPEN" || t.unseen_event_count > 0).length : 0),
    [tickets, filter],
  );
  const overdue = useMemo(
    () => (filter === "mine" ? tickets.filter((t) => t.sla_breached).length : 0),
    [tickets, filter],
  );

  return (
    <div className="flex flex-col h-full">
      <MobileAppHeader
        title="GRM Tickets"
        onRefresh={() => load(true)}
        refreshing={refreshing}
        showFilterButton
        filtersActive={filtersActive}
        onOpenFilters={() => setFiltersOpen(true)}
      />

      <MobileTicketFiltersSheet
        open={filtersOpen}
        values={listFilters}
        onChange={setListFilters}
        onClose={() => setFiltersOpen(false)}
        onApply={() => load()}
      />

      <div className="flex-shrink-0 bg-white px-4">
        {filter === "mine" && !loading && (actionNeeded > 0 || overdue > 0) && (
          <div className="flex gap-2 pb-2">
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

        <div className="flex border-b border-gray-200">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              onClick={() => setFilter(f.id)}
              className={`flex-1 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                filter === f.id ? "border-blue-600 text-blue-600" : "border-transparent text-gray-400"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center h-32 text-sm text-gray-400">Loading…</div>
        ) : tickets.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 gap-2">
            <span className="text-sm text-gray-400">No tickets in this view</span>
            {filtersActive && (
              <button
                type="button"
                onClick={() => {
                  setListFilters(EMPTY_TICKET_LIST_FILTERS);
                  setFiltersOpen(true);
                }}
                className="text-sm text-blue-600"
              >
                Adjust filters
              </button>
            )}
          </div>
        ) : (
          <div className="bg-white">
            <div className="px-4 py-2 text-xs text-gray-400 border-b border-gray-100">
              {total} ticket{total !== 1 ? "s" : ""}
            </div>
            {tickets.map((t) => (
              <QueueRow key={t.ticket_id} ticket={t} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
