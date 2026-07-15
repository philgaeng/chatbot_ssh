"use client";

/**
 * <ProjectWorkflowSelect> — workflow picker for the Settings → Projects frame.
 *
 * NOTE (T3-05): this component has **zero callers** — it was already dead at the time
 * of extraction (its only repo-wide reference is its own definition, and eslint has
 * flagged it in the baseline warning set). Moved verbatim rather than deleted, per the
 * T3-05 "move, don't fix" rule; deletion is tracked as a follow-up.
 *
 * Extracted verbatim from `app/settings/page.tsx` (T3-05) — no behaviour change.
 */
import React from "react";
import { type WorkflowDefinition } from "@/lib/api";

export function ProjectWorkflowSelect({
  label,
  hint,
  workflowType,
  value,
  workflows,
  disabled,
  onChange,
  onCreateNew,
}: {
  label: string;
  hint: string;
  workflowType: "standard" | "seah";
  value: string | null | undefined;
  workflows: WorkflowDefinition[];
  disabled?: boolean;
  onChange: (workflowId: string | null) => void;
  onCreateNew: () => void;
}) {
  const options = workflows.filter(
    (w) => !w.is_template && w.status !== "archived" && w.workflow_type.toLowerCase() === workflowType,
  );
  const selected = value ? options.find((w) => w.workflow_id === value) : undefined;

  return (
    <div>
      <label className="text-xs font-medium text-gray-600 block mb-1">{label}</label>
      <p className="text-xs text-gray-400 mb-2">{hint}</p>
      <select
        value={value ?? ""}
        disabled={disabled}
        onChange={(e) => {
          const v = e.target.value;
          if (v === "__new__") {
            onCreateNew();
            return;
          }
          onChange(v ? v : null);
        }}
        className="w-full max-w-lg text-sm border border-gray-300 rounded px-2 py-2 focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:opacity-50"
      >
        <option value="">— Not set —</option>
        {options.map((w) => (
          <option key={w.workflow_id} value={w.workflow_id}>
            {w.display_name} ({w.status})
          </option>
        ))}
        <option value="__new__">+ Create new workflow…</option>
      </select>
      {selected && (
        <p className="text-xs text-gray-500 mt-1 font-mono">{selected.workflow_key}</p>
      )}
    </div>
  );
}
