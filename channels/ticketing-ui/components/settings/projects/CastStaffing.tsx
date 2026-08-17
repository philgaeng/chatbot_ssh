// SPDX-License-Identifier: Apache-2.0

"use client";

/**
 * <CastStaffing> — staff ONE scope's cast (DESIGN-cast-model §3.6): the workflow's steps ×
 * enabled tiers, assign/remove officers. `package=null` is the project-wide (shared) cast;
 * a package is a per-package override that shows the project-wide officers greyed as inherited.
 *
 * Self-contained: loads the workflow's steps, the relevant cast rows, and the officer roster.
 * Each assignment writes an `officer_scope` via the sanctioned backend writer, so auto-assign,
 * SEAH isolation and the reassignment chain all key off the same rows.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

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

/**
 * The four jobs at a level. `hint` is what the job DOES; the row's heading is the **named role**
 * the workflow binds to it (doc 13 §5A.1 — never a generic word), which is why `roleKeyOf` below
 * pulls the role and the fallback label is only used when no role is bound yet.
 *
 * `required` is the actor only: doc 12 §6.2 has the author mark supervisor/participant/observer
 * mandatory per step via `required_tiers`, which is NOT BUILT (no model column, no API field), so
 * this is the one requirement the code can actually know. See the followup.
 */
const TIERS: {
  key: string;
  fallbackLabel: string;
  hint: string;
  accent: string;
  required: boolean;
  roleKeyOf: (s: WorkflowStep) => string | null;
}[] = [
  { key: "actor", fallbackLabel: "Works it", hint: "receives the grievance and resolves it",
    accent: "text-blue-700", required: true, roleKeyOf: (s) => s.assigned_role_key || null },
  { key: "supervisor", fallbackLabel: "Oversees", hint: "alerted on escalation; can reassign",
    accent: "text-blue-700", required: false, roleKeyOf: (s) => s.supervisor_role || null },
  { key: "participant", fallbackLabel: "Kept informed", hint: "sees updates and can add notes",
    accent: "text-violet-700", required: false, roleKeyOf: (s) => s.informed_roles?.[0] ?? null },
  { key: "observer", fallbackLabel: "Can view", hint: "read-only",
    accent: "text-gray-600", required: false, roleKeyOf: (s) => s.observer_roles?.[0] ?? null },
];

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase() ?? "").join("");
}

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
  stepIds = null,
  showStepHeader = true,
  onChanged,
}: {
  project: ProjectItem;
  orgs: OrganizationItem[];
  /** null = project-wide (shared) cast; a package = per-package override. */
  package?: PackageItem | null;
  /** Explicit workflow to staff; defaults to the project's standard/default workflow. */
  workflowId?: string | null;
  /** Render only these levels (in the order given). null = every level of the workflow.
   *  The staffing screen drives this: a level staffed per package is rendered once per package. */
  stepIds?: string[] | null;
  /** False when the parent already names the level (the per-package blocks on the staffing
   *  screen) — otherwise the level's name appears twice, once per package. */
  showStepHeader?: boolean;
  /** Called after an assign/remove — lets the parent refresh coverage indicators. */
  onChanged?: () => void;
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

  /** The levels this instance renders, in the order asked for. Must sit with the other hooks:
   *  below the early returns it changed the hook count between renders (React error #310). */
  const visibleSteps = useMemo(() => {
    if (!stepIds?.length) return steps;
    const order = new Map(stepIds.map((id, i) => [id, i]));
    return steps
      .filter((s) => order.has(s.step_id))
      .sort((a, b) => (order.get(a.step_id) ?? 0) - (order.get(b.step_id) ?? 0));
  }, [steps, stepIds]);

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

  /**
   * Officers staffed through the level's NAMED role rather than a per-level assignment.
   *
   * Two staffing paths coexist (TODO "Phase 3e seed refresh"): this screen writes
   * `officer_scopes` under a synthetic `wf:{workflow}:{step}:{tier}` key, while seeds — and the
   * older invite flow — scope officers under the step's named role (`site_safeguards_focal_person`).
   * Go-live's C1/C5 read the NAMED role, so without this the pane says "Not staffed" for a level
   * go-live has just called staffed. Shown read-only: it is coverage, not an assignment this
   * screen made, so there is nothing here to reassign.
   */
  /** Officers covering a job only because they hold its role — never an assignment made here.
   *  Shared by the row (which shows them) and the level (which explains them once). */
  const roleStaffedRef = useRef<(k: string | null) => OfficerRosterEntry[]>(() => []);

  const byRoleFor = useCallback(
    (step: WorkflowStep, tier: { key: string; roleKeyOf: (s: WorkflowStep) => string | null }) => {
      const cur = scopeCast.filter((c) => c.step_id === step.step_id && c.tier === tier.key);
      const inh = isPkg
        ? projectWideCast.filter((c) => c.step_id === step.step_id && c.tier === tier.key)
        : [];
      if (cur.length || inh.length) return [] as OfficerRosterEntry[];
      return roleStaffedRef.current(tier.roleKeyOf(step));
    },
    [scopeCast, projectWideCast, isPkg],
  );

  const roleStaffed = useCallback(
    (roleKey: string | null) => {
      if (!roleKey) return [] as OfficerRosterEntry[];
      const code = project.short_code;
      return roster.filter(
        (o) =>
          o.is_active !== false &&
          o.role_keys.includes(roleKey) &&
          (!o.project_codes?.length || o.project_codes.includes(code)),
      );
    },
    [roster, project.short_code],
  );

  roleStaffedRef.current = roleStaffed;

  /** The position the officer holds — the wireframe shows it under the name so an admin can
   *  see WHICH SEAT is doing the work, not just who. Positions come from the roster today;
   *  the position-first picker (doc 13 §5A.2) needs an endpoint that does not exist yet. */
  const officerPosition = useCallback(
    (uid: string) => roster.find((o) => o.user_id === uid)?.positions?.[0] ?? null,
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
      setError("Set the implementing agency first, under Partner organizations.");
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
      onChanged?.();
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
      onChanged?.();
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }

  if (!resolvedWfId) {
    return (
      <p className="text-xs text-gray-400">
        Link a published workflow (Grievance workflows) to staff this {isPkg ? "package" : "project"}.
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
      {/* Only true where a package CAN inherit — a level the workflow marks "staffed for each package"
          has no project-wide counterpart to inherit from, and the staffing screen renders those
          without a header. */}
      {isPkg && showStepHeader && (
        <p className="text-[11px] text-gray-400">
          Inherits Project-wide unless overridden. Greyed rows come from Project-wide; use
          &ldquo;+ assign&rdquo; to add an officer for this package only.
        </p>
      )}
      {visibleSteps.map((step) => {
        const tiers = stepTiers(step);
        return (
          <div key={step.step_id} className="rounded-lg border border-gray-200 bg-white overflow-hidden">
            {showStepHeader && (
              <div className="flex items-center gap-2.5 border-b border-gray-100 bg-gray-50 px-3 py-2">
                <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-white border border-gray-300 text-[11px] font-bold text-gray-600">
                  {step.step_order}
                </span>
                <span className="text-[13.5px] font-semibold text-gray-900">{step.display_name}</span>
              </div>
            )}
            <div className="divide-y divide-gray-100">
              {TIERS.filter((t) => tiers.includes(t.key)).map((t) => {
                const current = scopeCast.filter((c) => c.step_id === step.step_id && c.tier === t.key);
                const inherited = isPkg
                  ? projectWideCast.filter((c) => c.step_id === step.step_id && c.tier === t.key)
                  : [];
                const slotOpen = assigning?.stepId === step.step_id && assigning?.tier === t.key;
                // The job's name comes from the WORKFLOW and nowhere else (doc 12 §6.2): the
                // author writes it on the step editor, every screen reads it. The old second
                // choice — the bound role's display name — is gone: it made this screen look
                // like it ignored the workflow, and it is why a deployment could never use the
                // words on its own contract. Names are back-filled (`r4t6v8x0`) and required on
                // save, so `fallbackLabel` should be unreachable.
                const roleKey = t.roleKeyOf(step);
                const authored = step.tier_labels?.[t.key];
                const heading = authored?.label || t.fallbackLabel;
                const hint = authored?.description || t.hint;
                // The actor is always required; the author marks the rest (doc 12 §6.2).
                const required = t.required || (step.required_tiers ?? []).includes(t.key);
                const byRole = byRoleFor(step, t);
                const empty = current.length === 0 && inherited.length === 0 && byRole.length === 0;
                const blocking = empty && required && !isPkg;
                return (
                  <div key={t.key} className="px-3 py-2.5">
                    <div className="flex flex-wrap items-start gap-x-3 gap-y-1">
                      <div className="w-56 shrink-0">
                        <div className="flex items-center gap-1.5">
                          <span className={`text-xs font-semibold ${t.accent}`}>{heading}</span>
                          {required && (
                            <span className="rounded-full border border-gray-300 px-1.5 text-[9px] font-bold uppercase tracking-wide text-gray-500">
                              required
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-gray-400">{hint}</div>
                      </div>

                      <div className="flex-1 min-w-[220px] flex flex-wrap items-center gap-2">
                        {inherited.map((c) => (
                          <span
                            key={`inh-${c.scope_id}`}
                            className="inline-flex items-center gap-2 rounded-full border border-gray-200 bg-gray-50 px-2 py-1"
                            title="Same as project"
                          >
                            <span className="grid h-5 w-5 place-items-center rounded-full bg-white text-[9px] font-bold text-gray-500">
                              {initials(officerName(c.user_id))}
                            </span>
                            <span className="text-xs text-gray-500">{officerName(c.user_id)}</span>
                            <span className="text-[10px] text-gray-400">· same as project</span>
                          </span>
                        ))}
                        {current.map((c) => (
                          <span
                            key={c.scope_id}
                            className="inline-flex items-center gap-2 rounded-full border border-blue-300 bg-blue-50/60 px-2 py-1"
                            title="Assigned to this level"
                          >
                            <span className="grid h-5 w-5 place-items-center rounded-full bg-blue-600 text-[9px] font-bold text-white">
                              {initials(officerName(c.user_id))}
                            </span>
                            <span className="leading-tight">
                              <span className="block text-xs font-medium text-gray-900">
                                {officerName(c.user_id)}
                              </span>
                              {officerPosition(c.user_id) && (
                                <span className="block text-[10px] text-gray-400">
                                  {officerPosition(c.user_id)}
                                </span>
                              )}
                            </span>
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => void remove(c.scope_id)}
                              className="text-[11px] font-semibold text-blue-600 hover:underline disabled:opacity-40"
                            >
                              Reassign
                            </button>
                          </span>
                        ))}

                        {byRole.map((o) => (
                          <span
                            key={`role-${o.user_id}`}
                            className="inline-flex items-center gap-2 rounded-full border border-dashed border-gray-300 bg-gray-50 px-2 py-1"
                          >
                            <span className="grid h-5 w-5 place-items-center rounded-full bg-white text-[9px] font-bold text-gray-500">
                              {initials(o.display_name)}
                            </span>
                            <span className="text-xs font-medium text-gray-700">{o.display_name}</span>
                          </span>
                        ))}

                        {!slotOpen && (
                          <button
                            type="button"
                            onClick={() => {
                              setAssigning({ stepId: step.step_id, tier: t.key });
                              setPickerQ("");
                            }}
                            className={`rounded-full border border-dashed px-2.5 py-1 text-xs ${
                              blocking
                                ? "border-red-300 bg-red-50 text-red-700 font-semibold"
                                : "border-blue-200 bg-blue-50 text-blue-600 font-medium"
                            }`}
                          >
                            {empty ? "Assign an officer" : byRole.length ? "Assign for this level" : "+ Add another"}
                          </button>
                        )}
                      </div>
                    </div>

                    {blocking && (
                      <p className="mt-1.5 text-[11px] text-red-700">
                        {t.key === "actor"
                          ? "Not staffed. Every level needs someone to work it."
                          : "Not staffed. This workflow marks it required."}
                      </p>
                    )}


                    {slotOpen && (
                      <div className="mt-2 rounded-lg border border-blue-200 bg-white p-3">
                        <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-1.5">
                          Pick the officer
                        </div>
                        <input
                          autoFocus
                          value={pickerQ}
                          onChange={(e) => setPickerQ(e.target.value)}
                          placeholder="Search by name, email or position…"
                          className="w-full rounded border border-gray-300 px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-blue-400"
                        />
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          <span className="text-[10px] font-bold uppercase tracking-wide text-gray-400">
                            Search area
                          </span>
                          <select
                            value={pickerOrg}
                            onChange={(e) => setPickerOrg(e.target.value)}
                            className="rounded border border-gray-300 px-1.5 py-1 text-[11px] focus:outline-none focus:ring-1 focus:ring-blue-400"
                          >
                            <option value="">Partner organizations</option>
                            {[...actorOrgIds].map((id) => (
                              <option key={id} value={id}>
                                {orgLabel(id)}
                              </option>
                            ))}
                            <option value="__all__">Everyone</option>
                          </select>
                          {isPkg && pkgLocations.length > 0 && (
                            <label className="flex items-center gap-1 text-[11px] text-gray-600">
                              <input
                                type="checkbox"
                                checked={pickerLocMatch}
                                onChange={(e) => setPickerLocMatch(e.target.checked)}
                              />
                              in this package&rsquo;s locations
                            </label>
                          )}
                        </div>
                        <div className="mt-2 max-h-48 overflow-y-auto">
                          {pickerResults.length === 0 && (
                            <p className="px-1 py-1 text-[11px] text-gray-400">
                              No officers match. Try &ldquo;Everyone&rdquo;, or invite one under
                              Organizations &amp; officers.
                            </p>
                          )}
                          {pickerResults.map((o) => (
                            <button
                              key={o.user_id}
                              type="button"
                              disabled={busy}
                              onClick={() => void assign(o)}
                              className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left hover:bg-blue-50 disabled:opacity-40"
                            >
                              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-gray-100 text-[9px] font-bold text-gray-600">
                                {initials(o.display_name)}
                              </span>
                              <span className="min-w-0 flex-1">
                                <span className="block text-xs font-semibold text-gray-800 truncate">
                                  {o.display_name}
                                </span>
                                <span className="block text-[10px] text-gray-400 truncate">
                                  {o.positions?.[0] ?? o.email ?? ""}
                                </span>
                              </span>
                              <span className="text-[11px] font-semibold text-blue-600">Assign</span>
                            </button>
                          ))}
                        </div>
                        <div className="mt-1 text-right">
                          <button
                            type="button"
                            onClick={() => { setAssigning(null); setPickerQ(""); }}
                            className="rounded px-2 py-0.5 text-[11px] text-gray-500 hover:text-gray-700"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
            {/* The per-level explainer ("Dashed names are not assigned here — those officers
                cover the job because they hold its role…") was deleted 2026-08-08 (Philippe:
                "extremely confusing"). It replaced a per-chip "· by role" in 2139f145 and was
                the second attempt to put the covered-vs-assigned distinction into words; three
                clauses of prose is not an improvement on three grey words. The dashed chip
                already reads as "not set here", and the Assign button next to it is the action.
                If the distinction ever does need a word, it belongs as a short label on the
                dashed group — not a sentence under every level. */}
          </div>
        );
      })}
    </div>
  );
}

export default CastStaffing;
