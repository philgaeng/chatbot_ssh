"use client";

import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { AlertTriangle, X, Lock, Construction } from "lucide-react";
import { useAuth } from "@/app/providers/AuthProvider";
import { QuarterlyReportSettings } from "@/components/settings/QuarterlyReportSettings";
import {
  listWorkflows,
  listTemplates,
  listScopes,
  addScope,
  deleteScope,
  listOrganizations,
  listProjects,
  listProjectTypes,
  createProject,
  updateProject,
  deleteProject,
  addProjectOrg,
  removeProjectOrg,
  addProjectLocation,
  removeProjectLocation,
  updateProjectOrgRole,
  getOrgRoles,
  getProjectActorRoles,
  setProjectActorRoles,
  getProjectMessaging,
  patchProjectMessaging,
  type ProjectMessagingConfig,
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
  type WorkflowAssignmentItem,
  type OfficerScope,
  type OrganizationItem,
  type ProjectItem,
  type WorkflowRoutingOptions,
  type ProjectOrgItem,
  type OrgRole,
  listWorkflowRoutingOptions,
  type PackageItem,
  type PackageCreate,
  listRoles,
} from "@/lib/api";
import {
  normalizeEntityCodeInput,
  suggestNextPackageCode,
  validateEntityCode,
  ENTITY_CODE_MAX_LEN,
} from "@/lib/entityCodes";
import { ProjectStaffingSection } from "@/components/settings/ProjectStaffingSection";
import { ProjectOfficerModal } from "@/components/settings/ProjectOfficerModal";
import { ProjectGoLivePanel } from "@/components/settings/ProjectGoLivePanel";
import { ProjectTypesTab } from "@/components/settings/ProjectTypesTab";
import { ProjectActorAddRow } from "@/components/settings/ProjectActorAddRow";
import { LocationSearch } from "@/components/LocationSearch";
import { orgRoleBadge } from "@/lib/design-tokens";
// RB-2/RB-4: the god-file's flat OrgsSection + actor-role editor are replaced by the
// decomposed org-chart surfaces (tree + CSV + position types) and the doc-13 participant model.
import { OrganisationTab } from "@/components/settings/org/OrganisationTab";
import { OfficersTabV2 } from "@/components/settings/officers-v2/OfficersTabV2";
import { ProjectParticipants } from "@/components/settings/projects/ProjectParticipants";
import { SetupOverview } from "@/components/settings/overview/SetupOverview";
// R6 (BUILD-REVIEW M4/M7): plain-language labels in the still-inline clusters (labels not slugs).
// R5 (BUILD-REVIEW M3): the friendly-error contract — inline clusters route caught errors
// through formatUserFacingError (unwraps object 4xx detail) instead of raw messages or browser dialogs.
import { friendlyError } from "@/components/settings/lib/friendlyError";
import { AdminAccessTab } from "@/components/settings/platform/AdminAccessTab";
import { LocationsSection } from "@/components/settings/platform/LocationsSection";
import { SystemConfigTab } from "@/components/settings/platform/SystemConfigTab";
import { type RoleEntry, mapGrmRoleToEntry } from "@/components/settings/roles/roleEntry";
import { RolesTab } from "@/components/settings/roles/RolesTab";
import { WorkflowsTab } from "@/components/settings/workflows/WorkflowsTab";
import { ProjectWorkflowsEditor } from "@/components/settings/workflows/ProjectWorkflowsEditor";

type MainTab = "setup" | "org_officers" | "workflows_roles" | "projects" | "platform";
type OrgOfficersSub = "organizations" | "officers";
type WorkflowsRolesSub = "workflows" | "roles";
type PlatformSub = "locations" | "reports" | "project_types" | "system_config" | "admin_access";

const MAIN_TABS: { id: MainTab; label: string }[] = [
  { id: "setup",             label: "Setup & go-live" },   // R8: Frame 01 landing
  { id: "org_officers",      label: "Organizations & officers" },
  { id: "workflows_roles",   label: "Workflows, roles & permissions" },
  { id: "projects",          label: "Projects & packages" },
  { id: "platform",          label: "Settings" },
];

// Org-role badge colors now live in lib/design-tokens.ts (orgRoleBadge) — the banned-hue
// map that used to be here (purple/indigo/orange/teal) is gone (RB-2 §7.C, F24).

// ── Projects section ──────────────────────────────────────────────────────────

function ProjectsSection({
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
      p.sort((a, b) => {
        if (a.is_active !== b.is_active) return a.is_active ? -1 : 1;
        return a.short_code.localeCompare(b.short_code);
      });
      setProjects(p);
      setOrgs(o);
      setOrgRoles(r);
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
  const [resumeProject, setResumeProject] = useState<ProjectItem | null>(null);

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
    if (!name.trim()) { setError("Project name is required."); return; }
    const codeErr = validateEntityCode(shortCode, "Project code");
    if (codeErr) { setError(codeErr); return; }
    if (!typeKey) { setError("Select a project type."); return; }
    setCreating(true);
    setError("");
    setResumeProject(null);
    const code = normalizeEntityCodeInput(shortCode);
    try {
      const p = await createProject({
        name: name.trim(),
        short_code: code,
        country_code: country,
        description: desc.trim() || null,
        project_type_key: typeKey,
        is_active: false,
      });
      onCreated(p);
    } catch (e: unknown) {
      const msg = friendlyError(e);
      if (msg.includes("already exists")) {
        try {
          const existing = (await listProjects(undefined, false)).find((p) => p.short_code === code) ?? null;
          setResumeProject(existing);
          if (existing) {
            setError(
              `Project code “${code}” is already in use (${existing.is_active ? "active" : "inactive, awaiting setup"}).`,
            );
          } else {
            setError(`${msg} Refresh the project list or contact an administrator.`);
          }
        } catch {
          setError(msg);
        }
      } else {
        setError(msg);
      }
      setCreating(false);
    }
  }

  function handleResumeSetup() {
    if (resumeProject) onCreated(resumeProject);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 overflow-hidden">
        <div className="bg-slate-700 text-white px-6 py-4 flex items-center justify-between">
          <div className="font-semibold">New project</div>
          <button onClick={onClose} className="text-slate-300 hover:text-white text-xl leading-none">×</button>
        </div>
        <div className="p-6 space-y-4">
          {error && (
            <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2 space-y-2">
              <p>{error}</p>
              {resumeProject && (
                <button
                  type="button"
                  onClick={handleResumeSetup}
                  className="text-sm font-medium text-blue-700 hover:text-blue-900 underline"
                >
                  Resume setup — {resumeProject.short_code}
                  {!resumeProject.is_active ? " (inactive)" : ""}
                </button>
              )}
            </div>
          )}
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
                Clicking Create saves the project immediately — use Set up to finish configuration before activating.
              </p>
            </div>
            <div className="col-span-2">
              <label className="text-xs font-medium text-gray-500 block mb-1">Project name *</label>
              <input autoFocus value={name} onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Kakarbhitta-Laukahi Road"
                className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">Project code * <span className="font-normal text-gray-400">(unique, max {ENTITY_CODE_MAX_LEN})</span></label>
              <input value={shortCode} onChange={(e) => {
                setShortCode(normalizeEntityCodeInput(e.target.value));
                setResumeProject(null);
                setError("");
              }}
                placeholder="KL_ROAD"
                maxLength={ENTITY_CODE_MAX_LEN}
                className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 font-mono focus:outline-none focus:ring-1 focus:ring-blue-400" />
              <p className="text-xs text-gray-400 mt-1">A–Z, 0–9, underscore only.</p>
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
  isCountryAdmin,
  canManageProjectCatalog,
  canManageStructure,
  adminWorkflowTracks,
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
  isCountryAdmin: boolean;
  canManageProjectCatalog: boolean;
  canManageStructure: boolean;
  adminWorkflowTracks: ("standard" | "seah")[];
  showBack?: boolean;
  onBack: () => void;
  onUpdated: (p: ProjectItem) => void;
  onOrganizationCreated: (org: OrganizationItem) => void;
}) {
  const [p, setP]             = useState<ProjectItem>(initial);
  const [editingName, setEditingName] = useState(false);
  const [editingShortCode, setEditingShortCode] = useState(false);
  const [nameVal, setNameVal] = useState(p.name);
  const [shortCodeVal, setShortCodeVal] = useState(p.short_code);
  const [descVal, setDescVal] = useState(p.description ?? "");
  const [msg, setMsg]         = useState("");
  const [working, setWorking] = useState(false);
  const [locError, setLocError] = useState("");
  const { canSeeSeah } = useAuth();
  const [projectActorRoles, setProjectActorRolesState] = useState<OrgRole[]>(orgRoles);
  const [rolesSaving, setRolesSaving] = useState(false);
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([]);
  const [wfTemplates, setWfTemplates] = useState<WorkflowDefinition[]>([]);
  const [routingOptions, setRoutingOptions] = useState<WorkflowRoutingOptions | null>(null);
  const [wfSaving, setWfSaving] = useState(false);
  const [goLiveKey, setGoLiveKey] = useState(0);
  const [messaging, setMessaging] = useState<ProjectMessagingConfig | null>(null);
  const [messagingSaving, setMessagingSaving] = useState(false);
  const sectionRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const typedProject = Boolean(p.project_type_key);
  const lockTypeConfig = typedProject && !isSuperAdmin && !isCountryAdmin;
  const canEditProjectWorkflows = isSuperAdmin || isCountryAdmin;
  const canEditMessaging = isSuperAdmin || isCountryAdmin;

  function canEditWorkflowTrack(track: "standard" | "seah") {
    if (isSuperAdmin) return true;
    if (!isCountryAdmin) return false;
    return adminWorkflowTracks.includes(track);
  }

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
      flash(friendlyError(e));
    }
  }

  useEffect(() => {
    listWorkflows().then((r) => setWorkflows(r.items)).catch(() => {});
    listTemplates().then((r) => setWfTemplates(r.items)).catch(() => {});
    listWorkflowRoutingOptions().then(setRoutingOptions).catch(() => {});
  }, []);

  useEffect(() => {
    getProjectActorRoles(p.project_id)
      .then(setProjectActorRolesState)
      .catch(() => setProjectActorRolesState(orgRoles));
  }, [p.project_id, orgRoles]);

  useEffect(() => {
    getProjectMessaging(p.project_id)
      .then(setMessaging)
      .catch(() => setMessaging(null));
  }, [p.project_id]);

  useEffect(() => {
    setNameVal(p.name);
    setShortCodeVal(p.short_code);
    setDescVal(p.description ?? "");
  }, [p.project_id, p.name, p.short_code, p.description]);

  function flash(t: string) { setMsg(t); setTimeout(() => setMsg(""), 2500); }

  async function saveMeta() {
    try {
      const updated = await updateProject(p.project_id, { name: nameVal.trim(), description: descVal.trim() || null });
      setP(updated); onUpdated(updated); flash("Saved ✓");
    } catch { flash("Save failed"); }
    setEditingName(false);
  }

  async function saveShortCode() {
    const codeErr = validateEntityCode(shortCodeVal, "Project code");
    if (codeErr) { flash(codeErr); return; }
    const normalized = normalizeEntityCodeInput(shortCodeVal);
    if (normalized === p.short_code) {
      setEditingShortCode(false);
      return;
    }
    try {
      const updated = await updateProject(p.project_id, { short_code: normalized });
      setP(updated);
      onUpdated(updated);
      setShortCodeVal(updated.short_code);
      flash("Project code updated ✓");
    } catch (e: unknown) {
      flash(friendlyError(e));
      setShortCodeVal(p.short_code);
    }
    setEditingShortCode(false);
  }

  async function linkProjectActor(organizationId: string, orgRole: string) {
    setWorking(true);
    try {
      const item = await addProjectOrg(p.project_id, organizationId, orgRole || null);
      setP({ ...p, organizations: [...p.organizations, item] });
      flash("Project actor added ✓");
    } catch (e: unknown) {
      flash(friendlyError(e));
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
              {canManageProjectCatalog ? "← Projects" : "← All projects"}
            </button>
            <span className="text-gray-300">/</span>
          </>
        )}
        {canManageProjectCatalog && editingName ? (
          <div className="flex items-center gap-2">
            <input autoFocus value={nameVal} onChange={(e) => setNameVal(e.target.value)}
              onBlur={saveMeta} onKeyDown={(e) => e.key === "Enter" && saveMeta()}
              className="text-lg font-semibold text-gray-800 border-b-2 border-blue-400 bg-transparent focus:outline-none" />
          </div>
        ) : (
          <h2
            className={`text-lg font-semibold text-gray-800${canManageProjectCatalog ? " cursor-pointer hover:text-blue-600" : ""}`}
            onClick={canManageProjectCatalog ? () => setEditingName(true) : undefined}
            title={canManageProjectCatalog ? "Click to rename" : undefined}
          >
            {p.name}
          </h2>
        )}
        {canManageProjectCatalog && editingShortCode ? (
          <input
            autoFocus
            value={shortCodeVal}
            onChange={(e) => setShortCodeVal(normalizeEntityCodeInput(e.target.value))}
            onBlur={() => void saveShortCode()}
            onKeyDown={(e) => {
              if (e.key === "Enter") void saveShortCode();
              if (e.key === "Escape") {
                setShortCodeVal(p.short_code);
                setEditingShortCode(false);
              }
            }}
            maxLength={ENTITY_CODE_MAX_LEN}
            className="font-mono text-sm text-gray-600 border-b-2 border-blue-400 bg-transparent focus:outline-none w-24"
          />
        ) : (
          <span
            className={`font-mono text-sm text-gray-400${canManageProjectCatalog ? " cursor-pointer hover:text-blue-600" : ""}`}
            onClick={canManageProjectCatalog ? () => setEditingShortCode(true) : undefined}
            title={canManageProjectCatalog ? "Click to edit project code" : undefined}
          >
            {p.short_code}
          </span>
        )}
        {p.project_type_key && (
          <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-mono">{p.project_type_key}</span>
        )}
        {!p.is_active && <span className="text-xs text-amber-700 bg-amber-50 px-2 py-0.5 rounded">Inactive</span>}
        {canManageProjectCatalog && (
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

      {/* Grievance workflows — super_admin + country_admin (per workflow_track) */}
      {(canEditProjectWorkflows || (p.workflow_slots?.length ?? 0) > 0) && (
      <div
        ref={(el) => { sectionRefs.current.workflows = el; }}
        className="mb-6 border border-gray-200 rounded-lg p-4 bg-gray-50/60 max-w-2xl space-y-4"
      >
        <div>
          <h3 className="text-sm font-semibold text-gray-700">Grievance workflows</h3>
          <p className="text-xs text-gray-500 mt-1">
            Add published workflows and map taxonomy <strong>classifications</strong> and intake paths.
            One row must be <strong>Default</strong> (catch-all). Officers match each step&apos;s role via project staffing.
            {lockTypeConfig
              ? " Defaults come from the project type; super admin may override."
              : " Edit step chains under Settings → Workflows."}
          </p>
        </div>
        <ProjectWorkflowsEditor
          project={p}
          workflows={workflows}
          wfTemplates={wfTemplates}
          routingOptions={routingOptions}
          canEdit={canEditProjectWorkflows}
          canEditWorkflowTrack={canEditWorkflowTrack}
          canSeeSeah={!!canSeeSeah}
          lockTypeConfig={lockTypeConfig}
          flash={flash}
          onSaved={(slots) => {
            const defaultRow = slots.find((s) => s.is_default);
            const seahRow = slots.find((s) => s.workflow_track === "seah");
            const updated: ProjectItem = {
              ...p,
              workflow_slots: slots,
              standard_workflow_id: defaultRow?.workflow_id ?? null,
              seah_workflow_id: seahRow?.workflow_id ?? null,
            };
            setP(updated);
            onUpdated(updated);
          }}
        />
      </div>
      )}

      {/* Messaging — officer SMS on assignment */}
      <div
        ref={(el) => { sectionRefs.current.messaging = el; }}
        className="mb-6 border border-gray-200 rounded-lg p-4 bg-gray-50/60 max-w-2xl space-y-4"
      >
        <div>
          <h3 className="text-sm font-semibold text-gray-700">Messaging</h3>
          <p className="text-xs text-gray-500 mt-1">
            Officers receive a link-only SMS when assigned at checked levels. No complainant details are included.
          </p>
        </div>
        {!messaging ? (
          <p className="text-xs text-gray-400 italic">Loading messaging settings…</p>
        ) : (
          <>
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={messaging.sms_enabled}
                disabled={!canEditMessaging || messagingSaving}
                onChange={(e) =>
                  setMessaging({ ...messaging, sms_enabled: e.target.checked })
                }
              />
              Officer SMS enabled
            </label>
            {messaging.max_levels > 0 ? (
              <div className="space-y-2">
                <p className="text-xs font-medium text-gray-500">SMS at workflow level</p>
                <div className="flex flex-wrap gap-3">
                  {Array.from({ length: messaging.max_levels }, (_, i) => i + 1).map((level) => (
                    <label key={level} className="flex items-center gap-1.5 text-sm text-gray-700">
                      <input
                        type="checkbox"
                        checked={messaging.sms_levels.includes(level)}
                        disabled={!canEditMessaging || !messaging.sms_enabled || messagingSaving}
                        onChange={(e) => {
                          const next = e.target.checked
                            ? [...messaging.sms_levels, level].sort((a, b) => a - b)
                            : messaging.sms_levels.filter((l) => l !== level);
                          setMessaging({ ...messaging, sms_levels: next });
                        }}
                      />
                      L{level}
                    </label>
                  ))}
                </div>
                <p className="text-xs font-medium text-gray-500 pt-1">WhatsApp (coming soon)</p>
                <div className="flex flex-wrap gap-3 opacity-50 pointer-events-none">
                  {Array.from({ length: messaging.max_levels }, (_, i) => i + 1).map((level) => (
                    <label key={`wa-${level}`} className="flex items-center gap-1.5 text-sm text-gray-500">
                      <input type="checkbox" disabled readOnly />
                      L{level}
                    </label>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-xs text-amber-700">
                Link a published workflow above to configure per-level SMS.
              </p>
            )}
            {canEditMessaging && (
              <button
                type="button"
                disabled={messagingSaving || messaging.max_levels === 0}
                onClick={async () => {
                  setMessagingSaving(true);
                  try {
                    const saved = await patchProjectMessaging(p.project_id, {
                      sms_enabled: messaging.sms_enabled,
                      sms_levels: messaging.sms_levels,
                      whatsapp_levels: messaging.whatsapp_levels,
                    });
                    setMessaging(saved);
                    setGoLiveKey((k) => k + 1);
                    flash("Messaging saved ✓");
                  } catch (e: unknown) {
                    flash(friendlyError(e));
                  } finally {
                    setMessagingSaving(false);
                  }
                }}
                className="text-xs px-3 py-1.5 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {messagingSaving ? "Saving…" : "Save messaging"}
              </button>
            )}
          </>
        )}
      </div>

      {/* doc-13 / DECISION 2026-07-10: the per-project actor-role catalog is retired in
          favour of a single implementing agency + optional donors (with the last-step
          donor guardrail). */}
      <div className="mb-6">
        <ProjectParticipants
          project={p}
          canEdit={canEditProjectWorkflows && !lockTypeConfig}
          onUpdated={() => onUpdated(p)}
        />
      </div>

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
                  const roleColor = po.org_role ? orgRoleBadge(po.org_role) : "";
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
            existingCodes={packages.map((pk) => pk.package_code)}
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
  const [codeVal, setCodeVal]       = useState(pkg.package_code);
  const [nameVal, setNameVal]       = useState(pkg.name);
  const [descVal, setDescVal]       = useState(pkg.description ?? "");
  const [addingOrg, setAddingOrg]   = useState("");
  const [addingRole, setAddingRole] = useState(actorRoles[0]?.key ?? "");
  const [actorWorking, setActorWorking] = useState(false);
  const [saving, setSaving]         = useState(false);
  const [dirty, setDirty]           = useState(false);

  const organizations = pkg.organizations ?? [];

  React.useEffect(() => {
    setCodeVal(pkg.package_code);
    setNameVal(pkg.name);
    setDescVal(pkg.description ?? "");
    setDirty(false);
  }, [pkg.package_id, pkg.package_code, pkg.name, pkg.description]);

  React.useEffect(() => {
    if (actorRoles.length && !actorRoles.some((r) => r.key === addingRole)) {
      setAddingRole(actorRoles[0].key);
    }
  }, [actorRoles, addingRole]);

  async function handleSave() {
    const codeErr = validateEntityCode(codeVal, "Package code");
    if (codeErr) return;
    setSaving(true);
    await onUpdate({
      package_code: normalizeEntityCodeInput(codeVal),
      name: nameVal.trim(),
      description: descVal.trim() || null,
    });
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
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">Package code</label>
              <input
                value={codeVal}
                onChange={(e) => { setCodeVal(normalizeEntityCodeInput(e.target.value)); setDirty(true); }}
                maxLength={ENTITY_CODE_MAX_LEN}
                className="w-full text-sm font-mono border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
            </div>
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
  projectId, existingCodes, onCreated, onClose,
}: {
  projectId: string;
  existingCodes: string[];
  onCreated: (pkg: PackageItem) => void;
  onClose: () => void;
}) {
  const [code, setCode]       = useState(() => suggestNextPackageCode(existingCodes));
  const [name, setName]       = useState("");
  const [desc, setDesc]       = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError]     = useState("");

  async function handleCreate() {
    if (!name.trim()) { setError("Package name is required."); return; }
    const codeErr = validateEntityCode(code, "Package code");
    if (codeErr) { setError(codeErr); return; }
    setCreating(true); setError("");
    try {
      const pkg = await createPackage(projectId, {
        package_code: normalizeEntityCodeInput(code),
        name: name.trim(),
        description: desc.trim() || null,
      });
      onCreated(pkg);
    } catch (e: unknown) {
      const msg = friendlyError(e);
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
            <label className="text-xs font-medium text-gray-500 block mb-1">Package code * <span className="font-normal text-gray-400">(unique within project)</span></label>
            <input autoFocus value={code} onChange={(e) => setCode(normalizeEntityCodeInput(e.target.value))}
              placeholder="01"
              maxLength={ENTITY_CODE_MAX_LEN}
              className="w-full text-sm font-mono border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
            <p className="text-xs text-gray-400 mt-1">Default is next lot number. A–Z, 0–9, underscore, max {ENTITY_CODE_MAX_LEN}.</p>
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
    canCreateProject,
    canManageStructure,
    canCreateOperationalRoles,
    adminWorkflowTracks,
  } = useAuth();
  const canManageProjectCatalog = isSuperAdmin || isCountryAdmin;
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
      return MAIN_TABS.filter((t) => t.id === "setup" || t.id === "org_officers" || t.id === "workflows_roles" || t.id === "projects");
    }
    if (isAdmin) return MAIN_TABS.filter((t) => t.id === "setup" || t.id === "projects");
    return MAIN_TABS.filter((t) => t.id === "setup" || t.id === "projects");
  }, [isSuperAdmin, isCountryAdmin, isProjectAdmin, isAdmin, adminWorkflowTracks]);
  const [activeMain, setActiveMain] = useState<MainTab>("setup");
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

  if (!isAdmin) {
    return (
      <div className="p-8 text-center">
        <Lock size={32} strokeWidth={1.5} className="mx-auto mb-3 text-gray-300" />
        <p className="text-sm text-gray-500">Settings are only accessible to administrators.</p>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-5">
        <h1 className="text-xl font-semibold text-gray-800">{canManageProjectCatalog ? "Settings" : "Project setup"}</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          {canManageProjectCatalog
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

      {activeMain === "setup" && <SetupOverview onOpenProject={navigateToProject} />}

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
          {orgSub === "organizations" && (
            <OrganisationTab canEdit={canManageStructure} canCreateRoot={isSuperAdmin} />
          )}
          {orgSub === "officers" && (
            <OfficersTabV2
              // R10 (BUILD-REVIEW MO1): managing officers is an officer-admin capability, not
              // org-structure — decouple from canManageStructure so a project_admin who can
              // invite can also manage/deactivate. (Backend already enforces the real scope.)
              canInvite={isSuperAdmin || isCountryAdmin || isProjectAdmin}
              canManage={isSuperAdmin || isCountryAdmin || isProjectAdmin}
            />
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
        <ProjectsSection
          initialEditId={jumpProjectId}
          grmRoleChoices={grmRoleChoices}
          isSuperAdmin={isSuperAdmin}
          isCountryAdmin={isCountryAdmin}
          adminWorkflowTracks={adminWorkflowTracks}
          canCreateProject={canCreateProject}
          canManageStructure={canManageStructure}
        />
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
