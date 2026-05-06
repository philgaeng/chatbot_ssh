"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { listTickets, type TicketListItem } from "@/lib/api";
import { useAuth } from "@/app/providers/AuthProvider";
import { StatusBadge, PriorityBadge, SeahBadge, UrgencyDot, CountBubble } from "@/components/ui/Badge";
import { SlaCountdown } from "@/components/ui/SlaCountdown";
import { IconChevronRight } from "@/lib/icons";

// ── Tab definition ────────────────────────────────────────────────────────────

type Tab = "my_queue" | "all" | "escalated" | "resolved";

const TABS: { id: Tab; label: string; redBadge: boolean }[] = [
  { id: "my_queue",  label: "My Queue",    redBadge: true  },
  { id: "all",       label: "All Tickets", redBadge: false },
  { id: "escalated", label: "Escalated",   redBadge: true  },
  { id: "resolved",  label: "Resolved",    redBadge: false },
];

// ── Summary tile ──────────────────────────────────────────────────────────────

function SummaryTile({
  label, count, sub, urgent = false, warning = false, onClick,
}: {
  label: string;
  count: number;
  sub?: string;
  urgent?: boolean;
  warning?: boolean;
  onClick?: () => void;
}) {
  const isRed    = urgent  && count > 0;
  const isYellow = warning && count > 0;

  const borderCls = isRed
    ? "border-red-300 bg-red-50"
    : isYellow
    ? "border-yellow-300 bg-yellow-50"
    : "border-gray-200 bg-white";

  const countCls = isRed
    ? "text-red-700 font-bold"
    : isYellow
    ? "text-yellow-800 font-bold"
    : "text-gray-800 font-bold";

  return (
    <button
      onClick={onClick}
      className={`rounded-lg border p-4 text-left hover:shadow-sm transition w-full ${borderCls}`}
    >
      <div className={`text-2xl ${countCls}`}>{count}</div>
      <div className="text-sm font-medium text-gray-700 mt-0.5">{label}</div>
      {sub && <div className="text-xs text-gray-600 mt-0.5">{sub}</div>}
    </button>
  );
}

// ── Ticket row ────────────────────────────────────────────────────────────────

function TicketRow({ ticket }: { ticket: TicketListItem }) {
  const urgency = ticket.sla_breached ? "overdue" : "ok";

  return (
    <Link
      href={`/tickets/${ticket.ticket_id}`}
      className={`flex items-center gap-3 px-4 py-3 hover:bg-gray-50 transition border-b border-gray-100 last:border-0 ${ticket.is_seah ? "border-l-2 border-l-red-400" : ""}`}
    >
      {/* Urgency dot */}
      <UrgencyDot urgency={urgency} />

      {/* ID + summary */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-gray-600 font-mono">{ticket.grievance_id}</span>
          {ticket.is_seah && <SeahBadge />}
          <StatusBadge code={ticket.status_code} />
          <PriorityBadge priority={ticket.priority} />
        </div>
        <div className="text-sm text-gray-700 mt-0.5 truncate">
          {ticket.grievance_summary ?? "No summary"}
        </div>
        <div className="text-xs text-gray-600 mt-0.5">
          {[ticket.location_code, ticket.project_code].filter(Boolean).join(" · ")}
        </div>
      </div>

      {/* SLA */}
      <div className="shrink-0 w-28 text-right">
        <SlaCountdown ticketId={ticket.ticket_id} />
      </div>

      {/* Assigned */}
      <div className="hidden lg:block shrink-0 w-36 text-xs text-gray-600 truncate text-right">
        {ticket.assigned_to_user_id ?? "—"}
      </div>

      {/* Unread badge */}
      <div className="shrink-0">
        <CountBubble count={ticket.unseen_event_count} red />
      </div>

      {/* Arrow */}
      <IconChevronRight size={16} className="text-gray-400 shrink-0" />
    </Link>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function QueuePage() {
  const { isAuthenticated } = useAuth();
  const [activeTab, setActiveTab] = useState<Tab>("my_queue");
  const [tickets, setTickets] = useState<TicketListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  // ── My Queue tiles — fetched independently so they always reflect
  //    the officer's own plate regardless of which tab is active. ──────────────
  const [myQueueTickets, setMyQueueTickets] = useState<TicketListItem[]>([]);

  useEffect(() => {
    if (!isAuthenticated) return;
    listTickets({ my_queue: true, page_size: 50 })
      .then((r) => setMyQueueTickets(r.items))
      .catch(() => {});
  }, [isAuthenticated]);

  // Tile counts always come from My Queue, never from the current tab.
  const actionNeeded = useMemo(
    () => myQueueTickets.filter((t) => t.status_code === "OPEN" || t.unseen_event_count > 0).length,
    [myQueueTickets],
  );
  const dueToday = useMemo(
    () => myQueueTickets.filter((t) => !t.sla_breached && t.step_started_at !== null).length,
    [myQueueTickets],
  );
  const overdue = useMemo(
    () => myQueueTickets.filter((t) => t.sla_breached).length,
    [myQueueTickets],
  );

  // ── Independent escalated count for the tab badge ─────────────────────────
  const [escalatedTotal, setEscalatedTotal] = useState(0);

  useEffect(() => {
    if (!isAuthenticated) return;
    listTickets({ status_code: "ESCALATED", page_size: 1 })
      .then((r) => setEscalatedTotal(r.total))
      .catch(() => {});
  }, [isAuthenticated]);

  // ── Tab ticket list ───────────────────────────────────────────────────────
  useEffect(() => {
    if (!isAuthenticated) return;
    setLoading(true);

    const filters =
      activeTab === "my_queue"  ? { my_queue: true } :
      activeTab === "escalated" ? { status_code: "ESCALATED" } :
      activeTab === "resolved"  ? { status_code: "RESOLVED" } :
      {};

    listTickets({ ...filters, page_size: 50 })
      .then((r) => {
        setTickets(r.items);
        setTotal(r.total);
        // Sync escalated count when we land on that tab
        if (activeTab === "escalated") setEscalatedTotal(r.total);
        // Sync my queue tiles when we land on My Queue tab
        if (activeTab === "my_queue") setMyQueueTickets(r.items);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [activeTab, isAuthenticated]);

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-5">
        <h1 className="text-xl font-semibold text-gray-800">Officer Queue</h1>
        <p className="text-sm text-gray-500 mt-0.5">{total} ticket{total !== 1 ? "s" : ""}</p>
      </div>

      {/* Summary tiles — shown on all tabs */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        <SummaryTile label="Action Needed" count={actionNeeded} sub="OPEN or unread" />
        <SummaryTile label="Due Today"     count={dueToday}     sub="SLA &lt; 24 h" warning />
        <SummaryTile label="Overdue"       count={overdue}      sub="SLA breached"   urgent />
      </div>

      {/* Tabs */}
      <div className="flex gap-0 border-b border-gray-200 mb-4">
        {TABS.map((tab) => {
          const isActive = activeTab === tab.id;
          // Use the independent escalatedTotal for the Escalated tab badge
          // so it shows the correct count regardless of which tab is active.
          const tabBadgeCount =
            tab.id === "escalated" ? escalatedTotal :
            tab.id === "my_queue"  ? total :
            total;

          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                isActive
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab.label}
              {tabBadgeCount > 0 && (
                <CountBubble count={tabBadgeCount} red={tab.redBadge} />
              )}
            </button>
          );
        })}
      </div>

      {/* Ticket list */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-600 text-sm">Loading…</div>
        ) : tickets.length === 0 ? (
          <div className="p-8 text-center text-gray-600 text-sm">No tickets in this view.</div>
        ) : (
          <div>
            {/* Column headers */}
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
