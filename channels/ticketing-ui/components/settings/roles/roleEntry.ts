// SPDX-License-Identifier: Apache-2.0

/**
 * roleEntry.ts — the shared GRM role view-model for the Settings surfaces.
 *
 * `RoleEntry` + `mapGrmRoleToEntry` are consumed by three clusters (roles, workflows,
 * and the settings shell itself), so they live here rather than inside any one of them.
 *
 * Extracted verbatim from `app/settings/page.tsx` (T3-05) — no behaviour change.
 */
import { type GrmRole } from "@/lib/api";

export type RoleEntry = {
  role_id: string;
  key: string;
  label: string;
  workflow: string;
  jurisdiction: string;
  description: string;
  role_origin?: string;
  steps_count?: number;
  officers_count?: number;
  // R6 (BUILD-REVIEW M7): SH-7 org-scoped catalog owning level (NULL = System · everywhere).
  owner_organization_id?: string | null;
  // Actor affiliation (org_category vocab) — drives the Roles catalog "actor type" filter.
  actor_category?: string | null;
};

export function mapGrmRoleToEntry(r: GrmRole): RoleEntry {
  return {
    role_id: r.role_id,
    key: r.role_key,
    label: r.display_name,
    workflow: r.workflow_scope ?? "Standard",
    jurisdiction: r.jurisdiction_mode ?? "field",
    description: r.description ?? "",
    role_origin: r.role_origin ?? "system",
    steps_count: r.steps_count ?? 0,
    officers_count: r.officers_count ?? 0,
    owner_organization_id: r.owner_organization_id ?? null,
    actor_category: r.actor_category ?? null,
  };
}

/** R6: owning-level label for the SH-7 org-scoped catalog chip (M7 / §4.4). */
export function owningLevelLabel(ownerOrgId: string | null | undefined): string {
  return ownerOrgId ? `${ownerOrgId} & below` : "System · everywhere";
}
