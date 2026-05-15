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
  type OfficerScope,
} from "@/lib/api";
import {
  OfficerJurisdictionFields,
  useOfficerJurisdictionState,
} from "@/components/settings/OfficerJurisdictionForm";

type RoleChoice = { key: string; label: string };

function scopeLabel(
  s: {
    organization_id: string;
    project_code?: string | null;
    package_id?: string | null;
    location_code?: string | null;
    includes_children?: boolean;
    role_key: string;
  },
  orgName?: string,
  packageCode?: string,
) {
  const parts = [
    orgName ?? s.organization_id,
    s.project_code ?? null,
    packageCode ?? (s.package_id ? "package" : null),
    s.location_code ?? null,
    s.includes_children ? "+sub-locations" : null,
  ].filter(Boolean);
  return `${parts.join(" · ")} (${s.role_key})`;
}

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
  const [savedScopes, setSavedScopes] = useState<OfficerScope[]>([]);
  const [pendingRemoves, setPendingRemoves] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [roleKey, setRoleKey] = useState(officer.role_keys[0] ?? "");
  const j = useOfficerJurisdictionState();

  const orgNameById = useMemo(
    () => Object.fromEntries(j.orgs.map((o) => [o.organization_id, o.name])),
    [j.orgs],
  );

  const hasFormDraft = Boolean(j.orgId && j.hasJurisdiction());

  const keptCount = savedScopes.filter((s) => !pendingRemoves.has(s.scope_id)).length;
  const totalAfterSave = keptCount + (hasFormDraft ? 1 : 0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setSavedScopes(await listScopes(officer.user_id));
      setPendingRemoves(new Set());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load scopes");
    } finally {
      setLoading(false);
    }
  }, [officer.user_id]);

  useEffect(() => {
    load();
  }, [load]);

  function toggleRemove(scopeId: string) {
    setPendingRemoves((prev) => {
      const next = new Set(prev);
      if (next.has(scopeId)) next.delete(scopeId);
      else next.add(scopeId);
      return next;
    });
  }

  async function handleSave() {
    setError(null);

    if (totalAfterSave === 0) {
      setError("Add at least one jurisdiction (project, package, or location) before saving.");
      return;
    }

    setSaving(true);
    try {
      for (const scopeId of pendingRemoves) {
        await deleteScope(officer.user_id, scopeId);
      }
      if (hasFormDraft) {
        const p = j.toPayload(roleKey);
        await addScope(officer.user_id, {
          role_key: p.role_key,
          organization_id: p.organization_id,
          location_code: p.location_code,
          project_id: p.project_id,
          package_id: p.package_id,
          includes_children: p.includes_children,
        });
      }
      const kept = savedScopes.filter((s) => !pendingRemoves.has(s.scope_id));
      const primaryOrg = hasFormDraft ? j.orgId : kept[0]?.organization_id ?? j.orgId;
      await updateOfficerKeycloak(officer.user_id, {
        role_keys: officer.role_keys,
        organization_id: primaryOrg,
        location_code: hasFormDraft ? j.selLoc?.code ?? null : kept[0]?.location_code ?? null,
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

  const draftProj = j.filteredProjects.find((p) => p.project_id === j.selProject);
  const draftPkg = j.filteredPackages.find((p) => p.package_id === j.selPkg);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden">
        <div className="bg-slate-700 text-white px-6 py-4 flex justify-between shrink-0">
          <div>
            <div className="font-semibold">Manage officer</div>
            <div className="text-xs text-slate-300 font-mono">{officer.email ?? officer.user_id}</div>
          </div>
          <button type="button" onClick={onClose} className="text-slate-300 hover:text-white text-xl">×</button>
        </div>

        <div className="p-6 overflow-y-auto space-y-5 flex-1">
          {loading ? (
            <p className="text-sm text-gray-400">Loading…</p>
          ) : (
            <>
              <section>
                <div className="flex items-baseline justify-between gap-2 mb-2">
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    Current scopes
                  </h3>
                  <span className="text-xs text-gray-400">
                    {totalAfterSave === 0 ? "None" : `${totalAfterSave} after save`}
                  </span>
                </div>

                {savedScopes.length === 0 && !hasFormDraft ? (
                  <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                    No scopes yet. Fill in jurisdiction below, then save.
                  </p>
                ) : (
                  <ul className="border border-gray-200 rounded-lg divide-y text-sm overflow-hidden">
                    {savedScopes.map((s) => {
                      const removed = pendingRemoves.has(s.scope_id);
                      return (
                        <li
                          key={s.scope_id}
                          className={`flex items-center justify-between gap-2 px-3 py-2.5 ${
                            removed ? "bg-red-50 line-through opacity-60" : "bg-white"
                          }`}
                        >
                          <span className="text-gray-800 min-w-0 truncate">
                            {scopeLabel(s, orgNameById[s.organization_id])}
                          </span>
                          <button
                            type="button"
                            onClick={() => toggleRemove(s.scope_id)}
                            className="text-xs text-red-600 hover:text-red-800 shrink-0 font-medium"
                          >
                            {removed ? "Undo" : "Remove"}
                          </button>
                        </li>
                      );
                    })}
                    {hasFormDraft && (
                      <li className="flex items-center gap-2 px-3 py-2.5 bg-emerald-50">
                        <span className="text-emerald-700 text-xs font-semibold shrink-0">+ New</span>
                        <span className="text-gray-800 min-w-0 truncate">
                          {scopeLabel(
                            {
                              organization_id: j.orgId,
                              project_code: draftProj?.short_code ?? null,
                              package_id: j.selPkg || null,
                              location_code: j.selLoc?.code ?? null,
                              includes_children: j.inclChildren,
                              role_key: roleKey,
                            },
                            orgNameById[j.orgId],
                            draftPkg?.package_code,
                          )}
                        </span>
                      </li>
                    )}
                  </ul>
                )}
              </section>

              <section className="border border-gray-200 rounded-lg p-4 bg-gray-50/80 space-y-3">
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  {keptCount === 0 && !hasFormDraft ? "Jurisdiction" : "Change or add jurisdiction"}
                </h3>
                <p className="text-xs text-gray-500 -mt-1">
                  Updates apply when you click <strong>Save changes</strong> — nothing is written until then.
                </p>
                <div>
                  <label className="text-xs font-medium text-gray-500 block mb-1">Role for this scope</label>
                  <select
                    value={roleKey}
                    onChange={(e) => setRoleKey(e.target.value)}
                    className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 bg-white"
                  >
                    {roleChoices.map((r) => (
                      <option key={r.key} value={r.key}>{r.label}</option>
                    ))}
                  </select>
                </div>
                <OfficerJurisdictionFields {...j} />
              </section>
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
                disabled={saving || loading || totalAfterSave === 0}
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
