/** Align with ticketing.constants.jurisdiction — used before role catalog loads. */

export type JurisdictionMode = "field" | "country" | "global";

const COUNTRY_DEFAULT_ROLES = new Set([
  "country_admin",
  "adb_national_project_director",
  "adb_hq_safeguards",
  "adb_hq_project",
  "adb_hq_exec",
]);

export function defaultJurisdictionMode(roleKey: string): JurisdictionMode {
  if (roleKey === "super_admin") return "global";
  if (COUNTRY_DEFAULT_ROLES.has(roleKey)) return "country";
  return "field";
}

export function resolveJurisdictionMode(
  roleKey: string,
  stored: string | null | undefined,
): JurisdictionMode {
  if (stored === "field" || stored === "country" || stored === "global") {
    return stored;
  }
  return defaultJurisdictionMode(roleKey);
}

export function isCountryJurisdictionRole(roleKey: string, stored?: string | null): boolean {
  return resolveJurisdictionMode(roleKey, stored) === "country";
}

export function isGlobalJurisdictionRole(roleKey: string, stored?: string | null): boolean {
  return resolveJurisdictionMode(roleKey, stored) === "global";
}

export const JURISDICTION_MODE_LABELS: Record<JurisdictionMode, string> = {
  field: "Project / field (package or location required)",
  country: "Country-wide (all projects for this organization)",
  global: "Global (all tickets)",
};
