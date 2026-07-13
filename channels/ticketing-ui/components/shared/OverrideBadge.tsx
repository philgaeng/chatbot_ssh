"use client";

/**
 * <OverrideBadge> — marks a value the admin changed away from its pre-filled default
 * (DESIGN §4.1 invite-as-result: "override badge only on override"). Absent when the
 * value still matches the provenance default — the badge is a signal, not decoration.
 */
import { warning } from "@/lib/design-tokens";

export function OverrideBadge({
  show = true,
  title = "Changed from the suggested value",
  className = "",
}: {
  show?: boolean;
  title?: string;
  className?: string;
}) {
  if (!show) return null;
  return (
    <span
      title={title}
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${warning.bgMid} ${warning.textStrong} ${className}`}
    >
      Overridden
    </span>
  );
}
