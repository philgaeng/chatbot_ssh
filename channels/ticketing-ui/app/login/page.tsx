"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/app/providers/AuthProvider";

export default function LoginPage() {
  const { isAuthenticated, signIn } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isAuthenticated) router.replace("/queue");
  }, [isAuthenticated, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100">
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-10 w-full max-w-sm text-center">
        {/* Logo / title */}
        <div className="mb-8">
          <div className="text-3xl mb-3">📋</div>
          <h1 className="text-xl font-bold text-gray-800">GRM Ticketing</h1>
          <p className="text-sm text-gray-500 mt-1">
            ADB Grievance Redress Mechanism
          </p>
        </div>

        {/* Sign in button */}
        <button
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
