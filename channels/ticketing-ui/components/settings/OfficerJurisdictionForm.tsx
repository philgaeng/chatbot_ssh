"use client";

import { useEffect, useMemo, useState } from "react";
import {
  listOrganizations,
  listProjects,
  listPackages,
  type OrganizationItem,
  type ProjectItem,
  type PackageItem,
} from "@/lib/api";
import {
  isDonorAllProjectsOrg,
  packagesForOrganizationOnProject,
  projectsForOrganization,
} from "@/lib/officerJurisdiction";
import { isCountryJurisdictionRole } from "@/lib/jurisdiction";
import { LocationSearch } from "@/components/LocationSearch";

export type JurisdictionFormValue = {
  organization_id: string;
  location_code: string | null;
  project_id: string | null;
  package_id: string | null;
  includes_children: boolean;
};

export type JurisdictionDefaults = {
  organizationId?: string;
  projectId?: string;
  packageId?: string;
  lockOrganization?: boolean;
  lockProject?: boolean;
  /** Project-first: pick project, then orgs linked on that project (setup flow). */
  fieldOrder?: "org-first" | "project-first";
};

export function useOfficerJurisdictionState(
  defaults?: JurisdictionDefaults,
  roleKey = "",
) {
  const projectFirst = defaults?.fieldOrder === "project-first";
  const lockProject = Boolean(defaults?.lockProject);
  const lockOrganization = Boolean(defaults?.lockOrganization);
  const countryRole = isCountryJurisdictionRole(roleKey);
  const [orgId, setOrgId] = useState(defaults?.organizationId ?? "");
  const [selProject, setSelProject] = useState(defaults?.projectId ?? "");
  const [selLoc, setSelLoc] = useState<{ code: string; name: string } | null>(null);
  const [selPkg, setSelPkg] = useState(defaults?.packageId ?? "");
  const [inclChildren, setInclChildren] = useState(false);
  const [orgs, setOrgs] = useState<OrganizationItem[]>([]);
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [packagesByProject, setPackagesByProject] = useState<Record<string, PackageItem[]>>({});
  const [catalogLoading, setCatalogLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setCatalogLoading(true);
    (async () => {
      try {
        const [orgRows, projectRows] = await Promise.all([
          listOrganizations(),
          listProjects(undefined, false),
        ]);
        if (cancelled) return;
        setOrgs(orgRows);
        setProjects(projectRows);
        const pkgEntries = await Promise.all(
          projectRows.map(async (p) => {
            try {
              return [p.project_id, await listPackages(p.project_id)] as const;
            } catch {
              return [p.project_id, []] as const;
            }
          }),
        );
        if (!cancelled) {
          setPackagesByProject(Object.fromEntries(pkgEntries));
        }
      } catch {
        if (!cancelled) {
          setOrgs([]);
          setProjects([]);
          setPackagesByProject({});
        }
      } finally {
        if (!cancelled) setCatalogLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (projectFirst) {
      if (!lockOrganization) setOrgId("");
      setSelPkg("");
    } else if (!lockProject) {
      setSelProject("");
      setSelPkg("");
    } else if (!lockOrganization) {
      setSelPkg("");
    }
  }, [projectFirst, projectFirst ? selProject : orgId, lockProject, lockOrganization]);

  useEffect(() => {
    setSelPkg("");
  }, [selProject]);

  useEffect(() => {
    if (!projectFirst) {
      setSelPkg("");
    }
  }, [projectFirst, orgId]);

  const filteredProjects = useMemo(
    () => projectsForOrganization(orgId, projects, packagesByProject),
    [orgId, projects, packagesByProject],
  );

  const selectedProject = useMemo(
    () => projects.find((p) => p.project_id === selProject),
    [projects, selProject],
  );

  const orgsOnProject = useMemo(() => {
    if (!selectedProject) return [];
    const linked = new Set(selectedProject.organizations.map((o) => o.organization_id));
    return orgs.filter((o) => linked.has(o.organization_id));
  }, [selectedProject, orgs]);

  const filteredPackages = useMemo(
    () =>
      packagesForOrganizationOnProject(
        orgId,
        selectedProject,
        packagesByProject[selProject] ?? [],
      ),
    [orgId, selectedProject, selProject, packagesByProject],
  );

  function reset() {
    setOrgId("");
    setSelProject("");
    setSelLoc(null);
    setSelPkg("");
    setInclChildren(false);
  }

  function hasJurisdiction(): boolean {
    if (countryRole && orgId) return true;
    return Boolean(selProject || selPkg || selLoc);
  }

  function toPayload(roleKey: string): JurisdictionFormValue & { role_key: string } {
    return {
      role_key: roleKey,
      organization_id: orgId,
      location_code: selLoc?.code ?? null,
      project_id: selProject || null,
      package_id: selPkg || null,
      includes_children: inclChildren,
    };
  }

  return {
    orgId,
    setOrgId,
    selProject,
    setSelProject,
    selLoc,
    setSelLoc,
    selPkg,
    setSelPkg,
    inclChildren,
    setInclChildren,
    orgs,
    filteredProjects,
    filteredPackages,
    catalogLoading,
    isDonorOrg: isDonorAllProjectsOrg(orgId),
    lockOrganization,
    lockProject,
    countryRole,
    projectFirst,
    orgsOnProject,
    allProjects: projects,
    reset,
    hasJurisdiction,
    toPayload,
  };
}

type FieldsProps = {
  orgId: string;
  setOrgId: (v: string) => void;
  selProject: string;
  setSelProject: (v: string) => void;
  selLoc: { code: string; name: string } | null;
  setSelLoc: (v: { code: string; name: string } | null) => void;
  selPkg: string;
  setSelPkg: (v: string) => void;
  inclChildren: boolean;
  setInclChildren: (v: boolean) => void;
  orgs: OrganizationItem[];
  filteredProjects: ProjectItem[];
  filteredPackages: PackageItem[];
  catalogLoading?: boolean;
  isDonorOrg?: boolean;
  lockOrganization?: boolean;
  lockProject?: boolean;
  countryRole?: boolean;
  projectFirst?: boolean;
  orgsOnProject?: OrganizationItem[];
  allProjects?: ProjectItem[];
};

export function OfficerJurisdictionFields(props: FieldsProps) {
  const {
    orgId, setOrgId, selProject, setSelProject, selLoc, setSelLoc,
    selPkg, setSelPkg, inclChildren, setInclChildren,
    orgs, filteredProjects, filteredPackages, catalogLoading, isDonorOrg,
    lockOrganization, lockProject, countryRole = false,
    projectFirst = false,
    orgsOnProject = [],
    allProjects = [],
  } = props;

  const projectDisabled =
    Boolean(lockProject) || (!projectFirst && (!orgId || catalogLoading || filteredProjects.length === 0));

  const orgDisabled = Boolean(lockOrganization) || (projectFirst && !selProject);

  const locationAndPackage = (
    <>
      {countryRole && orgId && (
        <p className="text-xs text-blue-700 bg-blue-50 border border-blue-200 rounded px-3 py-2">
          <span className="font-medium">Country-wide role:</span> this officer sees all projects where{" "}
          <span className="font-mono">{orgId}</span> is a project actor. Optionally pick one project below to narrow.
        </p>
      )}
      {isDonorOrg && orgId && !countryRole && (
        <p className="text-xs text-blue-600">ADB may scope officers to any project on the system.</p>
      )}

      {selLoc ? (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="inline-flex items-center gap-1.5 bg-blue-50 text-blue-700 border border-blue-200 rounded px-2 py-1 text-xs">
            {selLoc.name}
            <span className="font-mono text-blue-400">{selLoc.code}</span>
            <button type="button" onClick={() => setSelLoc(null)} className="text-blue-300 hover:text-blue-600">×</button>
          </span>
          <label className="flex items-center gap-1 text-xs text-gray-500 cursor-pointer">
            <input
              type="checkbox"
              checked={inclChildren}
              onChange={(e) => setInclChildren(e.target.checked)}
              className="accent-purple-500"
            />
            include sub-locations
          </label>
        </div>
      ) : (
        <LocationSearch
          placeholder="Location (province, district, …)"
          onSelect={(code, name) => setSelLoc({ code, name })}
        />
      )}

      {selProject && (
        <select
          value={selPkg}
          onChange={(e) => setSelPkg(e.target.value)}
          className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
        >
          <option value="">
            {filteredPackages.length === 0
              ? "No packages for this organization on this project"
              : "Package (all under project)"}
          </option>
          {filteredPackages.map((pkg) => (
            <option key={pkg.package_id} value={pkg.package_id}>
              {pkg.package_code} — {pkg.name}
            </option>
          ))}
        </select>
      )}
    </>
  );

  if (projectFirst) {
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <select
            value={selProject}
            onChange={(e) => setSelProject(e.target.value)}
            disabled={Boolean(lockProject) || catalogLoading}
            className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:bg-gray-50"
          >
            <option value="">
              {catalogLoading ? "Loading projects…" : "Project *"}
            </option>
            {allProjects.map((p) => (
              <option key={p.project_id} value={p.project_id}>{p.short_code} — {p.name}</option>
            ))}
          </select>
          <select
            value={orgId}
            onChange={(e) => setOrgId(e.target.value)}
            required
            disabled={orgDisabled}
            className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:bg-gray-50"
          >
            <option value="">
              {!selProject
                ? "Select project first"
                : orgsOnProject.length === 0
                  ? "No orgs on project — add under Project actors"
                  : "Organization *"}
            </option>
            {orgsOnProject.map((o) => (
              <option key={o.organization_id} value={o.organization_id}>{o.name}</option>
            ))}
          </select>
        </div>
        {selProject && orgsOnProject.length === 0 && (
          <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
            Link organizations to this project first (Projects & packages → Project actors), then invite officers.
          </p>
        )}
        {locationAndPackage}
        <p className="text-xs text-gray-500">
          Flow: <strong>project</strong> → <strong>organization on that project</strong> → optional <strong>package</strong> or <strong>location</strong>.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <select
          value={orgId}
          onChange={(e) => setOrgId(e.target.value)}
          required
          disabled={lockOrganization}
          className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:bg-gray-50"
        >
          <option value="">Organization *</option>
          {orgs.map((o) => (
            <option key={o.organization_id} value={o.organization_id}>{o.name}</option>
          ))}
        </select>
        <select
          value={selProject}
          onChange={(e) => setSelProject(e.target.value)}
          disabled={projectDisabled}
          className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:bg-gray-50"
        >
          <option value="">
            {catalogLoading
              ? "Loading projects…"
              : !orgId
                ? "Select organization first"
                : filteredProjects.length === 0
                  ? "No projects for this organization"
                  : "Project (optional)"}
          </option>
          {filteredProjects.map((p) => (
            <option key={p.project_id} value={p.project_id}>{p.short_code} — {p.name}</option>
          ))}
        </select>
      </div>

      {locationAndPackage}

      <p className="text-xs text-gray-500">
        {countryRole ? (
          <>
            For this role, <strong>organization</strong> is enough for country-wide access. Add a project, package, or
            location only if you want to narrow coverage.
          </>
        ) : (
          <>
            At least one of <strong>project</strong>, <strong>package</strong>, or <strong>location</strong> is required.
            Contractors see projects via their awarded packages; donor orgs may select any project.
          </>
        )}
      </p>
    </div>
  );
}
