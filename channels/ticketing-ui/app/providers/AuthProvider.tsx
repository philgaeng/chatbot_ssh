"use client";

import React, { createContext, useContext, useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { OIDCAuthClient, type TokenPayload } from "@/lib/auth/oidc-auth";
import { getUserPreferences } from "@/lib/api";

// ── Mock user for proto (NEXT_PUBLIC_BYPASS_AUTH=true) ──────────────────────
// sub matches mock-officer-site-l1 from seed data so "My Queue" shows tickets.
// Switch to "mock-super-admin" / "super_admin" to test the admin view.
const MOCK_USER: TokenPayload = {
  sub: "mock-officer-site-l1",
  email: "site.officer@grm.local",
  name: "Site Officer L1 (mock)",
  email_verified: true,
  "custom:grm_roles": "site_safeguards_focal_person",
  "custom:organization_id": "DOR",
};

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
  const [user, setUser] = useState<TokenPayload | null>(bypass ? MOCK_USER : null);
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

  const roleKeys = (user?.["custom:grm_roles"] ?? "super_admin").split(",").map((r) => r.trim()).filter(Boolean);
  const { canSeeSeah, isAdmin } = derivePermissions(roleKeys);

  return (
    <AuthContext.Provider
      value={{ isAuthenticated, isLoading, user, error, roleKeys, canSeeSeah, isAdmin, signIn, signOut, accessToken, effectiveLang }}
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
