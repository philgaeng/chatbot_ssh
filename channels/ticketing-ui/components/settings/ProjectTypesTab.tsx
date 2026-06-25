"use client";

import { useCallback, useEffect, useState } from "react";
import {
  listProjectTypes,
  listWorkflows,
  updateProjectType,
  type ProjectTypeItem,
  type WorkflowDefinition,
} from "@/lib/api";

export function ProjectTypesTab() {
  const [types, setTypes] = useState<ProjectTypeItem[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [editing, setEditing] = useState<ProjectTypeItem | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [t, w] = await Promise.all([
        listProjectTypes(false),
        listWorkflows().then((r) => r.items),
      ]);
      setTypes(t);
      setWorkflows(w.filter((x) => !x.is_template && x.status === "published"));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function flash(t: string) {
    setMsg(t);
    setTimeout(() => setMsg(""), 2500);
  }

  async function saveType(patch: Partial<ProjectTypeItem> & { type_key: string }) {
    try {
      const updated = await updateProjectType(patch.type_key, patch);
      setTypes((prev) => prev.map((x) => (x.type_key === updated.type_key ? updated : x)));
      setEditing(null);
      flash("Saved ✓");
    } catch (e: unknown) {
      flash(e instanceof Error ? e.message : "Save failed");
    }
  }

  if (loading) return <p className="text-sm text-gray-400 animate-pulse">Loading project types…</p>;
  if (error) return <p className="text-sm text-red-500">{error}</p>;

  return (
    <div className="max-w-3xl">
      <p className="text-sm text-gray-500 mb-4">
        Super-admin archetypes. Local admins pick a type when creating a project; workflows and actor role keys are copied automatically.
      </p>
      {msg && <p className="text-xs text-green-600 font-medium mb-3">{msg}</p>}

      <div className="border border-gray-200 rounded-lg overflow-hidden divide-y divide-gray-100">
        {types.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-8">No project types. Run DB migration to seed construction_road.</p>
        ) : (
          types.map((t) => (
            <div key={t.type_key} className="px-5 py-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-800">{t.label}</span>
                    <span className="font-mono text-xs text-gray-400">{t.type_key}</span>
                    {!t.is_active && <span className="text-xs text-gray-400">(inactive)</span>}
                  </div>
                  {t.description && <p className="text-xs text-gray-500 mt-1">{t.description}</p>}
                  <p className="text-xs text-gray-400 mt-2">
                    Routing org role: <span className="font-mono">{t.routing_org_role}</span>
                    {" · "}
                    {t.actor_roles.length} actor role{t.actor_roles.length !== 1 ? "s" : ""}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setEditing(editing?.type_key === t.type_key ? null : t)}
                  className="text-sm text-blue-600 hover:underline shrink-0"
                >
                  {editing?.type_key === t.type_key ? "Close" : "Edit"}
                </button>
              </div>

              {editing?.type_key === t.type_key && (
                <TypeEditorForm
                  type={editing}
                  workflows={workflows}
                  onSave={(patch) => void saveType({ type_key: t.type_key, ...patch })}
                  onCancel={() => setEditing(null)}
                />
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function TypeEditorForm({
  type: initial,
  workflows,
  onSave,
  onCancel,
}: {
  type: ProjectTypeItem;
  workflows: WorkflowDefinition[];
  onSave: (patch: Partial<ProjectTypeItem>) => void;
  onCancel: () => void;
}) {
  const [label, setLabel] = useState(initial.label);
  const [description, setDescription] = useState(initial.description ?? "");
  const [standardWf, setStandardWf] = useState(initial.standard_workflow_id ?? "");
  const [seahWf, setSeahWf] = useState(initial.seah_workflow_id ?? "");
  const [routingRole, setRoutingRole] = useState(initial.routing_org_role);
  const workflowTrack = (w: WorkflowDefinition) =>
    (w.workflow_type || "standard").toLowerCase() === "seah" ? "seah" : "standard";
  const standardOpts = workflows.filter((w) => workflowTrack(w) === "standard");
  const seahOpts = workflows.filter((w) => workflowTrack(w) === "seah");

  return (
    <div className="mt-4 pt-4 border-t border-gray-100 space-y-3">
      <div>
        <label className="text-xs font-medium text-gray-500 block mb-1">Label</label>
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          className="w-full text-sm border border-gray-300 rounded px-3 py-1.5"
        />
      </div>
      <div>
        <label className="text-xs font-medium text-gray-500 block mb-1">Description</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={2}
          className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 resize-none"
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Standard workflow</label>
          <select
            value={standardWf}
            onChange={(e) => setStandardWf(e.target.value)}
            className="w-full text-sm border border-gray-300 rounded px-2 py-1.5"
          >
            <option value="">— none —</option>
            {standardOpts.map((w) => (
              <option key={w.workflow_id} value={w.workflow_id}>
                {w.display_name} (v{w.version})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">SEAH workflow</label>
          <select
            value={seahWf}
            onChange={(e) => setSeahWf(e.target.value)}
            className="w-full text-sm border border-gray-300 rounded px-2 py-1.5"
          >
            <option value="">— none —</option>
            {seahOpts.map((w) => (
              <option key={w.workflow_id} value={w.workflow_id}>
                {w.display_name} (v{w.version})
              </option>
            ))}
          </select>
        </div>
      </div>
      <div>
        <label className="text-xs font-medium text-gray-500 block mb-1">Routing org role key</label>
        <input
          value={routingRole}
          onChange={(e) => setRoutingRole(e.target.value)}
          className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 font-mono"
        />
      </div>
      <p className="text-xs text-gray-400">
        Actor roles are defined in the database seed for this type. Edit via migration or future JSON editor.
      </p>
      <div className="flex gap-2 justify-end">
        <button type="button" onClick={onCancel} className="text-sm text-gray-500 px-3 py-1.5">
          Cancel
        </button>
        <button
          type="button"
          onClick={() =>
            onSave({
              label: label.trim(),
              description: description.trim() || null,
              standard_workflow_id: standardWf || null,
              seah_workflow_id: seahWf || null,
              routing_org_role: routingRole.trim(),
            })
          }
          className="text-sm bg-blue-600 text-white px-4 py-1.5 rounded hover:bg-blue-700"
        >
          Save type
        </button>
      </div>
    </div>
  );
}
