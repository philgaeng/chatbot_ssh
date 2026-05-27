import type { TicketEvent, TicketTask } from "@/lib/api";
import { isThreadTaskEvent } from "@/lib/mobile-constants";
import { isSiteVisitTask } from "@/lib/field-visit";

/**
 * Thread task cards:
 * - One card per task_id (ignore duplicate TASK_ASSIGNED rows).
 * - SITE_VISIT: show every completed visit; show pending visits, but at most
 *   one pending card per assignee (latest wins if duplicates exist).
 */
export function shouldRenderTaskCardInThread(
  event: TicketEvent,
  allEvents: TicketEvent[],
  tasks: TicketTask[],
): boolean {
  if (!isThreadTaskEvent(event.event_type)) return true;

  const taskId = event.payload?.task_id as string | undefined;
  if (!taskId) return true;

  const firstAssignment = allEvents.find(
    (e) =>
      isThreadTaskEvent(e.event_type) &&
      (e.payload?.task_id as string | undefined) === taskId,
  );
  if (firstAssignment && firstAssignment.event_id !== event.event_id) return false;

  const task = tasks.find((t) => t.task_id === taskId);
  const taskType =
    task?.task_type ?? (event.payload?.task_type as string | undefined) ?? "";

  if (!isSiteVisitTask(taskType)) return true;

  const status = task?.status ?? "PENDING";
  if (status === "DONE") return true;

  const assignee =
    task?.assigned_to_user_id ??
    (event.payload?.assigned_to_user_id as string | undefined) ??
    "";

  const pendingForAssignee = tasks.filter(
    (t) =>
      isSiteVisitTask(t.task_type) &&
      t.status === "PENDING" &&
      t.assigned_to_user_id === assignee,
  );
  if (pendingForAssignee.length <= 1) return true;

  const latestPending = pendingForAssignee.reduce((a, b) =>
    new Date(a.created_at) > new Date(b.created_at) ? a : b,
  );
  return latestPending.task_id === taskId;
}
