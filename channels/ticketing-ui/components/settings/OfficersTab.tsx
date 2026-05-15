"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  listOfficerRoster,
  deleteOfficer,
  listProjects,
  listPackages,
  type OfficerRosterEntry,
  type ProjectItem,
  type PackageItem,
} from "@/lib/api";
import { InviteOfficerModal, EditOfficerModal } from "@/components/settings/OfficerModals";

type RoleEntry = { key: string; label: string };

function officerRoleLabels(roleKeys: string[], catalog: RoleEntry[]): string {
  return roleKeys.map((k) => catalog.find((x) => x.key === k)?.label ?? k).join(", ");
}

function compactList(items: string[], max = 2): string {
  if (items.length === 0) return "";
  if (items.length <= max) return items.join(", ");
  return `${items.slice(0, max).join(", ")} +${items.length - max}`;
}

function hasJurisdiction(o: OfficerRosterEntry): boolean {
  return (
    (o.project_codes?.length ?? 0) > 0 ||
    (o.package_ids?.length ?? 0) > 0 ||
    o.location_codes.length > 0
  );
}

function coverageSummary(o: OfficerRosterEntry, pkgById: Record<string, PackageItem>): string {
  const parts: string[] = [];
  if (o.project_codes?.length) parts.push(...o.project_codes);
  const pkgCodes = (o.package_ids ?? [])
    .map((id) => pkgById[id]?.package_code)
    .filter((c): c is string => Boolean(c));
  if (pkgCodes.length) parts.push(...pkgCodes);
  if (o.location_codes.length) parts.push(...o.location_codes);
  if (parts.length === 0) return "No area set";
  return compactList(parts, 3) || parts[0];
}

export function OfficersTab({ roleCatalog }: { roleCatalog: RoleEntry[] }) {
  const [officerList, setOfficerList] = useState<OfficerRosterEntry[]>([]);
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [pkgById, setPkgById] = useState<Record<string, PackageItem>>({});
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [showInvite, setShowInvite] = useState(false);
  const [editOfficer, setEditOfficer] = useState<OfficerRosterEntry | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const [searchQ, setSearchQ] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [projectFilter, setProjectFilter] = useState("");
  const [packageFilter, setPackageFilter] = useState("");
  const [locationFilter, setLocationFilter] = useState("");

  const loadRoster = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      setOfficerList(await listOfficerRoster());
    } catch (e: unknown) {
      setLoadError(e instanceof Error ? e.message : "Failed to load officers");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRoster();
    listProjects()
      .then(async (projs) => {
        setProjects(projs);
        const entries = await Promise.all(
          projs.map(async (p) => {
            try {
              return await listPackages(p.project_id);
            } catch {
              return [];
            }
          }),
        );
        const map: Record<string, PackageItem> = {};
        entries.flat().forEach((pkg) => {
          map[pkg.package_id] = pkg;
        });
        setPkgById(map);
      })
      .catch(() => {});
  }, [loadRoster]);

  const packageOptions = useMemo(() => {
    const all = Object.values(pkgById);
    if (!projectFilter) return all;
    return all.filter((p) => p.project_id === projectFilter);
  }, [pkgById, projectFilter]);

  const locationOptions = useMemo(() => {
    const codes = new Set<string>();
    officerList.forEach((o) => o.location_codes.forEach((c) => codes.add(c)));
    return [...codes].sort();
  }, [officerList]);

  const filtered = useMemo(() => {
    const q = searchQ.trim().toLowerCase();
    return officerList.filter((o) => {
      const hay = [
        o.display_name,
        o.user_id,
        o.email ?? "",
        ...o.role_keys,
        ...o.organization_ids,
        ...o.location_codes,
        ...o.project_codes ?? [],
        ...(o.package_ids ?? []).map((id) => pkgById[id]?.package_code ?? id),
        coverageSummary(o, pkgById),
      ]
        .join(" ")
        .toLowerCase();
      const matchesQ = !q || hay.includes(q);
      const matchesR = !roleFilter || o.role_keys.includes(roleFilter);
      const projCode = projects.find((p) => p.project_id === projectFilter)?.short_code;
      const matchesProj = !projectFilter || (o.project_codes ?? []).includes(projCode ?? "");
      const matchesPkg = !packageFilter || (o.package_ids ?? []).includes(packageFilter);
      const matchesLoc = !locationFilter || o.location_codes.includes(locationFilter);
      return matchesQ && matchesR && matchesProj && matchesPkg && matchesLoc;
    });
  }, [officerList, searchQ, roleFilter, projectFilter, packageFilter, locationFilter, projects, pkgById]);

  function handleInviteSuccess(email: string) {
    setShowInvite(false);
    setSuccessMsg(`Invite sent to ${email}.`);
    setTimeout(() => setSuccessMsg(null), 8000);
    loadRoster();
  }

  async function handleDeleteOfficer(o: OfficerRosterEntry) {
    const label = o.email ?? o.display_name ?? o.user_id;
    if (!confirm(`Remove officer ${label} from the system? This cannot be undone.`)) return;
    try {
      await deleteOfficer(o.user_id);
      if (editOfficer?.user_id === o.user_id) setEditOfficer(null);
      setSuccessMsg(`Removed ${label}.`);
      setTimeout(() => setSuccessMsg(null), 6000);
      loadRoster();
    } catch (e: unknown) {
      setLoadError(e instanceof Error ? e.message : "Delete failed");
    }
  }

  return (
    <div>
      {showInvite && (
        <InviteOfficerModal
          roleChoices={roleCatalog}
          onClose={() => setShowInvite(false)}
          onSuccess={handleInviteSuccess}
        />
      )}

      {editOfficer && (
        <EditOfficerModal
          officer={editOfficer}
          roleChoices={roleCatalog}
          onClose={() => setEditOfficer(null)}
          onSaved={loadRoster}
        />
      )}

      {successMsg && (
        <div className="mb-4 px-4 py-2.5 bg-green-50 border border-green-200 rounded text-sm text-green-700">
          ✓ {successMsg}
        </div>
      )}

      <p className="text-sm text-gray-600 mb-3">
        Use <strong>Manage</strong> to edit roles, work areas, and account settings. Filters match project, package, or location on each officer&apos;s record.
      </p>

      <div className="flex flex-wrap items-end gap-2 mb-3">
        <input
          type="text"
          value={searchQ}
          onChange={(e) => setSearchQ(e.target.value)}
          placeholder="Search name or email…"
          className="text-sm border border-gray-300 rounded px-3 py-1.5 w-48 focus:outline-none focus:ring-1 focus:ring-blue-400"
        />
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          className="text-sm border border-gray-300 rounded px-2 py-1.5 max-w-[12rem]"
          aria-label="Filter by role"
        >
          <option value="">All roles</option>
          {roleCatalog.map((r) => (
            <option key={r.key} value={r.key}>{r.label}</option>
          ))}
        </select>
        <select
          value={projectFilter}
          onChange={(e) => {
            setProjectFilter(e.target.value);
            setPackageFilter("");
          }}
          className="text-sm border border-gray-300 rounded px-2 py-1.5 max-w-[10rem]"
          aria-label="Filter by project"
        >
          <option value="">All projects</option>
          {projects.map((p) => (
            <option key={p.project_id} value={p.project_id}>{p.short_code}</option>
          ))}
        </select>
        <select
          value={packageFilter}
          onChange={(e) => setPackageFilter(e.target.value)}
          disabled={packageOptions.length === 0}
          className="text-sm border border-gray-300 rounded px-2 py-1.5 max-w-[12rem] disabled:bg-gray-50"
          aria-label="Filter by package"
        >
          <option value="">All packages</option>
          {packageOptions.map((pkg) => (
            <option key={pkg.package_id} value={pkg.package_id}>{pkg.package_code}</option>
          ))}
        </select>
        <select
          value={locationFilter}
          onChange={(e) => setLocationFilter(e.target.value)}
          className="text-sm border border-gray-300 rounded px-2 py-1.5 max-w-[10rem]"
          aria-label="Filter by location"
        >
          <option value="">All locations</option>
          {locationOptions.map((code) => (
            <option key={code} value={code}>{code}</option>
          ))}
        </select>
        <button type="button" onClick={() => loadRoster()} className="text-sm text-blue-600 hover:underline py-1.5">
          Refresh
        </button>
        <button
          type="button"
          onClick={() => setShowInvite(true)}
          className="ml-auto bg-blue-600 text-white text-sm px-4 py-2 rounded hover:bg-blue-700 font-medium"
        >
          + Invite officer
        </button>
      </div>

      {loading && <p className="text-sm text-gray-400 mb-3">Loading roster…</p>}
      {loadError && <p className="text-sm text-red-600 mb-3">{loadError}</p>}

      {!loading && !loadError && filtered.length === 0 && (
        <p className="text-sm text-gray-500 mb-3">No officers match the current filters.</p>
      )}

      {!loading && !loadError && filtered.length > 0 && (
        <div className="border border-gray-200 rounded-lg overflow-x-auto">
          <table className="w-full text-sm min-w-[720px]">
            <thead>
              <tr className="bg-slate-700 text-slate-100 text-left text-sm">
                <th className="px-3 py-2.5 font-medium">Name</th>
                <th className="px-3 py-2.5 font-medium">Email</th>
                <th className="px-3 py-2.5 font-medium">Role</th>
                <th className="px-3 py-2.5 font-medium">Area covered</th>
                <th className="px-3 py-2.5 font-medium w-24">Status</th>
                <th className="px-3 py-2.5 font-medium w-40">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((o) => {
                const coverage = coverageSummary(o, pkgById);
                const missingArea = !hasJurisdiction(o);
                const status = o.onboarding_status ?? "active";
                return (
                  <tr
                    key={o.user_id}
                    className={`border-t border-gray-100 hover:bg-gray-50 align-top ${missingArea ? "bg-amber-50/60" : ""}`}
                  >
                    <td className="px-3 py-2.5 font-medium text-gray-800">
                      {o.display_name}
                    </td>
                    <td className="px-3 py-2.5 text-gray-600 truncate max-w-[14rem]" title={o.email ?? o.user_id}>
                      {o.email ?? o.user_id}
                    </td>
                    <td className="px-3 py-2.5 text-gray-700 max-w-[12rem]" title={officerRoleLabels(o.role_keys, roleCatalog)}>
                      {officerRoleLabels(o.role_keys, roleCatalog)}
                    </td>
                    <td className="px-3 py-2.5">
                      <span
                        className={missingArea ? "text-amber-800 font-medium" : "text-gray-700"}
                        title={missingArea ? "Open Manage to set project, package, or location" : coverage}
                      >
                        {coverage}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      <span
                        className={
                          status === "invited"
                            ? "text-xs text-amber-800 bg-amber-100 px-2 py-0.5 rounded"
                            : "text-xs text-green-800 bg-green-100 px-2 py-0.5 rounded"
                        }
                      >
                        {status === "invited" ? "Invited" : "Active"}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 whitespace-nowrap">
                      <button
                        type="button"
                        onClick={() => setEditOfficer(o)}
                        className="text-sm text-blue-600 hover:underline font-medium mr-3"
                      >
                        Manage
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDeleteOfficer(o)}
                        className="text-sm text-red-600 hover:underline"
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
