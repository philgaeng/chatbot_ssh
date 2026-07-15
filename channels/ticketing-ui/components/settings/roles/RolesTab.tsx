"use client";

/**
 * <RolesTab> — Settings → Workflows, roles & permissions → Roles.
 *
 * Lists the operational role catalog (track-filtered), and drives create / edit /
 * remove. Admin assignments are a separate surface (Settings → Admin access).
 *
 * Extracted verbatim from `app/settings/page.tsx` (T3-05) — no behaviour change.
 */
import React, { useState } from "react";
import { deleteRole } from "@/lib/api";
import { useAuth } from "@/app/providers/AuthProvider";
import { roleMatchesFilter, type TrackFilter } from "@/lib/trackFilter";
import { ErrorNotice } from "@/components/shared/ErrorNotice";
import { friendlyError } from "@/components/settings/lib/friendlyError";
import { type RoleEntry, owningLevelLabel } from "@/components/settings/roles/roleEntry";
import { RoleEditModal } from "@/components/settings/roles/RoleEditModal";
import { RoleCreateModal } from "@/components/settings/roles/RoleCreateModal";

export function RolesTab({ catalog, loading, onReload, canCreate }: {
  catalog: RoleEntry[];
  loading: boolean;
  onReload: () => void;
  canCreate: boolean;
}) {
  const [editing, setEditing]   = useState<RoleEntry | null>(null);
  const [creating, setCreating] = useState(false);
  const [trackFilter, setTrackFilter] = useState<TrackFilter>("all");
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const { adminWorkflowTracks } = useAuth();
  const defaultTrack = adminWorkflowTracks.includes("seah") && !adminWorkflowTracks.includes("standard")
    ? "seah" as const : "standard" as const;

  // Track filter is single-sourced in lib/trackFilter.ts (RB-2 structural rule 1).
  const filtered = catalog.filter((r) => roleMatchesFilter(r.workflow, trackFilter));

  async function handleRemoveRole(r: RoleEntry) {
    if (!confirm(`Remove role "${r.label}" (${r.key}) from the catalog?`)) return;
    setDeleteError(null);
    try {
      await deleteRole(r.role_id);
      if (editing?.role_id === r.role_id) setEditing(null);
      onReload();
    } catch (e: unknown) {
      setDeleteError(friendlyError(e));
    }
  }

  const workflowBadge = (w: string) =>
    w === "SEAH"
      ? "bg-red-100 text-red-700"
      : w === "Both"
      ? "bg-violet-100 text-violet-700"
      : "bg-blue-100 text-blue-700";

  return (
    <div>
      {editing && (
        <RoleEditModal
          role={editing}
          onSaved={() => { onReload(); }}
          onClose={() => setEditing(null)}
        />
      )}
      {creating && (
        <RoleCreateModal
          defaultTrack={defaultTrack}
          onCreated={onReload}
          onClose={() => setCreating(false)}
        />
      )}

      <div className="flex items-center justify-between mb-5 gap-3 flex-wrap">
        <p className="text-sm text-gray-500">
          {loading ? "Loading roles…" : `${filtered.length} operational roles`}
        </p>
        <div className="flex items-center gap-2">
          <select value={trackFilter} onChange={(e) => setTrackFilter(e.target.value as typeof trackFilter)}
            className="text-xs border border-gray-300 rounded px-2 py-1">
            <option value="all">All tracks</option>
            <option value="standard">Standard</option>
            <option value="seah">SEAH</option>
          </select>
          {canCreate && (
            <button type="button" onClick={() => setCreating(true)}
              className="text-xs bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700">
              + New role
            </button>
          )}
          <button type="button" onClick={() => onReload()} className="text-xs text-blue-600 hover:underline">
            Refresh
          </button>
        </div>
      </div>

      {!loading && catalog.length === 0 && (
        <p className="text-sm text-gray-600 mb-3">
          No roles yet.{canCreate ? " Create the first role to get started." : ""}
        </p>
      )}

      {deleteError && <ErrorNotice error={deleteError} className="mb-3" />}

      <div className="border border-gray-200 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-700 text-slate-100 text-left">
              <th className="px-4 py-2.5 font-medium">Role</th>
              <th className="px-4 py-2.5 font-medium">Workflow</th>
              <th className="px-4 py-2.5 font-medium">Available in</th>
              <th className="px-4 py-2.5 font-medium">Usage</th>
              <th className="px-4 py-2.5 font-medium">Description</th>
              <th className="px-4 py-2.5 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
              <tr key={r.key} className="border-t border-gray-100 hover:bg-gray-50 align-top">
                <td className="px-4 py-3">
                  <div className="font-medium text-gray-800">{r.label}</div>
                  <div className="text-xs font-mono text-gray-400 mt-0.5">{r.key}</div>
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded ${workflowBadge(r.workflow)}`}>
                    {r.workflow}
                  </span>
                  {r.role_origin === "custom" && (
                    <span className="ml-1 text-[10px] text-gray-400">custom</span>
                  )}
                </td>
                <td className="px-4 py-3 text-xs whitespace-nowrap">
                  <span className={r.owner_organization_id ? "text-blue-700" : "text-gray-500"}>
                    {owningLevelLabel(r.owner_organization_id)}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                  {r.steps_count ?? 0} steps · {r.officers_count ?? 0} officers
                </td>
                <td className="px-4 py-3 text-gray-500 text-xs max-w-sm">{r.description}</td>
                <td className="px-4 py-3 whitespace-nowrap">
                  <button
                    type="button"
                    onClick={() => setEditing(r)}
                    className="text-blue-600 hover:underline text-xs mr-3"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => handleRemoveRole(r)}
                    className="text-red-600 hover:underline text-xs"
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-gray-400 mt-3">
        Operational catalog only — admin assignments live under Settings → Admin access.
        Organisation admins may create custom roles from &ldquo;acts as&rdquo; presets.
      </p>
    </div>
  );
}
