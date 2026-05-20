"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { LayoutList } from "lucide-react";
import { useAuth } from "@/app/providers/AuthProvider";
import { AuthApiError, requestPasswordResetApi } from "@/lib/auth/auth-api";
import { SESSION_EXPIRED_QUERY } from "@/lib/auth/session-expired";
import { readRememberedLoginEmail, rememberLoginEmail } from "@/lib/auth/token-storage";

type Step = "email" | "password" | "forgot" | "forgot-sent";

const BYPASS = process.env.NEXT_PUBLIC_BYPASS_AUTH === "true";

function normalizeEmail(raw: string): string {
  return raw.trim().toLowerCase();
}

function LoginContent() {
  const { isAuthenticated, signIn, loginWithPassword } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const queryEmail = searchParams.get("email") ?? "";
  const sessionExpired = searchParams.get("reason") === SESSION_EXPIRED_QUERY;
  const callbackError = searchParams.get("error") ?? "";

  const initialEmail = useMemo(() => {
    const fromQuery = normalizeEmail(queryEmail);
    if (fromQuery) return fromQuery;
    return readRememberedLoginEmail() ?? "";
  }, [queryEmail]);

  const [step, setStep] = useState<Step>(() => (initialEmail ? "password" : "email"));
  const [email, setEmail] = useState(initialEmail);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  useEffect(() => {
    if (isAuthenticated) router.replace("/queue");
  }, [isAuthenticated, router]);

  useEffect(() => {
    if (initialEmail) {
      setEmail(initialEmail);
      setStep("password");
    }
  }, [initialEmail]);

  useEffect(() => {
    if (callbackError) {
      setError(decodeURIComponent(callbackError));
      if (initialEmail) setStep("password");
    }
  }, [callbackError, initialEmail]);

  async function continueToPassword(e: React.FormEvent) {
    e.preventDefault();
    const normalized = normalizeEmail(email);
    if (!normalized.includes("@")) {
      setError("Enter the email address your administrator invited you with.");
      return;
    }
    setError(null);
    rememberLoginEmail(normalized);
    setEmail(normalized);
    setStep("password");
  }

  async function submitPassword(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await loginWithPassword(normalizeEmail(email), password);
      router.replace("/queue");
    } catch (err) {
      if (err instanceof AuthApiError) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Sign-in failed.");
      }
    } finally {
      setBusy(false);
    }
  }

  async function submitForgot(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const message = await requestPasswordResetApi(normalizeEmail(email));
      setInfo(message);
      setStep("forgot-sent");
    } catch (err) {
      setError(err instanceof AuthApiError ? err.message : "Could not send reset email.");
    } finally {
      setBusy(false);
    }
  }

  if (BYPASS) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-100">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-10 w-full max-w-sm text-center">
          <Header />
          <button
            type="button"
            onClick={signIn}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors text-sm"
          >
            Continue to demo queue
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100 px-4">
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-10 w-full max-w-sm">
        <Header />

        {sessionExpired && (
          <Alert tone="amber" title="Session expired">
            Your sign-in has timed out. Enter your password to continue.
          </Alert>
        )}

        {error && (
          <Alert tone="red" title="Sign-in problem">
            {error}
          </Alert>
        )}

        {info && step === "forgot-sent" && (
          <Alert tone="green" title="Check your email">
            {info}
          </Alert>
        )}

        {step === "email" && (
          <form onSubmit={continueToPassword} className="space-y-4 text-left">
            <Field label="Officer email">
              <input
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@organisation.org"
                className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </Field>
            <button
              type="submit"
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-lg text-sm"
            >
              Continue
            </button>
          </form>
        )}

        {step === "password" && (
          <form onSubmit={submitPassword} className="space-y-4 text-left">
            <Field label="Officer email">
              <input
                type="email"
                value={email}
                readOnly
                tabIndex={-1}
                aria-readonly="true"
                className="w-full rounded-lg border border-gray-200 bg-gray-100 px-3 py-2.5 text-sm text-gray-600 cursor-not-allowed"
              />
            </Field>
            <Field label="Password">
              <input
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </Field>
            <button
              type="submit"
              disabled={busy}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-semibold py-3 rounded-lg text-sm"
            >
              {busy ? "Signing in…" : "Sign in"}
            </button>
            <div className="flex items-center justify-between text-sm">
              <button
                type="button"
                className="text-blue-600 hover:underline"
                onClick={() => {
                  setError(null);
                  setStep("forgot");
                }}
              >
                Forgot password?
              </button>
              <button
                type="button"
                className="text-gray-500 hover:underline"
                onClick={() => {
                  setPassword("");
                  setError(null);
                  setStep("email");
                }}
              >
                Use different email
              </button>
            </div>
          </form>
        )}

        {step === "forgot" && (
          <form onSubmit={submitForgot} className="space-y-4 text-left">
            <p className="text-sm text-gray-600">
              We will email a password reset link to this address.
            </p>
            <Field label="Officer email">
              <input
                type="email"
                value={email}
                readOnly
                tabIndex={-1}
                className="w-full rounded-lg border border-gray-200 bg-gray-100 px-3 py-2.5 text-sm text-gray-600 cursor-not-allowed"
              />
            </Field>
            <button
              type="submit"
              disabled={busy}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-semibold py-3 rounded-lg text-sm"
            >
              {busy ? "Sending…" : "Send reset email"}
            </button>
            <button
              type="button"
              className="w-full text-sm text-gray-500 hover:underline"
              onClick={() => {
                setError(null);
                setStep("password");
              }}
            >
              Back to sign in
            </button>
          </form>
        )}

        {step === "forgot-sent" && (
          <div className="space-y-4 text-left">
            <button
              type="button"
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-lg text-sm"
              onClick={() => {
                setInfo(null);
                setPassword("");
                setStep("password");
              }}
            >
              Back to sign in
            </button>
          </div>
        )}

        <p className="text-xs text-gray-400 mt-6 text-center">
          Authorised officers only.
          <br />
          Contact your administrator if you need access.
        </p>
      </div>
    </div>
  );
}

function Header() {
  return (
    <div className="mb-8 text-center">
      <div className="mb-4 inline-flex items-center justify-center w-14 h-14 bg-blue-600 rounded-2xl">
        <LayoutList size={28} strokeWidth={1.75} className="text-white" />
      </div>
      <h1 className="text-xl font-bold text-gray-800">GRM Ticketing</h1>
      <p className="text-sm text-gray-500 mt-1">ADB Grievance Redress Mechanism</p>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-xs font-medium text-gray-600 mb-1.5">{label}</span>
      {children}
    </label>
  );
}

function Alert({
  tone,
  title,
  children,
}: {
  tone: "amber" | "red" | "green";
  title: string;
  children: React.ReactNode;
}) {
  const styles =
    tone === "amber"
      ? "border-amber-200 bg-amber-50 text-amber-900"
      : tone === "red"
        ? "border-red-200 bg-red-50 text-red-900"
        : "border-green-200 bg-green-50 text-green-900";
  return (
    <div role="alert" className={`mb-6 rounded-lg border px-4 py-3 text-left text-sm ${styles}`}>
      <p className="font-semibold">{title}</p>
      <p className="mt-1 opacity-90">{children}</p>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-slate-100">
          <p className="text-sm text-gray-500">Loading…</p>
        </div>
      }
    >
      <LoginContent />
    </Suspense>
  );
}
