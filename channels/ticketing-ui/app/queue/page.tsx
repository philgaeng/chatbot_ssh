"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { listTickets, type TicketListItem } from "@/lib/api";
import { useAuth } from "@/app/providers/AuthProvider";
import { StatusBadge, PriorityBadge, SeahBadge, UrgencyDot, CountBubble } from "@/components/ui/Badge";
import { SlaCountdown } from "@/components/ui/SlaCountdown";
import { IconChevronRight } from "@/lib/icons";

// ── Tab definition ────────────────────────────────────────────────────────────

type Tab = "actor" | "supervisor" | "informed" | "observer" | "high_priority" | "all";
type TileFilter = "all" | "action_needed" | "due_today" | "overdue";

interface TabDef {
  id: Tab;
  label: string;
  redBadge: boolean;
  showBadge: boolean;
  description: string;
}

const TABS: TabDef[] = [
  { id: "actor",         label: "Actor",         redBadge: true,  showBadge: true,  description: "Tickets where I'm the action owner or have a pending task" },
  { id: "supervisor",    label: "Supervisor",     redBadge: false, showBadge: true,  description: "Tickets I'm supervising at the next level" },
  { id: "informed",      label: "Informed",       redBadge: false, showBadge: true,  description: "Tickets I've been added to as an informed member" },
  { id: "observer",      label: "Observer",       redBadge: false, showBadge: false, description: "Tickets I'm watching in read-only mode" },
  { id: "high_priority", label: "High Priority",  redBadge: true,  showBadge: true,  description: "HIGH / CRITICAL priority or SLA-breached tickets" },
  { id: "all",           label: "All Tickets",    redBadge: false, showBadge: false, description: "All tickets visible to my role" },
];

// ── Deadline helpers ──────────────────────────────────────────────────────────

/**
 * Returns the effective deadline for a ticket:
 * - Action owner (assigned to me): ticket SLA deadline
 * - Task holder only: earliest pending task due date
 * - Both apply: earlier of the two
 */
function effectiveDeadline(t: TicketListItem): Date | null {
  const sla  = t.sla_deadline_at        ? new Date(t.sla_deadline_at)        : null;
  const task = t.my_earliest_task_due_at ? new Date(t.my_earliest_task_due_at) : null;
  if (sla && task) return sla < task ? sla : task;
  return sla ?? task;
}

type TicketCategory = "overdue" | "due_today" | "high_priority" | "other";

function ticketCategory(t: TicketListItem, now: number, in24h: number): TicketCategory {
  const d = effectiveDeadline(t);
  if (d && d.getTime() < now)   return "overdue";
  if (d && d.getTime() <= in24h) return "due_today";
  if (t.priority === "HIGH" || t.priority === "CRITICAL") return "high_priority";
  return "other";
}

const CATEGORY_ORDER: Record<TicketCategory, number> = {
  overdue:       0,
  due_today:     1,
  high_priority: 2,
  other:         3,
};

function sortTickets(tickets: TicketListItem[]): TicketListItem[] {
  const now   = Date.now();
  const in24h = now + 24 * 60 * 60 * 1000;
  return [...tickets].sort((a, b) => {
    const ca = CATEGORY_ORDER[ticketCategory(a, now, in24h)];
    const cb = CATEGORY_ORDER[ticketCategory(b, now, in24h)];
    if (ca !== cb) return ca - cb;
    // Within same category: closest deadline first
    const da = effectiveDeadline(a)?.getTime() ?? Infinity;
    const db = effectiveDeadline(b)?.getTime() ?? Infinity;
    return da - db;
  });
}

// ── Summary tile ──────────────────────────────────────────────────────────────

function SummaryTile({
  label, count, sub, urgent = false, warning = false, active = false, onClick,
}: {
  label: string;
  count: number;
  sub?: string;
  urgent?: boolean;
  warning?: boolean;
  active?: boolean;
  onClick?: () => void;
}) {
  const isRed    = urgent  && count > 0;
  const isYellow = warning && count > 0;

  const borderCls = active
    ? isRed
      ? "border-red-500 bg-red-100 ring-2 ring-red-300"
      : isYellow
      ? "border-yellow-500 bg-yellow-100 ring-2 ring-yellow-300"
      : "border-blue-500 bg-blue-50 ring-2 ring-blue-300"
    : isRed
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
      title={active ? "Click to clear filter" : "Click to filter"}
      className={`rounded-lg border p-4 text-left hover:shadow-sm transition w-full ${borderCls}`}
    >
      <div className={`text-2xl ${countCls}`}>{count}</div>
      <div className="text-sm font-medium text-gray-700 mt-0.5">{label}</div>
      {sub && <div className="text-xs text-gray-600 mt-0.5">{sub}</div>}
    </button>
  );
}

// ── Ticket row ────────────────────────────────────────────────────────────────

function TicketRow({ ticket, showAdminHints }: { ticket: TicketListItem; showAdminHints?: boolean }) {
  const now   = Date.now();
  const in24h = now + 24 * 60 * 60 * 1000;
  const cat   = ticketCategory(ticket, now, in24h);
  const urgency =
    cat === "overdue"   ? "overdue" :
    cat === "due_today" ? "warning" :
    "ok";

  return (
    <Link
      href={`/tickets/${ticket.ticket_id}`}
      className={`flex items-center gap-3 px-4 py-3 hover:bg-gray-50 transition border-b border-gray-100 last:border-0 ${ticket.is_seah ? "border-l-2 border-l-red-400" : ""}`}
    >
      <UrgencyDot urgency={urgency} />

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-gray-600 font-mono">{ticket.grievance_id}</span>
          {ticket.is_seah && <SeahBadge />}
          {showAdminHints && ticket.needs_assignment && (
            <span
              className="text-xs font-medium text-amber-800 bg-amber-100 border border-amber-300 px-1.5 py-0.5 rounded"
              title="No officer matched auto-assign rules — check jurisdiction scopes"
            >
              Needs assignment
            </span>
          )}
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

      <div className="shrink-0 w-28 text-right">
        <SlaCountdown ticketId={ticket.ticket_id} />
      </div>

      <div className="hidden lg:block shrink-0 w-36 text-xs text-gray-600 truncate text-right">
        {ticket.assigned_to_user_id ?? "—"}
      </div>

      <div className="shrink-0">
        <CountBubble count={ticket.unseen_event_count} red />
      </div>

      <IconChevronRight size={16} className="text-gray-400 shrink-0" />
    </Link>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function QueuePage() {
  const { isAuthenticated, isAdmin } = useAuth();
  const [activeTab, setActiveTab]     = useState<Tab>("actor");
  const [tileFilter, setTileFilter]   = useState<TileFilter>("all");
  const [tickets, setTickets]         = useState<TicketListItem[]>([]);
  const [total, setTotal]             = useState(0);
  const [loading, setLoading]         = useState(true);
  const [tabCounts, setTabCounts]     = useState<Partial<Record<Tab, number>>>({});

  // Reset tile filter whenever the active tab changes
  useEffect(() => { setTileFilter("all"); }, [activeTab]);

  // ── Actor tab tickets — always fetched for tile counts ────────────────────
  const [actorTickets, setActorTickets] = useState<TicketListItem[]>([]);

  useEffect(() => {
    if (!isAuthenticated) return;
    listTickets({ tab: "actor", page_size: 100 })
      .then((r) => {
        setActorTickets(r.items);
        setTabCounts((prev) => ({ ...prev, actor: r.total }));
      })
      .catch(() => {});
  }, [isAuthenticated]);

  // ── Tile counts — computed from actor tickets using effectiveDeadline ─────
  const { actionNeeded, dueToday, overdue } = useMemo(() => {
    const now   = Date.now();
    const in24h = now + 24 * 60 * 60 * 1000;
    let actionNeeded = 0, dueToday = 0, overdue = 0;
    for (const t of actorTickets) {
      // Action Needed = all active actor tickets (not resolved / closed)
      if (!["RESOLVED", "CLOSED"].includes(t.status_code)) {
        actionNeeded++;
        const d = effectiveDeadline(t);
        if (d) {
          if (d.getTime() < now)              overdue++;
          else if (d.getTime() <= in24h)      dueToday++;
        }
      }
    }
    return { actionNeeded, dueToday, overdue };
  }, [actorTickets]);

  // ── Independent badge counts for non-actor tabs ───────────────────────────
  useEffect(() => {
    if (!isAuthenticated) return;
    (["supervisor", "informed", "high_priority"] as Tab[]).forEach((tab) => {
      listTickets({ tab, page_size: 1 })
        .then((r) => setTabCounts((prev) => ({ ...prev, [tab]: r.total })))
        .catch(() => {});
    });
  }, [isAuthenticated]);

  // ── Active tab ticket list ────────────────────────────────────────────────
  useEffect(() => {
    if (!isAuthenticated) return;
    setLoading(true);
    listTickets({ tab: activeTab, page_size: 100 })
      .then((r) => {
        setTickets(r.items);
        setTotal(r.total);
        const tabDef = TABS.find((t) => t.id === activeTab);
        if (tabDef?.showBadge) setTabCounts((prev) => ({ ...prev, [activeTab]: r.total }));
        if (activeTab === "actor") setActorTickets(r.items);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [activeTab, isAuthenticated]);

  // ── Sorted + filtered list ────────────────────────────────────────────────
  const displayedTickets = useMemo(() => {
    const now   = Date.now();
    const in24h = now + 24 * 60 * 60 * 1000;
    const sorted = sortTickets(tickets);
    if (tileFilter === "overdue")       return sorted.filter((t) => { const d = effectiveDeadline(t); return d && d.getTime() < now; });
    if (tileFilter === "due_today")     return sorted.filter((t) => { const d = effectiveDeadline(t); const ms = d?.getTime(); return ms !== undefined && ms !== null && ms >= now && ms <= in24h; });
    if (tileFilter === "action_needed") return sorted.filter((t) => !["RESOLVED", "CLOSED"].includes(t.status_code));
    return sorted;
  }, [tickets, tileFilter]);

  const activeTabDef = TABS.find((t) => t.id === activeTab)!;

  const tileCount = tileFilter !== "all"
    ? displayedTickets.length
    : total;

  // ── Tile click handler — toggle: clicking active tile clears filter ───────
  function handleTileClick(filter: TileFilter) {
    if (activeTab !== "actor") setActiveTab("actor");
    setTileFilter((prev) => prev === filter ? "all" : filter);
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-5">
        <h1 className="text-xl font-semibold text-gray-800">Tickets</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          {tileFilter !== "all"
            ? `${tileCount} ticket${tileCount !== 1 ? "s" : ""} · filtered · click tile again to clear`
            : `${total} ticket${total !== 1 ? "s" : ""} · ${activeTabDef.description}`}
        </p>
      </div>

      {/* Summary tiles */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        <SummaryTile
          label="Action Needed"
          count={actionNeeded}
          sub="all active tickets on my plate"
          active={tileFilter === "action_needed"}
          onClick={() => handleTileClick("action_needed")}
        />
        <SummaryTile
          label="Due Today"
          count={dueToday}
          sub="deadline within 24 h"
          warning
          active={tileFilter === "due_today"}
          onClick={() => handleTileClick("due_today")}
        />
        <SummaryTile
          label="Overdue"
          count={overdue}
          sub="deadline already passed"
          urgent
          active={tileFilter === "overdue"}
          onClick={() => handleTileClick("overdue")}
        />
      </div>

      {/* Tabs */}
      <div className="flex gap-0 border-b border-gray-200 mb-4 overflow-x-auto">
        {TABS.map((tab) => {
          const isActive = activeTab === tab.id;
          const count    = tabCounts[tab.id] ?? 0;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition-colors ${
                isActive
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab.label}
              {tab.showBadge && count > 0 && (
                <CountBubble count={count} red={tab.redBadge} />
              )}
            </button>
          );
        })}
      </div>

      {/* Tile filter chip — shown when a filter is active */}
      {tileFilter !== "all" && (
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs text-gray-500">Filtered by:</span>
          <span className="inline-flex items-center gap-1 bg-blue-100 text-blue-700 text-xs font-medium px-2.5 py-0.5 rounded-full">
            {tileFilter === "overdue"       && "Overdue"}
            {tileFilter === "due_today"     && "Due Today"}
            {tileFilter === "action_needed" && "Action Needed"}
            <button
              onClick={() => setTileFilter("all")}
              className="ml-1 text-blue-500 hover:text-blue-700 font-bold"
              title="Clear filter"
            >
              ×
            </button>
          </span>
        </div>
      )}

      {/* Ticket list */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-600 text-sm">Loading…</div>
        ) : displayedTickets.length === 0 ? (
          <div className="p-8 text-center text-gray-500 text-sm">
            {tileFilter !== "all" ? "No tickets match this filter." : "No tickets in this view."}
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
            {displayedTickets.map((t) => (
              <TicketRow key={t.ticket_id} ticket={t} showAdminHints={isAdmin} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
