"use client";

import { IconWarning, IconRetry } from "@/lib/icons";

/**
 * Load-failure card for list pages (HR-06) — distinct from the "no results"
 * empty state so a down API is never mistaken for "no tickets".
 */
export function ErrorCard({
  message = "Couldn't load data.",
  onRetry,
  className = "",
}: {
  message?: string;
  onRetry: () => void;
  className?: string;
}) {
  return (
    <div className={`p-8 text-center ${className}`}>
      <IconWarning size={28} strokeWidth={1.5} className="mx-auto mb-2 text-red-500" />
      <p className="text-sm text-red-700 mb-3">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="inline-flex items-center gap-1.5 text-sm font-medium px-3 py-1.5 rounded border border-red-300 text-red-700 bg-red-50 hover:bg-red-100 transition"
      >
        <IconRetry size={15} />
        Retry
      </button>
    </div>
  );
}
