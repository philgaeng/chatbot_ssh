"use client";

/**
 * <ProjectWorkflowsEditor> — a project's grievance workflows.
 *
 * One card per link: a name the admin chooses + the published workflow it uses + the rules that
 * send grievances there (chatbot menu, categories). The REQUIRED default comes first on its own,
 * then the optional ones. Category routing lives on the card it applies to — there is no separate
 * "Classifications" section (doc 13 §5, amended 2026-08-02).
 *
 * Spec: docs/ticketing_system/13_projects_and_packages.md §5B (field by field).
 * Wireframe: docs/ticketing_system/ui/04_projects_packages_redesign.html — "Grievance workflows".
 * Copy: docs/ticketing_system/ui/05_ui_copy_style.md — "stream"/"slot"/"binding" never on screen.
 *
 * No API change: this edits the same `project_workflows` columns the previous row layout did
 * (display_label · workflow_id · intake_route · classifications · is_default · sort_order).
 */
import React, { useState, useEffect, useMemo } from "react";
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
  const [wfModal, setWfModal] = useState<null | { localId: string; track: "standard" | "seah" }>(null);

  useEffect(() => {
    setRows(bindingsFromProject(project.workflow_slots ?? []));
  }, [project.project_id, project.workflow_slots]);

  const classifications = routingOptions?.classifications ?? [];
  const intakeRoutes = routingOptions?.intake_routes ?? [];

  /** Sensitivity is a property of the WORKFLOW, never of the card — the card reflects whatever
   *  it currently points at. Set in the workflow editor only (doc 12 §6.0). */
  const isSensitive = (workflowId: string) => {
    const wf = workflows.find((w) => w.workflow_id === workflowId);
    return !!wf && workflowTrackOf(wf) === "seah";
  };

  const readOnly = !canEdit || lockTypeConfig;
  const defaultRow = rows.find((r) => r.is_default) ?? rows[0];
  const otherRows = rows.filter((r) => r !== defaultRow);

  /** Categories already claimed elsewhere — a category belongs to one workflow (doc 13 §5B.2). */
  const claimedElsewhere = useMemo(() => {
    const m = new Map<string, string>();
    for (const r of rows) {
      for (const c of r.classifications) m.set(c, r.localId);
    }
    return m;
  }, [rows]);

  function updateRow(localId: string, patch: Partial<WorkflowBindingDraft>) {
    setRows((prev) => prev.map((r) => (r.localId === localId ? { ...r, ...patch } : r)));
  }

  function removeRow(localId: string) {
    setRows((prev) => {
      const next = prev.filter((r) => r.localId !== localId);
      if (next.length && !next.some((r) => r.is_default)) next[0].is_default = true;
      return next.length ? next : [emptyBinding(10, true)];
    });
  }

  function toggleCategory(localId: string, category: string) {
    setRows((prev) =>
      prev.map((r) => {
        if (r.localId !== localId) return r;
        const has = r.classifications.includes(category);
        return {
          ...r,
          classifications: has
            ? r.classifications.filter((c) => c !== category)
            : [...r.classifications, category],
        };
      }),
    );
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

  /** One card. `isDefault` changes what routing it shows — the default takes everything that
   *  matches nothing else, so it carries no rules of its own. */
  function Card({ row, isDefault }: { row: WorkflowBindingDraft; isDefault: boolean }) {
    const selected = workflows.find((w) => w.workflow_id === row.workflow_id);
    const track = selected ? workflowTrackOf(selected) : "standard";
    const sensitive = isSensitive(row.workflow_id);
    const editable = !readOnly && (
      row.workflow_id
        ? canEditWorkflowTrack(track)
        : canEditWorkflowTrack("standard") || canEditWorkflowTrack("seah")
    );
    // A sensitive workflow can't be the default (server: 422) — so don't offer them here.
    const wfOptions = publishedWorkflowOptions(workflows, canEditWorkflowTrack, row.workflow_id)
      .filter((w) => !isDefault || workflowTrackOf(w) !== "seah");
    const unset = !row.workflow_id || !row.display_label.trim();

    return (
      <div
        className={`rounded-lg border bg-white overflow-hidden ${
          sensitive ? "border-red-200" : isDefault && unset ? "border-amber-300" : "border-gray-200"
        }`}
      >
        {/* Header — the name IS the card title, plus derived state and Remove */}
        <div
          className={`flex flex-wrap items-center gap-2 px-3 py-2 border-b ${
            sensitive
              ? "bg-red-50 border-red-200"
              : isDefault && unset
                ? "bg-amber-50 border-amber-200"
                : "bg-gray-50 border-gray-200"
          }`}
        >
          <label className="text-xs font-medium text-gray-600 shrink-0" htmlFor={`wf-name-${row.localId}`}>
            Name
          </label>
          <input
            id={`wf-name-${row.localId}`}
            type="text"
            value={row.display_label}
            disabled={!editable || saving}
            onChange={(e) => updateRow(row.localId, { display_label: e.target.value })}
            placeholder={isDefault ? "e.g. General grievances" : "e.g. Road hazards"}
            className="flex-1 min-w-[150px] max-w-xs text-sm font-medium border border-gray-300 rounded px-2 py-1.5 disabled:opacity-50 bg-white"
          />
          {/* Derived from the bound workflow — read-only here (doc 13 §5B.2) */}
          {sensitive && (
            <span
              className="text-xs font-semibold text-red-700 inline-flex items-center gap-1"
              title="Only officers staffed on this workflow can see these grievances"
            >
              🔒 Sensitive
            </span>
          )}
          {isDefault && unset && (
            <span className="text-xs font-semibold text-red-700 border border-red-200 bg-white rounded-full px-2 py-0.5">
              Not chosen
            </span>
          )}
          {editable && !isDefault && (
            <button
              type="button"
              className="ml-auto text-xs font-semibold text-red-600 hover:underline"
              onClick={() => removeRow(row.localId)}
            >
              Remove
            </button>
          )}
        </div>

        <div className="px-3 py-3 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <label className="text-xs font-medium text-gray-600 w-24 shrink-0" htmlFor={`wf-def-${row.localId}`}>
              Workflow
            </label>
            <select
              id={`wf-def-${row.localId}`}
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
              className="flex-1 min-w-[190px] max-w-sm text-sm border border-gray-300 rounded px-2 py-1.5 disabled:opacity-50"
            >
              <option value="">— choose a workflow —</option>
              {wfOptions.map((w) => (
                <option key={w.workflow_id} value={w.workflow_id}>
                  {w.display_name}
                  {workflowTrackOf(w) === "seah" ? " · sensitive" : ""}
                </option>
              ))}
              {editable && <option value="__new__">+ Create a new workflow…</option>}
            </select>
          </div>
          {isDefault && editable && (
            <p className="text-xs text-gray-400 ml-[104px]">
              Sensitive workflows aren&apos;t listed here — the default can&apos;t be sensitive.
            </p>
          )}

          {/* Routing */}
          <div className="pt-3 border-t border-dashed border-gray-200">
            <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-2">
              Grievances come here when
            </div>

            {isDefault ? (
              <p className="text-sm text-gray-600">
                Nothing else matches. <strong>All categories</strong> not listed below come here.
              </p>
            ) : (
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <label className="text-xs font-medium text-gray-600 w-24 shrink-0" htmlFor={`wf-route-${row.localId}`}>
                    Chatbot menu
                  </label>
                  <select
                    id={`wf-route-${row.localId}`}
                    value={row.intake_route ?? ""}
                    disabled={!editable || saving}
                    onChange={(e) => updateRow(row.localId, { intake_route: e.target.value || null })}
                    className="flex-1 min-w-[190px] max-w-sm text-sm border border-gray-300 rounded px-2 py-1.5 disabled:opacity-50"
                  >
                    <option value="">— choose —</option>
                    {intakeRoutes.map((ir) => (
                      <option key={ir.key} value={ir.key}>{ir.label}</option>
                    ))}
                  </select>
                </div>

                <div className="flex flex-wrap items-start gap-2">
                  <span className="text-xs font-medium text-gray-600 w-24 shrink-0 pt-1">Categories</span>
                  <div className="flex-1 flex flex-wrap gap-1.5 min-w-[200px]">
                    {row.classifications.map((c) => (
                      <span
                        key={c}
                        className="inline-flex items-center gap-1.5 text-xs text-gray-700 bg-gray-50 border border-gray-300 rounded-full pl-2.5 pr-1.5 py-1"
                      >
                        {c}
                        {editable && (
                          <button
                            type="button"
                            aria-label={`Remove ${c}`}
                            className="text-gray-400 hover:text-red-600 font-bold leading-none"
                            onClick={() => toggleCategory(row.localId, c)}
                          >
                            ×
                          </button>
                        )}
                      </span>
                    ))}
                    {editable && (
                      <select
                        value=""
                        disabled={saving}
                        onChange={(e) => e.target.value && toggleCategory(row.localId, e.target.value)}
                        className="text-xs text-blue-600 border border-dashed border-blue-200 bg-blue-50 rounded-full px-2 py-1"
                        aria-label="Add a category"
                      >
                        <option value="">+ Add a category</option>
                        {classifications
                          .filter((c) => {
                            const owner = claimedElsewhere.get(c);
                            return !owner || owner === row.localId;
                          })
                          .filter((c) => !row.classifications.includes(c))
                          .map((c) => (
                            <option key={c} value={c}>{c}</option>
                          ))}
                      </select>
                    )}
                    {!row.classifications.length && !editable && (
                      <span className="text-xs text-gray-400">No categories</span>
                    )}
                  </div>
                </div>
              </div>
            )}

            {sensitive && (
              <p className="text-xs text-gray-500 mt-3">
                <strong>Only officers staffed on this workflow</strong>{" "}
                can see these grievances or the complainant&apos;s contact details. Set this on the
                workflow itself, under Workflows, roles &amp; permissions.
              </p>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {workflows.length === 0 && !readOnly && (
        <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
          No workflows loaded. Publish a workflow under Settings → Workflows first, then return here.
        </p>
      )}

      <div>
        <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-2">
          Default workflow{" "}
          <span className="normal-case tracking-normal font-normal text-gray-400">
            — required; used when nothing else matches
          </span>
        </div>
        {defaultRow && <Card row={defaultRow} isDefault />}
      </div>

      <div>
        <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-2">
          Other workflows{" "}
          <span className="normal-case tracking-normal font-normal text-gray-400">— optional</span>
        </div>
        {otherRows.length === 0 && (
          <p className="text-xs text-gray-400 mb-2">
            None yet. Add one only if some grievances need different levels or officers.
          </p>
        )}
        <div className="space-y-3">
          {otherRows.map((row) => (
            <Card key={row.localId} row={row} isDefault={false} />
          ))}
        </div>
      </div>

      {!readOnly && (
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            className="text-sm font-semibold text-blue-600 border border-dashed border-blue-200 bg-blue-50 rounded px-3 py-1.5 hover:bg-blue-100"
            onClick={() => setRows((prev) => [...prev, emptyBinding((prev.length + 1) * 10)])}
          >
            + Add a workflow
          </button>
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
