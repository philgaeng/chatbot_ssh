"use client";

/**
 * <ErrorNotice> — the single inline seam for user-facing errors on Settings surfaces
 * (RB-2, DESIGN §7.C / F11). Wraps `formatUserFacingError` so raw `API 4xx …` strings
 * never reach the user. Text severity ("Please fix" / "Something went wrong") sits BESIDE
 * the colour so colour is never the only signal (WCAG + §7.C).
 */
import { AlertTriangle, Info } from "lucide-react";

import { danger, warning } from "@/lib/design-tokens";
import { formatUserFacingError } from "@/lib/user-messages";

export function ErrorNotice({
  error,
  className = "",
}: {
  /** An Error, a raw thrown value, or a pre-formatted message string. Null hides it. */
  error: unknown;
  className?: string;
}) {
  if (error === null || error === undefined || error === "") return null;

  const { message, kind } = formatUserFacingError(error);
  const isValidation = kind === "validation";
  const palette = isValidation ? warning : danger;
  const Icon = isValidation ? Info : AlertTriangle;
  const severityText = isValidation ? "Please fix" : "Something went wrong";

  return (
    <div
      role="alert"
      className={`flex items-start gap-2 rounded border px-3 py-2 text-sm ${palette.bgLight} ${palette.borderLight} ${palette.text} ${className}`}
    >
      <Icon size={15} className="mt-0.5 shrink-0" aria-hidden />
      <div>
        <span className="font-medium">{severityText}:</span> {message}
      </div>
    </div>
  );
}
