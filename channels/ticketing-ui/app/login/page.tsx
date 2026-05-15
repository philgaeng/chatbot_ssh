"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { LayoutList } from "lucide-react";
import { useAuth } from "@/app/providers/AuthProvider";
import { SESSION_EXPIRED_QUERY } from "@/lib/auth/session-expired";

function LoginContent() {
  const { isAuthenticated, signIn } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const sessionExpired = searchParams.get("reason") === SESSION_EXPIRED_QUERY;

  useEffect(() => {
    if (isAuthenticated) router.replace("/queue");
  }, [isAuthenticated, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100">
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-10 w-full max-w-sm text-center">
        <div className="mb-8">
          <div className="mb-4 inline-flex items-center justify-center w-14 h-14 bg-blue-600 rounded-2xl">
            <LayoutList size={28} strokeWidth={1.75} className="text-white" />
          </div>
          <h1 className="text-xl font-bold text-gray-800">GRM Ticketing</h1>
          <p className="text-sm text-gray-500 mt-1">ADB Grievance Redress Mechanism</p>
        </div>

        {sessionExpired && (
          <div
            role="alert"
            className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-left text-sm text-amber-900"
          >
            <p className="font-semibold">Session expired</p>
            <p className="mt-1 text-amber-800">
              Your sign-in has timed out for security. Please sign in again to continue.
            </p>
          </div>
        )}

        <button
          type="button"
          onClick={signIn}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors text-sm"
        >
          Sign in with ADB Account
        </button>

        <p className="text-xs text-gray-400 mt-6">
          Authorised officers only.
          <br />
          Contact your administrator if you need access.
        </p>
      </div>
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
