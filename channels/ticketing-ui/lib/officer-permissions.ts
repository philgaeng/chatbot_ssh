import type { TicketDetail } from "@/lib/api";

type StepLike = { supervisor_role?: string | null; assigned_role_key?: string } | null | undefined;

type TicketLike = Pick<
  TicketDetail,
  "status_code" | "assigned_to_user_id" | "current_step" | "step_supervisor_available"
>;

function supervisorAvailable(ticket: TicketLike): boolean {
  if (ticket.step_supervisor_available === true) return true;
  if (ticket.step_supervisor_available === false) return false;
  return !!ticket.current_step?.supervisor_role;
}

function isAssignedActor(
  ticket: TicketLike,
  currentUserId: string,
  _roleKeys: string[],
): boolean {
  if (ticket.status_code === "RESOLVED" || ticket.status_code === "CLOSED") return false;
  if (!ticket.assigned_to_user_id) return false;
  const uid = currentUserId.toLowerCase();
  const assignee = ticket.assigned_to_user_id.toLowerCase();
  // Assignee is the actor for case actions even when JWT user_roles holds a
  // different org identity (e.g. csc_officer) than the operational scope role.
  return uid === assignee || ticket.assigned_to_user_id === currentUserId;
}

function isStepSupervisor(roleKeys: string[], step: StepLike): boolean {
  const sup = step?.supervisor_role;
  return !!sup && roleKeys.includes(sup);
}

/** Step supervisor or platform admin may assign officers (TP-12). */
export function canSupervisorAssign(
  roleKeys: string[],
  ticket: TicketLike,
  isAdmin: boolean,
): boolean {
  if (isAdmin) return true;
  return isStepSupervisor(roleKeys, ticket.current_step);
}

/** Assigned actor may pick a same-level teammate when no supervisor is available. */
export function canPeerReassign(
  roleKeys: string[],
  ticket: TicketLike,
  currentUserId: string,
  isAdmin: boolean,
): boolean {
  if (isAdmin || canSupervisorAssign(roleKeys, ticket, isAdmin)) return false;
  if (supervisorAvailable(ticket)) return false;
  return isAssignedActor(ticket, currentUserId, roleKeys);
}

/** Supervisor assign or peer reassign when no supervisor on the step. */
export function canAssignTicket(
  roleKeys: string[],
  ticket: TicketLike,
  isAdmin: boolean,
  currentUserId?: string,
): boolean {
  if (canSupervisorAssign(roleKeys, ticket, isAdmin)) return true;
  if (currentUserId && canPeerReassign(roleKeys, ticket, currentUserId, isAdmin)) return true;
  return false;
}

/** Assigned actor asks step supervisor to reassign (supervisor must exist). */
export function canRequestReassignment(
  roleKeys: string[],
  ticket: TicketLike,
  currentUserId: string,
  isAdmin: boolean,
): boolean {
  if (isAdmin || canSupervisorAssign(roleKeys, ticket, isAdmin)) return false;
  if (!supervisorAvailable(ticket)) return false;
  return isAssignedActor(ticket, currentUserId, roleKeys);
}

export type ReassignMode = "supervisor" | "peer";

export function getReassignMode(
  roleKeys: string[],
  ticket: TicketLike,
  currentUserId: string,
  isAdmin: boolean,
): ReassignMode | null {
  if (canRequestReassignment(roleKeys, ticket, currentUserId, isAdmin)) return "supervisor";
  if (canPeerReassign(roleKeys, ticket, currentUserId, isAdmin)) return "peer";
  return null;
}

export function stepSupervisorLabel(step: StepLike): string {
  if (!step?.supervisor_role) return "your supervisor";
  return step.supervisor_role.replace(/_/g, " ");
}
