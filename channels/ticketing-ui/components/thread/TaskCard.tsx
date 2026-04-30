"use client";

import { useState } from "react";
import { Check, ClipboardList } from "lucide-react";
import { TASK_TYPES } from "@/lib/mobile-constants";
import { TaskTypeIcon } from "@/lib/icons";
import { createTask } from "@/lib/api";
import { useAuth } from "@/app/providers/AuthProvider";
import type { TicketEvent, TicketTask, TaskCreateRequest } from "@/lib/api";

// ── Task card ─────────────────────────────────────────────────────────────────

export function TaskCard({
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
      isCompleted ? "border-green-200 bg-green-50" : "border-amber-200 bg-amber-50"
    }`}>
      <div className={`px-3 py-2 rounded-t-xl font-semibold flex items-center gap-1.5 ${
        isCompleted ? "text-green-700" : "text-amber-800"
      }`}>
        <TaskTypeIcon name={typeInfo?.icon ?? "ClipboardList"} size={15} strokeWidth={2} />
        <span>{typeInfo?.label ?? taskType.replace(/_/g, " ")}</span>
        {isCompleted && (
          <span className="ml-auto inline-flex items-center gap-0.5 text-xs font-normal text-green-600">
            <Check size={12} strokeWidth={2.5} />
            Done
          </span>
        )}
      </div>
      <div className="px-3 pb-3 space-y-1">
        <div className="text-gray-600">
          → <span className="font-medium">{assignedTo === currentUserId ? "You" : assignedTo}</span>
        </div>
        {description && <div className="text-gray-700 italic">&ldquo;{description}&rdquo;</div>}
        <div className="text-xs text-gray-400">
          {dueDate ? `Due: ${dueDate} · ` : ""}
          Assigned {time}
          {isCompleted && task?.completed_at
            ? ` · Done ${new Date(task.completed_at).toLocaleDateString()}`
            : ""}
        </div>
        {!isCompleted && isAssignedToMe && taskId && (
          <button
            onClick={() => onComplete(taskId)}
            className="mt-2 w-full bg-amber-500 hover:bg-amber-600 active:bg-amber-700 text-white text-sm font-medium py-2 rounded-lg transition-colors"
          >
            <Check size={13} strokeWidth={2.5} className="inline mr-1" />
            Mark Complete
          </button>
        )}
      </div>
    </div>
  );
}

// ── Assign task sheet/modal ───────────────────────────────────────────────────
// On mobile: bottom sheet (flex-col justify-end).
// On desktop: centered modal (items-center justify-center).

export function AssignTaskSheet({
  ticketId,
  onClose,
  onAssigned,
  variant = "sheet",
}: {
  ticketId: string;
  onClose: () => void;
  onAssigned: () => void;
  /** "sheet" = mobile bottom, "modal" = desktop centered */
  variant?: "sheet" | "modal";
}) {
  const { user } = useAuth();
  const [taskType, setTaskType] = useState("");
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

  const panelCls = variant === "modal"
    ? "bg-white rounded-2xl shadow-xl p-5 w-full max-w-md max-h-[85vh] overflow-y-auto"
    : "bg-white rounded-t-2xl shadow-xl p-5 max-h-[85vh] overflow-y-auto";

  const wrapperCls = variant === "modal"
    ? "fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
    : "fixed inset-0 z-50 flex flex-col justify-end bg-black/20";

  return (
    <div className={wrapperCls} onClick={onClose}>
      <div className={panelCls} onClick={(e) => e.stopPropagation()}>
        <div className="w-12 h-1 bg-gray-300 rounded-full mx-auto mb-4" />
        <h3 className="text-base font-semibold text-gray-900 mb-4 flex items-center gap-1.5">
          <ClipboardList size={16} strokeWidth={2} className="text-gray-600" />
          Assign task
        </h3>

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
                <TaskTypeIcon name={t.icon} size={16} strokeWidth={2} />
                <span>{t.label}</span>
              </button>
            ))}
          </div>
        </div>

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
            canSubmit && !submitting ? "bg-blue-600 hover:bg-blue-700" : "bg-gray-300 text-gray-400"
          }`}
        >
          {submitting ? "Assigning…" : "Assign Task"}
        </button>
      </div>
    </div>
  );
}
