/**
 * trackFilter.ts — single source of truth for workflow-track ↔ role filtering.
 *
 * RB-2 (DESIGN §3 structural rule 1): the track-filter logic was duplicated four ways
 * (settings/page.tsx role list + the step→role picker, plus backend). A role's
 * `workflow_scope` is one of "Standard" | "SEAH" | "Both"; a workflow/step runs on a
 * "standard" | "seah" track. A "Both" role is valid on either track. Keep this the ONLY
 * place that encodes those rules on the client.
 */

export type TrackFilter = "all" | "standard" | "seah";
export type WorkflowTrack = "standard" | "seah";

/** Role workflow_scope as stored on ticketing.roles (display casing). */
export type RoleWorkflowScope = "Standard" | "SEAH" | "Both" | (string & {});

/** Does a role belong to a concrete workflow track? "Both" matches either. */
export function roleInTrack(workflowScope: string, track: WorkflowTrack): boolean {
  if (workflowScope === "Both") return true;
  return track === "seah" ? workflowScope === "SEAH" : workflowScope === "Standard";
}

/** Does a role pass a UI track filter? "all" matches everything. */
export function roleMatchesFilter(workflowScope: string, filter: TrackFilter): boolean {
  if (filter === "all") return true;
  return roleInTrack(workflowScope, filter);
}

/** Filter a list of items carrying a workflow_scope by a UI track filter. */
export function filterByTrack<T>(
  items: T[],
  getScope: (item: T) => string,
  filter: TrackFilter,
): T[] {
  if (filter === "all") return items;
  return items.filter((it) => roleInTrack(getScope(it), filter));
}

/** Normalize a workflow definition's track (workflow_type/track strings vary). */
export function workflowTrackOf(wf: { workflow_type?: string | null; track?: string | null } | null | undefined): WorkflowTrack {
  const raw = (wf?.workflow_type ?? wf?.track ?? "").toString().toLowerCase();
  return raw === "seah" ? "seah" : "standard";
}
