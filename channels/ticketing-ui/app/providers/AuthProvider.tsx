"use client";

import React, { createContext, useContext, useEffect, useState, Suspense, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { OIDCAuthClient, type TokenPayload } from "@/lib/auth/oidc-auth";
import { getUserPreferences, listOfficerRoster, type OfficerRosterEntry } from "@/lib/api";

// ── Demo / dev bypass (NEXT_PUBLIC_BYPASS_AUTH=true) ─────────────────────────
// No OIDC: the Next.js proxy reads `grm_bypass_user` and forwards internal
// identity headers. Officer choices come from GET /api/v1/users/roster (DB),
// not a hardcoded list — same data as production, with one-click role switching.

const BYPASS_COOKIE = "grm_bypass_user";
const LEGACY_MOCK_COOKIE = "grm_mock_user";

/** Matches ticketing `get_current_user` when no cookie is sent. */
const DEFAULT_BYPASS_USER_ID = "mock-super-admin";

function fallbackBypassToken(): TokenPayload {
  return {
    sub: DEFAULT_BYPASS_USER_ID,
    email: "admin@grm.local",
    name: "Super Admin",
    email_verified: true,
    "custom:grm_roles": "super_admin",
    "custom:organization_id": "DOR",
  };
}

function tokenFromRosterRow(o: OfficerRosterEntry): TokenPayload {
  const email =
    o.email ?? (o.user_id.includes("@") ? o.user_id : `${o.user_id}@bypass.local`);
  const orgId = o.organization_ids[0] ?? "";
  const loc = o.location_codes[0];
  return {
    sub: o.user_id,
    email,
    email_verified: true,
    name: o.display_name,
    "custom:grm_roles": o.role_keys.join(","),
    "custom:organization_id": orgId,
    ...(loc ? { "custom:location_code": loc } : {}),
  };
}

function pickDefaultOfficer(roster: OfficerRosterEntry[]): OfficerRosterEntry | null {
  if (roster.length === 0) return null;
  const privileged = roster.filter((r) =>
    r.role_keys.some((k) => k === "super_admin" || k === "local_admin"),
  );
  const pool = privileged.length ? privileged : roster;
  return [...pool].sort((a, b) => a.display_name.localeCompare(b.display_name))[0];
}

function clearCookie(name: string): void {
  if (typeof document === "undefined") return;
  document.cookie = `${name}=; path=/; max-age=0`;
}

/** Read bypass cookie JSON (raw value after =). */
function readBypassCookieRaw(): string | null {
  if (typeof document === "undefined") return null;
  const m = document.cookie.match(new RegExp(`(?:^|; )${BYPASS_COOKIE}=([^;]*)`));
  if (m) return m[1];
  const leg = document.cookie.match(new RegExp(`(?:^|; )${LEGACY_MOCK_COOKIE}=([^;]*)`));
  return leg ? leg[1] : null;
}

function parseBypassCookie(raw: string): {
  user_id: string;
  role_keys: string[];
  organization_id?: string;
} | null {
  try {
    const o = JSON.parse(raw) as {
      user_id?: string;
      role_keys?: string[];
      organization_id?: string;
    };
    if (!o.user_id || !Array.isArray(o.role_keys)) return null;
    return {
      user_id: o.user_id,
      role_keys: o.role_keys,
      organization_id: o.organization_id,
    };
  } catch {
    return null;
  }
}

/** Persist identity for the API route proxy (must stay JSON, not URL-encoded). */
export function setBypassUserCookie(entry: OfficerRosterEntry | null): void {
  if (typeof document === "undefined") return;
  clearCookie(LEGACY_MOCK_COOKIE);
  if (!entry) {
    clearCookie(BYPASS_COOKIE);
    return;
  }
  const orgId = entry.organization_ids[0] ?? "";
  const value = JSON.stringify({
    user_id: entry.user_id,
    role_keys: entry.role_keys,
    organization_id: orgId || undefined,
  });
  document.cookie = `${BYPASS_COOKIE}=${value}; path=/; max-age=86400`;
}

// ── Auth context ─────────────────────────────────────────────────────────────

export interface AuthContextValue {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: TokenPayload | null;
  error: string | null;
  /** Current user's role keys (from custom:grm_roles or OIDC) */
  roleKeys: string[];
  canSeeSeah: boolean;
  isAdmin: boolean;
  signIn: () => void;
  signOut: () => void;
  /** Bearer token for API calls (null in bypass mode) */
  accessToken: string | null;
  effectiveLang: "en" | "ne" | null;
  /**
   * Bypass mode: roster from DB for the header role switcher (null until first fetch).
   */
  bypassRoster: OfficerRosterEntry[] | null;
  bypassRosterError: string | null;
  /**
   * Bypass mode only: switch to another officer from `ticketing.user_roles`.
   * Sets cookie + reloads queue so API calls use the new identity.
   */
  switchBypassUser: (entry: OfficerRosterEntry) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

const SEAH_CAN_SEE_ROLES = new Set(["super_admin", "adb_hq_exec", "seah_national_officer", "seah_hq_officer"]);
const ADMIN_ROLES = new Set(["super_admin", "local_admin"]);

function derivePermissions(roleKeys: string[]) {
  return {
    canSeeSeah: roleKeys.some((r) => SEAH_CAN_SEE_ROLES.has(r)),
    isAdmin: roleKeys.some((r) => ADMIN_ROLES.has(r)),
  };
}

function AuthProviderInner({ children }: { children: React.ReactNode }) {
  const bypass = process.env.NEXT_PUBLIC_BYPASS_AUTH === "true";
  const searchParams = useSearchParams();

  const [isAuthenticated, setIsAuthenticated] = useState(bypass);
  const [isLoading, setIsLoading] = useState(!bypass);
  const [user, setUser] = useState<TokenPayload | null>(bypass ? fallbackBypassToken() : null);
  const [error, setError] = useState<string | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [effectiveLang, setEffectiveLang] = useState<"en" | "ne" | null>(null);
  const [bypassRoster, setBypassRoster] = useState<OfficerRosterEntry[] | null>(bypass ? null : []);
  const [bypassRosterError, setBypassRosterError] = useState<string | null>(null);

  const client = !bypass
    ? new OIDCAuthClient(
        process.env.NEXT_PUBLIC_OIDC_ISSUER ?? "",
        process.env.NEXT_PUBLIC_OIDC_CLIENT_ID ?? "",
        typeof window !== "undefined"
          ? `${window.location.origin}/auth/callback`
          : (process.env.NEXT_PUBLIC_REDIRECT_SIGN_IN ?? ""),
      )
    : null;

  // Bypass: load roster from DB, reconcile cookie + React user (matches proxy headers).
  useEffect(() => {
    if (!bypass) return;
    let cancelled = false;
    (async () => {
      try {
        const roster = await listOfficerRoster();
        if (cancelled) return;
        setBypassRoster(roster);
        setBypassRosterError(null);

        const raw = readBypassCookieRaw();
        const parsed = raw ? parseBypassCookie(raw) : null;
        let chosen: OfficerRosterEntry | null = null;
        if (parsed) {
          chosen =
            roster.find((r) => r.user_id === parsed.user_id) ??
            ({
              user_id: parsed.user_id,
              display_name: parsed.user_id,
              email: parsed.user_id.includes("@") ? parsed.user_id : null,
              role_keys: parsed.role_keys,
              organization_ids: parsed.organization_id ? [parsed.organization_id] : [],
              location_codes: [],
              onboarding_status: "active",
            } satisfies OfficerRosterEntry);
        }
        if (!chosen) {
          chosen = pickDefaultOfficer(roster);
        }
        if (chosen) {
          setBypassUserCookie(chosen);
          setUser(tokenFromRosterRow(chosen));
        } else {
          clearCookie(BYPASS_COOKIE);
          setUser(fallbackBypassToken());
        }
      } catch (e) {
        if (!cancelled) {
          setBypassRoster([]);
          setBypassRosterError(e instanceof Error ? e.message : "Failed to load roster");
          setUser(fallbackBypassToken());
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [bypass]);

  useEffect(() => {
    if (bypass) return;

    const code = searchParams.get("code");
    const state = searchParams.get("state");
    const errParam = searchParams.get("error");

    if (errParam) {
      setError(searchParams.get("error_description") ?? errParam);
      setIsLoading(false);
      return;
    }

    if (code && state && client) {
      client
        .handleCallback(code, state)
        .then(({ user: u, tokens }) => {
          setUser(u);
          setAccessToken(tokens.access_token);
          setIsAuthenticated(true);
          window.location.href = "/queue";
        })
        .catch((e) => setError(String(e)))
        .finally(() => setIsLoading(false));
      return;
    }

    if (client) {
      const existing = client.getCurrentUser();
      if (existing) {
        setUser(existing);
        setAccessToken(client.getAccessToken());
        setIsAuthenticated(true);
      }
    }
    setIsLoading(false);
  }, [bypass, searchParams]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!isAuthenticated || isLoading) return;
    getUserPreferences()
      .then((prefs) => setEffectiveLang(prefs.effective_language as "en" | "ne"))
      .catch(() => setEffectiveLang("en"));
  }, [isAuthenticated, isLoading]); // eslint-disable-line react-hooks/exhaustive-deps

  const signIn = async () => {
    if (bypass) {
      setIsAuthenticated(true);
      window.location.href = "/queue";
    } else {
      window.location.href = await client!.getAuthorizationUrl();
    }
  };

  const signOut = () => {
    if (bypass) {
      setIsAuthenticated(false);
      setUser(null);
      setBypassUserCookie(null);
      window.location.href = "/login";
    } else {
      client!.signOut();
    }
  };

  const switchBypassUser = useCallback((entry: OfficerRosterEntry) => {
    setBypassUserCookie(entry);
    setUser(tokenFromRosterRow(entry));
    window.location.href = "/queue";
  }, []);

  const roleKeys = ((user?.["custom:grm_roles"] as string | undefined) ?? "")
    .split(",")
    .map((r) => r.trim())
    .filter(Boolean);
  const { canSeeSeah, isAdmin } = derivePermissions(roleKeys);

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        isLoading,
        user,
        error,
        roleKeys,
        canSeeSeah,
        isAdmin,
        signIn,
        signOut,
        accessToken,
        effectiveLang,
        bypassRoster,
        bypassRosterError,
        switchBypassUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={null}>
      <AuthProviderInner>{children}</AuthProviderInner>
    </Suspense>
  );
}
