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
}) {
  return (
    <div className="border-t border-blue-100 pt-3 mt-1 space-y-3">
      <div>
        <div className="text-[11px] font-semibold text-blue-600 uppercase tracking-wide">
          Tiers at this step
        </div>
        <p className="text-[11px] text-gray-500 mt-0.5">
          Choose which tiers this step uses. You&apos;ll assign the actual officers per package
          when you set up each project.
        </p>
      </div>

      {/* Actor — always on, no control */}
      <div className="flex items-start gap-3">
        <span className="mt-0.5 inline-flex h-5 items-center rounded-full bg-blue-100 px-2 text-[10px] font-semibold uppercase tracking-wide text-blue-700">
          Always on
        </span>
        <div>
          <div className="text-xs font-medium text-gray-700">Actor</div>
          <div className="text-[11px] text-gray-500">
            Owns &amp; works the case — acknowledge, note, escalate, resolve, reply. Every step has one.
          </div>
        </div>
      </div>

      <TierToggle
        on={supervisorEnabled}
        onToggle={() => onSupervisorEnabled(!supervisorEnabled)}
        title="Supervisor"
        gloss="Oversees; the escalation / SLA-breach target and default reassignment authority."
      />

      <div className="space-y-2">
        <TierToggle
          on={participantsEnabled}
          onToggle={() => onParticipantsEnabled(!participantsEnabled)}
          title="Participants (kept informed)"
          gloss="View + add notes; auto-added on step entry. No workflow actions."
          accent="violet"
        />
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
        title="Observers (can view)"
        gloss="Read-only; no notifications."
      />

      {/* Advanced — Actor self-serve reassignment (§3.4 chain otherwise). */}
      <div className="border-t border-blue-100 pt-2">
        <TierToggle
          on={actorCanReassign}
          onToggle={() => onActorCanReassign(!actorCanReassign)}
          title="Actor can self-reassign at this step"
          gloss="Advanced — lets the assigned Actor route the ticket directly. Otherwise the chain is Dispatcher → Supervisor → project admin."
        />
      </div>

      {/* Escalation target — read-only, derived from step order. */}
      <div className="text-[11px] text-gray-500 bg-white/60 border border-blue-100 rounded px-2 py-1.5">
        {hasNextStep ? (
          <>Escalates to the next step&apos;s Actor.</>
        ) : (
          <>Last step — resolves here; no automatic escalation.</>
        )}
      </div>
    </div>
  );
}
