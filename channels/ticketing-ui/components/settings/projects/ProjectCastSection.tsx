"use client";

/**
 * <ProjectCastSection> — the "Project-wide staffing" pane (DESIGN-cast-model §3.6).
 *
 * "Cast" is the internal word for the set of roles on a level; it never reaches the screen
 * (ui/05 §4) — on screen this is "staffing" and "who works each level".
 *
 * Staff the shared cast ONCE here — the upper ladder (L2/L3/GRC/Legal) + observers that every
 * package inherits. Per-lot overrides live inside each package (see <CastStaffing> embedded in
 * <PackageRow>). A workflow selector handles the Standard vs SEAH track.
 */
import { useMemo, useState } from "react";

import { type OrganizationItem, type PackageItem, type ProjectItem } from "@/lib/api";
import { CastStaffing } from "@/components/settings/projects/CastStaffing";

export function ProjectCastSection({
  project,
  orgs,
  onChanged,
}: {
  project: ProjectItem;
  /** Kept for API compatibility with the mount; per-package staffing lives in PackageRow. */
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

  if (boundWorkflows.length === 0) {
    return (
      <div>
        <h3 className="sr-only">Staffing</h3>
        <p className="mt-2 text-sm text-gray-500">
          Choose a workflow first, under Grievance workflows. Then put officers on its levels
          here — every lot uses these officers unless you set different ones on the lot.
        </p>
      </div>
    );
  }

  return (
    <div>
      <p className="text-sm text-gray-600 max-w-2xl">
        Set these officers once — every lot uses them unless you set a different officer on
        that lot, under Packages.
      </p>

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
      <div className="mt-4">
        <CastStaffing
          project={project}
          orgs={orgs}
          package={null}
          workflowId={selectedWfId}
          onChanged={onChanged}
        />
      </div>
    </div>
  );
}

export default ProjectCastSection;
