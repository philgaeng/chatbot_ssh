// SPDX-License-Identifier: Apache-2.0

/**
 * Staffing levels: which ones open, and what a closed one says (`GRM-090`).
 *
 * **The default state is the whole design decision.** Collapsing every level hides exactly what
 * the pane exists to surface — on the live KL Road project that is two unstaffed required slots,
 * and the go-live rail's "2 blockers" is the only other place they are visible. Leaving every
 * level open is what the client asked to fix: the two blockers sit below a screen of controls
 * that are already satisfied.
 *
 * So: **closed by default, except a level with an unmet required slot.** And a closed level says
 * how many in WORDS, never by a coloured dot alone — `ui/05` rule 6 and `05_frontend` rule 8.2,
 * which exist for low-literacy, colour-blind and cheap-monitor readers in that order.
 *
 * Pure and separate from the component per `05_frontend` rule 2.2 — the predicate is the part
 * worth testing, and it needs no DOM.
 */

/** One slot on a level: is somebody required there, and is it empty? */
export interface TierState {
  required: boolean;
  empty: boolean;
}

/**
 * How many slots on this level block go-live.
 *
 * ⚠ **A package scope never blocks**, mirroring `blocking` in `CastStaffing`: a per-package level
 * inherits the project-wide officer unless overridden, so an empty package slot is "same as
 * project", not "nobody". Getting this wrong would open every package level on every project and
 * undo the item.
 */
export function blockingSlotCount(tiers: TierState[], isPackageScope: boolean): number {
  if (isPackageScope) return 0;
  return tiers.filter((t) => t.required && t.empty).length;
}

/**
 * What a closed level's header says, or `null` when it has nothing to report.
 *
 * Plain and short, per `ui/05` — "Needs an officer", not "1 unstaffed required tier".
 */
export function blockingSummary(count: number): string | null {
  if (count <= 0) return null;
  return count === 1 ? "Needs an officer" : `Needs ${count} officers`;
}

/**
 * The levels that start open: every level with at least one blocker.
 *
 * ⭐ **Returns an empty set when nothing blocks, and that is deliberate** — a fully staffed
 * workflow opens nothing, which is the state the collapse is for. It is also why this is
 * computed once as an initial value rather than derived on every render: staffing a level would
 * otherwise make it collapse under the admin's cursor the moment they finished it.
 */
export function initiallyOpenSteps(
  steps: { stepId: string; blockingCount: number }[],
): Set<string> {
  return new Set(steps.filter((s) => s.blockingCount > 0).map((s) => s.stepId));
}
