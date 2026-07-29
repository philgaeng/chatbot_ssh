"use client";

/**
 * <OfficersDirectory> — officer roster + lifecycle at scale (DESIGN §7.F / build sheet frame-11).
 *
 * Search-first directory. A dual-hat officer (multiple active positions, doc 16 §3.3) shows
 * one row per position (§5.1, pin 46). Office / position names via <Bilingual>. A ⋯ menu
 * exposes Manage (identity, positions, wired resend + end-position) and Deactivate.
 *
 * SCOPE NOTES (honest about backend gaps flagged in frame-11 §4/§6):
 *   • Search + filters run CLIENT-side on the full `listOfficerRoster()` payload.
 *     TODO: swap to server-side search/filter/pagination when the paged roster wrapper lands.
 *   • There is no soft-"deactivate" endpoint (only a hard `deleteOfficer`, which frame-11 §6
 *     flags as orphaning tickets with no open-case guard). Deactivate is therefore rendered
 *     DISABLED with a "backend pending" tooltip until §7.F1 (history-preserving deactivate +
 *     open-case guard) ships. It is deliberately NOT wired to the hard delete.
 */

import { useEffect, useMemo, useState } from "react";
import { MoreHorizontal, Search, X } from "lucide-react";

import {
  listOfficerRoster,
  listRoles,
  listOrganizations,
  listProjects,
  getAdminContext,
  listOfficerPositions,
  endOfficerPosition,
  resendOfficerInvite,
  deactivateOfficer,
  reactivateOfficer,
  type OfficerRosterEntry,
  type GrmRole,
  type OrganizationItem,
  type ProjectItem,
  type AdminContext,
  type OfficerPositionItem,
} from "@/lib/api";
import { Bilingual } from "@/components/shared/Bilingual";
import { SeverityBadge } from "@/components/shared/SeverityBadge";
import { ErrorNotice } from "@/components/shared/ErrorNotice";
import { primary, text as textTokens } from "@/lib/design-tokens";
import { prettyLocation } from "@/lib/prettyLocation";

const BTN_GHOST =
  "inline-flex items-center gap-1.5 rounded border border-gray-300 px-2.5 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50";
type TrackFilterValue = "all" | "standard" | "seah";

interface FlatRow {
  officer: OfficerRosterEntry;
  position: string | null;
  isFirst: boolean;
}

export function OfficersDirectory({ canManage }: { canManage: boolean }) {
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<unknown>(null);

  const [roster, setRoster] = useState<OfficerRosterEntry[]>([]);
  const [roles, setRoles] = useState<GrmRole[]>([]);
  const [orgs, setOrgs] = useState<OrganizationItem[]>([]);
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [ctx, setCtx] = useState<AdminContext | null>(null);

  const [q, setQ] = useState("");
  const [trackFilter, setTrackFilter] = useState<TrackFilterValue>("all");

  const [menuFor, setMenuFor] = useState<string | null>(null);
  const [manageOfficer, setManageOfficer] = useState<OfficerRosterEntry | null>(null);
  const [lifecycleMsg, setLifecycleMsg] = useState<string>("");   // success only (blue notice)
  const [lifecycleErr, setLifecycleErr] = useState<unknown>(null); // failure → <ErrorNotice>

  // Frame-11: history-preserving deactivate with the open-case guard (backend shipped).
  // R5 (BUILD-REVIEW M3b/FE-2#3): errors go through <ErrorNotice> (formatUserFacingError
  // unwraps the 409 {message, open_count} → friendly copy), so no raw "API 500 …" in a blue
  // box, and no redundant getOfficerOpenCases round-trip.
  async function handleDeactivate(o: OfficerRosterEntry) {
    setMenuFor(null);
    setLifecycleMsg("");
    setLifecycleErr(null);
    if (!confirm(`Deactivate ${o.email ?? o.user_id}? They keep their history but lose access until reactivated.`)) return;
    try {
      await deactivateOfficer(o.user_id);
      setLifecycleMsg(`${o.email ?? o.user_id} was deactivated.`);
      void reload();
    } catch (e: unknown) {
      setLifecycleErr(e);
    }
  }

  async function handleReactivate(o: OfficerRosterEntry) {
    setMenuFor(null);
    setLifecycleMsg("");
    setLifecycleErr(null);
    try {
      await reactivateOfficer(o.user_id);
      setLifecycleMsg(`${o.email ?? o.user_id} was reactivated.`);
      void reload();
    } catch (e: unknown) {
      setLifecycleErr(e);
    }
  }

  async function reload() {
    try {
      setLoading(true);
      const [ro, r, o, pr, ac] = await Promise.all([
        listOfficerRoster(),
        listRoles({ kind: "operational" }).catch(() => [] as GrmRole[]),
        listOrganizations().catch(() => [] as OrganizationItem[]),
        listProjects(undefined, false).catch(() => [] as ProjectItem[]),
        getAdminContext().catch(() => null),
      ]);
      setRoster(ro);
      setRoles(r);
      setOrgs(o);
      setProjects(pr);
      setCtx(ac);
    } catch (e) {
      setLoadError(e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
  }, []);

  const orgById = useMemo(() => new Map(orgs.map((o) => [o.organization_id, o])), [orgs]);
  const projectByCode = useMemo(
    () => new Map(projects.map((p) => [p.short_code, p])),
    [projects],
  );
  // SEAH classification is derived from role_keys internally (not shown to users) so the
  // Standard/SEAH track filter keeps working.
  const seahRoleKeys = useMemo(
    () => new Set(roles.filter((r) => (r.workflow_scope ?? "") === "SEAH").map((r) => r.role_key)),
    [roles],
  );
  const seahCapable = !!ctx && (ctx.is_super_admin || ctx.admin_workflow_tracks.includes("seah"));

  const officerIsSeah = (o: OfficerRosterEntry) =>
    o.role_keys.some((rk) => seahRoleKeys.has(rk)) ||
    (o.scopes ?? []).some((s) => seahRoleKeys.has(s.role_key));

  const filteredOfficers = useMemo(() => {
    const term = q.trim().toLowerCase();
    return roster.filter((o) => {
      if (trackFilter === "seah" && !officerIsSeah(o)) return false;
      if (trackFilter === "standard" && officerIsSeah(o) && o.role_keys.every((rk) => seahRoleKeys.has(rk)))
        return false;
      if (!term) return true;
      const haystack = [o.display_name, o.email ?? "", ...(o.positions ?? [])]
        .join(" ")
        .toLowerCase();
      return haystack.includes(term);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roster, q, trackFilter, seahRoleKeys]);

  // Dual-hat: one row per active position; fall back to a single row for legacy no-position officers.
  const rows: FlatRow[] = useMemo(() => {
    const out: FlatRow[] = [];
    for (const officer of filteredOfficers) {
      const positions = officer.positions ?? [];
      if (positions.length === 0) {
        out.push({ officer, position: null, isFirst: true });
      } else {
        positions.forEach((position, i) => {
          out.push({ officer, position, isFirst: i === 0 });
        });
      }
    }
    return out;
  }, [filteredOfficers]);

  function officeCell(o: OfficerRosterEntry) {
    const first = o.organization_ids[0];
    const org = first ? orgById.get(first) : null;
    if (!org) return <span className={textTokens.muted}>—</span>;
    return (
      <>
        <Bilingual en={org.name} ne={org.display_name_ne} mode="active" />
        {o.organization_ids.length > 1 ? (
          <span className={`ml-1 text-xs ${textTokens.muted}`}>+{o.organization_ids.length - 1}</span>
        ) : null}
      </>
    );
  }

  function projectAreaCell(o: OfficerRosterEntry) {
    const codes = o.project_codes ?? [];
    const names = codes.map((c) => projectByCode.get(c)?.name ?? c);
    const locs = [
      ...new Set(
        ((o.scopes ?? []).map((s) => s.location_code).filter(Boolean) as string[]).concat(
          o.location_codes,
        ),
      ),
    ].map(prettyLocation);
    if (names.length === 0 && locs.length === 0) return <span className={textTokens.muted}>—</span>;
    return (
      <div className="text-xs leading-snug">
        {names.length > 0 ? <div className="text-gray-700">{names.join(", ")}</div> : null}
        {locs.length > 0 ? <div className={textTokens.secondary}>{locs.slice(0, 4).join(", ")}</div> : null}
      </div>
    );
  }

  if (loading) {
    return (
      <div className="space-y-2" aria-busy="true">
        <div className="h-9 w-full animate-pulse rounded bg-gray-100" />
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-11 w-full animate-pulse rounded bg-gray-50" />
        ))}
      </div>
    );
  }

  if (loadError) {
    return <ErrorNotice error={loadError} />;
  }

  return (
    <div className="space-y-3">
      {lifecycleMsg && (
        <div className="rounded border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-800">
          {lifecycleMsg}
        </div>
      )}
      <ErrorNotice error={lifecycleErr} />
      {/* Search + filters (client-side for now — see file header TODO) */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex min-w-[16rem] flex-1 items-center gap-1.5 rounded border border-gray-300 bg-white px-2.5 py-1.5">
          <Search size={15} className="text-gray-400" aria-hidden />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search name, email, or position…"
            className="w-full text-sm outline-none"
          />
        </div>
        {seahCapable ? (
          <div className="inline-flex overflow-hidden rounded border border-gray-300 text-sm">
            {(["all", "standard", "seah"] as TrackFilterValue[]).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTrackFilter(t)}
                className={`px-2.5 py-1.5 ${
                  trackFilter === t ? `${primary.bg} text-white` : "bg-white text-gray-700 hover:bg-gray-50"
                }`}
              >
                {t === "all" ? "All" : t === "standard" ? "Standard" : "SEAH"}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      <p className={`text-xs ${textTokens.muted}`}>
        Showing {rows.length} {rows.length === 1 ? "position" : "positions"} across{" "}
        {filteredOfficers.length} {filteredOfficers.length === 1 ? "officer" : "officers"}.
      </p>

      {rows.length === 0 ? (
        <p className={`rounded border border-gray-200 bg-gray-50 px-3 py-6 text-center text-sm ${textTokens.secondary}`}>
          No officers match{q.trim() ? ` “${q.trim()}”` : ""}.
        </p>
      ) : (
        <div className="overflow-x-auto rounded border border-gray-200">
          <table className="w-full min-w-[52rem] text-left text-sm">
            <thead>
              <tr className={`border-b border-gray-200 bg-gray-50 text-xs ${textTokens.secondary}`}>
                <th className="px-3 py-2 font-medium">Officer</th>
                <th className="px-3 py-2 font-medium">Position</th>
                <th className="px-3 py-2 font-medium">Office</th>
                <th className="px-3 py-2 font-medium">Project / area</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium" />
              </tr>
            </thead>
            <tbody>
              {rows.map((row, idx) => {
                const o = row.officer;
                const invited = (o.onboarding_status ?? "active") === "invited";
                return (
                  <tr
                    key={`${o.user_id}-${row.position ?? "none"}-${idx}`}
                    className="border-t border-gray-100 align-top hover:bg-gray-50"
                  >
                    <td className="px-3 py-2.5">
                      {row.isFirst ? (
                        <div>
                          <div className="font-medium text-gray-800">{o.display_name}</div>
                          <div className={`text-xs ${textTokens.secondary}`}>{o.email ?? o.user_id}</div>
                        </div>
                      ) : null}
                    </td>
                    <td className="px-3 py-2.5 text-gray-700">
                      {row.position ?? <span className={textTokens.muted}>No position</span>}
                    </td>
                    <td className="px-3 py-2.5 text-gray-700">{row.isFirst ? officeCell(o) : null}</td>
                    <td className="px-3 py-2.5">{row.isFirst ? projectAreaCell(o) : null}</td>
                    <td className="px-3 py-2.5">
                      {row.isFirst ? (
                        <SeverityBadge
                          severity={invited ? "warn" : "pass"}
                          label={invited ? "Invited" : "Active"}
                        />
                      ) : null}
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      {row.isFirst && canManage ? (
                        <div className="relative inline-block">
                          <button
                            type="button"
                            aria-label={`Manage ${o.display_name}`}
                            onClick={() => setMenuFor(menuFor === o.user_id ? null : o.user_id)}
                            className="rounded p-1 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
                          >
                            <MoreHorizontal size={18} />
                          </button>
                          {menuFor === o.user_id ? (
                            <>
                              <button
                                type="button"
                                aria-hidden
                                tabIndex={-1}
                                className="fixed inset-0 z-10 cursor-default"
                                onClick={() => setMenuFor(null)}
                              />
                              <div className="absolute right-0 z-20 mt-1 w-52 rounded-md border border-gray-200 bg-white py-1 text-sm shadow-lg">
                                <button
                                  type="button"
                                  onClick={() => {
                                    setManageOfficer(o);
                                    setMenuFor(null);
                                  }}
                                  className="block w-full px-3 py-1.5 text-left text-gray-700 hover:bg-gray-50"
                                >
                                  Manage
                                </button>
                                {/* Frame-11: history-preserving deactivate with the open-case
                                    guard (409 → reassign first). Reactivate restores access. */}
                                {o.is_active === false ? (
                                  <button
                                    type="button"
                                    onClick={() => void handleReactivate(o)}
                                    className="block w-full px-3 py-1.5 text-left text-green-700 hover:bg-green-50"
                                  >
                                    Reactivate
                                  </button>
                                ) : (
                                  <button
                                    type="button"
                                    onClick={() => void handleDeactivate(o)}
                                    className="block w-full px-3 py-1.5 text-left text-red-700 hover:bg-red-50"
                                  >
                                    Deactivate
                                  </button>
                                )}
                              </div>
                            </>
                          ) : null}
                        </div>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {manageOfficer ? (
        <ManageOfficerModal
          officer={manageOfficer}
          onClose={() => setManageOfficer(null)}
          onChanged={() => void reload()}
        />
      ) : null}
    </div>
  );
}

// ── Manage modal (lightweight — the wired lifecycle slice, gaps flagged) ─────────

function ManageOfficerModal({
  officer,
  onClose,
  onChanged,
}: {
  officer: OfficerRosterEntry;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [positions, setPositions] = useState<OfficerPositionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [resending, setResending] = useState(false);

  const invited = (officer.onboarding_status ?? "active") === "invited";

  async function loadPositions() {
    try {
      setLoading(true);
      setPositions(await listOfficerPositions(officer.user_id));
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadPositions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [officer.user_id]);

  async function endPosition(op: OfficerPositionItem) {
    setBusyId(op.officer_position_id);
    setError(null);
    try {
      await endOfficerPosition(officer.user_id, op.officer_position_id);
      await loadPositions();
      onChanged();
    } catch (e) {
      setError(e);
    } finally {
      setBusyId(null);
    }
  }

  async function resend() {
    setResending(true);
    setError(null);
    try {
      await resendOfficerInvite(officer.user_id);
      onChanged();
    } catch (e) {
      setError(e);
    } finally {
      setResending(false);
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-black/30 p-4 sm:p-8">
      <div className="w-full max-w-lg rounded-lg bg-white shadow-xl">
        <div className="flex items-start justify-between border-b border-gray-200 px-4 py-3">
          <div>
            <h3 className="text-sm font-semibold text-gray-800">{officer.display_name}</h3>
            <p className={`text-xs ${textTokens.secondary}`}>{officer.email ?? officer.user_id}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            <X size={18} />
          </button>
        </div>

        <div className="space-y-4 px-4 py-4">
          {error ? <ErrorNotice error={error} /> : null}

          {/* Positions */}
          <section>
            <h4 className={`mb-1 text-xs font-medium ${textTokens.secondary}`}>Positions</h4>
            {loading ? (
              <div className="h-8 w-full animate-pulse rounded bg-gray-100" />
            ) : positions.length === 0 ? (
              <p className={`text-sm ${textTokens.muted}`}>No active positions.</p>
            ) : (
              <ul className="space-y-1">
                {positions.map((op) => (
                  <li
                    key={op.officer_position_id}
                    className="flex items-center justify-between rounded border border-gray-200 px-2.5 py-1.5"
                  >
                    <span className="text-sm text-gray-800">
                      {op.position_display_name ?? op.position_key ?? "Position"}
                      <span className={`ml-1.5 text-xs ${textTokens.muted}`}>{op.organization_id}</span>
                    </span>
                    <button
                      type="button"
                      disabled={busyId === op.officer_position_id}
                      onClick={() => endPosition(op)}
                      className={BTN_GHOST}
                    >
                      {busyId === op.officer_position_id ? "Ending…" : "End position"}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* Wired lifecycle action(s) */}
          {invited ? (
            <section>
              <button type="button" disabled={resending} onClick={resend} className={BTN_GHOST}>
                {resending ? "Sending…" : "Resend setup email"}
              </button>
            </section>
          ) : null}

          {/* Backend-pending lifecycle actions (frame-11 §6). Disabled with reason.
              TODO: wire Edit position & area, Transfer, and open-case-guarded Deactivate once
              the server endpoints (paged roster, soft-deactivate, open-case guard) land. */}
          <section className="space-y-1 border-t border-gray-100 pt-3">
            <p className={`text-xs ${textTokens.muted}`}>Coming soon (backend pending):</p>
            <div className="flex flex-wrap gap-2">
              {/* R12 (BUILD-REVIEW MO5): Deactivate is wired in the row ⋯ menu — removed from
                  this "coming soon" list to kill the self-contradiction. */}
              {["Edit position & area", "Transfer"].map((label) => (
                <button
                  key={label}
                  type="button"
                  disabled
                  title="Backend pending — this lifecycle endpoint isn't available yet."
                  className={BTN_GHOST}
                >
                  {label}
                </button>
              ))}
            </div>
          </section>
        </div>

        <div className="flex justify-end border-t border-gray-200 px-4 py-3">
          <button type="button" onClick={onClose} className={BTN_GHOST}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

export default OfficersDirectory;
