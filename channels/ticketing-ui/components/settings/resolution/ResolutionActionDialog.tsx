// SPDX-License-Identifier: Apache-2.0

"use client";

/**
 * <ResolutionActionDialog> — create a resolution action into a workflow, or edit one (GRM-119,
 * `ui/08` frame 2b). One dialog for both.
 *
 * **No owner field.** A new action belongs to the workflow's organization — or to its ministry when the
 * admin picks *A new national action*. A local action must say what it counts as in national reports,
 * so DOR's totals stay whole; on a ministry's own workflow the action is national and that field is
 * not shown. The similarity suggestion (`GRM-121`) will sit in this dialog; today it saves directly.
 */
import React, { useState } from "react";
import {
  createWorkflowResolutionAction,
  updateResolutionAction,
  type ResolutionActionRow,
  type WorkflowResolutionPanel,
} from "@/lib/api";
import { friendlyError } from "@/components/settings/lib/friendlyError";

const NATIONAL = "__national__";

export function ResolutionActionDialog({
  workflowId,
  panel,
  editing,
  initialLabel = "",
  onSaved,
  onClose,
}: {
  workflowId: string;
  panel: WorkflowResolutionPanel;
  /** Present when editing; absent when creating. */
  editing?: ResolutionActionRow;
  initialLabel?: string;
  onSaved: () => void;
  onClose: () => void;
}) {
  const [label, setLabel] = useState(editing?.label ?? initialLabel);
  const [wording, setWording] = useState(editing?.default_wording ?? "");
  const [countsAs, setCountsAs] = useState(editing?.counts_as_code ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // Creating: ask "counts as" unless the workflow belongs to a ministry. Editing: only a local action has it.
  const askCountsAs = editing ? !!editing.counts_as_code : !panel.owner_is_ministry;
  const national = countsAs === NATIONAL;
  const valid = label.trim() && wording.trim() && (!askCountsAs || !!countsAs);

  async function save() {
    setSaving(true);
    setError("");
    try {
      if (editing) {
        await updateResolutionAction(editing.code, {
          label: label.trim(),
          default_wording: wording.trim(),
          ...(askCountsAs ? { counts_as_code: countsAs } : {}),
        });
      } else {
        await createWorkflowResolutionAction(workflowId, {
          label: label.trim(),
          default_wording: wording.trim(),
          ...(national ? { national: true } : askCountsAs ? { counts_as_code: countsAs } : {}),
        });
      }
      onSaved();
    } catch (e: unknown) {
      setError(friendlyError(e));
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center bg-black/30">
      <div role="dialog" aria-labelledby="res-action-title"
        className="bg-white w-full md:max-w-md rounded-t-xl md:rounded-xl shadow-xl p-5 space-y-3">
        <h2 id="res-action-title" className="font-semibold text-gray-900">
          {editing ? "Edit resolution action" : "New resolution action"}
        </h2>

        <div>
          <label htmlFor="res-action-label" className="text-xs font-medium text-gray-500 block mb-1">Action</label>
          <input id="res-action-label" value={label} onChange={(e) => setLabel(e.target.value)} maxLength={120}
            placeholder="e.g. Culvert cleared"
            className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
        </div>

        <div>
          <label htmlFor="res-action-wording" className="text-xs font-medium text-gray-500 block mb-1">Default text for the officer</label>
          <textarea id="res-action-wording" value={wording} onChange={(e) => setWording(e.target.value)} rows={3} maxLength={1000}
            placeholder="e.g. The culvert was cleared and water flows again."
            className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
        </div>

        {askCountsAs && (
          <div>
            <label htmlFor="res-action-counts-as" className="text-xs font-medium text-gray-500 block mb-1">
              In national reports, count this as
            </label>
            <select id="res-action-counts-as" value={countsAs} onChange={(e) => setCountsAs(e.target.value)}
              className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 bg-white focus:outline-none focus:ring-1 focus:ring-blue-400">
              <option value="">— Choose —</option>
              {!editing && panel.can_create_national && <option value={NATIONAL}>A new national action</option>}
              {panel.national_choices.map((c) => <option key={c.code} value={c.code}>{c.label}</option>)}
            </select>
            <p className="text-xs text-gray-400 mt-1">
              {national
                ? "It becomes one of the ministry's national actions, available to all its workflows."
                : "Keeps the ministry's totals whole when offices name actions their own way."}
            </p>
          </div>
        )}

        {editing && editing.used_by_count > 1 && (
          <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded px-3 py-2">
            Used by {editing.used_by_count} workflows — the change applies to all of them.
          </p>
        )}
        {error && (
          <p role="alert" className="text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>
        )}

        <div className="flex justify-end gap-3 pt-1">
          <button type="button" onClick={onClose} disabled={saving}
            className="text-sm text-gray-600 hover:text-gray-800 px-4 py-1.5 rounded">Cancel</button>
          <button type="button" onClick={save} disabled={saving || !valid}
            className="text-sm bg-blue-600 text-white hover:bg-blue-700 px-4 py-1.5 rounded font-medium disabled:opacity-50">
            {saving ? "Saving…" : editing ? "Save" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}
