/**
 * i18n public API (RB-1).
 *
 * Import the primitives from here:
 *   - types + pure resolvers:  Lang, LocalizedText, resolveLocalized, hasNepali, lookup
 *   - dictionaries + accessor: EN_MESSAGES, NE_MESSAGES, MessageKey, t
 *
 * React wiring lives outside this barrel (client-only):
 *   - app/providers/LanguageProvider.tsx  → <LanguageProvider>, useLanguage(), useT()
 *   - components/shared/Bilingual.tsx      → <Bilingual>, <NepaliNameNeeded>
 */
export * from "./resolve";
export * from "./messages";
