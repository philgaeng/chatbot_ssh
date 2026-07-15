"use client";

/**
 * <RoleEditModal> — edits an existing operational role in `ticketing.roles`
 * (display name, workflow scope, default jurisdiction, description). The `role_key`
 * is fixed; assignment tiers are configured per workflow step.
 *
 * Extracted verbatim from `app/settings/page.tsx` (T3-05) — no behaviour change.
 */
import React, { useState } from "react";
import { updateRole } from "@/lib/api";
import { JURISDICTION_MODE_LABELS, type JurisdictionMode } from "@/lib/jurisdiction";
import { friendlyError } from "@/components/settings/lib/friendlyError";
import { type RoleEntry, mapGrmRoleToEntry } from "@/components/settings/roles/roleEntry";

export function RoleEditModal({ role, onSaved, onClose }: {
  role: RoleEntry;
  onSaved: (updated: RoleEntry) => void;
  onClose: () => void;
}) {
  const [label, setLabel]               = useState(role.label);
  const [workflow, setWorkflow]         = useState(role.workflow || "Standard");
  const [jurisdiction, setJurisdiction] = useState<JurisdictionMode>(
    (role.jurisdiction as JurisdictionMode) || "field",
  );
  const [description, setDescription] = useState(role.description);
  const [saved, setSaved]               = useState(false);
  const [saving, setSaving]             = useState(false);
  const [err, setErr]                   = useState("");

  async function handleSave() {
    setErr("");
    setSaving(true);
    try {
      const raw = await updateRole(role.role_id, {
        display_name: label.trim(),
        description: description.trim() || null,
        workflow_scope: workflow.trim() || null,
        jurisdiction_mode: jurisdiction,
      });
      onSaved(mapGrmRoleToEntry(raw));
      setSaved(true);
      setTimeout(() => { setSaved(false); onClose(); }, 650);
    } catch (e: unknown) {
      setErr(friendlyError(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 overflow-hidden">
        <div className="bg-slate-700 text-white px-6 py-4 flex items-center justify-between">
          <div>
            <div className="font-semibold">Edit Role</div>
            <div className="text-xs text-slate-300 font-mono mt-0.5">{role.key}</div>
          </div>
          <button type="button" onClick={onClose} className="text-slate-300 hover:text-white text-xl leading-none">×</button>
        </div>

        <div className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">Display name</label>
              <input
                autoFocus
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">Workflow scope</label>
              <select
                value={workflow}
                onChange={(e) => setWorkflow(e.target.value)}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
              >
                <option value="Standard">Standard</option>
                <option value="SEAH">SEAH</option>
                <option value="Both">Both</option>
              </select>
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Default jurisdiction</label>
            <select
              value={jurisdiction}
              onChange={(e) => setJurisdiction(e.target.value as JurisdictionMode)}
              className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
            >
              {(Object.keys(JURISDICTION_MODE_LABELS) as JurisdictionMode[]).map((mode) => (
                <option key={mode} value={mode}>{JURISDICTION_MODE_LABELS[mode]}</option>
              ))}
            </select>
            <p className="text-xs text-gray-400 mt-1">
              Controls whether new officer scopes need a project, package, or location. Observer roles typically use country-wide.
            </p>
          </div>

          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 resize-none focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>

          {err && <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-2 py-1">{err}</p>}

          <p className="text-xs text-gray-400">
            Changes are saved to <span className="font-mono">ticketing.roles</span>. Role <span className="font-mono">role_key</span> is fixed; workflow assignment tiers are configured per workflow step.
          </p>
        </div>

        <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-3">
          <button type="button" onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700 px-4 py-1.5 rounded transition">
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={saving || !label.trim()}
            className={`text-sm px-4 py-1.5 rounded font-medium transition disabled:opacity-40 ${
              saved ? "bg-green-600 text-white" : "bg-blue-600 text-white hover:bg-blue-700"
            }`}
          >
            {saved ? "✓ Saved" : saving ? "Saving…" : "Save changes"}
          </button>
        </div>
      </div>
    </div>
  );
}
