"use client";

/**
 * <RoleCreateModal> — creates a new operational role from an archetype preset.
 *
 * Used by both the Roles tab and the workflows <StepForm> (which offers role creation
 * inline while picking a step's cast), which is why it is its own module.
 *
 * Extracted verbatim from `app/settings/page.tsx` (T3-05) — no behaviour change.
 */
import React, { useState, useEffect } from "react";
import { createRole, listRoleArchetypes, type RoleArchetype } from "@/lib/api";
import { JURISDICTION_MODE_LABELS, type JurisdictionMode } from "@/lib/jurisdiction";
import { ErrorNotice } from "@/components/shared/ErrorNotice";
import { friendlyError } from "@/components/settings/lib/friendlyError";

export function RoleCreateModal({
  defaultTrack,
  onCreated,
  onClose,
}: {
  defaultTrack: "standard" | "seah";
  onCreated: () => void;
  onClose: () => void;
}) {
  const [displayName, setDisplayName] = useState("");
  const [roleKey, setRoleKey] = useState("");
  const [workflowScope, setWorkflowScope] = useState(defaultTrack === "seah" ? "SEAH" : "Standard");
  const [jurisdiction, setJurisdiction] = useState<JurisdictionMode>("field");
  const [archetype, setArchetype] = useState("field_actor");
  const [description, setDescription] = useState("");
  const [archetypes, setArchetypes] = useState<RoleArchetype[]>([]);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    listRoleArchetypes().then(setArchetypes).catch(() => setArchetypes([]));
  }, []);

  async function handleSave() {
    if (!displayName.trim()) { setErr("Display name is required"); return; }
    setSaving(true); setErr("");
    try {
      await createRole({
        display_name: displayName.trim(),
        role_key: roleKey.trim() || undefined,
        workflow_scope: workflowScope,
        jurisdiction_mode: jurisdiction,
        archetype,
        description: description.trim() || undefined,
      });
      onCreated();
      onClose();
    } catch (e: unknown) {
      setErr(friendlyError(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg p-5">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">New operational role</h3>
        {err && <ErrorNotice error={err} className="mb-3" />}
        <div className="space-y-3 text-sm">
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Display name *</label>
            <input value={displayName} onChange={(e) => setDisplayName(e.target.value)}
              className="w-full border border-gray-300 rounded px-2 py-1.5" />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Role key (slug)</label>
            <input value={roleKey} onChange={(e) => setRoleKey(e.target.value)} placeholder="auto-generated if empty"
              className="w-full border border-gray-300 rounded px-2 py-1.5 font-mono text-xs" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">Workflow track</label>
              <select value={workflowScope} onChange={(e) => setWorkflowScope(e.target.value)}
                className="w-full border border-gray-300 rounded px-2 py-1.5">
                <option value="Standard">Standard</option>
                <option value="SEAH">SEAH</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">Archetype</label>
              <select value={archetype} onChange={(e) => setArchetype(e.target.value)}
                className="w-full border border-gray-300 rounded px-2 py-1.5">
                {archetypes.map((a) => (
                  <option key={a.key} value={a.key}>{a.label}</option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Default jurisdiction</label>
            <select value={jurisdiction} onChange={(e) => setJurisdiction(e.target.value as JurisdictionMode)}
              className="w-full border border-gray-300 rounded px-2 py-1.5">
              {Object.entries(JURISDICTION_MODE_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Description</label>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2}
              className="w-full border border-gray-300 rounded px-2 py-1.5" />
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-5">
          <button type="button" onClick={onClose} className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded">Cancel</button>
          <button type="button" onClick={handleSave} disabled={saving}
            className="px-4 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50">
            {saving ? "Creating…" : "Create role"}
          </button>
        </div>
      </div>
    </div>
  );
}
