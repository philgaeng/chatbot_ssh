// SPDX-License-Identifier: Apache-2.0

"use client";

/**
 * <ProjectEditor> — the per-project console (doc 13 §5, wireframe ui/04).
 *
 * Two panes: a sticky rail that fuses go-live status with section navigation, and ONE section
 * at a time on the right. Replaces the single long scroll where every section was stacked and
 * the go-live checklist sat at the top, disconnected from the thing it was talking about.
 *
 * The go-live report is fetched HERE and passed to both the rail and the Overview pane — one
 * fetch, two consumers, so the rail's dots and the checklist can never disagree.
 *
 * Imports <ProjectWorkflowsEditor> from the workflows cluster — the spec's cross-cluster seam #2.
 */
import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  getProjectGoLive,
  type GoLiveReport,
  updateProject,
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
  getProjectType,
  patchProjectMessaging,
  type ProjectItem,
  type OrganizationItem,
  type OrgRole,
  type PackageItem,
  type ProjectMessagingConfig,
  type ProjectTypeItem,
  type WorkflowDefinition,
  type WorkflowRoutingOptions,
} from "@/lib/api";
import { useAuth } from "@/app/providers/AuthProvider";
import {
  normalizeEntityCodeInput,
  validateEntityCode,
  ENTITY_CODE_MAX_LEN,
} from "@/lib/entityCodes";
import { LocationSearch } from "@/components/LocationSearch";
import { ProjectGoLivePanel } from "@/components/settings/ProjectGoLivePanel";
import { ProjectCastSection } from "@/components/settings/projects/ProjectCastSection";
import { ProjectWorkflowsEditor } from "@/components/settings/workflows/ProjectWorkflowsEditor";
import { friendlyError } from "@/components/settings/lib/friendlyError";
import { PackageRow } from "@/components/settings/projects/PackageRow";
import { PackageCreateModal } from "@/components/settings/projects/PackageCreateModal";
import { ProjectConsoleRail } from "@/components/settings/projects/ProjectConsoleRail";
import { ProjectPartnersSection } from "@/components/settings/projects/ProjectPartnersSection";
import { ProjectWorkflowsSummary } from "@/components/settings/projects/ProjectWorkflowsSummary";
import {
  PROJECT_SECTIONS,
  SECTION_ORDER,
  blockerCount,
  type SectionKey,
} from "@/components/settings/projects/projectSections";

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
  onOpenProjectTypes,
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
  /** Jump to Settings → Project types. Absent for admins who cannot author types. */
  onOpenProjectTypes?: () => void;
}) {
  const [p, setP]             = useState<ProjectItem>(initial);
  const [nameVal, setNameVal] = useState(p.name);
  const [shortCodeVal, setShortCodeVal] = useState(p.short_code);
  const [descVal, setDescVal] = useState(p.description ?? "");
  const [msg, setMsg]         = useState("");
  const [working, setWorking] = useState(false);
  const [locError, setLocError] = useState("");
  const { canConfigureSensitive } = useAuth();
  const [projectActorRoles, setProjectActorRolesState] = useState<OrgRole[]>(orgRoles);
  const [rolesSaving, setRolesSaving] = useState(false);
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([]);
  const [wfTemplates, setWfTemplates] = useState<WorkflowDefinition[]>([]);
  const [routingOptions, setRoutingOptions] = useState<WorkflowRoutingOptions | null>(null);
  const [wfSaving, setWfSaving] = useState(false);
  const [goLiveKey, setGoLiveKey] = useState(0);
  const [messaging, setMessaging] = useState<ProjectMessagingConfig | null>(null);
  const [messagingSaving, setMessagingSaving] = useState(false);
  // The type's NAME — the header used to show its key, which is a slug on screen (ui/05 §2.5)
  // and told the reader nothing about what the project runs.
  const [projectType, setProjectType] = useState<ProjectTypeItem | null>(null);

  // ── Console: which section is on screen, and the go-live report that drives the rail ──
  const [activeSection, setActiveSection] = useState<SectionKey>("overview");
  const [report, setReport] = useState<GoLiveReport | null>(null);
  const [reportLoading, setReportLoading] = useState(true);
  const [reportError, setReportError] = useState("");
  const topRef = useRef<HTMLDivElement | null>(null);

  const loadGoLive = useCallback(async () => {
    setReportLoading(true);
    setReportError("");
    try {
      setReport(await getProjectGoLive(p.project_id));
    } catch (e: unknown) {
      setReportError(e instanceof Error ? e.message : "Could not check go-live status");
      setReport(null);
    } finally {
      setReportLoading(false);
    }
  }, [p.project_id]);

  useEffect(() => { void loadGoLive(); }, [loadGoLive, goLiveKey]);

  /** Re-run the go-live checks.
   *
   *  **Every mutation on this screen must call this** (2026-08-09, Philippe: *"when one makes
   *  one change it doesn't refresh the pass/no pass tests"*). The package handlers below
   *  updated their own state and stopped there, so adding a district left B2 red and naming a
   *  package's contractor left B3 red until the page was reloaded — on the two sections where
   *  most of the setup work happens. Named rather than inlined so the omission is visible. */
  const refreshGoLive = useCallback(() => setGoLiveKey((k) => k + 1), []);

  /** A net, not the mechanism: re-check when the reader moves to another section.
   *
   *  The explicit calls above are what keep the rail honest. This costs one request per
   *  navigation and means a *missed* call shows stale state only until the next click, instead
   *  of until a page reload — which is how this went unnoticed long enough to be reported as
   *  "several occasions". If it ever surfaces a change the rail should already have shown, the
   *  bug is a missing `refreshGoLive()`, not this. */
  useEffect(() => { refreshGoLive(); }, [activeSection, refreshGoLive]);

  function goToSection(key: SectionKey) {
    setActiveSection(key);
    topRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const sectionIndex = SECTION_ORDER.indexOf(activeSection);
  const prevSection = sectionIndex > 0 ? SECTION_ORDER[sectionIndex - 1] : null;
  const nextSection =
    sectionIndex >= 0 && sectionIndex < SECTION_ORDER.length - 1 ? SECTION_ORDER[sectionIndex + 1] : null;
  const activeMeta = PROJECT_SECTIONS.find((s) => s.key === activeSection);
  const blockers = blockerCount(report);

  // A typed project runs what its type says — for everyone, super_admin included
  // (DECISION-author-defined-slots §1: "a typed project cannot deviate from its type"). The
  // cards stay; they are a summary now, and the way to change them is the type. Only a legacy
  // untyped project still edits inline. The API refuses the write either way (409).
  const typedProject = Boolean(p.project_type_key);
  const lockTypeConfig = typedProject;
  const canEditProjectWorkflows = isSuperAdmin || isCountryAdmin;
  const canEditMessaging = isSuperAdmin || isCountryAdmin;

  function canEditWorkflowTrack(track: "standard" | "seah") {
    if (isSuperAdmin) return true;
    if (!isCountryAdmin) return false;
    return adminWorkflowTracks.includes(track);
  }

  /** A go-live check's "Fix →" — its `section` is a pane key, so this opens that pane. */
  function jumpToSection(section: string) {
    if ((SECTION_ORDER as string[]).includes(section)) goToSection(section as SectionKey);
  }

  async function toggleActive() {
    try {
      const updated = await updateProject(p.project_id, { is_active: !p.is_active });
      setP(updated);
      onUpdated(updated);
      refreshGoLive();
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
    if (!p.project_type_key) { setProjectType(null); return; }
    getProjectType(p.project_type_key).then(setProjectType).catch(() => setProjectType(null));
  }, [p.project_type_key]);

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
  }

  async function saveShortCode() {
    const codeErr = validateEntityCode(shortCodeVal, "Project code");
    if (codeErr) { flash(codeErr); return; }
    const normalized = normalizeEntityCodeInput(shortCodeVal);
    if (normalized === p.short_code) return;
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
  }

  // Project-level locations were removed 2026-08-08: coverage is declared on packages, and
  // only there. `addProjectLocation` / `removeProjectLocation` still exist in lib/api.ts and
  // the endpoints still answer — nothing in the UI calls them. See the Packages section below.

  // ── Packages ──
  const [packages, setPackages]           = useState<PackageItem[]>([]);
  const [pkgLoading, setPkgLoading]       = useState(true);
  const [showCreatePkg, setShowCreatePkg] = useState(false);
  const [expandedPkg, setExpandedPkg]     = useState<string | null>(null);



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
      refreshGoLive();
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
      refreshGoLive();
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
      refreshGoLive();
    } catch { flash("Failed"); }
  }

  return (
    <div ref={topRef}>
      {/* ── Top bar: what this project is, and whether it can go live ── */}
      <div className="rounded-lg border border-gray-200 bg-white px-4 py-3 mb-4">
        {showBack && (
          <button
            onClick={onBack}
            className="text-gray-400 hover:text-gray-600 text-xs flex items-center gap-1 mb-2"
          >
            {canManageProjectCatalog ? "← Projects" : "← All projects"}
          </button>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-lg font-semibold text-gray-900">{p.name}</h2>
          <span className="font-mono text-sm text-gray-400">{p.short_code}</span>
          {p.project_type_key && (
            onOpenProjectTypes ? (
              <button
                type="button"
                onClick={onOpenProjectTypes}
                title="Open project types"
                className="text-xs bg-slate-100 text-slate-700 hover:bg-slate-200 px-2 py-0.5 rounded"
              >
                Type: {projectType?.label ?? "…"}
              </button>
            ) : (
              <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded">
                Type: {projectType?.label ?? "…"}
              </span>
            )
          )}
          {!p.is_active && (
            <span className="text-xs text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded">
              Not active
            </span>
          )}

          <div className="ml-auto flex items-center gap-3">
            {/* Four states, not two. This read only the blocker count, so a project that was
                already running said "Ready to activate" — an instruction to do the thing it
                had done, next to a Deactivate button (2026-08-10, Philippe).

                A live project CAN still have blockers: activation is gated when you press the
                button, not swept afterwards, so promoting a check (D1 → B2, B3, C4…) can leave
                an activated project short. That says "Active · N to fix" in red — red because
                a gap on a project taking real grievances is worse than one on a draft, never
                green, and never the word "Ready". */}
            {!reportLoading && report && (
              <span
                className={`inline-flex items-center gap-2 text-xs font-semibold px-2.5 py-1 rounded-full border ${
                  blockers
                    ? "text-red-700 bg-red-50 border-red-200"
                    : "text-green-700 bg-green-50 border-green-200"
                }`}
              >
                <span className={`h-2 w-2 rounded-full ${blockers ? "bg-red-500" : "bg-green-500"}`} />
                {p.is_active
                  ? blockers
                    ? `Active · ${blockers} to fix`
                    : "Active"
                  : blockers
                    ? `${blockers} ${blockers === 1 ? "blocker" : "blockers"} · can’t activate yet`
                    : "Ready to activate"}
              </span>
            )}
            {canManageProjectCatalog && (
              <button
                type="button"
                onClick={() => void toggleActive()}
                disabled={!p.is_active && !!blockers}
                title={!p.is_active && blockers ? "Clear the blockers first" : undefined}
                className={
                  p.is_active
                    ? "text-xs text-gray-500 hover:text-gray-700 px-2 py-1.5"
                    : "text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 px-3 py-1.5 rounded"
                }
              >
                {p.is_active ? "Deactivate" : "Activate project"}
              </button>
            )}
          </div>
          {msg && <span className="text-xs text-green-600 font-medium w-full">{msg}</span>}
        </div>
      </div>

      {/* ── Console: rail + one section ── */}
      <div className="flex gap-4 items-start">
        <ProjectConsoleRail
          report={report}
          loading={reportLoading}
          active={activeSection}
          onSelect={goToSection}
        />

        <div className="flex-1 min-w-0">
          <div className="rounded-lg border border-gray-200 bg-white">
            <div className="px-5 py-4 border-b border-gray-100">
              <h3 className="text-base font-semibold text-gray-900">{activeMeta?.label}</h3>
            </div>
            <div className="px-5 py-4">

              {/* ── Overview & go-live ── */}
              {activeSection === "overview" && (
                <ProjectGoLivePanel
                  report={report}
                  loading={reportLoading}
                  error={reportError}
                  onRefresh={refreshGoLive}
                  onJumpSection={jumpToSection}
                />
              )}

              {/* ── Identity ── */}
              {activeSection === "identity" && (
                <div className="space-y-4 max-w-xl">
                  <p className="text-sm text-gray-600">
                    What this project is called, and how it is referenced on grievances and reports.
                  </p>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-xs font-medium text-gray-600 block mb-1">Project name</label>
                      <input
                        value={nameVal}
                        disabled={!canManageProjectCatalog}
                        onChange={(e) => setNameVal(e.target.value)}
                        onBlur={saveMeta}
                        onKeyDown={(e) => e.key === "Enter" && saveMeta()}
                        className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 disabled:opacity-60"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-gray-600 block mb-1">Short code</label>
                      <input
                        value={shortCodeVal}
                        disabled={!canManageProjectCatalog}
                        onChange={(e) => setShortCodeVal(normalizeEntityCodeInput(e.target.value))}
                        onBlur={() => void saveShortCode()}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") void saveShortCode();
                          if (e.key === "Escape") setShortCodeVal(p.short_code);
                        }}
                        maxLength={ENTITY_CODE_MAX_LEN}
                        className="w-full font-mono text-sm border border-gray-300 rounded px-2 py-1.5 disabled:opacity-60"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-600 block mb-1">Description</label>
                    <textarea
                      value={descVal}
                      disabled={!canManageProjectCatalog}
                      onChange={(e) => setDescVal(e.target.value)}
                      onBlur={saveMeta}
                      rows={2}
                      placeholder="What this project covers…"
                      className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 resize-none disabled:opacity-60"
                    />
                  </div>
                  <p className="text-xs text-gray-400">Changes save when you leave the field.</p>
                </div>
              )}

              {/* ── Grievance workflows ── */}
              {activeSection === "workflows" && (
                typedProject ? (
                  <ProjectWorkflowsSummary
                    project={p}
                    workflows={workflows}
                    routingOptions={routingOptions}
                    canEdit={canManageProjectCatalog}
                    onOpenProjectTypes={onOpenProjectTypes}
                    onChangeType={async (typeKey) => {
                      try {
                        const updated = await updateProject(p.project_id, { project_type_key: typeKey });
                        setP(updated);
                        onUpdated(updated);
                        refreshGoLive();
                        flash("Project type changed \u2713 — check Partner organizations");
                      } catch (e: unknown) {
                        flash(friendlyError(e));
                      }
                    }}
                  />
                ) : (
                  <div className="space-y-4">
                    <p className="text-sm text-gray-600 max-w-2xl">
                      One default workflow is required. Add more workflows to send different grievances to
                      different officers. Edit a workflow&rsquo;s levels under Settings &rarr; Workflows.
                    </p>
                    <ProjectWorkflowsEditor
                      project={p}
                      workflows={workflows}
                      wfTemplates={wfTemplates}
                      routingOptions={routingOptions}
                      canEdit={canEditProjectWorkflows}
                      canEditWorkflowTrack={canEditWorkflowTrack}
                      canSeeSeah={!!canConfigureSensitive}
                      lockTypeConfig={false}
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
                        refreshGoLive();
                      }}
                    />
                  </div>
                )
              )}

              {/* ── Officer messaging ── */}
              {activeSection === "messaging" && (
                <div className="space-y-4 max-w-xl">
                  <p className="text-sm text-gray-600">
                    Optional. Officers get a link-only SMS when a grievance is assigned to them — no
                    complainant details are included.
                  </p>
                  {!messaging ? (
                    <p className="text-xs text-gray-400 italic">Loading…</p>
                  ) : (
                    <>
                      <label className="flex items-center gap-2 text-sm text-gray-700">
                        <input
                          type="checkbox"
                          checked={messaging.sms_enabled}
                          disabled={!canEditMessaging || messagingSaving}
                          onChange={(e) => setMessaging({ ...messaging, sms_enabled: e.target.checked })}
                        />
                        Text officers when a grievance is assigned to them
                      </label>
                      {messaging.max_levels > 0 ? (
                        <div className="space-y-2">
                          <p className="text-xs font-medium text-gray-600">Which levels get the SMS</p>
                          <div className="flex flex-wrap gap-2">
                            {Array.from({ length: messaging.max_levels }, (_, i) => i + 1).map((level) => {
                              const on = messaging.sms_levels.includes(level);
                              const disabled = !canEditMessaging || !messaging.sms_enabled || messagingSaving;
                              return (
                                <button
                                  key={level}
                                  type="button"
                                  disabled={disabled}
                                  onClick={() => {
                                    const next = on
                                      ? messaging.sms_levels.filter((l) => l !== level)
                                      : [...messaging.sms_levels, level].sort((a, b) => a - b);
                                    setMessaging({ ...messaging, sms_levels: next });
                                  }}
                                  className={`text-xs rounded-full border px-3 py-1 disabled:opacity-40 ${
                                    on
                                      ? "bg-blue-50 border-blue-200 text-blue-700 font-semibold"
                                      : "bg-white border-gray-300 text-gray-600"
                                  }`}
                                >
                                  Level {level}
                                </button>
                              );
                            })}
                          </div>
                          <p className="text-xs text-gray-400">
                            Officers need a phone number in their profile to receive it.
                          </p>
                        </div>
                      ) : (
                        <p className="text-xs text-amber-700">
                          Choose a workflow first — the levels come from it.
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
                              refreshGoLive();
                              flash("Saved ✓");
                            } catch (e: unknown) {
                              flash(friendlyError(e));
                            } finally {
                              setMessagingSaving(false);
                            }
                          }}
                          className="text-sm px-3 py-1.5 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
                        >
                          {messagingSaving ? "Saving…" : "Save"}
                        </button>
                      )}
                    </>
                  )}
                </div>
              )}

              {/* ── Partner organizations ── */}
              {activeSection === "actors" && (
                <ProjectPartnersSection
                  project={p}
                  packages={packages}
                  orgs={orgs}
                  canEdit={canManageProjectCatalog}
                  onPackagesChanged={(next) => { setPackages(next); refreshGoLive(); }}
                  flash={flash}
                  onUpdated={(updated) => { setP(updated); onUpdated(updated); refreshGoLive(); }}
                />
              )}

              {/* ── Staffing ── */}
              {activeSection === "staffing" && (
                <ProjectCastSection
                  project={p}
                  packages={packages}
                  orgs={orgs}
                  onChanged={refreshGoLive}
                />
              )}

              {/* ── Packages ──
                  Was two sections until 2026-08-08: a project drew its own districts here, and
                  then each package drew its own again. Only the package copy routed anything
                  (location → package → officer), so the project copy drifted and misled. One
                  section now, and a project that was never split up has one package standing in
                  for it — which is why this reads the same for both. */}
              {activeSection === "packages" && (
                <div>
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <p className="text-sm text-gray-600 max-w-2xl">
                      Where this project works. A package is one contract — its own districts, its
                      own officers. A project that is not split into packages has one, covering
                      everywhere it works. Organizations and officers come next.
                    </p>
                    <button
                      onClick={() => setShowCreatePkg(true)}
                      className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700 transition font-medium shrink-0"
                    >
                      + Add a package
                    </button>
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
                    <p className="text-xs text-gray-400 italic">No packages yet.</p>
                  ) : (
                    <div className="space-y-2">
                      {packages.map((pkg) => {
                        const expanded = expandedPkg === pkg.package_id;
                        return (
                          <PackageRow
                            key={pkg.package_id}
                            pkg={pkg}
                            expanded={expanded}
                            onToggle={() => setExpandedPkg(expanded ? null : pkg.package_id)}
                            onUpdate={(payload) => handleUpdatePkg(pkg.package_id, payload)}
                            onAddLoc={(code) => handleAddPkgLoc(pkg.package_id, code)}
                            onRemoveLoc={(code) => handleRemovePkgLoc(pkg.package_id, code)}
                          />
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

            </div>
          </div>

          {/* ── Action bar: walk setup in order ── */}
          <div className="sticky bottom-3 mt-3 rounded-lg border border-gray-200 bg-white px-4 py-2.5 flex flex-wrap items-center gap-3">
            <p className="text-[11px] text-gray-400 flex-1 min-w-[220px]">
              Each section saves on its own — use <span className="font-semibold text-gray-500">Next</span> to
              walk setup in order, or pick any section on the left.
            </p>
            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                disabled={!prevSection}
                onClick={() => prevSection && goToSection(prevSection)}
                className="text-sm px-3 py-1.5 rounded border border-gray-300 text-gray-600 hover:bg-gray-50 disabled:opacity-40"
              >
                ← Back
              </button>
              <button
                type="button"
                disabled={!nextSection}
                onClick={() => nextSection && goToSection(nextSection)}
                className="text-sm px-3 py-1.5 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40"
              >
                Next →
              </button>
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}
