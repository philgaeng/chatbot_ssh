// SPDX-License-Identifier: Apache-2.0

"use client";

import { useEffect } from "react";
import Link from "next/link";
import { IconWarning, IconRetry } from "@/lib/icons";

/**
 * Route-segment error boundary (HR-06). Catches render-time crashes below the
 * root layout so officers see a recoverable card instead of a blank page.
 */
export default function ErrorPage({
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
    <div className="p-8 text-center max-w-md mx-auto">
      <IconWarning size={32} strokeWidth={1.5} className="mx-auto mb-3 text-red-500" />
      <h1 className="text-lg font-semibold text-gray-800 mb-1">Something went wrong</h1>
      <p className="text-sm text-gray-500 mb-5">
        This page hit an unexpected error. Try again, or head back to your queue.
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
        <Link
          href="/queue"
          className="text-sm font-medium px-4 py-2 rounded border border-gray-300 text-gray-700 hover:bg-gray-50 transition"
        >
          Back to queue
        </Link>
      </div>
    </div>
  );
}
