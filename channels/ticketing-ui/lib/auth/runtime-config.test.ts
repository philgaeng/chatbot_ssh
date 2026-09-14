// SPDX-License-Identifier: Apache-2.0

/**
 * GRM-104 — the Keycloak issuer resolves from the page's own origin when a build carries none.
 *
 * `NEXT_PUBLIC_OIDC_ISSUER` is inlined at BUILD time, and `images.yml` never passes it, so every
 * CI-built UI image shipped with an empty issuer. Refresh no longer depends on it (it runs through
 * `/api/v1/auth/refresh`), but the front-channel sign-out FALLBACK does — it navigated to a relative
 * `/protocol/openid-connect/logout`. Deriving the issuer from the origin repairs that, and matches
 * the pattern the redirect URI already uses (`${window.location.origin}/auth/callback`).
 */
import { afterEach, describe, expect, it, vi } from "vitest";

import { resolveOidcIssuer } from "./runtime-config";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("resolveOidcIssuer", () => {
  it("an explicitly configured issuer wins over the origin", () => {
    expect(resolveOidcIssuer("https://kc.example/keycloak/realms/grm", "https://grm-auth.example")).toBe(
      "https://kc.example/keycloak/realms/grm",
    );
  });

  it("with none configured, derives the same-origin realm URL", () => {
    // Staging proxies /keycloak/ on every host, and Keycloak still advertises its pinned issuer —
    // verified 2026-09-14 against grm-auth.nepal-gms-chatbot.facets-ai.com.
    expect(resolveOidcIssuer("", "https://grm-auth.example")).toBe("https://grm-auth.example/keycloak/realms/grm");
    expect(resolveOidcIssuer(undefined, "https://grm-auth.example")).toBe(
      "https://grm-auth.example/keycloak/realms/grm",
    );
  });

  it("never produces a double slash or a trailing one", () => {
    expect(resolveOidcIssuer("https://kc.example/realms/grm/", undefined)).toBe("https://kc.example/realms/grm");
    expect(resolveOidcIssuer("   ", "https://grm-auth.example/")).toBe("https://grm-auth.example/keycloak/realms/grm");
  });

  it("with neither — server render, bypass build — is empty, never a relative URL", () => {
    // An empty issuer is a detectable "not configured"; "/keycloak/realms/grm" would be a URL that
    // silently resolves against whatever page happens to be open.
    expect(resolveOidcIssuer(undefined, undefined)).toBe("");
    expect(resolveOidcIssuer("", "")).toBe("");
  });
});

describe("OIDC_ISSUER as the browser sees it", () => {
  it("resolves from window.location.origin in a build with no configured issuer", async () => {
    vi.stubEnv("NEXT_PUBLIC_OIDC_ISSUER", "");
    vi.stubGlobal("window", { location: { origin: "https://grm-auth.example" } });
    const { OIDC_ISSUER } = await import("./runtime-config");
    expect(OIDC_ISSUER).toBe("https://grm-auth.example/keycloak/realms/grm");
  });

  it("keeps an explicitly built-in issuer exactly as configured", async () => {
    vi.stubEnv("NEXT_PUBLIC_OIDC_ISSUER", "https://nepal-gms-chatbot.facets-ai.com/keycloak/realms/grm");
    vi.stubGlobal("window", { location: { origin: "https://grm-auth.example" } });
    const { OIDC_ISSUER } = await import("./runtime-config");
    expect(OIDC_ISSUER).toBe("https://nepal-gms-chatbot.facets-ai.com/keycloak/realms/grm");
  });
});
