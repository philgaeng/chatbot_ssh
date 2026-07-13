"use client";

/**
 * <InviteAdjustDisclosure> — the collapsed "▸ Adjust role, area, or project" editor
 * (DESIGN §4.1 / build sheet frame-03 §2). Behind a disclosure so the outcome card reads
 * as a result by default; opening it reveals role / organisation / scope / project as
 * editable fields. Every change is emitted up via `onChange`; the parent recomputes the
 * outcome card and stamps <OverrideBadge> on any value moved away from its default.
 *
 * This component holds no resolution logic — it edits the same `OutcomeValues` the card
 * reads. Override detection lives in the parent so the card + the disclosure agree.
 */

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

import type { OrganizationItem, ProjectItem } from "@/lib/api";
import { OverrideBadge } from "@/components/shared/OverrideBadge";
import { roleLabel } from "@/lib/labels";
import { primary, text as textTokens } from "@/lib/design-tokens";
import type { OutcomeValues } from "./InviteOutcomeCard";

export interface RoleChoice {
  role_key: string;
  display_name: string;
}

const FIELD =
  "w-full rounded border border-gray-300 bg-white px-2.5 py-1.5 text-sm text-gray-800 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:bg-gray-50";
const LABEL = "flex items-center gap-2 text-xs font-medium";

function orgOptionLabel(o: OrganizationItem): string {
  return o.display_name_ne ? `${o.name} / ${o.display_name_ne}` : o.name;
}

export function InviteAdjustDisclosure({
  values,
  defaults,
  roleChoices,
  orgChoices,
  projectChoices,
  onChange,
  forceOpen = false,
}: {
  values: OutcomeValues;
  defaults: OutcomeValues;
  roleChoices: RoleChoice[];
  orgChoices: OrganizationItem[];
  projectChoices: ProjectItem[];
  onChange: (next: OutcomeValues) => void;
  /** Force the disclosure open (e.g. the position has no default role → admin must pick one). */
  forceOpen?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const isOpen = open || forceOpen;

  const roleOverridden = (values.roleKey ?? "") !== (defaults.roleKey ?? "");
  const orgOverridden = values.organizationId !== defaults.organizationId;
  const scopeOverridden =
    (values.locationCode ?? "") !== (defaults.locationCode ?? "") ||
    values.includesChildren !== defaults.includesChildren;
  const projectOverridden = (values.projectId ?? "") !== (defaults.projectId ?? "");
  const anyOverride = roleOverridden || orgOverridden || scopeOverridden || projectOverridden;

  const set = (patch: Partial<OutcomeValues>) => onChange({ ...values, ...patch });

  const Chevron = isOpen ? ChevronDown : ChevronRight;

  return (
    <div className="rounded-md border border-gray-200">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={isOpen}
        disabled={forceOpen}
        className={`flex w-full items-center gap-1.5 px-3 py-2 text-left text-sm font-medium ${textTokens.body} disabled:cursor-default`}
      >
        <Chevron size={16} className="shrink-0" aria-hidden />
        Adjust role, area, or project
        {anyOverride ? <OverrideBadge className="ml-1" /> : null}
      </button>

      {isOpen ? (
        <div className="space-y-4 border-t border-gray-200 px-3 py-3">
          {/* Role */}
          <div className="space-y-1">
            <span className={`${LABEL} ${textTokens.secondary}`}>
              Role
              <OverrideBadge show={roleOverridden} />
            </span>
            <select
              className={FIELD}
              value={values.roleKey ?? ""}
              onChange={(e) => set({ roleKey: e.target.value || null })}
            >
              <option value="">Choose a role…</option>
              {roleChoices.map((r) => (
                <option key={r.role_key} value={r.role_key}>
                  {roleLabel(r.role_key, r.display_name)}
                </option>
              ))}
            </select>
            <p className={`text-xs ${textTokens.muted}`}>
              {roleOverridden
                ? "Overridden by you"
                : "Suggested from the position type."}
            </p>
          </div>

          {/* Organisation */}
          <div className="space-y-1">
            <span className={`${LABEL} ${textTokens.secondary}`}>
              Organisation
              <OverrideBadge show={orgOverridden} />
            </span>
            <select
              className={FIELD}
              value={values.organizationId}
              onChange={(e) => set({ organizationId: e.target.value })}
            >
              {orgChoices.map((o) => (
                <option key={o.organization_id} value={o.organization_id}>
                  {orgOptionLabel(o)}
                </option>
              ))}
            </select>
          </div>

          {/* Scope / area */}
          <div className="space-y-1">
            <span className={`${LABEL} ${textTokens.secondary}`}>
              Area covered
              <OverrideBadge show={scopeOverridden} />
            </span>
            <input
              type="text"
              className={FIELD}
              value={values.locationCode ?? ""}
              placeholder="Office territory (leave blank for the whole organisation)"
              onChange={(e) => set({ locationCode: e.target.value.trim() || null })}
            />
            <label className={`mt-1 flex items-center gap-2 text-xs ${textTokens.secondary}`}>
              <input
                type="checkbox"
                className="h-3.5 w-3.5"
                checked={values.includesChildren}
                onChange={(e) => set({ includesChildren: e.target.checked })}
              />
              Include everything under this area
            </label>
          </div>

          {/* Project */}
          <div className="space-y-1">
            <span className={`${LABEL} ${textTokens.secondary}`}>
              Project
              <OverrideBadge show={projectOverridden} />
            </span>
            <select
              className={FIELD}
              value={values.projectId ?? ""}
              onChange={(e) => {
                const p = projectChoices.find((x) => x.project_id === e.target.value) ?? null;
                set({ projectId: p?.project_id ?? null, projectCode: p?.short_code ?? null });
              }}
            >
              <option value="">No project</option>
              {projectChoices.map((p) => (
                <option key={p.project_id} value={p.project_id}>
                  {p.name} ({p.short_code})
                </option>
              ))}
            </select>
          </div>

          {anyOverride ? (
            <button
              type="button"
              onClick={() => onChange(defaults)}
              className={`text-xs underline ${primary.textLight} hover:no-underline`}
            >
              Reset to the suggested values
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export default InviteAdjustDisclosure;
