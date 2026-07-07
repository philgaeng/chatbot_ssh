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

/** Browser-facing Keycloak issuer (empty in a bypass build). */
export const OIDC_ISSUER = process.env.NEXT_PUBLIC_OIDC_ISSUER ?? "";

/** OIDC client id for the officer UI (public PKCE client). */
export const OIDC_CLIENT_ID = process.env.NEXT_PUBLIC_OIDC_CLIENT_ID ?? "ticketing-ui";
