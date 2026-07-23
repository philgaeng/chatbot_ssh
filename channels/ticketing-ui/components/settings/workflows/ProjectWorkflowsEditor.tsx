"use client";

/**
 * <ProjectWorkflowsEditor> — binds published workflows to a project's slots
 * (standard / seah tracks, default + ordering). Consumed by the Projects cluster's
 * <ProjectEditor> — the spec's cross-cluster seam #2.
 *
 * Extracted verbatim from `app/settings/page.tsx` (T3-05) — no behaviour change.
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
  emptyBinding,
  bindingsFromProject,
  publishedWorkflowOptions,
  workflowTrackOf,
  type WorkflowBindingDraft,
} from "@/components/settings/workflows/workflowHelpers";
import { NewWorkflowModal } from "@/components/settings/workflows/NewWorkflowModal";

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
  canSeeSeah: boolean;
  lockTypeConfig: boolean;
  onSaved: (slots: ProjectWorkflowSlot[]) => void;
  flash: (msg: string) => void;
}) {
  const [rows, setRows] = useState<WorkflowBindingDraft[]>(() =>
    bindingsFromProject(project.workflow_slots ?? []),
  );
  const [saving, setSaving] = useState(false);
  const [wfModal, setWfModal] = useState<null | { localId: string; track: "standard" | "seah" }>(null);

  useEffect(() => {
    setRows(bindingsFromProject(project.workflow_slots ?? []));
  }, [project.project_id, project.workflow_slots]);

  const classifications = routingOptions?.classifications ?? [];
  const intakeRoutes = routingOptions?.intake_routes ?? [];

  function updateRow(localId: string, patch: Partial<WorkflowBindingDraft>) {
    setRows((prev) => prev.map((r) => (r.localId === localId ? { ...r, ...patch } : r)));
  }

  function setDefault(localId: string) {
    setRows((prev) =>
      prev.map((r) => ({
        ...r,
        is_default: r.localId === localId,
        intake_route: r.localId === localId ? null : r.intake_route ?? "new_grievance",
      })),
    );
  }

  function removeRow(localId: string) {
    setRows((prev) => {
      const next = prev.filter((r) => r.localId !== localId);
      if (next.length && !next.some((r) => r.is_default)) next[0].is_default = true;
      return next.length ? next : [emptyBinding(10, true)];
    });
  }

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
      flash("Add at least one workflow with a label and published workflow");
      return;
    }
    if (payload.filter((p) => p.is_default).length !== 1) {
      flash("Exactly one workflow must be marked Default");
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

  const readOnly = !canEdit || lockTypeConfig;

  return (
    <div className="space-y-4">
      {workflows.length === 0 && !readOnly && (
        <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
          No workflows loaded. Publish a workflow under Settings → Workflows first, then return here.
        </p>
      )}
      {rows.map((row) => {
        const selected = workflows.find((w) => w.workflow_id === row.workflow_id);
        const track = selected ? workflowTrackOf(selected) : "standard";
        const editable = !readOnly && (
          row.workflow_id
            ? canEditWorkflowTrack(track)
            : canEditWorkflowTrack("standard") || canEditWorkflowTrack("seah")
        );
        const wfOptions = publishedWorkflowOptions(workflows, canEditWorkflowTrack, row.workflow_id);
        return (
          <div key={row.localId} className="border border-gray-200 rounded-lg p-3 bg-white space-y-3">
            <div className="flex flex-wrap gap-3 items-start">
              <div className="flex-1 min-w-[140px]">
                <label className="text-xs font-medium text-gray-600 block mb-1">Label</label>
                <input
                  type="text"
                  value={row.display_label}
                  disabled={!editable || saving}
                  onChange={(e) => updateRow(row.localId, { display_label: e.target.value })}
                  placeholder="e.g. Road hazard"
                  className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 disabled:opacity-50"
                />
              </div>
              <div className="flex-1 min-w-[200px]">
                <label className="text-xs font-medium text-gray-600 block mb-1">Published workflow</label>
                <select
                  value={row.workflow_id}
                  disabled={!editable || saving}
                  onChange={(e) => {
                    const v = e.target.value;
                    if (v === "__new__") {
                      setWfModal({ localId: row.localId, track });
                      return;
                    }
                    updateRow(row.localId, { workflow_id: v });
                  }}
                  className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 disabled:opacity-50"
                >
                  <option value="">— Select —</option>
                  {wfOptions.map((w) => (
                    <option key={w.workflow_id} value={w.workflow_id}>
                      {w.display_name}
                      {workflowTrackOf(w) === "seah" ? " · SEAH" : ""}
                    </option>
                  ))}
                  {editable && <option value="__new__">+ Create new workflow…</option>}
                </select>
              </div>
              <label className="flex items-center gap-2 text-xs text-gray-600 pt-6">
                <input
                  type="radio"
                  name={`default-wf-${project.project_id}`}
                  checked={row.is_default}
                  disabled={!editable || saving}
                  onChange={() => setDefault(row.localId)}
                />
                Default
              </label>
              {editable && rows.length > 1 && (
                <button
                  type="button"
                  className="text-xs text-red-600 hover:underline pt-6"
                  onClick={() => removeRow(row.localId)}
                >
                  Remove
                </button>
              )}
            </div>
            {!row.is_default && (
              <div>
                <label className="text-xs font-medium text-gray-600 block mb-1">Chatbot intake route</label>
                <select
                  value={row.intake_route ?? ""}
                  disabled={!editable || saving}
                  onChange={(e) => updateRow(row.localId, { intake_route: e.target.value || null })}
                  className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 disabled:opacity-50"
                >
                  <option value="">— Select —</option>
                  {intakeRoutes.map((ir) => (
                    <option key={ir.key} value={ir.key}>{ir.label}</option>
                  ))}
                </select>
                <p className="text-xs text-gray-400 mt-1">
                  Matches chatbot story_main at ticket creation (menu path after language).
                </p>
              </div>
            )}
            <div>
              <label className="text-xs font-medium text-gray-600 block mb-1">
                Classifications (re-route after category edit)
              </label>
              <select
                multiple
                value={row.classifications}
                disabled={!editable || saving}
                onChange={(e) => {
                  const selected = Array.from(e.target.selectedOptions).map((o) => o.value);
                  updateRow(row.localId, { classifications: selected });
                }}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 h-24 disabled:opacity-50"
              >
                {classifications.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
              <p className="text-xs text-gray-400 mt-1">
                Optional. Used when an officer reclassifies a safeguards (new_grievance) ticket.
              </p>
            </div>
          </div>
        );
      })}
      {!readOnly && (
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className="text-sm text-blue-600 hover:underline"
            onClick={() => setRows((prev) => [...prev, emptyBinding((prev.length + 1) * 10)])}
          >
            + Add workflow
          </button>
          <button
            type="button"
            disabled={saving}
            onClick={() => void saveAll()}
            className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save workflows"}
          </button>
        </div>
      )}
      {wfModal && (
        <NewWorkflowModal
          templates={wfTemplates}
          canSeeSeah={!!canSeeSeah}
          fixedWorkflowType={wfModal.track}
          onCreated={(w) => {
            updateRow(wfModal.localId, { workflow_id: w.workflow_id });
            setWfModal(null);
          }}
          onClose={() => setWfModal(null)}
        />
      )}
    </div>
  );
}
