import { performAction } from "@/lib/api";
import type { TicketDetail } from "@/lib/api";

/** Assigned actor posting moves OPEN/ESCALATED → IN_PROGRESS without a separate button press. */
export async function ensureTicketAcknowledged(
  ticket: TicketDetail | null,
  isAssignedActor: boolean,
  ticketId: string,
  reload: () => Promise<void>,
): Promise<void> {
  if (!ticket || !["OPEN", "ESCALATED"].includes(ticket.status_code)) return;
  if (!isAssignedActor) return;
  await performAction(ticketId, { action_type: "ACKNOWLEDGE" });
  await reload();
}
