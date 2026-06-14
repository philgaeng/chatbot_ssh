import type { OrganizationItem, OrgRole, PackageItem, ProjectItem } from "@/lib/api";

/** Matches backend `project_types.routing_org_role` default and go-live routing. */
export const DEFAULT_ROUTING_ORG_ROLE = "implementing_agency";

export type OrgScopeAssignment = {
  organization_id: string;
  org_role: string;
  project_id: string;
  package_id?: string;
};

/** Every org ↔ org_role link on projects and packages (for scope filtering). */
export function collectOrganizationScopeAssignments(
  projects: ProjectItem[],
  packagesByProject: Record<string, PackageItem[]>,
): OrgScopeAssignment[] {
  const rows: OrgScopeAssignment[] = [];
  for (const project of projects) {
    for (const link of project.organizations) {
      if (link.org_role) {
        rows.push({
          organization_id: link.organization_id,
          org_role: link.org_role,
          project_id: project.project_id,
        });
      }
    }
    for (const pkg of packagesByProject[project.project_id] ?? []) {
      for (const link of pkg.organizations ?? []) {
        if (link.org_role) {
          rows.push({
            organization_id: link.organization_id,
            org_role: link.org_role,
            project_id: project.project_id,
            package_id: pkg.package_id,
          });
        }
      }
    }
  }
  return rows;
}

/** Scope keys present in assignments (optionally limited to one project). */
export function scopeOptionsFromAssignments(
  assignments: OrgScopeAssignment[],
  orgRoles: OrgRole[],
  projectId?: string | null,
): { key: string; label: string }[] {
  const keys = new Set<string>();
  for (const row of assignments) {
    if (projectId && row.project_id !== projectId) continue;
    if (row.org_role) keys.add(row.org_role);
  }
  const labelByKey = new Map(orgRoles.map((r) => [r.key, r.label]));
  return [...keys]
    .sort((a, b) => (labelByKey.get(a) ?? a).localeCompare(labelByKey.get(b) ?? b))
    .map((key) => ({
      key,
      label: labelByKey.get(key) ?? key.replace(/_/g, " "),
    }));
}

/** Organizations linked with a given scope (org_role). Empty scope = all orgs in list. */
export function organizationsForScopeFilter(
  orgs: OrganizationItem[],
  assignments: OrgScopeAssignment[],
  scopeKey: string,
  projectId?: string | null,
): OrganizationItem[] {
  if (!scopeKey) {
    return [...orgs].sort((a, b) => a.name.localeCompare(b.name));
  }
  const allowed = new Set<string>();
  for (const row of assignments) {
    if (row.org_role !== scopeKey) continue;
    if (projectId && row.project_id !== projectId) continue;
    allowed.add(row.organization_id);
  }
  return orgs
    .filter((o) => allowed.has(o.organization_id))
    .sort((a, b) => a.name.localeCompare(b.name));
}

/** Org roles this organization holds (on a project when projectId set). */
export function orgRoleKeysForOrganization(
  orgId: string,
  assignments: OrgScopeAssignment[],
  projectId?: string | null,
): string[] {
  const keys = new Set<string>();
  for (const row of assignments) {
    if (row.organization_id !== orgId || !row.org_role) continue;
    if (projectId && row.project_id !== projectId) continue;
    keys.add(row.org_role);
  }
  return [...keys].sort();
}

/**
 * Organization that owns ticket routing for a project (e.g. DOR on KL Road).
 * Used to default officer invite org so scopes match auto-assign.
 */
export function routingOrganizationId(
  project: ProjectItem | undefined,
  routingOrgRole: string = DEFAULT_ROUTING_ORG_ROLE,
): string | null {
  if (!project) return null;
  const match = project.organizations.find((o) => o.org_role === routingOrgRole);
  return match?.organization_id ?? null;
}

/** Donor org (e.g. ADB) may scope officers to any project on the system. */
export function isDonorAllProjectsOrg(orgId: string): boolean {
  return orgId === "ADB" || orgId.toUpperCase() === "ADB";
}

function orgOnPackage(pkg: PackageItem, orgId: string): boolean {
  return (pkg.organizations ?? []).some((o) => o.organization_id === orgId);
}

/** Projects an org may scope officers to (project_organizations link or package actors). */
export function projectsForOrganization(
  orgId: string,
  projects: ProjectItem[],
  packagesByProject: Record<string, PackageItem[]>,
): ProjectItem[] {
  if (!orgId) return [];
  if (isDonorAllProjectsOrg(orgId)) return projects;
  return projects.filter((p) => {
    const orgLinked = p.organizations.some((o) => o.organization_id === orgId);
    const onPackage = (packagesByProject[p.project_id] ?? []).some((pkg) => orgOnPackage(pkg, orgId));
    return orgLinked || onPackage;
  });
}

/** Packages available when scoping an officer on a project for a given org. */
export function packagesForOrganizationOnProject(
  orgId: string,
  project: ProjectItem | undefined,
  allPackages: PackageItem[],
): PackageItem[] {
  if (!orgId || !project) return [];
  if (isDonorAllProjectsOrg(orgId)) return allPackages;
  const actorPkgs = allPackages.filter((pkg) => orgOnPackage(pkg, orgId));
  if (actorPkgs.length > 0) return actorPkgs;
  const orgLinked = project.organizations.some((o) => o.organization_id === orgId);
  if (orgLinked) return allPackages;
  return [];
}

/**
 * All organizations that may scope officers on a project: project actors plus
 * contractors/consultants linked on packages (e.g. main_contractor per lot).
 */
export function organizationsOnProject(
  project: ProjectItem | undefined,
  allOrgs: OrganizationItem[],
  packages: PackageItem[] = [],
): OrganizationItem[] {
  if (!project) return [];
  const linkedIds = new Set<string>();
  for (const link of project.organizations) {
    linkedIds.add(link.organization_id);
  }
  for (const pkg of packages) {
    for (const link of pkg.organizations ?? []) {
      linkedIds.add(link.organization_id);
    }
  }
  const byId = new Map(allOrgs.map((o) => [o.organization_id, o]));
  const rows: OrganizationItem[] = [];
  for (const id of linkedIds) {
    const org = byId.get(id);
    if (org) {
      rows.push(org);
    } else {
      rows.push({
        organization_id: id,
        name: id,
        country_code: null,
        is_active: true,
        created_at: "",
        updated_at: "",
      });
    }
  }
  return rows.sort((a, b) => a.name.localeCompare(b.name));
}

/** Organizations on a project, optionally narrowed to one org_role (scope). */
export function organizationsOnProjectForScope(
  project: ProjectItem | undefined,
  allOrgs: OrganizationItem[],
  packages: PackageItem[] = [],
  scopeKey = "",
): OrganizationItem[] {
  const base = organizationsOnProject(project, allOrgs, packages);
  if (!scopeKey || !project) return base;
  const allowed = new Set<string>();
  for (const link of project.organizations) {
    if (link.org_role === scopeKey) allowed.add(link.organization_id);
  }
  for (const pkg of packages) {
    for (const link of pkg.organizations ?? []) {
      if (link.org_role === scopeKey) allowed.add(link.organization_id);
    }
  }
  return base.filter((o) => allowed.has(o.organization_id));
}
