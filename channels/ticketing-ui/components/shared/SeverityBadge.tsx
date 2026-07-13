"use client";

/**
 * <SeverityBadge> — go-live / validation severity chip with TEXT beside colour
 * (DESIGN §7.C: text severity always accompanies the hue). Used by the go-live spine
 * and per-project readiness panels (block / warn / info / pass).
 */
import { danger, warning, success, text as textTokens } from "@/lib/design-tokens";

export type Severity = "block" | "warn" | "info" | "pass";

const SEVERITY: Record<Severity, { label: string; cls: string }> = {
  block: { label: "Must fix", cls: `${danger.bgLight} ${danger.borderLight} ${danger.text}` },
  warn:  { label: "Review",   cls: `${warning.bgLight} ${warning.borderLight} ${warning.text}` },
  info:  { label: "Optional", cls: `bg-gray-50 border-gray-200 ${textTokens.secondary}` },
  pass:  { label: "Ready",    cls: `${success.bgLight} ${success.borderLight} ${success.text}` },
};

export function SeverityBadge({
  severity,
  label,
  className = "",
}: {
  severity: Severity;
  /** Override the default word (e.g. "Blocked"); the colour still encodes severity. */
  label?: string;
  className?: string;
}) {
  const s = SEVERITY[severity];
  return (
    <span
      className={`inline-flex items-center rounded border px-1.5 py-0.5 text-xs font-medium ${s.cls} ${className}`}
    >
      {label ?? s.label}
    </span>
  );
}
