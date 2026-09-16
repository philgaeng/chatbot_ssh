// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it } from "vitest";

import { isAccessTokenExpired, isAccessTokenExpiringSoon } from "./session-expired";

// Standard-base64 payload segment: session-expired.ts does
// atob(seg.replace(/-/g,"+").replace(/_/g,"/")) — with no -/_ present that
// replace is a no-op and atob decodes the padded base64 directly.
function jwtExpiringInSeconds(deltaSeconds: number): string {
  const exp = Math.floor(Date.now() / 1000) + deltaSeconds;
  const seg = Buffer.from(JSON.stringify({ sub: "o@x", exp })).toString("base64");
  return `x.${seg}.y`;
}

describe("isAccessTokenExpired (skew regression, H2-01)", () => {
  it("treats a token 10s from expiry as EXPIRED (was kept valid by the old -30s skew)", () => {
    // Pre-fix: `exp*1000 < now - 30_000` → false here, guaranteeing a 401 window.
    // Post-fix: `< now + 30_000` → refresh early.
    expect(isAccessTokenExpired(jwtExpiringInSeconds(10))).toBe(true);
  });

  it("treats a token with plenty of life left as NOT expired", () => {
    expect(isAccessTokenExpired(jwtExpiringInSeconds(120))).toBe(false);
  });

  it("treats a long-expired token as expired", () => {
    expect(isAccessTokenExpired(jwtExpiringInSeconds(-300))).toBe(true);
  });
});

describe("isAccessTokenExpiringSoon (proactive-refresh trigger)", () => {
  it("fires inside the window", () => {
    expect(isAccessTokenExpiringSoon(jwtExpiringInSeconds(30), 60)).toBe(true);
  });

  it("does not fire outside the window", () => {
    expect(isAccessTokenExpiringSoon(jwtExpiringInSeconds(120), 60)).toBe(false);
  });

  it("returns false for a non-JWT string instead of throwing", () => {
    expect(isAccessTokenExpiringSoon("not-a-jwt", 60)).toBe(false);
  });
});
