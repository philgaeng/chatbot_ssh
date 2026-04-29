"use client";

/**
 * /m/tasks — My pending tasks across all tickets.
 * UI_SPEC.md §2.5 — "GET /api/v1/users/me/tasks"
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { listMyTasks, completeTask, type TicketTask } from "@/lib/api";
import { TASK_TYPES } from "@/lib/mobile-constants";
import { useAuth } from "@/app/providers/AuthProvider";

function taskTypeInfo(key: string) {
  return TASK_TYPES.find((t) => t.key === key) ?? { icon: "📋", label: key.replace(/_/g, " ") };
}

function TaskItem({ task, onComplete }: { task: TicketTask; onComplete: (t: TicketTask) => void }) {
  const [completing, setCompleting] = useState(false);
  const info = taskTypeInfo(task.task_type);
  const overdue = task.due_date && new Date(task.due_date) < new Date();

  const handleComplete = async () => {
    setCompleting(true);
    try {
      await completeTask(task.ticket_id, task.task_id);
      onComplete(task);
    } catch (e) {
      console.error("Complete failed", e);
    } finally {
      setCompleting(false);
    }
  };

  return (
    <div className={`mx-4 my-2 rounded-xl border ${overdue ? "border-red-200 bg-red-50" : "border-amber-200 bg-amber-50"}`}>
      <div className="px-4 py-3">
        <div className="flex items-start gap-2 mb-1">
          <span className="text-lg">{info.icon}</span>
          <div className="flex-1 min-w-0">
            <div className="font-medium text-sm text-gray-900">{info.label}</div>
            {task.description && (
              <div className="text-xs text-gray-600 mt-0.5 italic">"{task.description}"</div>
            )}
            <div className="text-xs text-gray-400 mt-1 flex items-center gap-2">
              <Link href={`/m/tickets/${task.ticket_id}`} className="text-blue-600 underline">
                {task.ticket_id.slice(0, 8)}…
              </Link>
              {task.due_date && (
                <span className={overdue ? "text-red-600 font-medium" : ""}>
                  Due {task.due_date}
                </span>
              )}
            </div>
          </div>
        </div>

        <button
          onClick={handleComplete}
          disabled={completing}
          className={`mt-2 w-full py-2 rounded-lg text-sm font-medium transition-colors ${
            completing
              ? "bg-gray-200 text-gray-400"
              : "bg-amber-500 active:bg-amber-600 text-white"
          }`}
        >
          {completing ? "Completing…" : "✓ Mark Complete"}
        </button>
      </div>
    </div>
  );
}

export default function MobileTasksPage() {
  const { isAuthenticated } = useAuth();
  const [tasks, setTasks] = useState<TicketTask[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    if (!isAuthenticated) return;
    setLoading(true);
    listMyTasks()
      .then(setTasks)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [isAuthenticated]);

  useEffect(() => { load(); }, [load]);

  const handleComplete = (completed: TicketTask) => {
    setTasks((prev) => prev.filter((t) => t.task_id !== completed.task_id));
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex-shrink-0 bg-white border-b border-gray-200 px-4 pt-safe-top">
        <div className="flex items-center justify-between py-3">
          <h1 className="text-lg font-semibold text-gray-900">My Tasks</h1>
          <button onClick={load} className="text-sm text-blue-600 font-medium">Refresh</button>
        </div>
      </div>

      {/* Task list */}
      <div className="flex-1 overflow-y-auto py-2">
        {loading ? (
          <div className="flex items-center justify-center h-32 text-sm text-gray-400">Loading…</div>
        ) : tasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 gap-2">
            <span className="text-4xl">✅</span>
            <span className="text-sm text-gray-400">No pending tasks</span>
          </div>
        ) : (
          <div>
            <div className="px-4 py-2 text-xs text-gray-400">
              {tasks.length} pending task{tasks.length !== 1 ? "s" : ""}
            </div>
            {tasks.map((t) => (
              <TaskItem key={t.task_id} task={t} onComplete={handleComplete} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
