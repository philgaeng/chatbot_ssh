// SPDX-License-Identifier: Apache-2.0

/**
 * Human, non-slug rendering of a territory location code (build sheet frame-03 §5: never
 * render a raw code). "NP-P1-D-JHAPA" → "Jhapa".
 *
 * TODO: swap for a real location-name lookup once a by-code resolver lands in lib/api.ts.
 */
export function prettyLocation(code: string | null | undefined): string {
  if (!code) return "";
  const tail = code.split(/[-_.:/]/).filter(Boolean).pop() ?? code;
  return tail
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");
}
