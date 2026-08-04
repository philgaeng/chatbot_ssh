/**
 * labels.ts — plain-language display map (DESIGN §7.C: "labels not slugs on product surfaces").
 *
 * The backend returns `display_name` for roles/workflows; prefer that. This module is the
 * fallback + the map for values that surface as raw slugs (org roles, tracks, tiers). Never
 * render a bare `role_key` / `org_role` on a product surface — route it through here.
 */

/** "site_safeguards_focal_person" → "Site Safeguards Focal Person". */
export function humanizeSlug(slug: string | null | undefined): string {
  if (!slug) return "";
  return slug
    .split(/[_\-\s]+/)
    .filter(Boolean)
    .map((w) => (w.length <= 3 && w === w.toLowerCase() ? w.toUpperCase() : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(" ");
}

/** Prefer a server-provided display name; fall back to a humanized key. */
export function roleLabel(key: string | null | undefined, displayName?: string | null): string {
  if (displayName && displayName.trim()) return displayName.trim();
  return humanizeSlug(key);
}

/** Workflow-track labels (the "standard"/"seah" internal values → product copy). */
export const TRACK_LABELS: Record<string, string> = {
  standard: "Standard",
  seah: "SEAH",
  both: "Both tracks",
};

export function trackLabel(track: string | null | undefined): string {
  if (!track) return "";
  return TRACK_LABELS[track.toLowerCase()] ?? humanizeSlug(track);
}

/**
 * Fallback labels for a level's four jobs, in plain language (DESIGN §4.3).
 *
 * These are a LAST RESORT. Doc 13 §5A.1: the screen shows the **named role** the workflow
 * declares for that job — never a generic word. So prefer, in order:
 *   1. the workflow author's own label for the job (`tier_labels`, not built yet — doc 12 §6.2);
 *   2. the display name of the role bound to it (`roleLabel(assigned_role_key, …)`);
 *   3. these.
 * "Handles it" is on the ui/05 §4 avoid list (informal, and generic where a name belongs).
 */
export const CAST_TIER_LABELS: Record<string, string> = {
  assigned_role_key: "Works it",
  supervisor_role: "Oversees",
  informed_roles: "Kept informed",
  observer_roles: "Can view",
};

/**
 * Organization-role labels. The org actor-role catalog is being retired (doc 13 /
 * DECISION 2026-07-10) in favour of implementing_agency + project_donors, but legacy
 * `org_role` values still surface during the expand phase — humanize them cleanly.
 */
export const ORG_ROLE_LABELS: Record<string, string> = {
  implementing_agency: "Implementing agency",
  donor: "Donor",
  executing_agency: "Executing agency",
  project_owner: "Project owner",
  main_contractor: "Main contractor",
  subcontractor_t1: "Subcontractor (T1)",
  subcontractor_t2: "Subcontractor (T2)",
  supervision_consultant: "Supervision consultant",
  specialized_consultant: "Specialized consultant",
};

export function orgRoleLabel(role: string | null | undefined): string {
  if (!role) return "";
  return ORG_ROLE_LABELS[role] ?? humanizeSlug(role);
}
