// SPDX-License-Identifier: Apache-2.0

"use client";

/**
 * <ProjectCastSection> — the "Staffing" pane: who works each level of each workflow.
 *
 * "Cast" is the internal word for the set of roles on a level; it never reaches the screen
 * (ui/05 §4) — on screen this is "staffing" and "who works each level".
 *
 * Two rules shape it (Philippe, 2026-08-04):
 *
 *   • **Last level first.** L4 → L1, the reverse of how a grievance travels. The upper ladder is
 *     the stable part you settle once; the lower levels are the ones that vary by package. Working
 *     down means the screen gets more specific as you go, not less.
 *   • **A level says whether it is staffed once or package by package** (`workflow_steps.staff_per_package`).
 *     The workflow author decides, so a project built from a type inherits it and has no switch
 *     of its own. A per-package level asks for an officer on each package **here** — you no longer go
 *     hunting through Packages to find where package 3 differs.
 *
 * One tab per workflow: each has its own levels, and staffing them is a separate job.
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  getWorkflow,
  type OrganizationItem,
  type PackageItem,
  type ProjectItem,
  type WorkflowStep,
} from "@/lib/api";
import { CastStaffing } from "@/components/settings/projects/CastStaffing";

export function ProjectCastSection({
  project,
  packages = [],
  orgs,
  onChanged,
}: {
  project: ProjectItem;
  /** Active packages — a level staffed per package asks for an officer on each of these. */
  packages?: PackageItem[];
  orgs: OrganizationItem[];
  onChanged?: () => void;
}) {
  /** One entry per **slot**, not per workflow.
   *
   *  Two slots may share a workflow, and the seeded `construction_road` type does exactly that:
   *  "Safeguards GRM" and "Road hazard" both point at the standard workflow, the second only to
   *  route Road Hazard classifications down the same ladder. Keying the tabs on `workflow_id`
   *  therefore produced two tabs with the *same* React key, and selecting either one selected
   *  both — indistinguishable on screen (2026-08-08). `project_workflow_id` is the slot's own
   *  id, so tabs stay distinct however many share a workflow. */
  const boundWorkflows = useMemo(() => {
    const slots = (project.workflow_slots ?? []).slice().sort((a, b) => a.sort_order - b.sort_order);
    if (slots.length) {
      return slots.map((s) => ({
        slotId: s.project_workflow_id,
        id: s.workflow_id,
        label: s.display_label || (s.workflow_track === "seah" ? "SEAH" : "Standard"),
        track: s.workflow_track,
      }));
    }
    // Legacy projects with no slot rows: the two mirrored columns. One workflow each, so the
    // workflow id doubles as the slot id.
    const out: { slotId: string; id: string; label: string; track: string }[] = [];
    if (project.standard_workflow_id) out.push({ slotId: project.standard_workflow_id, id: project.standard_workflow_id, label: "Standard", track: "standard" });
    if (project.seah_workflow_id) out.push({ slotId: project.seah_workflow_id, id: project.seah_workflow_id, label: "SEAH", track: "seah" });
    return out;
  }, [project.workflow_slots, project.standard_workflow_id, project.seah_workflow_id]);

  const [selectedSlotId, setSelectedSlotId] = useState<string | null>(boundWorkflows[0]?.slotId ?? null);
  const selectedSlot = boundWorkflows.find((w) => w.slotId === selectedSlotId) ?? boundWorkflows[0] ?? null;
  const selectedWfId = selectedSlot?.id ?? null;
  /** Steps for EVERY bound workflow, not just the open tab.
   *
   *  Loading only the open tab is what made the per-package switch look broken (2026-08-08):
   *  an author ticked "Staffed for each package" on the Road hazard workflow, opened Staffing,
   *  landed on the *first* tab — Safeguards, where every level is project-wide — and read a
   *  banner saying no package is asked about. True of that tab, and the screen had no way to
   *  say "but the next one does", because it had never looked. */
  const [stepsByWf, setStepsByWf] = useState<Record<string, WorkflowStep[]>>({});
  const [loading, setLoading] = useState(false);

  const activePackages = useMemo(() => packages.filter((p) => p.is_active), [packages]);

  // Deduped: two slots sharing a workflow fetch it once.
  const wfIdsKey = Array.from(new Set(boundWorkflows.map((w) => w.id))).join(",");
  const loadSteps = useCallback(async () => {
    const ids = wfIdsKey ? wfIdsKey.split(",") : [];
    if (!ids.length) { setStepsByWf({}); return; }
    setLoading(true);
    try {
      const loaded = await Promise.all(
        ids.map(async (id) => {
          try {
            const wf = await getWorkflow(id);
            return [id, (wf.steps ?? [])
              .filter((s) => !s.is_deleted)
              .slice()
              // Last level first — the settled, project-wide end of the ladder.
              .sort((a, b) => b.step_order - a.step_order)] as const;
          } catch {
            return [id, [] as WorkflowStep[]] as const;
          }
        }),
      );
      setStepsByWf(Object.fromEntries(loaded));
    } finally {
      setLoading(false);
    }
  }, [wfIdsKey]);

  useEffect(() => { void loadSteps(); }, [loadSteps]);

  const steps = useMemo(
    () => (selectedWfId ? stepsByWf[selectedWfId] ?? [] : []),
    [stepsByWf, selectedWfId],
  );

  /** Bound workflows that ask for an officer on each package — used to mark their tab, and to
   *  point at them from a tab that does not. */
  const perPackageWorkflows = useMemo(
    () => boundWorkflows.filter((w) => (stepsByWf[w.id] ?? []).some((s) => s.staff_per_package)),
    [boundWorkflows, stepsByWf],
  );
  const isPerPackage = (slotId: string) => perPackageWorkflows.some((p) => p.slotId === slotId);

  if (boundWorkflows.length === 0) {
    return (
      <div>
        <h3 className="sr-only">Staffing</h3>
        <p className="mt-2 text-sm text-gray-500">
          Choose a workflow first, under Grievance workflows. Then put officers on its levels
          here.
        </p>
      </div>
    );
  }

  return (
    <div>
      <p className="text-sm text-gray-600 max-w-2xl">
        Who works each level, from the last level down to the first. Each level is staffed once
        for the whole project, or package by package — the workflow decides which.
      </p>

      {/* A tab whose levels are all project-wide shows no packages, which is correct and reads
          as broken to someone who has just ticked "Staffed for each package" — on another
          workflow. So this says which workflow it is talking about, and, when a sibling tab
          does ask per package, names it instead of sending the reader to Workflows to look for
          a setting that is already on. */}
      {activePackages.length > 0 && steps.length > 0 && !steps.some((s) => s.staff_per_package) && (
        <p className="mt-2 max-w-2xl rounded border border-gray-200 bg-gray-50 px-3 py-2 text-xs text-gray-600">
          This project has {activePackages.length} {activePackages.length === 1 ? "package" : "packages"}.
          Every level of{" "}
          <strong>{selectedSlot?.label ?? "this workflow"}</strong>{" "}
          is staffed once for the whole project, so no package is asked about on this tab.{" "}
          {perPackageWorkflows.length > 0 ? (
            <>
              {perPackageWorkflows.length === 1 ? "It is " : "These are "}
              {perPackageWorkflows.map((w, i) => (
                <span key={w.id}>
                  {i > 0 && ", "}
                  <button
                    type="button"
                    onClick={() => setSelectedSlotId(w.slotId)}
                    className="font-semibold text-blue-600 hover:underline"
                  >
                    {w.label}
                  </button>
                </span>
              ))}
              {perPackageWorkflows.length === 1
                ? " that asks for an officer on each package."
                : " that ask for an officer on each package."}
            </>
          ) : (
            <>
              To staff a level package by package, tick <strong>Staffed for each package</strong> on
              that level, under Workflows.
            </>
          )}
        </p>
      )}

      {/* One tab per workflow: each has its own levels, and staffing them is a separate job.
          A dropdown hid the fact that a second workflow existed at all. */}
      {boundWorkflows.length > 1 && (
        <div className="mt-3 flex gap-0 border-b border-gray-200" role="tablist">
          {boundWorkflows.map((w) => {
            const on = w.slotId === selectedSlotId;
            return (
              <button
                key={w.slotId}
                type="button"
                role="tab"
                aria-selected={on}
                onClick={() => setSelectedSlotId(w.slotId)}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  on
                    ? "border-blue-500 text-blue-600"
                    : "border-transparent text-gray-500 hover:text-gray-700"
                }`}
              >
                {w.label}
                {w.track === "seah" && (
                  <span className="ml-1.5 text-xs font-semibold text-red-700">Sensitive</span>
                )}
                {/* Says where the per-package work is without opening every tab to find out. */}
                {isPerPackage(w.slotId) && (
                  <span className="ml-1.5 text-xs font-normal text-gray-500">by package</span>
                )}
              </button>
            );
          })}
        </div>
      )}

      <div className="mt-4 space-y-5">
        {loading && <p className="text-sm text-gray-400 animate-pulse">Loading levels…</p>}
        {!loading && steps.length === 0 && (
          <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
            This workflow has no levels yet. Add them under Workflows.
          </p>
        )}
        {steps.map((step) =>
          step.staff_per_package ? (
            <div key={step.step_id}>
              <div className="flex items-center gap-2.5 mb-1.5">
                <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-white border border-gray-300 text-[11px] font-bold text-gray-600">
                  {step.step_order}
                </span>
                <span className="text-[13.5px] font-semibold text-gray-900">{step.display_name}</span>
                <span className="text-xs text-gray-500">— set for each package</span>
              </div>
              {activePackages.length === 0 ? (
                <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
                  This level is staffed for each package, and this project has no packages yet. Add one
                  under Packages.
                </p>
              ) : (
                <div className="space-y-3">
                  {activePackages.map((pkg) => (
                    <div key={pkg.package_id}>
                      <div className="text-[11px] font-medium text-gray-500 mb-1">
                        {pkg.package_code ? `${pkg.package_code} — ` : ""}{pkg.name}
                      </div>
                      <CastStaffing
                        project={project}
                        orgs={orgs}
                        package={pkg}
                        workflowId={selectedWfId}
                        stepIds={[step.step_id]}
                        showStepHeader={false}
                        onChanged={onChanged}
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <CastStaffing
              key={step.step_id}
              project={project}
              orgs={orgs}
              package={null}
              workflowId={selectedWfId}
              stepIds={[step.step_id]}
              onChanged={onChanged}
            />
          ),
        )}
      </div>
    </div>
  );
}

export default ProjectCastSection;
