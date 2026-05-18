"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  addScope,
  inviteOfficer,
  listOfficerRoster,
  type OfficerRosterEntry,
  type ProjectItem,
} from "@/lib/api";
import {
  OfficerJurisdictionFields,
  useOfficerJurisdictionState,
} from "@/components/settings/OfficerJurisdictionForm";

type RoleChoice = { key: string; label: string };

export function ProjectOfficerModal({
  project,
  organizationId,
  organizationName,
  roleChoices,
  onClose,
  onSuccess,
}: {
  project: ProjectItem;
  organizationId: string;
  organizationName?: string;
  roleChoices: RoleChoice[];
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [mode, setMode] = useState<"invite" | "existing">("invite");
  const [email, setEmail] = useState("");
  const [roleKey, setRoleKey] = useState(roleChoices[0]?.key ?? "");
  const [roster, setRoster] = useState<OfficerRosterEntry[]>([]);
  const [existingUserId, setExistingUserId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const j = useOfficerJurisdictionState({
    organizationId,
    projectId: project.project_id,
    lockOrganization: true,
    lockProject: true,
  });

  useEffect(() => {
    if (roleChoices.length && !roleChoices.some((r) => r.key === roleKey)) {
      setRoleKey(roleChoices[0].key);
    }
  }, [roleChoices, roleKey]);

  useEffect(() => {
    listOfficerRoster()
      .then(setRoster)
      .catch(() => setRoster([]));
  }, []);

  const rosterForOrg = useMemo(
    () => roster.filter((o) => o.organization_ids.includes(organizationId)),
    [roster, organizationId],
  );

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!j.hasJurisdiction()) {
      setError("Select at least one of package or location for this officer.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const p = j.toPayload(roleKey);
      if (mode === "invite") {
        if (!email.trim()) {
          setError("Email is required.");
          setSubmitting(false);
          return;
        }
        await inviteOfficer({
          email: email.trim(),
          role_key: p.role_key,
          organization_id: p.organization_id,
          location_code: p.location_code,
          project_id: p.project_id,
          package_id: p.package_id,
          includes_children: p.includes_children,
        });
      } else {
        if (!existingUserId) {
          setError("Select an officer.");
          setSubmitting(false);
          return;
        }
        await addScope(existingUserId, {
          role_key: p.role_key,
          organization_id: p.organization_id,
          location_code: p.location_code,
          project_id: p.project_id,
          package_id: p.package_id,
          includes_children: p.includes_children,
        });
      }
      onSuccess();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setSubmitting(false);
    }
  }

  const orgLabel = organizationName ?? organizationId;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg overflow-hidden">
        <div className="bg-slate-700 text-white px-6 py-4 flex items-center justify-between">
          <div>
            <div className="font-semibold">Add officer</div>
            <div className="text-xs text-slate-300 mt-0.5">
              {orgLabel} · {project.short_code}
            </div>
          </div>
          <button type="button" onClick={onClose} className="text-slate-300 hover:text-white text-xl">×</button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div className="flex gap-2 text-sm">
            <button
              type="button"
              onClick={() => setMode("invite")}
              className={`px-3 py-1 rounded border ${mode === "invite" ? "bg-blue-50 border-blue-300 text-blue-700" : "border-gray-200 text-gray-600"}`}
            >
              Invite new
            </button>
            <button
              type="button"
              onClick={() => setMode("existing")}
              className={`px-3 py-1 rounded border ${mode === "existing" ? "bg-blue-50 border-blue-300 text-blue-700" : "border-gray-200 text-gray-600"}`}
            >
              Existing officer
            </button>
          </div>

          {mode === "invite" ? (
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">Email *</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full text-sm border border-gray-300 rounded px-3 py-1.5"
              />
            </div>
          ) : (
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">Officer *</label>
              <select
                value={existingUserId}
                onChange={(e) => setExistingUserId(e.target.value)}
                className="w-full text-sm border border-gray-300 rounded px-3 py-1.5"
              >
                <option value="">— select —</option>
                {rosterForOrg.map((o) => (
                  <option key={o.user_id} value={o.user_id}>
                    {o.display_name} ({o.email ?? o.user_id})
                  </option>
                ))}
              </select>
              {rosterForOrg.length === 0 && (
                <p className="text-xs text-gray-400 mt-1">No roster entries for this org yet — use Invite new.</p>
              )}
            </div>
          )}

          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">GRM role *</label>
            <select
              value={roleKey}
              onChange={(e) => setRoleKey(e.target.value)}
              className="w-full text-sm border border-gray-300 rounded px-3 py-1.5"
            >
              {roleChoices.map((r) => (
                <option key={r.key} value={r.key}>{r.label}</option>
              ))}
            </select>
          </div>

          <OfficerJurisdictionFields {...j} lockOrganization lockProject />

          {error && <p className="text-xs text-red-500">{error}</p>}
          <div className="flex justify-end gap-3 pt-1">
            <button type="button" onClick={onClose} className="text-sm text-gray-500 px-4 py-1.5">Cancel</button>
            <button
              type="submit"
              disabled={submitting}
              className="text-sm bg-blue-600 text-white px-4 py-1.5 rounded font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {submitting ? "Saving…" : mode === "invite" ? "Send invite" : "Add scope"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
