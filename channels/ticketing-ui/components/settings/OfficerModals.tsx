"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  addScope,
  deleteOfficer,
  deleteScope,
  inviteOfficer,
  listScopes,
  updateOfficerKeycloak,
  type OfficerRosterEntry,
} from "@/lib/api";
import {
  OfficerJurisdictionFields,
  useOfficerJurisdictionState,
} from "@/components/settings/OfficerJurisdictionForm";
import {
  activeScopeRows,
  OfficerScopeTable,
  scopeRowsToCreate,
  scopeRowsToDelete,
  scopeToDraftRow,
  type ScopeDraftRow,
} from "@/components/settings/OfficerScopeTable";

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
  const j = useOfficerJurisdictionState({ fieldOrder: "project-first" }, roleKey);

  useEffect(() => {
    if (roleChoices.length && !roleChoices.some((r) => r.key === roleKey)) {
      setRoleKey(roleChoices[0].key);
    }
  }, [roleChoices, roleKey]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim() || !j.orgId || !j.selProject) {
      setError("Email, project, and organization are required.");
      return;
    }
    if (!j.hasJurisdiction()) {
      setError(
        j.countryRole
          ? "Select an organization (country-wide), or narrow with project, package, or location."
          : "Select at least one of project, package, or location.",
      );
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const payloads = j.toPayloads(roleKey);
      if (payloads.length === 0) {
        setError("Select at least one of project, package, or location.");
        setSubmitting(false);
        return;
      }
      const [first, ...rest] = payloads;
      await inviteOfficer({
        email: email.trim(),
        role_key: first.role_key,
        organization_id: first.organization_id,
        location_code: first.location_code,
        project_id: first.project_id,
        package_id: first.package_id,
        includes_children: first.includes_children,
      });
      for (const p of rest) {
        await addScope(email.trim(), {
          role_key: p.role_key,
          organization_id: p.organization_id,
          location_code: p.location_code,
          project_id: p.project_id,
          package_id: p.package_id,
          includes_children: p.includes_children,
        });
      }
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
  const [rows, setRows] = useState<ScopeDraftRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [rowEditing, setRowEditing] = useState(false);
  const defaultRoleKey = officer.role_keys[0] ?? roleChoices[0]?.key ?? "";

  const officerOrgId = useMemo(() => {
    if (officer.organization_ids.length >= 1) return officer.organization_ids[0];
    const active = activeScopeRows(rows);
    const fromScopes = [...new Set(active.map((s) => s.organization_id))];
    return fromScopes[0] ?? "";
  }, [officer.organization_ids, rows]);

  const officerHasMultipleOrgs =
    officer.organization_ids.length > 1 ||
    new Set(activeScopeRows(rows).map((s) => s.organization_id)).size > 1;

  const activeRows = activeScopeRows(rows);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const scopes = await listScopes(officer.user_id);
      setRows(scopes.map(scopeToDraftRow));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load scopes");
    } finally {
      setLoading(false);
    }
  }, [officer.user_id]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleSave() {
    setError(null);

    if (rowEditing) {
      setError("Finish or cancel the scope row you are editing before saving.");
      return;
    }

    if (activeRows.length === 0) {
      setError("Add at least one scope before saving.");
      return;
    }

    const keptForeignOrg = activeRows.filter(
      (s) => officerOrgId && s.organization_id !== officerOrgId,
    );
    if (keptForeignOrg.length > 0) {
      setError("Remove scopes from other organizations before saving.");
      return;
    }

    setSaving(true);
    try {
      for (const scopeId of scopeRowsToDelete(rows)) {
        await deleteScope(officer.user_id, scopeId);
      }
      for (const row of scopeRowsToCreate(rows)) {
        await addScope(officer.user_id, {
          role_key: row.role_key,
          organization_id: row.organization_id,
          location_code: row.location_code,
          project_id: row.project_id,
          package_id: row.package_id,
          includes_children: row.includes_children,
        });
      }
      const primaryOrg = officerOrgId || activeRows[0]?.organization_id || "";
      await updateOfficerKeycloak(officer.user_id, {
        role_keys: officer.role_keys,
        organization_id: primaryOrg,
        location_code: activeRows[0]?.location_code ?? null,
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
      <div className="bg-white rounded-xl shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden">
        <div className="bg-slate-700 text-white px-6 py-4 flex justify-between shrink-0">
          <div>
            <div className="font-semibold">Manage officer</div>
            <div className="text-xs text-slate-300 font-mono">{officer.email ?? officer.user_id}</div>
          </div>
          <button type="button" onClick={onClose} className="text-slate-300 hover:text-white text-xl">×</button>
        </div>

        <div className="p-6 overflow-y-auto space-y-4 flex-1">
          {loading ? (
            <p className="text-sm text-gray-400">Loading…</p>
          ) : (
            <>
              {officerHasMultipleOrgs && (
                <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                  This officer has scopes in more than one organization. Each officer belongs to one organization
                  only — delete scopes from other organizations before saving.
                </p>
              )}
              <p className="text-xs text-gray-500">
                Each row is one jurisdiction scope. Edit or delete a row inline, or add a new row. Changes apply when
                you click <strong>Save changes</strong>.
              </p>
              <OfficerScopeTable
                rows={rows}
                onChange={setRows}
                roleChoices={roleChoices}
                officerOrgId={officerOrgId}
                defaultRoleKey={defaultRoleKey}
                onEditingChange={setRowEditing}
              />
            </>
          )}
          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>
          )}
        </div>

        <div className="px-6 py-4 border-t shrink-0 bg-gray-50">
          <div className="flex justify-between items-center gap-3">
            <button
              type="button"
              onClick={handleDeleteOfficer}
              className="text-sm text-red-600 hover:text-red-800 font-medium"
            >
              Delete officer
            </button>
            <div className="flex gap-2">
              <button type="button" onClick={onClose} className="text-sm text-gray-600 px-4 py-2">
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={saving || loading || activeRows.length === 0}
                className="text-sm bg-blue-600 text-white px-5 py-2.5 rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50 min-w-[9rem]"
              >
                {saving ? "Saving…" : "Save changes"}
              </button>
            </div>
          </div>
          <p className="text-xs text-gray-400 text-center mt-3">
            Applies scope changes and syncs Keycloak on the auth stack.
          </p>
        </div>
      </div>
    </div>
  );
}
