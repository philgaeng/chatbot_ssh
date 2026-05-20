"use client";

import { Suspense, useEffect } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/app/providers/AuthProvider";

function AuthCallbackContent() {
  const { isLoading, error, isAuthenticated } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const hasOAuthParams = Boolean(searchParams.get("code") && searchParams.get("state"));
  const oauthError = searchParams.get("error");

  useEffect(() => {
    if (isAuthenticated) {
      router.replace("/queue");
    }
  }, [isAuthenticated, router]);

  useEffect(() => {
    if (isLoading || hasOAuthParams || oauthError) return;
    router.replace("/login?error=" + encodeURIComponent("Sign-in could not be completed. Please sign in again."));
  }, [hasOAuthParams, isLoading, oauthError, router]);

  useEffect(() => {
    if (!oauthError || isLoading) return;
    const description = searchParams.get("error_description") ?? oauthError;
    router.replace("/login?error=" + encodeURIComponent(description));
  }, [isLoading, oauthError, router, searchParams]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-100 px-4">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8 w-full max-w-sm text-center">
          <div className="text-2xl mb-3">⚠️</div>
          <h1 className="text-lg font-semibold text-gray-800">Sign-in failed</h1>
          <p className="text-sm text-gray-600 mt-2">{error}</p>
          <Link
            href="/login"
            className="mt-6 inline-block w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-lg text-sm"
          >
            Back to sign in
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100">
      <div className="text-center">
        <div className="text-2xl mb-3">⏳</div>
        <p className="text-sm text-gray-500">Completing sign-in…</p>
      </div>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-slate-100">
          <p className="text-sm text-gray-500">Completing sign-in…</p>
        </div>
      }
    >
      <AuthCallbackContent />
    </Suspense>
  );
}
