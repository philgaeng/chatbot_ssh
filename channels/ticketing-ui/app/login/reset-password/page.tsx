"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { LayoutList } from "lucide-react";
import { AuthApiError, resetPasswordApi } from "@/lib/auth/auth-api";

function ResetPasswordContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get("token") ?? "";
  const email = searchParams.get("email") ?? "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!token) setError("This reset link is missing a token. Request a new link from the sign-in page.");
  }, [token]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await resetPasswordApi(token, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof AuthApiError ? err.message : "Could not reset password.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100 px-4">
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-10 w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="mb-4 inline-flex items-center justify-center w-14 h-14 bg-blue-600 rounded-2xl">
            <LayoutList size={28} strokeWidth={1.75} className="text-white" />
          </div>
          <h1 className="text-xl font-bold text-gray-800">Choose a new password</h1>
        </div>

        {error && (
          <div role="alert" className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
            {error}
          </div>
        )}

        {done ? (
          <div className="space-y-4 text-center text-sm text-gray-700">
            <p>Your password has been updated.</p>
            <Link
              href={email ? `/login?email=${encodeURIComponent(email)}` : "/login"}
              className="inline-block w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-lg"
            >
              Sign in
            </Link>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="space-y-4 text-left">
            {email && (
              <label className="block">
                <span className="block text-xs font-medium text-gray-600 mb-1.5">Officer email</span>
                <input
                  type="email"
                  value={email}
                  readOnly
                  className="w-full rounded-lg border border-gray-200 bg-gray-100 px-3 py-2.5 text-sm text-gray-600 cursor-not-allowed"
                />
              </label>
            )}
            <label className="block">
              <span className="block text-xs font-medium text-gray-600 mb-1.5">New password</span>
              <input
                type="password"
                autoComplete="new-password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </label>
            <label className="block">
              <span className="block text-xs font-medium text-gray-600 mb-1.5">Confirm password</span>
              <input
                type="password"
                autoComplete="new-password"
                required
                minLength={8}
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </label>
            <button
              type="submit"
              disabled={busy || !token}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-semibold py-3 rounded-lg text-sm"
            >
              {busy ? "Saving…" : "Update password"}
            </button>
            <Link href="/login" className="block text-center text-sm text-gray-500 hover:underline">
              Back to sign in
            </Link>
          </form>
        )}
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-slate-100 text-sm text-gray-500">Loading…</div>}>
      <ResetPasswordContent />
    </Suspense>
  );
}
