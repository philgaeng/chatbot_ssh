// SPDX-License-Identifier: Apache-2.0

/**
 * Cross-tab sign-out.
 *
 * Reported behaviour: signing out in one tab left a second tab rendering the app — signed in
 * to look at, showing stale case data — until the user clicked something and an API call
 * 401'd. `storage` events fire only in OTHER tabs, which is exactly the missing signal.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

function storageEvent(key: string | null, newValue: string | null, area?: unknown): StorageEvent {
  return { key, newValue, storageArea: area ?? localStorage } as unknown as StorageEvent;
}

let replaced: string[];

beforeEach(async () => {
  vi.resetModules();
  replaced = [];
  const listeners: Record<string, ((e: unknown) => void)[]> = {};
  vi.stubGlobal("localStorage", {
    getItem: () => null,
    setItem: () => {},
    removeItem: () => {},
  });
  vi.stubGlobal("sessionStorage", { removeItem: () => {} });
  vi.stubGlobal("window", {
    localStorage: globalThis.localStorage,
    location: { pathname: "/queue", replace: (u: string) => replaced.push(u) },
    addEventListener: (t: string, fn: (e: unknown) => void) => {
      (listeners[t] ??= []).push(fn);
    },
    removeEventListener: (t: string, fn: (e: unknown) => void) => {
      listeners[t] = (listeners[t] ?? []).filter((f) => f !== fn);
    },
    _fire: (t: string, e: unknown) => (listeners[t] ?? []).forEach((f) => f(e)),
  });
});

afterEach(() => vi.unstubAllGlobals());

describe("isSignedOutElsewhere", () => {
  it("a removed auth token means signed out elsewhere", async () => {
    const { isSignedOutElsewhere } = await import("./session-expired");
    expect(isSignedOutElsewhere(storageEvent("grm_access_token", null))).toBe(true);
    expect(isSignedOutElsewhere(storageEvent("grm_refresh_token", null))).toBe(true);
  });

  it("⭐ a token REFRESH must not sign other tabs out", async () => {
    // The false positive that would matter most: `persistAuthTokens` writes rotated tokens
    // with setItem, so newValue is non-null. Keying on "changed" instead of "removed" would
    // log every other tab out on every refresh.
    const { isSignedOutElsewhere } = await import("./session-expired");
    expect(isSignedOutElsewhere(storageEvent("grm_access_token", "a-new-token"))).toBe(false);
  });

  it("localStorage.clear() (key === null) counts as signed out", async () => {
    const { isSignedOutElsewhere } = await import("./session-expired");
    expect(isSignedOutElsewhere(storageEvent(null, null))).toBe(true);
  });

  it("an unrelated key is ignored", async () => {
    const { isSignedOutElsewhere } = await import("./session-expired");
    expect(isSignedOutElsewhere(storageEvent("theme", null))).toBe(false);
  });

  it("sessionStorage events are ignored", async () => {
    const { isSignedOutElsewhere } = await import("./session-expired");
    expect(isSignedOutElsewhere(storageEvent("grm_access_token", null, { other: true }))).toBe(false);
  });
});

describe("installCrossTabSignOut", () => {
  it("redirects this tab to /login when another signs out", async () => {
    const { installCrossTabSignOut } = await import("./session-expired");
    installCrossTabSignOut();
    (window as unknown as { _fire: (t: string, e: unknown) => void })._fire(
      "storage",
      storageEvent("grm_access_token", null),
    );
    expect(replaced).toEqual(["/login"]);
  });

  it("⚠ does not claim the session expired — the user signed out on purpose", async () => {
    const { installCrossTabSignOut } = await import("./session-expired");
    installCrossTabSignOut();
    (window as unknown as { _fire: (t: string, e: unknown) => void })._fire(
      "storage",
      storageEvent("grm_access_token", null),
    );
    expect(replaced[0]).not.toContain("reason=");
  });

  it("does nothing when already on /login (no redirect loop)", async () => {
    (window as unknown as { location: { pathname: string } }).location.pathname = "/login";
    const { installCrossTabSignOut } = await import("./session-expired");
    installCrossTabSignOut();
    (window as unknown as { _fire: (t: string, e: unknown) => void })._fire(
      "storage",
      storageEvent("grm_access_token", null),
    );
    expect(replaced).toEqual([]);
  });

  it("ignores a refresh, so a busy tab does not evict its siblings", async () => {
    const { installCrossTabSignOut } = await import("./session-expired");
    installCrossTabSignOut();
    (window as unknown as { _fire: (t: string, e: unknown) => void })._fire(
      "storage",
      storageEvent("grm_access_token", "rotated"),
    );
    expect(replaced).toEqual([]);
  });

  it("uninstalls cleanly", async () => {
    const { installCrossTabSignOut } = await import("./session-expired");
    installCrossTabSignOut()();
    (window as unknown as { _fire: (t: string, e: unknown) => void })._fire(
      "storage",
      storageEvent("grm_access_token", null),
    );
    expect(replaced).toEqual([]);
  });
});
