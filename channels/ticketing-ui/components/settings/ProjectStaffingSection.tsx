"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  listOfficerRoster,
  type OfficerRosterEntry,
  type OrganizationItem,
  type PackageItem,
  type ProjectItem,
  type ProjectOrgItem,
} from "@/lib/api";
import { officerHasRoleKey, projectStaffingCoverageLine } from "@/lib/officerRosterDisplay";
import { EditOfficerModal } from "@/components/settings/OfficerModals";
import { ProjectOfficerModal } from "@/components/settings/ProjectOfficerModal";

type RoleChoice = { key: string; label: string };

function officerOnProject(
  o: OfficerRosterEntry,
  project: ProjectItem,
  packageIds: Set<string>,
): boolean {
  if (o.project_codes?.includes(project.short_code)) return true;
  return (o.package_ids ?? []).some((id) => packageIds.has(id));
}

function officersForOrgOnProject(
  roster: OfficerRosterEntry[],
  project: ProjectItem,
  packageIds: Set<string>,
  organizationId: string,
): OfficerRosterEntry[] {
  return roster.filter(
    (o) =>
      o.organization_ids.includes(organizationId) &&
      officerOnProject(o, project, packageIds),
  );
}

function officerEmail(o: OfficerRosterEntry): string {
  return o.email ?? o.user_id;
}

function coverageLine(
  o: OfficerRosterEntry,
  project: ProjectItem,
  pkgById: Record<string, PackageItem>,
): string {
  return projectStaffingCoverageLine(o, project, pkgById);
}

/** Coverage tokens for filter matching (project codes, package codes, locations). */
function coverageTokens(
  o: OfficerRosterEntry,
  project: ProjectItem,
  pkgById: Record<string, PackageItem>,
): string[] {
  const tokens: string[] = [];
  (o.project_codes ?? []).forEach((c) => tokens.push(`proj:${c}`));
  (o.package_ids ?? []).forEach((id) => {
    const code = pkgById[id]?.package_code;
    tokens.push(`pkg:${id}`);
    if (code) tokens.push(`pkgcode:${code}`);
  });
  o.location_codes.forEach((c) => tokens.push(`loc:${c}`));
  // Match composite labels used in the Coverage column
  projectStaffingCoverageLine(o, project, pkgById)
    .split(", ")
    .forEach((label) => {
      if (label && label !== "—") tokens.push(`label:${label}`);
    });
  return tokens;
}

type SortColumn = "officer" | "email" | "organization" | "roles" | "coverage";
type SortDir = "asc" | "desc";

function SortableHeader({
  label,
  column,
  active,
  direction,
  onSort,
}: {
  label: string;
  column: SortColumn;
  active: boolean;
  direction: SortDir;
  onSort: (col: SortColumn) => void;
}) {
  return (
    <th className="px-3 py-2 text-xs font-medium text-gray-500">
      <button
        type="button"
        onClick={() => onSort(column)}
        className="inline-flex items-center gap-1 hover:text-gray-800 text-left"
      >
        {label}
        <span className="text-[10px] text-gray-400 tabular-nums">
          {active ? (direction === "asc" ? "▲" : "▼") : "↕"}
        </span>
      </button>
    </th>
  );
}

export function ProjectStaffingSection({
  project,
  projectActors,
  orgs,
  grmRoleChoices,
  packages,
}: {
  project: ProjectItem;
  projectActors: ProjectOrgItem[];
  orgs: OrganizationItem[];
  grmRoleChoices: RoleChoice[];
  packages: PackageItem[];
}) {
  const [roster, setRoster] = useState<OfficerRosterEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [editOfficer, setEditOfficer] = useState<OfficerRosterEntry | null>(null);
  const [addOfficerOrg, setAddOfficerOrg] = useState<{ id: string; name: string } | null>(null);
  const [searchQ, setSearchQ] = useState("");
  const [orgFilter, setOrgFilter] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [coverageFilter, setCoverageFilter] = useState("");
  const [sortColumn, setSortColumn] = useState<SortColumn>("officer");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const packageIds = useMemo(() => new Set(packages.map((p) => p.package_id)), [packages]);
  const pkgById = useMemo(
    () => Object.fromEntries(packages.map((p) => [p.package_id, p])),
    [packages],
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRoster(await listOfficerRoster());
    } catch {
      setRoster([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onProject = useMemo(
    () => roster.filter((o) => officerOnProject(o, project, packageIds)),
    [roster, project, packageIds],
  );

  const orgName = useCallback(
    (id: string) => orgs.find((x) => x.organization_id === id)?.name ?? id,
    [orgs],
  );

  const roleLabel = useCallback(
    (key: string) => grmRoleChoices.find((r) => r.key === key)?.label ?? key,
    [grmRoleChoices],
  );

  const orgFilterOptions = useMemo(() => {
    const ids = new Set<string>();
    onProject.forEach((o) => o.organization_ids.forEach((id) => ids.add(id)));
    return [...ids]
      .map((id) => ({ id, name: orgName(id) }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [onProject, orgName]);

  const roleFilterOptions = useMemo(() => {
    const keys = new Set<string>();
    onProject.forEach((o) => {
      o.role_keys.forEach((k) => keys.add(k));
      (o.scopes ?? []).forEach((s) => keys.add(s.role_key));
    });
    return [...keys]
      .map((key) => ({ key, label: roleLabel(key) }))
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [onProject, roleLabel]);

  const coverageFilterOptions = useMemo(() => {
    const opts: { value: string; label: string; group: string }[] = [];
    opts.push({ value: `proj:${project.short_code}`, label: project.short_code, group: "Project" });
    packages.forEach((pkg) => {
      opts.push({
        value: `pkg:${pkg.package_id}`,
        label: `${project.short_code}/${pkg.package_code}`,
        group: "Package",
      });
    });
    const locs = new Set<string>();
    onProject.forEach((o) => o.location_codes.forEach((c) => locs.add(c)));
    project.location_codes?.forEach((c) => locs.add(c));
    [...locs].sort().forEach((code) => {
      opts.push({ value: `loc:${code}`, label: code, group: "Location" });
    });
    return opts;
  }, [onProject, packages, project.short_code, project.location_codes]);

  const filtered = useMemo(() => {
    const q = searchQ.trim().toLowerCase();
    return onProject.filter((o) => {
      if (orgFilter && !o.organization_ids.includes(orgFilter)) return false;
      if (roleFilter && !officerHasRoleKey(o, roleFilter)) return false;
      if (coverageFilter && !coverageTokens(o, project, pkgById).includes(coverageFilter)) return false;
      if (!q) return true;
      const hay = [
        o.display_name,
        officerEmail(o),
        ...o.organization_ids.map(orgName),
        ...o.role_keys.map(roleLabel),
        coverageLine(o, project, pkgById),
      ]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
  }, [onProject, searchQ, orgFilter, roleFilter, coverageFilter, project, pkgById, orgName, roleLabel]);

  const sorted = useMemo(() => {
    const rows = [...filtered];
    const dir = sortDir === "asc" ? 1 : -1;
    rows.sort((a, b) => {
      let av = "";
      let bv = "";
      switch (sortColumn) {
        case "officer":
          av = a.display_name;
          bv = b.display_name;
          break;
        case "email":
          av = officerEmail(a);
          bv = officerEmail(b);
          break;
        case "organization":
          av = a.organization_ids.map(orgName).join(", ");
          bv = b.organization_ids.map(orgName).join(", ");
          break;
        case "roles":
          av = a.role_keys.map(roleLabel).join(", ");
          bv = b.role_keys.map(roleLabel).join(", ");
          break;
        case "coverage":
          av = coverageLine(a, project, pkgById);
          bv = coverageLine(b, project, pkgById);
          break;
        default:
          break;
      }
      return av.localeCompare(bv, undefined, { sensitivity: "base" }) * dir;
    });
    return rows;
  }, [filtered, sortColumn, sortDir, orgName, roleLabel, project, pkgById]);

  function handleSort(column: SortColumn) {
    if (sortColumn === column) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortColumn(column);
      setSortDir("asc");
    }
  }

  const filtersActive = Boolean(searchQ.trim() || orgFilter || roleFilter || coverageFilter);

  function clearFilters() {
    setSearchQ("");
    setOrgFilter("");
    setRoleFilter("");
    setCoverageFilter("");
  }

  const actorWarnings = useMemo(() => {
    const warnings: string[] = [];
    const seen = new Set<string>();
    for (const po of projectActors) {
      if (!po.organization_id || seen.has(po.organization_id)) continue;
      seen.add(po.organization_id);
      const covered = officersForOrgOnProject(roster, project, packageIds, po.organization_id);
      if (covered.length === 0) {
        const name = orgs.find((x) => x.organization_id === po.organization_id)?.name ?? po.organization_id;
        warnings.push(`No officer scoped for ${name} on this project.`);
      }
    }
    return warnings;
  }, [projectActors, roster, project, packageIds, orgs]);

  return (
    <div className="mt-8 pt-6 border-t border-gray-100 mb-6">
      <div className="flex items-start justify-between gap-4 mb-3">
        <div>
          <h3 className="text-sm font-semibold text-gray-700">Staffing</h3>
          <p className="text-xs text-gray-500 mt-0.5 max-w-2xl">
            Officers whose jurisdiction includes this project or its packages. Add or edit scopes here;
            GRM roles come from the Workflows tab.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            const first = projectActors[0];
            const name = first
              ? orgs.find((o) => o.organization_id === first.organization_id)?.name
              : undefined;
            if (first) {
              setAddOfficerOrg({ id: first.organization_id, name: name ?? first.organization_id });
            }
          }}
          disabled={projectActors.length === 0}
          className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700 disabled:opacity-50 shrink-0"
        >
          + Add officer
        </button>
      </div>

      {actorWarnings.length > 0 && (
        <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 space-y-1">
          {actorWarnings.map((w) => (
            <p key={w}>{w}</p>
          ))}
        </div>
      )}

      {loading ? (
        <p className="text-xs text-gray-400 animate-pulse">Loading officers…</p>
      ) : onProject.length === 0 ? (
        <p className="text-xs text-gray-400 italic">No officers scoped to this project yet.</p>
      ) : (
        <>
          <div className="flex flex-wrap items-end gap-2 mb-3 max-w-4xl">
            <input
              type="text"
              value={searchQ}
              onChange={(e) => setSearchQ(e.target.value)}
              placeholder="Search name or email…"
              className="text-sm border border-gray-300 rounded px-3 py-1.5 w-44 focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
            <select
              value={orgFilter}
              onChange={(e) => setOrgFilter(e.target.value)}
              className="text-sm border border-gray-300 rounded px-2 py-1.5 max-w-[11rem]"
              aria-label="Filter by organization"
            >
              <option value="">All organizations</option>
              {orgFilterOptions.map((o) => (
                <option key={o.id} value={o.id}>{o.name}</option>
              ))}
            </select>
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="text-sm border border-gray-300 rounded px-2 py-1.5 max-w-[12rem]"
              aria-label="Filter by GRM role"
            >
              <option value="">All GRM roles</option>
              {roleFilterOptions.map((r) => (
                <option key={r.key} value={r.key}>{r.label}</option>
              ))}
            </select>
            <select
              value={coverageFilter}
              onChange={(e) => setCoverageFilter(e.target.value)}
              className="text-sm border border-gray-300 rounded px-2 py-1.5 max-w-[12rem]"
              aria-label="Filter by coverage"
            >
              <option value="">All coverage</option>
              {(["Project", "Package", "Location"] as const).map((group) => {
                const items = coverageFilterOptions.filter((c) => c.group === group);
                if (items.length === 0) return null;
                return (
                  <optgroup key={group} label={group}>
                    {items.map((c) => (
                      <option key={c.value} value={c.value}>{c.label}</option>
                    ))}
                  </optgroup>
                );
              })}
            </select>
            {filtersActive && (
              <button
                type="button"
                onClick={clearFilters}
                className="text-sm text-gray-500 hover:text-gray-800 py-1.5"
              >
                Clear filters
              </button>
            )}
            <span className="text-xs text-gray-400 ml-auto py-1.5">
              {sorted.length === onProject.length
                ? `${onProject.length} officer${onProject.length === 1 ? "" : "s"}`
                : `${sorted.length} of ${onProject.length}`}
            </span>
          </div>

          {sorted.length === 0 ? (
            <p className="text-xs text-gray-500 italic mb-2">No officers match the current filters.</p>
          ) : (
        <div className="border border-gray-200 rounded-lg overflow-x-auto max-w-4xl">
          <table className="w-full text-sm min-w-[640px]">
            <thead>
              <tr className="bg-slate-50 text-left border-b border-gray-200">
                <SortableHeader label="Officer" column="officer" active={sortColumn === "officer"} direction={sortDir} onSort={handleSort} />
                <SortableHeader label="Email" column="email" active={sortColumn === "email"} direction={sortDir} onSort={handleSort} />
                <SortableHeader label="Organization" column="organization" active={sortColumn === "organization"} direction={sortDir} onSort={handleSort} />
                <SortableHeader label="GRM roles" column="roles" active={sortColumn === "roles"} direction={sortDir} onSort={handleSort} />
                <SortableHeader label="Coverage" column="coverage" active={sortColumn === "coverage"} direction={sortDir} onSort={handleSort} />
                <th className="px-3 py-2 w-24" />
              </tr>
            </thead>
            <tbody>
              {sorted.map((o) => (
                <tr key={o.user_id} className="border-t border-gray-100 hover:bg-gray-50">
                  <td className="px-3 py-2.5 font-medium text-gray-800">{o.display_name}</td>
                  <td className="px-3 py-2.5 text-xs text-gray-600 font-mono truncate max-w-[12rem]" title={officerEmail(o)}>
                    {officerEmail(o)}
                  </td>
                  <td className="px-3 py-2.5 text-xs text-gray-600">
                    {o.organization_ids.map((id) => orgName(id)).join(", ")}
                  </td>
                  <td className="px-3 py-2.5 text-xs text-gray-600">
                    {o.role_keys.map((k) => roleLabel(k)).join(", ")}
                  </td>
                  <td className="px-3 py-2.5 text-xs text-gray-500 font-mono">{coverageLine(o, project, pkgById)}</td>
                  <td className="px-3 py-2.5 text-right">
                    <button
                      type="button"
                      onClick={() => setEditOfficer(o)}
                      className="text-xs text-blue-600 hover:underline"
                    >
                      Manage
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
          )}
        </>
      )}

      {editOfficer && (
        <EditOfficerModal
          officer={editOfficer}
          roleChoices={grmRoleChoices}
          onClose={() => setEditOfficer(null)}
          onSaved={load}
        />
      )}

      {addOfficerOrg && (
        <ProjectOfficerModal
          project={project}
          organizationId={addOfficerOrg.id}
          organizationName={addOfficerOrg.name}
          roleChoices={grmRoleChoices}
          onClose={() => setAddOfficerOrg(null)}
          onSuccess={load}
        />
      )}
    </div>
  );
}
