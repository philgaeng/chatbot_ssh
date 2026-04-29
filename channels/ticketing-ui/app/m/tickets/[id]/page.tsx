"use client";

/**
 * /m/tickets/[id] — Mobile thread screen.
 * "A ticket is a conversation thread." — UI_SPEC.md §2.2
 *
 * Layout:
 *   sticky header (back + title + SLA)
 *   filter chips (horizontal scroll)
 *   scrollable thread (bubbles + system pills + task cards)
 *   fixed bottom bar (compose + primary CTA)
 */

import { use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  getTicket, getSla, performAction, markSeen, listTicketTasks, createTask, completeTask,
  type TicketDetail, type TicketEvent, type SlaStatus, type TicketTask, type TaskCreateRequest,
} from "@/lib/api";
import { useAuth } from "@/app/providers/AuthProvider";
import {
  SYSTEM_EVENT_TYPES, TASK_EVENT_TYPES, TASK_TYPES, getRoleBubbleStyle,
  systemEventLabel, urgencyDot, urgencyTextCls, type SlaUrgency,
} from "@/lib/mobile-constants";

// ── Type helpers ──────────────────────────────────────────────────────────────

type FilterChip = "all" | "mine" | "tasks" | "system" | string; // string = author user_id

// ── Role label for bubble footer ─────────────────────────────────────────────

function RoleLabel({ actorRole, userId, isMine }: { actorRole: string | null; userId: string | null; isMine: boolean }) {
  const style = getRoleBubbleStyle(actorRole);
  return (
    <div className={`text-[11px] mt-1 ${isMine ? "text-right text-blue-300" : `${style.labelCls}`}`}>
      {isMine ? "You" : `${style.emoji ? style.emoji + " " : ""}${style.label || userId || "Officer"}`}
    </div>
  );
}

// ── System pill ───────────────────────────────────────────────────────────────

function SystemPill({ event }: { event: TicketEvent }) {
  return (
    <div className="flex justify-center my-2 px-4">
      <span className="text-xs text-gray-400 bg-gray-100 rounded-full px-3 py-1 text-center">
        {systemEventLabel(event.event_type, event.payload)}
      </span>
    </div>
  );
}

// ── Note bubble ───────────────────────────────────────────────────────────────

function NoteBubble({ event, isMine }: { event: TicketEvent; isMine: boolean }) {
  const style = getRoleBubbleStyle(event.actor_role);
  const time = new Date(event.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  if (isMine) {
    return (
      <div className="flex flex-col items-end px-4 my-1">
        <div className="max-w-[80%] bg-blue-500 text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-sm">
          {event.note}
        </div>
        <div className="text-[11px] text-gray-400 mt-0.5">You · {time}</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-start px-4 my-1">
      <div className={`max-w-[80%] rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm text-gray-800 ${style.bubbleCls || "bg-gray-100"}`}>
        {event.note}
      </div>
      <RoleLabel actorRole={event.actor_role} userId={event.created_by_user_id} isMine={false} />
      <div className="text-[11px] text-gray-400">{time}</div>
    </div>
  );
}

// ── Task card ─────────────────────────────────────────────────────────────────

function TaskCard({
  event,
  tasks,
  currentUserId,
  ticketId,
  onComplete,
}: {
  event: TicketEvent;
  tasks: TicketTask[];
  currentUserId: string;
  ticketId: string;
  onComplete: (taskId: string) => void;
}) {
  const taskId = event.payload?.task_id as string | undefined;
  const task = tasks.find((t) => t.task_id === taskId);
  const isCompleted = event.event_type === "TASK_COMPLETED" || task?.status === "DONE";
  const taskType = (event.payload?.task_type as string) ?? "TASK";
  const assignedTo = (event.payload?.assigned_to_user_id as string) ?? "—";
  const description = (event.payload?.description as string) ?? "";
  const dueDate = event.payload?.due_date as string | undefined;
  const typeInfo = TASK_TYPES.find((t) => t.key === taskType);
  const isAssignedToMe = assignedTo === currentUserId || assignedTo === "mock-super-admin";

  const time = new Date(event.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  return (
    <div className={`mx-4 my-2 rounded-xl border text-sm ${
      isCompleted
        ? "border-green-200 bg-green-50"
        : "border-amber-200 bg-amber-50"
    }`}>
      <div className={`px-3 py-2 rounded-t-xl font-semibold flex items-center gap-1.5 ${
        isCompleted ? "text-green-700" : "text-amber-800"
      }`}>
        <span>{typeInfo?.icon ?? "📋"}</span>
        <span>{typeInfo?.label ?? taskType.replace(/_/g, " ")}</span>
        {isCompleted && <span className="ml-auto text-xs font-normal text-green-600">✅ Done</span>}
      </div>
      <div className="px-3 pb-3 space-y-1">
        <div className="text-gray-600">
          → <span className="font-medium">{assignedTo === currentUserId ? "You" : assignedTo}</span>
        </div>
        {description && <div className="text-gray-700 italic">"{description}"</div>}
        <div className="text-xs text-gray-400">
          {dueDate ? `Due: ${dueDate} · ` : ""}
          Assigned {time}
          {isCompleted && task?.completed_at
            ? ` · Done ${new Date(task.completed_at).toLocaleDateString()}`
            : ""}
        </div>
        {/* Complete button — only for the assigned officer, only when PENDING */}
        {!isCompleted && isAssignedToMe && taskId && (
          <button
            onClick={() => onComplete(taskId)}
            className="mt-2 w-full bg-amber-500 hover:bg-amber-600 active:bg-amber-700 text-white text-sm font-medium py-2 rounded-lg transition-colors"
          >
            ✓ Mark Complete
          </button>
        )}
      </div>
    </div>
  );
}

// ── Assign task bottom sheet ───────────────────────────────────────────────────

function AssignTaskSheet({
  ticketId,
  onClose,
  onAssigned,
}: {
  ticketId: string;
  onClose: () => void;
  onAssigned: () => void;
}) {
  const { user } = useAuth();
  const [taskType, setTaskType] = useState<string>("");
  const [assignTo, setAssignTo] = useState(user?.sub ?? "");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const canSubmit = taskType !== "" && assignTo.trim() !== "";

  const submit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    try {
      const body: TaskCreateRequest = {
        task_type: taskType,
        assigned_to_user_id: assignTo.trim(),
        description: description.trim() || undefined,
      };
      await createTask(ticketId, body);
      onAssigned();
    } catch (e) {
      console.error("Task assignment failed", e);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    /* Backdrop */
    <div className="fixed inset-0 z-50 flex flex-col justify-end" onClick={onClose}>
      {/* Sheet */}
      <div
        className="bg-white rounded-t-2xl shadow-xl p-5 max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="w-12 h-1 bg-gray-300 rounded-full mx-auto mb-4" />
        <h3 className="text-base font-semibold text-gray-900 mb-4">📋 Assign task</h3>

        {/* Task type grid */}
        <div className="mb-4">
          <div className="text-xs font-medium text-gray-500 uppercase mb-2">Type</div>
          <div className="grid grid-cols-2 gap-2">
            {TASK_TYPES.map((t) => (
              <button
                key={t.key}
                onClick={() => setTaskType(t.key)}
                className={`flex items-center gap-2 p-3 rounded-xl border text-sm font-medium transition-colors ${
                  taskType === t.key
                    ? "border-blue-500 bg-blue-50 text-blue-700"
                    : "border-gray-200 text-gray-700 active:bg-gray-50"
                }`}
              >
                <span className="text-lg">{t.icon}</span>
                <span>{t.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Assign to */}
        <div className="mb-4">
          <label className="text-xs font-medium text-gray-500 uppercase mb-1 block">Assign to</label>
          <input
            type="text"
            value={assignTo}
            onChange={(e) => setAssignTo(e.target.value)}
            placeholder="Officer user ID"
            className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500"
          />
        </div>

        {/* Instructions */}
        <div className="mb-5">
          <label className="text-xs font-medium text-gray-500 uppercase mb-1 block">
            Instructions (optional)
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            placeholder="What should they do?"
            className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500 resize-none"
          />
        </div>

        <button
          onClick={submit}
          disabled={!canSubmit || submitting}
          className={`w-full py-3 rounded-xl text-white font-semibold text-sm transition-colors ${
            canSubmit && !submitting
              ? "bg-blue-600 active:bg-blue-700"
              : "bg-gray-300 text-gray-400"
          }`}
        >
          {submitting ? "Assigning…" : "Assign Task"}
        </button>
      </div>
    </div>
  );
}

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

// ── Filter chips ──────────────────────────────────────────────────────────────

function FilterChips({
  events,
  currentUserId,
  active,
  pendingTaskCount,
  onChange,
}: {
  events: TicketEvent[];
  currentUserId: string;
  active: FilterChip;
  pendingTaskCount: number;
  onChange: (chip: FilterChip) => void;
}) {
  // Unique note/bubble authors other than current user
  const authors = useMemo(() => {
    const seen = new Set<string>();
    const result: { userId: string; role: string | null }[] = [];
    for (const e of events) {
      if (SYSTEM_EVENT_TYPES.has(e.event_type)) continue;
      if (TASK_EVENT_TYPES.has(e.event_type)) continue;
      const uid = e.created_by_user_id;
      if (!uid || uid === currentUserId || seen.has(uid)) continue;
      seen.add(uid);
      result.push({ userId: uid, role: e.actor_role });
    }
    return result;
  }, [events, currentUserId]);

  const chip = (id: FilterChip, label: string, badge?: number) => (
    <button
      key={id}
      onClick={() => onChange(active === id ? "all" : id)}
      className={`flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
        active === id
          ? "bg-blue-600 text-white border-blue-600"
          : "bg-white text-gray-600 border-gray-300"
      }`}
    >
      {label}
      {badge !== undefined && badge > 0 && (
        <span className={`ml-1 ${active === id ? "text-blue-200" : "text-amber-500"}`}>
          {badge}
        </span>
      )}
    </button>
  );

  return (
    <div className="flex gap-2 overflow-x-auto px-4 py-2 scrollbar-none">
      {chip("all", "All")}
      {chip("mine", "👤 You")}
      {authors.map(({ userId, role }) => {
        const style = getRoleBubbleStyle(role);
        return chip(userId, `${style.emoji || "@"}${style.label || userId.split("-")[0]}`);
      })}
      {chip("tasks", "📋 Tasks", pendingTaskCount)}
      {chip("system", "⚙️ System")}
    </div>
  );
}

// ── SLA sub-header pill ───────────────────────────────────────────────────────

function SlaSubHeader({ ticket, sla }: { ticket: TicketDetail; sla: SlaStatus | null }) {
  const urgency: SlaUrgency = ticket.sla_breached ? "overdue" : (sla?.urgency ?? "none");
  const dot = urgencyDot(urgency);
  const cls = urgencyTextCls(urgency);

  let timeText = "Active";
  if (ticket.sla_breached) timeText = "Overdue";
  else if (sla?.remaining_hours) {
    const h = sla.remaining_hours;
    timeText = h < 24 ? `${Math.round(h)}h left` : `${Math.round(h / 24)}d left`;
  }

  const step = ticket.current_step?.display_name ?? ticket.status_code;
  const loc = ticket.location_code ?? "";

  return (
    <div className={`flex items-center gap-1.5 px-4 py-1.5 bg-gray-50 border-b border-gray-200 text-xs ${cls}`}>
      <span>{dot}</span>
      <span className="font-medium">{step}</span>
      {loc && <><span className="text-gray-300">·</span><span className="text-gray-500">{loc}</span></>}
      <span className="text-gray-300">·</span>
      <span>{timeText}</span>
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

  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [sla, setSla] = useState<SlaStatus | null>(null);
  const [tasks, setTasks] = useState<TicketTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState<FilterChip>("all");
  const [noteText, setNoteText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showMore, setShowMore] = useState(false);
  const [showAssignTask, setShowAssignTask] = useState(false);

  const threadEndRef = useRef<HTMLDivElement>(null);

  // ── Data loading ────────────────────────────────────────────────────────────

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

  useEffect(() => {
    loadTicket();
  }, [loadTicket]);

  // Mark seen on open
  useEffect(() => {
    markSeen(ticketId).catch(() => {});
  }, [ticketId]);

  // Scroll to bottom when events load
  useEffect(() => {
    if (ticket && !loading) {
      threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [ticket, loading]);

  // ── Filter events ───────────────────────────────────────────────────────────

  const filteredEvents = useMemo(() => {
    if (!ticket) return [];
    const events = ticket.events;
    switch (activeFilter) {
      case "all":    return events;
      case "mine":   return events.filter((e) => e.created_by_user_id === currentUserId);
      case "tasks":  return events.filter((e) => TASK_EVENT_TYPES.has(e.event_type));
      case "system": return events.filter((e) => SYSTEM_EVENT_TYPES.has(e.event_type));
      default:       return events.filter((e) => e.created_by_user_id === activeFilter);
    }
  }, [ticket, activeFilter, currentUserId]);

  const pendingTaskCount = useMemo(
    () => tasks.filter((t) => t.status === "PENDING").length,
    [tasks],
  );

  // Pending tasks assigned to me — shown in sub-header banner
  const myPendingTasks = useMemo(
    () => tasks.filter((t) => t.status === "PENDING" && (t.assigned_to_user_id === currentUserId || t.assigned_to_user_id === "mock-super-admin")),
    [tasks, currentUserId],
  );

  // ── Actions ─────────────────────────────────────────────────────────────────

  const handleAction = useCallback(
    async (actionType: string) => {
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
    },
    [ticket, ticketId, loadTicket],
  );

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
      setNoteText(text); // restore on error
    } finally {
      setSubmitting(false);
    }
  }, [noteText, submitting, ticketId, loadTicket]);

  const handleCompleteTask = useCallback(
    async (taskId: string) => {
      if (!ticket) return;
      try {
        await completeTask(ticketId, taskId);
        await loadTicket();
      } catch (e) {
        console.error("Complete task failed", e);
      }
    },
    [ticket, ticketId, loadTicket],
  );

  // ── Render ──────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-sm text-gray-400">Loading…</div>
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
      {/* ── Sticky header ─────────────────────────────────────────────── */}
      <div className="flex-shrink-0 bg-white border-b border-gray-200 pt-safe-top">
        {/* Title bar */}
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

        {/* SLA sub-header */}
        <SlaSubHeader ticket={ticket} sla={sla} />

        {/* Task pending banner */}
        {myPendingTasks.length > 0 && (
          <div className="bg-amber-50 border-b border-amber-200 px-4 py-1.5 text-xs text-amber-700 font-medium">
            📋 {myPendingTasks.length} task{myPendingTasks.length > 1 ? "s" : ""} assigned to you
          </div>
        )}

        {/* Filter chips */}
        <FilterChips
          events={ticket.events}
          currentUserId={currentUserId}
          active={activeFilter}
          pendingTaskCount={pendingTaskCount}
          onChange={setActiveFilter}
        />
      </div>

      {/* ── Thread ────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto py-2">
        {filteredEvents.length === 0 ? (
          <div className="flex justify-center py-8 text-xs text-gray-400">No messages in this view</div>
        ) : (
          filteredEvents.map((event) => {
            const isMine = event.created_by_user_id === currentUserId;

            if (SYSTEM_EVENT_TYPES.has(event.event_type)) {
              return <SystemPill key={event.event_id} event={event} />;
            }

            if (TASK_EVENT_TYPES.has(event.event_type)) {
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
            }

            return <NoteBubble key={event.event_id} event={event} isMine={isMine} />;
          })
        )}
        <div ref={threadEndRef} />
      </div>

      {/* ── Fixed bottom bar ──────────────────────────────────────────── */}
      <div className="flex-shrink-0 bg-white border-t border-gray-200 pb-safe-bottom">
        {/* Compose bar */}
        <div className="flex items-end gap-2 px-3 py-2">
          <div className="flex-1 bg-gray-100 rounded-2xl px-4 py-2.5 min-h-[44px] flex items-center">
            <textarea
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
              placeholder="Add a note…"
              rows={1}
              className="w-full bg-transparent text-sm text-gray-800 placeholder-gray-400 resize-none focus:outline-none"
              style={{ maxHeight: "96px" }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleNote();
                }
              }}
            />
          </div>
          <button
            onClick={handleNote}
            disabled={!noteText.trim() || submitting}
            className={`w-10 h-10 rounded-full flex items-center justify-center text-white transition-colors flex-shrink-0 ${
              noteText.trim() && !submitting
                ? "bg-blue-600 active:bg-blue-700"
                : "bg-gray-300"
            }`}
          >
            ↑
          </button>
        </div>

        {/* Primary CTA */}
        <PrimaryCtaBar
          ticket={ticket}
          onAction={handleAction}
          onMore={() => setShowMore(true)}
        />
      </div>

      {/* ── Sheets ────────────────────────────────────────────────────── */}
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
          onClose={() => setShowAssignTask(false)}
          onAssigned={async () => {
            setShowAssignTask(false);
            await loadTicket();
          }}
        />
      )}
    </div>
  );
}
