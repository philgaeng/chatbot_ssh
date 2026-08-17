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
