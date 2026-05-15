"use client";

import { useEffect, useState } from "react";
import {
  listOrganizations,
  listProjects,
  listPackages,
  type OrganizationItem,
  type ProjectItem,
  type PackageItem,
} from "@/lib/api";
import { LocationSearch } from "@/components/LocationSearch";

export type JurisdictionFormValue = {
  organization_id: string;
  location_code: string | null;
  project_id: string | null;
  package_id: string | null;
  includes_children: boolean;
};

export function useOfficerJurisdictionState() {
  const [orgId, setOrgId] = useState("");
  const [selProject, setSelProject] = useState("");
  const [selLoc, setSelLoc] = useState<{ code: string; name: string } | null>(null);
  const [selPkg, setSelPkg] = useState("");
  const [inclChildren, setInclChildren] = useState(false);
  const [orgs, setOrgs] = useState<OrganizationItem[]>([]);
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [pkgOptions, setPkgOptions] = useState<PackageItem[]>([]);

  useEffect(() => {
    listOrganizations().then(setOrgs).catch(() => {});
    listProjects().then(setProjects).catch(() => {});
  }, []);

  useEffect(() => {
    setSelProject("");
    setSelPkg("");
    setPkgOptions([]);
  }, [orgId]);

  useEffect(() => {
    if (!selProject) {
      setPkgOptions([]);
      setSelPkg("");
      return;
    }
    listPackages(selProject).then(setPkgOptions).catch(() => setPkgOptions([]));
    setSelPkg("");
  }, [selProject]);

  const filteredProjects = orgId
    ? projects.filter((p) => p.organizations.some((o) => o.organization_id === orgId))
    : projects;

  function reset() {
    setOrgId("");
    setSelProject("");
    setSelLoc(null);
    setSelPkg("");
    setInclChildren(false);
  }

  function hasJurisdiction(): boolean {
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
    pkgOptions,
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
  pkgOptions: PackageItem[];
};

export function OfficerJurisdictionFields(props: FieldsProps) {
  const {
    orgId, setOrgId, selProject, setSelProject, selLoc, setSelLoc,
    selPkg, setSelPkg, inclChildren, setInclChildren,
    orgs, filteredProjects, pkgOptions,
  } = props;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <select
          value={orgId}
          onChange={(e) => setOrgId(e.target.value)}
          required
          className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
        >
          <option value="">Organization *</option>
          {orgs.map((o) => (
            <option key={o.organization_id} value={o.organization_id}>{o.name}</option>
          ))}
        </select>
        <select
          value={selProject}
          onChange={(e) => setSelProject(e.target.value)}
          disabled={filteredProjects.length === 0}
          className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:bg-gray-50"
        >
          <option value="">Project (optional)</option>
          {filteredProjects.map((p) => (
            <option key={p.project_id} value={p.project_id}>{p.short_code} — {p.name}</option>
          ))}
        </select>
      </div>

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

      {selProject && pkgOptions.length > 0 && (
        <select
          value={selPkg}
          onChange={(e) => setSelPkg(e.target.value)}
          className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
        >
          <option value="">Package (all under project)</option>
          {pkgOptions.map((pkg) => (
            <option key={pkg.package_id} value={pkg.package_id}>
              {pkg.package_code} — {pkg.name}
            </option>
          ))}
        </select>
      )}

      <p className="text-xs text-gray-500">
        At least one of <strong>project</strong>, <strong>package</strong>, or <strong>location</strong> is required.
        Project scope includes all packages under that project.
      </p>
    </div>
  );
}

