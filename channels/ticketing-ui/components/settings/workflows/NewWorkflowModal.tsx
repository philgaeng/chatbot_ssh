// SPDX-License-Identifier: Apache-2.0

"use client";

/**
 * <NewWorkflowModal> — creates a workflow, optionally seeded from a template.
 *
 * Extracted verbatim from `app/settings/page.tsx` (T3-05) — no behaviour change.
 */
import React, { useEffect, useState } from "react";
import { createWorkflow, listWorkflows, type OrganizationItem, type WorkflowDefinition } from "@/lib/api";
import { useAuth } from "@/app/providers/AuthProvider";
import { OrganizationSelect } from "@/components/settings/workflows/OrganizationSelect";
import { friendlyError } from "@/components/settings/lib/friendlyError";
import { topOrganizations, typeBadge, workflowTrackOf } from "@/components/settings/workflows/workflowHelpers";

export function NewWorkflowModal({
  mode = "workflow",
  templates,
  canSeeSeah,
  initialCloneFrom,
  fixedWorkflowType,
  onCreated,
  onClose,
}: {
  mode?: "workflow" | "template";
  templates: WorkflowDefinition[];
  canSeeSeah: boolean;
  initialCloneFrom?: string;
  /** When set (e.g. from Project editor), lock workflow type to standard or seah. */
  fixedWorkflowType?: "standard" | "seah";
  onCreated: (w: WorkflowDefinition) => void;
  onClose: () => void;
}) {
  const isTemplateMode = mode === "template";
  const { isSuperAdmin } = useAuth();
  const [name, setName]             = useState("");
  // GRM-122: every workflow and template belongs to an organization — it decides which resolution
  // actions it can offer. A platform admin chooses; an org admin's own is filled in.
  const [ownerOrgId, setOwnerOrgId] = useState("");
  // Templates of the chosen organization or one above it — so everything a template copies is
  // usable. null = not loaded for this organization yet.
  const [orgTemplates, setOrgTemplates] = useState<WorkflowDefinition[] | null>(null);
  const [wfType, setWfType]         = useState<string>(fixedWorkflowType ?? "standard");
  const [cloneFrom, setCloneFrom]   = useState(initialCloneFrom ?? "__builtin_default_grm");
  const [creating, setCreating]     = useState(false);
  const [error, setError]           = useState("");

  const builtIns = [
    { id: "__builtin_default_grm",  label: "Default GRM (4 steps)",  type: "standard" },
    ...(canSeeSeah ? [{ id: "__builtin_default_seah", label: "Default SEAH (2 steps)", type: "seah" }] : []),
    { id: "",  label: "Blank (0 steps)",  type: "any" },
  ];

  useEffect(() => {
    if (!ownerOrgId) return;
    let alive = true;
    listWorkflows({ is_template: true, for_organization_id: ownerOrgId })
      .then((res) => alive && setOrgTemplates(res.items))
      .catch(() => alive && setOrgTemplates([]));
    return () => { alive = false; };
  }, [ownerOrgId]);

  function chooseOwner(id: string) {
    setOrgTemplates(null);
    setOwnerOrgId(id);
    // A template of the previous organization may not belong to the new one.
    if (cloneFrom && !cloneFrom.startsWith("__builtin_") && cloneFrom !== initialCloneFrom) {
      setCloneFrom("__builtin_default_grm");
    }
  }

  function defaultOwner(orgs: OrganizationItem[]) {
    if (isSuperAdmin || ownerOrgId) return;
    const tops = topOrganizations(orgs);
    if (tops.length === 1) chooseOwner(tops[0].organization_id);
  }

  // Before an organization is chosen, only the prop's list (the caller's) can be shown; after, the
  // organization's own. `templates` is kept as the fallback so the Clone preset stays selectable.
  const candidateTemplates = ownerOrgId ? (orgTemplates ?? []) : templates;
  const adminTemplates = candidateTemplates.filter(t => canSeeSeah || workflowTrackOf(t) !== "seah");

  async function handleCreate() {
    if (!name.trim()) {
      setError(isTemplateMode ? "Template name is required." : "Workflow name is required.");
      return;
    }
    if (!ownerOrgId) {
      setError(`Choose the organization this ${isTemplateMode ? "template" : "workflow"} belongs to.`);
      return;
    }
    setCreating(true); setError("");
    try {
      const created = await createWorkflow({
        display_name: name.trim(),
        workflow_type: wfType,
        clone_from_id: cloneFrom || undefined,
        is_template: isTemplateMode,
        owner_organization_id: ownerOrgId,
      });
      onCreated(created);
    } catch (e: unknown) {
      setError(friendlyError(e));
      setCreating(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 overflow-hidden">
        <div className="bg-slate-700 text-white px-6 py-4 flex items-center justify-between">
          <div className="font-semibold">{isTemplateMode ? "New template" : "New workflow"}</div>
          <button onClick={onClose} className="text-slate-300 hover:text-white text-xl leading-none">×</button>
        </div>

        <div className="p-6 space-y-4">
          {error && <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>}

          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">{isTemplateMode ? "Template name *" : "Workflow name *"}</label>
            <input autoFocus value={name} onChange={e => setName(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleCreate()}
              placeholder={isTemplateMode ? "e.g. KL Road GRM template" : "e.g. KL Road Standard GRM"}
              className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
          </div>

          <div>
            <label htmlFor="new-wf-owner" className="text-xs font-medium text-gray-500 block mb-1">Belongs to *</label>
            <OrganizationSelect id="new-wf-owner" value={ownerOrgId} onChange={(id) => chooseOwner(id)} onLoaded={defaultOwner} />
          </div>

          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Type</label>
            {fixedWorkflowType ? (
              <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${typeBadge(fixedWorkflowType)}`}>
                {fixedWorkflowType.toUpperCase()}
              </span>
            ) : (
              <div className="flex gap-3">
                {["standard", ...(canSeeSeah ? ["seah"] : [])].map(t => (
                  <label key={t} className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="radio" value={t} checked={wfType === t} onChange={() => { setWfType(t); if (t === "seah") setCloneFrom("__builtin_default_seah"); else setCloneFrom("__builtin_default_grm"); }} />
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${typeBadge(t)}`}>{t.toUpperCase()}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-2">Start from template</label>
            <div className="space-y-1.5">
              {builtIns.filter(b => b.type === "any" || b.type === wfType || b.type === "standard").map(b => (
                <label key={b.id} className={`flex items-center gap-3 border rounded-lg px-3 py-2 cursor-pointer transition ${cloneFrom === b.id ? "border-blue-400 bg-blue-50" : "border-gray-200 hover:border-gray-300"}`}>
                  <input type="radio" value={b.id} checked={cloneFrom === b.id} onChange={() => setCloneFrom(b.id)} className="shrink-0" />
                  <span className="text-sm text-gray-700">{b.label}</span>
                </label>
              ))}
              {adminTemplates.map(t => (
                <label key={t.workflow_id} className={`flex items-center gap-3 border rounded-lg px-3 py-2 cursor-pointer transition ${cloneFrom === t.workflow_id ? "border-blue-400 bg-blue-50" : "border-gray-200 hover:border-gray-300"}`}>
                  <input type="radio" value={t.workflow_id} checked={cloneFrom === t.workflow_id} onChange={() => setCloneFrom(t.workflow_id)} className="shrink-0" />
                  <span className="text-sm text-gray-700">{t.display_name} <span className="text-xs text-gray-400">({t.steps.length} steps)</span></span>
                </label>
              ))}
            </div>
          </div>
        </div>

        <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-3">
          <button onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700 px-4 py-1.5 rounded transition">Cancel</button>
          <button onClick={handleCreate} disabled={creating || !name.trim() || !ownerOrgId}
            className="text-sm bg-blue-600 text-white hover:bg-blue-700 px-4 py-1.5 rounded font-medium disabled:opacity-50 transition">
            {creating ? "Creating…" : "Create workflow"}
          </button>
        </div>
      </div>
    </div>
  );
}
