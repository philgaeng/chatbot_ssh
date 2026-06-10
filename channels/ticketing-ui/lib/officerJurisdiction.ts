import type { PackageItem, ProjectItem } from "@/lib/api";

/** Matches backend `project_types.routing_org_role` default and go-live routing. */
export const DEFAULT_ROUTING_ORG_ROLE = "implementing_agency";

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
