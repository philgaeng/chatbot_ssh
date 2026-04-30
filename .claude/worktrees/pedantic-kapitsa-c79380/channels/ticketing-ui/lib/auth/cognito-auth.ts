// Custom OAuth2 client for AWS Cognito — no heavy OIDC library needed.
// Copied pattern from Stratcon, adapted for GRM ticketing pool.

export interface TokenPayload {
  sub: string;
  email: string;
  email_verified: boolean;
  name?: string;
  "custom:grm_roles"?: string;      // comma-separated role keys
  "custom:organization_id"?: string;
  "custom:location_code"?: string;
  [key: string]: unknown;
}

interface TokenResponse {
  access_token: string;
  id_token: string;
  refresh_token?: string;
  expires_in: number;
  token_type: string;
}

const STORAGE = {
  ACCESS_TOKEN: "grm_access_token",
  ID_TOKEN: "grm_id_token",
  REFRESH_TOKEN: "grm_refresh_token",
  USER: "grm_user",
  STATE: "grm_oauth_state",
} as const;

function rand(len: number) {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  return Array.from({ length: len }, () => chars[Math.floor(Math.random() * chars.length)]).join("");
}

function decodeJwt(token: string): TokenPayload | null {
  try {
    const payload = token.split(".")[1];
    return JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
  } catch {
    return null;
  }
}

export class CognitoAuthClient {
  constructor(
    private domain: string,
    private clientId: string,
    private redirectUri: string,
    private scopes = ["email", "openid", "profile"],
  ) {}

  getAuthorizationUrl(): string {
    const state = rand(32);
    localStorage.setItem(STORAGE.STATE, state);
    const p = new URLSearchParams({
      client_id: this.clientId,
      response_type: "code",
      scope: this.scopes.join(" "),
      redirect_uri: this.redirectUri,
      state,
    });
    return `${this.domain}/oauth2/authorize?${p}`;
  }

  async handleCallback(code: string, state: string): Promise<{ user: TokenPayload; tokens: TokenResponse }> {
    const stored = localStorage.getItem(STORAGE.STATE);
    localStorage.removeItem(STORAGE.STATE);
    if (state !== stored) throw new Error("State mismatch — possible CSRF attack");

    const resp = await fetch(`${this.domain}/oauth2/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        grant_type: "authorization_code",
        client_id: this.clientId,
        code,
        redirect_uri: this.redirectUri,
      }).toString(),
    });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.error_description || "Token exchange failed");
    }
    const tokens: TokenResponse = await resp.json();
    const user = decodeJwt(tokens.id_token);
    if (!user) throw new Error("Failed to decode id_token");

    localStorage.setItem(STORAGE.ACCESS_TOKEN, tokens.access_token);
    localStorage.setItem(STORAGE.ID_TOKEN, tokens.id_token);
    if (tokens.refresh_token) localStorage.setItem(STORAGE.REFRESH_TOKEN, tokens.refresh_token);
    localStorage.setItem(STORAGE.USER, JSON.stringify(user));
    return { user, tokens };
  }

  getCurrentUser(): TokenPayload | null {
    const json = localStorage.getItem(STORAGE.USER);
    return json ? JSON.parse(json) : null;
  }

  getAccessToken(): string | null {
    return localStorage.getItem(STORAGE.ACCESS_TOKEN);
  }

  isAuthenticated(): boolean {
    return !!localStorage.getItem(STORAGE.ACCESS_TOKEN);
  }

  signOut(): void {
    Object.values(STORAGE).forEach((k) => localStorage.removeItem(k));
    const logoutUrl = `${this.domain}/logout?client_id=${this.clientId}&logout_uri=${encodeURIComponent(
      typeof window !== "undefined" ? `${window.location.origin}/login` : ""
    )}`;
    window.location.href = logoutUrl;
  }
}
