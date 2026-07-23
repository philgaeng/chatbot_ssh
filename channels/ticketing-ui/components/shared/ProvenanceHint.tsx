"use client";

/**
 * <ProvenanceHint> — the muted "why this value" line under a pre-filled field
 * (DESIGN §4.1: "provenance on every value"). E.g. "From the position type", "Office
 * territory: Morang", "Supervisor: L2 handler pool — change". Never a control itself;
 * the optional `onAction` renders an inline "change" affordance.
 */
import { text as textTokens, primary } from "@/lib/design-tokens";

export function ProvenanceHint({
  children,
  actionLabel,
  onAction,
  className = "",
}: {
  children: React.ReactNode;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
}) {
  return (
    <p className={`text-xs ${textTokens.secondary} ${className}`}>
      {children}
      {actionLabel && onAction ? (
        <>
          {" — "}
          <button
            type="button"
            onClick={onAction}
            className={`underline ${primary.textLight} hover:no-underline`}
          >
            {actionLabel}
          </button>
        </>
      ) : null}
    </p>
  );
}
