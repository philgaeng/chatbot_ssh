"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  listOrganizations,
  listProjects,
  listPackages,
  type OrganizationItem,
  type PackageItem,
  type ProjectItem,
  type OfficerScope,
} from "@/lib/api";
import {
  packagesForOrganizationOnProject,
  projectsForOrganization,
} from "@/lib/officerJurisdiction";
import { isCountryJurisdictionRole } from "@/lib/jurisdiction";
import { LocationSearch } from "@/components/LocationSearch";

export type ScopeDraftRow = {
  rowId: string;
  scopeId?: string;
  status: "saved" | "new" | "edited" | "deleted";
  role_key: string;
  organization_id: string;
  project_id: string | null;
  project_code: string | null;
  package_id: string | null;
  location_code: string | null;
  location_name: string | null;
  includes_children: boolean;
};

type RoleChoice = { key: string; label: string };

type Catalog = {
  orgs: OrganizationItem[];
  projects: ProjectItem[];
  packagesByProject: Record<string, PackageItem[]>;
  loading: boolean;
};

function newRowId(): string {
  return `new-${crypto.randomUUID()}`;
}

export function scopeToDraftRow(s: OfficerScope): ScopeDraftRow {
  return {
    rowId: s.scope_id,
    scopeId: s.scope_id,
    status: "saved",
    role_key: s.role_key,
    organization_id: s.organization_id,
    project_id: s.project_id,
    project_code: s.project_code,
    package_id: s.package_id,
    location_code: s.location_code,
    location_name: s.location_code,
    includes_children: s.includes_children,
  };
}

export function emptyDraftRow(orgId: string, roleKey: string): ScopeDraftRow {
  return {
    rowId: newRowId(),
    status: "new",
    role_key: roleKey,
    organization_id: orgId,
    project_id: null,
    project_code: null,
    package_id: null,
    location_code: null,
    location_name: null,
    includes_children: false,
  };
}

function rowIsValid(row: ScopeDraftRow, countryRole: boolean): boolean {
  if (!row.organization_id || !row.role_key) return false;
  if (countryRole) return true;
  return Boolean(row.project_id || row.package_id || row.location_code);
}

function roleLabel(roleChoices: RoleChoice[], key: string): string {
  return roleChoices.find((r) => r.key === key)?.label ?? key;
}

function projectLabel(projects: ProjectItem[], projectId: string | null, projectCode: string | null): string {
  if (!projectId && !projectCode) return "—";
  const p = projects.find((x) => x.project_id === projectId);
  if (p) return p.short_code;
  return projectCode ?? "—";
}

function packageLabel(
  packagesByProject: Record<string, PackageItem[]>,
  projectId: string | null,
  packageId: string | null,
): string {
  if (!packageId) return "All packages";
  if (!projectId) return packageId.slice(0, 8);
  const pkg = (packagesByProject[projectId] ?? []).find((p) => p.package_id === packageId);
  return pkg ? pkg.package_code : packageId.slice(0, 8);
}

function locationLabel(row: ScopeDraftRow): string {
  if (!row.location_code) return "—";
  const name = row.location_name && row.location_name !== row.location_code ? row.location_name : null;
  const suffix = row.includes_children ? " (+ sub-locations)" : "";
  return name ? `${name}${suffix}` : `${row.location_code}${suffix}`;
}

function useScopeCatalog(): Catalog {
  const [orgs, setOrgs] = useState<OrganizationItem[]>([]);
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [packagesByProject, setPackagesByProject] = useState<Record<string, PackageItem[]>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
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
        if (!cancelled) setPackagesByProject(Object.fromEntries(pkgEntries));
      } catch {
        if (!cancelled) {
          setOrgs([]);
          setProjects([]);
          setPackagesByProject({});
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return { orgs, projects, packagesByProject, loading };
}

function ScopeRowEditor({
  draft,
  setDraft,
  catalog,
  roleChoices,
  officerOrgId,
  onSave,
  onCancel,
}: {
  draft: ScopeDraftRow;
  setDraft: React.Dispatch<React.SetStateAction<ScopeDraftRow | null>>;
  catalog: Catalog;
  roleChoices: RoleChoice[];
  officerOrgId: string;
  onSave: () => void;
  onCancel: () => void;
}) {
  const countryRole = isCountryJurisdictionRole(draft.role_key);
  const orgId = officerOrgId || draft.organization_id;

  const filteredProjects = useMemo(
    () => projectsForOrganization(orgId, catalog.projects, catalog.packagesByProject),
    [orgId, catalog.projects, catalog.packagesByProject],
  );

  const selectedProject = useMemo(
    () => catalog.projects.find((p) => p.project_id === draft.project_id),
    [catalog.projects, draft.project_id],
  );

  const filteredPackages = useMemo(
    () =>
      packagesForOrganizationOnProject(
        orgId,
        selectedProject,
        draft.project_id ? catalog.packagesByProject[draft.project_id] ?? [] : [],
      ),
    [orgId, selectedProject, draft.project_id, catalog.packagesByProject],
  );

  const singlePackage = filteredPackages.length === 1 ? filteredPackages[0] : null;

  function patchDraft(partial: Partial<ScopeDraftRow>) {
    setDraft((prev) => (prev ? { ...prev, ...partial } : prev));
  }

  useEffect(() => {
    if (singlePackage && draft.package_id !== singlePackage.package_id) {
      patchDraft({ package_id: singlePackage.package_id });
    }
  }, [singlePackage, draft.package_id]);

  const valid = rowIsValid({ ...draft, organization_id: orgId }, countryRole);

  return (
    <tr className="bg-blue-50/60">
      <td colSpan={5} className="px-3 py-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Role</label>
            <select
              value={draft.role_key}
              onChange={(e) => patchDraft({ role_key: e.target.value })}
              className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 bg-white"
            >
              {roleChoices.map((r) => (
                <option key={r.key} value={r.key}>{r.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Project</label>
            <select
              value={draft.project_id ?? ""}
              onChange={(e) => {
                const projectId = e.target.value || null;
                const proj = catalog.projects.find((p) => p.project_id === projectId);
                patchDraft({
                  project_id: projectId,
                  project_code: proj?.short_code ?? null,
                  package_id: null,
                  location_code: null,
                  location_name: null,
                });
              }}
              disabled={catalog.loading}
              className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 bg-white disabled:bg-gray-50"
            >
              <option value="">{catalog.loading ? "Loading…" : "— optional —"}</option>
              {filteredProjects.map((p) => (
                <option key={p.project_id} value={p.project_id}>{p.short_code} — {p.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Package</label>
            {singlePackage ? (
              <div className="text-sm border border-gray-200 rounded px-2 py-1.5 bg-gray-50 text-gray-700">
                {singlePackage.package_code}
              </div>
            ) : (
              <select
                value={draft.package_id ?? ""}
                onChange={(e) => patchDraft({ package_id: e.target.value || null })}
                disabled={!draft.project_id}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 bg-white disabled:bg-gray-50"
              >
                <option value="">{draft.project_id ? "All packages" : "Select project first"}</option>
                {filteredPackages.map((pkg) => (
                  <option key={pkg.package_id} value={pkg.package_id}>{pkg.package_code} — {pkg.name}</option>
                ))}
              </select>
            )}
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Location</label>
            {draft.location_code ? (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="inline-flex items-center gap-1 bg-blue-50 text-blue-700 border border-blue-200 rounded px-2 py-1 text-xs">
                  {draft.location_name ?? draft.location_code}
                  <button
                    type="button"
                    onClick={() => patchDraft({ location_code: null, location_name: null })}
                    className="text-blue-300 hover:text-blue-600"
                  >
                    ×
                  </button>
                </span>
                <label className="flex items-center gap-1 text-xs text-gray-500 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={draft.includes_children}
                    onChange={(e) => patchDraft({ includes_children: e.target.checked })}
                    className="accent-purple-500"
                  />
                  sub-locations
                </label>
              </div>
            ) : (
              <LocationSearch
                placeholder="Search location…"
                onSelect={(code, name) => patchDraft({ location_code: code, location_name: name })}
              />
            )}
          </div>
        </div>
        {!countryRole && (
          <p className="text-xs text-gray-500 mt-2">
            At least one of project, package, or location is required.
          </p>
        )}
        <div className="flex justify-end gap-2 mt-3">
          <button type="button" onClick={onCancel} className="text-xs text-gray-600 px-3 py-1.5">
            Cancel
          </button>
          <button
            type="button"
            onClick={onSave}
            disabled={!valid}
            className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {draft.status === "new" ? "Add row" : "Apply"}
          </button>
        </div>
      </td>
    </tr>
  );
}

export function OfficerScopeTable({
  rows,
  onChange,
  roleChoices,
  officerOrgId,
  defaultRoleKey,
  onEditingChange,
}: {
  rows: ScopeDraftRow[];
  onChange: (rows: ScopeDraftRow[]) => void;
  roleChoices: RoleChoice[];
  officerOrgId: string;
  defaultRoleKey: string;
  onEditingChange?: (editing: boolean) => void;
}) {
  const catalog = useScopeCatalog();
  const [editingRowId, setEditingRowId] = useState<string | null>(null);
  const [editorDraft, setEditorDraft] = useState<ScopeDraftRow | null>(null);

  useEffect(() => {
    onEditingChange?.(Boolean(editingRowId));
  }, [editingRowId, onEditingChange]);

  const visibleRows = rows.filter((r) => r.status !== "deleted");

  function startEdit(row: ScopeDraftRow) {
    if (editingRowId) return;
    setEditingRowId(row.rowId);
    setEditorDraft({ ...row });
  }

  function startAdd() {
    if (editingRowId) return;
    const draft = emptyDraftRow(officerOrgId, defaultRoleKey);
    setEditingRowId(draft.rowId);
    setEditorDraft(draft);
  }

  function cancelEdit() {
    setEditingRowId(null);
    setEditorDraft(null);
  }

  function commitEdit() {
    if (!editorDraft) return;
    const orgId = officerOrgId || editorDraft.organization_id;
    const committed: ScopeDraftRow = {
      ...editorDraft,
      organization_id: orgId,
      status:
        editorDraft.status === "new"
          ? "new"
          : editorDraft.status === "saved"
            ? "edited"
            : editorDraft.status,
    };
    if (!rowIsValid(committed, isCountryJurisdictionRole(committed.role_key))) return;

    const exists = rows.some((r) => r.rowId === committed.rowId);
    if (exists) {
      onChange(rows.map((r) => (r.rowId === committed.rowId ? committed : r)));
    } else {
      onChange([...rows, committed]);
    }
    cancelEdit();
  }

  function deleteRow(rowId: string) {
    if (editingRowId === rowId) cancelEdit();
    onChange(
      rows
        .map((r) => {
          if (r.rowId !== rowId) return r;
          if (r.status === "new") return { ...r, status: "deleted" as const };
          return { ...r, status: "deleted" as const };
        })
        .filter((r) => !(r.status === "deleted" && !r.scopeId)),
    );
  }

  const isAdding = editorDraft?.status === "new" && !rows.some((r) => r.rowId === editorDraft.rowId);

  const orgDisplayName =
    catalog.orgs.find((o) => o.organization_id === officerOrgId)?.name ?? officerOrgId;

  return (
    <div className="space-y-3">
      {officerOrgId && (
        <p className="text-sm text-gray-700">
          <span className="text-gray-500">Organization:</span>{" "}
          <span className="font-medium">{orgDisplayName}</span>
        </p>
      )}

      <div className="border border-gray-200 rounded-lg overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
              <th className="px-3 py-2.5">Role</th>
              <th className="px-3 py-2.5">Project</th>
              <th className="px-3 py-2.5">Package</th>
              <th className="px-3 py-2.5">Location</th>
              <th className="px-3 py-2.5 w-28 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {catalog.loading && visibleRows.length === 0 && !isAdding ? (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-gray-400">Loading scopes…</td>
              </tr>
            ) : visibleRows.length === 0 && !isAdding ? (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-gray-500">
                  No scopes yet. Add a row to define this officer&apos;s coverage.
                </td>
              </tr>
            ) : (
              visibleRows.map((row) => {
                const foreignOrg = officerOrgId && row.organization_id !== officerOrgId;
                if (editingRowId === row.rowId && editorDraft) {
                  return (
                    <ScopeRowEditor
                      key={row.rowId}
                      draft={editorDraft}
                      setDraft={setEditorDraft}
                      catalog={catalog}
                      roleChoices={roleChoices}
                      officerOrgId={officerOrgId}
                      onSave={commitEdit}
                      onCancel={cancelEdit}
                    />
                  );
                }
                return (
                  <tr
                    key={row.rowId}
                    className={foreignOrg ? "bg-amber-50" : row.status === "new" ? "bg-emerald-50/50" : undefined}
                  >
                    <td className="px-3 py-2.5 text-gray-800">
                      {roleLabel(roleChoices, row.role_key)}
                      {row.status === "new" && (
                        <span className="ml-1.5 text-[10px] font-semibold text-emerald-700 uppercase">New</span>
                      )}
                      {row.status === "edited" && (
                        <span className="ml-1.5 text-[10px] font-semibold text-blue-700 uppercase">Edited</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-gray-700">
                      {projectLabel(catalog.projects, row.project_id, row.project_code)}
                    </td>
                    <td className="px-3 py-2.5 text-gray-700">
                      {packageLabel(catalog.packagesByProject, row.project_id, row.package_id)}
                    </td>
                    <td className="px-3 py-2.5 text-gray-700">{locationLabel(row)}</td>
                    <td className="px-3 py-2.5 text-right whitespace-nowrap">
                      <button
                        type="button"
                        onClick={() => startEdit(row)}
                        disabled={Boolean(editingRowId)}
                        className="text-xs text-blue-600 hover:text-blue-800 font-medium disabled:opacity-40 mr-3"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => deleteRow(row.rowId)}
                        disabled={Boolean(editingRowId)}
                        className="text-xs text-red-600 hover:text-red-800 font-medium disabled:opacity-40"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
            {isAdding && editorDraft && (
              <ScopeRowEditor
                key={editorDraft.rowId}
                draft={editorDraft}
                setDraft={setEditorDraft}
                catalog={catalog}
                roleChoices={roleChoices}
                officerOrgId={officerOrgId}
                onSave={commitEdit}
                onCancel={cancelEdit}
              />
            )}
          </tbody>
        </table>
      </div>

      <button
        type="button"
        onClick={startAdd}
        disabled={Boolean(editingRowId) || catalog.loading}
        className="text-sm text-blue-600 hover:text-blue-800 font-medium disabled:opacity-40"
      >
        + Add scope
      </button>
    </div>
  );
}

/** Rows that need API delete (removed or replaced by edit). */
export function scopeRowsToDelete(rows: ScopeDraftRow[]): string[] {
  const ids = new Set<string>();
  for (const r of rows) {
    if (r.status === "deleted" && r.scopeId) ids.add(r.scopeId);
    if (r.status === "edited" && r.scopeId) ids.add(r.scopeId);
  }
  return [...ids];
}

/** Rows that need API create (new or edited replacements). */
export function scopeRowsToCreate(rows: ScopeDraftRow[]): ScopeDraftRow[] {
  return rows.filter((r) => r.status === "new" || r.status === "edited");
}

export function activeScopeRows(rows: ScopeDraftRow[]): ScopeDraftRow[] {
  return rows.filter((r) => r.status !== "deleted");
}
