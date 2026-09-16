// SPDX-License-Identifier: Apache-2.0

/**
 * Canonical frontend auth config — the single source for the auth mode + OIDC issuer.
 *
 * Derived from the canonical AUTH_MODE / KEYCLOAK_ISSUER scheme (CL-03), mirrored to
 * NEXT_PUBLIC_* build args and inlined by Next at build time:
 *   - NEXT_PUBLIC_AUTH_MODE   ← AUTH_MODE       (keycloak | bypass)
 *   - NEXT_PUBLIC_OIDC_ISSUER ← KEYCLOAK_ISSUER (browser-facing issuer URL)
 *
 * Do NOT read process.env.NEXT_PUBLIC_AUTH_MODE for auth decisions anywhere else —
 * import AUTH_BYPASS / OIDC_ISSUER from here.
 */

/** Dev auth bypass — honoured only when the build was made with AUTH_MODE=bypass. */
export const AUTH_BYPASS = process.env.NEXT_PUBLIC_AUTH_MODE === "bypass";

/** The realm every deployment uses — matches `ticketing/services/auth_login.py` (`/realms/grm`). */
export const OIDC_REALM = "grm";

/**
 * Resolve the browser-facing Keycloak issuer (GRM-104).
 *
 * An explicitly configured issuer wins. With none — and **every CI-built image has none**, because
 * `images.yml` never passes `NEXT_PUBLIC_OIDC_ISSUER` — it is derived from the page's own origin,
 * the same pattern the redirect URI already uses (`${window.location.origin}/auth/callback`).
 * Every deployment proxies `/keycloak/` on the UI's host, and Keycloak keeps advertising its pinned
 * issuer whichever host it is reached on (verified on staging 2026-09-14), so backend token
 * validation is unaffected.
 *
 * ⚠ **What this still serves, now that refresh does not need it:** the front-channel sign-out
 * FALLBACK, which navigated to a relative `/protocol/openid-connect/logout` with an empty issuer.
 *
 * ⚠ Returns `""` when neither is available (server render, bypass build) — never a relative URL,
 * which would resolve silently against whatever page is open.
 */
export function resolveOidcIssuer(configured: string | undefined, origin: string | undefined): string {
  const explicit = (configured ?? "").trim().replace(/\/+$/, "");
  if (explicit) return explicit;
  const base = (origin ?? "").trim().replace(/\/+$/, "");
  return base ? `${base}/keycloak/realms/${OIDC_REALM}` : "";
}

/** Browser-facing Keycloak issuer — configured, else same-origin; empty only with no origin. */
export const OIDC_ISSUER = resolveOidcIssuer(
  process.env.NEXT_PUBLIC_OIDC_ISSUER,
  typeof window !== "undefined" ? window.location?.origin : undefined,
);

/** OIDC client id for the officer UI (public PKCE client). */
export const OIDC_CLIENT_ID = process.env.NEXT_PUBLIC_OIDC_CLIENT_ID ?? "ticketing-ui";
