// SPDX-License-Identifier: Apache-2.0

/**
 * i18n/resolve.ts — pure, framework-free fallback resolvers (RB-1).
 *
 * These functions carry the ONE rule that matters for this build: **English is the
 * source of record; Nepali is an optional overlay that is NEVER fabricated.** Where a
 * Nepali string is absent or empty, everything here falls back to English.
 *
 * Kept dependency-free (no React, no dictionary imports) so the fallback logic is unit
 * testable in isolation (see resolve.test.ts) and reusable from both client components
 * (via <Bilingual> / useT) and any server-side render path.
 */

export type Lang = "en" | "ne";

export const DEFAULT_LANG: Lang = "en";

export const SUPPORTED_LANGS: readonly Lang[] = ["en", "ne"] as const;

/** A bilingual value: English is always present; Nepali is optional and never invented. */
export interface LocalizedText {
  /** English — the source-of-record string. Always present. */
  en: string;
  /** Nepali (Devanagari). Absent / null / empty ⇒ English fallback. Never fabricated. */
  ne?: string | null;
}

/** Narrow an arbitrary value to a supported language. */
export function isLang(value: unknown): value is Lang {
  return value === "en" || value === "ne";
}

/** Coerce any value to a supported language, defaulting to English. */
export function coerceLang(value: unknown): Lang {
  return isLang(value) ? value : DEFAULT_LANG;
}

/** True only when a real (non-empty, non-whitespace) Nepali string is present. */
export function hasNepali(text: Pick<LocalizedText, "ne">): boolean {
  return typeof text.ne === "string" && text.ne.trim().length > 0;
}

/**
 * Resolve a bilingual pair to a single string for the active language.
 * Returns Nepali only when the active language is `ne` AND a real Nepali string exists;
 * otherwise English.
 */
export function resolveLocalized(text: LocalizedText, lang: Lang): string {
  if (lang === "ne" && hasNepali(text)) {
    return (text.ne as string).trim();
  }
  return text.en;
}

/**
 * Dictionary lookup with English fallback. Generic over the key union so a typed
 * dictionary (EN complete, NE partial) keeps full key-safety at the call site.
 *
 * Order of resolution:
 *   1. Nepali overlay value — only if active lang is `ne` and the value is non-empty.
 *   2. English value.
 *   3. The key itself — last-resort dev signal that a key is missing from the EN source.
 */
export function lookup<K extends string>(
  key: K,
  lang: Lang,
  en: Readonly<Record<K, string>>,
  ne: Partial<Record<K, string>>,
): string {
  if (lang === "ne") {
    const candidate = ne[key];
    if (typeof candidate === "string" && candidate.trim().length > 0) {
      return candidate;
    }
  }
  const fallback = en[key];
  return typeof fallback === "string" ? fallback : key;
}
