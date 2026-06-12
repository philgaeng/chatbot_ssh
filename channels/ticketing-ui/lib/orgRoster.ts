import type { OrganizationItem, PackageItem, ProjectItem } from "@/lib/api";

export type OrgProjectLink = {
  project_id: string;
  short_code: string;
  org_role: string | null;
};

/** Project + actor-role links for one org (project actors + package contractors). */
export function orgProjectLinks(
  orgId: string,
  projects: ProjectItem[],
  packagesByProject: Record<string, PackageItem[]>,
): OrgProjectLink[] {
  const byProject = new Map<string, OrgProjectLink>();

  for (const p of projects) {
    const po = p.organizations.find((o) => o.organization_id === orgId);
    if (po) {
      byProject.set(p.project_id, {
        project_id: p.project_id,
        short_code: p.short_code,
        org_role: po.org_role,
      });
    }
  }

  for (const p of projects) {
    for (const pkg of packagesByProject[p.project_id] ?? []) {
      const pkgOrg = pkg.organizations.find((o) => o.organization_id === orgId);
      if (!pkgOrg) continue;
      const existing = byProject.get(p.project_id);
      if (!existing) {
        byProject.set(p.project_id, {
          project_id: p.project_id,
          short_code: p.short_code,
          org_role: pkgOrg.org_role,
        });
      } else if (!existing.org_role && pkgOrg.org_role) {
        existing.org_role = pkgOrg.org_role;
      }
    }
  }

  return [...byProject.values()].sort((a, b) => a.short_code.localeCompare(b.short_code));
}

export function orgProjectsSummary(links: OrgProjectLink[]): string {
  if (links.length === 0) return "—";
  return links.map((l) => l.short_code).join(", ");
}

export function orgActorRolesSummary(
  links: OrgProjectLink[],
  roleLabelFor: (projectId: string, roleKey: string | null) => string,
): string {
  const labels = new Set<string>();
  for (const link of links) {
    if (!link.org_role) continue;
    const label = roleLabelFor(link.project_id, link.org_role);
    if (label) labels.add(label);
  }
  if (labels.size === 0) return "—";
  return [...labels].sort().join(" · ");
}
