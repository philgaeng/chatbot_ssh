// PKCE-enabled OIDC client for Keycloak (drop-in replacement for CognitoAuthClient).
// Same public interface — only endpoint URLs and PKCE handling change.

export interface TokenPayload {
  sub: string;
  email: string;
  email_verified: boolean;
  name?: string;
  "custom:grm_roles"?: string;       // comma-separated role keys
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
  ACCESS_TOKEN:  "grm_access_token",
  ID_TOKEN:      "grm_id_token",
  REFRESH_TOKEN: "grm_refresh_token",
  USER:          "grm_user",
  STATE:         "grm_oauth_state",
  CODE_VERIFIER: "grm_pkce_verifier",  // sessionStorage — ephemeral
} as const;

function rand(len: number): string {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  return Array.from({ length: len }, () => chars[Math.floor(Math.random() * chars.length)]).join("");
}

function base64urlEncode(buffer: Uint8Array): string {
  let str = "";
  buffer.forEach((byte) => { str += String.fromCharCode(byte); });
  return btoa(str).replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
}

function generateCodeVerifier(): string {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return base64urlEncode(array);
}

async function generateCodeChallenge(verifier: string): Promise<string> {
  const data = new TextEncoder().encode(verifier);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return base64urlEncode(new Uint8Array(digest));
}

function decodeJwt(token: string): TokenPayload | null {
  try {
    const payload = token.split(".")[1];
    return JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
  } catch {
    return null;
  }
}

export class OIDCAuthClient {
  constructor(
    private issuer: string,        // e.g. http://localhost:8080/realms/grm
    private clientId: string,
    private redirectUri: string,
    private scopes = ["email", "openid", "profile"],
  ) {}

  async getAuthorizationUrl(): Promise<string> {
    const state = rand(32);
    localStorage.setItem(STORAGE.STATE, state);

    const verifier = generateCodeVerifier();
    sessionStorage.setItem(STORAGE.CODE_VERIFIER, verifier);
    const challenge = await generateCodeChallenge(verifier);

    const p = new URLSearchParams({
      client_id:             this.clientId,
      response_type:         "code",
      scope:                 this.scopes.join(" "),
      redirect_uri:          this.redirectUri,
      state,
      code_challenge:        challenge,
      code_challenge_method: "S256",
    });
    return `${this.issuer}/protocol/openid-connect/auth?${p}`;
  }

  async handleCallback(
    code: string,
    state: string,
  ): Promise<{ user: TokenPayload; tokens: TokenResponse }> {
    const stored = localStorage.getItem(STORAGE.STATE);
    localStorage.removeItem(STORAGE.STATE);
    if (state !== stored) throw new Error("State mismatch — possible CSRF attack");

    const verifier = sessionStorage.getItem(STORAGE.CODE_VERIFIER) ?? "";
    sessionStorage.removeItem(STORAGE.CODE_VERIFIER);

    const resp = await fetch(`${this.issuer}/protocol/openid-connect/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        grant_type:    "authorization_code",
        client_id:     this.clientId,
        code,
        redirect_uri:  this.redirectUri,
        code_verifier: verifier,
      }).toString(),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error((err as Record<string, string>).error_description ?? "Token exchange failed");
    }
    const tokens: TokenResponse = await resp.json();
    // Use id_token for user claims (access_token for API calls)
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
    const idToken = localStorage.getItem(STORAGE.ID_TOKEN);
    Object.values(STORAGE).forEach((k) => {
      localStorage.removeItem(k);
      sessionStorage.removeItem(k);
    });
    const postLogoutUri = typeof window !== "undefined"
      ? `${window.location.origin}/login`
      : "";
    const p = new URLSearchParams({ client_id: this.clientId });
    if (idToken) p.set("id_token_hint", idToken);
    if (postLogoutUri) p.set("post_logout_redirect_uri", postLogoutUri);
    window.location.href = `${this.issuer}/protocol/openid-connect/logout?${p}`;
  }
}
