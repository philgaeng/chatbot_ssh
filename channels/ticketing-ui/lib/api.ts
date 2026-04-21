// GRM Ticketing API client
// Base URL: NEXT_PUBLIC_API_URL (default http://localhost:5002)

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:5002";

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
  unseen_event_count: number;
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
}

export interface WorkflowDefinition {
  workflow_id: string;
  workflow_key: string;
  display_name: string;
  description: string | null;
  workflow_type: string;
  steps: WorkflowStep[];
}

// ── Fetch wrapper ─────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, opts?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...opts?.headers },
    ...opts,
  });
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`API ${resp.status} ${path}: ${body}`);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

// ── Ticket endpoints ──────────────────────────────────────────────────────────

export interface TicketFilters {
  my_queue?: boolean;
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
  if (filters.my_queue) p.set("my_queue", "true");
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

// ── Misc endpoints ────────────────────────────────────────────────────────────

export function getBadge(): Promise<BadgeResponse> {
  return apiFetch<BadgeResponse>("/api/v1/users/me/badge");
}

export function listWorkflows(): Promise<{ items: WorkflowDefinition[]; total: number }> {
  return apiFetch("/api/v1/workflows");
}

// ── Grievance PII (fetched from backend API, NOT ticketing API) ───────────────
// PII is never stored in ticketing.* — always fetched fresh from backend.

export interface GrievancePii {
  grievance_id: string;
  complainant_name?: string;
  phone_number?: string;
  email?: string;
  address?: string;
  [key: string]: unknown;
}

const BACKEND_BASE = process.env.NEXT_PUBLIC_BACKEND_API_URL ?? "http://localhost:5001";

export async function getGrievancePii(grievanceId: string): Promise<GrievancePii> {
  const resp = await fetch(`${BACKEND_BASE}/api/grievance/${grievanceId}`);
  if (!resp.ok) throw new Error(`Grievance API ${resp.status}`);
  return resp.json();
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
