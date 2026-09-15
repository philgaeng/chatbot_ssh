// SPDX-License-Identifier: Apache-2.0

import type {
  ExternalActor,
  OrganizationChoice,
  ResolutionActorKind,
  ResolutionActorPayload,
  ResolutionOption,
} from "@/lib/api";

export function isResolutionRecordEvent(event: {
  event_type: string;
  payload?: Record<string, unknown> | null;
}): boolean {
  return (
    event.event_type === "NOTE_ADDED" &&
    !!(event.payload as Record<string, unknown> | null)?.is_resolution_record
  );
}

export const RESOLUTION_MIN_NOTE_LEN = 12;

/** Preselected when the case's workflow offers it — the default before the catalog existed. */
export const PREFERRED_DEFAULT_ACTION_CODE = "ACCEPTED_OTHER";

export interface ResolutionFormState {
  /** No options: a sensitive workflow, whose cases record no action (GRM-116). */
  textOnly: boolean;
  category: string | null;
  note: string;
  valid: boolean;
}

/**
 * The resolve form, derived — never seeded from an effect (GRM-107's lesson: a seed that waits on
 * async loads loses to a fast click). `chosen` and `typed` are what the officer did; everything
 * else follows from the options the ticket currently offers, so a reload that changes them (the
 * case moved workflow) cannot leave the form on an action it no longer offers.
 */
export function resolutionFormState(
  options: ResolutionOption[],
  chosen: string | null,
  typed: string | null,
): ResolutionFormState {
  const textOnly = options.length === 0;
  const fallback = textOnly
    ? null
    : options.some((o) => o.code === PREFERRED_DEFAULT_ACTION_CODE)
      ? PREFERRED_DEFAULT_ACTION_CODE
      : options[0].code;
  const category = chosen && options.some((o) => o.code === chosen) ? chosen : fallback;
  const note = typed ?? options.find((o) => o.code === category)?.default_wording ?? "";
  return {
    textOnly,
    category,
    note,
    valid: note.trim().length >= RESOLUTION_MIN_NOTE_LEN && (textOnly || category !== null),
  };
}

/** What the officer has picked in *Who took the action?* (GRM-117). */
export interface ResolutionActorChoice {
  kind: ResolutionActorKind;
  /** For "self": which of their offices, when they have several. For "organization": the office. */
  organizationId: string | null;
  external: string | null;
}

export const DEFAULT_ACTOR_CHOICE: ResolutionActorChoice = { kind: "self", organizationId: null, external: null };

export interface ResolutionActorState {
  /** No choices at all: a sensitive workflow, whose cases record no actor — the section is absent. */
  hidden: boolean;
  /** "I did — <office>" when the office is decided; null when the officer must choose. */
  selfOffice: OrganizationChoice | null;
  /** The hint under the section when Confirm is blocked by it, else null. */
  missing: string | null;
  /** The RESOLVE fields, or null when hidden or incomplete. */
  payload: ResolutionActorPayload | null;
}

/**
 * The actor section, derived from what the ticket offers and what the officer picked — never seeded
 * from an effect, for the same reason as `resolutionFormState`.
 */
export function resolutionActorState(
  offers: { selfOffices: OrganizationChoice[]; externalActors: ExternalActor[] },
  choice: ResolutionActorChoice,
): ResolutionActorState {
  const { selfOffices, externalActors } = offers;
  if (selfOffices.length === 0 && externalActors.length === 0) {
    return { hidden: true, selfOffice: null, missing: null, payload: null };
  }
  const selfOffice = selfOffices.length === 1 ? selfOffices[0] : null;

  if (choice.kind === "self") {
    if (selfOffice) {
      return { hidden: false, selfOffice, missing: null, payload: { resolution_actor_kind: "self" } };
    }
    const picked = selfOffices.find((o) => o.organization_id === choice.organizationId);
    return picked
      ? { hidden: false, selfOffice, missing: null,
          payload: { resolution_actor_kind: "self", resolution_actor_organization_id: picked.organization_id } }
      : { hidden: false, selfOffice, missing: "Choose which of your offices took the action.", payload: null };
  }
  if (choice.kind === "organization") {
    return choice.organizationId
      ? { hidden: false, selfOffice, missing: null,
          payload: { resolution_actor_kind: "organization", resolution_actor_organization_id: choice.organizationId } }
      : { hidden: false, selfOffice, missing: "Choose the office that took the action.", payload: null };
  }
  const external = externalActors.find((a) => a.key === choice.external);
  return external
    ? { hidden: false, selfOffice, missing: null,
        payload: { resolution_actor_kind: "external", resolution_actor_external: external.key } }
    : { hidden: false, selfOffice, missing: "Choose who took the action.", payload: null };
}
