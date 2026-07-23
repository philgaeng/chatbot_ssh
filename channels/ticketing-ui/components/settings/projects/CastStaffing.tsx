"use client";

/**
 * <CastStaffing> — staff ONE scope's cast (DESIGN-cast-model §3.6): the workflow's steps ×
 * enabled tiers, assign/remove officers. `package=null` is the project-wide (shared) cast;
 * a package is a per-lot override that shows the project-wide officers greyed as inherited.
 *
 * Self-contained: loads the workflow's steps, the relevant cast rows, and the officer roster.
 * Each assignment writes an `officer_scope` via the sanctioned backend writer, so auto-assign,
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

export function CastStaffing({
  project,
  orgs,
  package: pkg = null,
  workflowId = null,
}: {
  project: ProjectItem;
  orgs: OrganizationItem[];
  /** null = project-wide (shared) cast; a package = per-lot override. */
  package?: PackageItem | null;
  /** Explicit workflow to staff; defaults to the project's standard/default workflow. */
  workflowId?: string | null;
}) {
  const isPkg = !!pkg;
  const scopePkgId = pkg?.package_id ?? null;

  const resolvedWfId = useMemo(() => {
    if (workflowId) return workflowId;
    const slots = project.workflow_slots ?? [];
    const def = slots.find((s) => s.is_default) ?? slots.find((s) => s.workflow_track === "standard");
    return def?.workflow_id ?? project.standard_workflow_id ?? null;
  }, [workflowId, project.workflow_slots, project.standard_workflow_id]);

  const [steps, setSteps] = useState<WorkflowStep[]>([]);
  const [projectWideCast, setProjectWideCast] = useState<CastScope[]>([]);
  const [scopeCast, setScopeCast] = useState<CastScope[]>([]);
  const [roster, setRoster] = useState<OfficerRosterEntry[]>([]);
  const [assigning, setAssigning] = useState<{ stepId: string; tier: string } | null>(null);
  const [pickerQ, setPickerQ] = useState("");
  const [pickerOrg, setPickerOrg] = useState<string>(""); // "" = project actors, id = one org, "__all__" = everyone
  const [pickerLocMatch, setPickerLocMatch] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const orgLabel = useCallback(
    (id: string) => orgs.find((o) => o.organization_id === id)?.name ?? id,
    [orgs],
  );
  const derivedOrg =
    project.implementing_agency_org_id || project.organizations[0]?.organization_id || "";
  const actorOrgIds = useMemo(() => {
    const s = new Set(project.organizations.map((o) => o.organization_id));
    (pkg?.organizations ?? []).forEach((o) => s.add(o.organization_id));
    return s;
  }, [project.organizations, pkg]);
  const pkgLocations = pkg?.location_codes ?? [];

  useEffect(() => {
    let alive = true;
    if (!resolvedWfId) {
      setSteps([]);
      return;
    }
    getWorkflow(resolvedWfId)
      .then((wf) => {
        if (alive) {
          setSteps((wf.steps ?? []).filter((s) => !s.is_deleted).slice().sort((a, b) => a.step_order - b.step_order));
        }
      })
      .catch(() => alive && setSteps([]));
    return () => {
      alive = false;
    };
  }, [resolvedWfId]);

  const loadCast = useCallback(async () => {
    if (!resolvedWfId) {
      setProjectWideCast([]);
      setScopeCast([]);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const pw = await readCast(project.project_id, { workflow_id: resolvedWfId });
      setProjectWideCast(pw);
      setScopeCast(
        isPkg ? await readCast(project.project_id, { workflow_id: resolvedWfId, package_id: scopePkgId! }) : pw,
      );
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setLoading(false);
    }
  }, [project.project_id, resolvedWfId, isPkg, scopePkgId]);

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

  const pickerResults = useMemo(() => {
    const q = pickerQ.trim().toLowerCase();
    return roster
      .filter((o) => o.is_active !== false)
      .filter((o) => {
        if (pickerOrg === "__all__") return true;
        if (pickerOrg === "") return o.organization_ids.some((id) => actorOrgIds.has(id));
        return o.organization_ids.includes(pickerOrg);
      })
      .filter((o) => {
        if (!isPkg || !pickerLocMatch || pkgLocations.length === 0) return true;
        return locationOverlaps(o.location_codes, pkgLocations);
      })
      .filter(
        (o) =>
          !q ||
          `${o.display_name} ${o.email ?? ""} ${(o.positions ?? []).join(" ")}`.toLowerCase().includes(q),
      )
      .slice(0, 40);
  }, [roster, pickerQ, pickerOrg, actorOrgIds, isPkg, pickerLocMatch, pkgLocations]);

  async function assign(officer: OfficerRosterEntry) {
    if (!assigning || !resolvedWfId) return;
    if (!derivedOrg) {
      setError("This project has no linked organization to staff under — set an implementing agency first.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await staffCastSlot(project.project_id, {
        workflow_id: resolvedWfId,
        step_id: assigning.stepId,
        tier: assigning.tier,
        user_id: officer.user_id,
        organization_id: derivedOrg,
        package_id: scopePkgId,
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

  if (!resolvedWfId) {
    return (
      <p className="text-xs text-gray-400">
        Link a published workflow (Grievance workflows) to staff this {isPkg ? "lot" : "project"}.
      </p>
    );
  }
  if (loading && steps.length === 0) return <p className="text-xs text-gray-400">Loading…</p>;
  if (steps.length === 0) return <p className="text-sm text-gray-500">This workflow has no steps yet.</p>;

  return (
    <div className="space-y-3">
      {error && (
        <p className="rounded border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-600">{error}</p>
      )}
      {isPkg && (
        <p className="text-[11px] text-gray-400">
          Inherits Project-wide unless overridden. Greyed rows come from Project-wide; use
          &ldquo;+ assign&rdquo; to add an officer for this lot only.
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
                const current = scopeCast.filter((c) => c.step_id === step.step_id && c.tier === t.key);
                const inherited = isPkg
                  ? projectWideCast.filter((c) => c.step_id === step.step_id && c.tier === t.key)
                  : [];
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
                              {[...actorOrgIds].map((id) => (
                                <option key={id} value={id}>
                                  {orgLabel(id)}
                                </option>
                              ))}
                              <option value="__all__">All officers</option>
                            </select>
                            {isPkg && pkgLocations.length > 0 && (
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
  );
}

export default CastStaffing;
