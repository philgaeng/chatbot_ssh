/** Query param on /login when the user was sent here after an expired OIDC token. */
export const SESSION_EXPIRED_QUERY = "session_expired";

const AUTH_STORAGE_KEYS = [
  "grm_access_token",
  "grm_id_token",
  "grm_refresh_token",
  "grm_user",
  "grm_oauth_state",
] as const;

let redirecting = false;

export class SessionExpiredError extends Error {
  constructor(message = "Your session has expired. Please sign in again.") {
    super(message);
    this.name = "SessionExpiredError";
  }
}

/**
 * True when a JWT access token expires within `withinSeconds` from now. This is
 * the proactive-refresh trigger (H2-01): `apiFetch` refreshes a token that is
 * about to expire *before* firing the request, rather than eating a 401.
 */
export function isAccessTokenExpiringSoon(token: string, withinSeconds: number): boolean {
  try {
    const payload = JSON.parse(
      atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")),
    ) as { exp?: number };
    if (!payload.exp) return false;
    return payload.exp * 1000 < Date.now() + withinSeconds * 1000;
  } catch {
    return false;
  }
}

/**
 * True when a JWT access token is at/near its `exp` claim. Treats the token as
 * expired 30s *before* the real deadline (H2-01: the old check was inverted —
 * `Date.now() - 30_000` kept a token "valid" 30s past expiry, guaranteeing a 401
 * window; it now refreshes early instead).
 */
export function isAccessTokenExpired(token: string): boolean {
  return isAccessTokenExpiringSoon(token, 30);
}

// isSessionExpiredResponse was retired (2026-07-15): every 401 path now routes through the
// status-code-based refresh+retry in apiFetch (JSON) or authedFetch (blob/multipart), so the
// substring body-sniffing heuristic is no longer needed.

export function clearAuthTokens(): void {
  if (typeof window === "undefined") return;
  for (const key of AUTH_STORAGE_KEYS) {
    localStorage.removeItem(key);
    sessionStorage.removeItem(key);
  }
}

/** Clear tokens and send the user to login with a friendly reason (client only). */
export function handleSessionExpired(): never {
  if (typeof window === "undefined") {
    throw new SessionExpiredError();
  }
  if (!redirecting) {
    redirecting = true;
    clearAuthTokens();
    const loginUrl = `/login?reason=${SESSION_EXPIRED_QUERY}`;
    window.location.replace(loginUrl);
  }
  throw new SessionExpiredError();
}

export function isSessionExpiredError(err: unknown): boolean {
  return err instanceof SessionExpiredError;
}
