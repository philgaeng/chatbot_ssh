"use client";

/**
 * <StepCast> — the four-slot cast for a workflow step (DESIGN §4.3): Handles it / Oversees /
 * Kept informed / Can view. A step is *not one role* — it's a small cast, one relationship per
 * slot (`assigned_role_key` / `supervisor_role` / `informed_roles[]` / `observer_roles[]`).
 *
 * Every slot picks a ROLE — officers are cast into it through the position they hold. That is
 * stated explicitly here so it is not confused with the sibling Positions surface (which does
 * talk in positions). Each picker is valid-only: roles whose track doesn't match the workflow
 * are shown greyed with the reason ("wrong track"), never silently dropped — single-sourced via
 * lib/trackFilter (DESIGN §4.3 / build-sheet frame-04; owner/level reasons are not client-derivable,
 * so v1 greys the derivable wrong-track case only). The escalation target is read-only, derived
 * from step order (the reporting line never redirects it — doc 16).
 */
import React from "react";

import { roleInTrack, type WorkflowTrack } from "@/lib/trackFilter";
import { roleLabel, CAST_TIER_LABELS } from "@/lib/labels";
import { type WorkflowRoleOption } from "@/components/settings/workflows/workflowHelpers";

const CREATE = "__create__";
const SELECT_CLS =
  "w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400";

export function StepCast({
  track,
  roleOptions,
  assignedRole,
  onAssignedRole,
  supervisorRole,
  onSupervisorRole,
  informedRoles,
  onInformedRoles,
  observerRoles,
  onObserverRoles,
  informedPii,
  onInformedPii,
  nextStepAssignedRole,
  canCreateRole,
  onCreateRole,
}: {
  track: WorkflowTrack;
  roleOptions: WorkflowRoleOption[];
  assignedRole: string;
  onAssignedRole: (v: string) => void;
  supervisorRole: string;
  onSupervisorRole: (v: string) => void;
  informedRoles: string[];
  onInformedRoles: (v: string[]) => void;
  observerRoles: string[];
  onObserverRoles: (v: string[]) => void;
  informedPii: boolean;
  onInformedPii: (v: boolean) => void;
  /** The next step's `assigned_role_key`, for the read-only escalation-target line. */
  nextStepAssignedRole?: string | null;
  canCreateRole?: boolean;
  onCreateRole?: () => void;
}) {
  const inTrack = roleOptions.filter((r) => roleInTrack(r.scope ?? "", track));
  const offTrack = roleOptions.filter((r) => !roleInTrack(r.scope ?? "", track));
  const systemInTrack = inTrack.filter((r) => r.origin !== "custom");
  const customInTrack = inTrack.filter((r) => r.origin === "custom");
  const assignedMissing = !!assignedRole && !roleOptions.some((r) => r.key === assignedRole);

  // Greyed, disabled "Not shown" group — wrong-track roles kept visible with their reason.
  const renderOffTrack = () =>
    offTrack.length > 0 ? (
      <optgroup label={`— Not shown (${offTrack.length}) · wrong track —`}>
        {offTrack.map((r) => (
          <option key={r.key} value={r.key} disabled>
            {r.label} · wrong track ({r.scope})
          </option>
        ))}
      </optgroup>
    ) : null;

  function addTo(list: string[], setList: (v: string[]) => void, key: string) {
    if (key && !list.includes(key)) setList([...list, key]);
  }

  const renderAddable = (exclude: string[]) => (
    <>
      {inTrack
        .filter((r) => !exclude.includes(r.key))
        .map((r) => (
          <option key={r.key} value={r.key}>
            {r.label}
          </option>
        ))}
      {renderOffTrack()}
    </>
  );

  return (
    <div className="border-t border-blue-100 pt-3 mt-1 space-y-3">
      <div>
        <div className="text-[11px] font-semibold text-blue-600 uppercase tracking-wide">
          Who&apos;s involved at this step
        </div>
        <p className="text-[11px] text-gray-500 mt-0.5">
          Each slot is a <span className="font-medium">role</span> — officers are cast into it through the
          position they hold. You&apos;re choosing roles here, not specific people or positions.
        </p>
      </div>

      {/* Handles it — assigned_role_key (one, required) */}
      <div>
        <label className="text-xs font-medium text-gray-500 block mb-1">
          {CAST_TIER_LABELS.assigned_role_key} <span className="text-red-500">*</span>
          <span className="font-normal text-gray-400"> · owns &amp; works the case · one</span>
        </label>
        <select
          value={assignedRole}
          onChange={(e) => {
            if (e.target.value === CREATE) {
              onCreateRole?.();
              return;
            }
            onAssignedRole(e.target.value);
          }}
          className={SELECT_CLS}
        >
          <option value="">— select role —</option>
          {assignedMissing && <option value={assignedRole}>{roleLabel(assignedRole)} (current)</option>}
          {systemInTrack.length > 0 && (
            <optgroup label="System (TOR)">
              {systemInTrack.map((r) => (
                <option key={r.key} value={r.key}>
                  {r.label}
                </option>
              ))}
            </optgroup>
          )}
          {customInTrack.length > 0 && (
            <optgroup label="Custom">
              {customInTrack.map((r) => (
                <option key={r.key} value={r.key}>
                  {r.label}
                </option>
              ))}
            </optgroup>
          )}
          {canCreateRole && <option value={CREATE}>+ Create role…</option>}
          {renderOffTrack()}
        </select>
      </div>

      {/* Oversees — supervisor_role (one) */}
      <div>
        <label className="text-xs font-medium text-gray-500 block mb-1">
          {CAST_TIER_LABELS.supervisor_role}
          <span className="font-normal text-gray-400"> · escalate / reassign · one, optional</span>
        </label>
        <select value={supervisorRole} onChange={(e) => onSupervisorRole(e.target.value)} className={SELECT_CLS}>
          <option value="">— None (no supervisor at this step) —</option>
          {inTrack.map((r) => (
            <option key={r.key} value={r.key}>
              {r.label}
            </option>
          ))}
          {renderOffTrack()}
        </select>
        <p className="text-[11px] text-gray-400 mt-0.5">
          Alerted on escalation / SLA breach. Can override the actor and reassign the ticket.
        </p>
      </div>

      {/* Kept informed — informed_roles[] (many) */}
      <div>
        <label className="text-xs font-medium text-gray-500 block mb-1">
          {CAST_TIER_LABELS.informed_roles}
          <span className="font-normal text-gray-400"> · view + notes · many · auto-added on entry</span>
        </label>
        <div className="flex flex-wrap gap-1 mb-1">
          {informedRoles.map((r) => (
            <span
              key={r}
              className="flex items-center gap-1 text-xs bg-violet-50 border border-violet-200 text-violet-700 px-2 py-0.5 rounded"
            >
              {roleLabel(r)}
              <button
                onClick={() => onInformedRoles(informedRoles.filter((x) => x !== r))}
                className="text-violet-300 hover:text-red-500 leading-none"
              >
                ×
              </button>
            </span>
          ))}
        </div>
        <select value="" onChange={(e) => addTo(informedRoles, onInformedRoles, e.target.value)} className={SELECT_CLS}>
          <option value="">+ Add informed role</option>
          {renderAddable(informedRoles)}
        </select>

        {/* PII access rides with the Informed slot */}
        <div className="flex items-center gap-3 mt-2">
          <button
            type="button"
            onClick={() => onInformedPii(!informedPii)}
            className={`relative inline-flex h-5 w-9 shrink-0 rounded-full border-2 border-transparent transition-colors ${informedPii ? "bg-violet-600" : "bg-gray-200"}`}
          >
            <span
              className={`inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform ${informedPii ? "translate-x-4" : "translate-x-0"}`}
            />
          </button>
          <span className="text-xs text-gray-600">
            Informed tier can see complainant PII<span className="text-gray-400 ml-1">(default: off)</span>
          </span>
        </div>
      </div>

      {/* Can view — observer_roles[] (many) */}
      <div>
        <label className="text-xs font-medium text-gray-500 block mb-1">
          {CAST_TIER_LABELS.observer_roles}
          <span className="font-normal text-gray-400"> · read-only, no notifications · many</span>
        </label>
        <div className="flex flex-wrap gap-1 mb-1">
          {observerRoles.map((r) => (
            <span
              key={r}
              className="flex items-center gap-1 text-xs bg-gray-100 border border-gray-200 text-gray-700 px-2 py-0.5 rounded"
            >
              {roleLabel(r)}
              <button
                onClick={() => onObserverRoles(observerRoles.filter((x) => x !== r))}
                className="text-gray-400 hover:text-red-500 leading-none"
              >
                ×
              </button>
            </span>
          ))}
        </div>
        <select value="" onChange={(e) => addTo(observerRoles, onObserverRoles, e.target.value)} className={SELECT_CLS}>
          <option value="">+ Add observer role</option>
          {renderAddable(observerRoles)}
        </select>
      </div>

      {/* Escalation target — read-only, derived from step order (not the reporting line). */}
      <div className="text-[11px] text-gray-500 bg-white/60 border border-blue-100 rounded px-2 py-1.5">
        {nextStepAssignedRole ? (
          <>
            Escalates to the next step&apos;s{" "}
            <span className="font-medium">{CAST_TIER_LABELS.assigned_role_key}</span>:{" "}
            {roleLabel(nextStepAssignedRole)}
          </>
        ) : (
          <>Last step — resolves here; no automatic escalation.</>
        )}
      </div>
    </div>
  );
}
