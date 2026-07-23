"use client";

import { useEffect } from "react";
import "./globals.css";
import { IconWarning, IconRetry } from "@/lib/icons";

/**
 * Root-layout error boundary (HR-06). Only fires when the root layout itself
 * (AuthProvider / AppShell) throws — must define its own html/body since it
 * replaces the whole layout. Uses a plain <a> (not next/link) since the
 * app router context that backs Link may not be intact at this level.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <html lang="en">
      <body className="text-gray-900">
        <div className="min-h-screen flex items-center justify-center p-8">
          <div className="text-center max-w-md">
            <IconWarning size={32} strokeWidth={1.5} className="mx-auto mb-3 text-red-500" />
            <h1 className="text-lg font-semibold text-gray-800 mb-1">Something went wrong</h1>
            <p className="text-sm text-gray-500 mb-5">
              The application hit an unexpected error. Try again, or head back to your queue.
            </p>
            <div className="flex items-center justify-center gap-3">
              <button
                type="button"
                onClick={() => reset()}
                className="inline-flex items-center gap-1.5 text-sm font-medium px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-700 transition"
              >
                <IconRetry size={15} />
                Try again
              </button>
              <a
                href="/queue"
                className="text-sm font-medium px-4 py-2 rounded border border-gray-300 text-gray-700 hover:bg-gray-50 transition"
              >
                Back to queue
              </a>
            </div>
          </div>
        </div>
      </body>
    </html>
  );
}
