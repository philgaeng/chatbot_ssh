import {
  completeTask,
  listTicketTasks,
  performAction,
  type TicketTask,
} from "@/lib/api";
import {
  fieldVisitSaveErrorMessage,
  formatFieldVisitNote,
  type FieldVisitFormData,
} from "@/lib/field-visit";

export async function submitStructuredFieldReport(opts: {
  ticketId: string;
  data: FieldVisitFormData;
  linkedTask: TicketTask | null;
  ensureAcknowledged: () => Promise<void>;
}): Promise<void> {
  const { ticketId, data, linkedTask, ensureAcknowledged } = opts;
  const note = formatFieldVisitNote(data);
  const taskId = linkedTask?.task_id;

  await ensureAcknowledged();
  await performAction(ticketId, { action_type: "FIELD_REPORT", note });

  if (taskId) {
    try {
      await completeTask(ticketId, taskId);
    } catch (completeErr) {
      const refreshed = await listTicketTasks(ticketId).catch(() => [] as TicketTask[]);
      const t = refreshed.find((x) => x.task_id === taskId);
      if (t?.status !== "DONE") throw completeErr;
    }
  }
}

export { fieldVisitSaveErrorMessage };
