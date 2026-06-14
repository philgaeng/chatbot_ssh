"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  listOfficerRoster,
  deleteOfficer,
  resendOfficerInvite,
  listProjects,
  listPackages,
  type OfficerRosterEntry,
  type ProjectItem,
  type PackageItem,
} from "@/lib/api";
import {
  officerHasRoleKey,
  officerHasScopeJurisdiction,
  officerLocationsSummary,
  roleProjectsLines,
} from "@/lib/officerRosterDisplay";
import { InviteOfficerModal, EditOfficerModal } from "@/components/settings/OfficerModals";

type RoleEntry = { key: string; label: string };

export function OfficersTab({
  roleCatalog,
  allowGlobalInvite = true,
}: {
  roleCatalog: RoleEntry[];
  /** Local admins invite from Projects → Project actors / Staffing only. */
  allowGlobalInvite?: boolean;
}) {
  const [officerList, setOfficerList] = useState<OfficerRosterEntry[]>([]);
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [pkgById, setPkgById] = useState<Record<string, PackageItem>>({});
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [showInvite, setShowInvite] = useState(false);
  const [editOfficer, setEditOfficer] = useState<OfficerRosterEntry | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [resendingId, setResendingId] = useState<string | null>(null);

  const [searchQ, setSearchQ] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [projectFilter, setProjectFilter] = useState("");
  const [packageFilter, setPackageFilter] = useState("");
  const [locationFilter, setLocationFilter] = useState("");

  const projectById = useMemo(
    () => Object.fromEntries(projects.map((p) => [p.project_id, p])),
    [projects],
  );

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
    listProjects(undefined, false)
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
    officerList.forEach((o) => {
      (o.scopes ?? []).forEach((s) => {
        if (s.location_code) codes.add(s.location_code);
      });
      o.location_codes.forEach((c) => codes.add(c));
    });
    return [...codes].sort();
  }, [officerList]);

  const filtered = useMemo(() => {
    const q = searchQ.trim().toLowerCase();
    return officerList.filter((o) => {
      const roleLines = roleProjectsLines(o, roleCatalog, projectById);
      const locSummary = officerLocationsSummary(o);
      const hay = [
        o.display_name,
        o.user_id,
        o.email ?? "",
        o.phone_number ?? "",
        ...o.role_keys,
        ...(o.scopes ?? []).map((s) => s.role_key),
        ...o.organization_ids,
        ...o.location_codes,
        ...(o.project_codes ?? []),
        ...(o.package_ids ?? []).map((id) => pkgById[id]?.package_code ?? id),
        ...roleLines,
        locSummary,
      ]
        .join(" ")
        .toLowerCase();
      const matchesQ = !q || hay.includes(q);
      const matchesR = officerHasRoleKey(o, roleFilter);
      const projCode = projects.find((p) => p.project_id === projectFilter)?.short_code;
      const matchesProj =
        !projectFilter ||
        (o.project_codes ?? []).includes(projCode ?? "") ||
        (o.scopes ?? []).some(
          (s) =>
            s.project_code === projCode ||
            (s.project_id && projectById[s.project_id]?.short_code === projCode),
        );
      const matchesPkg = !packageFilter || (o.package_ids ?? []).includes(packageFilter);
      const scopeLocs = (o.scopes ?? []).map((s) => s.location_code).filter(Boolean) as string[];
      const locs = scopeLocs.length > 0 ? scopeLocs : o.location_codes;
      const matchesLoc = !locationFilter || locs.includes(locationFilter);
      return matchesQ && matchesR && matchesProj && matchesPkg && matchesLoc;
    });
  }, [
    officerList,
    searchQ,
    roleFilter,
    projectFilter,
    packageFilter,
    locationFilter,
    projects,
    pkgById,
    roleCatalog,
    projectById,
  ]);

  function handleInviteSuccess(email: string) {
    setShowInvite(false);
    setSuccessMsg(`Invite sent to ${email}.`);
    setTimeout(() => setSuccessMsg(null), 8000);
    loadRoster();
  }

  async function handleResendInvite(o: OfficerRosterEntry) {
    const label = o.email ?? o.user_id;
    setResendingId(o.user_id);
    setLoadError(null);
    try {
      const result = await resendOfficerInvite(o.user_id);
      setSuccessMsg(result.message || `Invite resent to ${label}.`);
      setTimeout(() => setSuccessMsg(null), 8000);
    } catch (e: unknown) {
      setLoadError(e instanceof Error ? e.message : "Resend invite failed");
    } finally {
      setResendingId(null);
    }
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
        Use <strong>Manage</strong> to edit roles, work areas, and account settings. Filters match project, package, or location on each officer&apos;s scopes.
      </p>

      {!allowGlobalInvite && (
        <div className="mb-4 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
          <p className="font-medium mb-1">Invite officers from the project</p>
          <p className="text-blue-800 text-xs">
            Open <strong>Projects & packages</strong> → your project → add organizations under <strong>Project actors</strong>,
            then use <strong>Add officer</strong> on a row or the <strong>Staffing</strong> section.
            Organizations must be on the project before officers can be scoped there.
          </p>
        </div>
      )}

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
        {allowGlobalInvite && (
          <button
            type="button"
            onClick={() => setShowInvite(true)}
            className="ml-auto bg-blue-600 text-white text-sm px-4 py-2 rounded hover:bg-blue-700 font-medium"
          >
            + Invite officer
          </button>
        )}
      </div>

      {loading && <p className="text-sm text-gray-400 mb-3">Loading roster…</p>}
      {loadError && <p className="text-sm text-red-600 mb-3">{loadError}</p>}

      {!loading && !loadError && filtered.length === 0 && (
        <p className="text-sm text-gray-500 mb-3">No officers match the current filters.</p>
      )}

      {!loading && !loadError && filtered.length > 0 && (
        <div className="border border-gray-200 rounded-lg overflow-x-auto">
          <table className="w-full text-sm min-w-[880px]">
            <thead>
              <tr className="bg-slate-700 text-slate-100 text-left text-sm">
                <th className="px-3 py-2.5 font-medium">Name</th>
                <th className="px-3 py-2.5 font-medium">Email</th>
                <th className="px-3 py-2.5 font-medium">Phone</th>
                <th className="px-3 py-2.5 font-medium">Role: projects</th>
                <th className="px-3 py-2.5 font-medium">Area covered</th>
                <th className="px-3 py-2.5 font-medium w-24">Status</th>
                <th className="px-3 py-2.5 font-medium w-40">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((o) => {
                const roleLines = roleProjectsLines(o, roleCatalog, projectById);
                const locations = officerLocationsSummary(o);
                const missingArea = !officerHasScopeJurisdiction(o);
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
                    <td className="px-3 py-2.5 text-gray-600 font-mono text-xs">
                      {o.phone_number ?? "—"}
                    </td>
                    <td className="px-3 py-2.5 text-gray-700 max-w-[16rem]">
                      <ul className="space-y-0.5">
                        {roleLines.map((line) => (
                          <li key={line} className="text-xs leading-snug" title={line}>
                            {line}
                          </li>
                        ))}
                      </ul>
                    </td>
                    <td className="px-3 py-2.5">
                      <span
                        className={missingArea ? "text-amber-800 font-medium text-xs" : "text-gray-700 text-xs font-mono"}
                        title={missingArea ? "Open Manage to set project, package, or location" : locations}
                      >
                        {locations}
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
                      {status === "invited" && (
                        <button
                          type="button"
                          onClick={() => handleResendInvite(o)}
                          disabled={resendingId === o.user_id}
                          className="text-sm text-amber-800 hover:underline font-medium mr-3 disabled:opacity-50"
                          title="Send a new setup email (12-hour link; check spam)"
                        >
                          {resendingId === o.user_id ? "Sending…" : "Resend invite"}
                        </button>
                      )}
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
