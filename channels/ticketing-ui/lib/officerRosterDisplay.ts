import type { OfficerRosterEntry, OfficerRosterScope, PackageItem, ProjectItem } from "@/lib/api";
import { isCountryJurisdictionRole } from "@/lib/jurisdiction";

const ADMIN_ROLE_KEYS = new Set(["super_admin", "country_admin", "project_admin"]);

type RoleChoice = { key: string; label: string };

function roleLabel(roleKey: string, catalog: RoleChoice[]): string {
  return catalog.find((r) => r.key === roleKey)?.label ?? roleKey;
}

function compactList(items: string[], max = 3): string {
  if (items.length === 0) return "";
  if (items.length <= max) return items.join(", ");
  return `${items.slice(0, max).join(", ")} +${items.length - max}`;
}

function projectCodeForScope(
  scope: OfficerRosterScope,
  projectById: Record<string, ProjectItem>,
): string | null {
  if (scope.project_code) return scope.project_code;
  if (scope.project_id && projectById[scope.project_id]) {
    return projectById[scope.project_id].short_code;
  }
  return null;
}

/** Wide coverage label when scope has no project (org / country). */
function wideCoverageLabel(scope: OfficerRosterScope): string {
  if (scope.location_code) {
    const code = scope.location_code;
    if (/^P\d/i.test(code)) return "NP";
    return code.split("_")[0] || scope.organization_id;
  }
  return scope.organization_id || "NP";
}

function scopeOnProject(
  scope: OfficerRosterScope,
  project: ProjectItem,
  projectPackageIds: Set<string>,
): boolean {
  if (scope.project_id === project.project_id) return true;
  if (scope.project_code === project.short_code) return true;
  return Boolean(scope.package_id && projectPackageIds.has(scope.package_id));
}

/**
 * Coverage column on Settings → Projects → Staffing.
 * Project-wide: KL_ROAD. Package lot: KL_ROAD/01. Location codes appended when set.
 */
export function projectStaffingCoverageLine(
  officer: OfficerRosterEntry,
  project: ProjectItem,
  pkgById: Record<string, PackageItem>,
): string {
  const parts: string[] = [];
  const scopes = officer.scopes ?? [];
  const projectPackageIds = new Set(Object.keys(pkgById));

  let hasProjectWide = false;
  const packageLabels = new Set<string>();

  const relevantScopes = scopes.filter((s) =>
    scopeOnProject(s, project, projectPackageIds),
  );

  for (const s of relevantScopes) {
    if (s.package_id && projectPackageIds.has(s.package_id)) {
      const pkg = pkgById[s.package_id];
      if (pkg) packageLabels.add(`${project.short_code}/${pkg.package_code}`);
    } else if (!s.package_id) {
      hasProjectWide = true;
    }
  }

  if (relevantScopes.length === 0) {
    const pkgIdsOnProject = (officer.package_ids ?? []).filter((id) =>
      projectPackageIds.has(id),
    );
    if (
      (officer.project_codes ?? []).includes(project.short_code) &&
      pkgIdsOnProject.length === 0
    ) {
      hasProjectWide = true;
    }
    for (const id of pkgIdsOnProject) {
      const pkg = pkgById[id];
      if (pkg) packageLabels.add(`${project.short_code}/${pkg.package_code}`);
    }
  }

  if (hasProjectWide) parts.push(project.short_code);
  parts.push(
    ...[...packageLabels].sort((a, b) =>
      a.localeCompare(b, undefined, { numeric: true }),
    ),
  );

  const locs = new Set<string>();
  for (const s of relevantScopes) {
    if (s.location_code) locs.add(s.location_code);
  }
  if (locs.size === 0 && relevantScopes.length === 0) {
    officer.location_codes.forEach((c) => locs.add(c));
  }
  parts.push(...[...locs].sort());

  return parts.length ? parts.join(", ") : "—";
}

/**
 * One line per GRM role: "Site Safeguard Officer: KL_ROAD, SHEP/01".
 * Admin roles without scopes show "(all projects)".
 */
export function roleProjectsLines(
  officer: OfficerRosterEntry,
  roleCatalog: RoleChoice[],
  projectById: Record<string, ProjectItem>,
): string[] {
  const scopes = officer.scopes ?? [];
  const lines: string[] = [];
  const coveredRoles = new Set<string>();

  if (scopes.length > 0) {
    const projectsByRole = new Map<string, Set<string>>();
    for (const scope of scopes) {
      coveredRoles.add(scope.role_key);
      if (!projectsByRole.has(scope.role_key)) {
        projectsByRole.set(scope.role_key, new Set());
      }
      const bucket = projectsByRole.get(scope.role_key)!;
      const pcode = projectCodeForScope(scope, projectById);
      if (pcode) {
        bucket.add(pcode);
      } else {
        bucket.add(wideCoverageLabel(scope));
      }
    }

    for (const [rk, projs] of [...projectsByRole.entries()].sort(([a], [b]) =>
      roleLabel(a, roleCatalog).localeCompare(roleLabel(b, roleCatalog)),
    )) {
      const sorted = [...projs].sort();
      lines.push(`${roleLabel(rk, roleCatalog)}: ${sorted.join(", ")}`);
    }
  }

  for (const rk of officer.role_keys) {
    if (coveredRoles.has(rk)) continue;
    if (ADMIN_ROLE_KEYS.has(rk) || isCountryJurisdictionRole(rk)) {
      lines.push(`${roleLabel(rk, roleCatalog)}: (all projects)`);
    } else if (scopes.length === 0) {
      lines.push(`${roleLabel(rk, roleCatalog)}: —`);
    }
  }

  if (lines.length === 0 && officer.role_keys.length > 0) {
    for (const rk of officer.role_keys) {
      lines.push(`${roleLabel(rk, roleCatalog)}: —`);
    }
  }

  return lines;
}

/** Locations only — from scope rows when present. */
export function officerLocationsSummary(officer: OfficerRosterEntry): string {
  const fromScopes = (officer.scopes ?? [])
    .map((s) => s.location_code)
    .filter((c): c is string => Boolean(c));
  const locs = fromScopes.length > 0 ? fromScopes : officer.location_codes;
  const unique = [...new Set(locs)].sort();
  if (unique.length === 0) return "—";
  return compactList(unique, 4) || unique[0];
}

/** True when role appears on user_roles or any officer_scopes row (roster filter). */
export function officerHasRoleKey(officer: OfficerRosterEntry, roleKey: string): boolean {
  if (!roleKey) return true;
  if (officer.role_keys.includes(roleKey)) return true;
  return (officer.scopes ?? []).some((s) => s.role_key === roleKey);
}

export function officerHasScopeJurisdiction(officer: OfficerRosterEntry): boolean {
  const scopes = officer.scopes ?? [];
  if (scopes.length > 0) {
    return scopes.some(
      (s) =>
        Boolean(s.project_code || s.project_id || s.package_id || s.location_code) ||
        isCountryJurisdictionRole(s.role_key),
    );
  }
  return (
    (officer.project_codes?.length ?? 0) > 0 ||
    (officer.package_ids?.length ?? 0) > 0 ||
    officer.location_codes.length > 0
  );
}
