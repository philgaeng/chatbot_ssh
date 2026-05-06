"use client";

import React, { createContext, useContext, useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { OIDCAuthClient, type TokenPayload } from "@/lib/auth/oidc-auth";
import { getUserPreferences } from "@/lib/api";

// ── Mock officers for demo (NEXT_PUBLIC_BYPASS_AUTH=true) ────────────────────
// Each entry maps user_id → TokenPayload.  The proxy reads grm_mock_user cookie
// and injects X-Internal-User-Id / X-Internal-Role so the backend identity
// matches what the UI displays.

export interface MockOfficer {
  user_id: string;
  name: string;
  role_keys: string[];
  organization_id: string;
  token: TokenPayload;
}

export const MOCK_OFFICERS: MockOfficer[] = [
  {
    user_id: "mock-officer-site-l1",
    name: "Site Officer L1",
    role_keys: ["site_safeguards_focal_person"],
    organization_id: "DOR",
    token: { sub: "mock-officer-site-l1", email: "site.officer@grm.local", name: "Site Officer L1 (mock)", email_verified: true, "custom:grm_roles": "site_safeguards_focal_person", "custom:organization_id": "DOR" },
  },
  {
    user_id: "mock-officer-piu-l2",
    name: "PIU Officer L2",
    role_keys: ["pd_piu_safeguards_focal"],
    organization_id: "DOR",
    token: { sub: "mock-officer-piu-l2", email: "piu.officer@grm.local", name: "PIU Officer L2 (mock)", email_verified: true, "custom:grm_roles": "pd_piu_safeguards_focal", "custom:organization_id": "DOR" },
  },
  {
    user_id: "mock-officer-grc-chair",
    name: "GRC Chair",
    role_keys: ["grc_chair"],
    organization_id: "DOR",
    token: { sub: "mock-officer-grc-chair", email: "grc.chair@grm.local", name: "GRC Chair (mock)", email_verified: true, "custom:grm_roles": "grc_chair", "custom:organization_id": "DOR" },
  },
  {
    user_id: "mock-officer-adb-observer",
    name: "ADB Safeguards",
    role_keys: ["adb_hq_safeguards"],
    organization_id: "ADB",
    token: { sub: "mock-officer-adb-observer", email: "adb@grm.local", name: "ADB Safeguards (mock)", email_verified: true, "custom:grm_roles": "adb_hq_safeguards", "custom:organization_id": "ADB" },
  },
  {
    user_id: "mock-officer-seah-national",
    name: "SEAH Officer",
    role_keys: ["seah_national_officer"],
    organization_id: "DOR",
    token: { sub: "mock-officer-seah-national", email: "seah@grm.local", name: "SEAH Officer (mock)", email_verified: true, "custom:grm_roles": "seah_national_officer", "custom:organization_id": "DOR" },
  },
  {
    user_id: "mock-super-admin",
    name: "Super Admin",
    role_keys: ["super_admin"],
    organization_id: "DOR",
    token: { sub: "mock-super-admin", email: "admin@grm.local", name: "Super Admin (mock)", email_verified: true, "custom:grm_roles": "super_admin", "custom:organization_id": "DOR" },
  },
];

const MOCK_BY_ID = new Map(MOCK_OFFICERS.map(o => [o.user_id, o]));

/** Read grm_mock_user cookie → resolve MockOfficer (or undefined). */
function readMockCookie(): MockOfficer | undefined {
  if (typeof document === "undefined") return undefined;
  const match = document.cookie.match(/grm_mock_user=([^;]+)/);
  if (!match) return undefined;
  try {
    const { user_id } = JSON.parse(match[1]);
    return MOCK_BY_ID.get(user_id);
  } catch { return undefined; }
}

/** Write (or clear) the grm_mock_user cookie. */
export function setMockUserCookie(officer: MockOfficer | null): void {
  if (typeof document === "undefined") return;
  if (!officer) {
    document.cookie = "grm_mock_user=; path=/; max-age=0";
  } else {
    // Do NOT URL-encode — req.cookies.get() in Next.js API routes decodes
    // automatically, so the proxy reads the raw JSON value directly.
    const value = JSON.stringify({
      user_id: officer.user_id,
      role_keys: officer.role_keys,
      organization_id: officer.organization_id,
    });
    document.cookie = `grm_mock_user=${value}; path=/; max-age=86400`;
  }
}

// Default mock user (used when no cookie is set)
const DEFAULT_MOCK = MOCK_OFFICERS[0]; // site officer L1

function resolveMockUser(): MockOfficer {
  return readMockCookie() ?? DEFAULT_MOCK;
}

// ── Auth context ─────────────────────────────────────────────────────────────

export interface AuthContextValue {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: TokenPayload | null;
  error: string | null;
  /** Current user's role keys (from custom:grm_roles or mock) */
  roleKeys: string[];
  /** True if user can see SEAH tickets */
  canSeeSeah: boolean;
  /** True if user has admin privileges */
  isAdmin: boolean;
  signIn: () => void;
  signOut: () => void;
  /** Bearer token for API calls (null in mock mode) */
  accessToken: string | null;
  /**
   * Effective UI language for this officer.
   * 'en' = English-first (inline translation chips shown)
   * 'ne' = Nepali-first (inline chips hidden; translation panel for review)
   * null = still loading from API
   */
  effectiveLang: "en" | "ne" | null;
  /**
   * Switch mock officer (bypass mode only). Sets cookie + updates React state
   * so both UI identity and backend calls reflect the new officer immediately.
   */
  switchMockUser: (officer: MockOfficer) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

// ── Helper: derive permissions from role keys ─────────────────────────────────

const SEAH_CAN_SEE_ROLES = new Set(["super_admin", "adb_hq_exec", "seah_national_officer", "seah_hq_officer"]);
const ADMIN_ROLES = new Set(["super_admin", "local_admin"]);

function derivePermissions(roleKeys: string[]) {
  return {
    canSeeSeah: roleKeys.some((r) => SEAH_CAN_SEE_ROLES.has(r)),
    isAdmin: roleKeys.some((r) => ADMIN_ROLES.has(r)),
  };
}

// ── Inner provider (needs useSearchParams, so wrapped in Suspense) ────────────

function AuthProviderInner({ children }: { children: React.ReactNode }) {
  const bypass = process.env.NEXT_PUBLIC_BYPASS_AUTH === "true";
  const searchParams = useSearchParams();

  const [isAuthenticated, setIsAuthenticated] = useState(bypass);
  const [isLoading, setIsLoading] = useState(!bypass);
  const [user, setUser] = useState<TokenPayload | null>(bypass ? resolveMockUser().token : null);
  const [error, setError] = useState<string | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [effectiveLang, setEffectiveLang] = useState<"en" | "ne" | null>(null);

  const client = !bypass
    ? new OIDCAuthClient(
        process.env.NEXT_PUBLIC_OIDC_ISSUER ?? "",
        process.env.NEXT_PUBLIC_OIDC_CLIENT_ID ?? "",
        typeof window !== "undefined"
          ? `${window.location.origin}/auth/callback`
          : (process.env.NEXT_PUBLIC_REDIRECT_SIGN_IN ?? ""),
      )
    : null;

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

  // Fetch language preference once authenticated
  useEffect(() => {
    if (!isAuthenticated || isLoading) return;
    getUserPreferences()
      .then((prefs) => setEffectiveLang(prefs.effective_language as "en" | "ne"))
      .catch(() => setEffectiveLang("en")); // safe fallback — show translations to everyone
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
      window.location.href = "/login";
    } else {
      client!.signOut();
    }
  };

  const switchMockUser = (officer: MockOfficer) => {
    setMockUserCookie(officer);
    setUser(officer.token);
    // Navigate to queue so the new identity filters take effect immediately
    window.location.href = "/queue";
  };

  const roleKeys = (user?.["custom:grm_roles"] ?? "super_admin").split(",").map((r) => r.trim()).filter(Boolean);
  const { canSeeSeah, isAdmin } = derivePermissions(roleKeys);

  return (
    <AuthContext.Provider
      value={{ isAuthenticated, isLoading, user, error, roleKeys, canSeeSeah, isAdmin, signIn, signOut, accessToken, effectiveLang, switchMockUser }}
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
