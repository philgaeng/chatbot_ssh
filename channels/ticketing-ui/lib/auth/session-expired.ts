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

/** True when a JWT access token is past its `exp` claim (with 30s skew). */
export function isAccessTokenExpired(token: string): boolean {
  try {
    const payload = JSON.parse(
      atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")),
    ) as { exp?: number };
    if (!payload.exp) return false;
    return payload.exp * 1000 < Date.now() - 30_000;
  } catch {
    return false;
  }
}

/** Detect ticketing API 401 responses that mean re-login is required. */
export function isSessionExpiredResponse(status: number, body: string): boolean {
  if (status !== 401) return false;
  let detail = body;
  try {
    const parsed = JSON.parse(body) as { detail?: string | string[] };
    if (typeof parsed.detail === "string") detail = parsed.detail;
    else if (Array.isArray(parsed.detail)) detail = parsed.detail.join(" ");
  } catch {
    /* use raw body */
  }
  const lower = detail.toLowerCase();
  return (
    lower.includes("expired") ||
    lower.includes("invalid token") ||
    lower.includes("not authenticated") ||
    lower.includes("could not validate") ||
    lower.includes("credentials")
  );
}

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
