"use client";

/**
 * <StepForm> — inline accordion editor for a single workflow step: label, SLA, and the tier
 * cast as toggles (Actor always on; Supervisor / Participants / Observers on/off). The step
 * declares its cast STRUCTURE; who fills each tier is decided at per-package staffing
 * (DESIGN-cast-model §3.5). No role or person is picked here.
 */
import React, { useState } from "react";
import { updateStep, type WorkflowStep, type StepPayload } from "@/lib/api";
import { friendlyError } from "@/components/settings/lib/friendlyError";
import { StepCast } from "@/components/settings/workflows/StepCast";

export function StepForm({
  step,
  workflowId,
  hasNextStep,
  onSaved,
  onCancel,
}: {
  step: WorkflowStep;
  workflowId: string;
  /** Whether a later step exists — for StepCast's read-only escalation-target line. */
  hasNextStep?: boolean;
  onSaved: (s: WorkflowStep) => void;
  onCancel: () => void;
}) {
  const [displayName, setDisplayName] = useState(step.display_name);
  const [stepKey, setStepKey] = useState(step.step_key);
  const [responseH, setResponseH] = useState<string>(step.response_time_hours?.toString() ?? "");
  const [resolutionD, setResolutionD] = useState<string>(step.resolution_time_days?.toString() ?? "");
  // Tier toggles derived from the step's current fields.
  const [supervisorEnabled, setSupervisorEnabled] = useState<boolean>(!!step.supervisor_role);
  const [participantsEnabled, setParticipantsEnabled] = useState<boolean>((step.informed_roles?.length ?? 0) > 0);
  const [observersEnabled, setObserversEnabled] = useState<boolean>((step.observer_roles?.length ?? 0) > 0);
  const [informedPii, setInformedPii] = useState<boolean>(step.informed_pii_access ?? false);
  const [actorCanReassign, setActorCanReassign] = useState<boolean>(step.actor_can_reassign ?? false);
  // The author's name for each job at this level + which non-actor jobs are mandatory.
  const [tierLabels, setTierLabels] = useState<Record<string, { label: string; description?: string }>>(
    () => step.tier_labels ?? {},
  );
  const [requiredTiers, setRequiredTiers] = useState<string[]>(() => step.required_tiers ?? []);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSave() {
    if (!displayName.trim()) {
      setError("A step name is required.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const payload: Partial<StepPayload> = {
        display_name: displayName.trim(),
        step_key: stepKey.trim() || undefined,
        response_time_hours: responseH ? parseInt(responseH) : null,
        resolution_time_days: resolutionD ? parseInt(resolutionD) : null,
        // Tier toggles → backend mints/clears synthetic per-step-tier keys.
        supervisor_enabled: supervisorEnabled,
        participants_enabled: participantsEnabled,
        observers_enabled: observersEnabled,
        informed_pii_access: informedPii,
        actor_can_reassign: actorCanReassign,
        // Drop empty names so a blank input doesn't overwrite the role-name fallback.
        tier_labels: Object.fromEntries(
          Object.entries(tierLabels).filter(([, v]) => v.label.trim()),
        ),
        required_tiers: requiredTiers,
      };
      const updated = await updateStep(workflowId, step.step_id, payload);
      onSaved(updated);
    } catch (e: unknown) {
      setError(friendlyError(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="border border-blue-200 bg-blue-50 rounded-lg p-4 mt-2 space-y-3">
      {error && <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-2 py-1">{error}</p>}

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Step name *</label>
          <input
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="e.g. Level 1 — Site safeguards review"
            className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
          <p className="text-[11px] text-gray-400 mt-0.5">
            The name is the documentation — say what happens here, not just &ldquo;Step 1&rdquo;.
          </p>
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Step key</label>
          <input
            value={stepKey}
            onChange={(e) => setStepKey(e.target.value)}
            className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 font-mono focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
        </div>
      </div>

      <StepCast
        tierLabels={tierLabels}
        onTierLabel={(tier, patch) =>
          setTierLabels((prev) => ({
            ...prev,
            [tier]: { ...(prev[tier] ?? { label: "" }), ...patch },
          }))
        }
        requiredTiers={requiredTiers}
        onRequiredTier={(tier, v) =>
          setRequiredTiers((prev) => (v ? [...new Set([...prev, tier])] : prev.filter((t) => t !== tier)))
        }
        supervisorEnabled={supervisorEnabled}
        onSupervisorEnabled={setSupervisorEnabled}
        participantsEnabled={participantsEnabled}
        onParticipantsEnabled={setParticipantsEnabled}
        observersEnabled={observersEnabled}
        onObserversEnabled={setObserversEnabled}
        informedPii={informedPii}
        onInformedPii={setInformedPii}
        actorCanReassign={actorCanReassign}
        onActorCanReassign={setActorCanReassign}
        hasNextStep={hasNextStep}
      />

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Response time (hours)</label>
          <input
            type="number"
            min="0"
            value={responseH}
            onChange={(e) => setResponseH(e.target.value)}
            placeholder="e.g. 48"
            className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Resolution time (days)</label>
          <input
            type="number"
            min="0"
            value={resolutionD}
            onChange={(e) => setResolutionD(e.target.value)}
            placeholder="e.g. 7"
            className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
        </div>
      </div>

      <div className="flex justify-end gap-2 pt-1">
        <button onClick={onCancel} className="text-xs text-gray-500 hover:text-gray-700 px-3 py-1.5 rounded transition">Cancel</button>
        <button
          onClick={handleSave}
          disabled={saving}
          className="text-xs bg-blue-600 text-white hover:bg-blue-700 px-4 py-1.5 rounded font-medium disabled:opacity-50 transition"
        >
          {saving ? "Saving…" : "Save step"}
        </button>
      </div>
    </div>
  );
}
