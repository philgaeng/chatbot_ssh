/** Standard mask for complainant PII on the default (non-reveal) officer view. */
export const PII_MASK = "•••• ••••";

const CIPHERTEXT_HEX = /^[0-9a-f]{40,}$/i;

export function looksLikeCiphertext(value: unknown): boolean {
  if (typeof value !== "string") return false;
  const s = value.trim();
  return s.length >= 40 && CIPHERTEXT_HEX.test(s);
}

/** Display value for card UI — never show ciphertext or raw PII. */
export function displayMaskedPii(value: string | null | undefined): string {
  if (!value || looksLikeCiphertext(value)) return PII_MASK;
  return PII_MASK;
}

/** Display value inside audited reveal overlay — hide ciphertext if decrypt failed. */
export function displayRevealedPii(value: unknown): string {
  if (value == null || value === "") return "—";
  const s = String(value);
  if (looksLikeCiphertext(s)) {
    return "[Unavailable — contact system administrator]";
  }
  return s;
}
