// SPDX-License-Identifier: Apache-2.0

// PKCE-enabled OIDC client for Keycloak (drop-in replacement for CognitoAuthClient).

import { OIDC_CLIENT_ID, OIDC_ISSUER } from "./runtime-config";
import { isAccessTokenExpired } from "./session-expired";
import {
  TOKEN_STORAGE,
  clearAuthStorage,
  decodeJwt,
  persistAuthTokens,
  type AuthTokens,
  type TokenPayload,
} from "./token-storage";

export type { TokenPayload };

interface TokenResponse extends AuthTokens {
  token_type: string;
}

function base64urlEncode(buffer: Uint8Array): string {
  let str = "";
  buffer.forEach((byte) => { str += String.fromCharCode(byte); });
  return btoa(str).replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
}

/** CSPRNG token for `state`/`nonce` (was `Math.random`, which is not unguessable). */
function randomToken(bytes = 32): string {
  const array = new Uint8Array(bytes);
  crypto.getRandomValues(array);
  return base64urlEncode(array);
}

// ── Silent refresh (H2-01) ────────────────────────────────────────────────────

let refreshPromise: Promise<string | null> | null = null;

/**
 * Exchange the stored refresh token for a fresh access/id/refresh set via the
 * Keycloak refresh-token grant, and persist the rotated tokens. Returns the new
 * access token, or `null` when refresh is impossible (no refresh token / not
 * configured) or the grant is rejected — callers then hard-logout.
 *
 * **Single-flight:** concurrent callers (e.g. a burst of 401s) share one
 * in-flight POST. Keycloak rotates the refresh token, so a second grant with the
 * now-spent token would fail; deduping avoids that self-inflicted 400.
 */
export function refreshTokens(): Promise<string | null> {
  if (refreshPromise) return refreshPromise;
  refreshPromise = doRefresh().finally(() => {
    refreshPromise = null;
  });
  return refreshPromise;
}

async function doRefresh(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  const refreshToken = localStorage.getItem(TOKEN_STORAGE.REFRESH_TOKEN);
  if (!refreshToken || !OIDC_ISSUER || !OIDC_CLIENT_ID) return null;
  try {
    const resp = await fetch(`${OIDC_ISSUER}/protocol/openid-connect/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        grant_type:    "refresh_token",
        client_id:     OIDC_CLIENT_ID,
        refresh_token: refreshToken,
      }).toString(),
    });
    if (!resp.ok) return null;
    const tokens = (await resp.json()) as AuthTokens;
    persistAuthTokens(tokens); // stores rotated access/id/refresh + decoded user
    return tokens.access_token ?? null;
  } catch {
    return null;
  }
}

/**
 * Back-channel logout: invalidate the refresh token (and its Keycloak session)
 * server-side. `keepalive` so it survives the imminent front-channel navigation.
 * Best-effort — a failed revoke must not block sign-out.
 */
function revokeRefreshToken(issuer: string, clientId: string, refreshToken: string): void {
  try {
    void fetch(`${issuer}/protocol/openid-connect/logout`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ client_id: clientId, refresh_token: refreshToken }).toString(),
      keepalive: true,
    });
  } catch {
    /* best-effort */
  }
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
    // state, code_verifier and nonce all live in sessionStorage: a cross-tab login
    // then fails cleanly at the state check (empty in the new tab) instead of
    // reaching the token exchange with an empty verifier.
    const state = randomToken();
    sessionStorage.setItem(TOKEN_STORAGE.STATE, state);

    const nonce = randomToken();
    sessionStorage.setItem(TOKEN_STORAGE.NONCE, nonce);

    const verifier = generateCodeVerifier();
    sessionStorage.setItem(TOKEN_STORAGE.CODE_VERIFIER, verifier);
    const challenge = await generateCodeChallenge(verifier);

    const p = new URLSearchParams({
      client_id:             this.clientId,
      response_type:         "code",
      scope:                 this.scopes.join(" "),
      redirect_uri:          this.redirectUri,
      state,
      nonce,
      code_challenge:        challenge,
      code_challenge_method: "S256",
    });
    return `${this.issuer}/protocol/openid-connect/auth?${p}`;
  }

  async handleCallback(
    code: string,
    state: string,
  ): Promise<{ user: TokenPayload; tokens: TokenResponse }> {
    const stored = sessionStorage.getItem(TOKEN_STORAGE.STATE);
    sessionStorage.removeItem(TOKEN_STORAGE.STATE);
    if (state !== stored) throw new Error("Sign-in session expired. Please try again from the sign-in page.");

    const verifier = sessionStorage.getItem(TOKEN_STORAGE.CODE_VERIFIER) ?? "";
    sessionStorage.removeItem(TOKEN_STORAGE.CODE_VERIFIER);

    const expectedNonce = sessionStorage.getItem(TOKEN_STORAGE.NONCE);
    sessionStorage.removeItem(TOKEN_STORAGE.NONCE);

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

    // Bind the id_token to this browser's auth request (replay protection): the
    // returned nonce must match the one we generated for the authorize call.
    if (expectedNonce && tokens.id_token) {
      const claims = decodeJwt(tokens.id_token);
      if (claims?.nonce !== expectedNonce) {
        throw new Error("Sign-in verification failed. Please try again from the sign-in page.");
      }
    }

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
    if (typeof window === "undefined") return;

    const postLogoutUri = `${window.location.origin}/login`;
    const accessToken = localStorage.getItem(TOKEN_STORAGE.ACCESS_TOKEN);
    const idToken = localStorage.getItem(TOKEN_STORAGE.ID_TOKEN);
    const refreshToken = localStorage.getItem(TOKEN_STORAGE.REFRESH_TOKEN);
    const claims = idToken ? decodeJwt(idToken) : null;
    const azp = typeof claims?.azp === "string" ? claims.azp : undefined;
    const exp = typeof claims?.exp === "number" ? claims.exp : undefined;
    const idTokenFresh = exp != null && exp * 1000 > Date.now() + 30_000;
    const sessionStale =
      !accessToken ||
      !idToken ||
      !idTokenFresh ||
      isAccessTokenExpired(accessToken);

    // Revoke the refresh token server-side before we leave. Matters most on the
    // sessionStale path below, which skips the front-channel logout entirely and
    // would otherwise leave a live refresh token behind.
    if (refreshToken) revokeRefreshToken(this.issuer, this.clientId, refreshToken);

    clearAuthStorage();

    // Stale or missing tokens: skip Keycloak (expired id_token_hint shows an error page).
    if (sessionStale) {
      window.location.replace(postLogoutUri);
      return;
    }

    // Password login uses ticketing-api; PKCE uses ticketing-ui — client_id must match azp.
    const logoutClientId = azp ?? this.clientId;
    const p = new URLSearchParams({
      client_id: logoutClientId,
      id_token_hint: idToken,
      post_logout_redirect_uri: postLogoutUri,
    });
    window.location.href = `${this.issuer}/protocol/openid-connect/logout?${p}`;
  }
}
