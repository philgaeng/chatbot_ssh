"use client";

import { useEffect, useMemo, useState } from "react";
import {
  listOrganizations,
  listProjects,
  listPackages,
  getOrgRoles,
  type OrganizationItem,
  type OrgRole,
  type ProjectItem,
  type PackageItem,
} from "@/lib/api";
import {
  DEFAULT_ROUTING_ORG_ROLE,
  collectOrganizationScopeAssignments,
  isDonorAllProjectsOrg,
  organizationsForScopeFilter,
  organizationsOnProject,
  organizationsOnProjectForScope,
  orgRoleKeysForOrganization,
  packagesForOrganizationOnProject,
  projectsForOrganization,
  routingOrganizationId,
  scopeOptionsFromAssignments,
  type OrgScopeAssignment,
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
  const [selLocs, setSelLocs] = useState<{ code: string; name: string }[]>([]);
  const [selPkg, setSelPkg] = useState(defaults?.packageId ?? "");
  const [inclChildren, setInclChildren] = useState(false);
  const [orgs, setOrgs] = useState<OrganizationItem[]>([]);
  const [orgRoles, setOrgRoles] = useState<OrgRole[]>([]);
  const [scopeFilter, setScopeFilter] = useState("");
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [packagesByProject, setPackagesByProject] = useState<Record<string, PackageItem[]>>({});
  const [catalogLoading, setCatalogLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setCatalogLoading(true);
    (async () => {
      try {
        const [orgRows, projectRows, roleRows] = await Promise.all([
          listOrganizations(),
          listProjects(undefined, false),
          getOrgRoles().catch(() => [] as OrgRole[]),
        ]);
        if (cancelled) return;
        setOrgs(orgRows);
        setOrgRoles(roleRows);
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
    if (defaults?.organizationId) {
      setOrgId(defaults.organizationId);
    }
  }, [defaults?.organizationId]);

  useEffect(() => {
    if (projectFirst && !lockProject && !selProject && projects.length === 1) {
      setSelProject(projects[0].project_id);
    }
  }, [projectFirst, lockProject, selProject, projects]);

  useEffect(() => {
    if (projectFirst) {
      if (!lockOrganization) {
        if (!selProject) {
          setOrgId("");
        } else {
          const project = projects.find((p) => p.project_id === selProject);
          const routed = routingOrganizationId(project);
          if (!routed) {
            setOrgId("");
          } else if (scopeFilter) {
            const pkgs = packagesByProject[selProject] ?? [];
            const allowed = organizationsOnProjectForScope(project, orgs, pkgs, scopeFilter);
            setOrgId(allowed.some((o) => o.organization_id === routed) ? routed : "");
          } else {
            setOrgId(routed);
          }
        }
      }
      setSelPkg("");
    } else if (!lockProject) {
      setSelProject("");
      setSelPkg("");
    } else if (!lockOrganization) {
      setSelPkg("");
    }
  }, [projectFirst, projectFirst ? selProject : orgId, lockProject, lockOrganization, projects, scopeFilter, orgs, packagesByProject]);

  useEffect(() => {
    setSelPkg("");
    setSelLocs([]);
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

  const scopeAssignments = useMemo(
    () => collectOrganizationScopeAssignments(projects, packagesByProject),
    [projects, packagesByProject],
  );

  const scopeOptions = useMemo(
    () =>
      scopeOptionsFromAssignments(
        scopeAssignments,
        orgRoles,
        projectFirst ? selProject || null : null,
      ),
    [scopeAssignments, orgRoles, projectFirst, selProject],
  );

  const orgsOnProject = useMemo(
    () => organizationsOnProject(selectedProject, orgs, packagesByProject[selProject] ?? []),
    [selectedProject, orgs, selProject, packagesByProject],
  );

  const orgsOnProjectFiltered = useMemo(
    () =>
      organizationsOnProjectForScope(
        selectedProject,
        orgs,
        packagesByProject[selProject] ?? [],
        scopeFilter,
      ),
    [selectedProject, orgs, selProject, packagesByProject, scopeFilter],
  );

  const orgsFilteredByScope = useMemo(
    () => organizationsForScopeFilter(orgs, scopeAssignments, scopeFilter),
    [orgs, scopeAssignments, scopeFilter],
  );

  useEffect(() => {
    if (scopeFilter && orgId) {
      const allowed = projectFirst
        ? orgsOnProjectFiltered.some((o) => o.organization_id === orgId)
        : orgsFilteredByScope.some((o) => o.organization_id === orgId);
      if (!allowed) setOrgId("");
    }
  }, [scopeFilter, orgId, projectFirst, orgsOnProjectFiltered, orgsFilteredByScope]);

  useEffect(() => {
    setScopeFilter("");
  }, [projectFirst ? selProject : orgId]);

  const filteredPackages = useMemo(
    () =>
      packagesForOrganizationOnProject(
        orgId,
        selectedProject,
        packagesByProject[selProject] ?? [],
      ),
    [orgId, selectedProject, selProject, packagesByProject],
  );

  const singlePackage = filteredPackages.length === 1 ? filteredPackages[0] : null;

  useEffect(() => {
    if (singlePackage) {
      setSelPkg(singlePackage.package_id);
    }
  }, [singlePackage?.package_id]);

  function reset() {
    setOrgId("");
    setSelProject("");
    setSelLocs([]);
    setSelPkg("");
    setInclChildren(false);
  }

  function addLocation(code: string, name: string) {
    setSelLocs((prev) => (prev.some((l) => l.code === code) ? prev : [...prev, { code, name }]));
  }

  function removeLocation(code: string) {
    setSelLocs((prev) => prev.filter((l) => l.code !== code));
  }

  function hasJurisdiction(): boolean {
    return toPayloads("").length > 0;
  }

  function toPayloads(roleKey: string): (JurisdictionFormValue & { role_key: string })[] {
    if (!orgId) return [];
    const base = {
      organization_id: orgId,
      project_id: selProject || null,
      package_id: selPkg || null,
      includes_children: inclChildren,
    };
    if (selLocs.length > 0) {
      return selLocs.map((loc) => ({
        role_key: roleKey,
        ...base,
        location_code: loc.code,
      }));
    }
    if (countryRole || selProject || selPkg) {
      return [{ role_key: roleKey, ...base, location_code: null }];
    }
    return [];
  }

  /** @deprecated use toPayloads — returns first payload for single-scope callers */
  function toPayload(roleKey: string): JurisdictionFormValue & { role_key: string } {
    const rows = toPayloads(roleKey);
    return (
      rows[0] ?? {
        role_key: roleKey,
        organization_id: orgId,
        location_code: null,
        project_id: null,
        package_id: null,
        includes_children: inclChildren,
      }
    );
  }

  return {
    orgId,
    setOrgId,
    selProject,
    setSelProject,
    selLocs,
    setSelLocs,
    addLocation,
    removeLocation,
    selPkg,
    setSelPkg,
    inclChildren,
    setInclChildren,
    orgs,
    orgsFilteredByScope,
    filteredProjects,
    filteredPackages,
    catalogLoading,
    scopeFilter,
    setScopeFilter,
    scopeOptions,
    scopeAssignments,
    isDonorOrg: isDonorAllProjectsOrg(orgId),
    lockOrganization,
    lockProject,
    countryRole,
    projectFirst,
    orgsOnProject,
    orgsOnProjectFiltered,
    routingOrgId: routingOrganizationId(selectedProject),
    allProjects: projects,
    reset,
    hasJurisdiction,
    toPayload,
    toPayloads,
    singlePackage,
  };
}

type FieldsProps = {
  orgId: string;
  setOrgId: (v: string) => void;
  selProject: string;
  setSelProject: (v: string) => void;
  selLocs: { code: string; name: string }[];
  addLocation: (code: string, name: string) => void;
  removeLocation: (code: string) => void;
  singlePackage?: PackageItem | null;
  selPkg: string;
  setSelPkg: (v: string) => void;
  inclChildren: boolean;
  setInclChildren: (v: boolean) => void;
  orgs: OrganizationItem[];
  orgsFilteredByScope?: OrganizationItem[];
  filteredProjects: ProjectItem[];
  filteredPackages: PackageItem[];
  catalogLoading?: boolean;
  scopeFilter?: string;
  setScopeFilter?: (v: string) => void;
  scopeOptions?: { key: string; label: string }[];
  scopeAssignments?: OrgScopeAssignment[];
  isDonorOrg?: boolean;
  lockOrganization?: boolean;
  lockProject?: boolean;
  countryRole?: boolean;
  projectFirst?: boolean;
  orgsOnProject?: OrganizationItem[];
  orgsOnProjectFiltered?: OrganizationItem[];
  routingOrgId?: string | null;
  allProjects?: ProjectItem[];
};

function orgPickerLabel(
  org: OrganizationItem,
  scopeFilter: string,
  scopeAssignments: OrgScopeAssignment[],
  projectId?: string | null,
): string {
  if (scopeFilter) return org.name;
  const roles = orgRoleKeysForOrganization(org.organization_id, scopeAssignments, projectId);
  if (roles.length === 0) return org.name;
  return `${org.name} (${roles.join(", ")})`;
}

function OrgScopeFilterSelect({
  value,
  onChange,
  options,
  disabled,
  hint,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { key: string; label: string }[];
  disabled?: boolean;
  hint?: string;
}) {
  return (
    <div>
      <label className="text-xs font-medium text-gray-500 block mb-1">Filter by scope</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled || options.length === 0}
        className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:bg-gray-50"
      >
        <option value="">
          {options.length === 0 ? "No scoped organizations yet" : "All scopes"}
        </option>
        {options.map((opt) => (
          <option key={opt.key} value={opt.key}>
            {opt.label}
          </option>
        ))}
      </select>
      {hint && <p className="text-xs text-gray-500 mt-1">{hint}</p>}
    </div>
  );
}

export function OfficerJurisdictionFields(props: FieldsProps) {
  const {
    orgId, setOrgId, selProject, setSelProject, selLocs, addLocation, removeLocation,
    selPkg, setSelPkg, inclChildren, setInclChildren,
    orgs, orgsFilteredByScope = orgs, filteredProjects, filteredPackages, catalogLoading, isDonorOrg,
    scopeFilter = "", setScopeFilter, scopeOptions = [], scopeAssignments = [],
    lockOrganization, lockProject, countryRole = false,
    projectFirst = false,
    orgsOnProject = [],
    orgsOnProjectFiltered = orgsOnProject,
    routingOrgId = null,
    allProjects = [],
    singlePackage = null,
  } = props;

  const lockedOrgName = orgs.find((o) => o.organization_id === orgId)?.name ?? orgId;

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

      {selLocs.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          {selLocs.map((loc) => (
            <span
              key={loc.code}
              className="inline-flex items-center gap-1.5 bg-blue-50 text-blue-700 border border-blue-200 rounded px-2 py-1 text-xs"
            >
              {loc.name}
              <span className="font-mono text-blue-400">{loc.code}</span>
              <button
                type="button"
                onClick={() => removeLocation(loc.code)}
                className="text-blue-300 hover:text-blue-600 leading-none"
                aria-label={`Remove ${loc.name}`}
              >
                ×
              </button>
            </span>
          ))}
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
      )}

      <LocationSearch
        placeholder={
          selLocs.length > 0
            ? "Add another location…"
            : "Location (province, district, …)"
        }
        onSelect={(code, name) => addLocation(code, name)}
      />

      {selProject && singlePackage ? (
        <p className="text-xs text-gray-700 bg-gray-50 border border-gray-200 rounded px-3 py-2">
          <span className="font-medium">Package:</span> {singlePackage.package_code} — {singlePackage.name}
          <span className="text-gray-400 ml-1">(only package for this organization)</span>
        </p>
      ) : selProject ? (
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
      ) : null}
    </>
  );

  if (projectFirst) {
    const orgPickerList = scopeFilter ? orgsOnProjectFiltered : orgsOnProject;
    return (
      <div className="space-y-3">
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
        {selProject && setScopeFilter && (
          <OrgScopeFilterSelect
            value={scopeFilter}
            onChange={setScopeFilter}
            options={scopeOptions}
            disabled={catalogLoading}
            hint="Organizations appear under each scope they hold on this project (project actor or package role)."
          />
        )}
        <div className="flex items-center gap-2">
          {lockOrganization && orgId ? (
            <div className="w-full text-sm border border-gray-200 rounded px-3 py-1.5 bg-gray-50 text-gray-700">
              {lockedOrgName}
            </div>
          ) : (
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
                  : orgPickerList.length === 0
                    ? scopeFilter
                      ? "No organizations with this scope on project"
                      : "No orgs on project — add under Project actors or packages"
                    : "Organization *"}
              </option>
              {orgPickerList.map((o) => (
                <option key={o.organization_id} value={o.organization_id}>
                  {orgPickerLabel(o, scopeFilter, scopeAssignments, selProject)}
                </option>
              ))}
            </select>
          )}
        </div>
        {selProject && orgPickerList.length === 0 && (
          <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
            Link organizations to this project first (Projects & packages → Project actors or package contractors), then invite officers.
          </p>
        )}
        {selProject && routingOrgId && orgId === routingOrgId && (
          <p className="text-xs text-gray-600 bg-gray-50 border border-gray-200 rounded px-3 py-2">
            Organization defaults to the project&apos;s{" "}
            <span className="font-mono">{DEFAULT_ROUTING_ORG_ROLE.replace(/_/g, " ")}</span>{" "}
            (same org used for ticket routing). Change only if this officer works for another project actor.
          </p>
        )}
        {locationAndPackage}
        <p className="text-xs text-gray-500">
          Flow: <strong>project</strong> → <strong>organization on that project</strong> → optional <strong>package</strong> or <strong>location</strong>.
        </p>
      </div>
    );
  }

  const orgPickerList = scopeFilter ? orgsFilteredByScope : orgs;

  return (
    <div className="space-y-3">
      {setScopeFilter && (
        <OrgScopeFilterSelect
          value={scopeFilter}
          onChange={setScopeFilter}
          options={scopeOptions}
          disabled={catalogLoading}
          hint="Pick a project role (e.g. implementing agency, contractor) to narrow the organization list."
        />
      )}
      <div className="flex items-center gap-2">
        {lockOrganization && orgId ? (
          <div className="w-full text-sm border border-gray-200 rounded px-3 py-1.5 bg-gray-50 text-gray-700">
            {lockedOrgName}
          </div>
        ) : (
          <select
            value={orgId}
            onChange={(e) => setOrgId(e.target.value)}
            required
            disabled={lockOrganization}
            className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:bg-gray-50"
          >
            <option value="">
              {scopeFilter && orgPickerList.length === 0
                ? "No organizations with this scope"
                : "Organization *"}
            </option>
            {orgPickerList.map((o) => (
              <option key={o.organization_id} value={o.organization_id}>
                {orgPickerLabel(o, scopeFilter, scopeAssignments)}
              </option>
            ))}
          </select>
        )}
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
