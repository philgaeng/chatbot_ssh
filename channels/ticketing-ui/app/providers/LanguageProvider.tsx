// SPDX-License-Identifier: Apache-2.0

"use client";

/**
 * LanguageProvider — active-language context for the officer UI (RB-1).
 *
 * The active language follows the officer's backend-resolved preference
 * (`preferred_language ?? org default ?? 'en'`), surfaced by AuthProvider as
 * `effectiveLang`. There is no URL/locale routing (`/[lang]/…`): language is a runtime
 * user preference, not a route segment — so the Next.js 16 "Localization" dictionary
 * pattern (i18n guide) is the right half here, and the "internationalized routing" half
 * deliberately is not. `setLang` is exposed for a future in-app language toggle.
 *
 * `useT()` returns the chrome translator bound to the active language (English fallback).
 * For bilingual DATA pairs (`_ne` DB fields) use <Bilingual> instead.
 */

import React, { createContext, useContext, useMemo, useState } from "react";
import { useAuth } from "@/app/providers/AuthProvider";
import { DEFAULT_LANG, type Lang, t as translate, type MessageKey } from "@/lib/i18n";

interface LanguageContextValue {
  /** Active language. Defaults to English until the backend preference resolves. */
  lang: Lang;
  /** Manual override (e.g. a future language toggle). */
  setLang: (lang: Lang) => void;
  /** Chrome translator bound to the active language, with English fallback. */
  t: (key: MessageKey) => string;
}

// Safe default so the primitive never throws if a subtree renders outside the provider
// (e.g. an isolated unit render). Defaults to English — the fallback language.
const LanguageContext = createContext<LanguageContextValue>({
  lang: DEFAULT_LANG,
  setLang: () => {},
  t: (key) => translate(key, DEFAULT_LANG),
});

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const { effectiveLang } = useAuth();
  // Derive (don't sync-via-effect): a manual override wins; otherwise the active
  // language follows the officer's backend-resolved preference; English is the floor.
  const [override, setOverride] = useState<Lang | null>(null);
  const lang: Lang = override ?? effectiveLang ?? DEFAULT_LANG;

  const value = useMemo<LanguageContextValue>(
    () => ({
      lang,
      setLang: setOverride,
      t: (key: MessageKey) => translate(key, lang),
    }),
    [lang],
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

/** Access the language context: `{ lang, setLang, t }`. */
export function useLanguage(): LanguageContextValue {
  return useContext(LanguageContext);
}

/** Convenience hook: just the chrome translator bound to the active language. */
export function useT(): (key: MessageKey) => string {
  return useContext(LanguageContext).t;
}
