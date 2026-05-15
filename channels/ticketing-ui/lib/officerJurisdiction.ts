import type { PackageItem, ProjectItem } from "@/lib/api";

/** Donor org (e.g. ADB) may scope officers to any project on the system. */
export function isDonorAllProjectsOrg(orgId: string): boolean {
  return orgId === "ADB" || orgId.toUpperCase() === "ADB";
}

/** Projects an org may scope officers to (project_organizations link or contractor packages). */
export function projectsForOrganization(
  orgId: string,
  projects: ProjectItem[],
  packagesByProject: Record<string, PackageItem[]>,
): ProjectItem[] {
  if (!orgId) return [];
  if (isDonorAllProjectsOrg(orgId)) return projects;
  return projects.filter((p) => {
    const orgLinked = p.organizations.some((o) => o.organization_id === orgId);
    const contractorOnProject = (packagesByProject[p.project_id] ?? []).some(
      (pkg) => pkg.contractor_org_id === orgId,
    );
    return orgLinked || contractorOnProject;
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
  const contractorPkgs = allPackages.filter((pkg) => pkg.contractor_org_id === orgId);
  if (contractorPkgs.length > 0) return contractorPkgs;
  const orgLinked = project.organizations.some((o) => o.organization_id === orgId);
  if (orgLinked) return allPackages;
  return [];
}
