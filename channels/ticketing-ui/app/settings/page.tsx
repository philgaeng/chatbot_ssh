"use client";

import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { AlertTriangle, X, Lock, ClipboardList, Construction } from "lucide-react";
import { useAuth } from "@/app/providers/AuthProvider";
import { QuarterlyReportSettings } from "@/components/settings/QuarterlyReportSettings";
import {
  listWorkflows,
  listTemplates,
  createWorkflow,
  updateWorkflow,
  publishWorkflow,
  archiveWorkflow,
  deleteWorkflow,
  getWorkflow,
  saveWorkflowAsTemplate,
  addStep,
  updateStep,
  deleteStep,
  reorderSteps,
  listScopes,
  addScope,
  deleteScope,
  listOrganizations,
  listCountries,
  listLocations,
  listProjects,
  listProjectTypes,
  createProject,
  updateProject,
  deleteProject,
  addProjectOrg,
  removeProjectOrg,
  addProjectLocation,
  removeProjectLocation,
  importLocations,
  getLocationTemplateCsvUrl,
  getLocationTemplateJsonUrl,
  updateProjectOrgRole,
  getOrgRoles,
  setOrgRoles,
  getReportLimits,
  setReportLimits,
  getArchivingPolicy,
  setArchivingPolicy,
  getProjectActorRoles,
  setProjectActorRoles,
  addPackageOrg,
  removePackageOrg,
  updateOrganization,
  deleteOrganization,
  listProjectsForOrg,
  listPackages,
  createPackage,
  updatePackage,
  addPackageLocation,
  removePackageLocation,
  type WorkflowDefinition,
  type WorkflowStep,
  type WorkflowAssignmentItem,
  type StepPayload,
  type OfficerScope,
  type OrganizationItem,
  type CountryItem,
  type LocationNode,
  type ProjectItem,
  type ProjectOrgItem,
  type OrgRole,
  type PackageItem,
  type PackageCreate,
  listRoles,
  createRole,
  listRoleArchetypes,
  listAdminScopes,
  createAdminScope,
  deleteAdminScope,
  updateRole,
  deleteRole,
  type GrmRole,
  type AdminScopeRow,
  type RoleArchetype,
} from "@/lib/api";
import { OfficersTab } from "@/components/settings/OfficersTab";
import { ProjectStaffingSection } from "@/components/settings/ProjectStaffingSection";
import { ProjectOfficerModal } from "@/components/settings/ProjectOfficerModal";
import { ProjectGoLivePanel } from "@/components/settings/ProjectGoLivePanel";
import { ProjectTypesTab } from "@/components/settings/ProjectTypesTab";
import { OrgCreateModal } from "@/components/settings/OrgCreateModal";
import { ProjectActorAddRow } from "@/components/settings/ProjectActorAddRow";
import { LocationSearch } from "@/components/LocationSearch";
import { JURISDICTION_MODE_LABELS, type JurisdictionMode } from "@/lib/jurisdiction";

// ── GRM roles (ticketing.roles) ───────────────────────────────────────────────

type RoleEntry = {
  role_id: string;
  key: string;
  label: string;
  workflow: string;
  jurisdiction: string;
  description: string;
  role_origin?: string;
  steps_count?: number;
  officers_count?: number;
};

function mapGrmRoleToEntry(r: GrmRole): RoleEntry {
  return {
    role_id: r.role_id,
    key: r.role_key,
    label: r.display_name,
    workflow: r.workflow_scope ?? "Standard",
    jurisdiction: r.jurisdiction_mode ?? "field",
    description: r.description ?? "",
    role_origin: r.role_origin ?? "system",
    steps_count: r.steps_count ?? 0,
    officers_count: r.officers_count ?? 0,
  };
}

// ── Role edit modal ───────────────────────────────────────────────────────────

function RoleEditModal({ role, onSaved, onClose }: {
  role: RoleEntry;
  onSaved: (updated: RoleEntry) => void;
  onClose: () => void;
}) {
  const [label, setLabel]               = useState(role.label);
  const [workflow, setWorkflow]         = useState(role.workflow || "Standard");
  const [jurisdiction, setJurisdiction] = useState<JurisdictionMode>(
    (role.jurisdiction as JurisdictionMode) || "field",
  );
  const [description, setDescription] = useState(role.description);
  const [saved, setSaved]               = useState(false);
  const [saving, setSaving]             = useState(false);
  const [err, setErr]                   = useState("");

  async function handleSave() {
    setErr("");
    setSaving(true);
    try {
      const raw = await updateRole(role.role_id, {
        display_name: label.trim(),
        description: description.trim() || null,
        workflow_scope: workflow.trim() || null,
        jurisdiction_mode: jurisdiction,
      });
      onSaved(mapGrmRoleToEntry(raw));
      setSaved(true);
      setTimeout(() => { setSaved(false); onClose(); }, 650);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 overflow-hidden">
        <div className="bg-slate-700 text-white px-6 py-4 flex items-center justify-between">
          <div>
            <div className="font-semibold">Edit Role</div>
            <div className="text-xs text-slate-300 font-mono mt-0.5">{role.key}</div>
          </div>
          <button type="button" onClick={onClose} className="text-slate-300 hover:text-white text-xl leading-none">×</button>
        </div>

        <div className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">Display name</label>
              <input
                autoFocus
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">Workflow scope</label>
              <select
                value={workflow}
                onChange={(e) => setWorkflow(e.target.value)}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
              >
                <option value="Standard">Standard</option>
                <option value="SEAH">SEAH</option>
                <option value="Both">Both</option>
              </select>
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Default jurisdiction</label>
            <select
              value={jurisdiction}
              onChange={(e) => setJurisdiction(e.target.value as JurisdictionMode)}
              className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
            >
              {(Object.keys(JURISDICTION_MODE_LABELS) as JurisdictionMode[]).map((mode) => (
                <option key={mode} value={mode}>{JURISDICTION_MODE_LABELS[mode]}</option>
              ))}
            </select>
            <p className="text-xs text-gray-400 mt-1">
              Controls whether new officer scopes need a project, package, or location. Observer roles typically use country-wide.
            </p>
          </div>

          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 resize-none focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>

          {err && <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-2 py-1">{err}</p>}

          <p className="text-xs text-gray-400">
            Changes are saved to <span className="font-mono">ticketing.roles</span>. Role <span className="font-mono">role_key</span> is fixed; workflow assignment tiers are configured per workflow step.
          </p>
        </div>

        <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-3">
          <button type="button" onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700 px-4 py-1.5 rounded transition">
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={saving || !label.trim()}
            className={`text-sm px-4 py-1.5 rounded font-medium transition disabled:opacity-40 ${
              saved ? "bg-green-600 text-white" : "bg-blue-600 text-white hover:bg-blue-700"
            }`}
          >
            {saved ? "✓ Saved" : saving ? "Saving…" : "Save changes"}
          </button>
        </div>
      </div>
    </div>
  );
}

type MainTab = "org_officers" | "workflows_roles" | "projects" | "platform";
type OrgOfficersSub = "organizations" | "officers";
type WorkflowsRolesSub = "workflows" | "roles";
type PlatformSub = "locations" | "reports" | "project_types" | "system_config" | "admin_access";

const MAIN_TABS: { id: MainTab; label: string }[] = [
  { id: "org_officers",      label: "Organizations & officers" },
  { id: "workflows_roles",   label: "Workflows, roles & permissions" },
  { id: "projects",          label: "Projects & packages" },
  { id: "platform",          label: "Settings" },
];

// Color classes for org role badges (keyed by role.key)
const ORG_ROLE_COLORS: Record<string, string> = {
  project_owner:           "bg-slate-100 text-slate-700 border-slate-200",
  donor:                   "bg-blue-100 text-blue-700 border-blue-200",
  executing_agency:        "bg-purple-100 text-purple-700 border-purple-200",
  implementing_agency:     "bg-indigo-100 text-indigo-700 border-indigo-200",
  main_contractor:         "bg-orange-100 text-orange-700 border-orange-200",
  subcontractor_t1:        "bg-amber-100 text-amber-700 border-amber-200",
  subcontractor_t2:        "bg-amber-100 text-amber-600 border-amber-200",
  supervision_consultant:  "bg-teal-100 text-teal-700 border-teal-200",
  specialized_consultant:  "bg-green-100 text-green-700 border-green-200",
};

// ── Tab components ────────────────────────────────────────────────────────────

function RoleCreateModal({
  defaultTrack,
  onCreated,
  onClose,
}: {
  defaultTrack: "standard" | "seah";
  onCreated: () => void;
  onClose: () => void;
}) {
  const [displayName, setDisplayName] = useState("");
  const [roleKey, setRoleKey] = useState("");
  const [workflowScope, setWorkflowScope] = useState(defaultTrack === "seah" ? "SEAH" : "Standard");
  const [jurisdiction, setJurisdiction] = useState<JurisdictionMode>("field");
  const [archetype, setArchetype] = useState("field_actor");
  const [description, setDescription] = useState("");
  const [archetypes, setArchetypes] = useState<RoleArchetype[]>([]);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    listRoleArchetypes().then(setArchetypes).catch(() => setArchetypes([]));
  }, []);

  async function handleSave() {
    if (!displayName.trim()) { setErr("Display name is required"); return; }
    setSaving(true); setErr("");
    try {
      await createRole({
        display_name: displayName.trim(),
        role_key: roleKey.trim() || undefined,
        workflow_scope: workflowScope,
        jurisdiction_mode: jurisdiction,
        archetype,
        description: description.trim() || undefined,
      });
      onCreated();
      onClose();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Create failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg p-5">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">New operational role</h3>
        {err && <p className="text-sm text-red-600 mb-3">{err}</p>}
        <div className="space-y-3 text-sm">
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Display name *</label>
            <input value={displayName} onChange={(e) => setDisplayName(e.target.value)}
              className="w-full border border-gray-300 rounded px-2 py-1.5" />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Role key (slug)</label>
            <input value={roleKey} onChange={(e) => setRoleKey(e.target.value)} placeholder="auto-generated if empty"
              className="w-full border border-gray-300 rounded px-2 py-1.5 font-mono text-xs" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">Workflow track</label>
              <select value={workflowScope} onChange={(e) => setWorkflowScope(e.target.value)}
                className="w-full border border-gray-300 rounded px-2 py-1.5">
                <option value="Standard">Standard</option>
                <option value="SEAH">SEAH</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">Archetype</label>
              <select value={archetype} onChange={(e) => setArchetype(e.target.value)}
                className="w-full border border-gray-300 rounded px-2 py-1.5">
                {archetypes.map((a) => (
                  <option key={a.key} value={a.key}>{a.label}</option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Default jurisdiction</label>
            <select value={jurisdiction} onChange={(e) => setJurisdiction(e.target.value as JurisdictionMode)}
              className="w-full border border-gray-300 rounded px-2 py-1.5">
              {Object.entries(JURISDICTION_MODE_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Description</label>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2}
              className="w-full border border-gray-300 rounded px-2 py-1.5" />
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-5">
          <button type="button" onClick={onClose} className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded">Cancel</button>
          <button type="button" onClick={handleSave} disabled={saving}
            className="px-4 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50">
            {saving ? "Creating…" : "Create role"}
          </button>
        </div>
      </div>
    </div>
  );
}

function RolesTab({ catalog, loading, onReload, canCreate }: {
  catalog: RoleEntry[];
  loading: boolean;
  onReload: () => void;
  canCreate: boolean;
}) {
  const [editing, setEditing]   = useState<RoleEntry | null>(null);
  const [creating, setCreating] = useState(false);
  const [trackFilter, setTrackFilter] = useState<"all" | "standard" | "seah">("all");
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const { adminWorkflowTracks } = useAuth();
  const defaultTrack = adminWorkflowTracks.includes("seah") && !adminWorkflowTracks.includes("standard")
    ? "seah" as const : "standard" as const;

  const filtered = catalog.filter((r) => {
    if (trackFilter === "standard") return r.workflow === "Standard" || r.workflow === "Both";
    if (trackFilter === "seah") return r.workflow === "SEAH" || r.workflow === "Both";
    return true;
  });

  async function handleRemoveRole(r: RoleEntry) {
    if (!confirm(`Remove role "${r.label}" (${r.key}) from the catalog?`)) return;
    setDeleteError(null);
    try {
      await deleteRole(r.role_id);
      if (editing?.role_id === r.role_id) setEditing(null);
      onReload();
    } catch (e: unknown) {
      setDeleteError(e instanceof Error ? e.message : "Remove failed");
    }
  }

  const workflowBadge = (w: string) =>
    w === "SEAH"
      ? "bg-red-100 text-red-700"
      : w === "Both"
      ? "bg-purple-100 text-purple-700"
      : "bg-blue-100 text-blue-700";

  return (
    <div>
      {editing && (
        <RoleEditModal
          role={editing}
          onSaved={() => { onReload(); }}
          onClose={() => setEditing(null)}
        />
      )}
      {creating && (
        <RoleCreateModal
          defaultTrack={defaultTrack}
          onCreated={onReload}
          onClose={() => setCreating(false)}
        />
      )}

      <div className="flex items-center justify-between mb-5 gap-3 flex-wrap">
        <p className="text-sm text-gray-500">
          {loading ? "Loading roles…" : `${filtered.length} operational roles`}
        </p>
        <div className="flex items-center gap-2">
          <select value={trackFilter} onChange={(e) => setTrackFilter(e.target.value as typeof trackFilter)}
            className="text-xs border border-gray-300 rounded px-2 py-1">
            <option value="all">All tracks</option>
            <option value="standard">Standard</option>
            <option value="seah">SEAH</option>
          </select>
          {canCreate && (
            <button type="button" onClick={() => setCreating(true)}
              className="text-xs bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700">
              + New role
            </button>
          )}
          <button type="button" onClick={() => onReload()} className="text-xs text-blue-600 hover:underline">
            Refresh
          </button>
        </div>
      </div>

      {!loading && catalog.length === 0 && (
        <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2 mb-3">
          No roles found. Run Alembic migrations and seed (e.g. <span className="font-mono">mock_tickets --reset</span>) so{" "}
          <span className="font-mono">ticketing.constants.grm_role_catalog</span> is applied.
        </p>
      )}

      {deleteError && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2 mb-3">{deleteError}</p>
      )}

      <div className="border border-gray-200 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-700 text-slate-100 text-left">
              <th className="px-4 py-2.5 font-medium">Role</th>
              <th className="px-4 py-2.5 font-medium">Workflow</th>
              <th className="px-4 py-2.5 font-medium">Usage</th>
              <th className="px-4 py-2.5 font-medium">Description</th>
              <th className="px-4 py-2.5 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
              <tr key={r.key} className="border-t border-gray-100 hover:bg-gray-50 align-top">
                <td className="px-4 py-3">
                  <div className="font-medium text-gray-800">{r.label}</div>
                  <div className="text-xs font-mono text-gray-400 mt-0.5">{r.key}</div>
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded ${workflowBadge(r.workflow)}`}>
                    {r.workflow}
                  </span>
                  {r.role_origin === "custom" && (
                    <span className="ml-1 text-[10px] text-gray-400">custom</span>
                  )}
                </td>
                <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                  {r.steps_count ?? 0} steps · {r.officers_count ?? 0} officers
                </td>
                <td className="px-4 py-3 text-gray-500 text-xs max-w-sm">{r.description}</td>
                <td className="px-4 py-3 whitespace-nowrap">
                  <button
                    type="button"
                    onClick={() => setEditing(r)}
                    className="text-blue-600 hover:underline text-xs mr-3"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => handleRemoveRole(r)}
                    className="text-red-600 hover:underline text-xs"
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-gray-400 mt-3">
        Operational catalog only — admin assignments live under Settings → Admin access.
        Country admins may create custom roles via archetype templates.
      </p>
    </div>
  );
}

// ── Admin access (platform) ───────────────────────────────────────────────────

function AdminAccessTab() {
  const [rows, setRows] = useState<AdminScopeRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [userId, setUserId] = useState("");
  const [roleKey, setRoleKey] = useState<"country_admin" | "project_admin">("country_admin");
  const [countryCode, setCountryCode] = useState("NP");
  const [projectId, setProjectId] = useState("KL_ROAD");
  const [track, setTrack] = useState<"standard" | "seah">("standard");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await listAdminScopes());
      setErr("");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleAppoint() {
    if (!userId.trim()) return;
    try {
      await createAdminScope({
        user_id: userId.trim(),
        role_key: roleKey,
        country_code: roleKey === "country_admin" ? countryCode : undefined,
        project_id: roleKey === "project_admin" ? projectId : undefined,
        workflow_track: track,
      });
      setUserId("");
      await load();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Appoint failed");
    }
  }

  async function handleRevoke(id: string) {
    if (!confirm("Revoke this admin assignment?")) return;
    try {
      await deleteAdminScope(id);
      await load();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Revoke failed");
    }
  }

  return (
    <div>
      <p className="text-sm text-gray-500 mb-4">Appoint scoped country and project administrators.</p>
      {err && <p className="text-sm text-red-600 mb-3">{err}</p>}
      <div className="border border-gray-200 rounded-lg p-4 mb-5 bg-gray-50 space-y-3 text-sm">
        <div className="font-medium text-gray-700">+ Appoint admin</div>
        <div className="grid grid-cols-2 gap-3">
          <input value={userId} onChange={(e) => setUserId(e.target.value)} placeholder="Officer email"
            className="border border-gray-300 rounded px-2 py-1.5 col-span-2" />
          <select value={roleKey} onChange={(e) => setRoleKey(e.target.value as typeof roleKey)}
            className="border border-gray-300 rounded px-2 py-1.5">
            <option value="country_admin">country_admin</option>
            <option value="project_admin">project_admin</option>
          </select>
          <select value={track} onChange={(e) => setTrack(e.target.value as typeof track)}
            className="border border-gray-300 rounded px-2 py-1.5">
            <option value="standard">standard</option>
            <option value="seah">seah</option>
          </select>
          {roleKey === "country_admin" ? (
            <input value={countryCode} onChange={(e) => setCountryCode(e.target.value)} placeholder="Country code"
              className="border border-gray-300 rounded px-2 py-1.5" />
          ) : (
            <input value={projectId} onChange={(e) => setProjectId(e.target.value)} placeholder="Project (e.g. KL_ROAD)"
              className="border border-gray-300 rounded px-2 py-1.5" />
          )}
        </div>
        <button type="button" onClick={handleAppoint}
          className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700">
          Appoint
        </button>
      </div>
      {loading ? (
        <p className="text-sm text-gray-500">Loading…</p>
      ) : (
        <table className="w-full text-sm border border-gray-200 rounded-lg overflow-hidden">
          <thead>
            <tr className="bg-slate-700 text-slate-100 text-left">
              <th className="px-3 py-2">User</th>
              <th className="px-3 py-2">Role</th>
              <th className="px-3 py-2">Scope</th>
              <th className="px-3 py-2">Track</th>
              <th className="px-3 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.admin_scope_id} className="border-t border-gray-100">
                <td className="px-3 py-2 font-mono text-xs">{r.user_id}</td>
                <td className="px-3 py-2">{r.role_key}</td>
                <td className="px-3 py-2 text-xs">{r.country_code ?? r.project_id ?? "—"}</td>
                <td className="px-3 py-2">{r.workflow_track}</td>
                <td className="px-3 py-2">
                  <button type="button" onClick={() => handleRevoke(r.admin_scope_id)}
                    className="text-red-600 text-xs hover:underline">Revoke</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ── Workflow helpers ──────────────────────────────────────────────────────────

type WorkflowRoleOption = { key: string; label: string; origin?: string };

function statusBadge(status: string) {
  const map: Record<string, string> = {
    published: "bg-green-100 text-green-700",
    draft:     "bg-yellow-100 text-yellow-700",
    archived:  "bg-gray-100 text-gray-500",
    template:  "bg-blue-100 text-blue-700",
  };
  return map[status] ?? "bg-gray-100 text-gray-600";
}

function typeBadge(t: string) {
  return t === "seah" ? "bg-red-100 text-red-700" : "bg-slate-100 text-slate-600";
}

// ── Step form (inline accordion) ─────────────────────────────────────────────

function StepForm({
  step,
  workflowId,
  roleOptions,
  canCreateRole,
  onRoleCreated,
  onSaved,
  onCancel,
}: {
  step: WorkflowStep;
  workflowId: string;
  roleOptions: WorkflowRoleOption[];
  canCreateRole?: boolean;
  onRoleCreated?: () => void;
  onSaved: (s: WorkflowStep) => void;
  onCancel: () => void;
}) {
  const [displayName, setDisplayName]         = useState(step.display_name);
  const [stepKey, setStepKey]                 = useState(step.step_key);
  const [roleKey, setRoleKey]                 = useState(step.assigned_role_key);
  const [responseH, setResponseH]             = useState<string>(step.response_time_hours?.toString() ?? "");
  const [resolutionD, setResolutionD]         = useState<string>(step.resolution_time_days?.toString() ?? "");
  const [actions, setActions]                 = useState<string[]>(step.expected_actions ?? []);
  const [newAction, setNewAction]             = useState("");
  // Spec 12 tier fields
  const [supervisorRole, setSupervisorRole]   = useState<string>(step.supervisor_role ?? "");
  const [informedRoles, setInformedRoles]     = useState<string[]>(step.informed_roles ?? []);
  const [newInformed, setNewInformed]         = useState("");
  const [observerRoles, setObserverRoles]     = useState<string[]>(step.observer_roles ?? []);
  const [newObserver, setNewObserver]         = useState("");
  const [informedPii, setInformedPii]         = useState<boolean>(step.informed_pii_access ?? false);
  const [saving, setSaving]                   = useState(false);
  const [error, setError]                     = useState("");
  const [showCreateRole, setShowCreateRole]   = useState(false);
  const systemRoles = roleOptions.filter((r) => r.origin !== "custom");
  const customRoles = roleOptions.filter((r) => r.origin === "custom");

  async function handleSave() {
    if (!displayName.trim() || !roleKey) { setError("Name and role are required."); return; }
    setSaving(true); setError("");
    try {
      const payload: Partial<StepPayload> = {
        display_name: displayName.trim(),
        step_key: stepKey.trim() || undefined,
        assigned_role_key: roleKey,
        response_time_hours: responseH ? parseInt(responseH) : null,
        resolution_time_days: resolutionD ? parseInt(resolutionD) : null,
        expected_actions: actions.length ? actions : null,
        // Spec 12 tier fields
        supervisor_role: supervisorRole || null,
        informed_roles: informedRoles,
        observer_roles: observerRoles,
        informed_pii_access: informedPii,
      };
      const updated = await updateStep(workflowId, step.step_id, payload);
      onSaved(updated);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally { setSaving(false); }
  }

  function addTag(list: string[], setList: (v: string[]) => void, val: string, setVal: (v: string) => void) {
    const t = val.trim();
    if (t && !list.includes(t)) setList([...list, t]);
    setVal("");
  }

  return (
    <div className="border border-blue-200 bg-blue-50 rounded-lg p-4 mt-2 space-y-3">
      {error && <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-2 py-1">{error}</p>}

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Display name *</label>
          <input value={displayName} onChange={e => setDisplayName(e.target.value)}
            className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Step key</label>
          <input value={stepKey} onChange={e => setStepKey(e.target.value)}
            className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 font-mono focus:outline-none focus:ring-1 focus:ring-blue-400" />
        </div>
      </div>

      {showCreateRole && (
        <RoleCreateModal
          defaultTrack="standard"
          onCreated={() => { setShowCreateRole(false); onRoleCreated?.(); }}
          onClose={() => setShowCreateRole(false)}
        />
      )}
      <div>
        <label className="text-xs font-medium text-gray-500 block mb-1">Assigned role *</label>
        <select value={roleKey} onChange={e => {
          if (e.target.value === "__create__") { setShowCreateRole(true); return; }
          setRoleKey(e.target.value);
        }}
          className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400">
          <option value="">— select role —</option>
          {systemRoles.length > 0 && (
            <optgroup label="System (TOR)">
              {systemRoles.map(r => <option key={r.key} value={r.key}>{r.label}</option>)}
            </optgroup>
          )}
          {customRoles.length > 0 && (
            <optgroup label="Custom">
              {customRoles.map(r => <option key={r.key} value={r.key}>{r.label}</option>)}
            </optgroup>
          )}
          {canCreateRole && <option value="__create__">+ Create role…</option>}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Response time (hours)</label>
          <input type="number" min="0" value={responseH} onChange={e => setResponseH(e.target.value)} placeholder="e.g. 48"
            className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Resolution time (days)</label>
          <input type="number" min="0" value={resolutionD} onChange={e => setResolutionD(e.target.value)} placeholder="e.g. 7"
            className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
        </div>
      </div>

      {/* Expected actions */}
      <div>
        <label className="text-xs font-medium text-gray-500 block mb-1">Expected actions</label>
        <div className="flex flex-wrap gap-1 mb-1">
          {actions.map(a => (
            <span key={a} className="flex items-center gap-1 text-xs bg-white border border-gray-200 text-gray-700 px-2 py-0.5 rounded">
              {a}
              <button onClick={() => setActions(actions.filter(x => x !== a))} className="text-gray-400 hover:text-red-500 leading-none">×</button>
            </span>
          ))}
        </div>
        <div className="flex gap-2">
          <input value={newAction} onChange={e => setNewAction(e.target.value)}
            onKeyDown={e => e.key === "Enter" && addTag(actions, setActions, newAction, setNewAction)}
            placeholder="e.g. Investigate root cause"
            className="flex-1 text-xs border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
          <button onClick={() => addTag(actions, setActions, newAction, setNewAction)}
            disabled={!newAction.trim()}
            className="text-xs bg-gray-100 hover:bg-gray-200 px-3 py-1.5 rounded disabled:opacity-40 transition">Add</button>
        </div>
      </div>

      {/* ── Spec 12 tier model fields ────────────────────────────────────────── */}
      <div className="border-t border-blue-100 pt-3 mt-1 space-y-3">
        <div className="text-[11px] font-semibold text-blue-600 uppercase tracking-wide">Tier configuration (Spec 12)</div>

        {/* Supervisor role */}
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Supervisor role</label>
          <select value={supervisorRole} onChange={e => setSupervisorRole(e.target.value)}
            className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400">
            <option value="">— None (no supervisor at this step) —</option>
            {roleOptions.map(r => <option key={r.key} value={r.key}>{r.label}</option>)}
          </select>
          <p className="text-[11px] text-gray-400 mt-0.5">Notified on escalation/SLA breach. Can override Actor, reassign ticket.</p>
        </div>

        {/* Informed roles */}
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Informed roles — auto-added when ticket enters this step</label>
          <div className="flex flex-wrap gap-1 mb-1">
            {informedRoles.map(r => (
              <span key={r} className="flex items-center gap-1 text-xs bg-purple-50 border border-purple-200 text-purple-700 px-2 py-0.5 rounded">
                {r}
                <button onClick={() => setInformedRoles(informedRoles.filter(x => x !== r))} className="text-purple-300 hover:text-red-500 leading-none">×</button>
              </span>
            ))}
          </div>
          <div className="flex gap-2">
            <select value={newInformed} onChange={e => setNewInformed(e.target.value)}
              className="flex-1 text-xs border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400">
              <option value="">+ Add informed role</option>
              {roleOptions.filter(r => !informedRoles.includes(r.key)).map(r =>
                <option key={r.key} value={r.key}>{r.label}</option>
              )}
            </select>
            <button onClick={() => addTag(informedRoles, setInformedRoles, newInformed, setNewInformed)}
              disabled={!newInformed}
              className="text-xs bg-gray-100 hover:bg-gray-200 px-3 py-1.5 rounded disabled:opacity-40 transition">Add</button>
          </div>
        </div>

        {/* Observer roles */}
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Observer roles — read-only access, no notifications</label>
          <div className="flex flex-wrap gap-1 mb-1">
            {observerRoles.map(r => (
              <span key={r} className="flex items-center gap-1 text-xs bg-gray-100 border border-gray-200 text-gray-700 px-2 py-0.5 rounded">
                {r}
                <button onClick={() => setObserverRoles(observerRoles.filter(x => x !== r))} className="text-gray-400 hover:text-red-500 leading-none">×</button>
              </span>
            ))}
          </div>
          <div className="flex gap-2">
            <select value={newObserver} onChange={e => setNewObserver(e.target.value)}
              className="flex-1 text-xs border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400">
              <option value="">+ Add observer role</option>
              {roleOptions.filter(r => !observerRoles.includes(r.key)).map(r =>
                <option key={r.key} value={r.key}>{r.label}</option>
              )}
            </select>
            <button onClick={() => addTag(observerRoles, setObserverRoles, newObserver, setNewObserver)}
              disabled={!newObserver}
              className="text-xs bg-gray-100 hover:bg-gray-200 px-3 py-1.5 rounded disabled:opacity-40 transition">Add</button>
          </div>
        </div>

        {/* PII access toggle */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setInformedPii(!informedPii)}
            className={`relative inline-flex h-5 w-9 shrink-0 rounded-full border-2 border-transparent transition-colors ${informedPii ? "bg-purple-600" : "bg-gray-200"}`}
          >
            <span className={`inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform ${informedPii ? "translate-x-4" : "translate-x-0"}`} />
          </button>
          <span className="text-xs text-gray-600">
            Informed tier can see complainant PII
            <span className="text-gray-400 ml-1">(default: off)</span>
          </span>
        </div>
      </div>

      <div className="flex justify-end gap-2 pt-1">
        <button onClick={onCancel} className="text-xs text-gray-500 hover:text-gray-700 px-3 py-1.5 rounded transition">Cancel</button>
        <button onClick={handleSave} disabled={saving}
          className="text-xs bg-blue-600 text-white hover:bg-blue-700 px-4 py-1.5 rounded font-medium disabled:opacity-50 transition">
          {saving ? "Saving…" : "Save step"}
        </button>
      </div>
    </div>
  );
}

// ── Project workflow picker (Settings → Projects) ─────────────────────────────

function ProjectWorkflowSelect({
  label,
  hint,
  workflowType,
  value,
  workflows,
  disabled,
  onChange,
  onCreateNew,
}: {
  label: string;
  hint: string;
  workflowType: "standard" | "seah";
  value: string | null | undefined;
  workflows: WorkflowDefinition[];
  disabled?: boolean;
  onChange: (workflowId: string | null) => void;
  onCreateNew: () => void;
}) {
  const options = workflows.filter(
    (w) => !w.is_template && w.status !== "archived" && w.workflow_type.toLowerCase() === workflowType,
  );
  const selected = value ? options.find((w) => w.workflow_id === value) : undefined;

  return (
    <div>
      <label className="text-xs font-medium text-gray-600 block mb-1">{label}</label>
      <p className="text-xs text-gray-400 mb-2">{hint}</p>
      <select
        value={value ?? ""}
        disabled={disabled}
        onChange={(e) => {
          const v = e.target.value;
          if (v === "__new__") {
            onCreateNew();
            return;
          }
          onChange(v ? v : null);
        }}
        className="w-full max-w-lg text-sm border border-gray-300 rounded px-2 py-2 focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:opacity-50"
      >
        <option value="">— Not set —</option>
        {options.map((w) => (
          <option key={w.workflow_id} value={w.workflow_id}>
            {w.display_name} ({w.status})
          </option>
        ))}
        <option value="__new__">+ Create new workflow…</option>
      </select>
      {selected && (
        <p className="text-xs text-gray-500 mt-1 font-mono">{selected.workflow_key}</p>
      )}
    </div>
  );
}

// ── Workflow editor ───────────────────────────────────────────────────────────

function WorkflowEditor({
  workflow: initial,
  roleOptions,
  canCreateRole,
  onRoleCatalogRefresh,
  onBack,
  onUpdated,
}: {
  workflow: WorkflowDefinition;
  roleOptions: WorkflowRoleOption[];
  canCreateRole?: boolean;
  onRoleCatalogRefresh?: () => void;
  onBack: () => void;
  onUpdated: (w: WorkflowDefinition) => void;
}) {
  const [wf, setWf]               = useState<WorkflowDefinition>(initial);
  const [expandedStep, setExpanded] = useState<string | null>(null);
  const [editingName, setEditingName] = useState(false);
  const [nameVal, setNameVal]       = useState(wf.display_name);
  const [publishing, setPublishing] = useState(false);
  const [archiving, setArchiving]   = useState(false);
  const [savingTemplate, setSavingTemplate] = useState(false);
  const [addingStep, setAddingStep] = useState(false);
  const [msg, setMsg]               = useState("");

  const isTemplate = wf.is_template;
  const steps = wf.steps.filter(s => !s.is_deleted).sort((a, b) => a.step_order - b.step_order);

  function flash(text: string) { setMsg(text); setTimeout(() => setMsg(""), 2500); }

  async function handlePublish() {
    const missing = steps.filter((s) => !s.assigned_role_key);
    if (missing.length) {
      flash(`Assign a role to every step before publishing (${missing.length} missing)`);
      return;
    }
    setPublishing(true);
    try { const updated = await publishWorkflow(wf.workflow_id); setWf(updated); onUpdated(updated); flash("Published ✓"); }
    catch (e: unknown) { flash(e instanceof Error ? e.message : "Publish failed"); }
    finally { setPublishing(false); }
  }

  async function handleArchive() {
    if (!confirm("Archive this workflow? It won't be used for new tickets.")) return;
    setArchiving(true);
    try { const updated = await archiveWorkflow(wf.workflow_id); setWf(updated); onUpdated(updated); flash("Archived"); }
    catch (e: unknown) { flash(e instanceof Error ? e.message : "Archive failed"); }
    finally { setArchiving(false); }
  }

  async function handleRename() {
    if (!nameVal.trim() || nameVal === wf.display_name) { setEditingName(false); return; }
    try {
      const updated = await updateWorkflow(wf.workflow_id, { display_name: nameVal.trim() });
      setWf(updated); onUpdated(updated); flash("Renamed ✓");
    } catch { /* ignore */ }
    setEditingName(false);
  }

  async function handleMoveUp(idx: number) {
    if (idx === 0) return;
    const newOrder = [...steps];
    [newOrder[idx - 1], newOrder[idx]] = [newOrder[idx], newOrder[idx - 1]];
    const ids = newOrder.map(s => s.step_id);
    const updated = await reorderSteps(wf.workflow_id, ids);
    setWf(prev => ({ ...prev, steps: updated }));
  }

  async function handleMoveDown(idx: number) {
    if (idx === steps.length - 1) return;
    const newOrder = [...steps];
    [newOrder[idx], newOrder[idx + 1]] = [newOrder[idx + 1], newOrder[idx]];
    const ids = newOrder.map(s => s.step_id);
    const updated = await reorderSteps(wf.workflow_id, ids);
    setWf(prev => ({ ...prev, steps: updated }));
  }

  async function handleDeleteStep(step: WorkflowStep) {
    if (!confirm(`Remove step "${step.display_name}"? This cannot be undone if tickets are active on it.`)) return;
    try {
      await deleteStep(wf.workflow_id, step.step_id);
      setWf(prev => ({ ...prev, steps: prev.steps.map(s => s.step_id === step.step_id ? { ...s, is_deleted: true } : s) }));
      flash("Step removed");
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Cannot delete step");
    }
  }

  async function handleAddStep() {
    setAddingStep(true);
    try {
      const newStep = await addStep(wf.workflow_id, {
        display_name: `Step ${steps.length + 1}`,
        assigned_role_key: "site_safeguards_focal_person",
      });
      setWf(prev => ({ ...prev, steps: [...prev.steps, newStep] }));
      setExpanded(newStep.step_id);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Failed to add step");
    } finally { setAddingStep(false); }
  }

  async function handleSaveAsTemplate() {
    const defaultName = `${wf.display_name} (template)`;
    const name = window.prompt("Template name", defaultName);
    if (name === null) return;
    const trimmed = name.trim();
    if (!trimmed) return;
    setSavingTemplate(true);
    try {
      const tpl = await saveWorkflowAsTemplate(wf.workflow_id, { display_name: trimmed });
      flash(`Template created: ${tpl.display_name}`);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Failed to save template");
    } finally {
      setSavingTemplate(false);
    }
  }

  function handleStepSaved(updated: WorkflowStep) {
    setWf(prev => ({ ...prev, steps: prev.steps.map(s => s.step_id === updated.step_id ? updated : s) }));
    setExpanded(null);
    flash("Step saved ✓");
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-start justify-between mb-5">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="text-gray-400 hover:text-gray-600 text-sm flex items-center gap-1">
            ← <span>{isTemplate ? "Templates" : "Workflows"}</span>
          </button>
          <span className="text-gray-300">/</span>
          {editingName ? (
            <input autoFocus value={nameVal} onChange={e => setNameVal(e.target.value)}
              onBlur={handleRename} onKeyDown={e => e.key === "Enter" && handleRename()}
              className="text-lg font-semibold text-gray-800 border-b-2 border-blue-400 bg-transparent focus:outline-none" />
          ) : (
            <h2 className="text-lg font-semibold text-gray-800 cursor-pointer hover:text-blue-600" onClick={() => setEditingName(true)} title="Click to rename">
              {wf.display_name}
            </h2>
          )}
          {wf.workflow_type === "seah" && <span className="inline-flex items-center gap-0.5 text-xs text-red-600"><Lock size={10} strokeWidth={2.5} />SEAH</span>}
          {isTemplate && <span className="text-xs font-medium px-2 py-0.5 rounded bg-blue-100 text-blue-700">Template</span>}
        </div>
        <div className="flex items-center gap-3 flex-wrap justify-end">
          {msg && <span className="text-xs text-green-600 font-medium">{msg}</span>}
          <span className={`text-xs font-medium px-2 py-0.5 rounded ${statusBadge(wf.status)}`}>{wf.status}</span>
          <span className="text-xs text-gray-400">v{wf.version}</span>
          {!isTemplate && wf.status !== "archived" && (
            <button type="button" onClick={handlePublish} disabled={publishing}
              className="text-sm bg-green-600 text-white hover:bg-green-700 px-4 py-1.5 rounded font-medium disabled:opacity-50 transition">
              {publishing ? "Publishing…" : wf.status === "published" ? "Re-publish" : "Publish"}
            </button>
          )}
          {!isTemplate && wf.status === "published" && (
            <button type="button" onClick={handleArchive} disabled={archiving}
              className="text-sm text-gray-500 hover:text-gray-700 border border-gray-300 px-3 py-1.5 rounded transition">
              {archiving ? "Archiving…" : "Archive"}
            </button>
          )}
          {!isTemplate && (
            <button
              type="button"
              onClick={handleSaveAsTemplate}
              disabled={savingTemplate}
              className="text-sm text-blue-700 hover:text-blue-900 border border-blue-200 bg-blue-50 px-3 py-1.5 rounded transition disabled:opacity-50"
            >
              {savingTemplate ? "Saving…" : "Save as template"}
            </button>
          )}
        </div>
      </div>

      {/* Meta info */}
      <div className="flex items-center gap-4 mb-6 text-xs text-gray-500">
        <span>Type: <span className={`font-medium px-1.5 py-0.5 rounded ${typeBadge(wf.workflow_type)}`}>{wf.workflow_type.toUpperCase()}</span></span>
        <span>Key: <code className="text-gray-600 bg-gray-100 px-1.5 py-0.5 rounded">{wf.workflow_key}</code></span>
        {wf.description && <span className="text-gray-400 italic">{wf.description}</span>}
      </div>

      {/* Steps */}
      <div className="space-y-2 mb-4">
        {steps.map((step, idx) => (
          <div key={step.step_id} className="border border-gray-200 rounded-lg overflow-hidden">
            {/* Step row */}
            <div className="flex items-center gap-3 px-4 py-3 bg-white hover:bg-gray-50">
              {/* Reorder */}
              <div className="flex flex-col gap-0.5 shrink-0">
                <button onClick={() => handleMoveUp(idx)} disabled={idx === 0}
                  className="text-gray-400 hover:text-gray-700 disabled:opacity-20 text-xs leading-none">▲</button>
                <button onClick={() => handleMoveDown(idx)} disabled={idx === steps.length - 1}
                  className="text-gray-400 hover:text-gray-700 disabled:opacity-20 text-xs leading-none">▼</button>
              </div>

              {/* Step number */}
              <span className="w-6 h-6 rounded-full bg-slate-700 text-white text-xs flex items-center justify-center font-medium shrink-0">
                {idx + 1}
              </span>

              {/* Step info */}
              <div className="flex-1 min-w-0">
                <div className="font-medium text-gray-800 text-sm">{step.display_name}</div>
                <div className="text-xs text-gray-400 mt-0.5 flex items-center gap-3">
                  <span>Role: <code>{step.assigned_role_key}</code></span>
                  {step.response_time_hours != null && <span>Response: {step.response_time_hours}h</span>}
                  {step.resolution_time_days != null && <span>Resolution: {step.resolution_time_days}d</span>}
                  {step.response_time_hours == null && step.resolution_time_days == null && <span className="italic">No SLA</span>}
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => setExpanded(expandedStep === step.step_id ? null : step.step_id)}
                  className="text-xs text-blue-600 hover:underline px-2 py-1">
                  {expandedStep === step.step_id ? "Collapse" : "Edit"}
                </button>
                <button onClick={() => handleDeleteStep(step)}
                  className="text-xs text-gray-400 hover:text-red-500 px-1 py-1 leading-none">✕</button>
              </div>
            </div>

            {/* Accordion */}
            {expandedStep === step.step_id && (
              <div className="px-4 pb-4">
                <StepForm
                  step={step}
                  workflowId={wf.workflow_id}
                  roleOptions={roleOptions}
                  canCreateRole={canCreateRole}
                  onRoleCreated={onRoleCatalogRefresh}
                  onSaved={handleStepSaved}
                  onCancel={() => setExpanded(null)}
                />
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Add step */}
      <button onClick={handleAddStep} disabled={addingStep}
        className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 border border-dashed border-blue-300 hover:border-blue-500 rounded-lg px-4 py-2.5 w-full justify-center transition disabled:opacity-50">
        {addingStep ? "Adding…" : "+ Add step"}
      </button>

      {!isTemplate && (
        <div className="mt-6 border-t border-gray-200 pt-5">
          <p className="text-xs text-gray-500">
            Assign this workflow on a project under{" "}
            <span className="font-medium">Settings → Projects &amp; packages</span>
            {" "}(Standard / SEAH). New tickets use the workflows selected on their project.
          </p>
        </div>
      )}

      {/* Notification rules (Spec 12 §4) */}
      {!isTemplate && (
        <WorkflowNotificationsPanel workflowSlug={wf.workflow_type === "seah" ? "seah" : "standard"} />
      )}
    </div>
  );
}

// ── Workflow Notifications Panel (Spec 12 §4) ─────────────────────────────────

const NOTIFICATION_EVENTS: { key: string; label: string }[] = [
  { key: "ticket_created",   label: "Ticket created"     },
  { key: "ticket_escalated", label: "Ticket escalated"   },
  { key: "ticket_resolved",  label: "Ticket resolved"    },
  { key: "sla_breach",       label: "SLA breach"         },
  { key: "grc_convened",     label: "GRC convened"       },
  { key: "assignment",       label: "Assignment"         },
  { key: "quarterly_report", label: "Quarterly report"   },
];
const SEAH_EVENTS = new Set(["ticket_created","ticket_escalated","ticket_resolved","sla_breach","assignment"]);
const NOTIF_TIERS = ["actor","supervisor","informed","observer"] as const;
const NOTIF_CHANNELS = ["app","email","sms"] as const;

function WorkflowNotificationsPanel({ workflowSlug }: { workflowSlug: "standard" | "seah" }) {
  const [open, setOpen] = useState(false);
  const [rules, setRules] = useState<Record<string, Record<string, string[]>>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(false);

  const events = workflowSlug === "seah"
    ? NOTIFICATION_EVENTS.filter(e => SEAH_EVENTS.has(e.key))
    : NOTIFICATION_EVENTS;

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    fetch("/api/v1/settings/notification_rules")
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.value) setRules(data.value[workflowSlug] ?? {});
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [open, workflowSlug]);

  function toggle(event: string, tier: string, channel: string) {
    setRules(prev => {
      const evRules = { ...prev };
      const tierChannels: string[] = [...(evRules[event]?.[tier] ?? [])];
      const idx = tierChannels.indexOf(channel);
      if (idx >= 0) tierChannels.splice(idx, 1); else tierChannels.push(channel);
      return { ...evRules, [event]: { ...(evRules[event] ?? {}), [tier]: tierChannels } };
    });
  }

  async function handleSave() {
    setSaving(true);
    try {
      const current = await fetch("/api/v1/settings/notification_rules").then(r => r.json());
      const fullValue = { ...(current?.value ?? {}), [workflowSlug]: rules };
      await fetch("/api/v1/settings/notification_rules", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value: fullValue }),
      });
      setSaved(true); setTimeout(() => setSaved(false), 2000);
    } catch { /* ignore */ } finally { setSaving(false); }
  }

  const isChecked = (event: string, tier: string, ch: string) =>
    (rules[event]?.[tier] ?? []).includes(ch);

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden mt-2">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition text-sm font-medium text-gray-700"
      >
        <span>Notification rules — {workflowSlug === "seah" ? "SEAH" : "Standard"}</span>
        <span className="text-gray-400 text-xs">{open ? "▲ collapse" : "▼ expand"}</span>
      </button>

      {open && (
        <div className="p-4">
          {loading ? (
            <div className="text-xs text-gray-400 text-center py-4">Loading…</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr>
                    <th className="text-left font-medium text-gray-500 pb-2 pr-4 whitespace-nowrap">Event</th>
                    {NOTIF_TIERS.map(tier => (
                      <th key={tier} className="text-center font-medium text-gray-500 pb-2 px-2 capitalize min-w-[90px]" colSpan={3}>
                        {tier}
                      </th>
                    ))}
                  </tr>
                  <tr>
                    <th />
                    {NOTIF_TIERS.map(tier =>
                      NOTIF_CHANNELS.map(ch => (
                        <th key={`${tier}-${ch}`} className="text-center text-[10px] text-gray-400 pb-2 px-1 uppercase">{ch}</th>
                      ))
                    )}
                  </tr>
                </thead>
                <tbody>
                  {events.map((ev, i) => (
                    <tr key={ev.key} className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                      <td className="py-1.5 pr-4 font-medium text-gray-700 whitespace-nowrap">{ev.label}</td>
                      {NOTIF_TIERS.map(tier =>
                        NOTIF_CHANNELS.map(ch => (
                          <td key={`${tier}-${ch}`} className="text-center py-1.5 px-1">
                            <button
                              type="button"
                              onClick={() => toggle(ev.key, tier, ch)}
                              className={`w-5 h-5 rounded border flex items-center justify-center mx-auto transition ${
                                isChecked(ev.key, tier, ch)
                                  ? "bg-blue-600 border-blue-600 text-white"
                                  : "border-gray-300 text-transparent hover:border-blue-400"
                              }`}
                            >
                              ✓
                            </button>
                          </td>
                        ))
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="flex justify-between items-center mt-4 pt-3 border-t border-gray-100">
            <p className="text-[11px] text-gray-400">Changes apply to new events only — in-flight tickets unaffected.</p>
            <button onClick={handleSave} disabled={saving || loading}
              className={`text-xs px-4 py-1.5 rounded font-medium transition ${
                saved ? "bg-green-600 text-white" : "bg-blue-600 text-white hover:bg-blue-700"
              } disabled:opacity-50`}>
              {saved ? "✓ Saved" : saving ? "Saving…" : "Save rules"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── New workflow modal ────────────────────────────────────────────────────────

function NewWorkflowModal({
  mode = "workflow",
  templates,
  canSeeSeah,
  initialCloneFrom,
  fixedWorkflowType,
  onCreated,
  onClose,
}: {
  mode?: "workflow" | "template";
  templates: WorkflowDefinition[];
  canSeeSeah: boolean;
  initialCloneFrom?: string;
  /** When set (e.g. from Project editor), lock workflow type to standard or seah. */
  fixedWorkflowType?: "standard" | "seah";
  onCreated: (w: WorkflowDefinition) => void;
  onClose: () => void;
}) {
  const isTemplateMode = mode === "template";
  const [name, setName]             = useState("");
  const [wfType, setWfType]         = useState<string>(fixedWorkflowType ?? "standard");
  const [cloneFrom, setCloneFrom]   = useState(initialCloneFrom ?? "__builtin_default_grm");
  const [creating, setCreating]     = useState(false);
  const [error, setError]           = useState("");

  const builtIns = [
    { id: "__builtin_default_grm",  label: "Default GRM (4 steps)",  type: "standard" },
    ...(canSeeSeah ? [{ id: "__builtin_default_seah", label: "Default SEAH (2 steps)", type: "seah" }] : []),
    { id: "",  label: "Blank (0 steps)",  type: "any" },
  ];

  const adminTemplates = templates.filter(t => canSeeSeah || t.workflow_type !== "seah");

  async function handleCreate() {
    if (!name.trim()) {
      setError(isTemplateMode ? "Template name is required." : "Workflow name is required.");
      return;
    }
    setCreating(true); setError("");
    try {
      const created = await createWorkflow({
        display_name: name.trim(),
        workflow_type: wfType,
        clone_from_id: cloneFrom || undefined,
        is_template: isTemplateMode,
      });
      onCreated(created);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Create failed");
      setCreating(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 overflow-hidden">
        <div className="bg-slate-700 text-white px-6 py-4 flex items-center justify-between">
          <div className="font-semibold">{isTemplateMode ? "New template" : "New workflow"}</div>
          <button onClick={onClose} className="text-slate-300 hover:text-white text-xl leading-none">×</button>
        </div>

        <div className="p-6 space-y-4">
          {error && <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>}

          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">{isTemplateMode ? "Template name *" : "Workflow name *"}</label>
            <input autoFocus value={name} onChange={e => setName(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleCreate()}
              placeholder={isTemplateMode ? "e.g. KL Road GRM template" : "e.g. KL Road Standard GRM"}
              className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
          </div>

          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Type</label>
            {fixedWorkflowType ? (
              <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${typeBadge(fixedWorkflowType)}`}>
                {fixedWorkflowType.toUpperCase()}
              </span>
            ) : (
              <div className="flex gap-3">
                {["standard", ...(canSeeSeah ? ["seah"] : [])].map(t => (
                  <label key={t} className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="radio" value={t} checked={wfType === t} onChange={() => { setWfType(t); if (t === "seah") setCloneFrom("__builtin_default_seah"); else setCloneFrom("__builtin_default_grm"); }} />
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${typeBadge(t)}`}>{t.toUpperCase()}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-2">Start from template</label>
            <div className="space-y-1.5">
              {builtIns.filter(b => b.type === "any" || b.type === wfType || b.type === "standard").map(b => (
                <label key={b.id} className={`flex items-center gap-3 border rounded-lg px-3 py-2 cursor-pointer transition ${cloneFrom === b.id ? "border-blue-400 bg-blue-50" : "border-gray-200 hover:border-gray-300"}`}>
                  <input type="radio" value={b.id} checked={cloneFrom === b.id} onChange={() => setCloneFrom(b.id)} className="shrink-0" />
                  <span className="text-sm text-gray-700">{b.label}</span>
                </label>
              ))}
              {adminTemplates.map(t => (
                <label key={t.workflow_id} className={`flex items-center gap-3 border rounded-lg px-3 py-2 cursor-pointer transition ${cloneFrom === t.workflow_id ? "border-blue-400 bg-blue-50" : "border-gray-200 hover:border-gray-300"}`}>
                  <input type="radio" value={t.workflow_id} checked={cloneFrom === t.workflow_id} onChange={() => setCloneFrom(t.workflow_id)} className="shrink-0" />
                  <span className="text-sm text-gray-700">{t.display_name} <span className="text-xs text-gray-400">({t.steps.length} steps)</span></span>
                </label>
              ))}
            </div>
          </div>
        </div>

        <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-3">
          <button onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700 px-4 py-1.5 rounded transition">Cancel</button>
          <button onClick={handleCreate} disabled={creating || !name.trim()}
            className="text-sm bg-blue-600 text-white hover:bg-blue-700 px-4 py-1.5 rounded font-medium disabled:opacity-50 transition">
            {creating ? "Creating…" : "Create workflow"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Workflows tab ─────────────────────────────────────────────────────────────

function WorkflowsTab({
  roleCatalog,
  canCreateRole,
  onRoleCatalogRefresh,
}: {
  roleCatalog: RoleEntry[];
  canCreateRole: boolean;
  onRoleCatalogRefresh: () => void;
}) {
  const { canSeeSeah } = useAuth();
  const [workflows, setWorkflows]     = useState<WorkflowDefinition[]>([]);
  const [templates, setTemplates]     = useState<WorkflowDefinition[]>([]);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState("");
  const [editing, setEditing]         = useState<WorkflowDefinition | null>(null);
  const [showNewModal, setShowNewModal] = useState(false);
  const [newModalMode, setNewModalMode] = useState<"workflow" | "template">("workflow");
  const [clonePreset, setClonePreset] = useState<string | undefined>(undefined);
  const [search, setSearch]           = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [wfRes, tplRes] = await Promise.all([listWorkflows(), listTemplates()]);
      setWorkflows(wfRes.items.filter((w) => !w.is_template));
      setTemplates(tplRes.items.filter(t => t.is_template));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load workflows");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function openEditor(wf: WorkflowDefinition) {
    if (wf.workflow_id.startsWith("__builtin_")) return;
    try {
      const full = await getWorkflow(wf.workflow_id);
      setEditing(full);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to open workflow");
    }
  }

  async function handleRemoveWorkflow(wf: WorkflowDefinition) {
    if (wf.workflow_id.startsWith("__builtin_")) return;
    if (wf.status === "published") {
      if (!confirm(`Archive "${wf.display_name}"? It will no longer be used for new tickets.`)) return;
      try {
        await archiveWorkflow(wf.workflow_id);
        await load();
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Archive failed");
      }
      return;
    }
    if (!confirm(`Permanently remove "${wf.display_name}"? This cannot be undone.`)) return;
    try {
      await deleteWorkflow(wf.workflow_id);
      setWorkflows((prev) => prev.filter((w) => w.workflow_id !== wf.workflow_id));
      if (editing?.workflow_id === wf.workflow_id) setEditing(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Remove failed");
    }
  }

  const wfRoleOptions: WorkflowRoleOption[] = useMemo(() => {
    const wfType = editing?.workflow_type ?? "standard";
    return roleCatalog
      .filter((r) => {
        if (wfType === "seah") return r.workflow === "SEAH" || r.workflow === "Both";
        return r.workflow === "Standard" || r.workflow === "Both";
      })
      .map((r) => ({ key: r.key, label: r.label, origin: r.role_origin }));
  }, [roleCatalog, editing?.workflow_type]);

  // Editor view
  if (editing) {
    return (
      <WorkflowEditor
        workflow={editing}
        roleOptions={wfRoleOptions}
        canCreateRole={canCreateRole}
        onRoleCatalogRefresh={onRoleCatalogRefresh}
        onBack={() => { setEditing(null); load(); }}
        onUpdated={updated => setEditing(updated)}
      />
    );
  }

  const visible = workflows.filter(w => {
    if (!canSeeSeah && w.workflow_type === "seah") return false;
    if (search && !w.display_name.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  // Templates come entirely from the API (built-ins included)
  const allTemplates = templates.filter(t => canSeeSeah || t.workflow_type !== "seah");

  return (
    <div>
      {showNewModal && (
        <NewWorkflowModal
          mode={newModalMode}
          templates={templates}
          canSeeSeah={!!canSeeSeah}
          initialCloneFrom={clonePreset}
          onCreated={w => {
            setShowNewModal(false);
            setClonePreset(undefined);
            if (w.is_template) {
              setTemplates((prev) => [...prev.filter((t) => t.workflow_id !== w.workflow_id), w]);
            } else {
              setWorkflows((prev) => [...prev, w]);
            }
            setEditing(w);
          }}
          onClose={() => { setShowNewModal(false); setClonePreset(undefined); }}
        />
      )}

      {/* Toolbar */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <input
            value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search workflows…"
            className="text-sm border border-gray-300 rounded px-3 py-1.5 w-56 focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
          {loading && <span className="text-xs text-gray-400 animate-pulse">Loading…</span>}
          {error && <span className="text-xs text-red-500">{error}</span>}
        </div>
        <button
          type="button"
          onClick={() => { setNewModalMode("workflow"); setClonePreset(undefined); setShowNewModal(true); }}
          className="bg-blue-600 text-white text-sm px-4 py-1.5 rounded hover:bg-blue-700 transition font-medium">
          + New workflow
        </button>
      </div>

      {/* Workflow list */}
      {!loading && visible.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          <ClipboardList size={36} strokeWidth={1.25} className="mx-auto mb-3 text-gray-300" />
          <p className="text-sm">No workflows yet. Create one to get started.</p>
        </div>
      )}

      <div className="border border-gray-200 rounded-lg overflow-hidden divide-y divide-gray-100">
        {visible.map(wf => (
          <div key={wf.workflow_id} className="flex items-center gap-4 px-5 py-3.5 hover:bg-gray-50 transition">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-medium text-gray-800 text-sm">{wf.display_name}</span>
                {wf.workflow_type === "seah" && <Lock size={11} strokeWidth={2.5} className="text-red-500 shrink-0" />}
              </div>
              <div className="text-xs text-gray-400 mt-0.5">
                {wf.steps.filter(s => s && !s.is_deleted).length} steps
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className={`text-xs px-2 py-0.5 rounded font-medium ${typeBadge(wf.workflow_type)}`}>
                {wf.workflow_type.toUpperCase()}
              </span>
              <span className="text-xs text-gray-400">v{wf.version}</span>
              <span className={`text-xs px-2 py-0.5 rounded font-medium ${statusBadge(wf.status)}`}>
                {wf.status.charAt(0).toUpperCase() + wf.status.slice(1)}
              </span>
              <button type="button" onClick={() => openEditor(wf)}
                className="text-sm text-blue-600 hover:underline ml-2">Edit</button>
              <button type="button" onClick={() => handleRemoveWorkflow(wf)}
                className="text-sm text-red-600 hover:underline ml-2">
                {wf.status === "published" ? "Archive" : "Remove"}
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Templates section */}
      <div className="mt-8">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Templates</h3>
          <button
            type="button"
            onClick={() => { setNewModalMode("template"); setClonePreset(undefined); setShowNewModal(true); }}
            className="text-sm bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700 font-medium"
          >
            + New template
          </button>
        </div>
      {allTemplates.length > 0 ? (
          <div className="border border-gray-200 rounded-lg overflow-hidden divide-y divide-gray-100">
            {allTemplates.map(tpl => (
              <div key={tpl.workflow_id} className="flex items-center gap-4 px-5 py-3.5 hover:bg-gray-50 transition">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-800 text-sm">{tpl.display_name}</span>
                    {tpl.workflow_type === "seah" && <Lock size={11} strokeWidth={2.5} className="text-red-500 shrink-0" />}
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5">
                    {tpl.steps.filter(s => s && !s.is_deleted).length} steps · {tpl.workflow_id.startsWith("__builtin_") ? "built-in" : "admin template"}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className={`text-xs px-2 py-0.5 rounded font-medium ${typeBadge(tpl.workflow_type)}`}>
                    {tpl.workflow_type.toUpperCase()}
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded font-medium bg-blue-100 text-blue-700">Template</span>
                  {!tpl.workflow_id.startsWith("__builtin_") && (
                    <button type="button" onClick={() => openEditor(tpl)}
                      className="text-sm text-blue-600 hover:underline ml-2">Edit</button>
                  )}
                  <button
                    type="button"
                    onClick={() => {
                      setNewModalMode("workflow");
                      setClonePreset(tpl.workflow_id);
                      setShowNewModal(true);
                    }}
                    className="text-sm text-blue-600 hover:underline ml-2"
                  >
                    Clone
                  </button>
                  {!tpl.workflow_id.startsWith("__builtin_") && (
                    <button
                      type="button"
                      onClick={() => handleRemoveWorkflow(tpl)}
                      className="text-sm text-red-600 hover:underline ml-2"
                    >
                      Remove
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
      ) : (
        <p className="text-sm text-gray-400 border border-dashed border-gray-200 rounded-lg px-4 py-6 text-center">
          No custom templates yet. Create one or use <strong>Save as template</strong> from a workflow.
        </p>
      )}
      </div>
    </div>
  );
}

// ── Organizations section ─────────────────────────────────────────────────────

function OrgsSection({ onNavigateToProject }: { onNavigateToProject: (id: string) => void }) {
  const [orgs, setOrgs]           = useState<OrganizationItem[]>([]);
  const [countries, setCountries] = useState<CountryItem[]>([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing]     = useState<OrganizationItem | null>(null);

  async function load() {
    setLoading(true);
    try {
      const [o, c] = await Promise.all([listOrganizations(), listCountries()]);
      setOrgs(o);
      setCountries(c);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleRemoveOrg(o: OrganizationItem) {
    if (!confirm(`Remove organization "${o.name}" (${o.organization_id})? This cannot be undone.`)) return;
    try {
      await deleteOrganization(o.organization_id);
      if (editing?.organization_id === o.organization_id) setEditing(null);
      setOrgs((prev) => prev.filter((x) => x.organization_id !== o.organization_id));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Remove failed");
    }
  }

  if (editing) {
    return (
      <OrgEditor
        org={editing}
        countries={countries}
        onBack={() => { setEditing(null); load(); }}
        onUpdated={(updated) => setEditing(updated)}
        onNavigateToProject={onNavigateToProject}
      />
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-gray-500">{orgs.length} organization{orgs.length !== 1 ? "s" : ""}</p>
        <button
          onClick={() => setShowCreate(true)}
          className="bg-blue-600 text-white text-sm px-4 py-1.5 rounded font-medium hover:bg-blue-700 transition"
        >
          + Add Organization
        </button>
      </div>

      {showCreate && (
        <OrgCreateModal
          countries={countries}
          existingOrganizationIds={new Set(orgs.map((o) => o.organization_id))}
          onCreated={(org) => { setShowCreate(false); setOrgs((prev) => [...prev, org]); setEditing(org); }}
          onClose={() => setShowCreate(false)}
        />
      )}

      {loading && <p className="text-sm text-gray-400 animate-pulse">Loading…</p>}
      {error   && <p className="text-sm text-red-500">{error}</p>}

      {!loading && !error && (
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-700 text-slate-100 text-left">
                <th className="px-4 py-2.5 font-medium">ID</th>
                <th className="px-4 py-2.5 font-medium">Name</th>
                <th className="px-4 py-2.5 font-medium">Country</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {orgs.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-400">No organizations yet.</td></tr>
              )}
              {orgs.map((o) => (
                <tr key={o.organization_id} className="border-t border-gray-100 hover:bg-gray-50">
                  <td className="px-4 py-2.5 font-mono text-xs text-gray-600">{o.organization_id}</td>
                  <td className="px-4 py-2.5 font-medium text-gray-800">{o.name}</td>
                  <td className="px-4 py-2.5 text-gray-500">{o.country_code ?? <span className="text-gray-300">—</span>}</td>
                  <td className="px-4 py-2.5">
                    <span className={`text-xs font-medium ${o.is_active ? "text-green-600" : "text-gray-400"}`}>
                      {o.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right whitespace-nowrap">
                    <button type="button" onClick={() => setEditing(o)} className="text-xs text-blue-600 hover:underline mr-3">
                      Edit
                    </button>
                    <button type="button" onClick={() => handleRemoveOrg(o)} className="text-xs text-red-600 hover:underline">
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}


// ── Org editor ────────────────────────────────────────────────────────────────

function OrgEditor({
  org: initial,
  countries,
  onBack,
  onUpdated,
  onNavigateToProject,
}: {
  org: OrganizationItem;
  countries: CountryItem[];
  onBack: () => void;
  onUpdated: (o: OrganizationItem) => void;
  onNavigateToProject: (id: string) => void;
}) {
  const [org, setOrg]       = useState<OrganizationItem>(initial);
  const [nameVal, setNameVal] = useState(org.name);
  const [countryVal, setCountryVal] = useState(org.country_code ?? "");
  const [activeVal, setActiveVal]   = useState(org.is_active);
  const [msg, setMsg]       = useState("");
  const [dirty, setDirty]   = useState(false);
  const [saving, setSaving] = useState(false);

  // Project-linking state
  const [allProjects, setAllProjects] = useState<ProjectItem[]>([]);
  const [orgRoles, setOrgRoles]       = useState<OrgRole[]>([]);
  const [linkedProjects, setLinkedProjects] = useState<ProjectItem[]>([]);
  const [projectsLoading, setProjectsLoading] = useState(true);
  // Packages where this org is the contractor, keyed by project_id (read-only context)
  const [packagesByProject, setPackagesByProject] = useState<Record<string, PackageItem[]>>({});

  function flash(t: string) { setMsg(t); setTimeout(() => setMsg(""), 2500); }

  useEffect(() => {
    Promise.all([listProjects(), getOrgRoles().catch(() => [] as OrgRole[])])
      .then(([all, roles]) => {
        setAllProjects(all);
        setOrgRoles(roles);
        setLinkedProjects(all.filter((p) => p.organizations.some((o) => o.organization_id === org.organization_id)));
      })
      .finally(() => setProjectsLoading(false));
  }, [org.organization_id]);

  // Load packages for each linked project — show read-only contractor context
  useEffect(() => {
    if (linkedProjects.length === 0) { setPackagesByProject({}); return; }
    Promise.all(
      linkedProjects.map((proj) =>
        listPackages(proj.project_id)
          .then((pkgs) => [
            proj.project_id,
            pkgs.filter((pkg) =>
              (pkg.organizations ?? []).some((o) => o.organization_id === org.organization_id),
            ),
          ] as [string, PackageItem[]])
          .catch(() => [proj.project_id, []] as [string, PackageItem[]])
      )
    ).then((entries) => setPackagesByProject(Object.fromEntries(entries)));
  }, [linkedProjects, org.organization_id]);

  async function handleSaveMeta() {
    if (!nameVal.trim()) return;
    setSaving(true);
    try {
      const updated = await updateOrganization(org.organization_id, {
        name: nameVal.trim(),
        country_code: countryVal || null,
        is_active: activeVal,
      });
      setOrg(updated); onUpdated(updated); setDirty(false); flash("Saved ✓");
    } catch { flash("Save failed"); }
    setSaving(false);
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button onClick={onBack} className="text-gray-400 hover:text-gray-600 text-sm flex items-center gap-1">← Organizations</button>
        <span className="text-gray-300">/</span>
        <h2 className="text-lg font-semibold text-gray-800">{org.name}</h2>
        <span className="font-mono text-sm text-gray-400">{org.organization_id}</span>
        {msg && <span className="text-xs text-green-600 font-medium ml-2">{msg}</span>}
      </div>

      {/* Meta fields */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-5 mb-6 max-w-lg space-y-4">
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Full name</label>
          <input
            value={nameVal}
            onChange={(e) => { setNameVal(e.target.value); setDirty(true); }}
            className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Country</label>
            <select
              value={countryVal}
              onChange={(e) => { setCountryVal(e.target.value); setDirty(true); }}
              className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
            >
              <option value="">— none (multi-country) —</option>
              {countries.map((c) => <option key={c.country_code} value={c.country_code}>{c.name} ({c.country_code})</option>)}
            </select>
          </div>
          <div className="flex items-end pb-1">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={activeVal}
                onChange={(e) => { setActiveVal(e.target.checked); setDirty(true); }}
                className="w-4 h-4 rounded"
              />
              <span className="text-sm text-gray-700">Active</span>
            </label>
          </div>
        </div>
        {dirty && (
          <div className="flex justify-end">
            <button
              onClick={handleSaveMeta}
              disabled={saving || !nameVal.trim()}
              className="text-sm bg-blue-600 text-white px-4 py-1.5 rounded font-medium hover:bg-blue-700 disabled:opacity-50 transition"
            >
              {saving ? "Saving…" : "Save changes"}
            </button>
          </div>
        )}
      </div>

      {/* Projects — read-only list; click to open in Projects tab */}
      <div>
        <h3 className="text-sm font-semibold text-gray-700 mb-2">Projects</h3>
        <p className="text-xs text-gray-400 mb-3">
          Projects this organization is involved in. Click a project to open it and manage assignments.
        </p>

        {projectsLoading ? (
          <p className="text-sm text-gray-400 animate-pulse">Loading…</p>
        ) : linkedProjects.length === 0 ? (
          <p className="text-xs text-gray-400 italic">
            Not linked to any projects yet.{" "}
            <button
              onClick={() => onNavigateToProject("")}
              className="text-blue-500 hover:underline"
            >
              Go to Projects &amp; packages →
            </button>
          </p>
        ) : (
          <div className="border border-gray-200 rounded-lg overflow-hidden max-w-xl">
            <table className="w-full text-sm">
              <tbody>
                {linkedProjects.map((proj) => {
                  const link = proj.organizations.find((o) => o.organization_id === org.organization_id);
                  const roleDef = orgRoles.find((r) => r.key === link?.org_role);
                  const roleColor = link?.org_role
                    ? (ORG_ROLE_COLORS[link.org_role] ?? "bg-gray-100 text-gray-600 border-gray-200")
                    : "";
                  const contractorPkgs = packagesByProject[proj.project_id] ?? [];
                  return (
                    <React.Fragment key={proj.project_id}>
                      {/* Clickable project row → navigates to Projects tab with this project open */}
                      <tr
                        className="border-t border-gray-100 first:border-t-0 hover:bg-blue-50 cursor-pointer group transition-colors"
                        onClick={() => onNavigateToProject(proj.project_id)}
                      >
                        <td className="px-3 py-2.5">
                          <div className="font-medium text-gray-800 group-hover:text-blue-700 transition-colors">
                            {proj.name}
                          </div>
                          <div className="font-mono text-xs text-gray-400">{proj.short_code}</div>
                        </td>
                        <td className="px-3 py-2.5">
                          {roleDef ? (
                            <span className={`text-xs px-2 py-0.5 rounded border font-medium ${roleColor}`}>
                              {roleDef.label}
                            </span>
                          ) : (
                            <span className="text-xs text-gray-300">—</span>
                          )}
                        </td>
                        <td className="px-3 py-2.5 text-right">
                          <span className="text-xs text-gray-300 opacity-0 group-hover:opacity-100 transition-opacity">
                            Open →
                          </span>
                        </td>
                      </tr>
                      {/* Package contractor context (read-only) */}
                      {contractorPkgs.length > 0 && (
                        <tr
                          className="bg-orange-50/60 cursor-pointer"
                          onClick={() => onNavigateToProject(proj.project_id)}
                        >
                          <td colSpan={3} className="px-4 pb-2.5 pt-1">
                            <div className="flex flex-wrap gap-1.5 items-center">
                              <span className="text-xs text-gray-400 mr-0.5">Contractor on:</span>
                              {contractorPkgs.map((pkg) => (
                                <span
                                  key={pkg.package_id}
                                  title={pkg.name}
                                  className="text-xs font-mono bg-orange-100 text-orange-700 border border-orange-200 px-1.5 py-0.5 rounded"
                                >
                                  {pkg.package_code}
                                </span>
                              ))}
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Locations section ─────────────────────────────────────────────────────────

function LocationsSection() {
  const [countries, setCountries] = useState<CountryItem[]>([]);
  const [country, setCountry]     = useState("NP");
  const [level, setLevel]         = useState<number | "">("");
  const [parent, setParent]       = useState("");
  const [q, setQ]                 = useState("");
  const [nodes, setNodes]         = useState<LocationNode[]>([]);
  const [loadingNodes, setLoadingNodes] = useState(false);
  const [searched, setSearched]   = useState(false);

  // Import state
  const [importFile, setImportFile] = useState<File | null>(null);
  const [dryRun, setDryRun]         = useState(true);
  const [importing, setImporting]   = useState(false);
  const [importResult, setImportResult] = useState<{ locations_upserted: number; translations_upserted: number; dry_run: boolean } | null>(null);
  const [importError, setImportError] = useState("");

  useEffect(() => {
    listCountries().then(setCountries).catch(() => {});
  }, []);

  const selectedCountry = countries.find((c) => c.country_code === country);

  async function handleSearch() {
    setLoadingNodes(true);
    setSearched(true);
    try {
      const res = await listLocations({
        country,
        level: level !== "" ? (level as number) : undefined,
        parent: parent.trim() || undefined,
        q: q.trim() || undefined,
        limit: 200,
      });
      setNodes(res);
    } catch {
      setNodes([]);
    } finally {
      setLoadingNodes(false);
    }
  }

  function getName(node: LocationNode, lang = "en") {
    return node.translations.find((t) => t.lang_code === lang)?.name
      ?? node.translations[0]?.name
      ?? node.location_code;
  }

  async function handleImport() {
    if (!importFile) return;
    setImporting(true);
    setImportError("");
    setImportResult(null);
    try {
      const result = await importLocations(importFile, { country, dry_run: dryRun });
      setImportResult(result);
    } catch (e: unknown) {
      setImportError(e instanceof Error ? e.message : "Import failed");
    } finally {
      setImporting(false);
    }
  }

  const levelLabel = (n: number) =>
    selectedCountry?.level_defs.find((d) => d.level_number === n)?.level_name_en ?? `Level ${n}`;

  return (
    <div className="space-y-8">
      {/* ── Tree browser ── */}
      <section>
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Browse location tree</h3>
        <div className="flex flex-wrap items-end gap-3 mb-4">
          <div>
            <label className="text-xs text-gray-500 block mb-1">Country</label>
            <select
              value={country}
              onChange={(e) => { setCountry(e.target.value); setLevel(""); setParent(""); }}
              className="text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
            >
              {countries.map((c) => <option key={c.country_code} value={c.country_code}>{c.name}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Level</label>
            <select
              value={level}
              onChange={(e) => setLevel(e.target.value === "" ? "" : Number(e.target.value))}
              className="text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
            >
              <option value="">All levels</option>
              {(selectedCountry?.level_defs ?? []).map((d) => (
                <option key={d.level_number} value={d.level_number}>{d.level_name_en}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Parent code</label>
            <input
              value={parent}
              onChange={(e) => setParent(e.target.value)}
              placeholder="e.g. P1"
              className="text-sm border border-gray-300 rounded px-2 py-1.5 w-32 focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Search name</label>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder="e.g. Jhapa"
              className="text-sm border border-gray-300 rounded px-2 py-1.5 w-40 focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>
          <button
            onClick={handleSearch}
            disabled={loadingNodes}
            className="bg-slate-700 text-white text-sm px-4 py-1.5 rounded hover:bg-slate-800 disabled:opacity-50 transition"
          >
            {loadingNodes ? "Searching…" : "Search"}
          </button>
        </div>

        {searched && (
          <div className="border border-gray-200 rounded-lg overflow-hidden">
            {nodes.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-8">No locations found.</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-700 text-slate-100 text-left">
                    <th className="px-4 py-2.5 font-medium">Code</th>
                    <th className="px-4 py-2.5 font-medium">English name</th>
                    <th className="px-4 py-2.5 font-medium">Local name</th>
                    <th className="px-4 py-2.5 font-medium">Level</th>
                    <th className="px-4 py-2.5 font-medium">Parent</th>
                  </tr>
                </thead>
                <tbody>
                  {nodes.slice(0, 100).map((n) => (
                    <tr key={n.location_code} className="border-t border-gray-100 hover:bg-gray-50">
                      <td className="px-4 py-2 font-mono text-xs text-gray-600">{n.location_code}</td>
                      <td className="px-4 py-2 text-gray-800">{getName(n, "en")}</td>
                      <td className="px-4 py-2 text-gray-500">{getName(n, "ne") ?? "—"}</td>
                      <td className="px-4 py-2 text-gray-500 text-xs">{levelLabel(n.level_number)}</td>
                      <td className="px-4 py-2 font-mono text-xs text-gray-400">{n.parent_location_code ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {nodes.length > 100 && (
              <p className="text-xs text-gray-400 text-center py-2 border-t border-gray-100">
                Showing first 100 of {nodes.length} results. Refine your search to see more.
              </p>
            )}
          </div>
        )}
      </section>

      {/* ── Import ── */}
      <section>
        <h3 className="text-sm font-semibold text-gray-700 mb-1">Import location data</h3>
        <p className="text-xs text-gray-500 mb-4">
          Upload a CSV or nested JSON file to add or update locations. Operation is idempotent — safe to re-run.
          Super admin only.
        </p>

        {/* Template downloads */}
        <div className="flex gap-3 mb-5">
          <a
            href={getLocationTemplateCsvUrl()}
            download="location_template.csv"
            className="flex items-center gap-1.5 text-xs bg-white border border-gray-300 text-gray-700 hover:border-gray-400 hover:bg-gray-50 px-3 py-1.5 rounded transition"
          >
            ⬇ Download CSV template
          </a>
          <a
            href={getLocationTemplateJsonUrl()}
            download="location_template.json"
            className="flex items-center gap-1.5 text-xs bg-white border border-gray-300 text-gray-700 hover:border-gray-400 hover:bg-gray-50 px-3 py-1.5 rounded transition"
          >
            ⬇ Download JSON template
          </a>
        </div>

        {/* Upload form */}
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-3 max-w-xl">
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <label className="text-xs text-gray-500 block mb-1">Country</label>
              <select
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
              >
                {countries.map((c) => <option key={c.country_code} value={c.country_code}>{c.name}</option>)}
              </select>
            </div>
            <div className="flex items-center gap-2 pt-4">
              <input
                type="checkbox"
                id="dry-run-check"
                checked={dryRun}
                onChange={(e) => setDryRun(e.target.checked)}
                className="w-3.5 h-3.5"
              />
              <label htmlFor="dry-run-check" className="text-xs text-gray-600 cursor-pointer">
                Preview only (dry run)
              </label>
            </div>
          </div>

          <div>
            <label className="text-xs text-gray-500 block mb-1">File (CSV or JSON)</label>
            <input
              type="file"
              accept=".csv,.json"
              onChange={(e) => { setImportFile(e.target.files?.[0] ?? null); setImportResult(null); setImportError(""); }}
              className="w-full text-xs text-gray-600 file:mr-3 file:text-xs file:py-1.5 file:px-3 file:rounded file:border file:border-gray-300 file:bg-white file:text-gray-700 hover:file:bg-gray-50"
            />
          </div>

          <button
            onClick={handleImport}
            disabled={!importFile || importing}
            className="bg-blue-600 text-white text-sm px-5 py-1.5 rounded font-medium hover:bg-blue-700 disabled:opacity-40 transition"
          >
            {importing ? "Importing…" : dryRun ? "Preview import" : "Import"}
          </button>

          {importError && (
            <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
              {importError}
            </p>
          )}

          {importResult && (
            <div className={`text-xs rounded px-3 py-2 border ${importResult.dry_run ? "bg-amber-50 border-amber-200 text-amber-800" : "bg-green-50 border-green-200 text-green-800"}`}>
              {importResult.dry_run ? "Preview: " : "✓ Imported: "}
              <strong>{importResult.locations_upserted}</strong> locations,{" "}
              <strong>{importResult.translations_upserted}</strong> translations
              {importResult.dry_run && " — uncheck 'Preview only' and re-upload to commit."}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

// ── Projects section ──────────────────────────────────────────────────────────

function ProjectsSection({
  initialEditId = null,
  grmRoleChoices,
  isSuperAdmin,
}: {
  initialEditId?: string | null;
  grmRoleChoices: { key: string; label: string }[];
  isSuperAdmin: boolean;
}) {
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [orgs, setOrgs]         = useState<OrganizationItem[]>([]);
  const [orgRoles, setOrgRoles] = useState<OrgRole[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState("");
  const [editing, setEditing]   = useState<ProjectItem | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const [p, o] = await Promise.all([listProjects(), listOrganizations()]);
      const r = await getOrgRoles().catch(() => [] as OrgRole[]);
      setProjects(p);
      setOrgs(o);
      setOrgRoles(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed");
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

  // Local admins: land directly on their project when there is only one
  useEffect(() => {
    if (isSuperAdmin || loading || editing || projects.length !== 1) return;
    setEditing(projects[0]);
  }, [isSuperAdmin, loading, editing, projects]);

  async function handleRemoveProject(p: ProjectItem) {
    if (!confirm(`Remove project "${p.name}" (${p.short_code})? Packages and links will be deleted.`)) return;
    try {
      await deleteProject(p.project_id);
      if (editing?.project_id === p.project_id) setEditing(null);
      setProjects((prev) => prev.filter((x) => x.project_id !== p.project_id));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Remove failed");
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
        showBack={isSuperAdmin || projects.length > 1}
        onBack={() => { setEditing(null); load(); }}
        onUpdated={(p) => setEditing(p)}
        onOrganizationCreated={(org) => setOrgs((prev) => (prev.some((o) => o.organization_id === org.organization_id) ? prev : [...prev, org]))}
      />
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-gray-500">{projects.length} project{projects.length !== 1 ? "s" : ""}</p>
        {isSuperAdmin && (
          <button
            onClick={() => setShowCreate(true)}
            className="bg-blue-600 text-white text-sm px-4 py-1.5 rounded hover:bg-blue-700 transition font-medium"
          >
            + New Project
          </button>
        )}
      </div>

      {isSuperAdmin && showCreate && (
        <ProjectCreateModal
          onCreated={(p) => { setShowCreate(false); setProjects((prev) => [...prev, p]); setEditing(p); }}
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
            const orgSummary = p.organizations.map((po) => {
              const orgName = orgs.find((o) => o.organization_id === po.organization_id)?.name ?? po.organization_id;
              const roleDef = orgRoles.find((r) => r.key === po.org_role);
              return roleDef ? `${orgName} (${roleDef.label})` : orgName;
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
                    <span>Actors: {orgSummary.length > 0 ? orgSummary.join(", ") : <em>none</em>}</span>
                    <span>·</span>
                    <span>Locations: {p.location_codes.length > 0 ? `${p.location_codes.length} linked` : <em>none</em>}</span>
                  </div>
                </div>
                <button type="button" onClick={() => setEditing(p)} className="text-sm text-blue-600 hover:underline shrink-0 mr-3">
                  {isSuperAdmin ? "Edit" : "Set up"}
                </button>
                {isSuperAdmin && (
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

function ProjectCreateModal({
  onCreated,
  onClose,
}: {
  onCreated: (p: ProjectItem) => void;
  onClose: () => void;
}) {
  const [name, setName]         = useState("");
  const [shortCode, setShortCode] = useState("");
  const [country, setCountry]   = useState("NP");
  const [desc, setDesc]         = useState("");
  const [typeKey, setTypeKey]   = useState("construction_road");
  const [types, setTypes]       = useState<{ type_key: string; label: string }[]>([]);
  const [creating, setCreating] = useState(false);
  const [error, setError]       = useState("");

  useEffect(() => {
    listProjectTypes(true)
      .then((rows) => {
        setTypes(rows.map((t) => ({ type_key: t.type_key, label: t.label })));
        if (rows.length && !rows.some((t) => t.type_key === "construction_road")) {
          setTypeKey(rows[0].type_key);
        }
      })
      .catch(() => {});
  }, []);

  async function handleCreate() {
    if (!name.trim() || !shortCode.trim()) { setError("Name and short code are required."); return; }
    if (!typeKey) { setError("Select a project type."); return; }
    setCreating(true); setError("");
    try {
      const p = await createProject({
        name: name.trim(),
        short_code: shortCode.trim().toUpperCase(),
        country_code: country,
        description: desc.trim() || null,
        project_type_key: typeKey,
        is_active: false,
      });
      onCreated(p);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Create failed");
      setCreating(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 overflow-hidden">
        <div className="bg-slate-700 text-white px-6 py-4 flex items-center justify-between">
          <div className="font-semibold">New project</div>
          <button onClick={onClose} className="text-slate-300 hover:text-white text-xl leading-none">×</button>
        </div>
        <div className="p-6 space-y-4">
          {error && <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>}
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="text-xs font-medium text-gray-500 block mb-1">Project type *</label>
              <select
                value={typeKey}
                onChange={(e) => setTypeKey(e.target.value)}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 mb-2 focus:outline-none focus:ring-1 focus:ring-blue-400"
              >
                {types.length === 0 ? (
                  <option value="construction_road">Construction (road)</option>
                ) : (
                  types.map((t) => (
                    <option key={t.type_key} value={t.type_key}>{t.label}</option>
                  ))
                )}
              </select>
              <p className="text-xs text-gray-400 mb-2">
                Workflows and actor roles come from the type. Project starts inactive until go-live checks pass.
              </p>
            </div>
            <div className="col-span-2">
              <label className="text-xs font-medium text-gray-500 block mb-1">Project name *</label>
              <input autoFocus value={name} onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Kakarbhitta-Laukahi Road"
                className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">Short code * <span className="font-normal text-gray-400">(unique)</span></label>
              <input value={shortCode} onChange={(e) => setShortCode(e.target.value.toUpperCase())}
                placeholder="KL_ROAD"
                className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 font-mono focus:outline-none focus:ring-1 focus:ring-blue-400" />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">Country</label>
              <select value={country} onChange={(e) => setCountry(e.target.value)}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400">
                <option value="NP">Nepal (NP)</option>
              </select>
            </div>
            <div className="col-span-2">
              <label className="text-xs font-medium text-gray-500 block mb-1">Description</label>
              <textarea value={desc} onChange={(e) => setDesc(e.target.value)} rows={2}
                className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 resize-none focus:outline-none focus:ring-1 focus:ring-blue-400" />
            </div>
          </div>
        </div>
        <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-3">
          <button onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700 px-4 py-1.5 rounded">Cancel</button>
          <button onClick={handleCreate} disabled={creating || !name.trim() || !shortCode.trim()}
            className="text-sm bg-blue-600 text-white hover:bg-blue-700 px-4 py-1.5 rounded font-medium disabled:opacity-50 transition">
            {creating ? "Creating…" : "Create project"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ProjectEditor({
  project: initial,
  orgs,
  orgRoles,
  grmRoleChoices,
  isSuperAdmin,
  showBack = true,
  onBack,
  onUpdated,
  onOrganizationCreated,
}: {
  project: ProjectItem;
  orgs: OrganizationItem[];
  orgRoles: OrgRole[];
  grmRoleChoices: { key: string; label: string }[];
  isSuperAdmin: boolean;
  showBack?: boolean;
  onBack: () => void;
  onUpdated: (p: ProjectItem) => void;
  onOrganizationCreated: (org: OrganizationItem) => void;
}) {
  const [p, setP]             = useState<ProjectItem>(initial);
  const [editingName, setEditingName] = useState(false);
  const [nameVal, setNameVal] = useState(p.name);
  const [descVal, setDescVal] = useState(p.description ?? "");
  const [msg, setMsg]         = useState("");
  const [working, setWorking] = useState(false);
  const [locError, setLocError] = useState("");
  const { canSeeSeah } = useAuth();
  const [projectActorRoles, setProjectActorRolesState] = useState<OrgRole[]>(orgRoles);
  const [rolesSaving, setRolesSaving] = useState(false);
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([]);
  const [wfTemplates, setWfTemplates] = useState<WorkflowDefinition[]>([]);
  const [wfModal, setWfModal] = useState<null | "standard" | "seah">(null);
  const [wfSaving, setWfSaving] = useState(false);
  const [goLiveKey, setGoLiveKey] = useState(0);
  const sectionRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const typedProject = Boolean(p.project_type_key);
  const lockTypeConfig = typedProject && !isSuperAdmin;

  function jumpToSection(section: string) {
    sectionRefs.current[section]?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function toggleActive() {
    try {
      const updated = await updateProject(p.project_id, { is_active: !p.is_active });
      setP(updated);
      onUpdated(updated);
      setGoLiveKey((k) => k + 1);
      flash(updated.is_active ? "Project activated ✓" : "Project deactivated");
    } catch (e: unknown) {
      flash(e instanceof Error ? e.message : "Could not update status");
    }
  }

  useEffect(() => {
    listWorkflows().then((r) => setWorkflows(r.items)).catch(() => {});
    listTemplates().then((r) => setWfTemplates(r.items)).catch(() => {});
  }, []);

  useEffect(() => {
    getProjectActorRoles(p.project_id)
      .then(setProjectActorRolesState)
      .catch(() => setProjectActorRolesState(orgRoles));
  }, [p.project_id, orgRoles]);

  async function saveProjectWorkflow(
    field: "standard_workflow_id" | "seah_workflow_id",
    workflowId: string | null,
  ) {
    setWfSaving(true);
    try {
      const updated = await updateProject(p.project_id, { [field]: workflowId });
      setP(updated);
      onUpdated(updated);
      flash("Workflow saved ✓");
    } catch (e: unknown) {
      flash(e instanceof Error ? e.message : "Failed to save workflow");
    } finally {
      setWfSaving(false);
    }
  }

  function flash(t: string) { setMsg(t); setTimeout(() => setMsg(""), 2500); }

  async function saveMeta() {
    try {
      const updated = await updateProject(p.project_id, { name: nameVal.trim(), description: descVal.trim() || null });
      setP(updated); onUpdated(updated); flash("Saved ✓");
    } catch { flash("Save failed"); }
    setEditingName(false);
  }

  async function linkProjectActor(organizationId: string, orgRole: string) {
    setWorking(true);
    try {
      const item = await addProjectOrg(p.project_id, organizationId, orgRole || null);
      setP({ ...p, organizations: [...p.organizations, item] });
      flash("Project actor added ✓");
    } catch (e: unknown) {
      flash(e instanceof Error ? e.message : "Failed");
      throw e;
    } finally {
      setWorking(false);
    }
  }

  async function handleRemoveOrg(orgId: string) {
    setWorking(true);
    try {
      await removeProjectOrg(p.project_id, orgId);
      setP({ ...p, organizations: p.organizations.filter((o) => o.organization_id !== orgId) });
      flash("Removed ✓");
    } catch { flash("Failed"); }
    setWorking(false);
  }

  async function handleRoleChange(orgId: string, newRole: string | null) {
    try {
      const updated = await updateProjectOrgRole(p.project_id, orgId, newRole);
      setP({ ...p, organizations: p.organizations.map((o) => o.organization_id === orgId ? updated : o) });
      flash("Role updated ✓");
    } catch { flash("Failed"); }
  }

  async function handleAddLoc(code: string) {
    if (!code) return;
    setWorking(true); setLocError("");
    try {
      await addProjectLocation(p.project_id, code);
      setP({ ...p, location_codes: [...p.location_codes, code] });
      flash("Location linked ✓");
    } catch (e: unknown) {
      setLocError(e instanceof Error && e.message.includes("404") ? `Location '${code}' not found` : "Failed");
    }
    setWorking(false);
  }

  async function handleRemoveLoc(code: string) {
    setWorking(true);
    try {
      await removeProjectLocation(p.project_id, code);
      setP({ ...p, location_codes: p.location_codes.filter((x) => x !== code) });
      flash("Removed ✓");
    } catch { flash("Failed"); }
    setWorking(false);
  }

  // ── Packages ──
  const [packages, setPackages]           = useState<PackageItem[]>([]);
  const [pkgLoading, setPkgLoading]       = useState(true);
  const [showCreatePkg, setShowCreatePkg] = useState(false);
  const [expandedPkg, setExpandedPkg]     = useState<string | null>(null);
  const [officerModalOrg, setOfficerModalOrg] = useState<{ id: string; name: string } | null>(null);
  const [staffingTick, setStaffingTick] = useState(0);

  useEffect(() => {
    listPackages(p.project_id)
      .then(setPackages)
      .catch(() => {/* non-fatal */})
      .finally(() => setPkgLoading(false));
  }, [p.project_id]);

  async function handleUpdatePkg(packageId: string, payload: Partial<PackageItem>) {
    try {
      const updated = await updatePackage(p.project_id, packageId, payload);
      setPackages((prev) => prev.map((pk) => pk.package_id === packageId ? updated : pk));
      flash("Saved ✓");
    } catch { flash("Failed"); }
  }

  async function handleAddPkgLoc(packageId: string, code: string) {
    const uc = code.trim().toUpperCase();
    if (!uc) return;
    try {
      await addPackageLocation(p.project_id, packageId, uc);
      setPackages((prev) => prev.map((pk) =>
        pk.package_id === packageId
          ? { ...pk, location_codes: [...pk.location_codes, uc] }
          : pk
      ));
      flash("Location added ✓");
    } catch (e: unknown) {
      flash(e instanceof Error && e.message.includes("404") ? `'${uc}' not found` : "Failed");
    }
  }

  async function handleRemovePkgLoc(packageId: string, code: string) {
    try {
      await removePackageLocation(p.project_id, packageId, code);
      setPackages((prev) => prev.map((pk) =>
        pk.package_id === packageId
          ? { ...pk, location_codes: pk.location_codes.filter((c) => c !== code) }
          : pk
      ));
    } catch { flash("Failed"); }
  }

  const linkedOrgIds = new Set(p.organizations.map((o) => o.organization_id));

  return (
    <div>
      {/* Back + header */}
      <div className="flex items-center gap-3 mb-6">
        {showBack && (
          <>
            <button onClick={onBack} className="text-gray-400 hover:text-gray-600 text-sm flex items-center gap-1">
              {isSuperAdmin ? "← Projects" : "← All projects"}
            </button>
            <span className="text-gray-300">/</span>
          </>
        )}
        {isSuperAdmin && editingName ? (
          <div className="flex items-center gap-2">
            <input autoFocus value={nameVal} onChange={(e) => setNameVal(e.target.value)}
              onBlur={saveMeta} onKeyDown={(e) => e.key === "Enter" && saveMeta()}
              className="text-lg font-semibold text-gray-800 border-b-2 border-blue-400 bg-transparent focus:outline-none" />
          </div>
        ) : (
          <h2
            className={`text-lg font-semibold text-gray-800${isSuperAdmin ? " cursor-pointer hover:text-blue-600" : ""}`}
            onClick={isSuperAdmin ? () => setEditingName(true) : undefined}
            title={isSuperAdmin ? "Click to rename" : undefined}
          >
            {p.name}
          </h2>
        )}
        <span className="font-mono text-sm text-gray-400">{p.short_code}</span>
        {p.project_type_key && (
          <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-mono">{p.project_type_key}</span>
        )}
        {!p.is_active && <span className="text-xs text-amber-700 bg-amber-50 px-2 py-0.5 rounded">Inactive</span>}
        {isSuperAdmin && (
          <button
            type="button"
            onClick={() => void toggleActive()}
            className="text-xs text-blue-600 hover:underline ml-1"
          >
            {p.is_active ? "Deactivate" : "Activate project"}
          </button>
        )}
        {msg && <span className="text-xs text-green-600 font-medium ml-2">{msg}</span>}
      </div>

      <ProjectGoLivePanel
        key={goLiveKey}
        projectId={p.project_id}
        onJumpSection={jumpToSection}
      />

      {/* Description */}
      <div className="mb-6">
        <label className="text-xs font-medium text-gray-500 block mb-1">Description</label>
        <textarea value={descVal} onChange={(e) => setDescVal(e.target.value)}
          onBlur={saveMeta} rows={2}
          placeholder="Project description…"
          className="w-full max-w-lg text-sm border border-gray-200 rounded px-3 py-1.5 resize-none focus:outline-none focus:ring-1 focus:ring-blue-400" />
      </div>

      {/* Grievance workflows — super admin only */}
      {isSuperAdmin && (
      <div
        ref={(el) => { sectionRefs.current.workflows = el; }}
        className="mb-6 border border-gray-200 rounded-lg p-4 bg-gray-50/60 max-w-2xl space-y-4"
      >
        <div>
          <h3 className="text-sm font-semibold text-gray-700">Grievance workflows</h3>
          <p className="text-xs text-gray-500 mt-1">
            New tickets for project <span className="font-mono">{p.short_code}</span> use these workflows.
            {lockTypeConfig
              ? " Set by project type (super admin edits the type under Settings → Project types)."
              : " Configure steps under Settings → Workflows."}
          </p>
        </div>
        <ProjectWorkflowSelect
          label="Standard GRM workflow"
          hint="Used for normal grievances on this project."
          workflowType="standard"
          value={p.standard_workflow_id ?? null}
          workflows={workflows}
          disabled={wfSaving || lockTypeConfig}
          onChange={(id) => void saveProjectWorkflow("standard_workflow_id", id)}
          onCreateNew={() => setWfModal("standard")}
        />
        {canSeeSeah && (
          <ProjectWorkflowSelect
            label="SEAH workflow"
            hint="Used when the grievance is marked SEAH-sensitive."
            workflowType="seah"
            value={p.seah_workflow_id ?? null}
            workflows={workflows}
            disabled={wfSaving || lockTypeConfig}
            onChange={(id) => void saveProjectWorkflow("seah_workflow_id", id)}
            onCreateNew={() => setWfModal("seah")}
          />
        )}
      </div>
      )}

      {isSuperAdmin && wfModal && (
        <NewWorkflowModal
          templates={wfTemplates}
          canSeeSeah={!!canSeeSeah}
          fixedWorkflowType={wfModal}
          onCreated={(w) => {
            setWorkflows((prev) =>
              prev.some((x) => x.workflow_id === w.workflow_id) ? prev : [...prev, w],
            );
            void saveProjectWorkflow(
              wfModal === "seah" ? "seah_workflow_id" : "standard_workflow_id",
              w.workflow_id,
            );
            setWfModal(null);
          }}
          onClose={() => setWfModal(null)}
        />
      )}

      {isSuperAdmin && (
      <ProjectActorRolesEditor
        roles={projectActorRoles}
        saving={rolesSaving}
        readOnly={lockTypeConfig}
        onChange={setProjectActorRolesState}
        onSave={async (roles) => {
          setRolesSaving(true);
          try {
            const saved = await setProjectActorRoles(p.project_id, roles);
            setProjectActorRolesState(saved);
            flash("Actor roles saved ✓");
          } catch (e: unknown) {
            flash(e instanceof Error ? e.message : "Failed to save roles");
          } finally {
            setRolesSaving(false);
          }
        }}
      />
      )}

      {/* Project actors (project-wide org + role) */}
      <div ref={(el) => { sectionRefs.current.actors = el; }} className="mb-6">
        <div>
          <h3 className="text-sm font-semibold text-gray-700">Project actors</h3>
          <p className="text-xs text-gray-500 mt-0.5 max-w-2xl">
            Add each partner organization and its role on this project. Use <span className="font-medium">+ New organization</span> if it is not in the list yet.
          </p>
        </div>
        <p className="text-xs text-gray-500 mb-3 max-w-2xl">
          Then use <span className="font-medium">Add officer</span> on a row to invite or scope someone for that organization.
        </p>

        {p.organizations.length === 0 ? (
          <p className="text-xs text-gray-400 italic mb-3">No project actors yet</p>
        ) : (
          <div className="border border-gray-200 rounded-lg overflow-hidden mb-3 max-w-xl">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 text-left border-b border-gray-200">
                  <th className="px-3 py-2 text-xs font-medium text-gray-500 w-1/2">Organization</th>
                  <th className="px-3 py-2 text-xs font-medium text-gray-500">Role on project</th>
                  <th className="px-3 py-2 text-xs font-medium text-gray-500 w-24">Officer</th>
                  <th className="px-3 py-2 w-8" />
                </tr>
              </thead>
              <tbody>
                {p.organizations.map((po) => {
                  const orgName = orgs.find((o) => o.organization_id === po.organization_id)?.name ?? po.organization_id;
                  const roleDef = projectActorRoles.find((r) => r.key === po.org_role);
                  const roleColor = po.org_role ? (ORG_ROLE_COLORS[po.org_role] ?? "bg-gray-100 text-gray-600 border-gray-200") : "";
                  return (
                    <tr key={po.organization_id} className="border-t border-gray-100 hover:bg-gray-50">
                      <td className="px-3 py-2.5 font-medium text-gray-800">{orgName}</td>
                      <td className="px-3 py-2.5">
                        <select
                          value={po.org_role ?? ""}
                          onChange={(e) => handleRoleChange(po.organization_id, e.target.value || null)}
                          disabled={working}
                          className={`text-xs px-2 py-1 rounded border font-medium focus:outline-none focus:ring-1 focus:ring-blue-300 ${
                            roleDef ? roleColor : "text-gray-400 border-gray-200 bg-white"
                          }`}
                        >
                          <option value="">— no role —</option>
                          {projectActorRoles.map((r) => (
                            <option key={r.key} value={r.key}>{r.label}</option>
                          ))}
                        </select>
                      </td>
                      <td className="px-3 py-2.5">
                        <button
                          type="button"
                          onClick={() => setOfficerModalOrg({
                            id: po.organization_id,
                            name: orgName,
                          })}
                          className="text-xs text-blue-600 hover:underline whitespace-nowrap"
                        >
                          Add officer
                        </button>
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        <button onClick={() => handleRemoveOrg(po.organization_id)} disabled={working}
                          className="text-gray-300 hover:text-red-500 text-lg leading-none disabled:opacity-40">×</button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <ProjectActorAddRow
          actorRoles={projectActorRoles}
          orgs={orgs}
          defaultCountryCode={p.country_code || "NP"}
          excludeOrganizationIds={linkedOrgIds}
          working={working}
          onOrganizationCreated={onOrganizationCreated}
          onAdd={linkProjectActor}
        />
      </div>

      {officerModalOrg && (
        <ProjectOfficerModal
          project={p}
          organizationId={officerModalOrg.id}
          organizationName={officerModalOrg.name}
          roleChoices={grmRoleChoices}
          onClose={() => setOfficerModalOrg(null)}
          onSuccess={() => { setOfficerModalOrg(null); flash("Officer saved ✓"); setStaffingTick((n) => n + 1); }}
        />
      )}

      {/* Locations */}
      <div ref={(el) => { sectionRefs.current.locations = el; }}>
        <h3 className="text-sm font-semibold text-gray-700 mb-1">Linked locations</h3>
        <p className="text-xs text-gray-400 mb-3">
          Search for the provinces, districts or municipalities this project covers.
        </p>
        {locError && <p className="text-xs text-red-500 mb-2">{locError}</p>}
        <div className="flex flex-wrap gap-2 mb-3">
          {p.location_codes.length === 0 && <span className="text-xs text-gray-400 italic">No locations linked</span>}
          {p.location_codes.map((code) => (
            <span key={code} className="flex items-center gap-1.5 text-xs font-mono bg-blue-50 text-blue-700 border border-blue-200 px-2.5 py-1 rounded-full">
              {code}
              <button onClick={() => handleRemoveLoc(code)} disabled={working}
                className="text-blue-400 hover:text-red-500 leading-none disabled:opacity-50">×</button>
            </span>
          ))}
        </div>
        <div className="max-w-sm">
          <LocationSearch
            country={p.country_code || "NP"}
            placeholder="Search province, district or municipality…"
            excludeCodes={p.location_codes}
            onSelect={(code) => handleAddLoc(code)}
          />
        </div>
      </div>

      {/* Packages (lot-level actors + locations) */}
      <div ref={(el) => { sectionRefs.current.packages = el; }} className="mt-8 pt-6 border-t border-gray-100">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="text-sm font-semibold text-gray-700">Packages</h3>
            <p className="text-xs text-gray-500 mt-0.5 max-w-2xl">
              Lots, contracts, or work packages within this project. Assign organizations and roles per package
              when they apply to one lot only (e.g. a CSC or engineering team on a single package).
            </p>
          </div>
          <button
            onClick={() => setShowCreatePkg(true)}
            className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700 transition font-medium shrink-0"
          >
            + New Package
          </button>
        </div>

        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs text-amber-900 max-w-2xl" role="note">
          <span className="font-medium">Package overrides project:</span>{" "}
          An actor assigned on a package applies only to that lot and replaces the project-wide actor
          with the <em>same role</em> on that package only. Example: CSC&nbsp;A project-wide and CSC&nbsp;B on
          package&nbsp;3 → CSC&nbsp;A on every package except package&nbsp;3, where CSC&nbsp;B applies.
        </div>

        {showCreatePkg && (
          <PackageCreateModal
            projectId={p.project_id}
            onCreated={(pkg) => { setPackages((prev) => [...prev, pkg]); setShowCreatePkg(false); setExpandedPkg(pkg.package_id); }}
            onClose={() => setShowCreatePkg(false)}
          />
        )}

        {pkgLoading ? (
          <p className="text-sm text-gray-400 animate-pulse">Loading…</p>
        ) : packages.length === 0 ? (
          <p className="text-xs text-gray-400 italic">No packages defined yet.</p>
        ) : (
          <div className="space-y-2">
            {packages.map((pkg) => {
              const expanded = expandedPkg === pkg.package_id;
              return (
                <PackageRow
                  key={pkg.package_id}
                  projectId={p.project_id}
                  pkg={pkg}
                  orgs={orgs}
                  actorRoles={projectActorRoles}
                  expanded={expanded}
                  onToggle={() => setExpandedPkg(expanded ? null : pkg.package_id)}
                  onUpdate={(payload) => handleUpdatePkg(pkg.package_id, payload)}
                  onActorsChange={(organizations) =>
                    setPackages((prev) =>
                      prev.map((pk) => (pk.package_id === pkg.package_id ? { ...pk, organizations } : pk)),
                    )
                  }
                  onAddLoc={(code) => handleAddPkgLoc(pkg.package_id, code)}
                  onRemoveLoc={(code) => handleRemovePkgLoc(pkg.package_id, code)}
                />
              );
            })}
          </div>
        )}
      </div>

      <div ref={(el) => { sectionRefs.current.staffing = el; }}>
        <ProjectStaffingSection
          key={staffingTick}
          project={p}
          projectActors={p.organizations}
          orgs={orgs}
          grmRoleChoices={grmRoleChoices}
          packages={packages}
        />
      </div>
    </div>
  );
}

// ── Project actor role vocabulary (per project) ─────────────────────────────

function ProjectActorRolesEditor({
  roles,
  saving,
  readOnly = false,
  onChange,
  onSave,
}: {
  roles: OrgRole[];
  saving: boolean;
  readOnly?: boolean;
  onChange: (roles: OrgRole[]) => void;
  onSave: (roles: OrgRole[]) => Promise<void>;
}) {
  const [dirty, setDirty] = useState(false);

  function updateRow(index: number, patch: Partial<OrgRole>) {
    onChange(roles.map((r, i) => (i === index ? { ...r, ...patch } : r)));
    setDirty(true);
  }

  function addRow() {
    onChange([...roles, { key: "", label: "", description: "" }]);
    setDirty(true);
  }

  function removeRow(index: number) {
    onChange(roles.filter((_, i) => i !== index));
    setDirty(true);
  }

  return (
    <div className="mb-6 border border-gray-200 rounded-lg p-4 bg-white max-w-2xl">
      <h3 className="text-sm font-semibold text-gray-700 mb-1">Actor roles</h3>
      <p className="text-xs text-gray-500 mb-3">
        {readOnly
          ? "Role keys are defined by the project type. Assign organizations to these roles below."
          : "Role types for project and package actors. Seeded from system defaults; customize per project."}
      </p>
      <div className="border border-gray-200 rounded-lg overflow-hidden mb-3">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 text-left border-b border-gray-200">
              <th className="px-3 py-2 text-xs font-medium text-gray-500">Key</th>
              <th className="px-3 py-2 text-xs font-medium text-gray-500">Label</th>
              <th className="px-3 py-2 text-xs font-medium text-gray-500">Description</th>
              <th className="w-8" />
            </tr>
          </thead>
          <tbody>
            {roles.map((r, i) => (
              <tr key={i} className="border-t border-gray-100">
                <td className="px-2 py-1.5">
                  <input
                    value={r.key}
                    readOnly={readOnly}
                    onChange={(e) => updateRow(i, { key: e.target.value })}
                    placeholder="e.g. main_contractor"
                    className="w-full font-mono text-xs border border-gray-200 rounded px-2 py-1"
                  />
                </td>
                <td className="px-2 py-1.5">
                  <input
                    value={r.label}
                    readOnly={readOnly}
                    onChange={(e) => updateRow(i, { label: e.target.value })}
                    className="w-full text-xs border border-gray-200 rounded px-2 py-1"
                  />
                </td>
                <td className="px-2 py-1.5">
                  <input
                    value={r.description ?? ""}
                    readOnly={readOnly}
                    onChange={(e) => updateRow(i, { description: e.target.value })}
                    className="w-full text-xs border border-gray-200 rounded px-2 py-1"
                  />
                </td>
                <td className="px-2 py-1.5 text-right">
                  {!readOnly && (
                    <button type="button" onClick={() => removeRow(i)}
                      className="text-gray-300 hover:text-red-500 text-lg leading-none">×</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!readOnly && (
        <div className="flex items-center gap-2">
          <button type="button" onClick={addRow} className="text-xs text-blue-600 hover:text-blue-800 font-medium">
            + Add role
          </button>
          {dirty && (
            <button
              type="button"
              onClick={() => { void onSave(roles).then(() => setDirty(false)); }}
              disabled={saving}
              className="text-sm bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700 disabled:opacity-50 ml-auto"
            >
              {saving ? "Saving…" : "Save roles"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ── Package row (collapsed + expanded editor) ─────────────────────────────────

function PackageRow({
  projectId,
  pkg,
  orgs,
  actorRoles,
  expanded,
  onToggle,
  onUpdate,
  onActorsChange,
  onAddLoc,
  onRemoveLoc,
}: {
  projectId:    string;
  pkg:          PackageItem;
  orgs:         OrganizationItem[];
  actorRoles:   OrgRole[];
  expanded:     boolean;
  onToggle:     () => void;
  onUpdate:     (payload: Partial<PackageItem>) => Promise<void>;
  onActorsChange: (organizations: PackageItem["organizations"]) => void;
  onAddLoc:     (code: string) => Promise<void>;
  onRemoveLoc:  (code: string) => Promise<void>;
}) {
  const [nameVal, setNameVal]       = useState(pkg.name);
  const [descVal, setDescVal]       = useState(pkg.description ?? "");
  const [addingOrg, setAddingOrg]   = useState("");
  const [addingRole, setAddingRole] = useState(actorRoles[0]?.key ?? "");
  const [actorWorking, setActorWorking] = useState(false);
  const [saving, setSaving]         = useState(false);
  const [dirty, setDirty]           = useState(false);

  const organizations = pkg.organizations ?? [];

  React.useEffect(() => {
    setNameVal(pkg.name);
    setDescVal(pkg.description ?? "");
    setDirty(false);
  }, [pkg.package_id, pkg.name, pkg.description]);

  React.useEffect(() => {
    if (actorRoles.length && !actorRoles.some((r) => r.key === addingRole)) {
      setAddingRole(actorRoles[0].key);
    }
  }, [actorRoles, addingRole]);

  async function handleSave() {
    setSaving(true);
    await onUpdate({ name: nameVal.trim(), description: descVal.trim() || null });
    setDirty(false);
    setSaving(false);
  }

  async function handleAddActor() {
    if (!addingOrg || !addingRole) return;
    setActorWorking(true);
    try {
      const item = await addPackageOrg(projectId, pkg.package_id, addingOrg, addingRole);
      onActorsChange([...organizations, item]);
      setAddingOrg("");
    } catch { /* */ }
    setActorWorking(false);
  }

  async function handleRemoveActor(organizationId: string, orgRole: string) {
    setActorWorking(true);
    try {
      await removePackageOrg(projectId, pkg.package_id, organizationId, orgRole);
      onActorsChange(organizations.filter(
        (o) => !(o.organization_id === organizationId && o.org_role === orgRole),
      ));
    } catch { /* */ }
    setActorWorking(false);
  }

  const actorSummary = organizations.length === 0
    ? <em className="text-gray-500">No actors</em>
    : organizations.map((po) => {
        const orgName = orgs.find((o) => o.organization_id === po.organization_id)?.name ?? po.organization_id;
        const roleLabel = actorRoles.find((r) => r.key === po.org_role)?.label ?? po.org_role;
        return `${orgName} (${roleLabel})`;
      }).join(", ");

  return (
    <div className="border border-gray-200 rounded-lg">
      {/* Note: no overflow-hidden — LocationSearch uses a dropdown that must paint outside this card */}
      {/* Collapsed header — always visible; click to expand/collapse edit form */}
      <button
        onClick={onToggle}
        className={`group w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-slate-50 transition-colors cursor-pointer ${
          expanded ? "rounded-t-lg" : "rounded-lg"
        }`}
        title={expanded ? "Collapse" : "Click to edit"}
      >
        {/* Rotating chevron — right when collapsed, down when expanded */}
        <span
          className={`inline-block text-sm shrink-0 transition-transform duration-200 ${
            expanded ? "rotate-90 text-blue-500" : "text-gray-400"
          }`}
        >▶</span>
        <span className="font-mono text-xs text-gray-500 shrink-0">{pkg.package_code}</span>
        <span className={`font-medium text-sm flex-1 min-w-0 truncate ${expanded ? "text-blue-700" : "text-gray-800"}`}>
          {pkg.name}
        </span>
        <span className="text-xs text-gray-600 shrink-0 max-w-[40%] truncate" title={typeof actorSummary === "string" ? actorSummary : undefined}>
          {actorSummary}
        </span>
        {pkg.location_codes.length > 0 && (
          <div className="flex gap-1 shrink-0">
            {pkg.location_codes.map((c) => (
              <span key={c} className="text-xs font-mono bg-blue-100 text-blue-800 border border-blue-300 px-1.5 py-0.5 rounded">
                {c}
              </span>
            ))}
          </div>
        )}
        {!pkg.is_active && <span className="text-xs text-gray-500 shrink-0">(inactive)</span>}
        {/* Edit hint — visible on hover when collapsed */}
        {!expanded && (
          <span className="text-xs italic text-gray-500 opacity-0 group-hover:opacity-100 transition-opacity shrink-0 ml-1">
            edit
          </span>
        )}
      </button>

      {/* Expanded edit form */}
      {expanded && (
        <div className="border-t border-gray-100 px-4 py-4 bg-gray-50 space-y-4 rounded-b-lg">
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="text-xs font-medium text-gray-500 block mb-1">Name</label>
              <input
                value={nameVal}
                onChange={(e) => { setNameVal(e.target.value); setDirty(true); }}
                className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
            </div>
            <div className="col-span-2">
              <label className="text-xs font-medium text-gray-500 block mb-1">Description <span className="font-normal text-gray-400">(km range, scope)</span></label>
              <input
                value={descVal}
                onChange={(e) => { setDescVal(e.target.value); setDirty(true); }}
                placeholder="e.g. Km 0+000 to Km 45+000"
                className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
            </div>
            <div className="col-span-2">
              <label className="text-xs font-medium text-gray-500 block mb-2">Package actors</label>
              <p className="text-xs text-gray-400 mb-2">Overrides project-wide actor with the same role on this lot only.</p>
              {organizations.length === 0 ? (
                <p className="text-xs text-gray-400 italic mb-2">No package actors yet</p>
              ) : (
                <div className="border border-gray-200 rounded-lg overflow-hidden mb-2 max-w-xl bg-white">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-slate-50 text-left border-b border-gray-200">
                        <th className="px-3 py-2 text-xs font-medium text-gray-500">Organization</th>
                        <th className="px-3 py-2 text-xs font-medium text-gray-500">Role</th>
                        <th className="w-8" />
                      </tr>
                    </thead>
                    <tbody>
                      {organizations.map((po) => {
                        const orgName = orgs.find((o) => o.organization_id === po.organization_id)?.name ?? po.organization_id;
                        const roleLabel = actorRoles.find((r) => r.key === po.org_role)?.label ?? po.org_role;
                        return (
                          <tr key={`${po.organization_id}-${po.org_role}`} className="border-t border-gray-100">
                            <td className="px-3 py-2 font-medium text-gray-800">{orgName}</td>
                            <td className="px-3 py-2 text-xs text-gray-600">{roleLabel}</td>
                            <td className="px-3 py-2 text-right">
                              <button type="button" disabled={actorWorking}
                                onClick={() => void handleRemoveActor(po.organization_id, po.org_role)}
                                className="text-gray-300 hover:text-red-500 text-lg leading-none disabled:opacity-40">×</button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
              <div className="flex flex-wrap items-center gap-2">
                <select value={addingOrg} onChange={(e) => setAddingOrg(e.target.value)}
                  className="text-sm border border-gray-300 rounded px-2 py-1.5">
                  <option value="">— organization —</option>
                  {orgs.map((o) => <option key={o.organization_id} value={o.organization_id}>{o.name}</option>)}
                </select>
                <select value={addingRole} onChange={(e) => setAddingRole(e.target.value)}
                  className="text-sm border border-gray-300 rounded px-2 py-1.5">
                  {actorRoles.map((r) => <option key={r.key} value={r.key}>{r.label}</option>)}
                </select>
                <button type="button" onClick={() => void handleAddActor()}
                  disabled={!addingOrg || !addingRole || actorWorking}
                  className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700 disabled:opacity-50">
                  Add
                </button>
              </div>
            </div>
            <div className="flex items-end pb-1">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={pkg.is_active}
                  onChange={(e) => onUpdate({ is_active: e.target.checked })}
                  className="w-4 h-4 rounded"
                />
                <span className="text-sm text-gray-700">Active</span>
              </label>
            </div>
          </div>

          {/* Locations */}
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-2">Districts / locations covered</label>
            <div className="flex flex-wrap gap-1.5 mb-2">
              {pkg.location_codes.length === 0 && (
                <span className="text-xs text-gray-400 italic">No locations linked</span>
              )}
              {pkg.location_codes.map((c) => (
                <span key={c} className="flex items-center gap-1 text-xs font-mono bg-blue-100 text-blue-800 border border-blue-300 px-2 py-0.5 rounded-full">
                  {c}
                  <button onClick={() => onRemoveLoc(c)} className="text-blue-600 hover:text-red-600 leading-none">×</button>
                </span>
              ))}
            </div>
            <LocationSearch
              country="NP"
              placeholder="Search district or municipality…"
              excludeCodes={pkg.location_codes}
              onSelect={(code) => onAddLoc(code)}
            />
          </div>

          {dirty && (
            <div className="flex justify-end pt-1">
              <button
                onClick={handleSave}
                disabled={saving || !nameVal.trim()}
                className="text-sm bg-blue-600 text-white px-4 py-1.5 rounded font-medium hover:bg-blue-700 disabled:opacity-50 transition"
              >
                {saving ? "Saving…" : "Save changes"}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Package create modal ──────────────────────────────────────────────────────

function PackageCreateModal({
  projectId, onCreated, onClose,
}: {
  projectId: string;
  onCreated: (pkg: PackageItem) => void;
  onClose: () => void;
}) {
  const [code, setCode]       = useState("");
  const [name, setName]       = useState("");
  const [desc, setDesc]       = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError]     = useState("");

  async function handleCreate() {
    if (!code.trim() || !name.trim()) { setError("Package code and name are required."); return; }
    setCreating(true); setError("");
    try {
      const pkg = await createPackage(projectId, {
        package_code: code.trim(),
        name: name.trim(),
        description: desc.trim() || null,
      });
      onCreated(pkg);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Create failed";
      setError(msg.includes("409") ? `Code "${code.trim()}" already exists in this project.` : msg);
      setCreating(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 overflow-hidden">
        <div className="bg-slate-700 text-white px-6 py-4 flex items-center justify-between">
          <div className="font-semibold">New package</div>
          <button onClick={onClose} className="text-slate-300 hover:text-white text-xl leading-none">×</button>
        </div>
        <div className="p-6 space-y-4">
          {error && <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>}
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Package / lot code *</label>
            <input autoFocus value={code} onChange={(e) => setCode(e.target.value)}
              placeholder="e.g. SHEP/OCB/KL/01"
              className="w-full text-sm font-mono border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Name *</label>
            <input value={name} onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Lot 1 — Kakarbhitta to Sitapur"
              className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Description</label>
            <input value={desc} onChange={(e) => setDesc(e.target.value)}
              placeholder="e.g. Km 0+000 to Km 45+000"
              className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
          </div>
          <p className="text-xs text-gray-500">Assign package actors after creating the lot.</p>
        </div>
        <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-3">
          <button onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700 px-4 py-1.5 rounded">Cancel</button>
          <button onClick={handleCreate} disabled={creating || !code.trim() || !name.trim()}
            className="text-sm bg-blue-600 text-white hover:bg-blue-700 px-4 py-1.5 rounded font-medium disabled:opacity-50 transition">
            {creating ? "Creating…" : "Create package"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── System Config tab (super_admin only) ─────────────────────────────────────

const DEFAULT_REPORT_LIMITS_JSON = {
  max_export_rows: 100,
  max_exports_per_user_per_hour: 10,
  max_reports_per_role_per_quarter: 3,
  quarterly_email_enabled: true,
  allowed_recipient_roles: [
    "adb_national_project_director",
    "adb_hq_safeguards",
    "adb_hq_project",
    "mopit_rep",
    "dor_rep",
  ],
};

const DEFAULT_ARCHIVING_POLICY_JSON = {
  enabled: true,
  years_before_archiving: 1,
  archive_run_month: 1,
  archive_run_day: 2,
  timezone: "Asia/Kathmandu",
  attachment_tier_on_archive: "none",
  allow_complainant_download_when_archived: false,
  seah_years_before_archiving: null,
};

function SystemConfigTab() {
  const [jsonText, setJsonText] = useState("");
  const [limitsJson, setLimitsJson] = useState("");
  const [archivingJson, setArchivingJson] = useState("");
  const [loading, setLoading]   = useState(true);
  const [saving, setSaving]     = useState(false);
  const [savingLimits, setSavingLimits] = useState(false);
  const [savingArchiving, setSavingArchiving] = useState(false);
  const [error, setError]       = useState("");
  const [limitsError, setLimitsError] = useState("");
  const [archivingError, setArchivingError] = useState("");
  const [saved, setSaved]       = useState(false);
  const [limitsSaved, setLimitsSaved] = useState(false);
  const [archivingSaved, setArchivingSaved] = useState(false);

  useEffect(() => {
    Promise.all([
      getOrgRoles().catch(() => null),
      getReportLimits().catch(() => null),
      getArchivingPolicy().catch(() => null),
    ])
      .then(([roles, limits, archiving]) => {
        if (roles) {
          setJsonText(JSON.stringify(roles, null, 2));
        } else {
          setJsonText(
            JSON.stringify(
              [
                { key: "donor", label: "Donor", description: "Financing institution (e.g. ADB, World Bank)" },
                { key: "executing_agency", label: "Executing Agency", description: "Government project owner" },
                { key: "implementing_agency", label: "Implementing Agency", description: "Government implementation arm" },
                { key: "main_contractor", label: "Main Contractor", description: "Primary civil-works contractor" },
                { key: "subcontractor_t1", label: "Subcontractor (Tier 1)", description: "First-tier subcontractor" },
                { key: "subcontractor_t2", label: "Subcontractor (Tier 2)", description: "Second-tier subcontractor" },
                { key: "supervision_consultant", label: "Supervision Consultant", description: "Engineer's Representative" },
                { key: "specialized_consultant", label: "Specialized Consultant", description: "Safeguards, resettlement, etc." },
              ],
              null,
              2,
            ),
          );
        }
        setLimitsJson(JSON.stringify(limits ?? DEFAULT_REPORT_LIMITS_JSON, null, 2));
        setArchivingJson(JSON.stringify(archiving ?? DEFAULT_ARCHIVING_POLICY_JSON, null, 2));
      })
      .finally(() => setLoading(false));
  }, []);

  async function handleSave() {
    setSaving(true); setError(""); setSaved(false);
    try {
      const parsed = JSON.parse(jsonText);
      if (!Array.isArray(parsed)) throw new Error("Must be a JSON array");
      for (const item of parsed) {
        if (!item.key || !item.label) throw new Error(`Each entry needs "key" and "label". Missing on: ${JSON.stringify(item)}`);
      }
      await setOrgRoles(parsed);
      setSaved(true); setTimeout(() => setSaved(false), 2500);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Invalid JSON");
    }
    setSaving(false);
  }

  async function handleSaveLimits() {
    setSavingLimits(true);
    setLimitsError("");
    setLimitsSaved(false);
    try {
      const parsed = JSON.parse(limitsJson);
      if (typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("Must be a JSON object");
      }
      await setReportLimits(parsed);
      setLimitsSaved(true);
      setTimeout(() => setLimitsSaved(false), 2500);
    } catch (e: unknown) {
      setLimitsError(e instanceof Error ? e.message : "Invalid JSON");
    }
    setSavingLimits(false);
  }

  async function handleSaveArchiving() {
    setSavingArchiving(true);
    setArchivingError("");
    setArchivingSaved(false);
    try {
      const parsed = JSON.parse(archivingJson);
      if (typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("Must be a JSON object");
      }
      await setArchivingPolicy(parsed);
      setArchivingSaved(true);
      setTimeout(() => setArchivingSaved(false), 2500);
    } catch (e: unknown) {
      setArchivingError(e instanceof Error ? e.message : "Invalid JSON");
    }
    setSavingArchiving(false);
  }

  return (
    <div className="max-w-2xl">
      <div className="mb-5">
        <h2 className="text-base font-semibold text-gray-800 mb-0.5">System Configuration</h2>
        <p className="text-xs text-gray-500">
          Super-admin only. Settings here rarely need changing. Edit JSON directly — like VS Code settings.
        </p>
      </div>

      {/* Org Roles section */}
      <section className="bg-gray-50 border border-gray-200 rounded-lg p-5">
        <div className="mb-3">
          <h3 className="text-sm font-semibold text-gray-700 mb-0.5">Organization Role Vocabulary</h3>
          <p className="text-xs text-gray-500 leading-relaxed">
            Defines the roles organizations can hold within a project (donor, contractor, consultant, etc.).
            Used in the Projects editor. Each entry requires <code className="bg-gray-200 px-1 rounded text-xs">key</code>,{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">label</code>, and optionally{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">description</code>.
          </p>
        </div>

        {loading ? (
          <p className="text-sm text-gray-400 animate-pulse">Loading…</p>
        ) : (
          <textarea
            value={jsonText}
            onChange={(e) => setJsonText(e.target.value)}
            rows={24}
            spellCheck={false}
            className="w-full font-mono text-xs bg-white border border-gray-300 rounded px-3 py-2.5 focus:outline-none focus:ring-1 focus:ring-blue-400 resize-y"
          />
        )}

        {error && (
          <p className="mt-2 text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
            {error}
          </p>
        )}

        <div className="mt-3 flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving || loading}
            className="text-sm bg-blue-600 text-white px-4 py-1.5 rounded font-medium hover:bg-blue-700 disabled:opacity-50 transition"
          >
            {saving ? "Saving…" : "Save"}
          </button>
          {saved && <span className="text-xs text-green-600 font-medium">✓ Saved</span>}
          <span className="text-xs text-gray-400 ml-auto">
            Changes take effect on next project editor load
          </span>
        </div>
      </section>

      <section className="bg-gray-50 border border-gray-200 rounded-lg p-5 mt-6">
        <div className="mb-3">
          <h3 className="text-sm font-semibold text-gray-700 mb-0.5">Report dispatch limits</h3>
          <p className="text-xs text-gray-500 leading-relaxed">
            Caps exports and quarterly emails for all projects. Local admins configure templates
            within these limits. Keys:{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">max_export_rows</code>,{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">max_exports_per_user_per_hour</code>,{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">max_reports_per_role_per_quarter</code>,{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">quarterly_email_enabled</code>,{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">allowed_recipient_roles</code>.
          </p>
        </div>
        <textarea
          value={limitsJson}
          onChange={(e) => setLimitsJson(e.target.value)}
          rows={16}
          spellCheck={false}
          disabled={loading}
          className="w-full font-mono text-xs bg-white border border-gray-300 rounded px-3 py-2.5 focus:outline-none focus:ring-1 focus:ring-blue-400 resize-y"
        />
        {limitsError && (
          <p className="mt-2 text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
            {limitsError}
          </p>
        )}
        <div className="mt-3 flex items-center gap-3">
          <button
            type="button"
            onClick={handleSaveLimits}
            disabled={savingLimits || loading}
            className="text-sm bg-blue-600 text-white px-4 py-1.5 rounded font-medium hover:bg-blue-700 disabled:opacity-50 transition"
          >
            {savingLimits ? "Saving…" : "Save report limits"}
          </button>
          {limitsSaved && <span className="text-xs text-green-600 font-medium">✓ Saved</span>}
        </div>
      </section>

      <section className="bg-gray-50 border border-gray-200 rounded-lg p-5 mt-6">
        <div className="mb-3">
          <h3 className="text-sm font-semibold text-gray-700 mb-0.5">Archiving and retention</h3>
          <p className="text-xs text-gray-500 leading-relaxed">
            Resolved cases archive after{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">years_before_archiving</code> full
            calendar years (eligible from 2 January). Daily Celery job at 03:00 Asia/Kathmandu.
            Keys:{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">enabled</code>,{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">years_before_archiving</code>,{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">attachment_tier_on_archive</code>,{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">seah_years_before_archiving</code>.
          </p>
        </div>
        <textarea
          value={archivingJson}
          onChange={(e) => setArchivingJson(e.target.value)}
          rows={14}
          spellCheck={false}
          disabled={loading}
          className="w-full font-mono text-xs bg-white border border-gray-300 rounded px-3 py-2.5 focus:outline-none focus:ring-1 focus:ring-blue-400 resize-y"
        />
        {archivingError && (
          <p className="mt-2 text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
            {archivingError}
          </p>
        )}
        <div className="mt-3 flex items-center gap-3">
          <button
            type="button"
            onClick={handleSaveArchiving}
            disabled={savingArchiving || loading}
            className="text-sm bg-blue-600 text-white px-4 py-1.5 rounded font-medium hover:bg-blue-700 disabled:opacity-50 transition"
          >
            {savingArchiving ? "Saving…" : "Save archiving policy"}
          </button>
          {archivingSaved && <span className="text-xs text-green-600 font-medium">✓ Saved</span>}
        </div>
      </section>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

function ComingSoon({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <Construction size={40} strokeWidth={1.25} className="mb-4 text-gray-300" />
      <h3 className="text-base font-semibold text-gray-700 mb-1">{label}</h3>
      <p className="text-sm text-gray-400 max-w-xs">
        This section is coming in Week 3. Contact your administrator to make changes directly.
      </p>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

function SettingsSubTabs<T extends string>({
  tabs,
  active,
  onChange,
}: {
  tabs: { id: T; label: string }[];
  active: T;
  onChange: (id: T) => void;
}) {
  return (
    <div className="flex gap-0 border-b border-gray-200 mb-6">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          onClick={() => onChange(tab.id)}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            active === tab.id
              ? "border-blue-500 text-blue-600"
              : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

export default function SettingsPage() {
  const {
    isAdmin,
    isSuperAdmin,
    isCountryAdmin,
    isProjectAdmin,
    canAccessPlatformSettings,
    canCreateOperationalRoles,
    adminWorkflowTracks,
  } = useAuth();
  const mainTabs = useMemo(() => {
    if (isSuperAdmin) return MAIN_TABS;
    if (isCountryAdmin) {
      const tabs = MAIN_TABS.filter((t) => t.id !== "platform");
      if (!adminWorkflowTracks.includes("standard")) {
        return tabs.filter((t) => t.id !== "projects" || adminWorkflowTracks.includes("seah"));
      }
      return tabs;
    }
    if (isProjectAdmin) {
      return MAIN_TABS.filter((t) => t.id === "org_officers" || t.id === "workflows_roles" || t.id === "projects");
    }
    if (isAdmin) return MAIN_TABS.filter((t) => t.id === "projects");
    return MAIN_TABS.filter((t) => t.id === "projects");
  }, [isSuperAdmin, isCountryAdmin, isProjectAdmin, isAdmin, adminWorkflowTracks]);
  const [activeMain, setActiveMain] = useState<MainTab>("projects");
  const [orgSub, setOrgSub] = useState<OrgOfficersSub>("organizations");
  const [wfSub, setWfSub] = useState<WorkflowsRolesSub>("workflows");
  const [platformSub, setPlatformSub] = useState<PlatformSub>("locations");
  const [jumpProjectId, setJumpProjectId] = useState<string | null>(null);
  const [roleCatalog, setRoleCatalog]     = useState<RoleEntry[]>([]);
  const [rolesLoading, setRolesLoading] = useState(true);

  const grmRoleChoices = useMemo(
    () => roleCatalog.map((r) => ({ key: r.key, label: r.label })),
    [roleCatalog],
  );

  const loadRoleCatalog = useCallback(async () => {
    setRolesLoading(true);
    try {
      const raw = await listRoles({ kind: "operational" });
      setRoleCatalog(raw.map(mapGrmRoleToEntry));
    } catch {
      setRoleCatalog([]);
    } finally {
      setRolesLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRoleCatalog();
  }, [loadRoleCatalog]);

  useEffect(() => {
    if (!mainTabs.some((t) => t.id === activeMain)) {
      setActiveMain(mainTabs[0]?.id ?? "projects");
    }
  }, [mainTabs, activeMain]);

  function navigateToProject(projectId: string) {
    setJumpProjectId(projectId);
    setActiveMain("projects");
  }

  if (!isAdmin) {
    return (
      <div className="p-8 text-center">
        <Lock size={32} strokeWidth={1.5} className="mx-auto mb-3 text-gray-300" />
        <p className="text-sm text-gray-500">Settings are only accessible to administrators.</p>
      </div>
    );
  }

  const platformTabs: { id: PlatformSub; label: string }[] = useMemo(() => {
    if (canAccessPlatformSettings) {
      return [
        { id: "locations", label: "Locations" },
        { id: "reports", label: "Quarterly reports" },
        { id: "project_types", label: "Project types" },
        { id: "system_config", label: "Advanced (JSON)" },
        { id: "admin_access", label: "Admin access" },
      ];
    }
    return [];
  }, [canAccessPlatformSettings]);

  useEffect(() => {
    if (!canAccessPlatformSettings && platformSub !== "reports") {
      setPlatformSub("locations");
    }
  }, [canAccessPlatformSettings, platformSub]);

  return (
    <div className="p-6">
      <div className="mb-5">
        <h1 className="text-xl font-semibold text-gray-800">{isSuperAdmin ? "Settings" : "Project setup"}</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          {isSuperAdmin
            ? "Admin configuration — organizations, projects, workflows, and platform data"
            : "Add partner organizations, invite officers, link locations, and complete go-live checks."}
        </p>
      </div>

      {mainTabs.length > 1 && (
      <div className="flex gap-0 border-b border-gray-200 mb-4 overflow-x-auto">
        {mainTabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveMain(tab.id)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
              activeMain === tab.id
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      )}

      {activeMain === "org_officers" && (
        <>
          <SettingsSubTabs
            tabs={[
              { id: "organizations", label: "Organizations" },
              { id: "officers", label: "Officers" },
            ]}
            active={orgSub}
            onChange={setOrgSub}
          />
          {orgSub === "organizations" && <OrgsSection onNavigateToProject={navigateToProject} />}
          {orgSub === "officers" && (
            <OfficersTab roleCatalog={roleCatalog} allowGlobalInvite={isSuperAdmin} />
          )}
        </>
      )}

      {activeMain === "workflows_roles" && (
        <>
          <SettingsSubTabs
            tabs={[
              { id: "workflows", label: "Workflows" },
              { id: "roles", label: "Roles & permissions" },
            ]}
            active={wfSub}
            onChange={setWfSub}
          />
          {wfSub === "workflows" && (
            <WorkflowsTab
              roleCatalog={roleCatalog}
              canCreateRole={canCreateOperationalRoles}
              onRoleCatalogRefresh={loadRoleCatalog}
            />
          )}
          {wfSub === "roles" && (
            <RolesTab
              catalog={roleCatalog}
              loading={rolesLoading}
              onReload={loadRoleCatalog}
              canCreate={canCreateOperationalRoles}
            />
          )}
        </>
      )}

      {activeMain === "projects" && (
        <ProjectsSection initialEditId={jumpProjectId} grmRoleChoices={grmRoleChoices} isSuperAdmin={isSuperAdmin} />
      )}

      {activeMain === "platform" && (
        <>
          <SettingsSubTabs tabs={platformTabs} active={platformSub} onChange={setPlatformSub} />
          {platformSub === "locations" && <LocationsSection />}
          {platformSub === "reports" && <QuarterlyReportSettings />}
          {platformSub === "project_types" && isSuperAdmin && <ProjectTypesTab />}
          {platformSub === "system_config" && isSuperAdmin && <SystemConfigTab />}
          {platformSub === "admin_access" && isSuperAdmin && <AdminAccessTab />}
        </>
      )}
    </div>
  );
}
