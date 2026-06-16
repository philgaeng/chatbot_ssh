"use client";

import React, { createContext, useContext, useEffect, useState, Suspense, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { OIDCAuthClient, type TokenPayload } from "@/lib/auth/oidc-auth";
import { loginWithPasswordApi } from "@/lib/auth/auth-api";
import { persistAuthTokens, rememberLoginEmail } from "@/lib/auth/token-storage";
import { clearAuthTokens, isAccessTokenExpired } from "@/lib/auth/session-expired";
import { getUserPreferences, getMyProfile, getMySession, listOfficerRoster, getAdminContext, type OfficerRosterEntry, type AdminContext } from "@/lib/api";

const BYPASS_DEFAULT_EMAIL = "admin@grm.local";

const BYPASS_COOKIE = "grm_bypass_user";
const LEGACY_MOCK_COOKIE = "grm_mock_user";

function fallbackBypassToken(): TokenPayload {
  return {
    sub: BYPASS_DEFAULT_EMAIL,
    email: BYPASS_DEFAULT_EMAIL,
    name: "GRM Admin",
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

const PRIVILEGED_ROLE_KEYS = new Set([
  "super_admin",
  "country_admin",
  "project_admin",
]);

function pickDefaultOfficer(roster: OfficerRosterEntry[]): OfficerRosterEntry | null {
  if (roster.length === 0) return null;
  const privileged = roster.filter((r) =>
    r.role_keys.some((k) => PRIVILEGED_ROLE_KEYS.has(k)),
  );
  const pool = privileged.length ? privileged : roster;
  return [...pool].sort((a, b) => a.display_name.localeCompare(b.display_name))[0];
}

function clearCookie(name: string): void {
  if (typeof document === "undefined") return;
  document.cookie = `${name}=; path=/; max-age=0`;
}

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

export interface AuthContextValue {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: TokenPayload | null;
  error: string | null;
  roleKeys: string[];
  canSeeSeah: boolean;
  isAdmin: boolean;
  isSuperAdmin: boolean;
  isCountryAdmin: boolean;
  isProjectAdmin: boolean;
  adminWorkflowTracks: ("standard" | "seah")[];
  adminProjectIds: string[];
  adminCountryCode: string | null;
  canAccessPlatformSettings: boolean;
  canManageStructure: boolean;
  canCreateProject: boolean;
  canCreateOperationalRoles: boolean;
  signIn: () => void;
  signOut: () => void;
  loginWithPassword: (email: string, password: string) => Promise<void>;
  accessToken: string | null;
  effectiveLang: "en" | "ne" | null;
  bypassRoster: OfficerRosterEntry[] | null;
  bypassRosterError: string | null;
  switchBypassUser: (entry: OfficerRosterEntry) => void;
  refreshDisplayName: () => Promise<void>;
  refreshAdminContext: () => Promise<void>;
  refreshSession: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

const SEAH_CAN_SEE_ROLES = new Set(["super_admin", "adb_hq_exec", "seah_national_officer", "seah_hq_officer", "country_admin", "project_admin"]);
const ADMIN_ROLES = new Set(["super_admin", "country_admin", "project_admin"]);

function derivePermissions(roleKeys: string[], adminCtx: AdminContext | null) {
  const fromRoles = {
    canSeeSeah: roleKeys.some((r) => SEAH_CAN_SEE_ROLES.has(r)),
    isAdmin: roleKeys.some((r) => ADMIN_ROLES.has(r)),
    isSuperAdmin: roleKeys.includes("super_admin"),
    isCountryAdmin: roleKeys.includes("country_admin"),
    isProjectAdmin: roleKeys.includes("project_admin"),
  };
  if (!adminCtx) return fromRoles;
  return {
    canSeeSeah: fromRoles.canSeeSeah || adminCtx.admin_workflow_tracks.includes("seah"),
    isAdmin: fromRoles.isAdmin || adminCtx.is_country_admin || adminCtx.is_project_admin || adminCtx.is_super_admin,
    isSuperAdmin: fromRoles.isSuperAdmin || adminCtx.is_super_admin,
    isCountryAdmin: fromRoles.isCountryAdmin || adminCtx.is_country_admin,
    isProjectAdmin: fromRoles.isProjectAdmin || adminCtx.is_project_admin,
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
  const [adminContext, setAdminContext] = useState<AdminContext | null>(null);
  const [effectiveRoleKeys, setEffectiveRoleKeys] = useState<string[]>([]);

  const refreshSession = useCallback(async () => {
    if (bypass) return;
    try {
      const session = await getMySession();
      setEffectiveRoleKeys(session.role_keys);
      setUser((prev) =>
        prev
          ? {
              ...prev,
              "custom:grm_roles": session.role_keys.join(","),
              "custom:organization_id": session.organization_id ?? prev["custom:organization_id"],
            }
          : prev,
      );
    } catch {
      setEffectiveRoleKeys([]);
    }
  }, [bypass]);

  const client = !bypass
    ? new OIDCAuthClient(
        process.env.NEXT_PUBLIC_OIDC_ISSUER ?? "",
        process.env.NEXT_PUBLIC_OIDC_CLIENT_ID ?? "",
        typeof window !== "undefined"
          ? `${window.location.origin}/auth/callback`
          : (process.env.NEXT_PUBLIC_REDIRECT_SIGN_IN ?? ""),
      )
    : null;

  const refreshAdminContext = useCallback(async () => {
    try {
      const ctx = await getAdminContext();
      setAdminContext(ctx);
    } catch {
      setAdminContext(null);
    }
  }, []);

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
          setEffectiveRoleKeys(chosen.role_keys);
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
    if (!isAuthenticated || isLoading) return;
    refreshAdminContext();
    refreshSession();
  }, [isAuthenticated, isLoading, user?.sub, refreshAdminContext, refreshSession]);

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
      const token = client.getAccessToken();
      const existing = client.getCurrentUser();
      if (existing && token) {
        if (isAccessTokenExpired(token)) {
          clearAuthTokens();
          setUser(null);
          setAccessToken(null);
          setIsAuthenticated(false);
          if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
            window.location.replace("/login?reason=session_expired");
            return;
          }
        } else {
          clearCookie(BYPASS_COOKIE);
          clearCookie(LEGACY_MOCK_COOKIE);
          setUser(existing);
          setAccessToken(token);
          setIsAuthenticated(true);
        }
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
      window.location.href = "/login";
    }
  };

  const loginWithPassword = useCallback(async (email: string, password: string) => {
    const tokens = await loginWithPasswordApi(email, password);
    const u = persistAuthTokens(tokens);
    rememberLoginEmail(email);
    clearCookie(BYPASS_COOKIE);
    clearCookie(LEGACY_MOCK_COOKIE);
    setUser(u);
    setAccessToken(tokens.access_token);
    setIsAuthenticated(true);
    setError(null);
  }, []);

  const signOut = () => {
    if (bypass) {
      setIsAuthenticated(false);
      setUser(null);
      setBypassUserCookie(null);
      window.location.href = "/login";
    } else {
      clearCookie(BYPASS_COOKIE);
      clearCookie(LEGACY_MOCK_COOKIE);
      client!.signOut();
    }
  };

  const switchBypassUser = useCallback((entry: OfficerRosterEntry) => {
    setBypassUserCookie(entry);
    setUser(tokenFromRosterRow(entry));
    setEffectiveRoleKeys(entry.role_keys);
    window.location.href = "/queue";
  }, []);

  const refreshDisplayName = useCallback(async () => {
    try {
      const p = await getMyProfile();
      const name = `${p.first_name} ${p.last_name}`.trim() || p.email;
      setUser((prev) => (prev ? { ...prev, name, email: p.email } : prev));
      if (bypass && typeof window !== "undefined") {
        const raw = readBypassCookieRaw();
        const parsed = raw ? parseBypassCookie(raw) : null;
        if (parsed) {
          setBypassRoster((prev) =>
            (prev ?? []).map((r) =>
              r.user_id === parsed.user_id
                ? { ...r, display_name: name, email: p.email, phone_number: p.phone_number }
                : r,
            ),
          );
        }
      }
      if (!bypass && typeof window !== "undefined") {
        const stored = localStorage.getItem("grm_user");
        if (stored) {
          try {
            const u = JSON.parse(stored) as TokenPayload;
            localStorage.setItem("grm_user", JSON.stringify({ ...u, name, email: p.email }));
          } catch {
            /* ignore */
          }
        }
      }
    } catch {
      /* profile API unavailable */
    }
  }, [bypass]);

  const roleKeys =
    effectiveRoleKeys.length > 0
      ? effectiveRoleKeys
      : ((user?.["custom:grm_roles"] as string | undefined) ?? "")
          .split(",")
          .map((r) => r.trim())
          .filter(Boolean);
  const perms = derivePermissions(roleKeys, adminContext);
  const adminWorkflowTracks = (adminContext?.admin_workflow_tracks ?? []) as ("standard" | "seah")[];
  const canCreateOperationalRoles =
    perms.isSuperAdmin ||
    adminWorkflowTracks.some((t) => t === "standard" || t === "seah");

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        isLoading,
        user,
        error,
        roleKeys,
        canSeeSeah: perms.canSeeSeah,
        isAdmin: perms.isAdmin,
        isSuperAdmin: perms.isSuperAdmin,
        isCountryAdmin: perms.isCountryAdmin,
        isProjectAdmin: perms.isProjectAdmin,
        adminWorkflowTracks,
        adminProjectIds: adminContext?.admin_project_ids ?? [],
        adminCountryCode: adminContext?.admin_country_codes[0] ?? null,
        canAccessPlatformSettings: adminContext?.can_access_platform_settings ?? perms.isSuperAdmin,
        canManageStructure: adminContext?.can_manage_structure ?? perms.isSuperAdmin,
        canCreateProject: adminContext?.can_create_project ?? perms.isSuperAdmin,
        canCreateOperationalRoles,
        signIn,
        signOut,
        loginWithPassword,
        accessToken,
        effectiveLang,
        bypassRoster,
        bypassRosterError,
        switchBypassUser,
        refreshDisplayName,
        refreshAdminContext,
        refreshSession,
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
