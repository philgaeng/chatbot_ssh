// PKCE-enabled OIDC client for Keycloak (drop-in replacement for CognitoAuthClient).

import {
  TOKEN_STORAGE,
  persistAuthTokens,
  type AuthTokens,
  type TokenPayload,
} from "./token-storage";

export type { TokenPayload };

interface TokenResponse extends AuthTokens {
  token_type: string;
}

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

export class OIDCAuthClient {
  constructor(
    private issuer: string,
    private clientId: string,
    private redirectUri: string,
    private scopes = ["email", "openid", "profile"],
  ) {}

  async getAuthorizationUrl(): Promise<string> {
    const state = rand(32);
    localStorage.setItem(TOKEN_STORAGE.STATE, state);

    const verifier = generateCodeVerifier();
    sessionStorage.setItem(TOKEN_STORAGE.CODE_VERIFIER, verifier);
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
    const stored = localStorage.getItem(TOKEN_STORAGE.STATE);
    localStorage.removeItem(TOKEN_STORAGE.STATE);
    if (state !== stored) throw new Error("Sign-in session expired. Please try again from the sign-in page.");

    const verifier = sessionStorage.getItem(TOKEN_STORAGE.CODE_VERIFIER) ?? "";
    sessionStorage.removeItem(TOKEN_STORAGE.CODE_VERIFIER);

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
      throw new Error((err as Record<string, string>).error_description ?? "Token exchange failed. Please sign in again.");
    }
    const tokens: TokenResponse = await resp.json();
    const user = persistAuthTokens(tokens);
    return { user, tokens };
  }

  getCurrentUser(): TokenPayload | null {
    const json = localStorage.getItem(TOKEN_STORAGE.USER);
    return json ? JSON.parse(json) : null;
  }

  getAccessToken(): string | null {
    return localStorage.getItem(TOKEN_STORAGE.ACCESS_TOKEN);
  }

  isAuthenticated(): boolean {
    return !!localStorage.getItem(TOKEN_STORAGE.ACCESS_TOKEN);
  }

  signOut(): void {
    const idToken = localStorage.getItem(TOKEN_STORAGE.ID_TOKEN);
    Object.values(TOKEN_STORAGE).forEach((k) => {
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
