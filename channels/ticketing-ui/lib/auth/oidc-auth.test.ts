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

describe("refresh runs through the server, as the client that issued the session (GRM-104)", () => {
  // ⚠ The single-flight tests above mock fetch WITHOUT checking where it posts or as which client,
  // and they stub an issuer. Both are why they passed for the whole life of the defect: refresh
  // posted straight to Keycloak as the public `ticketing-ui` client, with no secret, a token that
  // password sign-in issues to the CONFIDENTIAL `ticketing-api` client. Keycloak refused every
  // time and every officer was signed out at the hour. These pin the destination and the payload.

  function capture(ok = true) {
    const calls: { url: string; body: Record<string, unknown> }[] = [];
    vi.stubGlobal("fetch", async (url: string, init?: { body?: string }) => {
      calls.push({ url: String(url), body: init?.body ? JSON.parse(init.body) : {} });
      return {
        ok,
        status: ok ? 200 : 401,
        json: async () =>
          ok
            ? {
                access_token: jwt({ sub: "o@x", email: "o@x", exp: 9999999999 }),
                id_token: jwt({ sub: "o@x", email: "o@x", exp: 9999999999 }),
                refresh_token: "rotated",
              }
            : { detail: { code: "session_expired" } },
      };
    });
    return calls;
  }

  it("posts to the same-origin /api/v1/auth/refresh and never to Keycloak", async () => {
    ls.setItem("grm_refresh_token", "r1");
    const calls = capture();
    const { refreshTokens } = await import("./oidc-auth");
    await refreshTokens();

    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe("/api/v1/auth/refresh");
    expect(calls.some((c) => /openid-connect|realms\//.test(c.url))).toBe(false);
  });

  it("sends ONLY the refresh token — no client id, no secret, from the browser", async () => {
    // Choosing the client and holding its secret is the server's job; a browser that sends
    // client_id is a browser guessing, and guessing is exactly what failed.
    ls.setItem("grm_refresh_token", "r1");
    const calls = capture();
    const { refreshTokens } = await import("./oidc-auth");
    await refreshTokens();

    expect(Object.keys(calls[0].body)).toEqual(["refresh_token"]);
    expect(calls[0].body.refresh_token).toBe("r1");
  });

  it("works in a build with NO Keycloak issuer — the CI-built image", async () => {
    // ⭐ The case the old tests hid by stubbing NEXT_PUBLIC_OIDC_ISSUER. ui:<sha> images are built
    // by images.yml, which never passes it; refresh used to bail out on `!OIDC_ISSUER` there.
    vi.stubEnv("NEXT_PUBLIC_OIDC_ISSUER", "");
    ls.setItem("grm_refresh_token", "r1");
    const calls = capture();
    const { refreshTokens } = await import("./oidc-auth");

    expect(await refreshTokens()).toBeTruthy();
    expect(calls).toHaveLength(1);
    // Keycloak issues a NEW refresh token on every refresh, so the newest must be kept — and since
    // GRM-105 the realm revokes the old one, so keeping a stale token is a sign-out waiting to happen.
    expect(ls.getItem("grm_refresh_token")).toBe("rotated");
  });

  it("a refused refresh returns null and keeps the stored token untouched for sign-out", async () => {
    ls.setItem("grm_refresh_token", "stale");
    capture(false);
    const { refreshTokens } = await import("./oidc-auth");

    expect(await refreshTokens()).toBeNull();
    expect(ls.getItem("grm_refresh_token")).toBe("stale");
  });
});

describe("renewal is serialised across tabs (GRM-105)", () => {
  // ⭐ Why this matters now. The realm revokes a refresh token once used, and — measured on Keycloak
  // 2026-09-14 — a SECOND use ends the whole session, the fresh token included. Two tabs renewing at
  // once used to cost one harmless 400; with revocation on it signs the officer out of every tab.
  //
  // Each `import` after `vi.resetModules()` is a separate module instance, so each "tab" has its own
  // single-flight — exactly like two real tabs — while sharing storage and the lock, as tabs do.

  /** A FIFO exclusive lock with the `navigator.locks.request` shape. */
  function fakeLocks() {
    let tail: Promise<unknown> = Promise.resolve();
    const requests: { name: string; mode?: string }[] = [];
    return {
      requests,
      request(name: string, opts: { mode?: string }, fn: () => Promise<unknown>) {
        requests.push({ name, mode: opts?.mode });
        const run = tail.then(() => fn());
        tail = run.then(
          () => undefined,
          () => undefined,
        );
        return run;
      },
    };
  }

  const fresh = () => jwt({ sub: "o@x", email: "o@x", exp: 9999999999 });

  /** The server: rotates r1 → r2 → r3 …, and records every token it was sent. */
  function rotatingServer(delayMs = 10) {
    const sent: string[] = [];
    let n = 1;
    vi.stubGlobal("fetch", async (_url: string, init?: { body?: string }) => {
      sent.push(JSON.parse(init?.body ?? "{}").refresh_token);
      await new Promise((r) => setTimeout(r, delayMs));
      n += 1;
      return {
        ok: true,
        status: 200,
        json: async () => ({ access_token: fresh(), id_token: fresh(), refresh_token: `r${n}` }),
      };
    });
    return sent;
  }

  async function twoTabs() {
    const tabA = await import("./oidc-auth");
    vi.resetModules();
    const tabB = await import("./oidc-auth");
    return [tabA, tabB];
  }

  it("⭐ two tabs renewing at once send ONE token to the server — the second uses the first's result", async () => {
    const locks = fakeLocks();
    vi.stubGlobal("navigator", { locks });
    ls.setItem("grm_refresh_token", "r1");
    const sent = rotatingServer();
    const [a, b] = await twoTabs();

    const [ra, rb] = await Promise.all([a.refreshTokens(), b.refreshTokens()]);

    expect(sent).toEqual(["r1"]); // never r1 twice: that is the reuse that ends the session
    expect(ra).toBeTruthy();
    expect(rb).toBe(ra);
    expect(ls.getItem("grm_refresh_token")).toBe("r2");
    expect(locks.requests.every((r) => r.name === "grm-token-renewal" && r.mode === "exclusive")).toBe(true);
  });

  it("without Web Locks both tabs send the same token — the residual 16_auth_keycloak.md states", async () => {
    // The control for the test above: it is the lock, not luck in the mock, that prevents the reuse.
    vi.stubGlobal("navigator", {});
    ls.setItem("grm_refresh_token", "r1");
    const sent = rotatingServer();
    const [a, b] = await twoTabs();

    await Promise.all([a.refreshTokens(), b.refreshTokens()]);

    expect(sent).toEqual(["r1", "r1"]);
  });

  it("a waiting tab whose rotated access token is ALREADY near expiry renews with the NEW token, never the spent one", async () => {
    const locks = fakeLocks();
    vi.stubGlobal("navigator", { locks });
    ls.setItem("grm_refresh_token", "r1");
    const sent: string[] = [];
    let first = true;
    vi.stubGlobal("fetch", async (_url: string, init?: { body?: string }) => {
      sent.push(JSON.parse(init?.body ?? "{}").refresh_token);
      await new Promise((r) => setTimeout(r, 10));
      // The first renewal hands back an access token that is already inside the 60-second window.
      const access = first ? jwt({ sub: "o@x", email: "o@x", exp: Math.floor(Date.now() / 1000) + 5 }) : fresh();
      const rt = first ? "r2" : "r3";
      first = false;
      return { ok: true, status: 200, json: async () => ({ access_token: access, id_token: fresh(), refresh_token: rt }) };
    });
    const [a, b] = await twoTabs();

    await Promise.all([a.refreshTokens(), b.refreshTokens()]);

    expect(sent).toEqual(["r1", "r2"]);
    expect(ls.getItem("grm_refresh_token")).toBe("r3");
  });

  it("a tab that waited while the officer signed out renews nothing", async () => {
    const locks = fakeLocks();
    vi.stubGlobal("navigator", { locks });
    ls.setItem("grm_refresh_token", "r1");
    const sent: string[] = [];
    vi.stubGlobal("fetch", async (_url: string, init?: { body?: string }) => {
      sent.push(JSON.parse(init?.body ?? "{}").refresh_token);
      await new Promise((r) => setTimeout(r, 10));
      ls.removeItem("grm_refresh_token"); // sign-out lands in another tab mid-renewal
      return { ok: false, status: 401, json: async () => ({}) };
    });
    const [a, b] = await twoTabs();

    const [ra, rb] = await Promise.all([a.refreshTokens(), b.refreshTokens()]);

    expect(sent).toEqual(["r1"]);
    expect(ra).toBeNull();
    expect(rb).toBeNull();
  });

  it("a renewal that hangs gives the lock back, so other tabs are not frozen behind it", async () => {
    vi.useFakeTimers();
    try {
      const locks = fakeLocks();
      vi.stubGlobal("navigator", { locks });
      ls.setItem("grm_refresh_token", "r1");
      vi.stubGlobal("fetch", (_url: string, init?: { signal?: AbortSignal }) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => reject(new Error("aborted")));
        }),
      );
      const { refreshTokens } = await import("./oidc-auth");

      const pending = refreshTokens();
      await vi.advanceTimersByTimeAsync(15_000);

      expect(await pending).toBeNull();
      // The lock is free again: a fresh request runs rather than queueing forever.
      let ran = false;
      await locks.request("grm-token-renewal", { mode: "exclusive" }, async () => {
        ran = true;
      });
      expect(ran).toBe(true);
    } finally {
      vi.useRealTimers();
    }
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
