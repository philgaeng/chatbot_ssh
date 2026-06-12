"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  deleteOrganization,
  getProjectActorRoles,
  listCountries,
  listOrganizations,
  listPackages,
  listProjects,
  type CountryItem,
  type OrganizationItem,
  type OrgRole,
  type PackageItem,
  type ProjectItem,
} from "@/lib/api";
import { OrgCreateModal } from "@/components/settings/OrgCreateModal";
import {
  orgProjectLinks,
  orgProjectsSummary,
} from "@/lib/orgRoster";

const ORG_ROLE_COLORS: Record<string, string> = {
  project_owner: "bg-slate-100 text-slate-700 border-slate-200",
  donor: "bg-blue-100 text-blue-700 border-blue-200",
  executing_agency: "bg-purple-100 text-purple-700 border-purple-200",
  implementing_agency: "bg-indigo-100 text-indigo-700 border-indigo-200",
  main_contractor: "bg-orange-100 text-orange-700 border-orange-200",
  subcontractor_t1: "bg-amber-100 text-amber-700 border-amber-200",
  subcontractor_t2: "bg-amber-100 text-amber-600 border-amber-200",
  supervision_consultant: "bg-teal-100 text-teal-700 border-teal-200",
  specialized_consultant: "bg-green-100 text-green-700 border-green-200",
};

export function OrganizationsTab({
  onEdit,
  onNavigateToProject,
}: {
  onEdit: (org: OrganizationItem) => void;
  onNavigateToProject: (projectId: string) => void;
}) {
  const [orgs, setOrgs] = useState<OrganizationItem[]>([]);
  const [countries, setCountries] = useState<CountryItem[]>([]);
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [packagesByProject, setPackagesByProject] = useState<Record<string, PackageItem[]>>({});
  const [actorRolesByProject, setActorRolesByProject] = useState<Record<string, OrgRole[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);

  const [searchQ, setSearchQ] = useState("");
  const [countryFilter, setCountryFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [projectFilter, setProjectFilter] = useState("");
  const [actorRoleFilter, setActorRoleFilter] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [o, c, p] = await Promise.all([
        listOrganizations(),
        listCountries(),
        listProjects(undefined, false),
      ]);
      setOrgs(o);
      setCountries(c);
      setProjects(p);

      const pkgEntries = await Promise.all(
        p.map(async (proj) => {
          try {
            return [proj.project_id, await listPackages(proj.project_id)] as const;
          } catch {
            return [proj.project_id, []] as const;
          }
        }),
      );
      setPackagesByProject(Object.fromEntries(pkgEntries));

      const roleEntries = await Promise.all(
        p.map(async (proj) => {
          try {
            return [proj.project_id, await getProjectActorRoles(proj.project_id)] as const;
          } catch {
            return [proj.project_id, []] as const;
          }
        }),
      );
      setActorRolesByProject(Object.fromEntries(roleEntries));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load organizations");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const orgLinksMap = useMemo(() => {
    const map = new Map<string, ReturnType<typeof orgProjectLinks>>();
    for (const org of orgs) {
      map.set(org.organization_id, orgProjectLinks(org.organization_id, projects, packagesByProject));
    }
    return map;
  }, [orgs, projects, packagesByProject]);

  const roleLabelFor = useMemo(() => {
    return (projectId: string, roleKey: string | null) => {
      if (!roleKey) return "";
      const vocab = actorRolesByProject[projectId] ?? [];
      return vocab.find((r) => r.key === roleKey)?.label ?? roleKey.replace(/_/g, " ");
    };
  }, [actorRolesByProject]);

  const actorRoleOptions = useMemo(() => {
    const seen = new Map<string, string>();
    for (const links of orgLinksMap.values()) {
      for (const link of links) {
        if (!link.org_role || seen.has(link.org_role)) continue;
        seen.set(link.org_role, roleLabelFor(link.project_id, link.org_role));
      }
    }
    return [...seen.entries()]
      .sort((a, b) => a[1].localeCompare(b[1]))
      .map(([key, label]) => ({ key, label }));
  }, [orgLinksMap, roleLabelFor]);

  const filtered = useMemo(() => {
    const q = searchQ.trim().toLowerCase();
    return orgs.filter((o) => {
      const links = orgLinksMap.get(o.organization_id) ?? [];
      const hay = [o.organization_id, o.name, o.country_code ?? "", orgProjectsSummary(links)]
        .join(" ")
        .toLowerCase();
      const matchesQ = !q || hay.includes(q);
      const matchesCountry = !countryFilter || o.country_code === countryFilter;
      const matchesStatus =
        !statusFilter ||
        (statusFilter === "active" && o.is_active) ||
        (statusFilter === "inactive" && !o.is_active);
      const matchesProject =
        !projectFilter || links.some((l) => l.project_id === projectFilter);
      const matchesActorRole =
        !actorRoleFilter || links.some((l) => l.org_role === actorRoleFilter);
      return matchesQ && matchesCountry && matchesStatus && matchesProject && matchesActorRole;
    });
  }, [orgs, orgLinksMap, searchQ, countryFilter, statusFilter, projectFilter, actorRoleFilter]);

  async function handleRemoveOrg(o: OrganizationItem) {
    if (!confirm(`Remove organization "${o.name}" (${o.organization_id})? This cannot be undone.`)) {
      return;
    }
    try {
      await deleteOrganization(o.organization_id);
      setOrgs((prev) => prev.filter((x) => x.organization_id !== o.organization_id));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Remove failed");
    }
  }

  return (
    <div>
      <div className="flex flex-wrap items-end gap-2 mb-4">
        <input
          type="text"
          value={searchQ}
          onChange={(e) => setSearchQ(e.target.value)}
          placeholder="Search name or ID…"
          className="text-sm border border-gray-300 rounded px-3 py-1.5 w-48 focus:outline-none focus:ring-1 focus:ring-blue-400"
        />
        <select
          value={countryFilter}
          onChange={(e) => setCountryFilter(e.target.value)}
          className="text-sm border border-gray-300 rounded px-2 py-1.5 max-w-[8rem]"
          aria-label="Filter by country"
        >
          <option value="">All countries</option>
          {countries.map((c) => (
            <option key={c.country_code} value={c.country_code}>
              {c.country_code}
            </option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="text-sm border border-gray-300 rounded px-2 py-1.5 max-w-[9rem]"
          aria-label="Filter by status"
        >
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
        <select
          value={projectFilter}
          onChange={(e) => setProjectFilter(e.target.value)}
          className="text-sm border border-gray-300 rounded px-2 py-1.5 max-w-[10rem]"
          aria-label="Filter by project"
        >
          <option value="">All projects</option>
          {projects.map((p) => (
            <option key={p.project_id} value={p.project_id}>
              {p.short_code}
            </option>
          ))}
        </select>
        <select
          value={actorRoleFilter}
          onChange={(e) => setActorRoleFilter(e.target.value)}
          className="text-sm border border-gray-300 rounded px-2 py-1.5 max-w-[12rem]"
          aria-label="Filter by actor role"
        >
          <option value="">All actor roles</option>
          {actorRoleOptions.map((r) => (
            <option key={r.key} value={r.key}>
              {r.label}
            </option>
          ))}
        </select>
        <button type="button" onClick={() => void load()} className="text-sm text-blue-600 hover:underline py-1.5">
          Refresh
        </button>
        <button
          type="button"
          onClick={() => setShowCreate(true)}
          className="ml-auto bg-blue-600 text-white text-sm px-4 py-1.5 rounded font-medium hover:bg-blue-700 transition"
        >
          + Add Organization
        </button>
      </div>

      {showCreate && (
        <OrgCreateModal
          countries={countries}
          existingOrganizationIds={new Set(orgs.map((o) => o.organization_id))}
          onCreated={(org) => {
            setShowCreate(false);
            setOrgs((prev) => [...prev, org]);
            onEdit(org);
          }}
          onClose={() => setShowCreate(false)}
        />
      )}

      <p className="text-sm text-gray-500 mb-3">
        {filtered.length} of {orgs.length} organization{orgs.length !== 1 ? "s" : ""}
      </p>

      {loading && <p className="text-sm text-gray-400 animate-pulse">Loading…</p>}
      {error && <p className="text-sm text-red-500 mb-3">{error}</p>}

      {!loading && !error && (
        <div className="border border-gray-200 rounded-lg overflow-x-auto">
          <table className="w-full text-sm min-w-[900px]">
            <thead>
              <tr className="bg-slate-700 text-slate-100 text-left">
                <th className="px-4 py-2.5 font-medium">ID</th>
                <th className="px-4 py-2.5 font-medium">Name</th>
                <th className="px-4 py-2.5 font-medium">Country</th>
                <th className="px-4 py-2.5 font-medium">Projects</th>
                <th className="px-4 py-2.5 font-medium">Actor role</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-sm text-gray-400">
                    No organizations match the current filters.
                  </td>
                </tr>
              )}
              {filtered.map((o) => {
                const links = orgLinksMap.get(o.organization_id) ?? [];
                return (
                  <tr key={o.organization_id} className="border-t border-gray-100 hover:bg-gray-50 align-top">
                    <td className="px-4 py-2.5 font-mono text-xs text-gray-600">{o.organization_id}</td>
                    <td className="px-4 py-2.5 font-medium text-gray-800">{o.name}</td>
                    <td className="px-4 py-2.5 text-gray-500">
                      {o.country_code ?? <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-4 py-2.5 text-gray-700 max-w-[14rem]">
                      {links.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {links.map((link) => (
                            <button
                              key={link.project_id}
                              type="button"
                              onClick={() => onNavigateToProject(link.project_id)}
                              className="text-xs font-mono text-blue-700 hover:underline"
                              title={`Open ${link.short_code}`}
                            >
                              {link.short_code}
                            </button>
                          ))}
                        </div>
                      ) : (
                        <span className="text-gray-300">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 max-w-[16rem]">
                      {links.some((l) => l.org_role) ? (
                        <div className="flex flex-wrap gap-1">
                          {[...new Set(links.map((l) => l.org_role).filter(Boolean))].map((rk) => {
                            const label = links
                              .filter((l) => l.org_role === rk)
                              .map((l) => roleLabelFor(l.project_id, rk))
                              .find(Boolean) ?? rk!;
                            const color = ORG_ROLE_COLORS[rk!] ?? "bg-gray-100 text-gray-600 border-gray-200";
                            return (
                              <span
                                key={rk}
                                className={`text-xs px-2 py-0.5 rounded border font-medium ${color}`}
                              >
                                {label}
                              </span>
                            );
                          })}
                        </div>
                      ) : (
                        <span className="text-gray-300">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={`text-xs font-medium ${o.is_active ? "text-green-600" : "text-gray-400"}`}>
                        {o.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right whitespace-nowrap">
                      <button
                        type="button"
                        onClick={() => onEdit(o)}
                        className="text-xs text-blue-600 hover:underline mr-3"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleRemoveOrg(o)}
                        className="text-xs text-red-600 hover:underline"
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
