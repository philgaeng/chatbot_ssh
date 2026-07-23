"use client";

/**
 * <ProjectCastSection> — the per-package Cast matrix (DESIGN-cast-model §3.6).
 *
 * "Who plays which tier, per package." For the project's bound workflow(s), each step shows its
 * enabled tiers (Actor always; Supervisor / Participants / Observers when the step uses them);
 * an admin staffs officers into each (step, tier) slot per package (or project-wide). Each
 * assignment writes an `officer_scope` through the sanctioned backend writer (`staffCastSlot`),
 * so auto-assign, SEAH isolation, and the reassignment chain all key off the same rows.
 *
 * Two-level model: the "Project-wide" tab covers every package; a package tab shows the
 * project-wide cast as inherited (greyed) and lets you add package-specific overrides.
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
  const [selectedPkgId, setSelectedPkgId] = useState<string | null>(null); // null = project-wide
  const [steps, setSteps] = useState<WorkflowStep[]>([]);
  const [packageCast, setPackageCast] = useState<CastScope[]>([]);
  const [projectWideCast, setProjectWideCast] = useState<CastScope[]>([]);
  const [roster, setRoster] = useState<OfficerRosterEntry[]>([]);
  const [assigning, setAssigning] = useState<{ stepId: string; tier: string } | null>(null);
  const [pickerQ, setPickerQ] = useState("");
  const [pickerOrg, setPickerOrg] = useState<string>(""); // "" = project actors, id = one org, "__all__" = everyone
  const [pickerLocMatch, setPickerLocMatch] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const activePkgs = useMemo(() => packages.filter((p) => p.is_active), [packages]);
  const selectedPkg = useMemo(
    () => packages.find((p) => p.package_id === selectedPkgId) ?? null,
    [packages, selectedPkgId],
  );
  const orgLabel = useCallback(
    (id: string) => orgs.find((o) => o.organization_id === id)?.name ?? id,
    [orgs],
  );
  // Organizations that are actors on this project (project participants + the package's orgs).
  const actorOrgIds = useMemo(() => {
    const s = new Set(project.organizations.map((o) => o.organization_id));
    (selectedPkg?.organizations ?? []).forEach((o) => s.add(o.organization_id));
    return s;
  }, [project.organizations, selectedPkg]);
  const pkgLocations = selectedPkg?.location_codes ?? [];
  const derivedOrg =
    project.implementing_agency_org_id || project.organizations[0]?.organization_id || "";

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

  const loadCast = useCallback(async () => {
    if (!selectedWfId) {
      setProjectWideCast([]);
      setPackageCast([]);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const [pw, pk] = await Promise.all([
        readCast(project.project_id, { workflow_id: selectedWfId }),
        selectedPkgId
          ? readCast(project.project_id, { workflow_id: selectedWfId, package_id: selectedPkgId })
          : Promise.resolve<CastScope[]>([]),
      ]);
      setProjectWideCast(pw);
      setPackageCast(pk);
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setLoading(false);
    }
  }, [project.project_id, selectedWfId, selectedPkgId]);

  useEffect(() => {
    void loadCast();
  }, [loadCast]);

  useEffect(() => {
    listOfficerRoster().then(setRoster).catch(() => setRoster([]));
  }, []);

  const officerName = useCallback(
    (uid: string) => roster.find((o) => o.user_id === uid)?.display_name || uid,
    [roster],
  );

  // Officers staffed into (step, tier) in the CURRENT scope (package tab → package rows;
  // project-wide tab → project-wide rows).
  function currentSlot(stepId: string, tier: string): CastScope[] {
    const src = selectedPkgId ? packageCast : projectWideCast;
    return src.filter((c) => c.step_id === stepId && c.tier === tier);
  }
  // Project-wide rows shown as inherited context on a package tab.
  function inheritedSlot(stepId: string, tier: string): CastScope[] {
    if (!selectedPkgId) return [];
    return projectWideCast.filter((c) => c.step_id === stepId && c.tier === tier);
  }

  const pickerResults = useMemo(() => {
    const q = pickerQ.trim().toLowerCase();
    return roster
      .filter((o) => o.is_active !== false)
      // Org: default to this project's actor orgs; narrow to one; or show everyone.
      .filter((o) => {
        if (pickerOrg === "__all__") return true;
        if (pickerOrg === "") return o.organization_ids.some((id) => actorOrgIds.has(id));
        return o.organization_ids.includes(pickerOrg);
      })
      // Location: on a package tab, optionally keep only officers whose scope covers the package.
      .filter((o) => {
        if (!selectedPkgId || !pickerLocMatch || pkgLocations.length === 0) return true;
        return locationOverlaps(o.location_codes, pkgLocations);
      })
      .filter(
        (o) =>
          !q ||
          `${o.display_name} ${o.email ?? ""} ${(o.positions ?? []).join(" ")}`.toLowerCase().includes(q),
      )
      .slice(0, 40);
  }, [roster, pickerQ, pickerOrg, actorOrgIds, selectedPkgId, pickerLocMatch, pkgLocations]);

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
        package_id: selectedPkgId,
      });
      setAssigning(null);
      setPickerQ("");
      await loadCast();
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
      await loadCast();
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

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold text-gray-800">Cast — staff the workflow</h3>
          <p className="mt-1 text-sm text-gray-500">
            Assign officers to each step&rsquo;s tiers, per package. Project-wide covers every package;
            override only the packages that differ.
          </p>
        </div>
        {boundWorkflows.length > 1 && (
          <select
            value={selectedWfId ?? ""}
            onChange={(e) => {
              setSelectedWfId(e.target.value);
              setSelectedPkgId(null);
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

      {/* Package tabs — Project-wide + each active package */}
      <div className="mt-4 flex flex-wrap gap-1 border-b border-gray-100 pb-2">
        <button
          type="button"
          onClick={() => {
            setSelectedPkgId(null);
            setAssigning(null);
          }}
          className={`rounded px-3 py-1 text-xs font-medium transition ${
            selectedPkgId === null ? "bg-blue-100 text-blue-700" : "text-gray-600 hover:bg-gray-100"
          }`}
        >
          Project-wide
        </button>
        {activePkgs.map((pkg) => (
          <button
            key={pkg.package_id}
            type="button"
            onClick={() => {
              setSelectedPkgId(pkg.package_id);
              setAssigning(null);
            }}
            className={`rounded px-3 py-1 text-xs font-medium transition ${
              selectedPkgId === pkg.package_id ? "bg-blue-100 text-blue-700" : "text-gray-600 hover:bg-gray-100"
            }`}
          >
            {pkg.package_code} · {pkg.name}
          </button>
        ))}
      </div>

      {selectedPkgId && (
        <p className="mt-2 text-[11px] text-gray-400">
          Showing this package. Greyed rows are inherited from Project-wide; use “+ assign” to add a
          package-specific officer.
        </p>
      )}

      {loading && <p className="mt-3 text-xs text-gray-400">Loading…</p>}
      {!loading && steps.length === 0 && (
        <p className="mt-3 text-sm text-gray-500">This workflow has no steps yet.</p>
      )}

      <div className="mt-3 space-y-4">
        {steps.map((step) => {
          const tiers = stepTiers(step);
          return (
            <div key={step.step_id} className="rounded-lg border border-gray-100 bg-gray-50/50 p-3">
              <div className="mb-2 text-sm font-medium text-gray-700">
                <span className="mr-2 inline-flex h-5 w-5 items-center justify-center rounded-full bg-gray-200 text-[11px] text-gray-600">
                  {step.step_order}
                </span>
                {step.display_name}
              </div>
              <div className="space-y-2">
                {TIERS.filter((t) => tiers.includes(t.key)).map((t) => {
                  const current = currentSlot(step.step_id, t.key);
                  const inherited = inheritedSlot(step.step_id, t.key);
                  const slotOpen = assigning?.stepId === step.step_id && assigning?.tier === t.key;
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
                            className="inline-flex items-center gap-1 rounded border border-gray-200 bg-white px-2 py-0.5 text-xs text-gray-400"
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
                                {[...actorOrgIds].map((id) => (
                                  <option key={id} value={id}>
                                    {orgLabel(id)}
                                  </option>
                                ))}
                                <option value="__all__">All officers</option>
                              </select>
                              {selectedPkgId && pkgLocations.length > 0 && (
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
                                  No matching officers — try “All officers”, or invite one under
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
                              setAssigning({ stepId: step.step_id, tier: t.key });
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
    </div>
  );
}

export default ProjectCastSection;
