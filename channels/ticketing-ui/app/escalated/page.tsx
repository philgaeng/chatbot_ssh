"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { listTickets, type TicketListItem } from "@/lib/api";
import { useAuth } from "@/app/providers/AuthProvider";
import { StatusBadge, PriorityBadge, SeahBadge, UrgencyDot, CountBubble } from "@/components/ui/Badge";
import { SlaCountdown } from "@/components/ui/SlaCountdown";

function TicketRow({ ticket }: { ticket: TicketListItem }) {
  return (
    <Link
      href={`/tickets/${ticket.ticket_id}`}
      className={`flex items-center gap-3 px-4 py-3 hover:bg-gray-50 transition border-b border-gray-100 last:border-0 ${ticket.is_seah ? "border-l-2 border-l-red-400" : ""}`}
    >
      <UrgencyDot urgency="overdue" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-gray-400 font-mono">{ticket.grievance_id}</span>
          {ticket.is_seah && <SeahBadge />}
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

export default function EscalatedPage() {
  const { isAuthenticated } = useAuth();
  const [tickets, setTickets] = useState<TicketListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated) return;
    setLoading(true);
    listTickets({ status_code: "ESCALATED", page_size: 100 })
      .then((r) => { setTickets(r.items); setTotal(r.total); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [isAuthenticated]);

  return (
    <div className="p-6">
      <div className="mb-5">
        <h1 className="text-xl font-semibold text-gray-800 flex items-center gap-2">
          <AlertTriangle size={20} strokeWidth={2} className="text-orange-500" />
          Escalated Tickets
        </h1>
        <p className="text-sm text-gray-500 mt-0.5">
          {total} ticket{total !== 1 ? "s" : ""} — SLA-breached or manually escalated
        </p>
      </div>

      {/* Summary bar */}
      {!loading && total > 0 && (
        <div className="bg-orange-50 border border-orange-200 rounded-lg px-4 py-3 mb-4 text-sm text-orange-800">
          <strong>{total}</strong> ticket{total !== 1 ? "s" : ""} need{total === 1 ? "s" : ""} escalation review.
          Ensure each has an active assignee and updated note.
        </div>
      )}

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-400 text-sm">Loading…</div>
        ) : tickets.length === 0 ? (
          <div className="p-8 text-center text-gray-400 text-sm">
            <CheckCircle2 size={18} strokeWidth={2} className="inline mr-1.5 text-green-500" />
            No escalated tickets right now.
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
