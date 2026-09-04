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

describe("signOut revoke routing (F-19-adjacent: the confidential-client logout bug)", () => {
  // The defect: this always posted to Keycloak with `client_id` alone. Correct for the PUBLIC
  // `ticketing-ui` client; impossible for the CONFIDENTIAL `ticketing-api`, which needs a
  // client_secret a browser must never hold — so every password-login revoke was rejected with
  // invalid_client_credentials, and the browser discarded the result by design. Found in the
  // Keycloak event log minutes after that log was first switched on.

  function armSignOut(refreshPayload: Record<string, unknown>, idPayload?: Record<string, unknown>) {
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
    if (idPayload) ls.setItem("grm_id_token", jwt(idPayload));
    return calls;
  }

  it("password login (azp=ticketing-api) revokes via the API, not Keycloak", async () => {
    const calls = armSignOut({ azp: "ticketing-api" });
    const { OIDCAuthClient } = await import("./oidc-auth");
    const { OIDC_ISSUER, OIDC_CLIENT_ID } = await import("./runtime-config");
    new OIDCAuthClient(OIDC_ISSUER, OIDC_CLIENT_ID, "https://grm.test/auth/callback").signOut();
    expect(calls.some((u) => u.includes("/api/v1/auth/logout"))).toBe(true);
    expect(calls.some((u) => u.includes("/protocol/openid-connect/logout"))).toBe(false);
  });

  it("PKCE login (azp=ticketing-ui) still revokes directly against Keycloak", async () => {
    // Guards the over-correction: routing everything through the API would break the public
    // path, whose token ticketing-api's credentials cannot revoke either.
    const calls = armSignOut({ azp: "ticketing-ui" });
    const { OIDCAuthClient } = await import("./oidc-auth");
    const { OIDC_ISSUER, OIDC_CLIENT_ID } = await import("./runtime-config");
    new OIDCAuthClient(OIDC_ISSUER, OIDC_CLIENT_ID, "https://grm.test/auth/callback").signOut();
    expect(calls.some((u) => u.includes("/protocol/openid-connect/logout"))).toBe(true);
    expect(calls.some((u) => u.includes("/api/v1/auth/logout"))).toBe(false);
  });

  it("routes on the REFRESH token's azp when the id_token is missing", async () => {
    // ⭐ The case that matters most and is easiest to get wrong. On the sessionStale path the
    // id_token is routinely absent, so an id_token-derived azp is undefined exactly when this
    // revoke is the only thing ending the session.
    const calls = armSignOut({ azp: "ticketing-api" }); // no id_token stored
    const { OIDCAuthClient } = await import("./oidc-auth");
    const { OIDC_ISSUER, OIDC_CLIENT_ID } = await import("./runtime-config");
    new OIDCAuthClient(OIDC_ISSUER, OIDC_CLIENT_ID, "https://grm.test/auth/callback").signOut();
    expect(calls.some((u) => u.includes("/api/v1/auth/logout"))).toBe(true);
  });

  it("never puts the refresh token in the URL", async () => {
    const calls = armSignOut({ azp: "ticketing-api" });
    const { OIDCAuthClient } = await import("./oidc-auth");
    const { OIDC_ISSUER, OIDC_CLIENT_ID } = await import("./runtime-config");
    new OIDCAuthClient(OIDC_ISSUER, OIDC_CLIENT_ID, "https://grm.test/auth/callback").signOut();
    for (const u of calls) expect(u).not.toContain("azp");
  });
});
