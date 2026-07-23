"use client";

/**
 * <ProjectCastSection> — the per-package Cast matrix (DESIGN-cast-model §3.6), as an accordion.
 *
 * "Who plays which tier, per package." One expandable block per scope:
 *   • Project-wide — the shared cast (upper ladder + observers), set ONCE; covers every package.
 *   • Each package — its actor orgs, then its staffing for that lot: the same workflow steps ×
 *     enabled tiers, showing the inherited project-wide officers (greyed) plus package-specific
 *     overrides. Reads top-to-bottom as actors → staffing, so which lot you're editing is
 *     unmistakable.
 *
 * Each assignment writes an `officer_scope` through the sanctioned backend writer, so auto-assign,
 * SEAH isolation and the reassignment chain all key off the same rows.
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  getWorkflow,
  listOfficerRoster,
  readCast,
  staffCastSlot,
  unstaffCastSlot,
  type CastScope,
  type OfficerRosterEntry,
  type OrganizationItem,
  type PackageItem,
  type ProjectItem,
  type WorkflowStep,
} from "@/lib/api";
import { friendlyError } from "@/components/settings/lib/friendlyError";

const PROJECT_WIDE = "project-wide";

/** A location code covers another when they share an ancestor path (e.g. P1 covers P1_JHA).
 *  An officer with no location is country-wide and covers everything. */
function locationOverlaps(officerLocs: string[] | undefined, pkgLocs: string[]): boolean {
  if (!officerLocs || officerLocs.length === 0) return true; // country-wide
  if (pkgLocs.length === 0) return true;
  return officerLocs.some((ol) =>
    pkgLocs.some((pl) => ol === pl || ol.startsWith(`${pl}_`) || pl.startsWith(`${ol}_`)),
  );
}

const TIERS: { key: string; label: string; hint: string; accent: string }[] = [
  { key: "actor", label: "Actor", hint: "owns & works the case", accent: "text-blue-700" },
  { key: "supervisor", label: "Supervisor", hint: "oversees; escalation / reassign", accent: "text-blue-700" },
  { key: "participant", label: "Participants", hint: "informed + notes", accent: "text-violet-700" },
  { key: "observer", label: "Observers", hint: "read-only", accent: "text-gray-600" },
];

function stepTiers(step: WorkflowStep): string[] {
  const t = ["actor"];
  if (step.supervisor_role) t.push("supervisor");
  if ((step.informed_roles?.length ?? 0) > 0) t.push("participant");
  if ((step.observer_roles?.length ?? 0) > 0) t.push("observer");
  return t;
}

export function ProjectCastSection({
  project,
  packages,
  orgs,
}: {
  project: ProjectItem;
  packages: PackageItem[];
  orgs: OrganizationItem[];
}) {
  const boundWorkflows = useMemo(() => {
    const slots = (project.workflow_slots ?? []).slice().sort((a, b) => a.sort_order - b.sort_order);
    if (slots.length) {
      return slots.map((s) => ({
        id: s.workflow_id,
        label: s.display_label || (s.workflow_track === "seah" ? "SEAH" : "Standard"),
        track: s.workflow_track,
      }));
    }
    const out: { id: string; label: string; track: string }[] = [];
    if (project.standard_workflow_id) out.push({ id: project.standard_workflow_id, label: "Standard", track: "standard" });
    if (project.seah_workflow_id) out.push({ id: project.seah_workflow_id, label: "SEAH", track: "seah" });
    return out;
  }, [project.workflow_slots, project.standard_workflow_id, project.seah_workflow_id]);

  const [selectedWfId, setSelectedWfId] = useState<string | null>(boundWorkflows[0]?.id ?? null);
  const [expanded, setExpanded] = useState<string>(PROJECT_WIDE);
  const [steps, setSteps] = useState<WorkflowStep[]>([]);
  const [projectWideCast, setProjectWideCast] = useState<CastScope[]>([]);
  const [packageCasts, setPackageCasts] = useState<Record<string, CastScope[]>>({});
  const [roster, setRoster] = useState<OfficerRosterEntry[]>([]);
  const [assigning, setAssigning] = useState<{ scope: string; stepId: string; tier: string } | null>(null);
  const [pickerQ, setPickerQ] = useState("");
  const [pickerOrg, setPickerOrg] = useState<string>(""); // "" = project actors, id = one org, "__all__" = everyone
  const [pickerLocMatch, setPickerLocMatch] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const activePkgs = useMemo(() => packages.filter((p) => p.is_active), [packages]);
  const orgLabel = useCallback(
    (id: string) => orgs.find((o) => o.organization_id === id)?.name ?? id,
    [orgs],
  );
  const derivedOrg =
    project.implementing_agency_org_id || project.organizations[0]?.organization_id || "";

  const scopes = useMemo(
    () => [
      { id: PROJECT_WIDE, label: "Project-wide", sub: "the shared cast — covers every package", pkg: null as PackageItem | null },
      ...activePkgs.map((p) => ({ id: p.package_id, label: `${p.package_code} · ${p.name}`, sub: null, pkg: p })),
    ],
    [activePkgs],
  );

  // Load the selected workflow's steps (fresh — reflects the latest tier toggles).
  useEffect(() => {
    let alive = true;
    if (!selectedWfId) {
      setSteps([]);
      return;
    }
    getWorkflow(selectedWfId)
      .then((wf) => {
        if (alive) {
          setSteps((wf.steps ?? []).filter((s) => !s.is_deleted).slice().sort((a, b) => a.step_order - b.step_order));
        }
      })
      .catch(() => alive && setSteps([]));
    return () => {
      alive = false;
    };
  }, [selectedWfId]);

  const loadAllCast = useCallback(async () => {
    if (!selectedWfId) {
      setProjectWideCast([]);
      setPackageCasts({});
      return;
    }
    setLoading(true);
    setError("");
    try {
      const pw = await readCast(project.project_id, { workflow_id: selectedWfId });
      setProjectWideCast(pw);
      const entries = await Promise.all(
        activePkgs.map(
          async (pkg) =>
            [pkg.package_id, await readCast(project.project_id, { workflow_id: selectedWfId, package_id: pkg.package_id })] as const,
        ),
      );
      setPackageCasts(Object.fromEntries(entries));
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setLoading(false);
    }
  }, [project.project_id, selectedWfId, activePkgs]);

  useEffect(() => {
    void loadAllCast();
  }, [loadAllCast]);

  useEffect(() => {
    listOfficerRoster().then(setRoster).catch(() => setRoster([]));
  }, []);

  const officerName = useCallback(
    (uid: string) => roster.find((o) => o.user_id === uid)?.display_name || uid,
    [roster],
  );

  function castForScope(scopeId: string): CastScope[] {
    return scopeId === PROJECT_WIDE ? projectWideCast : packageCasts[scopeId] ?? [];
  }
  function slotOfficers(scopeId: string, stepId: string, tier: string): CastScope[] {
    return castForScope(scopeId).filter((c) => c.step_id === stepId && c.tier === tier);
  }
  function inheritedOfficers(scopeId: string, stepId: string, tier: string): CastScope[] {
    if (scopeId === PROJECT_WIDE) return [];
    return projectWideCast.filter((c) => c.step_id === stepId && c.tier === tier);
  }
  function packageActorLine(pkg: PackageItem): string {
    const ids = (pkg.organizations ?? []).map((o) => o.organization_id);
    if (ids.length === 0) return "inherits project actors";
    return ids.map(orgLabel).join(", ");
  }
  function scopeCount(scopeId: string): number {
    return castForScope(scopeId).length;
  }

  // Officer-picker context — the org/location filters follow the scope being assigned.
  const assignPkg =
    assigning && assigning.scope !== PROJECT_WIDE
      ? packages.find((p) => p.package_id === assigning.scope) ?? null
      : null;
  const assignActorOrgIds = useMemo(() => {
    const s = new Set(project.organizations.map((o) => o.organization_id));
    (assignPkg?.organizations ?? []).forEach((o) => s.add(o.organization_id));
    return s;
  }, [project.organizations, assignPkg]);
  const assignPkgLocations = assignPkg?.location_codes ?? [];

  const pickerResults = useMemo(() => {
    const q = pickerQ.trim().toLowerCase();
    return roster
      .filter((o) => o.is_active !== false)
      .filter((o) => {
        if (pickerOrg === "__all__") return true;
        if (pickerOrg === "") return o.organization_ids.some((id) => assignActorOrgIds.has(id));
        return o.organization_ids.includes(pickerOrg);
      })
      .filter((o) => {
        if (!assignPkg || !pickerLocMatch || assignPkgLocations.length === 0) return true;
        return locationOverlaps(o.location_codes, assignPkgLocations);
      })
      .filter(
        (o) =>
          !q ||
          `${o.display_name} ${o.email ?? ""} ${(o.positions ?? []).join(" ")}`.toLowerCase().includes(q),
      )
      .slice(0, 40);
  }, [roster, pickerQ, pickerOrg, assignActorOrgIds, assignPkg, pickerLocMatch, assignPkgLocations]);

  async function assign(officer: OfficerRosterEntry) {
    if (!assigning || !selectedWfId) return;
    if (!derivedOrg) {
      setError("This project has no linked organization to staff under — set an implementing agency first.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await staffCastSlot(project.project_id, {
        workflow_id: selectedWfId,
        step_id: assigning.stepId,
        tier: assigning.tier,
        user_id: officer.user_id,
        organization_id: derivedOrg,
        package_id: assigning.scope === PROJECT_WIDE ? null : assigning.scope,
      });
      setAssigning(null);
      setPickerQ("");
      await loadAllCast();
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove(scopeId: string) {
    setBusy(true);
    setError("");
    try {
      await unstaffCastSlot(project.project_id, scopeId);
      await loadAllCast();
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }

  if (boundWorkflows.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-5">
        <h3 className="text-base font-semibold text-gray-800">Cast — staff the workflow</h3>
        <p className="mt-2 text-sm text-gray-500">
          Link a published workflow above (Grievance workflows) first — then staff each step&rsquo;s
          tiers per package here.
        </p>
      </div>
    );
  }

  function renderSteps(scopeId: string) {
    if (loading) return <p className="text-xs text-gray-400">Loading…</p>;
    if (steps.length === 0) return <p className="text-sm text-gray-500">This workflow has no steps yet.</p>;
    const isPkg = scopeId !== PROJECT_WIDE;
    return (
      <div className="space-y-4">
        {isPkg && (
          <p className="text-[11px] text-gray-400">
            Inherits Project-wide unless overridden. Greyed rows come from Project-wide; use
            &ldquo;+ assign&rdquo; to add an officer for this lot.
          </p>
        )}
        {steps.map((step) => {
          const tiers = stepTiers(step);
          return (
            <div key={step.step_id} className="rounded-lg border border-gray-100 bg-white p-3">
              <div className="mb-2 text-sm font-medium text-gray-700">
                <span className="mr-2 inline-flex h-5 w-5 items-center justify-center rounded-full bg-gray-200 text-[11px] text-gray-600">
                  {step.step_order}
                </span>
                {step.display_name}
              </div>
              <div className="space-y-2">
                {TIERS.filter((t) => tiers.includes(t.key)).map((t) => {
                  const current = slotOfficers(scopeId, step.step_id, t.key);
                  const inherited = inheritedOfficers(scopeId, step.step_id, t.key);
                  const slotOpen =
                    assigning?.scope === scopeId && assigning?.stepId === step.step_id && assigning?.tier === t.key;
                  return (
                    <div key={t.key} className="grid grid-cols-[7rem_1fr] items-start gap-2">
                      <div className={`pt-1 text-xs font-medium ${t.accent}`}>
                        {t.label}
                        <div className="text-[10px] font-normal text-gray-400">{t.hint}</div>
                      </div>
                      <div className="flex flex-wrap items-center gap-1.5">
                        {inherited.map((c) => (
                          <span
                            key={`inh-${c.scope_id}`}
                            className="inline-flex items-center gap-1 rounded border border-gray-200 bg-gray-50 px-2 py-0.5 text-xs text-gray-400"
                            title="Inherited from project-wide"
                          >
                            {officerName(c.user_id)}
                            <span className="text-[9px] uppercase">· project-wide</span>
                          </span>
                        ))}
                        {current.map((c) => (
                          <span
                            key={c.scope_id}
                            className="inline-flex items-center gap-1 rounded border border-blue-200 bg-blue-50 px-2 py-0.5 text-xs text-blue-700"
                          >
                            {officerName(c.user_id)}
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => void remove(c.scope_id)}
                              className="leading-none text-blue-300 hover:text-red-500 disabled:opacity-40"
                              aria-label="Remove"
                            >
                              ×
                            </button>
                          </span>
                        ))}
                        {slotOpen ? (
                          <div className="w-full max-w-md rounded border border-blue-200 bg-white p-2 shadow-sm">
                            <input
                              autoFocus
                              value={pickerQ}
                              onChange={(e) => setPickerQ(e.target.value)}
                              placeholder="Search officers by name / email / title…"
                              className="w-full rounded border border-gray-300 px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-blue-400"
                            />
                            <div className="mt-1 flex flex-wrap items-center gap-2">
                              <select
                                value={pickerOrg}
                                onChange={(e) => setPickerOrg(e.target.value)}
                                className="rounded border border-gray-300 px-1.5 py-1 text-[11px] focus:outline-none focus:ring-1 focus:ring-blue-400"
                              >
                                <option value="">Project actors</option>
                                {[...assignActorOrgIds].map((id) => (
                                  <option key={id} value={id}>
                                    {orgLabel(id)}
                                  </option>
                                ))}
                                <option value="__all__">All officers</option>
                              </select>
                              {assignPkg && assignPkgLocations.length > 0 && (
                                <label className="flex items-center gap-1 text-[11px] text-gray-600">
                                  <input
                                    type="checkbox"
                                    checked={pickerLocMatch}
                                    onChange={(e) => setPickerLocMatch(e.target.checked)}
                                  />
                                  in package locations
                                </label>
                              )}
                            </div>
                            <div className="mt-1 max-h-44 overflow-y-auto">
                              {pickerResults.length === 0 && (
                                <p className="px-1 py-1 text-[11px] text-gray-400">
                                  No matching officers — try &ldquo;All officers&rdquo;, or invite one under
                                  Organizations &amp; officers.
                                </p>
                              )}
                              {pickerResults.map((o) => (
                                <button
                                  key={o.user_id}
                                  type="button"
                                  disabled={busy}
                                  onClick={() => void assign(o)}
                                  className="block w-full rounded px-2 py-1 text-left text-xs hover:bg-blue-50 disabled:opacity-40"
                                >
                                  <span className="font-medium text-gray-700">{o.display_name}</span>
                                  {o.email && <span className="text-gray-400"> · {o.email}</span>}
                                  {o.positions && o.positions.length > 0 && (
                                    <span className="text-gray-400"> · {o.positions[0]}</span>
                                  )}
                                </button>
                              ))}
                            </div>
                            <div className="mt-1 text-right">
                              <button
                                type="button"
                                onClick={() => {
                                  setAssigning(null);
                                  setPickerQ("");
                                }}
                                className="rounded px-2 py-0.5 text-[11px] text-gray-500 hover:text-gray-700"
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => {
                              setAssigning({ scope: scopeId, stepId: step.step_id, tier: t.key });
                              setPickerQ("");
                            }}
                            className="rounded border border-dashed border-gray-300 px-2 py-0.5 text-xs text-gray-500 hover:border-blue-300 hover:text-blue-600"
                          >
                            + assign
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold text-gray-800">Cast — staff the workflow</h3>
          <p className="mt-1 text-sm text-gray-500">
            Set the shared cast once under Project-wide; open a lot to override just the officers
            that differ for it.
          </p>
        </div>
        {boundWorkflows.length > 1 && (
          <select
            value={selectedWfId ?? ""}
            onChange={(e) => {
              setSelectedWfId(e.target.value);
              setExpanded(PROJECT_WIDE);
              setAssigning(null);
            }}
            className="rounded border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
          >
            {boundWorkflows.map((w) => (
              <option key={w.id} value={w.id}>
                {w.label}
                {w.track === "seah" ? " (SEAH)" : ""}
              </option>
            ))}
          </select>
        )}
      </div>

      {error && (
        <p className="mt-3 rounded border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-600">{error}</p>
      )}

      <div className="mt-4 space-y-2">
        {scopes.map((scope) => {
          const isOpen = expanded === scope.id;
          const isPkg = scope.id !== PROJECT_WIDE;
          const count = scopeCount(scope.id);
          return (
            <div
              key={scope.id}
              className={`rounded-lg border ${isPkg ? "border-gray-200" : "border-blue-200 bg-blue-50/30"}`}
            >
              <button
                type="button"
                onClick={() => {
                  setExpanded(isOpen ? "" : scope.id);
                  setAssigning(null);
                }}
                className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left"
              >
                <div className="min-w-0">
                  <div className="text-sm font-medium text-gray-800">
                    {scope.label}
                    {count > 0 && (
                      <span className="ml-2 rounded-full bg-blue-100 px-1.5 py-0.5 text-[10px] font-medium text-blue-700">
                        {count} staffed
                      </span>
                    )}
                  </div>
                  <div className="truncate text-xs text-gray-400">
                    {isPkg && scope.pkg ? `Actors: ${packageActorLine(scope.pkg)}` : scope.sub}
                  </div>
                </div>
                <span className="shrink-0 text-gray-400">{isOpen ? "▾" : "▸"}</span>
              </button>
              {isOpen && <div className="border-t border-gray-100 px-4 py-3">{renderSteps(scope.id)}</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default ProjectCastSection;
