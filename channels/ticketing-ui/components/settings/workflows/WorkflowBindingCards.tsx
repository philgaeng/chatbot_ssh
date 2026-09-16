// SPDX-License-Identifier: Apache-2.0

"use client";

/**
 * <WorkflowBindingCards> — the card list that edits a set of workflow links.
 *
 * One card per link: a name the admin chooses + the published workflow it uses + the rules that
 * send grievances there (chatbot menu, categories). The REQUIRED default comes first on its own,
 * then the optional ones. Category routing lives on the card it applies to (doc 13 §5B).
 *
 * Presentational and store-agnostic: it edits `WorkflowBindingDraft[]` and hands them back. Two
 * screens use it, which is the whole point —
 *   • <ProjectWorkflowsEditor> — the project's own links (`project_workflows`)
 *   • <ProjectTypesTab>        — the template's links (`project_types.workflow_bindings`)
 * A project type is mostly a bundle of workflows, so authoring one must look like editing one.
 *
 * Copy: docs/ticketing_system/ui/05_ui_copy_style.md — "stream"/"slot"/"binding" never on screen.
 */
import React, { useMemo } from "react";
import {
  type WorkflowDefinition,
  type WorkflowRoutingOptions,
} from "@/lib/api";
import {
  emptyBinding,
  publishedWorkflowOptions,
  workflowTrackOf,
  type WorkflowBindingDraft,
} from "@/components/settings/workflows/workflowHelpers";
import { NewWorkflowModal } from "@/components/settings/workflows/NewWorkflowModal";

type CardProps = {
  row: WorkflowBindingDraft;
  isDefault: boolean;
  rows: WorkflowBindingDraft[];
  workflows: WorkflowDefinition[];
  routingOptions: WorkflowRoutingOptions | null;
  readOnly: boolean;
  busy: boolean;
  canEditWorkflowTrack: (track: "standard" | "seah") => boolean;
  onPatch: (localId: string, patch: Partial<WorkflowBindingDraft>) => void;
  onRemove: (localId: string) => void;
  onNewWorkflow: (localId: string, track: "standard" | "seah") => void;
};

/** Top-level on purpose: nested inside the parent it remounted on every keystroke, so the
 *  name field lost focus after each letter. */
function BindingCard({
  row,
  isDefault,
  rows,
  workflows,
  routingOptions,
  readOnly,
  busy,
  canEditWorkflowTrack,
  onPatch,
  onRemove,
  onNewWorkflow,
}: CardProps) {
  const classifications = routingOptions?.classifications ?? [];
  const intakeRoutes = routingOptions?.intake_routes ?? [];

  /** Categories already claimed elsewhere — a category belongs to one workflow (doc 13 §5B.2). */
  const claimedElsewhere = useMemo(() => {
    const m = new Map<string, string>();
    for (const r of rows) {
      for (const c of r.classifications) m.set(c, r.localId);
    }
    return m;
  }, [rows]);

  const selected = workflows.find((w) => w.workflow_id === row.workflow_id);
  const track = selected ? workflowTrackOf(selected) : "standard";
  /** Sensitivity is a property of the WORKFLOW, never of the card — the card reflects whatever
   *  it currently points at. Set in the workflow editor only (doc 12 §6.0). */
  const sensitive = !!selected && workflowTrackOf(selected) === "seah";
  const editable = !readOnly && (
    row.workflow_id
      ? canEditWorkflowTrack(track)
      : canEditWorkflowTrack("standard") || canEditWorkflowTrack("seah")
  );
  // A sensitive workflow can't be the default (server: 422) — so don't offer them here.
  const wfOptions = publishedWorkflowOptions(workflows, canEditWorkflowTrack, row.workflow_id)
    .filter((w) => !isDefault || workflowTrackOf(w) !== "seah");
  const unset = !row.workflow_id || !row.display_label.trim();

  function toggleCategory(category: string) {
    const has = row.classifications.includes(category);
    onPatch(row.localId, {
      classifications: has
        ? row.classifications.filter((c) => c !== category)
        : [...row.classifications, category],
    });
  }

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
          disabled={!editable || busy}
          onChange={(e) => onPatch(row.localId, { display_label: e.target.value })}
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
            onClick={() => onRemove(row.localId)}
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
            disabled={!editable || busy}
            onChange={(e) => {
              const v = e.target.value;
              if (v === "__new__") {
                onNewWorkflow(row.localId, track);
                return;
              }
              onPatch(row.localId, { workflow_id: v });
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
                  disabled={!editable || busy}
                  onChange={(e) => onPatch(row.localId, { intake_route: e.target.value || null })}
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
                          onClick={() => toggleCategory(c)}
                        >
                          ×
                        </button>
                      )}
                    </span>
                  ))}
                  {editable && (
                    <select
                      value=""
                      disabled={busy}
                      onChange={(e) => e.target.value && toggleCategory(e.target.value)}
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

export function WorkflowBindingCards({
  rows,
  onChange,
  workflows,
  wfTemplates,
  routingOptions,
  readOnly,
  busy = false,
  canEditWorkflowTrack,
  canSeeSeah,
}: {
  rows: WorkflowBindingDraft[];
  onChange: (rows: WorkflowBindingDraft[]) => void;
  workflows: WorkflowDefinition[];
  wfTemplates: WorkflowDefinition[];
  routingOptions: WorkflowRoutingOptions | null;
  readOnly: boolean;
  busy?: boolean;
  canEditWorkflowTrack: (track: "standard" | "seah") => boolean;
  /** May *configure* sensitive workflows. NOT case access — see DECISION-sensitive-workflows §3. */
  canSeeSeah: boolean;
}) {
  const [wfModal, setWfModal] = React.useState<null | { localId: string; track: "standard" | "seah" }>(null);

  const defaultRow = rows.find((r) => r.is_default) ?? rows[0];
  const otherRows = rows.filter((r) => r !== defaultRow);

  function patchRow(localId: string, patch: Partial<WorkflowBindingDraft>) {
    onChange(rows.map((r) => (r.localId === localId ? { ...r, ...patch } : r)));
  }

  function removeRow(localId: string) {
    const next = rows.filter((r) => r.localId !== localId);
    if (next.length && !next.some((r) => r.is_default)) next[0] = { ...next[0], is_default: true };
    onChange(next.length ? next : [emptyBinding(10, true)]);
  }

  const cardProps = {
    rows,
    workflows,
    routingOptions,
    readOnly,
    busy,
    canEditWorkflowTrack,
    onPatch: patchRow,
    onRemove: removeRow,
    onNewWorkflow: (localId: string, track: "standard" | "seah") => setWfModal({ localId, track }),
  };

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
        {defaultRow && <BindingCard row={defaultRow} isDefault {...cardProps} />}
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
            <BindingCard key={row.localId} row={row} isDefault={false} {...cardProps} />
          ))}
        </div>
      </div>

      {!readOnly && (
        <button
          type="button"
          className="text-sm font-semibold text-blue-600 border border-dashed border-blue-200 bg-blue-50 rounded px-3 py-1.5 hover:bg-blue-100"
          onClick={() => onChange([...rows, emptyBinding((rows.length + 1) * 10)])}
        >
          + Add a workflow
        </button>
      )}

      {wfModal && (
        <NewWorkflowModal
          templates={wfTemplates}
          canSeeSeah={!!canSeeSeah}
          fixedWorkflowType={wfModal.track}
          onCreated={(w) => {
            patchRow(wfModal.localId, { workflow_id: w.workflow_id });
            setWfModal(null);
          }}
          onClose={() => setWfModal(null)}
        />
      )}
    </div>
  );
}
