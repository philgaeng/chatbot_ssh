"use client";

/**
 * <StepForm> — the inline accordion editor for a single workflow step: label, SLA,
 * and the four-tier cast (actor / supervisor / informed / observer). Offers inline role
 * creation via <RoleCreateModal> (the roles-cluster seam).
 *
 * Extracted verbatim from `app/settings/page.tsx` (T3-05) — no behaviour change.
 */
import React, { useState } from "react";
import { updateStep, type WorkflowStep, type StepPayload } from "@/lib/api";
import { roleLabel, CAST_TIER_LABELS } from "@/lib/labels";
import { friendlyError } from "@/components/settings/lib/friendlyError";
import { RoleCreateModal } from "@/components/settings/roles/RoleCreateModal";
import { type WorkflowRoleOption } from "@/components/settings/workflows/workflowHelpers";

export function StepForm({
  step,
  workflowId,
  roleOptions,
  canCreateRole,
  onRoleCreated,
  onSaved,
  onCancel,
}: {
  step: WorkflowStep;
  workflowId: string;
  roleOptions: WorkflowRoleOption[];
  canCreateRole?: boolean;
  onRoleCreated?: () => void;
  onSaved: (s: WorkflowStep) => void;
  onCancel: () => void;
}) {
  const [displayName, setDisplayName]         = useState(step.display_name);
  const [stepKey, setStepKey]                 = useState(step.step_key);
  const [roleKey, setRoleKey]                 = useState(step.assigned_role_key);
  const [responseH, setResponseH]             = useState<string>(step.response_time_hours?.toString() ?? "");
  const [resolutionD, setResolutionD]         = useState<string>(step.resolution_time_days?.toString() ?? "");
  const [actions, setActions]                 = useState<string[]>(step.expected_actions ?? []);
  const [newAction, setNewAction]             = useState("");
  // Spec 12 tier fields
  const [supervisorRole, setSupervisorRole]   = useState<string>(step.supervisor_role ?? "");
  const [informedRoles, setInformedRoles]     = useState<string[]>(step.informed_roles ?? []);
  const [newInformed, setNewInformed]         = useState("");
  const [observerRoles, setObserverRoles]     = useState<string[]>(step.observer_roles ?? []);
  const [newObserver, setNewObserver]         = useState("");
  const [informedPii, setInformedPii]         = useState<boolean>(step.informed_pii_access ?? false);
  const [saving, setSaving]                   = useState(false);
  const [error, setError]                     = useState("");
  const [showCreateRole, setShowCreateRole]   = useState(false);
  const systemRoles = roleOptions.filter((r) => r.origin !== "custom");
  const customRoles = roleOptions.filter((r) => r.origin === "custom");
  const assignedRoleMissing =
    roleKey &&
    !roleOptions.some((r) => r.key === roleKey);

  async function handleSave() {
    if (!displayName.trim() || !roleKey) { setError("Name and role are required."); return; }
    setSaving(true); setError("");
    try {
      const payload: Partial<StepPayload> = {
        display_name: displayName.trim(),
        step_key: stepKey.trim() || undefined,
        assigned_role_key: roleKey,
        response_time_hours: responseH ? parseInt(responseH) : null,
        resolution_time_days: resolutionD ? parseInt(resolutionD) : null,
        expected_actions: actions.length ? actions : null,
        // Spec 12 tier fields
        supervisor_role: supervisorRole || null,
        informed_roles: informedRoles,
        observer_roles: observerRoles,
        informed_pii_access: informedPii,
      };
      const updated = await updateStep(workflowId, step.step_id, payload);
      onSaved(updated);
    } catch (e: unknown) {
      setError(friendlyError(e));
    } finally { setSaving(false); }
  }

  function addTag(list: string[], setList: (v: string[]) => void, val: string, setVal: (v: string) => void) {
    const t = val.trim();
    if (t && !list.includes(t)) setList([...list, t]);
    setVal("");
  }

  return (
    <div className="border border-blue-200 bg-blue-50 rounded-lg p-4 mt-2 space-y-3">
      {error && <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-2 py-1">{error}</p>}

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Display name *</label>
          <input value={displayName} onChange={e => setDisplayName(e.target.value)}
            className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Step key</label>
          <input value={stepKey} onChange={e => setStepKey(e.target.value)}
            className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 font-mono focus:outline-none focus:ring-1 focus:ring-blue-400" />
        </div>
      </div>

      {showCreateRole && (
        <RoleCreateModal
          defaultTrack="standard"
          onCreated={() => { setShowCreateRole(false); onRoleCreated?.(); }}
          onClose={() => setShowCreateRole(false)}
        />
      )}
      <div>
        <label className="text-xs font-medium text-gray-500 block mb-1">Assigned role *</label>
        <select value={roleKey} onChange={e => {
          if (e.target.value === "__create__") { setShowCreateRole(true); return; }
          setRoleKey(e.target.value);
        }}
          className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400">
          <option value="">— select role —</option>
          {assignedRoleMissing && (
            <option value={roleKey}>{roleKey} (current)</option>
          )}
          {systemRoles.length > 0 && (
            <optgroup label="System (TOR)">
              {systemRoles.map(r => <option key={r.key} value={r.key}>{r.label}</option>)}
            </optgroup>
          )}
          {customRoles.length > 0 && (
            <optgroup label="Custom">
              {customRoles.map(r => <option key={r.key} value={r.key}>{r.label}</option>)}
            </optgroup>
          )}
          {canCreateRole && <option value="__create__">+ Create role…</option>}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Response time (hours)</label>
          <input type="number" min="0" value={responseH} onChange={e => setResponseH(e.target.value)} placeholder="e.g. 48"
            className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Resolution time (days)</label>
          <input type="number" min="0" value={resolutionD} onChange={e => setResolutionD(e.target.value)} placeholder="e.g. 7"
            className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
        </div>
      </div>

      {/* Expected actions */}
      <div>
        <label className="text-xs font-medium text-gray-500 block mb-1">Expected actions</label>
        <div className="flex flex-wrap gap-1 mb-1">
          {actions.map(a => (
            <span key={a} className="flex items-center gap-1 text-xs bg-white border border-gray-200 text-gray-700 px-2 py-0.5 rounded">
              {a}
              <button onClick={() => setActions(actions.filter(x => x !== a))} className="text-gray-400 hover:text-red-500 leading-none">×</button>
            </span>
          ))}
        </div>
        <div className="flex gap-2">
          <input value={newAction} onChange={e => setNewAction(e.target.value)}
            onKeyDown={e => e.key === "Enter" && addTag(actions, setActions, newAction, setNewAction)}
            placeholder="e.g. Investigate root cause"
            className="flex-1 text-xs border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
          <button onClick={() => addTag(actions, setActions, newAction, setNewAction)}
            disabled={!newAction.trim()}
            className="text-xs bg-gray-100 hover:bg-gray-200 px-3 py-1.5 rounded disabled:opacity-40 transition">Add</button>
        </div>
      </div>

      {/* ── Step cast (who's involved at this step) ──────────────────────────── */}
      <div className="border-t border-blue-100 pt-3 mt-1 space-y-3">
        <div className="text-[11px] font-semibold text-blue-600 uppercase tracking-wide">Who&apos;s involved at this step</div>

        {/* Supervisor role → "Oversees" */}
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">{CAST_TIER_LABELS.supervisor_role}</label>
          <select value={supervisorRole} onChange={e => setSupervisorRole(e.target.value)}
            className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400">
            <option value="">— None (no supervisor at this step) —</option>
            {roleOptions.map(r => <option key={r.key} value={r.key}>{r.label}</option>)}
          </select>
          <p className="text-[11px] text-gray-400 mt-0.5">Notified on escalation/SLA breach. Can override Actor, reassign ticket.</p>
        </div>

        {/* Informed roles */}
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">{CAST_TIER_LABELS.informed_roles} — auto-added when a ticket enters this step</label>
          <div className="flex flex-wrap gap-1 mb-1">
            {informedRoles.map(r => (
              <span key={r} className="flex items-center gap-1 text-xs bg-violet-50 border border-violet-200 text-violet-700 px-2 py-0.5 rounded">
                {roleLabel(r)}
                <button onClick={() => setInformedRoles(informedRoles.filter(x => x !== r))} className="text-violet-300 hover:text-red-500 leading-none">×</button>
              </span>
            ))}
          </div>
          <div className="flex gap-2">
            <select value={newInformed} onChange={e => setNewInformed(e.target.value)}
              className="flex-1 text-xs border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400">
              <option value="">+ Add informed role</option>
              {roleOptions.filter(r => !informedRoles.includes(r.key)).map(r =>
                <option key={r.key} value={r.key}>{r.label}</option>
              )}
            </select>
            <button onClick={() => addTag(informedRoles, setInformedRoles, newInformed, setNewInformed)}
              disabled={!newInformed}
              className="text-xs bg-gray-100 hover:bg-gray-200 px-3 py-1.5 rounded disabled:opacity-40 transition">Add</button>
          </div>
        </div>

        {/* Observer roles */}
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">{CAST_TIER_LABELS.observer_roles} — read-only access, no notifications</label>
          <div className="flex flex-wrap gap-1 mb-1">
            {observerRoles.map(r => (
              <span key={r} className="flex items-center gap-1 text-xs bg-gray-100 border border-gray-200 text-gray-700 px-2 py-0.5 rounded">
                {roleLabel(r)}
                <button onClick={() => setObserverRoles(observerRoles.filter(x => x !== r))} className="text-gray-400 hover:text-red-500 leading-none">×</button>
              </span>
            ))}
          </div>
          <div className="flex gap-2">
            <select value={newObserver} onChange={e => setNewObserver(e.target.value)}
              className="flex-1 text-xs border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400">
              <option value="">+ Add observer role</option>
              {roleOptions.filter(r => !observerRoles.includes(r.key)).map(r =>
                <option key={r.key} value={r.key}>{r.label}</option>
              )}
            </select>
            <button onClick={() => addTag(observerRoles, setObserverRoles, newObserver, setNewObserver)}
              disabled={!newObserver}
              className="text-xs bg-gray-100 hover:bg-gray-200 px-3 py-1.5 rounded disabled:opacity-40 transition">Add</button>
          </div>
        </div>

        {/* PII access toggle */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setInformedPii(!informedPii)}
            className={`relative inline-flex h-5 w-9 shrink-0 rounded-full border-2 border-transparent transition-colors ${informedPii ? "bg-violet-600" : "bg-gray-200"}`}
          >
            <span className={`inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform ${informedPii ? "translate-x-4" : "translate-x-0"}`} />
          </button>
          <span className="text-xs text-gray-600">
            Informed tier can see complainant PII
            <span className="text-gray-400 ml-1">(default: off)</span>
          </span>
        </div>
      </div>

      <div className="flex justify-end gap-2 pt-1">
        <button onClick={onCancel} className="text-xs text-gray-500 hover:text-gray-700 px-3 py-1.5 rounded transition">Cancel</button>
        <button onClick={handleSave} disabled={saving}
          className="text-xs bg-blue-600 text-white hover:bg-blue-700 px-4 py-1.5 rounded font-medium disabled:opacity-50 transition">
          {saving ? "Saving…" : "Save step"}
        </button>
      </div>
    </div>
  );
}
