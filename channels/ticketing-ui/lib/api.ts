// GRM Ticketing API client
// All requests use relative paths (/api/v1/...) so they are proxied through
// the Next.js server rewrites → ticketing_api:5002 (see next.config.ts).
// This avoids CORS issues and means the browser only needs port 3001.

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
  grievance_location: string | null;
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
  const resp = await fetch(`${BASE}${path}`, { ...opts, headers });
  if (!resp.ok) {
    const body = await resp.text();
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
  if (filters.sla_breached !== undefined) p.set("sla_breached", String(filters.sla_breached));
  p.set("page", String(filters.page ?? 1));
  p.set("page_size", String(filters.page_size ?? 50));
  return apiFetch<TicketListResponse>(`/api/v1/tickets?${p}`);
}

export function getTicket(id: string): Promise<TicketDetail> {
  return apiFetch<TicketDetail>(`/api/v1/tickets/${id}`);
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
  assign_to_user_id?: string;
  grc_hearing_date?: string;
  grc_decision?: string;
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
}

export function createWorkflow(payload: WorkflowCreatePayload): Promise<WorkflowDefinition> {
  return apiFetch("/api/v1/workflows", { method: "POST", body: JSON.stringify(payload) });
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
  permissions: unknown;
  created_at: string;
  updated_at: string;
}

export function listRoles(): Promise<GrmRole[]> {
  return apiFetch<GrmRole[]>("/api/v1/roles");
}

export function updateRole(
  roleId: string,
  payload: {
    display_name?: string | null;
    description?: string | null;
    workflow_scope?: string | null;
  }
): Promise<GrmRole> {
  return apiFetch<GrmRole>(`/api/v1/roles/${roleId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

/** Settings → Officers (admin): aggregated ticketing.user_roles — no Keycloak sync. */
export interface OfficerRosterEntry {
  user_id: string;
  display_name: string;
  email: string | null;
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

export function getFileDownloadUrl(fileId: string): string {
  return `${BASE}/api/v1/files/${fileId}`;
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

export function getOfficerAttachmentUrl(fileId: string): string {
  return `${BASE}/api/v1/attachments/${fileId}`;
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
    throw new Error(`Upload failed ${resp.status}: ${body}`);
  }
  return resp.json();
}

// ── Reports ───────────────────────────────────────────────────────────────────

export function exportReport(params: {
  date_from?: string;
  date_to?: string;
  organization_id?: string;
}): string {
  const p = new URLSearchParams();
  if (params.date_from) p.set("date_from", params.date_from);
  if (params.date_to) p.set("date_to", params.date_to);
  if (params.organization_id) p.set("organization_id", params.organization_id);
  return `${BASE}/api/v1/reports/export?${p}`;
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

export interface ProjectItem {
  project_id: string;
  country_code: string;
  short_code: string;
  name: string;
  description: string | null;
  is_active: boolean;
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

/** List all projects that include a given organization. */
export function listProjectsForOrg(orgId: string): Promise<ProjectItem[]> {
  // Filter client-side from the full project list (no dedicated endpoint needed yet)
  return listProjects().then((all) =>
    all.filter((p) => p.organizations.some((o) => o.organization_id === orgId))
  );
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

export function listProjects(country?: string): Promise<ProjectItem[]> {
  const qs = country ? `?country=${country}` : "";
  return apiFetch<ProjectItem[]>(`/api/v1/projects${qs}`);
}

export function createProject(payload: ProjectCreate): Promise<ProjectItem> {
  return apiFetch<ProjectItem>("/api/v1/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateProject(projectId: string, payload: { name?: string; description?: string | null; is_active?: boolean }): Promise<ProjectItem> {
  return apiFetch<ProjectItem>(`/api/v1/projects/${projectId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
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

export interface PackageItem {
  package_id:        string;
  project_id:        string;
  package_code:      string;
  name:              string;
  description:       string | null;
  contractor_org_id: string | null;
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
  contractor_org_id?: string | null;
  is_active?:        boolean;
}

export interface PackageUpdate {
  name?:              string;
  description?:       string | null;
  contractor_org_id?: string | null;
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

