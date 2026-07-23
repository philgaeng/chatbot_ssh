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
import { type WorkflowTrack } from "@/lib/trackFilter";
import { friendlyError } from "@/components/settings/lib/friendlyError";
import { RoleCreateModal } from "@/components/settings/roles/RoleCreateModal";
import { StepCast } from "@/components/settings/workflows/StepCast";
import { type WorkflowRoleOption } from "@/components/settings/workflows/workflowHelpers";

export function StepForm({
  step,
  workflowId,
  roleOptions,
  track,
  nextStepAssignedRole,
  canCreateRole,
  onRoleCreated,
  onSaved,
  onCancel,
}: {
  step: WorkflowStep;
  workflowId: string;
  roleOptions: WorkflowRoleOption[];
  track: WorkflowTrack;
  /** Next step's `assigned_role_key`, for StepCast's read-only escalation-target line. */
  nextStepAssignedRole?: string | null;
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
  const [observerRoles, setObserverRoles]     = useState<string[]>(step.observer_roles ?? []);
  const [informedPii, setInformedPii]         = useState<boolean>(step.informed_pii_access ?? false);
  const [saving, setSaving]                   = useState(false);
  const [error, setError]                     = useState("");
  const [showCreateRole, setShowCreateRole]   = useState(false);

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
      <StepCast
        track={track}
        roleOptions={roleOptions}
        assignedRole={roleKey}
        onAssignedRole={setRoleKey}
        supervisorRole={supervisorRole}
        onSupervisorRole={setSupervisorRole}
        informedRoles={informedRoles}
        onInformedRoles={setInformedRoles}
        observerRoles={observerRoles}
        onObserverRoles={setObserverRoles}
        informedPii={informedPii}
        onInformedPii={setInformedPii}
        nextStepAssignedRole={nextStepAssignedRole}
        canCreateRole={canCreateRole}
        onCreateRole={() => setShowCreateRole(true)}
      />

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
