// SPDX-License-Identifier: Apache-2.0

"use client";

/**
 * <ProjectWorkflowsSummary> — what a typed project runs: pick the type, read the workflows.
 *
 * A typed project cannot deviate from its type (DECISION-author-defined-slots §1), so there is
 * nothing to edit here — the old screen showed the full editor with every control disabled,
 * which is a form that lies about being a form. The only choice a project still owns is
 * **which type it is built from**, and even that is refused once it accepts grievances: the one
 * operation that could silently restaff work in flight (§8). Change the workflows themselves
 * under Workflows → Project types.
 *
 * Untyped legacy projects keep the inline editor (<ProjectWorkflowsEditor>).
 */
import { useEffect, useState } from "react";
import {
  listProjectTypes,
  type ProjectItem,
  type ProjectTypeItem,
  type WorkflowDefinition,
  type WorkflowRoutingOptions,
} from "@/lib/api";

export function ProjectWorkflowsSummary({
  project,
  workflows,
  routingOptions,
  canEdit,
  onOpenProjectTypes,
  onChangeType,
}: {
  project: ProjectItem;
  workflows: WorkflowDefinition[];
  routingOptions: WorkflowRoutingOptions | null;
  canEdit: boolean;
  onOpenProjectTypes?: () => void;
  onChangeType: (typeKey: string) => Promise<void>;
}) {
  const [types, setTypes] = useState<ProjectTypeItem[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    listProjectTypes(true).then(setTypes).catch(() => setTypes([]));
  }, []);

  const current = types.find((t) => t.type_key === project.project_type_key) ?? null;
  /** The chatbot menu's own words — never its `story_main` key (ui/05 §2.5: no slugs). */
  const routeLabel = (key: string) =>
    routingOptions?.intake_routes.find((r) => r.key === key)?.label ?? key;
  const slots = (project.workflow_slots ?? []).slice().sort((a, b) => a.sort_order - b.sort_order);
  // A live project keeps its setup: changing the type would re-apply a template over work in
  // flight. Deactivate first — the server refuses it either way (409).
  const canSwitch = canEdit && !project.is_active;

  return (
    <div className="space-y-5 max-w-2xl">
      <div>
        <label
          className="text-[10px] font-bold uppercase tracking-wider text-gray-400 block mb-1"
          htmlFor="project-type-picker"
        >
          Project type
        </label>
        <select
          id="project-type-picker"
          value={project.project_type_key ?? ""}
          disabled={!canSwitch || saving}
          onChange={async (e) => {
            const next = e.target.value;
            if (!next || next === project.project_type_key) return;
            setSaving(true);
            try {
              await onChangeType(next);
            } finally {
              setSaving(false);
            }
          }}
          className="w-full max-w-sm text-sm border border-gray-300 rounded px-2 py-1.5 disabled:bg-gray-50 disabled:text-gray-600"
        >
          {!current && <option value="">— none —</option>}
          {current && !types.some((t) => t.type_key === current.type_key) && (
            <option value={current.type_key}>{current.label}</option>
          )}
          {types.map((t) => (
            <option key={t.type_key} value={t.type_key}>{t.label}</option>
          ))}
        </select>
        <p className="text-xs text-gray-500 mt-1">
          {project.is_active ? (
            <>
              The type sets the workflows below. To change it, deactivate the project first —
              officers are working to this setup.
            </>
          ) : (
            <>The type sets the workflows below, and the organizations this project must name.</>
          )}
        </p>
      </div>

      <div>
        <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-2">
          Workflows this project runs
        </div>
        {slots.length === 0 ? (
          <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
            This type has no workflows yet, so grievances have nowhere to go. Add one to the type.
          </p>
        ) : (
          <ul className="space-y-2">
            {slots.map((s) => {
              const wf = workflows.find((w) => w.workflow_id === s.workflow_id);
              const sensitive = s.workflow_track === "seah";
              return (
                <li
                  key={s.project_workflow_id}
                  className={`rounded-lg border px-3 py-2.5 ${
                    sensitive ? "border-red-200 bg-red-50/40" : "border-gray-200"
                  }`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-gray-900">{s.display_label}</span>
                    <span className="text-xs text-gray-500">
                      {wf?.display_name ?? "workflow not found"}
                    </span>
                    {s.is_default && (
                      <span className="text-xs text-gray-600 border border-gray-200 bg-white rounded-full px-2 py-0.5">
                        Used when nothing else matches
                      </span>
                    )}
                    {sensitive && (
                      <span className="text-xs font-semibold text-red-700">🔒 Sensitive</span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    {s.is_default ? (
                      <>All categories not listed on another workflow come here.</>
                    ) : (
                      <>
                        {s.intake_route ? <>Chatbot menu: {routeLabel(s.intake_route)}. </> : null}
                        {s.classifications?.length
                          ? `Categories: ${s.classifications.join(", ")}.`
                          : "No categories."}
                      </>
                    )}
                  </p>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {onOpenProjectTypes && (
        <button
          type="button"
          onClick={onOpenProjectTypes}
          className="text-sm font-semibold text-blue-600 border border-blue-200 bg-blue-50 rounded px-3 py-1.5 hover:bg-blue-100"
        >
          Open project types
        </button>
      )}
    </div>
  );
}
