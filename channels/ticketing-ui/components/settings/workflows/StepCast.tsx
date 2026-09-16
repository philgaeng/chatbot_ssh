// SPDX-License-Identifier: Apache-2.0

"use client";

/**
 * <StepCast> — a workflow step's tier structure as toggles (DESIGN-cast-model §3.5).
 *
 * A step no longer picks roles or people. It declares which tiers exist: Actor (always on),
 * Supervisor / Participants / Observers (on/off). WHO fills each tier is decided at per-package
 * staffing (Project → Cast), so cloning a workflow rarely needs edits and the messy per-project
 * reality lives where it belongs. The four role-pickers of the old cast are gone.
 */
import React from "react";

function TierToggle({
  on,
  onToggle,
  title,
  gloss,
  accent = "blue",
}: {
  on: boolean;
  onToggle: () => void;
  title: string;
  gloss: string;
  accent?: "blue" | "violet";
}) {
  const bg = on ? (accent === "violet" ? "bg-violet-600" : "bg-blue-600") : "bg-gray-200";
  return (
    <div className="flex items-start gap-3">
      <button
        type="button"
        onClick={onToggle}
        aria-pressed={on}
        className={`relative mt-0.5 inline-flex h-5 w-9 shrink-0 rounded-full border-2 border-transparent transition-colors ${bg}`}
      >
        <span
          className={`inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform ${on ? "translate-x-4" : "translate-x-0"}`}
        />
      </button>
      <div className="min-w-0">
        <div className="text-xs font-medium text-gray-700">{title}</div>
        <div className="text-[11px] text-gray-500">{gloss}</div>
      </div>
    </div>
  );
}

/** The author's naming + required control for one job (doc 12 §6.2, wireframe ui/06). */
function JobDetail({
  tier,
  placeholder,
  labels,
  onLabel,
  required,
  onRequired,
  canRequire = true,
}: {
  tier: string;
  placeholder: string;
  labels: Record<string, { label: string; description?: string }>;
  onLabel: (tier: string, patch: { label?: string; description?: string }) => void;
  required: boolean;
  onRequired: (tier: string, v: boolean) => void;
  canRequire?: boolean;
}) {
  const v = labels[tier] ?? { label: "", description: "" };
  // A job with no name cannot be saved (doc 12 §6.2): officers read this word on the staffing
  // screen, the case view and the go-live checklist, and a project cannot supply it. Flagged
  // here so the requirement is visible while typing, not only when the save is refused.
  const unnamed = !(v.label ?? "").trim();
  return (
    <div className="ml-12 mt-1.5 space-y-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <input
          value={v.label}
          onChange={(e) => onLabel(tier, { label: e.target.value })}
          placeholder={placeholder}
          aria-invalid={unnamed || undefined}
          className={`flex-1 min-w-[160px] max-w-xs rounded border px-2 py-1 text-xs ${
            unnamed ? "border-red-300 bg-red-50" : "border-gray-300"
          }`}
          aria-label="Name shown to officers"
        />
        {canRequire ? (
          <label className="flex items-center gap-1.5 text-[11px] text-gray-600">
            <input type="checkbox" checked={required} onChange={(e) => onRequired(tier, e.target.checked)} />
            Required
          </label>
        ) : (
          <span className="text-[10px] font-semibold uppercase tracking-wide text-gray-400">
            Always required
          </span>
        )}
      </div>
      <input
        value={v.description ?? ""}
        onChange={(e) => onLabel(tier, { description: e.target.value })}
        placeholder="Short description (optional)"
        className="w-full max-w-md rounded border border-gray-200 px-2 py-1 text-[11px]"
        aria-label="Short description"
      />
      {unnamed && (
        <p className="text-[11px] text-red-700">
          Give this job a name — officers see it on every screen.
        </p>
      )}
    </div>
  );
}

export function StepCast({
  supervisorEnabled,
  onSupervisorEnabled,
  participantsEnabled,
  onParticipantsEnabled,
  observersEnabled,
  onObserversEnabled,
  informedPii,
  onInformedPii,
  actorCanReassign,
  onActorCanReassign,
  hasNextStep,
  tierLabels,
  onTierLabel,
  requiredTiers,
  onRequiredTier,
}: {
  supervisorEnabled: boolean;
  onSupervisorEnabled: (v: boolean) => void;
  participantsEnabled: boolean;
  onParticipantsEnabled: (v: boolean) => void;
  observersEnabled: boolean;
  onObserversEnabled: (v: boolean) => void;
  informedPii: boolean;
  onInformedPii: (v: boolean) => void;
  actorCanReassign: boolean;
  onActorCanReassign: (v: boolean) => void;
  /** Whether a later step exists — drives the read-only escalation-target line. */
  hasNextStep?: boolean;
  tierLabels: Record<string, { label: string; description?: string }>;
  onTierLabel: (tier: string, patch: { label?: string; description?: string }) => void;
  requiredTiers: string[];
  onRequiredTier: (tier: string, v: boolean) => void;
}) {
  const isRequired = (t: string) => requiredTiers.includes(t);
  return (
    <div className="border-t border-blue-100 pt-3 mt-1 space-y-3">
      <div>
        <div className="text-[11px] font-semibold text-blue-600 uppercase tracking-wide">
          The jobs at this level
        </div>
        <p className="text-[11px] text-gray-500 mt-0.5">
          Choose which jobs this level has and name them. Officers see the name you write here
          on every screen. You assign the people per project.
        </p>
      </div>

      {/* Actor — always on, no control */}
      <div className="flex items-start gap-3">
        <span className="mt-0.5 inline-flex h-5 items-center rounded-full bg-blue-100 px-2 text-[10px] font-semibold uppercase tracking-wide text-blue-700">
          Always on
        </span>
        <div>
          <div className="text-xs font-medium text-gray-700">Works it</div>
          <div className="text-[11px] text-gray-500">
            Receives the grievance and resolves it. Every level has one.
          </div>
        </div>
      </div>
      <JobDetail
        tier="actor"
        placeholder="e.g. Safeguard Officer"
        labels={tierLabels}
        onLabel={onTierLabel}
        required
        onRequired={onRequiredTier}
        canRequire={false}
      />

      <TierToggle
        on={supervisorEnabled}
        onToggle={() => onSupervisorEnabled(!supervisorEnabled)}
        title="Oversees"
        gloss="Alerted on escalation and when an SLA is missed; can reassign."
      />
      {supervisorEnabled && (
        <JobDetail
          tier="supervisor"
          placeholder="e.g. Escalation Lead"
          labels={tierLabels}
          onLabel={onTierLabel}
          required={isRequired("supervisor")}
          onRequired={onRequiredTier}
        />
      )}

      <div className="space-y-2">
        <TierToggle
          on={participantsEnabled}
          onToggle={() => onParticipantsEnabled(!participantsEnabled)}
          title="Kept informed"
          gloss="Sees updates and can add notes. No workflow actions."
          accent="violet"
        />
        {participantsEnabled && (
          <JobDetail
            tier="informed"
            placeholder="e.g. Donor Focal"
            labels={tierLabels}
            onLabel={onTierLabel}
            required={isRequired("informed")}
            onRequired={onRequiredTier}
          />
        )}
        {participantsEnabled && (
          <div className="ml-12 flex items-center gap-3">
            <button
              type="button"
              onClick={() => onInformedPii(!informedPii)}
              aria-pressed={informedPii}
              className={`relative inline-flex h-5 w-9 shrink-0 rounded-full border-2 border-transparent transition-colors ${informedPii ? "bg-violet-600" : "bg-gray-200"}`}
            >
              <span
                className={`inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform ${informedPii ? "translate-x-4" : "translate-x-0"}`}
              />
            </button>
            <span className="text-[11px] text-gray-600">
              Participants can see complainant PII
              <span className="text-gray-400 ml-1">(default: off)</span>
            </span>
          </div>
        )}
      </div>

      <TierToggle
        on={observersEnabled}
        onToggle={() => onObserversEnabled(!observersEnabled)}
        title="Can view"
        gloss="Read-only; no notifications."
      />
      {observersEnabled && (
        <JobDetail
          tier="observer"
          placeholder="e.g. Legal Observer"
          labels={tierLabels}
          onLabel={onTierLabel}
          required={isRequired("observer")}
          onRequired={onRequiredTier}
        />
      )}

      {/* Advanced — Actor self-serve reassignment (§3.4 chain otherwise). */}
      <div className="border-t border-blue-100 pt-2">
        <TierToggle
          on={actorCanReassign}
          onToggle={() => onActorCanReassign(!actorCanReassign)}
          title="Let the officer working it reassign the grievance"
          gloss="Advanced. Otherwise reassignment goes through whoever oversees the level, then a project administrator."
        />
      </div>

      {/* Escalation target — read-only, derived from step order. */}
      <div className="text-[11px] text-gray-500 bg-white/60 border border-blue-100 rounded px-2 py-1.5">
        {hasNextStep ? (
          <>Escalates to the next level.</>
        ) : (
          <>Last level — resolves here; no automatic escalation.</>
        )}
      </div>
    </div>
  );
}
