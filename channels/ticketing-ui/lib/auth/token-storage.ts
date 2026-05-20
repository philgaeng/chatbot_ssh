export interface TokenPayload {
  sub: string;
  email: string;
  email_verified: boolean;
  name?: string;
  "custom:grm_roles"?: string;
  "custom:organization_id"?: string;
  "custom:location_code"?: string;
  [key: string]: unknown;
}

export interface AuthTokens {
  access_token: string;
  id_token?: string | null;
  refresh_token?: string | null;
  expires_in?: number;
  token_type?: string;
}

export const TOKEN_STORAGE = {
  ACCESS_TOKEN: "grm_access_token",
  ID_TOKEN: "grm_id_token",
  REFRESH_TOKEN: "grm_refresh_token",
  USER: "grm_user",
  STATE: "grm_oauth_state",
  CODE_VERIFIER: "grm_pkce_verifier",
  LOGIN_EMAIL: "grm_login_email",
} as const;

export function decodeJwt(token: string): TokenPayload | null {
  try {
    const payload = token.split(".")[1];
    return JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
  } catch {
    return null;
  }
}

export function persistAuthTokens(tokens: AuthTokens): TokenPayload {
  const user =
    (tokens.id_token ? decodeJwt(tokens.id_token) : null) ??
    (tokens.access_token ? decodeJwt(tokens.access_token) : null);
  if (!user?.email && !user?.sub) {
    throw new Error("Failed to read account details from sign-in token.");
  }

  localStorage.setItem(TOKEN_STORAGE.ACCESS_TOKEN, tokens.access_token);
  if (tokens.id_token) localStorage.setItem(TOKEN_STORAGE.ID_TOKEN, tokens.id_token);
  if (tokens.refresh_token) localStorage.setItem(TOKEN_STORAGE.REFRESH_TOKEN, tokens.refresh_token);
  localStorage.setItem(TOKEN_STORAGE.USER, JSON.stringify(user));
  return user;
}

export function clearAuthStorage(): void {
  Object.values(TOKEN_STORAGE).forEach((k) => {
    localStorage.removeItem(k);
    sessionStorage.removeItem(k);
  });
}

export function rememberLoginEmail(email: string): void {
  localStorage.setItem(TOKEN_STORAGE.LOGIN_EMAIL, email.trim().toLowerCase());
}

export function readRememberedLoginEmail(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_STORAGE.LOGIN_EMAIL);
}
