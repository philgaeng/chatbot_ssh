"use client";

/**
 * <ProjectsSection> — Settings → Projects & packages.
 *
 * Lists projects, hosts the create modal and the per-project editor, and owns the
 * org-role vocabulary fetch shared with the editor.
 *
 * Extracted verbatim from `app/settings/page.tsx` (T3-05) — no behaviour change.
 */
import React, { useState, useEffect } from "react";
import {
  listProjects,
  deleteProject,
  listOrganizations,
  listProjectTypes,
  getOrgRoles,
  type ProjectItem,
  type OrganizationItem,
  type OrgRole,
  type ProjectTypeItem,
} from "@/lib/api";
import { friendlyError } from "@/components/settings/lib/friendlyError";
import { ProjectCreateModal } from "@/components/settings/projects/ProjectCreateModal";
import { ProjectEditor } from "@/components/settings/projects/ProjectEditor";

export function ProjectsSection({
  initialEditId = null,
  grmRoleChoices,
  isSuperAdmin,
  isCountryAdmin,
  adminWorkflowTracks,
  canCreateProject,
  canManageStructure,
}: {
  initialEditId?: string | null;
  grmRoleChoices: { key: string; label: string }[];
  isSuperAdmin: boolean;
  isCountryAdmin: boolean;
  adminWorkflowTracks: ("standard" | "seah")[];
  canCreateProject: boolean;
  canManageStructure: boolean;
}) {
  const canManageProjectCatalog = isSuperAdmin || isCountryAdmin;
  const isProjectScopedOnly = !canManageProjectCatalog;
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [orgs, setOrgs]         = useState<OrganizationItem[]>([]);
  const [orgRoles, setOrgRoles] = useState<OrgRole[]>([]);
  const [types, setTypes]       = useState<ProjectTypeItem[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState("");
  const [editing, setEditing]   = useState<ProjectItem | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  async function load() {
    setLoading(true);
    try {
      // Include inactive/draft projects — typed projects are created is_active=false until go-live.
      const [p, o] = await Promise.all([listProjects(undefined, false), listOrganizations()]);
      const r = await getOrgRoles().catch(() => [] as OrgRole[]);
      // Role labels come from the project's TYPE (doc 13 §2) — the global list is only a
      // fallback for legacy untyped projects.
      const t = await listProjectTypes(false).catch(() => [] as ProjectTypeItem[]);
      p.sort((a, b) => {
        if (a.is_active !== b.is_active) return a.is_active ? -1 : 1;
        return a.short_code.localeCompare(b.short_code);
      });
      setProjects(p);
      setOrgs(o);
      setOrgRoles(r);
      setTypes(t);
    } catch (e: unknown) {
      setError(friendlyError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  // Auto-open a project when navigated here from the Org tab
  useEffect(() => {
    if (!initialEditId || projects.length === 0) return;
    const target = projects.find((p) => p.project_id === initialEditId);
    if (target) setEditing(target);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialEditId, projects]);

  // Project-scoped admins only: land on their sole project (country_admin keeps the catalog view)
  useEffect(() => {
    if (!isProjectScopedOnly || loading || editing || projects.length !== 1) return;
    setEditing(projects[0]);
  }, [isProjectScopedOnly, loading, editing, projects]);

  async function handleRemoveProject(p: ProjectItem) {
    if (!confirm(`Remove project "${p.name}" (${p.short_code})? Packages and links will be deleted.`)) return;
    try {
      await deleteProject(p.project_id);
      if (editing?.project_id === p.project_id) setEditing(null);
      setProjects((prev) => prev.filter((x) => x.project_id !== p.project_id));
    } catch (e: unknown) {
      setError(friendlyError(e));
    }
  }

  if (editing) {
    return (
      <ProjectEditor
        project={editing}
        orgs={orgs}
        orgRoles={orgRoles}
        grmRoleChoices={grmRoleChoices}
        isSuperAdmin={isSuperAdmin}
        isCountryAdmin={isCountryAdmin}
        canManageProjectCatalog={canManageProjectCatalog}
        canManageStructure={canManageStructure}
        adminWorkflowTracks={adminWorkflowTracks}
        showBack={canManageProjectCatalog || projects.length > 1}
        onBack={() => { setEditing(null); load(); }}
        onUpdated={(p) => setEditing(p)}
        onOrganizationCreated={(org) => setOrgs((prev) => (prev.some((o) => o.organization_id === org.organization_id) ? prev : [...prev, org]))}
      />
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-gray-500">
          {projects.length} project{projects.length !== 1 ? "s" : ""}
          {projects.some((p) => !p.is_active) && (
            <span className="text-gray-400">
              {" "}
              · {projects.filter((p) => !p.is_active).length} inactive (awaiting setup / go-live)
            </span>
          )}
        </p>
        {canCreateProject && (
          <button
            onClick={() => setShowCreate(true)}
            className="bg-blue-600 text-white text-sm px-4 py-1.5 rounded hover:bg-blue-700 transition font-medium"
          >
            + New Project
          </button>
        )}
      </div>

      {canCreateProject && showCreate && (
        <ProjectCreateModal
          onCreated={(p) => {
            setShowCreate(false);
            setProjects((prev) => (
              prev.some((x) => x.project_id === p.project_id) ? prev : [...prev, p]
            ));
            setEditing(p);
          }}
          onClose={() => setShowCreate(false)}
        />
      )}

      {loading && <p className="text-sm text-gray-400 animate-pulse">Loading…</p>}
      {error   && <p className="text-sm text-red-500">{error}</p>}

      {!loading && !error && (
        <div className="border border-gray-200 rounded-lg overflow-hidden divide-y divide-gray-100">
          {projects.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-10">No projects yet.</p>
          ) : projects.map((p) => {
            const typeRoles = types.find((t) => t.type_key === p.project_type_key)?.actor_roles ?? [];
            const orgSummary = p.organizations.map((po) => {
              const orgName = orgs.find((o) => o.organization_id === po.organization_id)?.name ?? po.organization_id;
              const label =
                typeRoles.find((r) => r.key === po.org_role)?.label
                ?? orgRoles.find((r) => r.key === po.org_role)?.label;
              return label ? `${orgName} (${label})` : orgName;
            });
            return (
              <div key={p.project_id} className="flex items-center gap-4 px-5 py-3.5 hover:bg-gray-50">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-800 text-sm">{p.name}</span>
                    <span className="font-mono text-xs text-gray-400">{p.short_code}</span>
                    {!p.is_active && <span className="text-xs text-gray-400">(inactive)</span>}
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5 flex items-center gap-3">
                    <span>Organizations: {orgSummary.length > 0 ? orgSummary.join(", ") : <em>none</em>}</span>
                    <span>·</span>
                    <span>Locations: {p.location_codes.length > 0 ? `${p.location_codes.length} linked` : <em>none</em>}</span>
                  </div>
                </div>
                <button type="button" onClick={() => setEditing(p)} className="text-sm text-blue-600 hover:underline shrink-0 mr-3">
                  {canManageProjectCatalog ? "Edit" : "Set up"}
                </button>
                {canManageProjectCatalog && (
                  <button type="button" onClick={() => handleRemoveProject(p)} className="text-sm text-red-600 hover:underline shrink-0">
                    Remove
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
