// GRM Ticketing API client
// All requests use relative paths (/api/v1/...) so they are proxied through
// the Next.js server rewrites → ticketing_api:5002 (see next.config.ts).
// This avoids CORS issues and means the browser only needs port 3001.

import { handleSessionExpired, isSessionExpiredResponse } from "./auth/session-expired";
import { projectsForOrganization } from "./officerJurisdiction";

const BASE = "";

// ── Types (mirror ticketing backend schemas) ──────────────────────────────────

export type SlaUrgency = "overdue" | "critical" | "warning" | "ok" | "none";

export interface TicketListItem {
  ticket_id: string;
  grievance_id: string;
  grievance_summary: string | null;
  status_code: string;
  priority: string;
  is_seah: boolean;
  organization_id: string;
  location_code: string | null;
  project_code: string | null;
  assigned_to_user_id: string | null;
  sla_breached: boolean;
  step_started_at: string | null;
  created_at: string;
  /** Computed: step_started_at + step.resolution_time_days. Null if not started or no SLA configured. */
  sla_deadline_at: string | null;
  /** Earliest pending task due date assigned to me on this ticket. Null if none. */
  my_earliest_task_due_at: string | null;
  unseen_event_count: number;
  needs_assignment?: boolean;
}

export interface TicketListResponse {
  items: TicketListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface WorkflowStepBrief {
  step_id: string;
  step_order: number;
  step_key: string;
  display_name: string;
  assigned_role_key: string;
  response_time_hours: number | null;
  resolution_time_days: number | null;
  // Spec 12 tier model
  supervisor_role: string | null;
  informed_roles: string[];
  observer_roles: string[];
  informed_pii_access: boolean;
  expected_actions?: string[] | null;
}

export interface TicketEvent {
  event_id: string;
  event_type: string;
  old_status_code: string | null;
  new_status_code: string | null;
  old_assigned_to: string | null;
  new_assigned_to: string | null;
  workflow_step_id: string | null;
  note: string | null;
  payload: Record<string, unknown> | null;
  seen: boolean;
  created_at: string;
  created_by_user_id: string | null;
  /** Role key snapshotted at write time — for audit trail role bubbles */
  actor_role: string | null;
  /** 'standard' | 'seah' — copied from ticket.is_seah at event creation */
  case_sensitivity: string;
  /** True when this event should trigger LLM summary regeneration */
  summary_regen_required: boolean;
}

export interface TicketViewer {
  viewer_id: string;
  user_id: string;
  added_by_user_id: string;
  added_at: string;
  /** 'observer' (read-only) | 'informed' (notes + tasks + notifications) */
  tier: "observer" | "informed";
}

export interface TicketDetail extends TicketListItem {
  complainant_id: string | null;
  session_id: string | null;
  chatbot_id: string;
  grievance_categories: string | null;
  grievance_description?: string | null;
  grievance_location: string | null;
  grievance_classification_status?: string | null;
  classification_validated_by_complainant?: boolean;
  classification_validated_by_officer?: boolean;
  classification_officer_validation_required?: boolean;
  classification_validated?: boolean;
  country_code: string;
  assigned_role_id: string | null;
  is_deleted: boolean;
  updated_at: string;
  updated_by_user_id: string | null;
  current_step: WorkflowStepBrief | null;
  events: TicketEvent[];
  viewers: TicketViewer[];
  /** AI-generated case findings (supervisor/GRC view only). Null until first generated. */
  ai_summary_en: string | null;
  ai_summary_updated_at: string | null;
  /** Spec 12: who holds the reply-to-complainant capability. Defaults to L1 actor. */
  complainant_reply_owner_id: string | null;
  /** Step supervisor role configured and at least one officer resolvable in scope. */
  step_supervisor_available?: boolean;
}

export interface SlaStatus {
  ticket_id: string;
  step_key: string | null;
  step_display_name: string | null;
  resolution_time_days: number | null;
  step_started_at: string | null;
  deadline: string | null;
  breached: boolean;
  remaining_hours: number | null;
  urgency: SlaUrgency;
}

export interface BadgeResponse {
  unseen_count: number;
}

export interface NotificationItem {
  event_id: string;
  ticket_id: string;
  grievance_id: string;
  grievance_summary: string | null;
  event_type: string;
  note: string | null;
  created_at: string;
  created_by_user_id: string | null;
}

export interface NotificationsResponse {
  items: NotificationItem[];
  total: number;
}

export interface ActionResponse {
  ticket_id: string;
  action_type: string;
  new_status_code: string;
  current_step_id: string | null;
  event_id: string;
}

export interface WorkflowStep {
  step_id: string;
  step_order: number;
  step_key: string;
  display_name: string;
  assigned_role_key: string;
  response_time_hours: number | null;
  resolution_time_days: number | null;
  stakeholders: string[] | null;
  expected_actions: string[] | null;
  // Spec 12 tier model
  supervisor_role: string | null;
  informed_roles: string[];
  observer_roles: string[];
  informed_pii_access: boolean;
  is_deleted?: boolean;
  workflow_id?: string;
  created_at?: string;
  updated_at?: string;
}

export interface WorkflowAssignmentItem {
  assignment_id: string;
  workflow_id: string;
  organization_id: string;
  location_code: string | null;
  project_code: string | null;
  priority: string | null;
}

export interface WorkflowDefinition {
  workflow_id: string;
  workflow_key: string;
  display_name: string;
  description: string | null;
  workflow_type: string;
  status: string;
  version: number;
  is_template: boolean;
  template_source_id: string | null;
  steps: WorkflowStep[];
  assignments: WorkflowAssignmentItem[];
  created_at: string;
  updated_at: string;
}

// ── Fetch wrapper ─────────────────────────────────────────────────────────────

/**
 * Read the OIDC access token (set by lib/auth/oidc-auth.ts) and turn it into
 * an Authorization header. Returns an empty object on the server side or when
 * no token is present (bypass-auth builds rely on the proxy cookie instead),
 * so it's safe to spread blindly.
 */
function authHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = window.localStorage.getItem("grm_access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function apiFetch<T>(path: string, opts?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...authHeaders(),
    ...((opts?.headers as Record<string, string> | undefined) ?? {}),
  };
  const resp = await fetch(`${BASE}${path}`, { ...opts, headers, credentials: "include" });
  if (!resp.ok) {
    const body = await resp.text();
    if (isSessionExpiredResponse(resp.status, body)) {
      handleSessionExpired();
    }
    throw new Error(`API ${resp.status} ${path}: ${body}`);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

// ── Ticket endpoints ──────────────────────────────────────────────────────────

export interface TicketFilters {
  /** Role-tier tab: "actor" | "supervisor" | "informed" | "observer" | "high_priority" | "all" */
  tab?: string;
  status_code?: string;
  is_seah?: boolean;
  organization_id?: string;
  location_code?: string;
  project_code?: string;
  package_id?: string;
  priority?: string;
  /** Search grievance ID, summary, or assignee email */
  q?: string;
  created_from?: string;
  created_to?: string;
  sla_breached?: boolean;
  page?: number;
  page_size?: number;
}

export function listTickets(filters: TicketFilters = {}): Promise<TicketListResponse> {
  const p = new URLSearchParams();
  if (filters.tab) p.set("tab", filters.tab);
  if (filters.status_code) p.set("status_code", filters.status_code);
  if (filters.is_seah !== undefined) p.set("is_seah", String(filters.is_seah));
  if (filters.organization_id) p.set("organization_id", filters.organization_id);
  if (filters.location_code) p.set("location_code", filters.location_code);
  if (filters.project_code) p.set("project_code", filters.project_code);
  if (filters.package_id) p.set("package_id", filters.package_id);
  if (filters.priority) p.set("priority", filters.priority);
  if (filters.q?.trim()) p.set("q", filters.q.trim());
  if (filters.created_from) p.set("created_from", filters.created_from);
  if (filters.created_to) p.set("created_to", filters.created_to);
  if (filters.sla_breached !== undefined) p.set("sla_breached", String(filters.sla_breached));
  p.set("page", String(filters.page ?? 1));
  p.set("page_size", String(filters.page_size ?? 50));
  return apiFetch<TicketListResponse>(`/api/v1/tickets?${p}`);
}

export type FiledDatePreset = "" | "today" | "2d" | "7d" | "30d" | "month" | "custom";

export type TicketListFilterValues = {
  q: string;
  priority: string;
  sla: string;
  /** Preset filed-date filter; `custom` uses createdFrom / createdTo. */
  filedPreset: FiledDatePreset;
  createdFrom: string;
  createdTo: string;
  projectCode: string;
  packageId: string;
};

export const EMPTY_TICKET_LIST_FILTERS: TicketListFilterValues = {
  q: "",
  priority: "",
  sla: "",
  filedPreset: "",
  createdFrom: "",
  createdTo: "",
  projectCode: "",
  packageId: "",
};

/** Calendar date in the officer's local timezone (matches ticket detail "Created" display). */
function localCalendarDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Map created-date preset to API date range (inclusive calendar days). */
export function filedPresetToDateRange(
  preset: FiledDatePreset,
  customFrom: string,
  customTo: string,
): { created_from?: string; created_to?: string } {
  if (preset === "custom") {
    const out: { created_from?: string; created_to?: string } = {};
    if (customFrom) out.created_from = customFrom;
    if (customTo) out.created_to = customTo;
    return out;
  }
  if (!preset) return {};

  const today = new Date();
  const end = localCalendarDate(today);
  if (preset === "today") {
    return { created_from: end, created_to: end };
  }
  if (preset === "2d") {
    const start = new Date(today);
    start.setDate(start.getDate() - 1);
    return { created_from: localCalendarDate(start), created_to: end };
  }
  if (preset === "7d") {
    const start = new Date(today);
    start.setDate(start.getDate() - 6);
    return { created_from: localCalendarDate(start), created_to: end };
  }
  if (preset === "30d") {
    const start = new Date(today);
    start.setDate(start.getDate() - 29);
    return { created_from: localCalendarDate(start), created_to: end };
  }
  if (preset === "month") {
    const start = new Date(today.getFullYear(), today.getMonth(), 1);
    return { created_from: localCalendarDate(start), created_to: end };
  }
  return {};
}

export function filedPresetLabel(
  preset: FiledDatePreset,
  customFrom: string,
  customTo: string,
): string | null {
  switch (preset) {
    case "today":
      return "Created today";
    case "2d":
      return "Created last 2 days";
    case "7d":
      return "Created last 7 days";
    case "30d":
      return "Created last 30 days";
    case "month":
      return "Created this month";
    case "custom":
      if (customFrom && customTo) return `Created ${customFrom} – ${customTo}`;
      if (customFrom) return `Created from ${customFrom}`;
      if (customTo) return `Created until ${customTo}`;
      return "Custom date range";
    default:
      return null;
  }
}

export function ticketListFiltersToApi(
  values: TicketListFilterValues,
): Pick<
  TicketFilters,
  "q" | "priority" | "sla_breached" | "created_from" | "created_to" | "project_code" | "package_id"
> {
  const out: Pick<
    TicketFilters,
    "q" | "priority" | "sla_breached" | "created_from" | "created_to" | "project_code" | "package_id"
  > = {};
  if (values.q.trim()) out.q = values.q.trim();
  if (values.priority) out.priority = values.priority;
  if (values.sla === "overdue") out.sla_breached = true;
  if (values.sla === "not_overdue") out.sla_breached = false;
  const dates = filedPresetToDateRange(values.filedPreset, values.createdFrom, values.createdTo);
  if (dates.created_from) out.created_from = dates.created_from;
  if (dates.created_to) out.created_to = dates.created_to;
  if (values.projectCode) out.project_code = values.projectCode;
  if (values.packageId) out.package_id = values.packageId;
  return out;
}

export function ticketListFiltersActive(values: TicketListFilterValues): boolean {
  return (
    !!values.q.trim() ||
    !!values.priority ||
    !!values.sla ||
    !!values.filedPreset ||
    !!values.projectCode ||
    !!values.packageId
  );
}

export function getTicket(id: string): Promise<TicketDetail> {
  return apiFetch<TicketDetail>(`/api/v1/tickets/${id}`);
}

export interface GrievanceCategoryOption {
  key: string;
  label: string;
  classification: string;
  generic_name: string;
  high_priority: boolean;
}

export function listGrievanceCategories(): Promise<GrievanceCategoryOption[]> {
  return apiFetch<GrievanceCategoryOption[]>("/api/v1/reference/grievance-categories");
}

export interface ClassificationValidatePayload {
  grievance_summary: string;
  grievance_categories: string;
  note?: string;
}

export function validateTicketClassification(
  ticketId: string,
  payload: ClassificationValidatePayload,
): Promise<{
  ticket_id: string;
  grievance_id: string;
  grievance_classification_status: string;
  event_id: string;
}> {
  return apiFetch(`/api/v1/tickets/${ticketId}/classification`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function getSla(id: string): Promise<SlaStatus> {
  return apiFetch<SlaStatus>(`/api/v1/tickets/${id}/sla`);
}

export function markSeen(id: string): Promise<void> {
  return apiFetch<void>(`/api/v1/tickets/${id}/seen`, { method: "POST" });
}

export interface ActionPayload {
  action_type: string;
  note?: string;
  resolution_category?: string;
  assign_to_user_id?: string;
  grc_hearing_date?: string;
  escalation_date?: string;
  persons_involved?: string[];
  escalation_notes?: string;
  reassignment_reason_code?: string;
  reassignment_notes?: string;
  is_call_report?: boolean;
}

export interface ClosureCaseHeader {
  reference: string;
  complaint_date?: string | null;
  resolved_date?: string | null;
  resolution_duration_days?: number | null;
  resolved_by?: string | null;
  project_name?: string | null;
  package_label?: string | null;
}

export interface ClosureOfficerMetrics {
  complaint_category?: string | null;
  escalated_yn?: string | null;
  stage_at_resolution?: string | null;
  stage_level_at_resolution?: string | null;
  days_spent_overdue?: number | null;
  sla_breached_yn?: string | null;
  resolution_category?: string | null;
  instance?: string | null;
  location_display?: string | null;
}

export interface ResolvedSummaryResponse {
  ticket_id: string;
  grievance_id: string;
  generation_status: string;
  closure_public_url: string | null;
  summary_json: Record<string, unknown>;
  summary_public_json: Record<string, unknown> | null;
  primary_language: string;
  case_header?: ClosureCaseHeader;
  officer_metrics?: ClosureOfficerMetrics;
}

export function getResolvedSummary(ticketId: string): Promise<ResolvedSummaryResponse> {
  return apiFetch<ResolvedSummaryResponse>(`/api/v1/tickets/${ticketId}/resolved-summary`);
}

export function triggerResolvedSummary(ticketId: string, force = false): Promise<{ ticket_id: string; status: string }> {
  const q = force ? "?force=true" : "";
  return apiFetch<{ ticket_id: string; status: string }>(`/api/v1/tickets/${ticketId}/resolved-summary${q}`, {
    method: "POST",
  });
}

export function performAction(id: string, payload: ActionPayload): Promise<ActionResponse> {
  return apiFetch<ActionResponse>(`/api/v1/tickets/${id}/actions`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function replyToComplainant(id: string, text: string): Promise<unknown> {
  return apiFetch(`/api/v1/tickets/${id}/reply`, {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export function patchTicket(id: string, body: { assign_to_user_id?: string; priority?: string }): Promise<unknown> {
  return apiFetch(`/api/v1/tickets/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

// ── Spec 12 tier endpoints ────────────────────────────────────────────────────

export interface AddInformedResponse {
  ticket_id: string;
  user_id: string;
  tier: string;
  viewer_id: string;
  event_id: string;
}

export function addInformed(ticketId: string, userId: string): Promise<AddInformedResponse> {
  return apiFetch<AddInformedResponse>(`/api/v1/tickets/${ticketId}/informed`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId }),
  });
}

export function updateReplyOwner(ticketId: string, userId: string): Promise<{ ticket_id: string; complainant_reply_owner_id: string; event_id: string }> {
  return apiFetch(`/api/v1/tickets/${ticketId}/complainant-reply-owner`, {
    method: "PUT",
    body: JSON.stringify({ user_id: userId }),
  });
}

export interface InboundMessagePayload {
  message: string;
  intent?: "ADDITIONAL_INFO" | "AMENDMENT" | "STATUS_CHECK" | "WITHDRAW_REQUEST" | "OTHER";
  session_id?: string;
  channel?: string;
}

export interface InboundMessageResult {
  ticket_id: string;
  event_id: string | null;
  status: string;
  ticket_status: string;
  current_step: string | null;
}

/** Simulate a complainant inbound message (dev/testing only — chatbot calls this in production). */
export function postInboundMessage(id: string, payload: InboundMessagePayload): Promise<InboundMessageResult> {
  return apiFetch<InboundMessageResult>(`/api/v1/tickets/${id}/inbound`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// ── Misc endpoints ────────────────────────────────────────────────────────────

export function getBadge(): Promise<BadgeResponse> {
  return apiFetch<BadgeResponse>("/api/v1/users/me/badge");
}

export function getNotifications(limit = 20): Promise<NotificationsResponse> {
  return apiFetch<NotificationsResponse>(`/api/v1/users/me/notifications?limit=${limit}`);
}

export function listWorkflows(filters?: {
  workflow_type?: string;
  status?: string;
  is_template?: boolean;
}): Promise<{ items: WorkflowDefinition[]; total: number }> {
  const p = new URLSearchParams();
  if (filters?.workflow_type) p.set("workflow_type", filters.workflow_type);
  if (filters?.status) p.set("status", filters.status);
  if (filters?.is_template !== undefined) p.set("is_template", String(filters.is_template));
  const qs = p.toString();
  return apiFetch(`/api/v1/workflows${qs ? `?${qs}` : ""}`);
}

export function listTemplates(): Promise<{ items: WorkflowDefinition[]; total: number }> {
  return apiFetch("/api/v1/workflows/templates");
}

export interface WorkflowCreatePayload {
  display_name: string;
  workflow_type: string;
  description?: string;
  clone_from_id?: string;
  is_template?: boolean;
}

export function createWorkflow(payload: WorkflowCreatePayload): Promise<WorkflowDefinition> {
  return apiFetch("/api/v1/workflows", { method: "POST", body: JSON.stringify(payload) });
}

export function getWorkflow(workflowId: string): Promise<WorkflowDefinition> {
  return apiFetch<WorkflowDefinition>(`/api/v1/workflows/${workflowId}`);
}

export function saveWorkflowAsTemplate(
  workflowId: string,
  payload?: { display_name?: string },
): Promise<WorkflowDefinition> {
  return apiFetch(`/api/v1/workflows/${workflowId}/save-as-template`, {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
  });
}

export function updateWorkflow(id: string, payload: { display_name?: string; description?: string; workflow_key?: string }): Promise<WorkflowDefinition> {
  return apiFetch(`/api/v1/workflows/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function publishWorkflow(id: string): Promise<WorkflowDefinition> {
  return apiFetch(`/api/v1/workflows/${id}/publish`, { method: "POST" });
}

export function archiveWorkflow(id: string): Promise<WorkflowDefinition> {
  return apiFetch(`/api/v1/workflows/${id}/archive`, { method: "POST" });
}

export function deleteWorkflow(id: string): Promise<void> {
  return apiFetch(`/api/v1/workflows/${id}`, { method: "DELETE" });
}

export interface StepPayload {
  display_name: string;
  assigned_role_key: string;
  step_key?: string;
  response_time_hours?: number | null;
  resolution_time_days?: number | null;
  stakeholders?: string[] | null;
  expected_actions?: string[] | null;
  // Spec 12 tier model fields
  supervisor_role?: string | null;
  informed_roles?: string[];
  observer_roles?: string[];
  informed_pii_access?: boolean;
}

export function addStep(workflowId: string, payload: StepPayload): Promise<WorkflowStep> {
  return apiFetch(`/api/v1/workflows/${workflowId}/steps`, { method: "POST", body: JSON.stringify(payload) });
}

export function updateStep(workflowId: string, stepId: string, payload: Partial<StepPayload>): Promise<WorkflowStep> {
  return apiFetch(`/api/v1/workflows/${workflowId}/steps/${stepId}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function deleteStep(workflowId: string, stepId: string): Promise<void> {
  return apiFetch(`/api/v1/workflows/${workflowId}/steps/${stepId}`, { method: "DELETE" });
}

export function reorderSteps(workflowId: string, stepIds: string[]): Promise<WorkflowStep[]> {
  return apiFetch(`/api/v1/workflows/${workflowId}/steps/reorder`, { method: "POST", body: JSON.stringify({ step_ids: stepIds }) });
}

export interface AssignmentPayload {
  organization_id: string;
  location_code?: string | null;
  project_code?: string | null;
  priority?: string | null;
}

export function addAssignment(workflowId: string, payload: AssignmentPayload): Promise<WorkflowAssignmentItem> {
  return apiFetch(`/api/v1/workflows/${workflowId}/assignments`, { method: "POST", body: JSON.stringify(payload) });
}

export function removeAssignment(workflowId: string, assignmentId: string): Promise<void> {
  return apiFetch(`/api/v1/workflows/${workflowId}/assignments/${assignmentId}`, { method: "DELETE" });
}

// ── Complainant PII (brokered through ticketing API — browser never calls backend directly) ──
// Per PRIVACY.md: all sensitive reads go through the ticketing API (internal Docker network).
// The old NEXT_PUBLIC_BACKEND_API_URL direct call is replaced by GET /tickets/{id}/pii.

export interface GrievancePii {
  grievance_id?: string;
  complainant_name?: string;
  phone_number?: string;
  email?: string;
  address?: string;
  municipality?: string;
  district?: string;
  /** JSON map pin from complainant record, e.g. `{"lat":27.5,"lng":85.3,"source":"map_pin"}` */
  location_geo?: string | null;
  /** True for SEAH tickets — contact fields omitted from /pii; use vault reveal */
  pii_masked?: boolean;
  /** True when the grievance backend was unreachable — PII fields will be null */
  _backend_unavailable?: boolean;
  [key: string]: unknown;
}

/** Fetch complainant name + contact via the ticketing API broker (not direct backend call). */
export function getGrievancePii(ticketId: string): Promise<GrievancePii> {
  return apiFetch<GrievancePii>(`/api/v1/tickets/${ticketId}/pii`);
}

// ── Officers (for assign dropdown) ───────────────────────────────────────────

export interface OfficerBrief {
  user_id: string;
  role_keys: string[];
  organization_id: string | null;
  location_code: string | null;
}

export function listOfficers(): Promise<OfficerBrief[]> {
  return apiFetch<OfficerBrief[]>("/api/v1/users/officers");
}

/** ticketing.roles row — catalog metadata + permissions JSON */
export interface GrmRole {
  role_id: string;
  role_key: string;
  display_name: string;
  description: string | null;
  workflow_scope: string | null;
  jurisdiction_mode: string | null;
  permissions: unknown;
  role_kind?: string | null;
  role_origin?: string | null;
  steps_count?: number;
  officers_count?: number;
  created_at: string;
  updated_at: string;
}

export function listRoles(params?: {
  kind?: "operational" | "admin";
  workflow_track?: "standard" | "seah";
}): Promise<GrmRole[]> {
  const qs = new URLSearchParams();
  if (params?.kind) qs.set("kind", params.kind);
  if (params?.workflow_track) qs.set("workflow_track", params.workflow_track);
  const suffix = qs.toString() ? `?${qs}` : "";
  return apiFetch<GrmRole[]>(`/api/v1/roles${suffix}`);
}

export interface RoleArchetype {
  key: string;
  label: string;
}

export function listRoleArchetypes(): Promise<RoleArchetype[]> {
  return apiFetch<RoleArchetype[]>("/api/v1/roles/archetypes");
}

export function createRole(payload: {
  display_name: string;
  role_key?: string;
  workflow_scope: string;
  jurisdiction_mode?: string;
  archetype?: string;
  permissions?: string[];
  description?: string;
}): Promise<GrmRole> {
  return apiFetch<GrmRole>("/api/v1/roles", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export interface AdminScopeRow {
  admin_scope_id: string;
  user_id: string;
  role_key: string;
  country_code: string | null;
  project_id: string | null;
  organization_id: string | null;
  package_id: string | null;
  workflow_track: string;
  created_at: string;
  created_by_user_id?: string | null;
  /** True when Keycloak still has pending setup actions (invite link can be resent). */
  can_resend_invite?: boolean;
  can_send_setup_email?: boolean;
  onboarding_status?: string | null;
  invite_email_sent?: boolean;
}

export interface AdminContext {
  is_super_admin: boolean;
  is_country_admin: boolean;
  is_project_admin: boolean;
  admin_workflow_tracks: string[];
  admin_project_ids: string[];
  admin_country_codes: string[];
  can_access_platform_settings: boolean;
  can_manage_structure: boolean;
  can_create_project: boolean;
  admin_scopes: AdminScopeRow[];
}

export function getAdminContext(): Promise<AdminContext> {
  return apiFetch<AdminContext>("/api/v1/users/me/admin-context");
}

export function listAdminScopes(): Promise<AdminScopeRow[]> {
  return apiFetch<AdminScopeRow[]>("/api/v1/admin-scopes");
}

export function createAdminScope(payload: {
  user_id: string;
  role_key: "country_admin" | "project_admin";
  country_code?: string;
  project_id?: string;
  organization_id?: string;
  workflow_track: "standard" | "seah";
}): Promise<AdminScopeRow> {
  return apiFetch<AdminScopeRow>("/api/v1/admin-scopes", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteAdminScope(adminScopeId: string): Promise<void> {
  return apiFetch(`/api/v1/admin-scopes/${adminScopeId}`, { method: "DELETE" });
}

export function sendAdminScopeInvite(adminScopeId: string): Promise<AdminScopeRow> {
  return apiFetch<AdminScopeRow>(`/api/v1/admin-scopes/${adminScopeId}/send-invite`, {
    method: "POST",
  });
}

export function updateRole(
  roleId: string,
  payload: {
    display_name?: string | null;
    description?: string | null;
    workflow_scope?: string | null;
    jurisdiction_mode?: string | null;
  }
): Promise<GrmRole> {
  return apiFetch<GrmRole>(`/api/v1/roles/${roleId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteRole(roleId: string): Promise<void> {
  return apiFetch(`/api/v1/roles/${roleId}`, { method: "DELETE" });
}

/** Settings → Officers (admin): aggregated ticketing.user_roles — no Keycloak sync. */
export interface OfficerRosterEntry {
  user_id: string;
  display_name: string;
  email: string | null;
  phone_number?: string | null;
  role_keys: string[];
  organization_ids: string[];
  location_codes: string[];
  project_codes?: string[];
  package_ids?: string[];
  /** invited until Keycloak webhook confirms password update */
  onboarding_status?: string;
}

export function listOfficerRoster(): Promise<OfficerRosterEntry[]> {
  return apiFetch<OfficerRosterEntry[]>("/api/v1/users/roster");
}

// ── File attachments ──────────────────────────────────────────────────────────

export interface TicketFile {
  file_id: string;
  file_name: string;
  file_path: string;
  file_type: string;
  file_size: number;
  upload_timestamp: string;
}

export function listTicketFiles(ticketId: string): Promise<TicketFile[]> {
  return apiFetch<TicketFile[]>(`/api/v1/tickets/${ticketId}/files`);
}

/** @deprecated Prefer openComplainantFile — plain URLs cannot send Bearer auth in a new tab. */
export function getFileDownloadUrl(fileId: string): string {
  return `${BASE}/api/v1/files/${fileId}`;
}

export function complainantFilePath(fileId: string): string {
  return `/api/v1/files/${fileId}`;
}

// ── Officer file attachments ──────────────────────────────────────────────────

export interface OfficerAttachment {
  file_id: string;
  file_name: string;
  file_type: string | null;
  file_size: number;
  caption: string | null;
  uploaded_by_user_id: string | null;
  uploaded_at: string;
}

export function listOfficerAttachments(ticketId: string): Promise<OfficerAttachment[]> {
  return apiFetch<OfficerAttachment[]>(`/api/v1/tickets/${ticketId}/attachments`);
}

/** @deprecated Prefer openOfficerAttachment — plain URLs cannot send Bearer auth in a new tab. */
export function getOfficerAttachmentUrl(fileId: string): string {
  return `${BASE}/api/v1/attachments/${fileId}`;
}

export function officerAttachmentPath(fileId: string): string {
  return `/api/v1/attachments/${fileId}`;
}

/** Fetch a protected file with session cookie + Bearer token; returns a blob URL. */
export async function fetchAuthenticatedBlobUrl(path: string): Promise<string> {
  const resp = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: {
      Accept: "*/*",
      ...authHeaders(),
    },
  });
  if (!resp.ok) {
    const text = await resp.text();
    if (isSessionExpiredResponse(resp.status, text)) {
      handleSessionExpired();
    }
    let message = text || `File request failed (${resp.status})`;
    try {
      const parsed = JSON.parse(text) as { detail?: string };
      if (parsed.detail) {
        message = typeof parsed.detail === "string" ? parsed.detail : JSON.stringify(parsed.detail);
      }
    } catch {
      /* plain text */
    }
    throw new Error(message);
  }
  const blob = await resp.blob();
  return URL.createObjectURL(blob);
}

function triggerBlobDownload(blobUrl: string, fileName: string): void {
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

/**
 * Open or download after authenticated fetch.
 * Pass `previewWindow` opened synchronously on click to avoid popup blockers (PDF etc.).
 */
export async function openAuthenticatedAttachment(
  path: string,
  fileName: string,
  opts?: { previewWindow?: Window | null },
): Promise<void> {
  const blobUrl = await fetchAuthenticatedBlobUrl(path);
  const isPdf = /\.pdf$/i.test(fileName);
  if (isPdf) {
    const w = opts?.previewWindow;
    if (w && !w.closed) {
      w.location.href = blobUrl;
      window.setTimeout(() => URL.revokeObjectURL(blobUrl), 120_000);
      return;
    }
  }
  triggerBlobDownload(blobUrl, fileName);
  window.setTimeout(() => URL.revokeObjectURL(blobUrl), 5_000);
}

export function openComplainantFile(
  fileId: string,
  fileName: string,
  opts?: { previewWindow?: Window | null },
): Promise<void> {
  return openAuthenticatedAttachment(complainantFilePath(fileId), fileName, opts);
}

export function openOfficerAttachment(
  fileId: string,
  fileName: string,
  opts?: { previewWindow?: Window | null },
): Promise<void> {
  return openAuthenticatedAttachment(officerAttachmentPath(fileId), fileName, opts);
}

export async function uploadOfficerAttachment(
  ticketId: string,
  file: File,
  caption: string,
): Promise<OfficerAttachment> {
  const form = new FormData();
  form.append("file", file);
  form.append("caption", caption);
  // Do NOT set Content-Type — browser sets multipart boundary automatically
  const resp = await fetch(`${BASE}/api/v1/tickets/${ticketId}/attachments`, {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  if (!resp.ok) {
    const body = await resp.text();
    if (isSessionExpiredResponse(resp.status, body)) {
      handleSessionExpired();
    }
    throw new Error(`Upload failed ${resp.status}: ${body}`);
  }
  return resp.json();
}

// ── Reports ───────────────────────────────────────────────────────────────────

export type ReportBucket = "resolved" | "high" | "overdue" | "other";

export interface ReportRow {
  ticket_id?: string;
  complaint_date?: string;
  grievance_id?: string;
  high_yn?: string;
  escalated_yn?: string;
  overdue_yn?: string;
  stage?: string;
  complaint_category?: string;
  days_in_stage?: number | null;
  total_days?: number | null;
  resolution_category?: string;
  status_code?: string;
  project_name?: string;
  package_label?: string;
  location_display?: string;
  grievance_summary?: string;
  [key: string]: string | number | null | undefined;
}

export interface ReportSectionBlock {
  items: ReportRow[];
  total: number;
}

export interface ReportQueryResponse {
  filters: Record<string, unknown>;
  summary: { total: number; resolved: number; high: number; overdue: number; other: number };
  columns: string[];
  column_labels: Record<string, string>;
  sections: Record<ReportBucket, ReportSectionBlock>;
  field_catalog: { key: string; label: string }[];
}

export type PivotAgg = "count" | "sum" | "avg" | "max" | "min";

export interface PivotValueSpec {
  field: string;
  agg: PivotAgg;
}

export interface PivotConfig {
  rows: string[];
  columns: string[];
  values: PivotValueSpec[];
  filters: Record<string, string[]>;
}

export interface ReportFieldsResponse {
  fields: { key: string; label: string }[];
  dimensions: { key: string; label: string }[];
  measures: { key: string; label: string }[];
  group_by_options: string[];
  aggregates: string[];
  default_columns: string[];
  default_pivot?: PivotConfig;
}

export interface PivotHeaderCell {
  text: string;
  row_span?: number;
  col_span?: number;
  kind?: string;
}

export interface ReportBuildResult {
  columns: string[];
  column_labels?: Record<string, string>;
  rows: Record<string, unknown>[];
  total: number;
  grouped?: boolean;
  pivot?: boolean;
  row_dims?: string[];
  col_dims?: string[];
  row_dim_labels?: string[];
  col_dim_labels?: string[];
  column_groups?: { title: string; col_key: string[]; value_headers: string[]; col_span: number }[];
  header_rows?: PivotHeaderCell[][];
}

export function exportReportUrl(params: {
  date_from?: string;
  date_to?: string;
  organization_id?: string;
  project_ids?: string[];
  package_ids?: string[];
  location_codes?: string[];
  include_seah?: boolean;
}): string {
  const p = new URLSearchParams();
  if (params.date_from) p.set("date_from", params.date_from);
  if (params.date_to) p.set("date_to", params.date_to);
  if (params.organization_id) p.set("organization_id", params.organization_id);
  if (params.project_ids?.length) p.set("project_ids", params.project_ids.join(","));
  if (params.package_ids?.length) p.set("package_ids", params.package_ids.join(","));
  if (params.location_codes?.length) p.set("location_codes", params.location_codes.join(","));
  if (params.include_seah) p.set("include_seah", "true");
  return `${BASE}/api/v1/reports/export?${p}`;
}

/** @deprecated Use exportReportUrl */
export const exportReport = exportReportUrl;

/** Download binary export with auth cookie + Bearer token (anchor href cannot send these). */
async function downloadApiFile(path: string, filename: string, init?: RequestInit): Promise<void> {
  const extraHeaders = (init?.headers as Record<string, string> | undefined) ?? {};
  const resp = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      Accept: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/octet-stream",
      ...authHeaders(),
      ...extraHeaders,
    },
  });
  if (!resp.ok) {
    const text = await resp.text();
    if (isSessionExpiredResponse(resp.status, text)) {
      handleSessionExpired();
    }
    let message = text || `Export failed (${resp.status})`;
    try {
      const parsed = JSON.parse(text) as { detail?: string };
      if (parsed.detail) message = typeof parsed.detail === "string" ? parsed.detail : JSON.stringify(parsed.detail);
    } catch {
      /* plain text error */
    }
    throw new Error(message);
  }
  const contentType = resp.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    const text = await resp.text();
    throw new Error(text || "Server returned JSON instead of a file");
  }
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export async function downloadExportReportXlsx(params: {
  date_from?: string;
  date_to?: string;
  organization_id?: string;
  project_ids?: string[];
  package_ids?: string[];
  location_codes?: string[];
  include_seah?: boolean;
}): Promise<void> {
  const from = params.date_from ?? "start";
  const to = params.date_to ?? "end";
  const path = exportReportUrl(params).replace(BASE, "");
  await downloadApiFile(path, `grm-report-${from}-to-${to}.xlsx`);
}

export async function downloadExportAllDataXlsx(params: {
  date_from?: string;
  date_to?: string;
  project_ids?: string[];
  package_ids?: string[];
  location_codes?: string[];
  include_seah?: boolean;
}): Promise<void> {
  const p = new URLSearchParams();
  if (params.date_from) p.set("date_from", params.date_from);
  if (params.date_to) p.set("date_to", params.date_to);
  if (params.project_ids?.length) p.set("project_ids", params.project_ids.join(","));
  if (params.package_ids?.length) p.set("package_ids", params.package_ids.join(","));
  if (params.location_codes?.length) p.set("location_codes", params.location_codes.join(","));
  if (params.include_seah) p.set("include_seah", "true");
  const from = params.date_from ?? "start";
  const to = params.date_to ?? "end";
  await downloadApiFile(`/api/v1/reports/export-all?${p}`, `grm-all-data-${from}-to-${to}.xlsx`);
}

export interface ReportShareResponse {
  id: string;
  name: string;
  internal_url_path: string;
  public_url_path: string;
  internal_token: string;
  public_token: string;
  row_count: number;
}

export function createReportShare(body: {
  name: string;
  report_kind?: string;
  date_from?: string;
  date_to?: string;
  project_ids?: string[];
  package_ids?: string[];
  location_codes?: string[];
  include_seah?: boolean;
  library_item_id?: string;
}): Promise<ReportShareResponse> {
  return apiFetch<ReportShareResponse>("/api/v1/reports/share", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function fetchPublicReport(token: string): Promise<{
  name: string;
  columns: string[];
  rows: Record<string, unknown>[];
  filters: Record<string, unknown>;
  generated_at?: string;
}> {
  return apiFetch(`/api/v1/public/report/${token}`);
}

export function fetchInternalReportShare(token: string): Promise<{
  name: string;
  columns: string[];
  rows: Record<string, unknown>[];
  filters: Record<string, unknown>;
  generated_at?: string;
}> {
  return apiFetch(`/api/v1/reports/share/${token}`);
}

export function queryReport(params: {
  date_from: string;
  date_to: string;
  project_ids?: string[];
  package_ids?: string[];
  location_codes?: string[];
  include_seah?: boolean;
  page?: number;
  page_size?: number;
}): Promise<ReportQueryResponse> {
  const p = new URLSearchParams();
  p.set("date_from", params.date_from);
  p.set("date_to", params.date_to);
  if (params.project_ids?.length) p.set("project_ids", params.project_ids.join(","));
  if (params.package_ids?.length) p.set("package_ids", params.package_ids.join(","));
  if (params.location_codes?.length) p.set("location_codes", params.location_codes.join(","));
  if (params.include_seah) p.set("include_seah", "true");
  if (params.page) p.set("page", String(params.page));
  if (params.page_size) p.set("page_size", String(params.page_size));
  return apiFetch<ReportQueryResponse>(`/api/v1/reports/query?${p}`);
}

export function fetchReportFields(): Promise<ReportFieldsResponse> {
  return apiFetch<ReportFieldsResponse>("/api/v1/reports/fields");
}

export type ReportBuildBody = {
  date_from: string;
  date_to: string;
  project_ids?: string[];
  package_ids?: string[];
  location_codes?: string[];
  include_seah?: boolean;
  pivot?: PivotConfig;
  columns?: string[];
  group_by?: string | null;
  aggregate?: "none" | "count" | "avg_total_days" | "sum_total_days";
  page?: number;
  page_size?: number;
};

export function buildReportJson(body: ReportBuildBody): Promise<ReportBuildResult> {
  return apiFetch<ReportBuildResult>("/api/v1/reports/build", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...body, format: "json" }),
  });
}

export async function downloadBuildReportXlsx(body: ReportBuildBody): Promise<void> {
  await downloadApiFile(
    "/api/v1/reports/build",
    `grm-pivot-report-${body.date_from}-${body.date_to}.xlsx`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...body, format: "xlsx", page: 1, page_size: 500 }),
    },
  );
}

export interface QuarterlyReportSchedule {
  frequency: "quarterly";
  day_of_month: number;
}

export type QuarterlyReportKind = "overview" | "pivot" | "summary";

export interface QuarterlyReportTemplate {
  name: string;
  kind: QuarterlyReportKind;
  include_seah: boolean;
  project_ids: string[];
  package_ids: string[];
  location_codes: string[];
  pivot: PivotConfig | null;
  summary_quarter_keys?: string[];
  summary_province_code?: string | null;
}

export interface ReportSummaryPieSlice {
  label: string;
  value: number;
  percent: number;
}

export interface ReportSummaryResponse {
  filters: Record<string, unknown>;
  matrix: {
    column_groups: {
      id: string;
      label: string;
      tooltip?: string;
      children: { key: string; label: string; tooltip?: string }[];
    }[];
    rows: {
      project_id: string;
      project_name: string;
      package_id: string | null;
      package_name: string;
      cells: Record<string, number>;
    }[];
  };
  charts: {
    resolved_by_month: { month: string; packages: { package_id: string | null; package_name: string; count: number }[] }[];
    pies: {
      overdue_vs_ontime: ReportSummaryPieSlice[];
      escalated: ReportSummaryPieSlice[];
      max_level: ReportSummaryPieSlice[];
      resolution_category: ReportSummaryPieSlice[];
    };
  };
  definitions: Record<string, string>;
}

export function fetchReportSummary(params: {
  project_id: string;
  province_code?: string;
  quarter_keys?: string[];
  years?: number[];
  chart_package_ids?: string[];
  include_seah?: boolean;
}): Promise<ReportSummaryResponse> {
  const p = new URLSearchParams();
  p.set("project_id", params.project_id);
  if (params.province_code) p.set("province_code", params.province_code);
  if (params.quarter_keys?.length) p.set("quarter_keys", params.quarter_keys.join(","));
  if (params.years?.length) p.set("years", params.years.join(","));
  if (params.chart_package_ids?.length) p.set("chart_package_ids", params.chart_package_ids.join(","));
  if (params.include_seah) p.set("include_seah", "true");
  return apiFetch<ReportSummaryResponse>(`/api/v1/reports/summary?${p}`);
}

export function summaryExportUrl(params: {
  project_id: string;
  province_code?: string;
  quarter_keys?: string[];
  years?: number[];
  chart_package_ids?: string[];
  include_seah?: boolean;
}): string {
  const p = new URLSearchParams();
  p.set("project_id", params.project_id);
  if (params.province_code) p.set("province_code", params.province_code);
  if (params.quarter_keys?.length) p.set("quarter_keys", params.quarter_keys.join(","));
  if (params.years?.length) p.set("years", params.years.join(","));
  if (params.chart_package_ids?.length) p.set("chart_package_ids", params.chart_package_ids.join(","));
  if (params.include_seah) p.set("include_seah", "true");
  return `${BASE}/api/v1/reports/summary/export?${p}`;
}

export async function downloadSummaryReportXlsx(params: {
  project_id: string;
  province_code?: string;
  quarter_keys?: string[];
  years?: number[];
  chart_package_ids?: string[];
  include_seah?: boolean;
  project_name?: string;
}): Promise<void> {
  const qpart = params.quarter_keys?.length ? params.quarter_keys.join("-") : "summary";
  const project =
    (params.project_name || "project").replace(/[^\w\-]+/g, "_").slice(0, 40) || "project";
  const path = summaryExportUrl(params).replace(BASE, "");
  await downloadApiFile(path, `grm-summary_${project}_${qpart}.xlsx`);
}

export interface ReportLimitsInfo {
  max_export_rows: number;
  max_exports_per_user_per_hour: number;
  max_reports_per_role_per_quarter: number;
  quarterly_email_enabled: boolean;
  allowed_recipient_roles: string[] | null;
}

export interface ArchivingPolicyInfo {
  enabled: boolean;
  years_before_archiving: number;
  archive_run_month: number;
  archive_run_day: number;
  timezone: string;
  attachment_tier_on_archive: "none" | "cold" | "glacier";
  allow_complainant_download_when_archived: boolean;
  seah_years_before_archiving: number | null;
}

/** One grievance classification entry (LLM + officer UI taxonomy). */
export interface GrievanceCategoryCatalogEntry {
  category_key: string;
  generic_grievance_name: string;
  generic_grievance_name_ne: string;
  short_description: string;
  short_description_ne: string;
  classification: string;
  classification_ne: string;
  description: string;
  description_ne: string;
  follow_up_question_description: string;
  follow_up_question_description_ne: string;
  follow_up_question_quantification: string;
  follow_up_question_quantification_ne: string;
  high_priority: boolean;
}

export interface GrievanceCategoriesCatalogInfo {
  categories: GrievanceCategoryCatalogEntry[];
}

export interface QuarterlyAssignment {
  id: string;
  quarter_key: string;
  role_key: string;
  name: string;
  template: QuarterlyReportTemplate;
  active: boolean;
}

export interface QuarterlyRolePlan {
  role_key: string;
  count: number;
  max: number;
  assignments: QuarterlyAssignment[];
}

export interface QuarterlyPlanResponse {
  quarter_key: string;
  max_per_role: number;
  schedule: QuarterlyReportSchedule;
  limits: ReportLimitsInfo;
  roles: QuarterlyRolePlan[];
}

export function getQuarterlyPlan(quarterKey?: string): Promise<QuarterlyPlanResponse> {
  const q = quarterKey ? `?quarter_key=${encodeURIComponent(quarterKey)}` : "";
  return apiFetch<QuarterlyPlanResponse>(`/api/v1/reports/quarterly-plan${q}`);
}

export function saveQuarterlySchedule(dayOfMonth: number): Promise<QuarterlyReportSchedule> {
  return apiFetch<QuarterlyReportSchedule>("/api/v1/reports/quarterly-schedule", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ day_of_month: dayOfMonth }),
  });
}

export interface QuarterlyReportLibraryItem {
  id: string;
  name: string;
  template: QuarterlyReportTemplate;
}

export function createQuarterlyAssignments(body: {
  quarter_key: string;
  role_keys: string[];
  library_id?: string;
  name?: string;
  template?: QuarterlyReportTemplate;
}): Promise<QuarterlyAssignment[]> {
  return apiFetch<QuarterlyAssignment[]>("/api/v1/reports/quarterly-assignments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function getQuarterlyLibrary(): Promise<QuarterlyReportLibraryItem[]> {
  return apiFetch<QuarterlyReportLibraryItem[]>("/api/v1/reports/quarterly-library");
}

export function saveToQuarterlyLibrary(body: {
  name: string;
  template: QuarterlyReportTemplate;
}): Promise<QuarterlyReportLibraryItem> {
  return apiFetch<QuarterlyReportLibraryItem>("/api/v1/reports/quarterly-library", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function deleteQuarterlyLibraryItem(itemId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/reports/quarterly-library/${itemId}`, { method: "DELETE" });
}

export function deleteQuarterlyAssignment(assignmentId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/reports/quarterly-assignments/${assignmentId}`, {
    method: "DELETE",
  });
}

/** Current calendar quarter key, e.g. 2026-Q2 */
export function currentQuarterKey(d = new Date()): string {
  const q = Math.floor(d.getMonth() / 3) + 1;
  return `${d.getFullYear()}-Q${q}`;
}

// ── Organizations / Countries / Locations / Projects ─────────────────────────

export interface OrganizationItem {
  organization_id: string;
  name: string;
  country_code: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface LevelDef {
  level_number: number;
  level_name_en: string;
  level_name_local: string | null;
}

export interface CountryItem {
  country_code: string;
  name: string;
  level_defs: LevelDef[];
}

export interface LocationTranslation {
  lang_code: string;
  name: string;
}

export interface LocationNode {
  location_code: string;
  country_code: string;
  level_number: number;
  parent_location_code: string | null;
  source_id: number | null;
  is_active: boolean;
  translations: LocationTranslation[];
}

/** Role of an organization within a specific project. */
export interface OrgRole {
  key: string;
  label: string;
  description: string;
}

/** Organization linked to a project, with its role in that project. */
export interface ProjectOrgItem {
  organization_id: string;
  org_role: string | null;
}

export interface ProjectWorkflowSlot {
  project_workflow_id: string;
  workflow_id: string;
  display_label: string;
  classifications: string[];
  intake_routes: string[];
  is_default: boolean;
  workflow_track: "standard" | "seah";
  sort_order: number;
}

export interface WorkflowRoutingOptions {
  classifications: string[];
  intake_routes: { key: string; label: string }[];
}

export interface ProjectItem {
  project_id: string;
  country_code: string;
  short_code: string;
  name: string;
  description: string | null;
  is_active: boolean;
  project_type_key: string | null;
  /** @deprecated use workflow_slots — mirrors safeguards slot */
  standard_workflow_id: string | null;
  /** @deprecated use workflow_slots — mirrors seah slot */
  seah_workflow_id: string | null;
  workflow_slots?: ProjectWorkflowSlot[];
  created_at: string;
  updated_at: string;
  /** Organizations linked to this project, each with an optional role. */
  organizations: ProjectOrgItem[];
  location_codes: string[];
}

export interface ProjectCreate {
  country_code: string;
  short_code: string;
  name: string;
  description?: string | null;
  is_active?: boolean;
  project_type_key?: string | null;
}

export interface TypeActorRoleDef {
  key: string;
  label: string;
  description?: string;
  required?: boolean;
  required_package?: boolean;
  scope?: string;
}

export interface ProjectTypeItem {
  type_key: string;
  label: string;
  description: string | null;
  standard_workflow_id: string | null;
  seah_workflow_id: string | null;
  routing_org_role: string;
  actor_roles: TypeActorRoleDef[];
  is_active: boolean;
  sort_order: number;
}

export interface GoLiveCheck {
  id: string;
  label: string;
  group: string;
  severity: string;
  status: string;
  message: string;
  section: string | null;
}

export interface GoLiveReport {
  checks: GoLiveCheck[];
  can_activate: boolean;
  can_accept_tickets: boolean;
  summary: Record<string, number>;
}

export interface ImportResult {
  country: string;
  format: string;
  locations_upserted: number;
  translations_upserted: number;
  dry_run: boolean;
}

export interface OrganizationCreate {
  /** Omit to let the API derive a unique id from name + country. */
  organization_id?: string | null;
  name: string;
  country_code?: string | null;
  is_active?: boolean;
}

export interface OrganizationUpdate {
  name?: string;
  country_code?: string | null;
  is_active?: boolean;
}

export function listOrganizations(country?: string): Promise<OrganizationItem[]> {
  const qs = country ? `?country=${country}&active_only=false` : "?active_only=false";
  return apiFetch<OrganizationItem[]>(`/api/v1/organizations${qs}`);
}

export function createOrganization(payload: OrganizationCreate): Promise<OrganizationItem> {
  return apiFetch<OrganizationItem>("/api/v1/organizations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateOrganization(orgId: string, payload: OrganizationUpdate): Promise<OrganizationItem> {
  return apiFetch<OrganizationItem>(`/api/v1/organizations/${orgId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteOrganization(orgId: string): Promise<void> {
  return apiFetch(`/api/v1/organizations/${orgId}`, { method: "DELETE" });
}

/** List all projects that include a given organization (linked org or contractor packages). */
export async function listProjectsForOrg(orgId: string): Promise<ProjectItem[]> {
  const all = await listProjects();
  const pkgEntries = await Promise.all(
    all.map(async (p) => {
      try {
        return [p.project_id, await listPackages(p.project_id)] as const;
      } catch {
        return [p.project_id, []] as const;
      }
    }),
  );
  const packagesByProject = Object.fromEntries(pkgEntries);
  return projectsForOrganization(orgId, all, packagesByProject);
}

export function listCountries(): Promise<CountryItem[]> {
  return apiFetch<CountryItem[]>("/api/v1/countries");
}

export function listLocations(params: {
  country?: string;
  level?: number;
  parent?: string;
  q?: string;
  active_only?: boolean;
  limit?: number;
  offset?: number;
}): Promise<LocationNode[]> {
  const p = new URLSearchParams();
  if (params.country) p.set("country", params.country);
  if (params.level !== undefined) p.set("level", String(params.level));
  if (params.parent) p.set("parent", params.parent);
  if (params.q) p.set("q", params.q);
  if (params.active_only !== undefined) p.set("active_only", String(params.active_only));
  if (params.limit !== undefined) p.set("limit", String(params.limit));
  if (params.offset !== undefined) p.set("offset", String(params.offset));
  return apiFetch<LocationNode[]>(`/api/v1/locations?${p}`);
}

export function listProjects(country?: string, activeOnly = true): Promise<ProjectItem[]> {
  const p = new URLSearchParams();
  if (country) p.set("country", country);
  p.set("active_only", String(activeOnly));
  return apiFetch<ProjectItem[]>(`/api/v1/projects?${p}`);
}

export function createProject(payload: ProjectCreate): Promise<ProjectItem> {
  return apiFetch<ProjectItem>("/api/v1/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export interface ProjectMessagingConfig {
  sms_enabled: boolean;
  sms_levels: number[];
  whatsapp_levels: number[];
  max_levels: number;
}

export interface ProjectMessagingPatch {
  sms_enabled?: boolean;
  sms_levels?: number[];
  whatsapp_levels?: number[];
}

export function getProjectMessaging(projectId: string): Promise<ProjectMessagingConfig> {
  return apiFetch<ProjectMessagingConfig>(`/api/v1/projects/${projectId}/messaging`);
}

export function patchProjectMessaging(
  projectId: string,
  body: ProjectMessagingPatch,
): Promise<ProjectMessagingConfig> {
  return apiFetch<ProjectMessagingConfig>(`/api/v1/projects/${projectId}/messaging`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function getProjectGoLive(projectId: string): Promise<GoLiveReport> {
  return apiFetch<GoLiveReport>(`/api/v1/projects/${projectId}/go-live`);
}

export function listProjectTypes(activeOnly = true): Promise<ProjectTypeItem[]> {
  return apiFetch<ProjectTypeItem[]>(`/api/v1/project-types?active_only=${activeOnly}`);
}

export function updateProjectType(
  typeKey: string,
  payload: Partial<Omit<ProjectTypeItem, "type_key" | "actor_roles">>,
): Promise<ProjectTypeItem> {
  return apiFetch<ProjectTypeItem>(`/api/v1/project-types/${typeKey}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function updateProject(
  projectId: string,
  payload: {
    name?: string;
    description?: string | null;
    is_active?: boolean;
    standard_workflow_id?: string | null;
    seah_workflow_id?: string | null;
  },
): Promise<ProjectItem> {
  return apiFetch<ProjectItem>(`/api/v1/projects/${projectId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function listWorkflowRoutingOptions(): Promise<WorkflowRoutingOptions> {
  return apiFetch("/api/v1/workflows/routing-options");
}

export function replaceProjectWorkflows(
  projectId: string,
  items: {
    display_label: string;
    workflow_id: string;
    classifications?: string[];
    intake_routes?: string[];
    is_default?: boolean;
    sort_order?: number;
  }[],
): Promise<ProjectWorkflowSlot[]> {
  return apiFetch(`/api/v1/projects/${projectId}/workflows`, {
    method: "PUT",
    body: JSON.stringify({ items }),
  });
}

export function deleteProject(projectId: string): Promise<void> {
  return apiFetch(`/api/v1/projects/${projectId}`, { method: "DELETE" });
}

export function addProjectOrg(
  projectId: string,
  orgId: string,
  orgRole?: string | null,
): Promise<ProjectOrgItem> {
  return apiFetch<ProjectOrgItem>(`/api/v1/projects/${projectId}/organizations/${orgId}`, {
    method: "POST",
    body: JSON.stringify({ org_role: orgRole ?? null }),
  });
}

export function updateProjectOrgRole(
  projectId: string,
  orgId: string,
  orgRole: string | null,
): Promise<ProjectOrgItem> {
  return apiFetch<ProjectOrgItem>(`/api/v1/projects/${projectId}/organizations/${orgId}`, {
    method: "PATCH",
    body: JSON.stringify({ org_role: orgRole }),
  });
}

/** Fetch the list of org-role definitions from settings. */
export function getOrgRoles(): Promise<OrgRole[]> {
  return apiFetch<{ key: string; value: OrgRole[] }>("/api/v1/settings/org_roles")
    .then((r) => r.value);
}

/** Super-admin: overwrite org-role definitions. */
export function setOrgRoles(roles: OrgRole[]): Promise<void> {
  return apiFetch<void>("/api/v1/settings/org_roles", {
    method: "PUT",
    body: JSON.stringify({ value: roles }),
  });
}

/** Super-admin: report export / quarterly email caps (ticketing.settings.report_limits). */
export function getReportLimits(): Promise<ReportLimitsInfo> {
  return apiFetch<{ key: string; value: ReportLimitsInfo }>("/api/v1/settings/report_limits").then(
    (r) => r.value,
  );
}

export function setReportLimits(limits: ReportLimitsInfo): Promise<void> {
  return apiFetch<void>("/api/v1/settings/report_limits", {
    method: "PUT",
    body: JSON.stringify({ value: limits }),
  });
}

/** Super-admin: resolved-case archiving policy (ticketing.settings.archiving_policy). */
export function getArchivingPolicy(): Promise<ArchivingPolicyInfo> {
  return apiFetch<{ key: string; value: ArchivingPolicyInfo }>(
    "/api/v1/settings/archiving_policy",
  ).then((r) => r.value);
}

export function setArchivingPolicy(policy: ArchivingPolicyInfo): Promise<void> {
  return apiFetch<void>("/api/v1/settings/archiving_policy", {
    method: "PUT",
    body: JSON.stringify({ value: policy }),
  });
}

/** Super-admin: grievance classification catalog (ticketing.settings.grievance_categories). */
export function getGrievanceCategoriesCatalog(): Promise<GrievanceCategoriesCatalogInfo> {
  return apiFetch<{ key: string; value: GrievanceCategoriesCatalogInfo }>(
    "/api/v1/settings/grievance_categories",
  ).then((r) => r.value);
}

export function setGrievanceCategoriesCatalog(
  catalog: GrievanceCategoriesCatalogInfo,
): Promise<void> {
  return apiFetch<void>("/api/v1/settings/grievance_categories", {
    method: "PUT",
    body: JSON.stringify({ value: catalog }),
  });
}

/** Per-project actor role vocabulary (editable; seeded from global defaults). */
export function getProjectActorRoles(projectId: string): Promise<OrgRole[]> {
  return apiFetch<OrgRole[]>(`/api/v1/projects/${projectId}/actor-roles`);
}

export function setProjectActorRoles(projectId: string, roles: OrgRole[]): Promise<OrgRole[]> {
  return apiFetch<OrgRole[]>(`/api/v1/projects/${projectId}/actor-roles`, {
    method: "PUT",
    body: JSON.stringify({ roles }),
  });
}

export function removeProjectOrg(projectId: string, orgId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/projects/${projectId}/organizations/${orgId}`, { method: "DELETE" });
}

export function addProjectLocation(projectId: string, locationCode: string): Promise<unknown> {
  return apiFetch(`/api/v1/projects/${projectId}/locations/${locationCode}`, { method: "POST" });
}

export function removeProjectLocation(projectId: string, locationCode: string): Promise<void> {
  return apiFetch<void>(`/api/v1/projects/${projectId}/locations/${locationCode}`, { method: "DELETE" });
}

// ── Packages ──────────────────────────────────────────────────────────────────

export interface PackageOrgItem {
  organization_id: string;
  org_role: string;
}

export interface PackageItem {
  package_id:        string;
  project_id:        string;
  package_code:      string;
  name:              string;
  description:       string | null;
  organizations:     PackageOrgItem[];
  is_active:         boolean;
  /** District/municipality codes this package covers. */
  location_codes:    string[];
  created_at:        string;
  updated_at:        string;
}

export interface PackageCreate {
  package_code:      string;
  name:              string;
  description?:      string | null;
  is_active?:        boolean;
}

export interface PackageUpdate {
  name?:              string;
  description?:       string | null;
  is_active?:         boolean;
}

export function listPackages(projectId: string): Promise<PackageItem[]> {
  return apiFetch<PackageItem[]>(`/api/v1/projects/${projectId}/packages`);
}

export function createPackage(projectId: string, payload: PackageCreate): Promise<PackageItem> {
  return apiFetch<PackageItem>(`/api/v1/projects/${projectId}/packages`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updatePackage(
  projectId: string,
  packageId: string,
  payload: PackageUpdate,
): Promise<PackageItem> {
  return apiFetch<PackageItem>(`/api/v1/projects/${projectId}/packages/${packageId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function addPackageLocation(
  projectId: string,
  packageId: string,
  locationCode: string,
): Promise<unknown> {
  return apiFetch(
    `/api/v1/projects/${projectId}/packages/${packageId}/locations/${locationCode}`,
    { method: "POST" },
  );
}

export function removePackageLocation(
  projectId: string,
  packageId: string,
  locationCode: string,
): Promise<void> {
  return apiFetch<void>(
    `/api/v1/projects/${projectId}/packages/${packageId}/locations/${locationCode}`,
    { method: "DELETE" },
  );
}

export function addPackageOrg(
  projectId: string,
  packageId: string,
  organizationId: string,
  orgRole: string,
): Promise<PackageOrgItem> {
  return apiFetch<PackageOrgItem>(
    `/api/v1/projects/${projectId}/packages/${packageId}/organizations/${organizationId}`,
    { method: "POST", body: JSON.stringify({ org_role: orgRole }) },
  );
}

export function removePackageOrg(
  projectId: string,
  packageId: string,
  organizationId: string,
  orgRole: string,
): Promise<void> {
  return apiFetch<void>(
    `/api/v1/projects/${projectId}/packages/${packageId}/organizations/${organizationId}/${encodeURIComponent(orgRole)}`,
    { method: "DELETE" },
  );
}

export function getLocationTemplateCsvUrl(): string {
  return `${BASE}/api/v1/locations/import/template.csv`;
}

export function getLocationTemplateJsonUrl(): string {
  return `${BASE}/api/v1/locations/import/template.json`;
}

export async function importLocations(
  file: File,
  opts: { country?: string; dry_run?: boolean; max_level?: number },
): Promise<ImportResult> {
  const form = new FormData();
  form.append("file", file);
  form.append("country", opts.country ?? "NP");
  form.append("dry_run", String(opts.dry_run ?? false));
  form.append("max_level", String(opts.max_level ?? 3));
  form.append("format", "auto");
  const resp = await fetch(`${BASE}/api/v1/locations/import`, {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`Import failed ${resp.status}: ${body}`);
  }
  return resp.json();
}

// ── QR Tokens ─────────────────────────────────────────────────────────────────

export interface QrTokenOut {
  token: string;
  package_id: string;
  is_active: boolean;
  created_at: string;
  created_by_user_id: string | null;
  expires_at: string | null;
  scan_url: string | null;
}

export interface QrTokenCreateResponse {
  token: string;
  package_id: string;
  scan_url: string;
}

export interface PackageQrItem {
  package_id: string;
  package_code: string;
  name: string;
  project_code: string;
  token: string;
  scan_url: string;
}

export function listMyPackagesQr(): Promise<PackageQrItem[]> {
  return apiFetch<PackageQrItem[]>("/api/v1/my-packages/qr");
}

export function listQrTokens(packageId: string): Promise<QrTokenOut[]> {
  return apiFetch<QrTokenOut[]>(`/api/v1/packages/${packageId}/qr-tokens`);
}

export function createQrToken(packageId: string): Promise<QrTokenCreateResponse> {
  return apiFetch<QrTokenCreateResponse>(`/api/v1/packages/${packageId}/qr-tokens`, {
    method: "POST",
  });
}

export function revokeQrToken(token: string): Promise<void> {
  return apiFetch<void>(`/api/v1/qr-tokens/${token}`, { method: "DELETE" });
}

// ── Officer jurisdiction scopes ───────────────────────────────────────────────

export interface OfficerScope {
  scope_id: string;
  user_id: string;
  role_key: string;
  organization_id: string;
  location_code: string | null;
  project_id: string | null;
  project_code: string | null;
  package_id: string | null;
  includes_children: boolean;
  created_at: string;
}

export interface ScopeCreate {
  role_key: string;
  organization_id: string;
  location_code?: string | null;
  project_id?: string | null;
  project_code?: string | null;
  package_id?: string | null;
  includes_children?: boolean;
}

export function listScopes(userId: string): Promise<OfficerScope[]> {
  return apiFetch<OfficerScope[]>(`/api/v1/users/${userId}/scopes`);
}

export function addScope(userId: string, payload: ScopeCreate): Promise<OfficerScope> {
  return apiFetch<OfficerScope>(`/api/v1/users/${userId}/scopes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function deleteScope(userId: string, scopeId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/users/${userId}/scopes/${scopeId}`, {
    method: "DELETE",
  });
}

// ── Teammates (for reassign dropdown) ────────────────────────────────────────

export interface TeammatesResponse {
  ticket_id: string;
  teammates: string[]; // user_ids
}

export function getTeammates(ticketId: string): Promise<TeammatesResponse> {
  return apiFetch<TeammatesResponse>(`/api/v1/tickets/${ticketId}/teammates`);
}

// ── LLM findings ──────────────────────────────────────────────────────────────

/** Trigger (re)generation of the AI case-findings summary. Returns 202 immediately. */
export function generateFindings(ticketId: string): Promise<{ ticket_id: string; status: string; message: string }> {
  return apiFetch(`/api/v1/tickets/${ticketId}/findings`, { method: "POST" });
}

// ── Vault reveal ──────────────────────────────────────────────────────────────

export const REVEAL_REASON_CODES = [
  { code: "immediate_safeguarding_action", label: "Immediate safeguarding action required" },
  { code: "investigation_required",        label: "Active investigation in progress" },
  { code: "legal_referral",                label: "Preparing legal referral or police report" },
  { code: "grc_hearing_preparation",       label: "Preparing for GRC hearing" },
  { code: "audit_verification",            label: "Audit or compliance verification" },
  { code: "supervisory_oversight",         label: "Supervisory review of case handling" },
  { code: "other",                         label: "Other (please explain below)" },
] as const;

export type RevealReasonCode = (typeof REVEAL_REASON_CODES)[number]["code"];

export interface RevealRequest {
  reason_code: RevealReasonCode | string;
  reason_text?: string;
}

/** Shape returned by POST /api/v1/tickets/{id}/reveal (proto + production). */
export interface RevealSession {
  granted: boolean;
  reveal_session_id?: string;
  /** ISO-8601 UTC — when this session token expires */
  expires_at_utc?: string;
  ttl_seconds?: number;
  /** Proto only: full grievance detail dict from GET /api/grievance/{id} */
  content?: {
    grievance_description?: string;
    complainant_name?: string;
    phone_number?: string;
    email?: string;
    address?: string;
    [key: string]: unknown;
  };
  watermark_text?: string;
  deny_code?: string;
  _proto_mode?: boolean;
}

/** Begin a vault reveal session — returns session with content for proto. */
export function revealOriginal(ticketId: string, payload: RevealRequest): Promise<RevealSession> {
  return apiFetch<RevealSession>(`/api/v1/tickets/${ticketId}/reveal`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** Close a reveal session (sends audit close event). */
export function closeReveal(
  ticketId: string,
  sessionId: string,
  closeReason = "user_closed",
): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>(`/api/v1/tickets/${ticketId}/reveal/close`, {
    method: "POST",
    body: JSON.stringify({ reveal_session_id: sessionId, close_reason: closeReason }),
  });
}

// ── Officer invite ────────────────────────────────────────────────────────────

export interface OfficerInvitePayload {
  email: string;
  role_key: string;
  organization_id: string;
  location_code?: string | null;
  project_id?: string | null;
  project_code?: string | null;
  package_id?: string | null;
  includes_children?: boolean;
  temp_password?: string;
}

export interface OfficerInviteResult {
  ok: boolean;
  email: string;
  message: string;
}

export function inviteOfficer(payload: OfficerInvitePayload): Promise<OfficerInviteResult> {
  return apiFetch<OfficerInviteResult>("/api/v1/users/invite", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function resendOfficerInvite(userId: string): Promise<OfficerInviteResult> {
  return apiFetch<OfficerInviteResult>(
    `/api/v1/users/${encodeURIComponent(userId)}/resend-invite`,
    { method: "POST" },
  );
}

export function deleteOfficer(userId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/users/${encodeURIComponent(userId)}`, { method: "DELETE" });
}

export function updateOfficerKeycloak(
  userId: string,
  payload: {
    role_keys: string[];
    organization_id: string;
    location_code?: string | null;
    sync_keycloak?: boolean;
  },
): Promise<{ ok: boolean; user_id: string }> {
  return apiFetch(`/api/v1/users/${encodeURIComponent(userId)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export interface UserRoleRow {
  user_role_id: string;
  user_id: string;
  role_id: string;
  organization_id: string;
  location_code: string | null;
  created_at: string;
}

export function listUserRoles(userId: string): Promise<UserRoleRow[]> {
  return apiFetch<UserRoleRow[]>(`/api/v1/users/${encodeURIComponent(userId)}/roles`);
}

export function deleteUserRole(userId: string, userRoleId: string): Promise<void> {
  return apiFetch<void>(
    `/api/v1/users/${encodeURIComponent(userId)}/roles/${encodeURIComponent(userRoleId)}`,
    { method: "DELETE" },
  );
}

// ── Language preferences ──────────────────────────────────────────────────────

export interface UserPreferences {
  user_id: string;
  /** Personal override set by the officer. null = use org default. */
  preferred_language: "en" | "ne" | null;
  /** The organisation's default (DOR → 'ne', ADB → 'en'). */
  org_default_language: string;
  /** Resolved language: preferred_language ?? org_default_language ?? 'en' */
  effective_language: "en" | "ne";
}

export function getUserPreferences(): Promise<UserPreferences> {
  return apiFetch<UserPreferences>("/api/v1/users/me/preferences");
}

export function patchUserPreferences(preferred_language: "en" | "ne" | null): Promise<UserPreferences> {
  return apiFetch<UserPreferences>("/api/v1/users/me/preferences", {
    method: "PATCH",
    body: JSON.stringify({ preferred_language }),
  });
}

// ── Officer profile (Keycloak) ──────────────────────────────────────────────

export interface OfficerProfile {
  user_id: string;
  email: string;
  first_name: string;
  last_name: string;
  phone_number: string;
  job_title: string;
  role_keys: string[];
  role_labels: string[];
}

export function getMyProfile(): Promise<OfficerProfile> {
  return apiFetch<OfficerProfile>("/api/v1/users/me/profile");
}

export function updateMyProfile(payload: {
  first_name: string;
  last_name: string;
  phone_number: string;
  job_title: string;
}): Promise<OfficerProfile> {
  return apiFetch<OfficerProfile>("/api/v1/users/me/profile", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

// ── Tasks ─────────────────────────────────────────────────────────────────────

export interface TicketTask {
  task_id: string;
  ticket_id: string;
  task_type: string;
  assigned_to_user_id: string;
  assigned_by_user_id: string;
  description: string | null;
  due_date: string | null;
  status: "PENDING" | "DONE" | "DISMISSED";
  completed_at: string | null;
  completed_by_user_id: string | null;
  created_at: string;
}

export interface TaskCreateRequest {
  task_type: string;
  assigned_to_user_id: string;
  description?: string;
  due_date?: string;
}

export function listTicketTasks(ticketId: string): Promise<TicketTask[]> {
  return apiFetch<TicketTask[]>(`/api/v1/tickets/${ticketId}/tasks`);
}

export function createTask(ticketId: string, body: TaskCreateRequest): Promise<TicketTask> {
  return apiFetch<TicketTask>(`/api/v1/tickets/${ticketId}/tasks`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function completeTask(ticketId: string, taskId: string): Promise<TicketTask> {
  return apiFetch<TicketTask>(`/api/v1/tickets/${ticketId}/tasks/${taskId}/complete`, {
    method: "POST",
  });
}

export function listMyTasks(): Promise<TicketTask[]> {
  return apiFetch<TicketTask[]>("/api/v1/users/me/tasks");
}

// ── Viewers (watchers) ────────────────────────────────────────────────────────

export function listViewers(ticketId: string): Promise<TicketViewer[]> {
  return apiFetch<TicketViewer[]>(`/api/v1/tickets/${ticketId}/viewers`);
}

export function addViewer(ticketId: string, userId: string): Promise<TicketViewer> {
  return apiFetch<TicketViewer>(`/api/v1/tickets/${ticketId}/viewers`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId }),
  });
}

export function removeViewer(ticketId: string, userId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/tickets/${ticketId}/viewers/${userId}`, { method: "DELETE" });
}

// ── Complainant info edit ─────────────────────────────────────────────────────

export interface ComplainantPatchPayload {
  complainant_full_name?:    string;
  complainant_phone?:        string;
  complainant_address?:      string;
  complainant_village?:      string;
  complainant_ward?:         string;
  complainant_municipality?: string;
  complainant_district?:     string;
  complainant_province?:     string;
  complainant_email?:        string;
}

export interface ComplainantPatchResponse {
  ticket_id:      string;
  complainant_id: string;
  fields_updated: string[];
  event_id:       string;
}

export function patchComplainant(
  ticketId: string,
  fields: ComplainantPatchPayload,
): Promise<ComplainantPatchResponse> {
  return apiFetch<ComplainantPatchResponse>(`/api/v1/tickets/${ticketId}/complainant`, {
    method: "PATCH",
    body: JSON.stringify(fields),
  });
}

