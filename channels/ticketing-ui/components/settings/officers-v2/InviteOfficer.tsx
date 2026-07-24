"use client";

/**
 * <InviteOfficer> — invite an officer by Office · Position · Email (DESIGN-cast-model §3.4).
 *
 * A position is a literal job title; it carries NO role. The operational role/tier and
 * jurisdiction are bound later by per-package Cast staffing (Projects → Cast), which writes
 * the `user_roles` / `officer_scopes` enforcement rows. So the invite here only:
 *   • provisions the account (Keycloak set-password email, when configured), and
 *   • records the descriptive officer_positions row.
 * The invitee shows in the Directory as "invited, unstaffed" until they are cast on a package.
 *
 * Three inputs, that's it — Office, Position, Email. No role, no area, no project.
 *
 * Send routing (dual-hat): if the email already belongs to an officer we ADD a position
 * (assignOfficerPosition — additive, no email); a brand-new email goes through inviteOfficer
 * (provisions Keycloak + emails a set-password link).
 *
 * When no position fits the chosen office, the Position picker offers inline creation via
 * <PositionTypeEditor>, seeded with the office's unit type so the new title fits.
 */

import { useEffect, useMemo, useState } from "react";

import {
  listOrganizations,
  listPositionTypes,
  listOfficerRoster,
  getAdminContext,
  inviteOfficer,
  assignOfficerPosition,
  type OrganizationItem,
  type PositionTypeItem,
  type OfficerRosterEntry,
  type AdminContext,
  type OfficerInvitePayload,
  type OfficerPositionAssign,
} from "@/lib/api";
import { Bilingual } from "@/components/shared/Bilingual";
import { ErrorNotice } from "@/components/shared/ErrorNotice";
import { primary, danger, warning, success, text as textTokens } from "@/lib/design-tokens";
import { ChevronDown, Plus, Search } from "lucide-react";

import { PositionTypeEditor } from "@/components/settings/org/PositionTypeEditor";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const BTN_PRIMARY = `inline-flex items-center gap-1.5 rounded px-3.5 py-2 text-sm font-medium text-white ${primary.bg} ${primary.bgHover} disabled:cursor-not-allowed disabled:opacity-50`;
const BTN_GHOST =
  "inline-flex items-center gap-1.5 rounded border border-gray-300 px-3.5 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50";
const FIELD =
  "w-full rounded border border-gray-300 bg-white px-2.5 py-1.5 text-sm text-gray-800 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:bg-gray-50";

// ── Small searchable picker (office + position share the shape) ──────────────────

function PickerButton({
  placeholder,
  disabled,
  children,
  open,
  onToggle,
}: {
  placeholder: string;
  disabled?: boolean;
  children: React.ReactNode | null;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onToggle}
      aria-expanded={open}
      className={`flex w-full items-center justify-between gap-2 rounded border px-2.5 py-1.5 text-left text-sm ${
        disabled ? "cursor-not-allowed border-gray-200 bg-gray-50 text-gray-400" : "border-gray-300 bg-white text-gray-800"
      }`}
    >
      <span className="min-w-0 truncate">
        {children ?? <span className={textTokens.muted}>{placeholder}</span>}
      </span>
      <ChevronDown size={16} className="shrink-0 text-gray-400" aria-hidden />
    </button>
  );
}

function OfficePicker({
  orgs,
  depthOf,
  value,
  onSelect,
}: {
  orgs: OrganizationItem[];
  depthOf: (o: OrganizationItem) => number;
  value: OrganizationItem | null;
  onSelect: (o: OrganizationItem) => void;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const term = q.trim().toLowerCase();
  const filtered = orgs.filter(
    (o) =>
      !term ||
      o.name.toLowerCase().includes(term) ||
      (o.display_name_ne ?? "").toLowerCase().includes(term),
  );

  return (
    <div className="relative">
      <PickerButton
        placeholder="Pick an office (org unit)…"
        open={open}
        onToggle={() => setOpen((v) => !v)}
      >
        {value ? <Bilingual en={value.name} ne={value.display_name_ne} mode="active" /> : null}
      </PickerButton>
      {open ? (
        <div className="absolute z-20 mt-1 max-h-72 w-full overflow-auto rounded-md border border-gray-200 bg-white shadow-lg">
          <div className="sticky top-0 flex items-center gap-1.5 border-b border-gray-100 bg-white px-2 py-1.5">
            <Search size={14} className="text-gray-400" aria-hidden />
            <input
              autoFocus
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search offices…"
              className="w-full text-sm outline-none"
            />
          </div>
          {filtered.length === 0 ? (
            <p className={`px-3 py-3 text-sm ${textTokens.muted}`}>No offices match.</p>
          ) : (
            filtered.map((o) => (
              <button
                key={o.organization_id}
                type="button"
                onClick={() => {
                  onSelect(o);
                  setOpen(false);
                  setQ("");
                }}
                className="block w-full px-3 py-1.5 text-left text-sm text-gray-800 hover:bg-blue-50"
                style={{ paddingLeft: `${0.75 + depthOf(o) * 0.9}rem` }}
              >
                <Bilingual en={o.name} ne={o.display_name_ne} mode="active" />
                {o.unit_type ? (
                  <span className={`ml-1.5 text-xs ${textTokens.muted}`}>· {o.unit_type.replace(/_/g, " ")}</span>
                ) : null}
              </button>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}

function PositionPicker({
  positions,
  value,
  disabled,
  onSelect,
  onCreateNew,
}: {
  positions: PositionTypeItem[];
  value: PositionTypeItem | null;
  disabled?: boolean;
  onSelect: (p: PositionTypeItem) => void;
  /** Open the position-type modal: create a title that fits this office. */
  onCreateNew?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const term = q.trim().toLowerCase();
  const filtered = positions.filter(
    (p) =>
      !term ||
      p.display_name.toLowerCase().includes(term) ||
      (p.display_name_ne ?? "").toLowerCase().includes(term),
  );

  return (
    <div className="relative">
      <PickerButton
        placeholder={disabled ? "Pick an office first…" : "Pick a position…"}
        disabled={disabled}
        open={open}
        onToggle={() => setOpen((v) => !v)}
      >
        {value ? <Bilingual en={value.display_name} ne={value.display_name_ne} mode="active" /> : null}
      </PickerButton>
      {open && !disabled ? (
        <div className="absolute z-20 mt-1 max-h-72 w-full overflow-auto rounded-md border border-gray-200 bg-white shadow-lg">
          <div className="sticky top-0 flex items-center gap-1.5 border-b border-gray-100 bg-white px-2 py-1.5">
            <Search size={14} className="text-gray-400" aria-hidden />
            <input
              autoFocus
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search positions…"
              className="w-full text-sm outline-none"
            />
          </div>
          {filtered.length === 0 ? (
            <p className={`px-3 py-3 text-sm ${textTokens.muted}`}>
              No positions fit this office type.
            </p>
          ) : (
            filtered.map((p) => (
              <button
                key={p.position_type_id}
                type="button"
                onClick={() => {
                  onSelect(p);
                  setOpen(false);
                  setQ("");
                }}
                className="block w-full px-3 py-1.5 text-left text-sm text-gray-800 hover:bg-blue-50"
              >
                <Bilingual en={p.display_name} ne={p.display_name_ne} mode="active" />
              </button>
            ))
          )}
          {onCreateNew ? (
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                setQ("");
                onCreateNew();
              }}
              className="sticky bottom-0 flex w-full items-center gap-1.5 border-t border-gray-100 bg-white px-3 py-2 text-left text-sm font-medium text-blue-700 hover:bg-blue-50"
            >
              <Plus size={14} aria-hidden /> Create a new position…
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

// ── Main component ───────────────────────────────────────────────────────────────

export function InviteOfficer({
  canInvite,
  onInvited,
}: {
  canInvite: boolean;
  onInvited?: () => void;
}) {
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<unknown>(null);

  const [orgs, setOrgs] = useState<OrganizationItem[]>([]);
  const [positions, setPositions] = useState<PositionTypeItem[]>([]);
  const [roster, setRoster] = useState<OfficerRosterEntry[]>([]);
  const [ctx, setCtx] = useState<AdminContext | null>(null);

  // selections
  const [office, setOffice] = useState<OrganizationItem | null>(null);
  const [position, setPosition] = useState<PositionTypeItem | null>(null);
  const [email, setEmail] = useState("");

  // flow
  const [mode, setMode] = useState<"edit" | "confirm" | "sent">("edit");
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<unknown>(null);

  // Inline position-type creation: when no title fits the chosen office, mint one without
  // leaving the invite. Backend stamps owner scope + enforces the real permission (403 → modal).
  const [creatingPosition, setCreatingPosition] = useState(false);

  // Fast path — only these three (all DB-backed) gate the form. The officer roster is slow on a
  // large realm (it lists the whole Keycloak directory), so it must NOT block the form: it only
  // powers the "already an officer" hint and loads separately, below.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        const [o, pt, ac] = await Promise.all([
          listOrganizations(undefined, { tree: true }),
          listPositionTypes(),
          getAdminContext().catch(() => null),
        ]);
        if (cancelled) return;
        setOrgs(o);
        setPositions(pt);
        setCtx(ac);
      } catch (e) {
        if (!cancelled) setLoadError(e);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Roster loads separately (non-blocking) — only for the existing-officer / dual-hat hint.
  // Until it arrives, a send routes through invite; the backend still handles a dup gracefully.
  useEffect(() => {
    let cancelled = false;
    listOfficerRoster()
      .then((r) => {
        if (!cancelled) setRoster(r);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const orgById = useMemo(
    () => new Map(orgs.map((o) => [o.organization_id, o])),
    [orgs],
  );

  const depthOf = useMemo(() => {
    const cache = new Map<string, number>();
    const compute = (o: OrganizationItem, guard = 0): number => {
      if (cache.has(o.organization_id)) return cache.get(o.organization_id)!;
      const parentId = o.parent_organization_id;
      const parent = parentId ? orgById.get(parentId) : null;
      const d = parent && guard < 32 ? compute(parent, guard + 1) + 1 : 0;
      cache.set(o.organization_id, d);
      return d;
    };
    return (o: OrganizationItem) => compute(o);
  }, [orgById]);

  const seahCapable =
    !!ctx && (ctx.is_super_admin || ctx.admin_workflow_tracks.includes("seah"));

  // Positions filtered by the office's unit_type + SEAH gating (frame-03 §3 rule 1 / pin 9).
  const availablePositions = useMemo(() => {
    return positions.filter((p) => {
      if (!seahCapable && p.workflow_track === "seah") return false;
      if (!office) return true;
      const allowed = p.allowed_unit_types ?? [];
      if (allowed.length === 0) return true;
      return office.unit_type ? allowed.includes(office.unit_type) : true;
    });
  }, [positions, office, seahCapable]);

  // Reset the flow whenever the office/position changes.
  useEffect(() => {
    setMode("edit");
    setSendError(null);
  }, [office, position]);

  const existingOfficer = useMemo(() => {
    const e = email.trim().toLowerCase();
    if (!e) return null;
    return roster.find((r) => (r.email ?? "").toLowerCase() === e) ?? null;
  }, [roster, email]);

  const emailValid = EMAIL_RE.test(email.trim());
  const showCard = !!office && !!position;
  const canSend = !!office && !!position && emailValid;

  function resetAll() {
    setOffice(null);
    setPosition(null);
    setEmail("");
    setMode("edit");
    setSendError(null);
  }

  async function doSend() {
    if (!office || !position) return;
    setSending(true);
    setSendError(null);
    try {
      if (existingOfficer) {
        // Additive "add a position" path — no Keycloak email, no role (Cast binds the tier).
        const payload: OfficerPositionAssign = {
          position_type_id: position.position_type_id,
          organization_id: office.organization_id,
        };
        await assignOfficerPosition(existingOfficer.user_id, payload);
      } else {
        // New email → invite (provisions Keycloak, emails a set-password link). No role —
        // the officer is "invited, unstaffed" until cast on a package.
        const payload: OfficerInvitePayload = {
          email: email.trim(),
          organization_id: office.organization_id,
          position_type_id: position.position_type_id,
        };
        await inviteOfficer(payload);
      }
      setMode("sent");
      onInvited?.();
      // Keep roster fresh so a follow-up invite detects the just-added officer.
      listOfficerRoster()
        .then(setRoster)
        .catch(() => {});
    } catch (e) {
      setSendError(e);
      setMode("edit");
    } finally {
      setSending(false);
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  if (!canInvite) {
    return (
      <div className={`rounded border ${warning.borderLight} ${warning.bgLight} px-3 py-2 text-sm ${warning.text}`}>
        You don&rsquo;t have permission to invite officers.
      </div>
    );
  }

  if (loading) {
    return (
      <div className="space-y-3" aria-busy="true">
        <div className="h-9 w-full animate-pulse rounded bg-gray-100" />
        <div className="h-9 w-full animate-pulse rounded bg-gray-100" />
        <div className="h-9 w-2/3 animate-pulse rounded bg-gray-100" />
      </div>
    );
  }

  if (loadError) {
    return <ErrorNotice error={loadError} />;
  }

  if (mode === "sent") {
    return (
      <div className={`rounded-lg border ${success.borderLight} ${success.bgLight} p-4`}>
        <p className={`text-sm font-medium ${success.text}`}>
          {existingOfficer
            ? "Position added."
            : "Invite sent — a set-password link is on its way."}
        </p>
        <p className={`mt-0.5 text-sm ${textTokens.secondary}`}>
          {email.trim()}
          {position ? (
            <>
              {" · "}
              <Bilingual en={position.display_name} ne={position.display_name_ne} mode="active" />
            </>
          ) : null}
        </p>
        <p className={`mt-1 text-xs ${textTokens.muted}`}>
          Staff them on a package (Projects &rarr; Cast) to grant queue access.
        </p>
        <button type="button" onClick={resetAll} className={`mt-3 ${BTN_GHOST}`}>
          Invite another officer
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Inputs — Office · Position · Email */}
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <label className={`text-xs font-medium ${textTokens.secondary}`}>Office</label>
          <OfficePicker orgs={orgs} depthOf={depthOf} value={office} onSelect={setOffice} />
        </div>
        <div className="space-y-1">
          <label className={`text-xs font-medium ${textTokens.secondary}`}>Position</label>
          <PositionPicker
            positions={availablePositions}
            value={position}
            disabled={!office}
            onSelect={setPosition}
            onCreateNew={office ? () => setCreatingPosition(true) : undefined}
          />
        </div>
      </div>

      <div className="space-y-1">
        <label className={`text-xs font-medium ${textTokens.secondary}`}>Officer email</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="name@dor.gov.np"
          className={FIELD}
        />
        {email.trim() && !emailValid ? (
          <p className={`text-xs ${danger.text}`}>Enter a valid email address.</p>
        ) : existingOfficer ? (
          <p className={`text-xs ${textTokens.secondary}`}>
            {existingOfficer.display_name} is already an officer — this adds a position, no new
            email is sent.
          </p>
        ) : null}
      </div>

      {/* Once office + position are chosen, offer the send action. Role/area are NOT set here —
          the confirm step below restates the invite before the irreversible email. */}
      {showCard && office && position ? (
        <div className="space-y-3">
          <p className={`text-xs ${textTokens.muted}`}>
            The role and work area are set later when you staff this officer on a package
            (Projects &rarr; Cast).
          </p>

          {sendError ? <ErrorNotice error={sendError} /> : null}

          {/* Confirm gate before the irreversible email */}
          {mode === "confirm" ? (
            <div className={`rounded-lg border ${primary.borderLight} ${primary.bgLight} p-4`}>
              <p className="text-sm text-gray-800">
                {existingOfficer ? (
                  <>
                    Add a{" "}
                    <span className="font-medium">
                      <Bilingual en={position.display_name} ne={position.display_name_ne} mode="active" />
                    </span>{" "}
                    position for{" "}
                    <span className="font-medium">{existingOfficer.display_name}</span> (
                    {email.trim()})? No email is sent.
                  </>
                ) : (
                  <>
                    Send an invite to <span className="font-medium">{email.trim()}</span> as{" "}
                    <span className="font-medium">
                      <Bilingual en={position.display_name} ne={position.display_name_ne} mode="active" />
                    </span>{" "}
                    at{" "}
                    <Bilingual en={office.name} ne={office.display_name_ne} mode="active" />? This
                    emails a set-password link &mdash; it can&rsquo;t be un-sent.
                  </>
                )}
              </p>
              <div className="mt-3 flex items-center gap-2">
                <button type="button" disabled={sending} onClick={doSend} className={BTN_PRIMARY}>
                  {sending
                    ? "Sending…"
                    : existingOfficer
                      ? "Add position"
                      : "Send invite"}
                </button>
                <button
                  type="button"
                  disabled={sending}
                  onClick={() => setMode("edit")}
                  className={BTN_GHOST}
                >
                  Back
                </button>
              </div>
            </div>
          ) : (
            <div>
              <button
                type="button"
                disabled={!canSend}
                onClick={() => setMode("confirm")}
                className={BTN_PRIMARY}
                title={!canSend ? "Pick an office, position, and a valid email first" : undefined}
              >
                Review &amp; send
              </button>
            </div>
          )}
        </div>
      ) : (
        <p className={`text-sm ${textTokens.muted}`}>
          Pick an office and a position to continue.
        </p>
      )}

      {creatingPosition && office ? (
        <PositionTypeEditor
          mode="create"
          allPositionTypes={positions}
          // Seed "Used at" with the chosen office's unit type so the new title fits it.
          initialAllowedUnitTypes={office.unit_type ? [office.unit_type] : []}
          onSaved={(pt) => {
            setPositions((prev) => [...prev, pt]);
            setPosition(pt); // auto-select the just-created title
            setCreatingPosition(false);
          }}
          onCancel={() => setCreatingPosition(false)}
        />
      ) : null}
    </div>
  );
}

export default InviteOfficer;
