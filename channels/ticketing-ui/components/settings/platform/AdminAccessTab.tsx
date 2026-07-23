"use client";

/**
 * <AdminAccessTab> — Settings → Platform → Admin access (super_admin only).
 *
 * Appoints scoped org/project administrators on the SH-7 4-tier ladder
 * (org_admin / project_admin / officer_admin; country_admin retired) and drives the
 * Keycloak setup-email + resend-invite flow.
 *
 * Extracted verbatim from `app/settings/page.tsx` (T3-05) — no behaviour change.
 */
import React, { useState, useEffect, useCallback } from "react";
import {
  listAdminScopes,
  createAdminScope,
  deleteAdminScope,
  sendAdminScopeInvite,
  type AdminScopeRow,
} from "@/lib/api";
import { friendlyError } from "@/components/settings/lib/friendlyError";

export function AdminAccessTab() {
  const [rows, setRows] = useState<AdminScopeRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [userId, setUserId] = useState("");
  // SH-7: country_admin retired → org_admin (org-subtree, any depth). 4-tier ladder.
  const [roleKey, setRoleKey] = useState<"org_admin" | "project_admin" | "officer_admin">("org_admin");
  const [countryCode, setCountryCode] = useState("NP");
  const [projectId, setProjectId] = useState("KL_ROAD");
  const [track, setTrack] = useState<"standard" | "seah">("standard");
  const [countryTracks, setCountryTracks] = useState({ standard: true, seah: false });
  const [resendingId, setResendingId] = useState<string | null>(null);
  const [resendMsg, setResendMsg] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await listAdminScopes());
      setErr("");
    } catch (e: unknown) {
      setErr(friendlyError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleAppoint() {
    if (!userId.trim()) return;
    setResendMsg("");
    const workflow_tracks: ("standard" | "seah")[] =
      roleKey === "org_admin"
        ? (["standard", "seah"] as const).filter((t) => countryTracks[t])
        : [track];
    if (workflow_tracks.length === 0) {
      setErr("Select at least one workflow track.");
      return;
    }
    try {
      const created = await createAdminScope({
        user_id: userId.trim(),
        role_key: roleKey,
        // org_admin: country-wide subtree (country_code, NULL org). project/officer admin: project-scoped.
        country_code: roleKey === "org_admin" ? countryCode : undefined,
        project_id: roleKey === "org_admin" ? undefined : projectId,
        workflow_tracks,
      });
      setUserId("");
      if (created.invite_email_sent) {
        setResendMsg(
          `Setup email sent to ${created.user_id}. They can use Resend invite if it does not arrive.`,
        );
      } else if (created.onboarding_status === "active") {
        setResendMsg(`${created.user_id} already has an active Keycloak account — no invite email sent.`);
      }
      await load();
    } catch (e: unknown) {
      setErr(friendlyError(e));
    }
  }

  async function handleRevoke(id: string) {
    if (!confirm("Revoke this admin assignment?")) return;
    try {
      await deleteAdminScope(id);
      await load();
    } catch (e: unknown) {
      setErr(friendlyError(e));
    }
  }

  async function handleSendSetupEmail(adminScopeId: string, email: string) {
    setResendingId(email);
    setResendMsg("");
    setErr("");
    try {
      const result = await sendAdminScopeInvite(adminScopeId);
      if (result.invite_email_sent) {
        setResendMsg(`Setup email sent to ${result.user_id}.`);
      } else {
        setResendMsg(`${result.user_id} already has an active Keycloak account.`);
      }
      await load();
    } catch (e: unknown) {
      setErr(friendlyError(e));
    } finally {
      setResendingId(null);
    }
  }

  return (
    <div>
      <p className="text-sm text-gray-500 mb-4">
        Appoint scoped organisation and project administrators. For <span className="font-medium">org_admin</span>,
        you may assign Standard, SEAH, or both tracks (two scope rows). New officers receive a Keycloak setup email;
        use <span className="font-medium">Send setup email</span> if it does not arrive.
      </p>
      {err && <p className="text-sm text-red-600 mb-3">{err}</p>}
      {resendMsg && <p className="text-sm text-green-700 mb-3">{resendMsg}</p>}
      <div className="border border-gray-200 rounded-lg p-4 mb-5 bg-gray-50 space-y-3 text-sm">
        <div className="font-medium text-gray-700">+ Appoint admin</div>
        <div className="grid grid-cols-2 gap-3">
          <input value={userId} onChange={(e) => setUserId(e.target.value)} placeholder="Officer email"
            className="border border-gray-300 rounded px-2 py-1.5 col-span-2" />
          <select value={roleKey} onChange={(e) => setRoleKey(e.target.value as typeof roleKey)}
            className="border border-gray-300 rounded px-2 py-1.5">
            <option value="org_admin">org_admin</option>
            <option value="project_admin">project_admin</option>
            <option value="officer_admin">officer_admin</option>
          </select>
          {roleKey === "org_admin" ? (
            <div className="flex items-center gap-4 px-1">
              <label className="flex items-center gap-1.5 text-xs text-gray-700">
                <input
                  type="checkbox"
                  checked={countryTracks.standard}
                  onChange={(e) => setCountryTracks((t) => ({ ...t, standard: e.target.checked }))}
                />
                Standard
              </label>
              <label className="flex items-center gap-1.5 text-xs text-gray-700">
                <input
                  type="checkbox"
                  checked={countryTracks.seah}
                  onChange={(e) => setCountryTracks((t) => ({ ...t, seah: e.target.checked }))}
                />
                SEAH
              </label>
            </div>
          ) : (
            <select value={track} onChange={(e) => setTrack(e.target.value as typeof track)}
              className="border border-gray-300 rounded px-2 py-1.5">
              <option value="standard">standard</option>
              <option value="seah">seah</option>
            </select>
          )}
          {roleKey === "org_admin" ? (
            <input value={countryCode} onChange={(e) => setCountryCode(e.target.value)} placeholder="Country code"
              className="border border-gray-300 rounded px-2 py-1.5" />
          ) : (
            <input value={projectId} onChange={(e) => setProjectId(e.target.value)} placeholder="Project (e.g. KL_ROAD)"
              className="border border-gray-300 rounded px-2 py-1.5" />
          )}
        </div>
        <button type="button" onClick={handleAppoint}
          className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700">
          Appoint
        </button>
      </div>
      {loading ? (
        <p className="text-sm text-gray-500">Loading…</p>
      ) : (
        <table className="w-full text-sm border border-gray-200 rounded-lg overflow-hidden">
          <thead>
            <tr className="bg-slate-700 text-slate-100 text-left">
              <th className="px-3 py-2">User</th>
              <th className="px-3 py-2">Role</th>
              <th className="px-3 py-2">Scope</th>
              <th className="px-3 py-2">Track</th>
              <th className="px-3 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.admin_scope_id} className="border-t border-gray-100">
                <td className="px-3 py-2 font-mono text-xs">{r.user_id}</td>
                <td className="px-3 py-2">{r.role_key}</td>
                <td className="px-3 py-2 text-xs">{r.country_code ?? r.project_id ?? "—"}</td>
                <td className="px-3 py-2">{r.workflow_track}</td>
                <td className="px-3 py-2 whitespace-nowrap space-x-3">
                  {r.can_send_setup_email && (
                    <button
                      type="button"
                      onClick={() => handleSendSetupEmail(r.admin_scope_id, r.user_id)}
                      disabled={resendingId === r.user_id}
                      className="text-amber-800 text-xs hover:underline disabled:opacity-50"
                      title="Send Keycloak password setup email (7-day link)"
                    >
                      {resendingId === r.user_id
                        ? "Sending…"
                        : r.can_resend_invite
                          ? "Resend invite"
                          : "Send setup email"}
                    </button>
                  )}
                  <button type="button" onClick={() => handleRevoke(r.admin_scope_id)}
                    className="text-red-600 text-xs hover:underline">Revoke</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
