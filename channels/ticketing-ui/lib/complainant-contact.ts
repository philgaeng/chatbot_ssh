import { PII_MASK } from "@/lib/pii-display";

/** Visible text for complainant contact fields on the default card (not vault reveal). */
const PLACEHOLDER_VALUES = new Set([
  "not provided",
  "unknown",
  "n/a",
  "na",
  "anonymous",
]);

export function complainantIdentityOnFile(
  value: string | null | undefined,
): boolean {
  const t = value?.trim();
  if (!t || t === PII_MASK) return false;
  return !PLACEHOLDER_VALUES.has(t.toLowerCase());
}

export function complainantContactDisplay(
  value: string | null | undefined,
  maskSensitive: boolean,
): string {
  if (maskSensitive) return PII_MASK;
  const trimmed = value?.trim();
  if (!trimmed || PLACEHOLDER_VALUES.has(trimmed.toLowerCase())) return "—";
  return trimmed;
}

/** `tel:` href for click-to-call on mobile (and desktop softphones). */
export function phoneTelHref(phone: string | null | undefined): string | null {
  if (!phone?.trim()) return null;
  const digits = phone.replace(/[^\d+]/g, "");
  if (!digits) return null;
  return `tel:${digits}`;
}
