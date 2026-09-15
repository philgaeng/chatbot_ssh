// SPDX-License-Identifier: Apache-2.0

"use client";

/**
 * <WorkflowOrganizationDialog> — change which organization a workflow or template belongs to
 * (GRM-122, `ui/08` frames 4b–4c).
 *
 * The organization decides which resolution actions the workflow can offer, so a move is refused
 * while its list holds an action the new organization could not use. The server names each one; the
 * dialog stays open and shows them, one per line, so the admin knows exactly what to remove.
 */
import React, { useState } from "react";
import { changeWorkflowOrganization, type WorkflowDefinition } from "@/lib/api";
import { friendlyError } from "@/components/settings/lib/friendlyError";
import { OrganizationSelect } from "@/components/settings/workflows/OrganizationSelect";

export function WorkflowOrganizationDialog({
  workflow,
  onSaved,
  onClose,
}: {
  workflow: WorkflowDefinition;
  onSaved: (updated: WorkflowDefinition) => void;
  onClose: () => void;
}) {
  const [orgId, setOrgId] = useState(workflow.owner_organization_id ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const projects = workflow.used_by_projects ?? [];
  const unchanged = orgId === (workflow.owner_organization_id ?? "");

  async function save() {
    setSaving(true);
    setError("");
    try {
      onSaved(await changeWorkflowOrganization(workflow.workflow_id, orgId));
    } catch (e: unknown) {
      setError(friendlyError(e));
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center bg-black/30">
      <div role="dialog" aria-labelledby="wf-org-title"
        className="bg-white w-full md:max-w-md rounded-t-xl md:rounded-xl shadow-xl p-5 space-y-4">
        <h2 id="wf-org-title" className="font-semibold text-gray-900">
          Which organization does this {workflow.is_template ? "template" : "workflow"} belong to?
        </h2>
        <div>
          <label htmlFor="wf-org-select" className="text-xs font-medium text-gray-500 block mb-1">Belongs to</label>
          <OrganizationSelect id="wf-org-select" value={orgId} onChange={(id) => { setOrgId(id); setError(""); }} disabled={saving} />
        </div>
        {!workflow.is_template && (
          <p className="text-sm text-gray-500">
            Projects using this workflow: {projects.length ? projects.join(", ") : "none"}
          </p>
        )}
        {error && (
          <p role="alert" className="text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2 whitespace-pre-line">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-3">
          <button type="button" onClick={onClose} disabled={saving}
            className="text-sm text-gray-600 hover:text-gray-800 px-4 py-1.5 rounded">Cancel</button>
          <button type="button" onClick={save} disabled={saving || !orgId || unchanged}
            className="text-sm bg-blue-600 text-white hover:bg-blue-700 px-4 py-1.5 rounded font-medium disabled:opacity-50">
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
