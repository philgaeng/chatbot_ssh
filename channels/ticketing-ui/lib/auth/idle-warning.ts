// SPDX-License-Identifier: Apache-2.0

/**
 * When to warn an officer that their session is about to end (`GRM-111`, D-012).
 *
 * The realm ends a session after 30 minutes without a renewal, and the UI renews only when the officer's
 * next request finds the 5-minute access token near its end. **Typing does not call the server**, so an
 * officer writing a long note can reach the idle window mid-sentence. Without a warning, their next Send
 * is refused and they are taken to sign-in with the text gone.
 *
 * The deadline is read from the stored refresh token. Measured on Keycloak 2026-09-15, its `exp` is the
 * end of the idle window (or of the 8-hour maximum, whichever comes first), and it moves forward on
 * every renewal. Reading it costs no request.
 *
 * ⚠ **The warning must never renew by itself.** A timer that renewed would keep an unattended session
 * alive for the full 8 hours, which is the exact risk the idle window closes on a shared computer. Only
 * the officer's click on *Stay signed in* renews.
 */

/** Show the warning this long before the session ends. */
export const IDLE_WARNING_LEAD_MS = 2 * 60_000;

export type IdleWarning =
  | { kind: "none" }
  /** The idle window is closing; one renewal keeps the officer signed in. */
  | { kind: "idle"; msLeft: number }
  /** A renewal did not move the deadline: the 8-hour maximum, which nothing extends. */
  | { kind: "limit"; msLeft: number }
  /** The deadline has passed. Whatever is on screen is still there, until the officer navigates. */
  | { kind: "ended" };

/** `exp` of a JWT in milliseconds, or null when there is no token or it cannot be read. */
export function tokenExpiryMs(token: string | null | undefined): number | null {
  if (!token) return null;
  try {
    const seg = token.split(".")[1];
    const json = atob(seg.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (seg.length % 4)) % 4));
    const exp = (JSON.parse(json) as { exp?: unknown }).exp;
    return typeof exp === "number" ? exp * 1000 : null;
  } catch {
    return null;
  }
}

/**
 * @param sessionEndsAtMs the stored refresh token's `exp`, or null when signed out
 * @param atLimit a renewal already failed to move the deadline past the warning window
 */
export function idleWarningState(sessionEndsAtMs: number | null, nowMs: number, atLimit = false): IdleWarning {
  if (sessionEndsAtMs === null) return { kind: "none" };
  const msLeft = sessionEndsAtMs - nowMs;
  if (msLeft <= 0) return { kind: "ended" };
  if (msLeft > IDLE_WARNING_LEAD_MS) return { kind: "none" };
  return atLimit ? { kind: "limit", msLeft } : { kind: "idle", msLeft };
}

/** "1:05" — minutes and seconds left, rounded up so the banner never shows 0:00 while still open. */
export function formatTimeLeft(msLeft: number): string {
  const total = Math.max(0, Math.ceil(msLeft / 1000));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}
