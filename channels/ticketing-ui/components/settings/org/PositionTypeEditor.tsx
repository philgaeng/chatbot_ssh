// SPDX-License-Identifier: Apache-2.0

"use client";

/**
 * <PositionTypeEditor> — create/edit a position type (DESIGN-cast-model §3.2, Frame 06).
 *
 * A position is a **literal job title, display-only**. The modal is four fields, one
 * required: Title (EN) *, Title (Nepali), Used at (allowed_unit_types — optional,
 * descriptive), and Reports to (reports_to_position_key + locus — descriptive, does NOT
 * drive supervision/escalation; that is the tier chain).
 *
 * Removed with the old role coupling: Default role (the position↔role link is gone —
 * the tier is chosen at per-package staffing), Grievance type (workflow_track), supervisor
 * visibility (visibility_mode), and Owning level (owner_organization_id — server-stamped
 * from the author's scope; advanced re-scope is API-only).
 *
 * `position_key` is server-minted from the title (never user-authored) and immutable after create.
 */

import { useState } from "react";

import {
  createPositionType,
  updatePositionType,
  type PositionTypeItem,
  type PositionTypeCreate,
  type PositionTypeUpdate,
} from "@/lib/api";
import { roleLabel } from "@/lib/labels";
import { ErrorNotice } from "@/components/shared/ErrorNotice";
import { ProvenanceHint } from "@/components/shared/ProvenanceHint";

import {
  UNIT_TYPES,
  REPORTS_TO_LOCI,
  unitTypeLabel,
  reportsToLocusLabel,
} from "./orgVocab";

export function PositionTypeEditor({
  mode,
  positionType,
  allPositionTypes,
  initialAllowedUnitTypes,
  onSaved,
  onCancel,
}: {
  mode: "create" | "edit";
  positionType?: PositionTypeItem;
  /** For the "reports to" picker. */
  allPositionTypes: PositionTypeItem[];
  /**
   * Create-mode seed for "Used at" — e.g. the office's unit_type the invite flow launched
   * from, so the new position immediately fits that office. Ignored in edit mode.
   */
  initialAllowedUnitTypes?: string[];
  onSaved: (pt: PositionTypeItem) => void;
  onCancel: () => void;
}) {
  const [displayName, setDisplayName] = useState(positionType?.display_name ?? "");
  const [displayNameNe, setDisplayNameNe] = useState(positionType?.display_name_ne ?? "");
  const [allowedUnitTypes, setAllowedUnitTypes] = useState<string[]>(
    positionType?.allowed_unit_types ?? initialAllowedUnitTypes ?? [],
  );
  const [reportsToKey, setReportsToKey] = useState(positionType?.reports_to_position_key ?? "");
  const [reportsToLocus, setReportsToLocus] = useState(positionType?.reports_to_locus ?? "same_unit");

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);

  function toggleUnitType(ut: string) {
    setAllowedUnitTypes((prev) =>
      prev.includes(ut) ? prev.filter((x) => x !== ut) : [...prev, ut],
    );
  }

  async function handleSave() {
    if (!displayName.trim()) {
      setError("Please enter a title.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (mode === "create") {
        const payload: PositionTypeCreate = {
          display_name: displayName.trim(),
          display_name_ne: displayNameNe.trim() || null,
          allowed_unit_types: allowedUnitTypes,
          reports_to_position_key: reportsToKey || null,
          reports_to_locus: reportsToKey ? reportsToLocus : null,
        };
        const created = await createPositionType(payload);
        onSaved(created);
      } else if (positionType) {
        const payload: PositionTypeUpdate = {
          display_name: displayName.trim(),
          display_name_ne: displayNameNe.trim() || null,
          allowed_unit_types: allowedUnitTypes,
          reports_to_position_key: reportsToKey || null,
          reports_to_locus: reportsToKey ? reportsToLocus : null,
        };
        const updated = await updatePositionType(positionType.position_type_id, payload);
        onSaved(updated);
      }
    } catch (e) {
      setError(e);
      setSaving(false);
    }
  }

  const otherPositions = allPositionTypes.filter(
    (p) => p.position_type_id !== positionType?.position_type_id,
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-hidden rounded-xl bg-white shadow-xl">
        <div className="flex items-center justify-between bg-slate-700 px-6 py-4 text-white">
          <div className="font-semibold">
            {mode === "create" ? "Add position type" : "Edit position type"}
          </div>
          <button
            type="button"
            onClick={onCancel}
            className="text-xl leading-none text-slate-300 hover:text-white"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="max-h-[calc(90vh-8rem)] space-y-4 overflow-y-auto p-6">
          <ErrorNotice error={error} />

          <p className="text-xs text-gray-500">
            A position is just a job title. Who plays which tier (Actor, Supervisor, …) is
            decided per package when you staff a project — not here.
          </p>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-500">Title (English) *</label>
              <input
                autoFocus
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="e.g. Senior Divisional Engineer"
                className="w-full rounded border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-500">Title (Nepali)</label>
              <input
                value={displayNameNe}
                onChange={(e) => setDisplayNameNe(e.target.value)}
                placeholder="वरिष्ठ डिभिजनल इन्जिनियर"
                className="w-full rounded border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
              {!displayNameNe.trim() && (
                <ProvenanceHint className="mt-1">
                  No Nepali title yet — add it later, never invented.
                </ProvenanceHint>
              )}
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-gray-500">
              Used at (office types) <span className="font-normal text-gray-400">— optional</span>
            </label>
            <div className="flex flex-wrap gap-2">
              {UNIT_TYPES.map((ut) => {
                const on = allowedUnitTypes.includes(ut);
                return (
                  <button
                    key={ut}
                    type="button"
                    onClick={() => toggleUnitType(ut)}
                    aria-pressed={on}
                    className={`rounded-full border px-2.5 py-1 text-xs font-medium transition ${
                      on
                        ? "border-blue-300 bg-blue-100 text-blue-700"
                        : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
                    }`}
                  >
                    {unitTypeLabel(ut)}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-500">Reports to</label>
              <select
                value={reportsToKey}
                onChange={(e) => setReportsToKey(e.target.value)}
                className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              >
                <option value="">— No one (top of the line) —</option>
                {otherPositions.map((p) => (
                  <option key={p.position_type_id} value={p.position_key}>
                    {roleLabel(p.position_key, p.display_name)}
                  </option>
                ))}
              </select>
              <ProvenanceHint className="mt-1">
                Descriptive only — the org chart. It doesn&rsquo;t drive supervision or
                escalation; that&rsquo;s the tier chain per step.
              </ProvenanceHint>
            </div>
            {reportsToKey && (
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-500">In the</label>
                <select
                  value={reportsToLocus}
                  onChange={(e) => setReportsToLocus(e.target.value)}
                  className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                >
                  {REPORTS_TO_LOCI.map((l) => (
                    <option key={l} value={l}>
                      {reportsToLocusLabel(l)}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        </div>

        <div className="flex justify-end gap-3 border-t border-gray-100 px-6 py-4">
          <button
            type="button"
            onClick={onCancel}
            className="rounded px-4 py-1.5 text-sm text-gray-500 hover:text-gray-700"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={saving}
            className="rounded bg-blue-600 px-4 py-1.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "Saving…" : mode === "create" ? "Create position type" : "Save changes"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default PositionTypeEditor;
