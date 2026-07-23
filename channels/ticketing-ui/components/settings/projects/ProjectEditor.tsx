"use client";

/**
 * <ProjectEditor> — the per-project frame: identity, participants (doc-13), locations,
 * packages, workflow bindings, staffing, messaging and go-live.
 *
 * Imports <ProjectWorkflowsEditor> from the workflows cluster — the spec's
 * cross-cluster seam #2.
 *
 * Extracted verbatim from `app/settings/page.tsx` (T3-05) — no behaviour change.
 */
import React, { useState, useEffect, useRef } from "react";
import {
  updateProject,
  addProjectOrg,
  removeProjectOrg,
  updateProjectOrgRole,
  addProjectLocation,
  removeProjectLocation,
  listPackages,
  updatePackage,
  addPackageLocation,
  removePackageLocation,
  listWorkflows,
  listTemplates,
  listWorkflowRoutingOptions,
  getProjectActorRoles,
  getProjectMessaging,
  patchProjectMessaging,
  type ProjectItem,
  type OrganizationItem,
  type OrgRole,
  type PackageItem,
  type ProjectMessagingConfig,
  type WorkflowDefinition,
  type WorkflowRoutingOptions,
} from "@/lib/api";
import { useAuth } from "@/app/providers/AuthProvider";
import { orgRoleBadge } from "@/lib/design-tokens";
import {
  normalizeEntityCodeInput,
  validateEntityCode,
  ENTITY_CODE_MAX_LEN,
} from "@/lib/entityCodes";
import { LocationSearch } from "@/components/LocationSearch";
import { ProjectStaffingSection } from "@/components/settings/ProjectStaffingSection";
import { ProjectOfficerModal } from "@/components/settings/ProjectOfficerModal";
import { ProjectGoLivePanel } from "@/components/settings/ProjectGoLivePanel";
import { ProjectActorAddRow } from "@/components/settings/ProjectActorAddRow";
import { ProjectParticipants } from "@/components/settings/projects/ProjectParticipants";
import { ProjectCastSection } from "@/components/settings/projects/ProjectCastSection";
import { ProjectWorkflowsEditor } from "@/components/settings/workflows/ProjectWorkflowsEditor";
import { friendlyError } from "@/components/settings/lib/friendlyError";
import { PackageRow } from "@/components/settings/projects/PackageRow";
import { PackageCreateModal } from "@/components/settings/projects/PackageCreateModal";

export function ProjectEditor({
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

      <div ref={(el) => { sectionRefs.current.cast = el; }}>
        <ProjectCastSection project={p} packages={packages} />
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
