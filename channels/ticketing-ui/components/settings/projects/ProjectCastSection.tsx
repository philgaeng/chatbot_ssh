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
  const [steps, setSteps] = useState<WorkflowStep[]>([]);
  const [loading, setLoading] = useState(false);

  const activePackages = useMemo(() => packages.filter((p) => p.is_active), [packages]);

  const loadSteps = useCallback(async () => {
    if (!selectedWfId) { setSteps([]); return; }
    setLoading(true);
    try {
      const wf = await getWorkflow(selectedWfId);
      setSteps(
        (wf.steps ?? [])
          .filter((s) => !s.is_deleted)
          .slice()
          // Last level first — the settled, project-wide end of the ladder.
          .sort((a, b) => b.step_order - a.step_order),
      );
    } catch {
      setSteps([]);
    } finally {
      setLoading(false);
    }
  }, [selectedWfId]);

  useEffect(() => { void loadSteps(); }, [loadSteps]);

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

      {/* A project with packages whose workflow marks no level per-package shows no packages here at all.
          That is correct, and silently confusing: someone who has just created packages expects to
          staff them. Say where the setting lives instead of leaving a hole. */}
      {activePackages.length > 0 && steps.length > 0 && !steps.some((s) => s.staff_per_package) && (
        <p className="mt-2 max-w-2xl rounded border border-gray-200 bg-gray-50 px-3 py-2 text-xs text-gray-600">
          This project has {activePackages.length} {activePackages.length === 1 ? "package" : "packages"}, and
          every level below is staffed once for the whole project — so no package is asked about
          here. To staff a level package by package, tick <strong>Staffed for each package</strong> on that
          level, under Workflows.
        </p>
      )}

      {/* One tab per workflow: each has its own levels, and staffing them is a separate job.
          A dropdown hid the fact that a second workflow existed at all. */}
      {boundWorkflows.length > 1 && (
        <div className="mt-3 flex gap-0 border-b border-gray-200" role="tablist">
          {boundWorkflows.map((w) => {
            const on = w.id === selectedWfId;
            return (
              <button
                key={w.id}
                type="button"
                role="tab"
                aria-selected={on}
                onClick={() => setSelectedWfId(w.id)}
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
