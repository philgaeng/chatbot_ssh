"use client";

/**
 * /m/tickets/[id] — Mobile thread screen.
 * Layout: sticky header → filter chips → scrollable thread → fixed bottom bar.
 * Shared sub-components live in components/thread/ and are reused by the desktop.
 */

import { use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  getTicket, getSla, performAction, markSeen, listTicketTasks, completeTask,
  type TicketDetail, type TicketEvent, type SlaStatus, type TicketTask,
} from "@/lib/api";
import { useAuth } from "@/app/providers/AuthProvider";
import { SYSTEM_EVENT_TYPES, TASK_EVENT_TYPES, NOTIFICATION_ONLY_EVENT_TYPES } from "@/lib/mobile-constants";

import { NoteBubble }                        from "@/components/thread/NoteBubble";
import { SystemPill }                         from "@/components/thread/SystemPill";
import { TaskCard, AssignTaskSheet }          from "@/components/thread/TaskCard";
import { FilterChips, type FilterChip }       from "@/components/thread/FilterChips";
import { ViewersBar }                         from "@/components/thread/ViewersBar";
import { ComposeBar }                         from "@/components/thread/ComposeBar";
import { SlaSubHeader, WorkflowMiniStepper }  from "@/components/thread/SlaSubHeader";

// ── More actions bottom sheet ─────────────────────────────────────────────────

function MoreActionsSheet({
  ticket,
  onAction,
  onAssignTask,
  onClose,
}: {
  ticket: TicketDetail;
  onAction: (type: string) => void;
  onAssignTask: () => void;
  onClose: () => void;
}) {
  const canEscalate = !["RESOLVED", "CLOSED"].includes(ticket.status_code);
  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end" onClick={onClose}>
      <div className="bg-white rounded-t-2xl shadow-xl p-5" onClick={(e) => e.stopPropagation()}>
        <div className="w-12 h-1 bg-gray-300 rounded-full mx-auto mb-4" />
        <div className="space-y-1">
          {canEscalate && (
            <button
              onClick={() => { onAction("ESCALATE"); onClose(); }}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-xl active:bg-gray-50 text-left"
            >
              <span className="text-xl">🔺</span>
              <span className="text-sm font-medium text-gray-800">Escalate to next level</span>
            </button>
          )}
          <button
            onClick={() => { onAssignTask(); onClose(); }}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-xl active:bg-gray-50 text-left"
          >
            <span className="text-xl">📋</span>
            <span className="text-sm font-medium text-gray-800">Assign a task</span>
          </button>
          {canEscalate && (
            <button
              onClick={() => { onAction("CLOSE"); onClose(); }}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-xl active:bg-gray-50 text-left"
            >
              <span className="text-xl">🔒</span>
              <span className="text-sm font-medium text-red-600">Close without resolve</span>
            </button>
          )}
        </div>
        <div className="mt-3 pt-3 border-t border-gray-100">
          <button onClick={onClose} className="w-full py-3 text-sm font-medium text-gray-500">
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Primary CTA bar ───────────────────────────────────────────────────────────

function PrimaryCtaBar({
  ticket,
  onAction,
  onMore,
}: {
  ticket: TicketDetail;
  onAction: (type: string) => void;
  onMore: () => void;
}) {
  const { status_code } = ticket;

  if (status_code === "RESOLVED" || status_code === "CLOSED") {
    return (
      <div className="px-4 py-2">
        <div className="text-center text-sm text-gray-400 py-2">
          {status_code === "RESOLVED" ? "✅ Case resolved" : "🔒 Case closed"}
        </div>
      </div>
    );
  }

  if (status_code === "OPEN") {
    return (
      <div className="px-4 py-2">
        <button
          onClick={() => onAction("ACKNOWLEDGE")}
          className="w-full bg-blue-600 active:bg-blue-700 text-white font-semibold py-3 rounded-xl text-sm transition-colors"
        >
          ✅ Acknowledge — tap to start
        </button>
      </div>
    );
  }

  return (
    <div className="flex gap-2 px-4 py-2">
      <button
        onClick={() => onAction("RESOLVE")}
        className="flex-1 bg-green-600 active:bg-green-700 text-white font-semibold py-3 rounded-xl text-sm transition-colors"
      >
        🏁 Resolve
      </button>
      <button
        onClick={onMore}
        className="flex-1 bg-gray-100 active:bg-gray-200 text-gray-800 font-semibold py-3 rounded-xl text-sm transition-colors"
      >
        🔺 More ▾
      </button>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function MobileThreadPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: ticketId } = use(params);
  const router = useRouter();
  const { user } = useAuth();
  const currentUserId = user?.sub ?? "mock-super-admin";

  const [ticket, setTicket]       = useState<TicketDetail | null>(null);
  const [sla, setSla]             = useState<SlaStatus | null>(null);
  const [tasks, setTasks]         = useState<TicketTask[]>([]);
  const [loading, setLoading]     = useState(true);
  const [activeFilter, setActiveFilter] = useState<FilterChip>("all");
  const [noteText, setNoteText]   = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showMore, setShowMore]   = useState(false);
  const [showAssignTask, setShowAssignTask] = useState(false);

  const threadEndRef = useRef<HTMLDivElement>(null);

  // ── Data loading ────────────────────────────────────────────────────────

  const loadTicket = useCallback(async () => {
    try {
      const [t, s, tk] = await Promise.all([
        getTicket(ticketId),
        getSla(ticketId).catch(() => null),
        listTicketTasks(ticketId).catch(() => [] as TicketTask[]),
      ]);
      setTicket(t);
      setSla(s);
      setTasks(tk);
    } catch (e) {
      console.error("Failed to load ticket", e);
    } finally {
      setLoading(false);
    }
  }, [ticketId]);

  useEffect(() => { loadTicket(); }, [loadTicket]);
  useEffect(() => { markSeen(ticketId).catch(() => {}); }, [ticketId]);
  useEffect(() => {
    if (ticket && !loading) threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [ticket, loading]);

  // ── Derived state ───────────────────────────────────────────────────────

  const filteredEvents = useMemo(() => {
    if (!ticket) return [];
    switch (activeFilter) {
      case "all":    return ticket.events;
      case "mine":   return ticket.events.filter((e) => e.created_by_user_id === currentUserId);
      case "tasks":  return ticket.events.filter((e) => TASK_EVENT_TYPES.has(e.event_type));
      case "system": return ticket.events.filter((e) => SYSTEM_EVENT_TYPES.has(e.event_type));
      default:       return ticket.events.filter((e) => e.created_by_user_id === activeFilter);
    }
  }, [ticket, activeFilter, currentUserId]);

  const pendingTaskCount = useMemo(
    () => tasks.filter((t) => t.status === "PENDING").length,
    [tasks],
  );

  const viewerIds = useMemo(
    () => new Set((ticket?.viewers ?? []).map((v) => v.user_id)),
    [ticket],
  );

  const myPendingTasks = useMemo(
    () => tasks.filter((t) => t.status === "PENDING" &&
      (t.assigned_to_user_id === currentUserId || t.assigned_to_user_id === "mock-super-admin")),
    [tasks, currentUserId],
  );

  const canManageViewers = useMemo(
    () => !!ticket && ticket.assigned_to_user_id === currentUserId,
    [ticket, currentUserId],
  );

  const mentionParticipants = useMemo(() => {
    if (!ticket) return [];
    const ids = new Set<string>();
    if (ticket.assigned_to_user_id) ids.add(ticket.assigned_to_user_id);
    (ticket.viewers ?? []).forEach((v) => ids.add(v.user_id));
    ids.delete(currentUserId);
    const list = Array.from(ids).map((id) => ({ user_id: id, label: `@${id}` }));
    list.unshift({ user_id: "all", label: "@all" });
    return list;
  }, [ticket, currentUserId]);

  // ── Actions ─────────────────────────────────────────────────────────────

  const handleAction = useCallback(async (actionType: string) => {
    if (!ticket) return;
    setSubmitting(true);
    try {
      await performAction(ticketId, { action_type: actionType });
      await loadTicket();
    } catch (e) {
      console.error("Action failed", e);
    } finally {
      setSubmitting(false);
    }
  }, [ticket, ticketId, loadTicket]);

  const handleNote = useCallback(async () => {
    if (!noteText.trim() || submitting) return;
    setSubmitting(true);
    const text = noteText.trim();
    setNoteText("");
    try {
      await performAction(ticketId, { action_type: "NOTE", note: text });
      await loadTicket();
      threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
    } catch (e) {
      console.error("Note failed", e);
      setNoteText(text);
    } finally {
      setSubmitting(false);
    }
  }, [noteText, submitting, ticketId, loadTicket]);

  const handleCompleteTask = useCallback(async (taskId: string) => {
    if (!ticket) return;
    try {
      await completeTask(ticketId, taskId);
      await loadTicket();
    } catch (e) {
      console.error("Complete task failed", e);
    }
  }, [ticket, ticketId, loadTicket]);

  // ── Render ──────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-sm text-gray-400 animate-pulse">Loading…</div>
      </div>
    );
  }

  if (!ticket) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3">
        <div className="text-3xl">⚠️</div>
        <div className="text-sm text-gray-500">Ticket not found</div>
        <button onClick={() => router.back()} className="text-blue-600 text-sm">← Go back</button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-dvh bg-white">

      {/* ── Sticky header ───────────────────────────────────────── */}
      <div className="flex-shrink-0 bg-white border-b border-gray-200 pt-safe-top">
        <div className="flex items-center gap-2 px-2 py-3">
          <button onClick={() => router.back()} className="p-2 text-gray-500 active:bg-gray-100 rounded-lg">
            ←
          </button>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-gray-900 truncate">{ticket.grievance_id}</span>
              {ticket.is_seah && (
                <span className="text-[10px] font-bold text-red-600 bg-red-50 px-1.5 py-0.5 rounded shrink-0">
                  🔒 SEAH
                </span>
              )}
            </div>
            <div className="text-xs text-gray-400 truncate">
              {ticket.grievance_summary ?? "No summary"}
            </div>
          </div>
          <button className="p-2 text-gray-400 active:bg-gray-100 rounded-lg text-lg">⋮</button>
        </div>

        <SlaSubHeader ticket={ticket} sla={sla} />

        {/* Mini stepper — needs full step list; current_step only carries one step,
            so stepper will show just that step until we wire a full step list API. */}
        {ticket.current_step && (
          <WorkflowMiniStepper
            steps={[ticket.current_step]}
            currentStepKey={ticket.current_step.step_key}
          />
        )}

        {myPendingTasks.length > 0 && (
          <div className="bg-amber-50 border-b border-amber-200 px-4 py-1.5 text-xs text-amber-700 font-medium">
            📋 {myPendingTasks.length} task{myPendingTasks.length > 1 ? "s" : ""} assigned to you
          </div>
        )}

        <FilterChips
          events={ticket.events}
          currentUserId={currentUserId}
          active={activeFilter}
          pendingTaskCount={pendingTaskCount}
          onChange={setActiveFilter}
        />

        <ViewersBar
          viewers={ticket.viewers ?? []}
          canManage={canManageViewers}
          ticketId={ticketId}
          onChanged={loadTicket}
        />
      </div>

      {/* ── Thread ──────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto py-2">
        {filteredEvents.length === 0 ? (
          <div className="flex justify-center py-8 text-xs text-gray-400">No messages in this view</div>
        ) : (
          filteredEvents
            .filter((e: TicketEvent) => !NOTIFICATION_ONLY_EVENT_TYPES.has(e.event_type))
            .map((event: TicketEvent) => {
              const isMine = event.created_by_user_id === currentUserId;
              if (SYSTEM_EVENT_TYPES.has(event.event_type))
                return <SystemPill key={event.event_id} event={event} />;
              if (TASK_EVENT_TYPES.has(event.event_type))
                return (
                  <TaskCard
                    key={event.event_id}
                    event={event}
                    tasks={tasks}
                    currentUserId={currentUserId}
                    ticketId={ticketId}
                    onComplete={handleCompleteTask}
                  />
                );
              return <NoteBubble key={event.event_id} event={event} isMine={isMine} assignedToUserId={ticket.assigned_to_user_id} viewerIds={viewerIds} />;
            })
        )}
        <div ref={threadEndRef} />
      </div>

      {/* ── Fixed bottom bar ────────────────────────────────────── */}
      <div className="flex-shrink-0 bg-white border-t border-gray-200 pb-safe-bottom">
        <ComposeBar
          value={noteText}
          onChange={setNoteText}
          onSubmit={handleNote}
          disabled={submitting}
          participants={mentionParticipants}
        />
        <PrimaryCtaBar ticket={ticket} onAction={handleAction} onMore={() => setShowMore(true)} />
      </div>

      {/* ── Sheets ──────────────────────────────────────────────── */}
      {showMore && (
        <MoreActionsSheet
          ticket={ticket}
          onAction={handleAction}
          onAssignTask={() => setShowAssignTask(true)}
          onClose={() => setShowMore(false)}
        />
      )}
      {showAssignTask && (
        <AssignTaskSheet
          ticketId={ticketId}
          variant="sheet"
          onClose={() => setShowAssignTask(false)}
          onAssigned={async () => { setShowAssignTask(false); await loadTicket(); }}
        />
      )}
    </div>
  );
}
