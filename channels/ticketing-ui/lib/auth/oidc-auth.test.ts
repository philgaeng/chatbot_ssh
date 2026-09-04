// SPDX-License-Identifier: Apache-2.0

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// oidc-auth reads runtime-config (env) at module load, so stub env + reset the
// module registry before each dynamic import. No jsdom: window/localStorage/fetch
// are stubbed globals (vitest env is "node").

function fakeStorage() {
  const m = new Map<string, string>();
  return {
    getItem: (k: string) => (m.has(k) ? (m.get(k) as string) : null),
    setItem: (k: string, v: string) => void m.set(k, String(v)),
    removeItem: (k: string) => void m.delete(k),
    clear: () => m.clear(),
    _map: m,
  };
}

function jwt(payload: Record<string, unknown>): string {
  const seg = Buffer.from(JSON.stringify(payload)).toString("base64");
  return `x.${seg}.y`;
}

let ls: ReturnType<typeof fakeStorage>;

beforeEach(() => {
  vi.resetModules();
  vi.stubEnv("NEXT_PUBLIC_OIDC_ISSUER", "https://kc.test/realms/grm");
  vi.stubEnv("NEXT_PUBLIC_OIDC_CLIENT_ID", "ticketing-ui");
  ls = fakeStorage();
  vi.stubGlobal("localStorage", ls);
  vi.stubGlobal("window", { localStorage: ls });
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("refreshTokens single-flight (H2-01)", () => {
  it("collapses 3 concurrent callers into exactly one token-endpoint POST", async () => {
    ls.setItem("grm_refresh_token", "r1");
    const newAccess = jwt({ sub: "o@x", email: "o@x", exp: 9999999999 });
    const fetchMock = vi.fn(async () => {
      await new Promise((r) => setTimeout(r, 10)); // hold the flight open
      return {
        ok: true,
        json: async () => ({
          access_token: newAccess,
          id_token: jwt({ sub: "o@x", email: "o@x", exp: 9999999999 }),
          refresh_token: "r2",
        }),
      };
    });
    vi.stubGlobal("fetch", fetchMock);

    const { refreshTokens } = await import("./oidc-auth");
    const results = await Promise.all([refreshTokens(), refreshTokens(), refreshTokens()]);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(results).toEqual([newAccess, newAccess, newAccess]);
    expect(ls.getItem("grm_access_token")).toBe(newAccess);
    expect(ls.getItem("grm_refresh_token")).toBe("r2"); // rotation persisted
  });

  it("returns null (no POST) when there is no stored refresh token", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const { refreshTokens } = await import("./oidc-auth");
    expect(await refreshTokens()).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("returns null when the grant is rejected (expired/rotated refresh token)", async () => {
    ls.setItem("grm_refresh_token", "stale");
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, status: 400, json: async () => ({}) })));
    const { refreshTokens } = await import("./oidc-auth");
    expect(await refreshTokens()).toBeNull();
  });
});

describe("signOut revoke: the browser must not decide how to authenticate it", () => {
  // Two earlier versions failed here, both invisibly. The first posted straight to Keycloak
  // with client_id alone — valid only for a PUBLIC client. The second routed on
  // `azp !== clientId`, assuming clientId names the public client; on this deployment
  // NEXT_PUBLIC_OIDC_CLIENT_ID is `ticketing-api`, the CONFIDENTIAL one, so the comparison
  // was a value against itself and never fired. Both were found in the realm event log.

  function armSignOut(refreshPayload: Record<string, unknown>) {
    const calls: string[] = [];
    vi.stubGlobal("fetch", (url: string) => {
      calls.push(String(url));
      return Promise.resolve({ ok: true, status: 204, json: () => Promise.resolve({}) });
    });
    vi.stubGlobal("location", { origin: "https://grm.test", href: "", replace: () => {} });
    vi.stubGlobal("sessionStorage", fakeStorage());
    vi.stubGlobal("window", {
      localStorage: ls,
      location: { origin: "https://grm.test", href: "", replace: () => {} },
    });
    ls.setItem("grm_refresh_token", jwt(refreshPayload));
    return calls;
  }

  it.each([
    ["ticketing-api (confidential)", "ticketing-api"],
    ["ticketing-ui (public)", "ticketing-ui"],
  ])("%s → always the server endpoint, never Keycloak directly", async (_label, azp) => {
    const calls = armSignOut({ azp });
    const { OIDCAuthClient } = await import("./oidc-auth");
    const { OIDC_ISSUER, OIDC_CLIENT_ID } = await import("./runtime-config");
    new OIDCAuthClient(OIDC_ISSUER, OIDC_CLIENT_ID, "https://grm.test/auth/callback").signOut();

    expect(calls.some((u) => u.includes("/api/v1/auth/logout"))).toBe(true);
    expect(calls.some((u) => u.includes("/protocol/openid-connect/logout"))).toBe(false);
  });

  it("⭐ regression: routes to the server even when azp EQUALS the configured client id", async () => {
    // This is the exact shape the previous fix could not see. NEXT_PUBLIC_OIDC_CLIENT_ID is
    // "ticketing-api" here, matching the token's azp — the old `azp !== clientId` test was
    // false and the revoke went to Keycloak and 401'd.
    vi.stubEnv("NEXT_PUBLIC_OIDC_CLIENT_ID", "ticketing-api");
    vi.resetModules();
    const calls = armSignOut({ azp: "ticketing-api" });
    const { OIDCAuthClient } = await import("./oidc-auth");
    const { OIDC_ISSUER, OIDC_CLIENT_ID } = await import("./runtime-config");
    expect(OIDC_CLIENT_ID).toBe("ticketing-api"); // the precondition that broke the last fix
    new OIDCAuthClient(OIDC_ISSUER, OIDC_CLIENT_ID, "https://grm.test/auth/callback").signOut();

    expect(calls.some((u) => u.includes("/api/v1/auth/logout"))).toBe(true);
    expect(calls.some((u) => u.includes("/protocol/openid-connect/logout"))).toBe(false);
  });

  it("still revokes when there is no id_token at all (the stale-session path)", async () => {
    const calls = armSignOut({ azp: "ticketing-api" });
    const { OIDCAuthClient } = await import("./oidc-auth");
    const { OIDC_ISSUER, OIDC_CLIENT_ID } = await import("./runtime-config");
    new OIDCAuthClient(OIDC_ISSUER, OIDC_CLIENT_ID, "https://grm.test/auth/callback").signOut();
    expect(calls.some((u) => u.includes("/api/v1/auth/logout"))).toBe(true);
  });
});
