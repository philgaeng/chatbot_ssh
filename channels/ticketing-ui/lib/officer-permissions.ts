import type { TicketDetail } from "@/lib/api";

type StepLike = { supervisor_role?: string | null; assigned_role_key?: string } | null | undefined;

/** Step supervisor or platform admin may assign officers (TP-12). */
export function canAssignTicket(
  roleKeys: string[],
  ticket: TicketDetail,
  isAdmin: boolean,
): boolean {
  if (isAdmin) return true;
  const sup = ticket.current_step?.supervisor_role;
  if (sup && roleKeys.includes(sup)) return true;
  return false;
}

/** L1 actor (assigned, not supervisor) may ask for reassignment. */
export function canRequestReassignment(
  roleKeys: string[],
  ticket: TicketDetail,
  currentUserId: string,
  isAdmin: boolean,
): boolean {
  if (isAdmin || canAssignTicket(roleKeys, ticket, isAdmin)) return false;
  if (ticket.status_code === "RESOLVED" || ticket.status_code === "CLOSED") return false;
  const actorRole = ticket.current_step?.assigned_role_key;
  if (!actorRole || !roleKeys.includes(actorRole)) return false;
  if (!ticket.assigned_to_user_id) return false;
  const uid = currentUserId.toLowerCase();
  const assignee = ticket.assigned_to_user_id.toLowerCase();
  return uid === assignee || ticket.assigned_to_user_id === currentUserId;
}

export function stepSupervisorLabel(step: StepLike): string {
  if (!step?.supervisor_role) return "your supervisor";
  return step.supervisor_role.replace(/_/g, " ");
}
