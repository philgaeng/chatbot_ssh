"use client";

import React, { useCallback, useEffect, useState } from "react";
import { X } from "lucide-react";
import {
  addScope,
  deleteOfficer,
  deleteScope,
  inviteOfficer,
  listScopes,
  updateOfficerKeycloak,
  type OfficerRosterEntry,
  type OfficerScope,
} from "@/lib/api";
import {
  OfficerJurisdictionFields,
  useOfficerJurisdictionState,
} from "@/components/settings/OfficerJurisdictionForm";

type RoleChoice = { key: string; label: string };

export function InviteOfficerModal({
  roleChoices,
  onClose,
  onSuccess,
}: {
  roleChoices: RoleChoice[];
  onClose: () => void;
  onSuccess: (email: string) => void;
}) {
  const [email, setEmail] = useState("");
  const [roleKey, setRoleKey] = useState(roleChoices[0]?.key ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const j = useOfficerJurisdictionState();

  useEffect(() => {
    if (roleChoices.length && !roleChoices.some((r) => r.key === roleKey)) {
      setRoleKey(roleChoices[0].key);
    }
  }, [roleChoices, roleKey]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim() || !j.orgId) {
      setError("Email and organization are required.");
      return;
    }
    if (!j.hasJurisdiction()) {
      setError("Select at least one of project, package, or location.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const p = j.toPayload(roleKey);
      await inviteOfficer({
        email: email.trim(),
        role_key: p.role_key,
        organization_id: p.organization_id,
        location_code: p.location_code,
        project_id: p.project_id,
        package_id: p.package_id,
        includes_children: p.includes_children,
      });
      onSuccess(email.trim());
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg.includes("409") ? `${email} already exists.` : msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 overflow-hidden">
        <div className="bg-slate-700 text-white px-6 py-4 flex items-center justify-between">
          <div className="font-semibold">Invite Officer</div>
          <button type="button" onClick={onClose} className="text-slate-300 hover:text-white text-xl">×</button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Email address *</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="officer@example.com"
              className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Role *</label>
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
          <OfficerJurisdictionFields {...j} />
          <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded px-3 py-2">
            Temporary password via Keycloak when auth stack is running; demo mode creates DB roster only.
          </p>
          {error && <p className="text-xs text-red-500">{error}</p>}
          <div className="flex justify-end gap-3 pt-1">
            <button type="button" onClick={onClose} className="text-sm text-gray-500 px-4 py-1.5">Cancel</button>
            <button
              type="submit"
              disabled={submitting}
              className="text-sm bg-blue-600 text-white px-4 py-1.5 rounded font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {submitting ? "Inviting…" : "Send invite"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function EditOfficerModal({
  officer,
  roleChoices,
  onClose,
  onSaved,
}: {
  officer: OfficerRosterEntry;
  roleChoices: RoleChoice[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [scopes, setScopes] = useState<OfficerScope[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [roleKey, setRoleKey] = useState(officer.role_keys[0] ?? "");
  const j = useOfficerJurisdictionState();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setScopes(await listScopes(officer.user_id));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load scopes");
    } finally {
      setLoading(false);
    }
  }, [officer.user_id]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleAddScope() {
    if (!j.hasJurisdiction() || !j.orgId) {
      setError("Organization and at least one of project, package, or location required.");
      return;
    }
    setError(null);
    try {
      const p = j.toPayload(roleKey);
      const created = await addScope(officer.user_id, {
        role_key: p.role_key,
        organization_id: p.organization_id,
        location_code: p.location_code,
        project_id: p.project_id,
        package_id: p.package_id,
        includes_children: p.includes_children,
      });
      setScopes((prev) => [...prev, created]);
      j.reset();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to add scope");
    }
  }

  async function handleRemoveScope(scopeId: string) {
    try {
      await deleteScope(officer.user_id, scopeId);
      setScopes((prev) => prev.filter((s) => s.scope_id !== scopeId));
    } catch {
      setError("Failed to remove scope");
    }
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      await updateOfficerKeycloak(officer.user_id, {
        role_keys: officer.role_keys,
        organization_id: officer.organization_ids[0] ?? j.orgId,
        location_code: officer.location_codes[0] ?? null,
        sync_keycloak: true,
      });
      onSaved();
      onClose();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteOfficer() {
    if (!confirm(`Remove officer ${officer.display_name} completely?`)) return;
    try {
      await deleteOfficer(officer.user_id);
      onSaved();
      onClose();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden">
        <div className="bg-slate-700 text-white px-6 py-4 flex justify-between shrink-0">
          <div>
            <div className="font-semibold">Edit Officer</div>
            <div className="text-xs text-slate-300 font-mono">{officer.email ?? officer.user_id}</div>
          </div>
          <button type="button" onClick={onClose} className="text-slate-300 hover:text-white text-xl">×</button>
        </div>
        <div className="p-6 overflow-y-auto space-y-4 flex-1">
          {loading ? (
            <p className="text-sm text-gray-400">Loading…</p>
          ) : (
            <>
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Jurisdiction scopes</p>
                {scopes.length === 0 ? (
                  <p className="text-xs text-amber-600">No scopes — officer will not receive auto-assigned tickets.</p>
                ) : (
                  <ul className="text-xs space-y-0 border border-gray-200 rounded divide-y max-h-40 overflow-y-auto">
                    {scopes.map((s) => (
                      <li key={s.scope_id} className="flex items-center justify-between px-3 py-2">
                        <span className="text-gray-700 pr-2">
                          {s.organization_id}
                          {s.project_code ? ` · ${s.project_code}` : ""}
                          {s.package_id ? ` · pkg` : ""}
                          {s.location_code ? ` · ${s.location_code}` : ""}
                          {s.includes_children ? " (+sub)" : ""}
                          <span className="text-gray-400 ml-1">({s.role_key})</span>
                        </span>
                        <button
                          type="button"
                          onClick={() => handleRemoveScope(s.scope_id)}
                          className="text-red-500 hover:text-red-700 shrink-0"
                          aria-label="Remove scope"
                        >
                          <X size={14} />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div className="border-t pt-4">
                <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Add scope</p>
                <select
                  value={roleKey}
                  onChange={(e) => setRoleKey(e.target.value)}
                  className="w-full text-sm border border-gray-300 rounded px-2 py-1 mb-2"
                >
                  {roleChoices.map((r) => (
                    <option key={r.key} value={r.key}>{r.label}</option>
                  ))}
                </select>
                <OfficerJurisdictionFields {...j} />
                <button
                  type="button"
                  onClick={handleAddScope}
                  className="mt-2 text-xs bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700"
                >
                  Add scope
                </button>
              </div>
            </>
          )}
          {error && <p className="text-xs text-red-500">{error}</p>}
        </div>
        <div className="px-6 py-4 border-t flex justify-between shrink-0 bg-gray-50">
          <button type="button" onClick={handleDeleteOfficer} className="text-sm text-red-600 hover:text-red-800">
            Delete officer
          </button>
          <div className="flex gap-2">
            <button type="button" onClick={onClose} className="text-sm text-gray-500 px-4 py-1.5">Cancel</button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="text-sm bg-blue-600 text-white px-4 py-1.5 rounded font-medium disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save & sync Keycloak"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
