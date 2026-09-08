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
