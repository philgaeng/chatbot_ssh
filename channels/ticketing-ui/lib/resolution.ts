// SPDX-License-Identifier: Apache-2.0

import type { ResolutionOption } from "@/lib/api";

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
