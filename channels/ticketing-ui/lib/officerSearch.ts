// SPDX-License-Identifier: Apache-2.0

/**
 * Officer directory search — the haystack, as a pure function (GRM-087).
 *
 * **What was wrong.** The directory matched `display_name`, `email` and `positions` only, while
 * the table renders five columns. So the two an admin actually scans by — **Office** and
 * **Project / area** — were on screen and unsearchable, and "find everyone at the Jhapa division
 * office" meant reading 57 rows.
 *
 * **Why this is cheap.** None of it is a new fetch. `<OfficersDirectory>` already resolves org
 * names, project names and location scopes client-side to render `projectAreaCell`; this reuses
 * those same lookups. Filtering stays client-side over the full roster — the standing TODO to move
 * search server-side is unchanged and out of scope here.
 *
 * Pure and in `lib/` per `engineering/05_frontend.md` rule 2.2, which is what makes the matching
 * rules testable without a DOM.
 */

/** The subset of `OfficerRosterEntry` search reads. Structural, so tests need no API types. */
export interface SearchableOfficer {
  display_name: string;
  email: string | null;
  positions?: string[];
  organization_ids: string[];
  project_codes?: string[];
  location_codes: string[];
  scopes?: { location_code?: string | null }[];
}

export interface OfficerSearchLookups {
  /** organization_id → the names shown in the Office column. */
  orgById: Map<string, { name: string; display_name_ne?: string | null }>;
  /** short_code → the name shown in the Project / area column. */
  projectByCode: Map<string, { name: string }>;
  /** Code → human label. `prettyLocation` in the app; injected so this file stays pure. */
  locationLabel: (code: string) => string;
}

/**
 * Every string one officer can be found by, lower-cased and space-joined.
 *
 * ⚠ **Raw codes are included alongside their labels**, deliberately. A location code never
 * reaches the screen (`ui/05` rule 5 forbids slugs in the UI) — but an admin handed a code in an
 * email should be able to paste it here and land on the right officer. Searching by a code is not
 * displaying one.
 */
export function officerSearchHaystack(
  officer: SearchableOfficer,
  lookups: OfficerSearchLookups,
): string {
  const parts: (string | null | undefined)[] = [
    officer.display_name,
    officer.email,
    ...(officer.positions ?? []),
  ];

  for (const id of officer.organization_ids) {
    const org = lookups.orgById.get(id);
    if (org) parts.push(org.name, org.display_name_ne);
  }

  for (const code of officer.project_codes ?? []) {
    parts.push(code, lookups.projectByCode.get(code)?.name);
  }

  // Scope locations and directly-held locations are the same column on screen, so they are one
  // haystack here. De-duplicated because a location usually appears in both.
  const codes = new Set<string>();
  for (const s of officer.scopes ?? []) if (s.location_code) codes.add(s.location_code);
  for (const c of officer.location_codes) if (c) codes.add(c);
  for (const c of codes) parts.push(c, lookups.locationLabel(c));

  return parts.filter(Boolean).join(" ").toLowerCase();
}

/**
 * Does this officer match the typed term?
 *
 * An empty or whitespace-only term matches everything — the search box is not a filter until
 * somebody types in it, and returning nothing for `""` would render the directory empty on load.
 */
export function officerMatchesSearch(
  officer: SearchableOfficer,
  term: string,
  lookups: OfficerSearchLookups,
): boolean {
  const needle = term.trim().toLowerCase();
  if (!needle) return true;
  return officerSearchHaystack(officer, lookups).includes(needle);
}

// ── Structured filters (GRM-088) ────────────────────────────────────────────

/**
 * The narrowing controls beside the search box.
 *
 * ⚠ **Deliberately NOT the track filter.** Standard / SEAH is a different kind of control — it
 * partitions by sensitivity and is gated on whether the admin may see SEAH at all — so it stays
 * where it is and composes with these. Folding it in here would put a permissions question in the
 * same bag as a convenience one.
 */
export interface OfficerFilterCriteria {
  /** `organization_id`, or "" for any. */
  organizationId: string;
  /** Project `short_code`, or "" for any. */
  projectCode: string;
  /** A location code held directly or through a scope, or "" for any. */
  locationCode: string;
}

export const EMPTY_OFFICER_FILTER: OfficerFilterCriteria = {
  organizationId: "",
  projectCode: "",
  locationCode: "",
};

export function isOfficerFilterActive(c: OfficerFilterCriteria): boolean {
  return c.organizationId !== "" || c.projectCode !== "" || c.locationCode !== "";
}

/** Every location this officer covers — held directly, or through a scope. One set, as on screen. */
export function officerLocationCodes(officer: SearchableOfficer): Set<string> {
  const out = new Set<string>();
  for (const s of officer.scopes ?? []) if (s.location_code) out.add(s.location_code);
  for (const c of officer.location_codes) if (c) out.add(c);
  return out;
}

/**
 * Does this officer pass every set filter?
 *
 * The filters **AND** together, and with the search term — an admin who picks an organisation and
 * then types is narrowing, not starting over. (A filter set that ORed would widen as you added
 * controls, which is the surprising direction.)
 */
export function officerMatchesFilter(
  officer: SearchableOfficer,
  c: OfficerFilterCriteria,
): boolean {
  if (c.organizationId && !officer.organization_ids.includes(c.organizationId)) return false;
  if (c.projectCode && !(officer.project_codes ?? []).includes(c.projectCode)) return false;
  if (c.locationCode && !officerLocationCodes(officer).has(c.locationCode)) return false;
  return true;
}

/**
 * The values the filters can offer, taken from the roster itself.
 *
 * ⭐ Derived, never hardcoded — and derived from the **roster**, not from the full organisation or
 * project lists: a filter offering an organisation that employs nobody is a control whose only
 * possible outcome is an empty table. Same rule as `availableFilterValues` on the org tree.
 */
export function availableOfficerFilterValues(officers: SearchableOfficer[]): {
  organizationIds: string[];
  projectCodes: string[];
  locationCodes: string[];
} {
  const organizationIds = new Set<string>();
  const projectCodes = new Set<string>();
  const locationCodes = new Set<string>();
  for (const o of officers) {
    for (const id of o.organization_ids) organizationIds.add(id);
    for (const c of o.project_codes ?? []) projectCodes.add(c);
    for (const c of officerLocationCodes(o)) locationCodes.add(c);
  }
  return {
    organizationIds: [...organizationIds].sort(),
    projectCodes: [...projectCodes].sort(),
    locationCodes: [...locationCodes].sort(),
  };
}
