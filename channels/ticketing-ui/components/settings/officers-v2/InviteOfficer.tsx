"use client";

/**
 * <InviteOfficer> — invite-AS-RESULT (DESIGN §4.1 / build sheet frame-03).
 *
 * A state machine, not a form. Three always-visible inputs — Office, Position, Email —
 * then the role / organisation / scope / project fall out as a RESULT (<InviteOutcomeCard>),
 * with role/org/scope tucked behind an "Adjust" disclosure (<InviteAdjustDisclosure>) and an
 * <OverrideBadge> shown only where the admin changed a default. A one-sentence confirm gates
 * the irreversible Keycloak invite email.
 *
 * Send routing (frame-03 §3 rule 8, dual-hat): if the email already belongs to an officer we
 * ADD a position (assignOfficerPosition — additive, no email); a brand-new email goes through
 * inviteOfficer (provisions Keycloak + emails a set-password link).
 *
 * S5 dead-end kill (frame-03 §3 rule 5): if the office isn't on a project, we don't dead-end —
 * we offer "Link it and continue" (addProjectOrg) inline, then the card completes.
 */

import { useEffect, useMemo, useState } from "react";

import {
  listOrganizations,
  listPositionTypes,
  listRoles,
  listProjects,
  listOfficerRoster,
  getAdminContext,
  inviteOfficer,
  assignOfficerPosition,
  addProjectOrg,
  type OrganizationItem,
  type PositionTypeItem,
  type GrmRole,
  type ProjectItem,
  type OfficerRosterEntry,
  type AdminContext,
  type OfficerInvitePayload,
  type OfficerPositionAssign,
} from "@/lib/api";
import { roleMatchesFilter, type TrackFilter } from "@/lib/trackFilter";
import { Bilingual } from "@/components/shared/Bilingual";
import { RoleLabel } from "@/components/shared/RoleLabel";
import { ErrorNotice } from "@/components/shared/ErrorNotice";
import { primary, danger, warning, success, text as textTokens } from "@/lib/design-tokens";
import { ChevronDown, Search } from "lucide-react";

import {
  InviteOutcomeCard,
  type OutcomeValues,
  type OutcomeResolved,
} from "./InviteOutcomeCard";
import { InviteAdjustDisclosure, type RoleChoice } from "./InviteAdjustDisclosure";

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
}: {
  positions: PositionTypeItem[];
  value: PositionTypeItem | null;
  disabled?: boolean;
  onSelect: (p: PositionTypeItem) => void;
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
  const [roles, setRoles] = useState<GrmRole[]>([]);
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [roster, setRoster] = useState<OfficerRosterEntry[]>([]);
  const [ctx, setCtx] = useState<AdminContext | null>(null);

  // selections
  const [office, setOffice] = useState<OrganizationItem | null>(null);
  const [position, setPosition] = useState<PositionTypeItem | null>(null);
  const [email, setEmail] = useState("");
  const [values, setValues] = useState<OutcomeValues | null>(null);

  // flow
  const [mode, setMode] = useState<"edit" | "confirm" | "sent">("edit");
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<unknown>(null);
  const [forceAdjust, setForceAdjust] = useState(false);

  // S5 link
  const [s5ProjectId, setS5ProjectId] = useState("");
  const [linking, setLinking] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        const [o, pt, r, pr, ro, ac] = await Promise.all([
          listOrganizations(undefined, { tree: true }),
          listPositionTypes(),
          listRoles({ kind: "operational" }),
          listProjects(undefined, false),
          listOfficerRoster().catch(() => [] as OfficerRosterEntry[]),
          getAdminContext().catch(() => null),
        ]);
        if (cancelled) return;
        setOrgs(o);
        setPositions(pt);
        setRoles(r);
        setProjects(pr);
        setRoster(ro);
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

  const orgById = useMemo(
    () => new Map(orgs.map((o) => [o.organization_id, o])),
    [orgs],
  );
  const roleByKey = useMemo(() => new Map(roles.map((r) => [r.role_key, r])), [roles]);
  const projectById = useMemo(
    () => new Map(projects.map((p) => [p.project_id, p])),
    [projects],
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

  // Role catalog for Adjust — track-filtered to the chosen position's track.
  const roleChoices: RoleChoice[] = useMemo(() => {
    const track = position?.workflow_track ?? "standard";
    const filter: TrackFilter = track === "seah" ? "seah" : track === "both" ? "all" : "standard";
    return roles
      .filter((r) => (seahCapable ? true : (r.workflow_scope ?? "") !== "SEAH"))
      .filter((r) => roleMatchesFilter(r.workflow_scope ?? "Both", filter))
      .map((r) => ({ role_key: r.role_key, display_name: r.display_name }));
  }, [roles, position, seahCapable]);

  // Projects the chosen office is linked to (S5 prerequisite resolved here).
  const linkedProjects = useMemo(() => {
    if (!office) return [];
    return projects.filter(
      (p) =>
        p.organizations.some((o) => o.organization_id === office.organization_id) ||
        p.implementing_agency_org_id === office.organization_id,
    );
  }, [projects, office]);

  // Defaults = the matrix + territory pre-fill. The client shows what the server will compute.
  const defaults: OutcomeValues | null = useMemo(() => {
    if (!office || !position) return null;
    const proj = linkedProjects[0] ?? null;
    return {
      roleKey: position.default_role_key || null,
      organizationId: office.organization_id,
      locationCode: office.territory_location_code ?? null,
      includesChildren: office.territory_includes_children ?? false,
      projectId: proj?.project_id ?? null,
      projectCode: proj?.short_code ?? null,
    };
  }, [office, position, linkedProjects]);

  // Reset the working values whenever the resolved defaults change (office/position/link).
  useEffect(() => {
    setValues(defaults);
    setForceAdjust(false);
    setMode("edit");
    setSendError(null);
  }, [defaults]);

  const existingOfficer = useMemo(() => {
    const e = email.trim().toLowerCase();
    if (!e) return null;
    return roster.find((r) => (r.email ?? "").toLowerCase() === e) ?? null;
  }, [roster, email]);

  const emailValid = EMAIL_RE.test(email.trim());
  const showCard = !!office && !!position && !!values && !!defaults;
  const needsProjectLink =
    !!office && !!position && linkedProjects.length === 0 && !(values?.projectId);
  const canSend = !!office && !!position && emailValid && !!values?.roleKey;

  const resolved: OutcomeResolved = useMemo(() => {
    const overrideOrg =
      values && office && values.organizationId !== office.organization_id
        ? orgById.get(values.organizationId)
        : null;
    const proj = values?.projectId ? projectById.get(values.projectId) : null;
    return {
      roleDisplayName: values?.roleKey ? roleByKey.get(values.roleKey)?.display_name ?? null : null,
      organizationName: overrideOrg?.name ?? null,
      organizationNameNe: overrideOrg?.display_name_ne ?? null,
      projectName: proj?.name ?? null,
      territoryName: null, // no by-code name resolver yet → card falls back to prettyLocation()
    };
  }, [values, office, orgById, roleByKey, projectById]);

  async function linkAndContinue() {
    if (!office || !s5ProjectId) return;
    setLinking(true);
    setSendError(null);
    try {
      await addProjectOrg(s5ProjectId, office.organization_id, null);
      const fresh = await listProjects(undefined, false);
      setProjects(fresh); // → linkedProjects → defaults → values reset with the new project
      setS5ProjectId("");
    } catch (e) {
      setSendError(e);
    } finally {
      setLinking(false);
    }
  }

  function resetAll() {
    setOffice(null);
    setPosition(null);
    setEmail("");
    setValues(null);
    setMode("edit");
    setSendError(null);
    setForceAdjust(false);
  }

  async function doSend() {
    if (!office || !position || !values || !values.roleKey) return;
    setSending(true);
    setSendError(null);
    try {
      if (existingOfficer) {
        // Additive "add a position" path — no Keycloak email (frame-03 §3 rule 8).
        const roleOverridden = (values.roleKey ?? "") !== (defaults?.roleKey ?? "");
        const payload: OfficerPositionAssign = {
          position_type_id: position.position_type_id,
          organization_id: values.organizationId,
          role_key: roleOverridden ? values.roleKey : null,
          location_code: values.locationCode,
          includes_children: values.includesChildren,
          project_id: values.projectId,
          project_code: values.projectCode,
        };
        await assignOfficerPosition(existingOfficer.user_id, payload);
      } else {
        // New email → invite (provisions Keycloak, emails a set-password link).
        // R7 (M5): carry the chosen position so the invite records the officer_positions row.
        const payload: OfficerInvitePayload = {
          email: email.trim(),
          role_key: values.roleKey,
          organization_id: values.organizationId,
          location_code: values.locationCode,
          project_id: values.projectId,
          project_code: values.projectCode,
          includes_children: values.includesChildren,
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
        <div className="h-28 w-full animate-pulse rounded bg-gray-100" />
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
        <button type="button" onClick={resetAll} className={`mt-3 ${BTN_GHOST}`}>
          Invite another officer
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Inputs — always visible */}
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

      {/* Outcome — a result, not a form */}
      {showCard && office && position && values && defaults ? (
        <div className="space-y-3">
          {values.roleKey ? null : (
            <ErrorNotice error="This position has no default role. Choose a role manually under Adjust." />
          )}

          <InviteOutcomeCard
            email={email}
            office={office}
            position={position}
            values={values}
            defaults={defaults}
            resolved={resolved}
            onAdjust={() => setForceAdjust(true)}
          />

          {needsProjectLink ? (
            <div className={`rounded-md border ${warning.borderLight} ${warning.bgLight} p-3`}>
              <p className={`text-sm ${warning.text}`}>
                <Bilingual en={office.name} ne={office.display_name_ne} mode="active" /> isn&rsquo;t
                on a project yet.
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <select
                  className={FIELD + " sm:w-64"}
                  value={s5ProjectId}
                  onChange={(e) => setS5ProjectId(e.target.value)}
                >
                  <option value="">Choose a project…</option>
                  {projects.map((p) => (
                    <option key={p.project_id} value={p.project_id}>
                      {p.name} ({p.short_code})
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  disabled={!s5ProjectId || linking}
                  onClick={linkAndContinue}
                  className={BTN_PRIMARY}
                >
                  {linking ? "Linking…" : "Link it and continue"}
                </button>
              </div>
            </div>
          ) : null}

          <InviteAdjustDisclosure
            values={values}
            defaults={defaults}
            roleChoices={roleChoices}
            orgChoices={orgs}
            projectChoices={projects}
            onChange={setValues}
            forceOpen={forceAdjust || !values.roleKey}
          />

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
                    {email.trim()})? They&rsquo;ll act as{" "}
                    <RoleLabel roleKey={values.roleKey} displayName={resolved.roleDisplayName} />
                    {resolved.projectName ? <> on {resolved.projectName}</> : null}. No email is
                    sent.
                  </>
                ) : (
                  <>
                    Send an invite to <span className="font-medium">{email.trim()}</span>? They join
                    as{" "}
                    <RoleLabel roleKey={values.roleKey} displayName={resolved.roleDisplayName} />,{" "}
                    <Bilingual en={office.name} ne={office.display_name_ne} mode="active" />
                    {resolved.projectName ? <> on {resolved.projectName}</> : null}. This emails a
                    set-password link &mdash; it can&rsquo;t be un-sent.
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
                disabled={!canSend || needsProjectLink}
                onClick={() => setMode("confirm")}
                className={BTN_PRIMARY}
                title={
                  !canSend
                    ? "Pick an office, position, valid email, and role first"
                    : needsProjectLink
                      ? "Link the office to a project first"
                      : undefined
                }
              >
                Review &amp; send
              </button>
            </div>
          )}
        </div>
      ) : (
        <p className={`text-sm ${textTokens.muted}`}>
          Pick an office and a position to see what this invite will create.
        </p>
      )}
    </div>
  );
}

export default InviteOfficer;
