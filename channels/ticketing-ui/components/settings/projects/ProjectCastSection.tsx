"use client";

/**
 * <ProjectCastSection> — the Project-wide (shared) cast block (DESIGN-cast-model §3.6).
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
}: {
  project: ProjectItem;
  /** Kept for API compatibility with the mount; per-package staffing lives in PackageRow. */
  packages?: PackageItem[];
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

  if (boundWorkflows.length === 0) {
    return (
      <div className="rounded-lg border border-blue-200 bg-blue-50/30 p-5">
        <h3 className="text-base font-semibold text-gray-800">Project-wide cast</h3>
        <p className="mt-2 text-sm text-gray-500">
          Link a published workflow above (Grievance workflows) first — then staff the shared cast
          here and override per lot inside each package.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-blue-200 bg-blue-50/30 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold text-gray-800">Project-wide cast — the shared staffing</h3>
          <p className="mt-1 text-sm text-gray-500">
            Staff the shared ladder (L2 / L3 / GRC / Legal) + observers once — every lot inherits
            it. Override just the field tiers per lot inside each package below.
          </p>
        </div>
        {boundWorkflows.length > 1 && (
          <select
            value={selectedWfId ?? ""}
            onChange={(e) => setSelectedWfId(e.target.value)}
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
      <div className="mt-4">
        <CastStaffing project={project} orgs={orgs} package={null} workflowId={selectedWfId} />
      </div>
    </div>
  );
}

export default ProjectCastSection;
