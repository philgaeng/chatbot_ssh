// SPDX-License-Identifier: Apache-2.0

"use client";

/**
 * <ProjectWorkflowsEditor> — a project's grievance workflows.
 *
 * The cards live in <WorkflowBindingCards> (shared with the project-type editor — a type is
 * mostly a bundle of workflows, so authoring one looks like editing one). What stays here is
 * the project's own: load from `project_workflows`, validate, PUT it back.
 *
 * Spec: docs/ticketing_system/13_projects_and_packages.md §5B (field by field).
 * Wireframe: docs/ticketing_system/ui/04_projects_packages_redesign.html — "Grievance workflows".
 *
 * No API change: this edits the same `project_workflows` columns the previous row layout did
 * (display_label · workflow_id · intake_route · classifications · is_default · sort_order).
 */
import React, { useState, useEffect } from "react";
import {
  replaceProjectWorkflows,
  type ProjectItem,
  type ProjectWorkflowSlot,
  type WorkflowDefinition,
  type WorkflowRoutingOptions,
} from "@/lib/api";
import { friendlyError } from "@/components/settings/lib/friendlyError";
import {
  bindingsFromProject,
  type WorkflowBindingDraft,
} from "@/components/settings/workflows/workflowHelpers";
import { WorkflowBindingCards } from "@/components/settings/workflows/WorkflowBindingCards";

export function ProjectWorkflowsEditor({
  project,
  workflows,
  wfTemplates,
  routingOptions,
  canEdit,
  canEditWorkflowTrack,
  canSeeSeah,
  lockTypeConfig,
  onSaved,
  flash,
}: {
  project: ProjectItem;
  workflows: WorkflowDefinition[];
  wfTemplates: WorkflowDefinition[];
  routingOptions: WorkflowRoutingOptions | null;
  canEdit: boolean;
  canEditWorkflowTrack: (track: "standard" | "seah") => boolean;
  /** May *configure* sensitive workflows. NOT case access — see DECISION-sensitive-workflows §3. */
  canSeeSeah: boolean;
  lockTypeConfig: boolean;
  onSaved: (slots: ProjectWorkflowSlot[]) => void;
  flash: (msg: string) => void;
}) {
  const [rows, setRows] = useState<WorkflowBindingDraft[]>(() =>
    bindingsFromProject(project.workflow_slots ?? []),
  );
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setRows(bindingsFromProject(project.workflow_slots ?? []));
  }, [project.project_id, project.workflow_slots]);

  const readOnly = !canEdit || lockTypeConfig;

  async function saveAll() {
    const payload = rows
      .filter((r) => r.display_label.trim() && r.workflow_id)
      .map((r, i) => ({
        display_label: r.display_label.trim(),
        workflow_id: r.workflow_id,
        classifications: r.classifications,
        intake_route: r.is_default ? null : r.intake_route,
        is_default: r.is_default,
        sort_order: r.sort_order || (i + 1) * 10,
      }));
    if (!payload.length) {
      flash("Give the default workflow a name and pick a workflow first");
      return;
    }
    if (payload.filter((p) => p.is_default).length !== 1) {
      flash("One workflow must be the default");
      return;
    }
    setSaving(true);
    try {
      const saved = await replaceProjectWorkflows(project.project_id, payload);
      onSaved(saved);
      flash("Workflows saved ✓");
    } catch (e: unknown) {
      flash(friendlyError(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-5">
      <WorkflowBindingCards
        rows={rows}
        onChange={setRows}
        workflows={workflows}
        wfTemplates={wfTemplates}
        routingOptions={routingOptions}
        readOnly={readOnly}
        busy={saving}
        canEditWorkflowTrack={canEditWorkflowTrack}
        canSeeSeah={canSeeSeah}
      />

      {!readOnly && (
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            disabled={saving}
            onClick={() => void saveAll()}
            className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save workflows"}
          </button>
          <span className="text-xs text-gray-400">A category can be used by one workflow only.</span>
        </div>
      )}
    </div>
  );
}
