/**
 * friendlyError.ts — the shared friendly-error contract for the Settings surfaces.
 *
 * R5 (BUILD-REVIEW M3): settings clusters route caught errors through
 * formatUserFacingError (which unwraps an object 4xx `detail`) instead of surfacing
 * raw messages or browser dialogs. Extracted from `app/settings/page.tsx` (T3-05) so
 * the per-tab clusters can share it once they no longer live in the page module.
 */
import { formatUserFacingError } from "@/lib/user-messages";

export function friendlyError(e: unknown): string {
  return formatUserFacingError(e).message;
}
