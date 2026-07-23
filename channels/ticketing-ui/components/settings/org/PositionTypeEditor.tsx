"use client";

/**
 * <PositionTypeEditor> — create/edit a position type (DESIGN §4.4, Frame 06).
 *
 * Fields: Title (EN + Nepali), Used at (allowed_unit_types), Default role (the matrix —
 * a valid-only picker filtered to the position's track via lib/trackFilter), Grievance
 * type (workflow_track), supervisor visibility (visibility_mode), reporting line
 * (reports_to_position_key + reports_to_locus), and owning level (owner_organization_id).
 *
 * `position_key` is server-minted from the title (never user-authored) and immutable after create.
 * Track/matrix validation is enforced server-side (422); we prevent most of it by only
 * listing track-valid roles, and surface any residual 422/409 via <ErrorNotice>.
 */

import { useEffect, useMemo, useState } from "react";

import {
  createPositionType,
  updatePositionType,
  listRoles,
  type PositionTypeItem,
  type PositionTypeCreate,
  type PositionTypeUpdate,
  type OrganizationItem,
  type GrmRole,
} from "@/lib/api";
import { roleInTrack } from "@/lib/trackFilter";
import { roleLabel } from "@/lib/labels";
import { text as textTokens } from "@/lib/design-tokens";
import { ErrorNotice } from "@/components/shared/ErrorNotice";
import { RoleLabel } from "@/components/shared/RoleLabel";
import { ProvenanceHint } from "@/components/shared/ProvenanceHint";

import {
  UNIT_TYPES,
  UNIT_TYPE_ORG_CATEGORY,
  VISIBILITY_MODES,
  POSITION_TRACKS,
  REPORTS_TO_LOCI,
  unitTypeLabel,
  visibilityModeLabel,
  positionTrackLabel,
  reportsToLocusLabel,
  owningLevelLabel,
  orgCategorySector,
  orgNameMap,
} from "./orgVocab";

/** Roles valid for a position's track (mirrors the server matrix rule). */
function rolesForTrack(roles: GrmRole[], track: string): GrmRole[] {
  if (track === "both") {
    return roles.filter((r) => (r.workflow_scope ?? "") === "Both");
  }
  const concrete = track === "seah" ? "seah" : "standard";
  return roles.filter((r) => roleInTrack(r.workflow_scope ?? "", concrete));
}

/**
 * Role-picker groups, operational-first (mirrors role_archetypes.ARCHETYPE_LABELS).
 * Roles whose archetype is null/unlisted (custom rows, admin ladder) fall into "Other".
 */
const ARCHETYPE_GROUPS: { key: string; label: string }[] = [
  { key: "field_actor", label: "Field actors (L1)" },
  { key: "supervisor", label: "Supervisors (L2)" },
  { key: "grc_committee", label: "GRC — chair" },
  { key: "grc_member", label: "GRC — members" },
  { key: "seah_handler", label: "SEAH handlers" },
  { key: "observer", label: "Observers (read-only)" },
];

/** Bucket track-valid roles into ordered archetype groups for <optgroup> rendering. */
function groupRolesByArchetype(roles: GrmRole[]): { label: string; roles: GrmRole[] }[] {
  const byArch: Record<string, GrmRole[]> = {};
  for (const r of roles) {
    const key = r.archetype ?? "__other__";
    (byArch[key] ??= []).push(r);
  }
  const known = new Set(ARCHETYPE_GROUPS.map((g) => g.key));
  const groups: { label: string; roles: GrmRole[] }[] = [];
  for (const g of ARCHETYPE_GROUPS) {
    const rs = byArch[g.key];
    if (rs && rs.length) groups.push({ label: g.label, roles: rs });
  }
  const other = Object.entries(byArch)
    .filter(([k]) => !known.has(k))
    .flatMap(([, rs]) => rs);
  if (other.length) groups.push({ label: "Other", roles: other });
  return groups;
}

export function PositionTypeEditor({
  mode,
  positionType,
  allPositionTypes,
  orgs,
  onSaved,
  onCancel,
}: {
  mode: "create" | "edit";
  positionType?: PositionTypeItem;
  /** For the "reports to" picker. */
  allPositionTypes: PositionTypeItem[];
  /** For the owning-level picker. */
  orgs: OrganizationItem[];
  onSaved: (pt: PositionTypeItem) => void;
  onCancel: () => void;
}) {
  const [displayName, setDisplayName] = useState(positionType?.display_name ?? "");
  const [displayNameNe, setDisplayNameNe] = useState(positionType?.display_name_ne ?? "");
  const [allowedUnitTypes, setAllowedUnitTypes] = useState<string[]>(
    positionType?.allowed_unit_types ?? [],
  );
  const [workflowTrack, setWorkflowTrack] = useState(positionType?.workflow_track ?? "standard");
  const [defaultRoleKey, setDefaultRoleKey] = useState(positionType?.default_role_key ?? "");
  const [visibilityMode, setVisibilityMode] = useState(positionType?.visibility_mode ?? "none");
  const [reportsToKey, setReportsToKey] = useState(positionType?.reports_to_position_key ?? "");
  const [reportsToLocus, setReportsToLocus] = useState(positionType?.reports_to_locus ?? "same_unit");
  const [ownerOrgId, setOwnerOrgId] = useState(positionType?.owner_organization_id ?? "");

  const [roles, setRoles] = useState<GrmRole[]>([]);
  const [rolesLoading, setRolesLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const orgNames = useMemo(() => orgNameMap(orgs), [orgs]);

  useEffect(() => {
    let alive = true;
    setRolesLoading(true);
    listRoles({ kind: "operational" })
      .then((r) => {
        if (alive) setRoles(r);
      })
      .catch(() => {
        if (alive) setRoles([]);
      })
      .finally(() => {
        if (alive) setRolesLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  const trackRoles = useMemo(() => rolesForTrack(roles, workflowTrack), [roles, workflowTrack]);

  // Soft office-type narrowing: which actor sectors the selected "Used at" office types imply.
  const selectedSectors = useMemo(() => {
    const s = new Set<string>();
    for (const ut of allowedUnitTypes) {
      const sec = orgCategorySector(UNIT_TYPE_ORG_CATEGORY[ut]);
      if (sec) s.add(sec);
    }
    return s;
  }, [allowedUnitTypes]);

  // Hard office-type filter: only roles whose affiliation matches the selected office types are
  // listed (typicalGroups). `otherRoles` (the rest) are hidden from the picker — retained solely to
  // detect when the CURRENT selection would be hidden, so it is preserved (see currentAtypicalRole).
  const { typicalGroups, otherRoles } = useMemo(() => {
    const isTypical = (r: GrmRole): boolean => {
      if (selectedSectors.size === 0) return true; // no office chosen yet → everything typical
      const sec = orgCategorySector(r.actor_category);
      return sec === null || selectedSectors.has(sec); // unclassified role → neutral, never demoted
    };
    const typical: GrmRole[] = [];
    const other: GrmRole[] = [];
    for (const r of trackRoles) (isTypical(r) ? typical : other).push(r);
    return { typicalGroups: groupRolesByArchetype(typical), otherRoles: other };
  }, [trackRoles, selectedSectors]);

  // Flag when the current default role isn't valid for the chosen track (server would 422).
  const defaultRoleOutOfTrack =
    !!defaultRoleKey && roles.length > 0 && !trackRoles.some((r) => r.role_key === defaultRoleKey);

  // The hard filter never silently drops the current pick: if it's track-valid but atypical for the
  // selected office types (hidden from the list), keep it shown as a labelled "current" option.
  const currentAtypicalRole = defaultRoleOutOfTrack
    ? undefined
    : otherRoles.find((r) => r.role_key === defaultRoleKey);

  function toggleUnitType(ut: string) {
    setAllowedUnitTypes((prev) =>
      prev.includes(ut) ? prev.filter((x) => x !== ut) : [...prev, ut],
    );
  }

  async function handleSave() {
    if (!displayName.trim()) {
      setError("Please enter a title.");
      return;
    }
    if (!defaultRoleKey) {
      setError("Please choose a default role for this position.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (mode === "create") {
        const payload: PositionTypeCreate = {
          display_name: displayName.trim(),
          display_name_ne: displayNameNe.trim() || null,
          allowed_unit_types: allowedUnitTypes,
          reports_to_position_key: reportsToKey || null,
          reports_to_locus: reportsToKey ? reportsToLocus : null,
          default_role_key: defaultRoleKey,
          visibility_mode: visibilityMode,
          workflow_track: workflowTrack,
          owner_organization_id: ownerOrgId || null,
        };
        const created = await createPositionType(payload);
        onSaved(created);
      } else if (positionType) {
        const payload: PositionTypeUpdate = {
          display_name: displayName.trim(),
          display_name_ne: displayNameNe.trim() || null,
          allowed_unit_types: allowedUnitTypes,
          reports_to_position_key: reportsToKey || null,
          reports_to_locus: reportsToKey ? reportsToLocus : null,
          default_role_key: defaultRoleKey,
          visibility_mode: visibilityMode,
          workflow_track: workflowTrack,
          owner_organization_id: ownerOrgId || null,
        };
        const updated = await updatePositionType(positionType.position_type_id, payload);
        onSaved(updated);
      }
    } catch (e) {
      setError(e);
      setSaving(false);
    }
  }

  const otherPositions = allPositionTypes.filter(
    (p) => p.position_type_id !== positionType?.position_type_id,
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-hidden rounded-xl bg-white shadow-xl">
        <div className="flex items-center justify-between bg-slate-700 px-6 py-4 text-white">
          <div className="font-semibold">
            {mode === "create" ? "Add position type" : "Edit position type"}
          </div>
          <button
            type="button"
            onClick={onCancel}
            className="text-xl leading-none text-slate-300 hover:text-white"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="max-h-[calc(90vh-8rem)] space-y-4 overflow-y-auto p-6">
          <ErrorNotice error={error} />

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-500">Title (English) *</label>
              <input
                autoFocus
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="e.g. Senior Divisional Engineer"
                className="w-full rounded border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-500">Title (Nepali)</label>
              <input
                value={displayNameNe}
                onChange={(e) => setDisplayNameNe(e.target.value)}
                placeholder="वरिष्ठ डिभिजनल इन्जिनियर"
                className="w-full rounded border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
              {!displayNameNe.trim() && (
                <ProvenanceHint className="mt-1">
                  No Nepali title yet — add it later, never invented.
                </ProvenanceHint>
              )}
            </div>
          </div>

          {/* Slicers first: grievance type + office types both narrow the role list below. */}
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-500">Used at (office types)</label>
            <div className="flex flex-wrap gap-2">
              {UNIT_TYPES.map((ut) => {
                const on = allowedUnitTypes.includes(ut);
                return (
                  <button
                    key={ut}
                    type="button"
                    onClick={() => toggleUnitType(ut)}
                    aria-pressed={on}
                    className={`rounded-full border px-2.5 py-1 text-xs font-medium transition ${
                      on
                        ? "border-blue-300 bg-blue-100 text-blue-700"
                        : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
                    }`}
                  >
                    {unitTypeLabel(ut)}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-500">Grievance type</label>
              <select
                value={workflowTrack}
                onChange={(e) => setWorkflowTrack(e.target.value)}
                className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              >
                {POSITION_TRACKS.map((t) => (
                  <option key={t} value={t}>
                    {positionTrackLabel(t)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-500">
                Default role for this position *
              </label>
              <select
                value={defaultRoleKey}
                onChange={(e) => setDefaultRoleKey(e.target.value)}
                disabled={rolesLoading}
                className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              >
                <option value="">{rolesLoading ? "Loading roles…" : "— Choose a role —"}</option>
                {defaultRoleOutOfTrack && (
                  <option value={defaultRoleKey}>
                    {roleLabel(defaultRoleKey)} (current — wrong grievance type)
                  </option>
                )}
                {currentAtypicalRole && (
                  <option value={currentAtypicalRole.role_key}>
                    {roleLabel(currentAtypicalRole.role_key, currentAtypicalRole.display_name)} (current
                    — atypical for the selected office type{allowedUnitTypes.length === 1 ? "" : "s"})
                  </option>
                )}
                {typicalGroups.map((g) => (
                  <optgroup key={g.label} label={g.label}>
                    {g.roles.map((r) => (
                      <option key={r.role_key} value={r.role_key}>
                        {roleLabel(r.role_key, r.display_name)}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
              {defaultRoleKey && (
                <p className={`mt-1 text-xs ${textTokens.secondary}`}>
                  Officers in this position act as <RoleLabel roleKey={defaultRoleKey} />.
                </p>
              )}
              {defaultRoleOutOfTrack && (
                <ProvenanceHint className="mt-1">
                  This role doesn&rsquo;t match the chosen grievance type — pick another or it will be
                  rejected on save.
                </ProvenanceHint>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-500">
                This position&rsquo;s supervisor sees
              </label>
              <select
                value={visibilityMode}
                onChange={(e) => setVisibilityMode(e.target.value)}
                className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              >
                {VISIBILITY_MODES.map((vm) => (
                  <option key={vm} value={vm}>
                    {visibilityModeLabel(vm)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-500">Owning level</label>
              <select
                value={ownerOrgId}
                onChange={(e) => setOwnerOrgId(e.target.value)}
                className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              >
                <option value="">System (available everywhere)</option>
                {orgs.map((o) => (
                  <option key={o.organization_id} value={o.organization_id}>
                    {owningLevelLabel(o.organization_id, orgNames)}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-500">Reports to</label>
              <select
                value={reportsToKey}
                onChange={(e) => setReportsToKey(e.target.value)}
                className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              >
                <option value="">— No one (top of the line) —</option>
                {otherPositions.map((p) => (
                  <option key={p.position_type_id} value={p.position_key}>
                    {roleLabel(p.position_key, p.display_name)}
                  </option>
                ))}
              </select>
            </div>
            {reportsToKey && (
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-500">In the</label>
                <select
                  value={reportsToLocus}
                  onChange={(e) => setReportsToLocus(e.target.value)}
                  className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                >
                  {REPORTS_TO_LOCI.map((l) => (
                    <option key={l} value={l}>
                      {reportsToLocusLabel(l)}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        </div>

        <div className="flex justify-end gap-3 border-t border-gray-100 px-6 py-4">
          <button
            type="button"
            onClick={onCancel}
            className="rounded px-4 py-1.5 text-sm text-gray-500 hover:text-gray-700"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={saving}
            className="rounded bg-blue-600 px-4 py-1.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "Saving…" : mode === "create" ? "Create position type" : "Save changes"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default PositionTypeEditor;
