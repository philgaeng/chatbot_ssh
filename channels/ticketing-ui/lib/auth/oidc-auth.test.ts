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

describe("signOut: checked revoke, same-origin on success, Keycloak as fallback", () => {
  // Option 3. The same-origin redirect is the benefit — no cross-origin hop means no separate
  // app window and no spurious LOGOUT_ERROR against an already-dead session. The front-channel
  // navigation is KEPT for the unconfirmed case, because it is the guaranteed mechanism: a
  // browser navigation always runs, where the fetch is best-effort.

  function arm(opts: { revoked?: boolean; ok?: boolean; reject?: boolean } = {}) {
    const calls: string[] = [];
    const nav = { href: "", replaced: [] as string[] };
    vi.stubGlobal("fetch", (url: string) => {
      calls.push(String(url));
      if (opts.reject) return Promise.reject(new Error("offline"));
      return Promise.resolve({
        ok: opts.ok ?? true,
        status: 200,
        json: () => Promise.resolve({ message: "Signed out.", revoked: opts.revoked ?? true }),
      });
    });
    const location = {
      origin: "https://grm.test",
      pathname: "/queue",
      get href() {
        return nav.href;
      },
      set href(v: string) {
        nav.href = v;
      },
      replace: (u: string) => nav.replaced.push(u),
    };
    vi.stubGlobal("location", location);
    vi.stubGlobal("sessionStorage", fakeStorage());
    vi.stubGlobal("window", { localStorage: ls, location });
    return { calls, nav };
  }

  async function signOut() {
    const { OIDCAuthClient } = await import("./oidc-auth");
    const { OIDC_ISSUER, OIDC_CLIENT_ID } = await import("./runtime-config");
    await new OIDCAuthClient(
      OIDC_ISSUER,
      OIDC_CLIENT_ID,
      "https://grm.test/auth/callback",
    ).signOut();
  }

  function armSession() {
    const future = Math.floor(Date.now() / 1000) + 3600;
    ls.setItem("grm_refresh_token", jwt({ azp: "ticketing-api" }));
    ls.setItem("grm_id_token", jwt({ azp: "ticketing-api", exp: future }));
    ls.setItem("grm_access_token", jwt({ exp: future }));
  }

  it("⭐ confirmed revoke → same-origin redirect, and NO cross-origin navigation", async () => {
    const { calls, nav } = arm({ revoked: true });
    armSession();
    await signOut();

    expect(calls.some((u) => u.includes("/api/v1/auth/logout"))).toBe(true);
    expect(nav.replaced).toEqual(["https://grm.test/login"]);
    expect(nav.href).toBe(""); // the Keycloak hop is what spawns a second window
  });

  it("⚠ unconfirmed revoke → falls back to the Keycloak front channel", async () => {
    // revoked:false with HTTP 200 — the exact shape the endpoint returns on failure, and the
    // reason the flag lives in the body rather than the status.
    const { nav } = arm({ revoked: false });
    armSession();
    await signOut();

    expect(nav.href).toContain("/protocol/openid-connect/logout");
    expect(nav.replaced).toEqual([]);
  });

  it("a network failure falls back rather than stranding the user", async () => {
    const { nav } = arm({ reject: true });
    armSession();
    await signOut();
    expect(nav.href).toContain("/protocol/openid-connect/logout");
  });

  it("a non-200 falls back too", async () => {
    const { nav } = arm({ ok: false });
    armSession();
    await signOut();
    expect(nav.href).toContain("/protocol/openid-connect/logout");
  });

  it("stale session with an unconfirmed revoke still lands on /login, not a Keycloak error page", async () => {
    // No id_token: `id_token_hint` would be absent and Keycloak renders an error rather than
    // logging anyone out, so the front channel cannot help here whatever the revoke did.
    const { nav } = arm({ revoked: false });
    ls.setItem("grm_refresh_token", jwt({ azp: "ticketing-api" }));
    await signOut();
    expect(nav.replaced).toEqual(["https://grm.test/login"]);
    expect(nav.href).toBe("");
  });

  it("clears local storage before awaiting, so other tabs do not wait on the network", async () => {
    arm({ revoked: true });
    armSession();
    await signOut();
    expect(ls.getItem("grm_access_token")).toBeNull();
    expect(ls.getItem("grm_refresh_token")).toBeNull();
  });
});
