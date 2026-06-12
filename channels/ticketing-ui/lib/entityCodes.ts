/** Shared rules for project short_code and package package_code. */

export const ENTITY_CODE_MAX_LEN = 8;
export const ENTITY_CODE_PATTERN = /^[A-Z0-9_]{1,8}$/;

export function normalizeEntityCodeInput(raw: string): string {
  return raw
    .toUpperCase()
    .replace(/[^A-Z0-9_]/g, "")
    .slice(0, ENTITY_CODE_MAX_LEN);
}

export function validateEntityCode(code: string, field = "Code"): string | null {
  const normalized = normalizeEntityCodeInput(code);
  if (!normalized) return `${field} is required.`;
  if (!ENTITY_CODE_PATTERN.test(normalized)) {
    return `${field} must be 1–${ENTITY_CODE_MAX_LEN} characters: A–Z, 0–9, underscore.`;
  }
  return null;
}

/** Next zero-padded numeric package code (01, 02, …). */
export function suggestNextPackageCode(existing: string[]): string {
  const nums = existing
    .filter((c) => /^\d+$/.test(c))
    .map((c) => parseInt(c, 10));
  const n = (nums.length ? Math.max(...nums) : 0) + 1;
  return n < 100 ? String(n).padStart(2, "0") : String(n).slice(0, ENTITY_CODE_MAX_LEN);
}
