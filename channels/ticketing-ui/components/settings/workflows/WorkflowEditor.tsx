"use client";

/**
 * <WorkflowEditor> — edits one workflow definition: its steps (add / reorder / delete
 * via <StepForm>), publish / archive / save-as-template, and the notifications panel.
 *
 * Extracted verbatim from `app/settings/page.tsx` (T3-05) — no behaviour change.
 */
import React, { useState } from "react";
import { Lock } from "lucide-react";
import {
  addStep,
  deleteStep,
  reorderSteps,
  updateWorkflow,
  publishWorkflow,
  archiveWorkflow,
  saveWorkflowAsTemplate,
  type WorkflowDefinition,
  type WorkflowStep,
} from "@/lib/api";
import { roleLabel, CAST_TIER_LABELS } from "@/lib/labels";
import { friendlyError } from "@/components/settings/lib/friendlyError";
import {
  statusBadge,
  typeBadge,
  workflowTrackOf,
  type WorkflowRoleOption,
} from "@/components/settings/workflows/workflowHelpers";
import { StepForm } from "@/components/settings/workflows/StepForm";
import { WorkflowNotificationsPanel } from "@/components/settings/workflows/WorkflowNotificationsPanel";

export function WorkflowEditor({
  workflow: initial,
  roleOptions,
  canCreateRole,
  onRoleCatalogRefresh,
  onBack,
  onUpdated,
}: {
  workflow: WorkflowDefinition;
  roleOptions: WorkflowRoleOption[];
  canCreateRole?: boolean;
  onRoleCatalogRefresh?: () => void;
  onBack: () => void;
  onUpdated: (w: WorkflowDefinition) => void;
}) {
  const [wf, setWf]               = useState<WorkflowDefinition>(initial);
  const [expandedStep, setExpanded] = useState<string | null>(null);
  const [editingName, setEditingName] = useState(false);
  const [nameVal, setNameVal]       = useState(wf.display_name);
  const [publishing, setPublishing] = useState(false);
  const [archiving, setArchiving]   = useState(false);
  const [savingTemplate, setSavingTemplate] = useState(false);
  const [addingStep, setAddingStep] = useState(false);
  const [msg, setMsg]               = useState("");

  const isTemplate = wf.is_template;
  const steps = wf.steps.filter(s => !s.is_deleted).sort((a, b) => a.step_order - b.step_order);

  function flash(text: string) { setMsg(text); setTimeout(() => setMsg(""), 2500); }

  async function handlePublish() {
    const missing = steps.filter((s) => !s.assigned_role_key);
    if (missing.length) {
      flash(`Assign a role to every step before publishing (${missing.length} missing)`);
      return;
    }
    setPublishing(true);
    try { const updated = await publishWorkflow(wf.workflow_id); setWf(updated); onUpdated(updated); flash("Published ✓"); }
    catch (e: unknown) { flash(friendlyError(e)); }
    finally { setPublishing(false); }
  }

  async function handleArchive() {
    if (!confirm("Archive this workflow? It won't be used for new tickets.")) return;
    setArchiving(true);
    try { const updated = await archiveWorkflow(wf.workflow_id); setWf(updated); onUpdated(updated); flash("Archived"); }
    catch (e: unknown) { flash(friendlyError(e)); }
    finally { setArchiving(false); }
  }

  async function handleRename() {
    if (!nameVal.trim() || nameVal === wf.display_name) { setEditingName(false); return; }
    try {
      const updated = await updateWorkflow(wf.workflow_id, { display_name: nameVal.trim() });
      setWf(updated); onUpdated(updated); flash("Renamed ✓");
    } catch { /* ignore */ }
    setEditingName(false);
  }

  async function handleMoveUp(idx: number) {
    if (idx === 0) return;
    const newOrder = [...steps];
    [newOrder[idx - 1], newOrder[idx]] = [newOrder[idx], newOrder[idx - 1]];
    const ids = newOrder.map(s => s.step_id);
    const updated = await reorderSteps(wf.workflow_id, ids);
    setWf(prev => ({ ...prev, steps: updated }));
  }

  async function handleMoveDown(idx: number) {
    if (idx === steps.length - 1) return;
    const newOrder = [...steps];
    [newOrder[idx], newOrder[idx + 1]] = [newOrder[idx + 1], newOrder[idx]];
    const ids = newOrder.map(s => s.step_id);
    const updated = await reorderSteps(wf.workflow_id, ids);
    setWf(prev => ({ ...prev, steps: updated }));
  }

  async function handleDeleteStep(step: WorkflowStep) {
    if (!confirm(`Remove step "${step.display_name}"? This cannot be undone if tickets are active on it.`)) return;
    try {
      await deleteStep(wf.workflow_id, step.step_id);
      setWf(prev => ({ ...prev, steps: prev.steps.map(s => s.step_id === step.step_id ? { ...s, is_deleted: true } : s) }));
      flash("Step removed");
    } catch (e: unknown) {
      flash(friendlyError(e));
    }
  }

  async function handleAddStep() {
    setAddingStep(true);
    try {
      // Tier-toggle model: Actor is auto-minted; sending a toggle enables tier-toggle mode.
      const newStep = await addStep(wf.workflow_id, {
        display_name: `Step ${steps.length + 1}`,
        supervisor_enabled: true,
      });
      setWf(prev => ({ ...prev, steps: [...prev.steps, newStep] }));
      setExpanded(newStep.step_id);
    } catch (e: unknown) {
      flash(friendlyError(e));
    } finally { setAddingStep(false); }
  }

  async function handleSaveAsTemplate() {
    const defaultName = `${wf.display_name} (template)`;
    const name = window.prompt("Template name", defaultName);
    if (name === null) return;
    const trimmed = name.trim();
    if (!trimmed) return;
    setSavingTemplate(true);
    try {
      const tpl = await saveWorkflowAsTemplate(wf.workflow_id, { display_name: trimmed });
      flash(`Template created: ${tpl.display_name}`);
    } catch (e: unknown) {
      flash(friendlyError(e));
    } finally {
      setSavingTemplate(false);
    }
  }

  function handleStepSaved(updated: WorkflowStep) {
    setWf(prev => ({ ...prev, steps: prev.steps.map(s => s.step_id === updated.step_id ? updated : s) }));
    setExpanded(null);
    flash("Step saved ✓");
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-start justify-between mb-5">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="text-gray-400 hover:text-gray-600 text-sm flex items-center gap-1">
            ← <span>{isTemplate ? "Templates" : "Workflows"}</span>
          </button>
          <span className="text-gray-300">/</span>
          {editingName ? (
            <input autoFocus value={nameVal} onChange={e => setNameVal(e.target.value)}
              onBlur={handleRename} onKeyDown={e => e.key === "Enter" && handleRename()}
              className="text-lg font-semibold text-gray-800 border-b-2 border-blue-400 bg-transparent focus:outline-none" />
          ) : (
            <h2 className="text-lg font-semibold text-gray-800 cursor-pointer hover:text-blue-600" onClick={() => setEditingName(true)} title="Click to rename">
              {wf.display_name}
            </h2>
          )}
          {workflowTrackOf(wf) === "seah" && <span className="inline-flex items-center gap-0.5 text-xs text-red-600"><Lock size={10} strokeWidth={2.5} />SEAH</span>}
          {isTemplate && <span className="text-xs font-medium px-2 py-0.5 rounded bg-blue-100 text-blue-700">Template</span>}
        </div>
        <div className="flex items-center gap-3 flex-wrap justify-end">
          {msg && <span className="text-xs text-green-600 font-medium">{msg}</span>}
          <span className={`text-xs font-medium px-2 py-0.5 rounded ${statusBadge(wf.status)}`}>{wf.status}</span>
          <span className="text-xs text-gray-400">v{wf.version}</span>
          {!isTemplate && wf.status !== "archived" && (
            <button type="button" onClick={handlePublish} disabled={publishing}
              className="text-sm bg-green-600 text-white hover:bg-green-700 px-4 py-1.5 rounded font-medium disabled:opacity-50 transition">
              {publishing ? "Publishing…" : wf.status === "published" ? "Re-publish" : "Publish"}
            </button>
          )}
          {!isTemplate && wf.status === "published" && (
            <button type="button" onClick={handleArchive} disabled={archiving}
              className="text-sm text-gray-500 hover:text-gray-700 border border-gray-300 px-3 py-1.5 rounded transition">
              {archiving ? "Archiving…" : "Archive"}
            </button>
          )}
          {!isTemplate && (
            <button
              type="button"
              onClick={handleSaveAsTemplate}
              disabled={savingTemplate}
              className="text-sm text-blue-700 hover:text-blue-900 border border-blue-200 bg-blue-50 px-3 py-1.5 rounded transition disabled:opacity-50"
            >
              {savingTemplate ? "Saving…" : "Save as template"}
            </button>
          )}
        </div>
      </div>

      {/* Meta info */}
      <div className="flex items-center gap-4 mb-6 text-xs text-gray-500">
        <span>Type: <span className={`font-medium px-1.5 py-0.5 rounded ${typeBadge(wf.workflow_type)}`}>{wf.workflow_type.toUpperCase()}</span></span>
        <span>Key: <code className="text-gray-600 bg-gray-100 px-1.5 py-0.5 rounded">{wf.workflow_key}</code></span>
        {wf.description && <span className="text-gray-400 italic">{wf.description}</span>}
      </div>

      {/* Steps */}
      <div className="space-y-2 mb-4">
        {steps.map((step, idx) => (
          <div key={step.step_id} className="border border-gray-200 rounded-lg overflow-hidden">
            {/* Step row */}
            <div className="flex items-center gap-3 px-4 py-3 bg-white hover:bg-gray-50">
              {/* Reorder */}
              <div className="flex flex-col gap-0.5 shrink-0">
                <button onClick={() => handleMoveUp(idx)} disabled={idx === 0}
                  className="text-gray-400 hover:text-gray-700 disabled:opacity-20 text-xs leading-none">▲</button>
                <button onClick={() => handleMoveDown(idx)} disabled={idx === steps.length - 1}
                  className="text-gray-400 hover:text-gray-700 disabled:opacity-20 text-xs leading-none">▼</button>
              </div>

              {/* Step number */}
              <span className="w-6 h-6 rounded-full bg-slate-700 text-white text-xs flex items-center justify-center font-medium shrink-0">
                {idx + 1}
              </span>

              {/* Step info */}
              <div className="flex-1 min-w-0">
                <div className="font-medium text-gray-800 text-sm">{step.display_name}</div>
                <div className="text-xs text-gray-400 mt-0.5 flex items-center gap-3">
                  <span>{CAST_TIER_LABELS.assigned_role_key}: {roleLabel(step.assigned_role_key)}</span>
                  {step.response_time_hours != null && <span>Response: {step.response_time_hours}h</span>}
                  {step.resolution_time_days != null && <span>Resolution: {step.resolution_time_days}d</span>}
                  {step.response_time_hours == null && step.resolution_time_days == null && <span className="italic">No SLA</span>}
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => setExpanded(expandedStep === step.step_id ? null : step.step_id)}
                  className="text-xs text-blue-600 hover:underline px-2 py-1">
                  {expandedStep === step.step_id ? "Collapse" : "Edit"}
                </button>
                <button onClick={() => handleDeleteStep(step)}
                  className="text-xs text-gray-400 hover:text-red-500 px-1 py-1 leading-none">✕</button>
              </div>
            </div>

            {/* Accordion */}
            {expandedStep === step.step_id && (
              <div className="px-4 pb-4">
                <StepForm
                  step={step}
                  workflowId={wf.workflow_id}
                  hasNextStep={!!steps[idx + 1]}
                  onSaved={handleStepSaved}
                  onCancel={() => setExpanded(null)}
                />
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Add step */}
      <button onClick={handleAddStep} disabled={addingStep}
        className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 border border-dashed border-blue-300 hover:border-blue-500 rounded-lg px-4 py-2.5 w-full justify-center transition disabled:opacity-50">
        {addingStep ? "Adding…" : "+ Add step"}
      </button>

      {!isTemplate && (
        <div className="mt-6 border-t border-gray-200 pt-5">
          <p className="text-xs text-gray-500">
            Assign this workflow on a project under{" "}
            <span className="font-medium">Settings → Projects &amp; packages</span>
            {" "}(Standard / SEAH). New tickets use the workflows selected on their project.
          </p>
        </div>
      )}

      {/* Notification rules (Spec 12 §4) */}
      {!isTemplate && (
        <WorkflowNotificationsPanel workflowSlug={workflowTrackOf(wf)} />
      )}
    </div>
  );
}
