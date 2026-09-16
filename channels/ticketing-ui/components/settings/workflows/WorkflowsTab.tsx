// SPDX-License-Identifier: Apache-2.0

"use client";

/**
 * <WorkflowsTab> — Settings → Workflows, roles & permissions → Workflows.
 *
 * Lists workflows + templates (track-filtered by the admin's own tracks) and hosts the
 * editor / create modal.
 *
 * Extracted verbatim from `app/settings/page.tsx` (T3-05) — no behaviour change.
 */
import React, { useState, useEffect, useCallback, useMemo } from "react";
import { ClipboardList, Lock } from "lucide-react";
import {
  listWorkflows,
  listTemplates,
  getWorkflow,
  archiveWorkflow,
  deleteWorkflow,
  type WorkflowDefinition,
} from "@/lib/api";
import { useAuth } from "@/app/providers/AuthProvider";
import { friendlyError } from "@/components/settings/lib/friendlyError";
import { type RoleEntry } from "@/components/settings/roles/roleEntry";
import {
  statusBadge,
  typeBadge,
  workflowTrackOf,
  type WorkflowRoleOption,
} from "@/components/settings/workflows/workflowHelpers";
import { WorkflowEditor } from "@/components/settings/workflows/WorkflowEditor";
import { NewWorkflowModal } from "@/components/settings/workflows/NewWorkflowModal";

export function WorkflowsTab({
  roleCatalog,
  canCreateRole,
  onRoleCatalogRefresh,
}: {
  roleCatalog: RoleEntry[];
  canCreateRole: boolean;
  onRoleCatalogRefresh: () => void;
}) {
  const { canSeeSeah } = useAuth();
  const [workflows, setWorkflows]     = useState<WorkflowDefinition[]>([]);
  const [templates, setTemplates]     = useState<WorkflowDefinition[]>([]);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState("");
  const [editing, setEditing]         = useState<WorkflowDefinition | null>(null);
  const [showNewModal, setShowNewModal] = useState(false);
  const [newModalMode, setNewModalMode] = useState<"workflow" | "template">("workflow");
  const [clonePreset, setClonePreset] = useState<string | undefined>(undefined);
  const [search, setSearch]           = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [wfRes, tplRes] = await Promise.all([listWorkflows(), listTemplates()]);
      setWorkflows(wfRes.items.filter((w) => !w.is_template));
      setTemplates(tplRes.items.filter(t => t.is_template));
    } catch (e: unknown) {
      setError(friendlyError(e));
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function openEditor(wf: WorkflowDefinition) {
    if (wf.workflow_id.startsWith("__builtin_")) return;
    try {
      const full = await getWorkflow(wf.workflow_id);
      setEditing(full);
    } catch (e: unknown) {
      setError(friendlyError(e));
    }
  }

  async function handleRemoveWorkflow(wf: WorkflowDefinition) {
    if (wf.workflow_id.startsWith("__builtin_")) return;
    if (wf.status === "published") {
      if (!confirm(`Archive "${wf.display_name}"? It will no longer be used for new tickets.`)) return;
      try {
        await archiveWorkflow(wf.workflow_id);
        await load();
      } catch (e: unknown) {
        setError(friendlyError(e));
      }
      return;
    }
    if (!confirm(`Permanently remove "${wf.display_name}"? This cannot be undone.`)) return;
    try {
      await deleteWorkflow(wf.workflow_id);
      setWorkflows((prev) => prev.filter((w) => w.workflow_id !== wf.workflow_id));
      if (editing?.workflow_id === wf.workflow_id) setEditing(null);
    } catch (e: unknown) {
      setError(friendlyError(e));
    }
  }

  // Full operational catalog with each role's track scope. The step cast (StepCast) filters/greys
  // per the workflow's own track, so out-of-track roles surface as "wrong track" rather than vanish.
  const wfRoleOptions: WorkflowRoleOption[] = useMemo(
    () =>
      roleCatalog.map((r) => ({
        key: r.key,
        label: r.label,
        origin: r.role_origin,
        scope: r.workflow,
      })),
    [roleCatalog],
  );

  // Editor view
  if (editing) {
    return (
      <WorkflowEditor
        workflow={editing}
        roleOptions={wfRoleOptions}
        canCreateRole={canCreateRole}
        onRoleCatalogRefresh={onRoleCatalogRefresh}
        onBack={() => { setEditing(null); load(); }}
        onUpdated={updated => setEditing(updated)}
      />
    );
  }

  const visible = workflows.filter(w => {
    if (!canSeeSeah && workflowTrackOf(w) === "seah") return false;
    if (search && !w.display_name.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  // Templates come entirely from the API (built-ins included)
  const allTemplates = templates.filter(t => canSeeSeah || workflowTrackOf(t) !== "seah");

  return (
    <div>
      {showNewModal && (
        <NewWorkflowModal
          mode={newModalMode}
          templates={templates}
          canSeeSeah={!!canSeeSeah}
          initialCloneFrom={clonePreset}
          onCreated={w => {
            setShowNewModal(false);
            setClonePreset(undefined);
            if (w.is_template) {
              setTemplates((prev) => [...prev.filter((t) => t.workflow_id !== w.workflow_id), w]);
            } else {
              setWorkflows((prev) => [...prev, w]);
            }
            setEditing(w);
          }}
          onClose={() => { setShowNewModal(false); setClonePreset(undefined); }}
        />
      )}

      {/* Toolbar */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <input
            value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search workflows…"
            className="text-sm border border-gray-300 rounded px-3 py-1.5 w-56 focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
          {loading && <span className="text-xs text-gray-400 animate-pulse">Loading…</span>}
          {error && <span className="text-xs text-red-500">{error}</span>}
        </div>
        <button
          type="button"
          onClick={() => { setNewModalMode("workflow"); setClonePreset(undefined); setShowNewModal(true); }}
          className="bg-blue-600 text-white text-sm px-4 py-1.5 rounded hover:bg-blue-700 transition font-medium">
          + New workflow
        </button>
      </div>

      {/* Workflow list */}
      {!loading && visible.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          <ClipboardList size={36} strokeWidth={1.25} className="mx-auto mb-3 text-gray-300" />
          <p className="text-sm">No workflows yet. Create one to get started.</p>
        </div>
      )}

      <div className="border border-gray-200 rounded-lg overflow-hidden divide-y divide-gray-100">
        {visible.map(wf => (
          <div key={wf.workflow_id} className="flex items-center gap-4 px-5 py-3.5 hover:bg-gray-50 transition">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-medium text-gray-800 text-sm">{wf.display_name}</span>
                {workflowTrackOf(wf) === "seah" && <Lock size={11} strokeWidth={2.5} className="text-red-500 shrink-0" />}
              </div>
              <div className="text-xs text-gray-400 mt-0.5">
                {wf.steps.filter(s => s && !s.is_deleted).length} steps
                {" · "}{wf.owner_name ? `For ${wf.owner_name}` : "No organization"}
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className={`text-xs px-2 py-0.5 rounded font-medium ${typeBadge(wf.workflow_type)}`}>
                {wf.workflow_type.toUpperCase()}
              </span>
              <span className="text-xs text-gray-400">v{wf.version}</span>
              <span className={`text-xs px-2 py-0.5 rounded font-medium ${statusBadge(wf.status)}`}>
                {wf.status.charAt(0).toUpperCase() + wf.status.slice(1)}
              </span>
              <button type="button" onClick={() => openEditor(wf)}
                className="text-sm text-blue-600 hover:underline ml-2">Edit</button>
              <button type="button" onClick={() => handleRemoveWorkflow(wf)}
                className="text-sm text-red-600 hover:underline ml-2">
                {wf.status === "published" ? "Archive" : "Remove"}
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Templates section */}
      <div className="mt-8">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Templates</h3>
          <button
            type="button"
            onClick={() => { setNewModalMode("template"); setClonePreset(undefined); setShowNewModal(true); }}
            className="text-sm bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700 font-medium"
          >
            + New template
          </button>
        </div>
      {allTemplates.length > 0 ? (
          <div className="border border-gray-200 rounded-lg overflow-hidden divide-y divide-gray-100">
            {allTemplates.map(tpl => (
              <div key={tpl.workflow_id} className="flex items-center gap-4 px-5 py-3.5 hover:bg-gray-50 transition">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-800 text-sm">{tpl.display_name}</span>
                    {workflowTrackOf(tpl) === "seah" && <Lock size={11} strokeWidth={2.5} className="text-red-500 shrink-0" />}
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5">
                    {tpl.steps.filter(s => s && !s.is_deleted).length} steps · {tpl.workflow_id.startsWith("__builtin_") ? "built-in" : tpl.owner_name ? `For ${tpl.owner_name}` : "No organization"}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className={`text-xs px-2 py-0.5 rounded font-medium ${typeBadge(tpl.workflow_type)}`}>
                    {tpl.workflow_type.toUpperCase()}
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded font-medium bg-blue-100 text-blue-700">Template</span>
                  {!tpl.workflow_id.startsWith("__builtin_") && (
                    <button type="button" onClick={() => openEditor(tpl)}
                      className="text-sm text-blue-600 hover:underline ml-2">Edit</button>
                  )}
                  <button
                    type="button"
                    onClick={() => {
                      setNewModalMode("workflow");
                      setClonePreset(tpl.workflow_id);
                      setShowNewModal(true);
                    }}
                    className="text-sm text-blue-600 hover:underline ml-2"
                  >
                    Clone
                  </button>
                  {!tpl.workflow_id.startsWith("__builtin_") && (
                    <button
                      type="button"
                      onClick={() => handleRemoveWorkflow(tpl)}
                      className="text-sm text-red-600 hover:underline ml-2"
                    >
                      Remove
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
      ) : (
        <p className="text-sm text-gray-400 border border-dashed border-gray-200 rounded-lg px-4 py-6 text-center">
          No custom templates yet. Create one or use <strong>Save as template</strong> from a workflow.
        </p>
      )}
      </div>
    </div>
  );
}
