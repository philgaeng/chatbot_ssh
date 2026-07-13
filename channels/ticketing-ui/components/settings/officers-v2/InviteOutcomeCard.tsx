"use client";

/**
 * <InviteOutcomeCard> — the read-AS-RESULT card (DESIGN §4.1 / build sheet frame-03 §2, D2).
 *
 * This is the whole point of invite-as-result: once an admin picks an office + a position,
 * the role / organisation / scope / project are a *result*, not a form. The card states the
 * outcome in plain language — "acts as {role}, covers {area}, on {project}" — with:
 *   • a <ProvenanceHint> under every value ("From the position", "Office territory"), and
 *   • an <OverrideBadge> beside a value ONLY when the admin changed it away from the default.
 *
 * Pure presentation. All resolution + override detection is done by the parent
 * (InviteOfficer) and handed down as `values` (current) vs `defaults` (matrix/territory).
 */

import type { OrganizationItem, PositionTypeItem } from "@/lib/api";
import { Bilingual } from "@/components/shared/Bilingual";
import { RoleLabel } from "@/components/shared/RoleLabel";
import { OverrideBadge } from "@/components/shared/OverrideBadge";
import { ProvenanceHint } from "@/components/shared/ProvenanceHint";
import { primary, text as textTokens, warning } from "@/lib/design-tokens";

/** The four resolved facts of an invite. Shared with InviteOfficer + InviteAdjustDisclosure. */
export interface OutcomeValues {
  roleKey: string | null;
  organizationId: string;
  locationCode: string | null;
  includesChildren: boolean;
  projectId: string | null;
  projectCode: string | null;
}

/** Display names resolved by the parent (catalog lookups) so the card stays presentational. */
export interface OutcomeResolved {
  /** role catalog display_name for values.roleKey */
  roleDisplayName?: string | null;
  /** when the org was overridden away from the office, its name (else the office name is shown) */
  organizationName?: string | null;
  organizationNameNe?: string | null;
  /** localized project name for values.projectId */
  projectName?: string | null;
  /** localized territory/area name; falls back to prettyLocation(code) when absent */
  territoryName?: string | null;
}

/**
 * Human, non-slug rendering of a territory location code — used as a fallback when no
 * code→name resolver is wired (see build sheet frame-03 §5: never render a raw code).
 * "NP-P1-D-JHAPA" → "Jhapa".
 * TODO: swap for a real location-name lookup once a by-code resolver lands in lib/api.ts.
 */
export function prettyLocation(code: string | null | undefined): string {
  if (!code) return "";
  const tail = code.split(/[-_.:/]/).filter(Boolean).pop() ?? code;
  return tail
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");
}

function OutcomeRow({
  label,
  provenance,
  overridden,
  children,
}: {
  label: string;
  provenance: string;
  overridden: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-0.5 border-t border-gray-100 py-2 first:border-t-0 sm:flex-row sm:items-start sm:gap-3">
      <div className={`w-32 shrink-0 pt-0.5 text-xs font-medium ${textTokens.secondary}`}>
        {label}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2 text-sm text-gray-800">
          {children}
          <OverrideBadge show={overridden} />
        </div>
        <ProvenanceHint>{overridden ? "Overridden by you" : provenance}</ProvenanceHint>
      </div>
    </div>
  );
}

export function InviteOutcomeCard({
  email,
  office,
  position,
  values,
  defaults,
  resolved,
  onAdjust,
}: {
  email: string;
  office: OrganizationItem;
  position: PositionTypeItem;
  values: OutcomeValues;
  defaults: OutcomeValues;
  resolved: OutcomeResolved;
  /** open the Adjust disclosure (used by the "choose a role" affordance). */
  onAdjust?: () => void;
}) {
  const roleOverridden = (values.roleKey ?? "") !== (defaults.roleKey ?? "");
  const orgOverridden = values.organizationId !== defaults.organizationId;
  const scopeOverridden =
    (values.locationCode ?? "") !== (defaults.locationCode ?? "") ||
    values.includesChildren !== defaults.includesChildren;
  const projectOverridden = (values.projectId ?? "") !== (defaults.projectId ?? "");

  const territoryLabel =
    resolved.territoryName ??
    (values.locationCode ? prettyLocation(values.locationCode) : null);

  return (
    <div className={`rounded-lg border ${primary.borderLight} ${primary.bgLight} p-4`}>
      <div className={`mb-1 text-xs font-semibold uppercase tracking-wide ${textTokens.secondary}`}>
        This is what you&rsquo;ll create
      </div>
      <div className="mb-3 text-sm text-gray-800">
        <span className="font-semibold">
          <Bilingual en={position.display_name} ne={position.display_name_ne} mode="active" />
        </span>
        {", "}
        <Bilingual en={office.name} ne={office.display_name_ne} mode="active" />
        {" — invite "}
        <span className="font-medium">{email.trim() || "…"}</span>
      </div>

      <div className="rounded-md bg-white/70 px-3">
        <OutcomeRow
          label="Acts as"
          provenance={`From the position: ${position.display_name}`}
          overridden={roleOverridden}
        >
          {values.roleKey ? (
            <RoleLabel
              roleKey={values.roleKey}
              displayName={resolved.roleDisplayName}
              className="font-medium"
            />
          ) : (
            <span className={`font-medium ${warning.text}`}>
              Role needs to be chosen manually
            </span>
          )}
        </OutcomeRow>

        <OutcomeRow
          label="Organisation"
          provenance="The office you chose"
          overridden={orgOverridden}
        >
          {orgOverridden && resolved.organizationName ? (
            <Bilingual
              en={resolved.organizationName}
              ne={resolved.organizationNameNe}
              mode="active"
              className="font-medium"
            />
          ) : (
            <Bilingual en={office.name} ne={office.display_name_ne} className="font-medium" />
          )}
        </OutcomeRow>

        <OutcomeRow
          label="Covers"
          provenance="Office territory"
          overridden={scopeOverridden}
        >
          {territoryLabel ? (
            <span className="font-medium">
              {territoryLabel}
              {values.includesChildren ? (
                <span className={textTokens.secondary}> and everything under it</span>
              ) : null}
            </span>
          ) : (
            <span className={textTokens.secondary}>All areas of this office</span>
          )}
        </OutcomeRow>

        <OutcomeRow
          label="On project"
          provenance="The office is on this project"
          overridden={projectOverridden}
        >
          {values.projectId ? (
            <span className="font-medium">{resolved.projectName ?? values.projectCode ?? "—"}</span>
          ) : (
            <span className={warning.text}>Not linked to a project yet</span>
          )}
        </OutcomeRow>
      </div>

      {onAdjust && !values.roleKey ? (
        <p className="mt-2 text-xs">
          <button
            type="button"
            onClick={onAdjust}
            className={`underline ${primary.textLight} hover:no-underline`}
          >
            Choose a role &mdash; Adjust
          </button>
        </p>
      ) : null}
    </div>
  );
}

export default InviteOutcomeCard;
