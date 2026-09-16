// SPDX-License-Identifier: Apache-2.0

"use client";

/**
 * <SessionIdleWarning> — tells an officer their session is about to end, before a draft is lost to it
 * (`GRM-111`, D-012). The rules and why they are shaped this way live in `lib/auth/idle-warning.ts`.
 *
 * It reads the stored refresh token once a second, with no request. Only *Stay signed in* renews: a
 * warning that renewed by itself would keep an unattended session alive for 8 hours.
 */
import { useEffect, useState } from "react";

import { useAuth } from "@/app/providers/AuthProvider";
import { refreshTokens } from "@/lib/auth/oidc-auth";
import { AUTH_BYPASS } from "@/lib/auth/runtime-config";
import { handleSessionExpired } from "@/lib/auth/session-expired";
import { TOKEN_STORAGE } from "@/lib/auth/token-storage";
import {
  IDLE_WARNING_LEAD_MS,
  formatTimeLeft,
  idleWarningState,
  tokenExpiryMs,
  type IdleWarning,
} from "@/lib/auth/idle-warning";

function readSessionEnd(): number | null {
  try {
    return tokenExpiryMs(localStorage.getItem(TOKEN_STORAGE.REFRESH_TOKEN));
  } catch {
    return null;
  }
}

export function SessionIdleWarning() {
  const { isAuthenticated } = useAuth();
  const [now, setNow] = useState(() => Date.now());
  const [sessionEnd, setSessionEnd] = useState<number | null>(null);
  const [atLimit, setAtLimit] = useState(false);
  const [renewalRefused, setRenewalRefused] = useState(false);
  const [renewing, setRenewing] = useState(false);
  const active = isAuthenticated && !AUTH_BYPASS;

  useEffect(() => {
    if (!active) return;
    const tick = () => {
      setNow(Date.now());
      setSessionEnd(readSessionEnd());  // another tab's renewal moves it too
    };
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, [active]);

  if (!active) return null;
  // A refused renewal means the session is already gone, whatever the stored token still says.
  const state: IdleWarning = renewalRefused ? { kind: "ended" } : idleWarningState(sessionEnd, now, atLimit);
  if (state.kind === "none") return null;

  async function staySignedIn() {
    setRenewing(true);
    const renewed = await refreshTokens();
    const end = readSessionEnd();
    setRenewing(false);
    setSessionEnd(end);
    setNow(Date.now());
    if (!renewed) setRenewalRefused(true);
    // Renewed, but the deadline stayed inside the window: the 8-hour maximum, which nothing extends.
    if (renewed && end !== null && end - Date.now() <= IDLE_WARNING_LEAD_MS) setAtLimit(true);
  }

  function signInAgain() {
    try {
      handleSessionExpired();
    } catch {
      /* it throws by design once the redirect is under way */
    }
  }

  return (
    <div
      role="alert"
      className="fixed inset-x-3 top-3 z-[60] mx-auto max-w-lg rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 shadow-lg"
    >
      {state.kind === "idle" && (
        <div className="flex flex-wrap items-center gap-3">
          <p className="flex-1 min-w-[12rem] text-sm text-amber-900">
            You will be signed out in <strong className="tabular-nums">{formatTimeLeft(state.msLeft)}</strong> because
            nothing has been sent for a while. Anything you have not sent will be lost.
          </p>
          <button
            type="button"
            onClick={staySignedIn}
            disabled={renewing}
            className="rounded-lg bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50"
          >
            {renewing ? "Staying signed in…" : "Stay signed in"}
          </button>
        </div>
      )}
      {state.kind === "limit" && (
        <p className="text-sm text-amber-900">
          Your session reaches its time limit in <strong className="tabular-nums">{formatTimeLeft(state.msLeft)}</strong>.
          Send or copy anything you are writing, then sign in again.
        </p>
      )}
      {state.kind === "ended" && (
        <div className="flex flex-wrap items-center gap-3">
          <p className="flex-1 min-w-[12rem] text-sm text-amber-900">
            You have been signed out. Copy anything you have not sent before you sign in again. It is still on
            this page, but it will not be kept.
          </p>
          <button
            type="button"
            onClick={signInAgain}
            className="rounded-lg border border-amber-400 bg-white px-3 py-1.5 text-sm font-medium text-amber-800 hover:bg-amber-100"
          >
            Sign in again
          </button>
        </div>
      )}
    </div>
  );
}
