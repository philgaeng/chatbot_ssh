// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it } from "vitest";

import { IDLE_WARNING_LEAD_MS, formatTimeLeft, idleWarningState, tokenExpiryMs } from "./idle-warning";

const NOW = 1_800_000_000_000;

function jwt(payload: object): string {
  const seg = Buffer.from(JSON.stringify(payload)).toString("base64url");
  return `h.${seg}.s`;
}

describe("tokenExpiryMs", () => {
  it("reads exp from a base64url payload, in ms", () => {
    expect(tokenExpiryMs(jwt({ typ: "Refresh", exp: 1_800_001_800, sub: "o?>x" }))).toBe(1_800_001_800_000);
  });

  it("is null for no token, a malformed one, or one without exp", () => {
    expect(tokenExpiryMs(null)).toBeNull();
    expect(tokenExpiryMs("not-a-jwt")).toBeNull();
    expect(tokenExpiryMs(jwt({ sub: "x" }))).toBeNull();
  });
});

describe("idleWarningState (GRM-111)", () => {
  it("says nothing while the idle window is comfortably open — a working officer never sees it", () => {
    // Renewing every ~5 minutes keeps the deadline 25–30 minutes away.
    expect(idleWarningState(NOW + 25 * 60_000, NOW)).toEqual({ kind: "none" });
    expect(idleWarningState(NOW + IDLE_WARNING_LEAD_MS + 1, NOW)).toEqual({ kind: "none" });
  });

  it("warns inside the last two minutes", () => {
    expect(idleWarningState(NOW + 90_000, NOW)).toEqual({ kind: "idle", msLeft: 90_000 });
  });

  it("says the session hit its limit when a renewal did not move the deadline", () => {
    expect(idleWarningState(NOW + 90_000, NOW, true)).toEqual({ kind: "limit", msLeft: 90_000 });
  });

  it("says the session ended once the deadline passed — before the officer's Send is refused", () => {
    expect(idleWarningState(NOW - 1, NOW)).toEqual({ kind: "ended" });
    expect(idleWarningState(NOW, NOW)).toEqual({ kind: "ended" });
  });

  it("says nothing when signed out (no refresh token, e.g. another tab signed out, or bypass mode)", () => {
    expect(idleWarningState(null, NOW)).toEqual({ kind: "none" });
  });
});

describe("formatTimeLeft", () => {
  it("rounds up, so it never reads 0:00 while the session is still open", () => {
    expect(formatTimeLeft(120_000)).toBe("2:00");
    expect(formatTimeLeft(65_001)).toBe("1:06");
    expect(formatTimeLeft(1)).toBe("0:01");
    expect(formatTimeLeft(-5)).toBe("0:00");
  });
});
