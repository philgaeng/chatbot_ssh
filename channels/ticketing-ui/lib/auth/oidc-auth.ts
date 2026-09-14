// SPDX-License-Identifier: Apache-2.0

// PKCE-enabled OIDC client for Keycloak (drop-in replacement for CognitoAuthClient).

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
 * Exchange the stored refresh token for a fresh access/id/refresh set, and persist the
 * rotated tokens. Returns the new access token, or `null` when there is no refresh token
 * or the server refuses it — callers then hard-logout.
 *
 * ⭐ **Through the server, never straight to Keycloak (GRM-104).** Officers sign in with the
 * password form, which issues tokens to `ticketing-api` — a CONFIDENTIAL client whose secret
 * only the server holds. This used to post to Keycloak from the browser as the public
 * `ticketing-ui` client with no secret: the wrong client and no credentials, refused every
 * time, so every officer was signed out when the 1-hour access token expired. It is the same
 * finding the sign-out path made (see `revokeRefreshToken` below). The browser sends ONLY the
 * refresh token; the server picks the client and supplies the secret.
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
  // ⚠ No issuer check any more: this no longer needs one, and the CI-built image has none
  // (images.yml never passes NEXT_PUBLIC_OIDC_ISSUER). Requiring it is what made the old
  // version bail out before even trying on every deployed build.
  if (!refreshToken) return null;
  try {
    // Same-origin, same shape as revokeRefreshToken: no CORS, no client credentials in the browser.
    const resp = await fetch("/api/v1/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
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
 * Back-channel logout: ask the server to revoke the refresh token and end the session.
 * Resolves **true only when the server confirms the session was revoked.**
 *
 * ⭐ **Checked, not fire-and-forget, and that is the point of the design.** The caller uses the
 * answer to decide whether the same-origin redirect is enough or whether it must fall back to
 * the front-channel Keycloak logout. Both bugs found in this file were invisible *because* this
 * result used to be discarded.
 *
 * ⚠ **`revoked` comes from the BODY, not the status.** The endpoint deliberately answers 200
 * even when the revoke fails — a sign-out that returns an error invites a UI that keeps the
 * user signed in — so `resp.ok` is always true and would never trigger the fallback.
 *
 * ⚠ **The browser does not decide how to authenticate this.** Whether a revoke needs a
 * `client_secret` depends on whether the token's client is confidential, a fact about the
 * *realm* that only the server knows. Two earlier versions tried to infer it here and both
 * were wrong. Do not reintroduce a client-identity test.
 */
async function revokeRefreshToken(refreshToken: string, timeoutMs = 3000): Promise<boolean> {
  // A hung request must not strand the user on a page they asked to leave, so the fallback
  // is time-boxed rather than waited on indefinitely.
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const resp = await fetch("/api/v1/auth/logout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
      signal: controller.signal,
    });
    if (!resp.ok) return false;
    const body = (await resp.json()) as { revoked?: boolean };
    return body.revoked === true;
  } catch {
    return false; // aborted, offline, or unparseable — all mean "not confirmed"
  } finally {
    clearTimeout(timer);
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

  async signOut(): Promise<void> {
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
    // Clear BEFORE the round trip: the `storage` event is what signs the user's other tabs
    // out, and they should not keep rendering case data while we wait on the network.
    clearAuthStorage();

    const revoked = refreshToken ? await revokeRefreshToken(refreshToken) : false;

    // ⭐ Happy path: the server confirmed the session is gone, so there is nothing left for
    // Keycloak to end. Staying SAME-ORIGIN is the entire benefit — the cross-origin hop is
    // what spawns a separate window for anyone running this as an app window, and what makes
    // Keycloak log a spurious LOGOUT_ERROR (`session_expired`) against an already-dead
    // session, in the audit log we rely on as breach evidence.
    if (revoked) {
      window.location.replace(postLogoutUri);
      return;
    }

    // Stale or missing tokens: Keycloak cannot help either — an expired `id_token_hint`
    // renders an error page rather than logging anyone out.
    if (sessionStale) {
      window.location.replace(postLogoutUri);
      return;
    }

    // ⚠ FALLBACK, and the reason the front channel is kept at all. The revoke was not
    // confirmed — API down, offline, timed out — so the session may still be live. This is a
    // browser NAVIGATION, which the browser guarantees to run, where the fetch above is
    // best-effort. It also clears Keycloak's own cookie, which the back channel never does.
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
