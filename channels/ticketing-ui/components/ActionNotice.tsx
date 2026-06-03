"use client";

import { AlertTriangle, X } from "lucide-react";
import type { ActionNoticeState } from "@/lib/user-messages";

export function ActionNotice({
  notice,
  onDismiss,
  className = "",
}: {
  notice: ActionNoticeState | null;
  onDismiss: () => void;
  className?: string;
}) {
  if (!notice) return null;

  const isValidation = notice.kind === "validation";

  return (
    <div
      role="alert"
      className={`flex items-start gap-2.5 rounded-lg border px-4 py-3 text-sm ${className} ${
        isValidation
          ? "border-amber-200 bg-amber-50 text-amber-900"
          : "border-red-200 bg-red-50 text-red-900"
      }`}
    >
      <AlertTriangle
        size={18}
        strokeWidth={2}
        className={`shrink-0 mt-0.5 ${isValidation ? "text-amber-600" : "text-red-600"}`}
        aria-hidden
      />
      <p className="flex-1 whitespace-pre-wrap leading-snug">{notice.message}</p>
      <button
        type="button"
        onClick={onDismiss}
        className={`shrink-0 rounded p-0.5 transition ${
          isValidation ? "text-amber-700 hover:bg-amber-100" : "text-red-700 hover:bg-red-100"
        }`}
        aria-label="Dismiss"
      >
        <X size={16} strokeWidth={2} />
      </button>
    </div>
  );
}
