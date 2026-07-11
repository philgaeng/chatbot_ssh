"use client";

/**
 * <Bilingual> — the single render seam for bilingual strings (RB-1, DESIGN §D4 / §7.C).
 *
 * Two shapes of input, one rule (English is the source of record; Nepali is never
 * fabricated — absent ⇒ English fallback):
 *
 *   • DATA pair  — <Bilingual en={org.name} ne={org.display_name_ne} />
 *       Used on every `_name` / `display_name` render across Organisation, Officers,
 *       Position types (RB-2/3/4). This is the DESIGN §D4 seam.
 *   • CHROME key — <Bilingual k="nav.settings" />
 *       Resolves from the EN/NE dictionaries.
 *
 * Two render modes:
 *   • mode="pair"  (default) — DESIGN §D4 inline form: "English / नेपाली". When Nepali is
 *       absent, shows "English / —" plus a "Nepali name needed" chip (DESIGN §7.C),
 *       never an invented string.
 *   • mode="active" — the active-language string only (English fallback). For chrome or
 *       places where showing both languages is noise.
 *
 * Design-system contract (§7.C): gray/slate only, no banned hues, no emoji.
 */

import { useLanguage } from "@/app/providers/LanguageProvider";
import {
  EN_MESSAGES,
  NE_MESSAGES,
  hasNepali,
  resolveLocalized,
  lookup,
  type LocalizedText,
  type MessageKey,
} from "@/lib/i18n";

type BilingualProps = {
  /** Explicit English string (data pair). Ignored when `k` is given. */
  en?: string;
  /** Explicit Nepali string (data pair). Absent/empty ⇒ English fallback; never fabricate. */
  ne?: string | null;
  /** OR a chrome dictionary key — resolves to a bilingual pair from the dictionaries. */
  k?: MessageKey;
  /** "pair" → inline "English / नेपाली" (default, DESIGN §D4); "active" → active language only. */
  mode?: "pair" | "active";
  /** In pair mode, render the "Nepali name needed" affordance when Nepali is absent (default true). */
  showMissing?: boolean;
  className?: string;
};

/**
 * The "/ —  Nepali name needed" chip (DESIGN §7.C) — a labelled, translator-facing flag
 * for a missing Nepali name. Gray chrome only; no jargon, no emoji.
 */
export function NepaliNameNeeded({ className }: { className?: string }) {
  const { lang } = useLanguage();
  return (
    <span
      className={`inline-flex items-center rounded-md border border-gray-200 bg-gray-100 px-1.5 py-0.5 align-middle text-[11px] font-medium text-gray-600 ${className ?? ""}`}
    >
      {lookup("bilingual.nepaliNameNeeded", lang, EN_MESSAGES, NE_MESSAGES)}
    </span>
  );
}

export function Bilingual({
  en,
  ne,
  k,
  mode = "pair",
  showMissing = true,
  className,
}: BilingualProps) {
  const { lang } = useLanguage();

  const pair: LocalizedText =
    k !== undefined ? { en: EN_MESSAGES[k], ne: NE_MESSAGES[k] } : { en: en ?? "", ne };

  if (mode === "active") {
    return <span className={className}>{resolveLocalized(pair, lang)}</span>;
  }

  // mode === "pair" — DESIGN §D4 inline "English / नेपाली"
  if (hasNepali(pair)) {
    return (
      <span className={className}>
        {pair.en} <span className="text-gray-500">/ {(pair.ne as string).trim()}</span>
      </span>
    );
  }

  return (
    <span className={className}>
      {pair.en}
      {showMissing && (
        <>
          {" "}
          <span className="text-gray-400">/ —</span> <NepaliNameNeeded />
        </>
      )}
    </span>
  );
}

export default Bilingual;
