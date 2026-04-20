"use client";

// The AuthProvider (in layout.tsx) reads ?code and ?state from useSearchParams
// and handles the token exchange. This page is just a loading screen while that runs.

export default function AuthCallbackPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100">
      <div className="text-center">
        <div className="text-2xl mb-3">⏳</div>
        <p className="text-sm text-gray-500">Completing sign-in…</p>
      </div>
    </div>
  );
}
