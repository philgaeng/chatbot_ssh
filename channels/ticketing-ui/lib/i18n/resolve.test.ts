import { describe, it, expect } from "vitest";
import {
  hasNepali,
  resolveLocalized,
  lookup,
  coerceLang,
  isLang,
  type Lang,
} from "./resolve";
import { t, EN_MESSAGES, NE_MESSAGES, type MessageKey } from "./messages";

describe("hasNepali", () => {
  it("is true only for a real, non-empty Nepali string", () => {
    expect(hasNepali({ ne: "नेपाली" })).toBe(true);
  });

  it.each([
    ["undefined", undefined],
    ["null", null],
    ["empty", ""],
    ["whitespace", "   "],
  ])("is false when Nepali is %s", (_label, ne) => {
    expect(hasNepali({ ne })).toBe(false);
  });
});

describe("resolveLocalized — active language with English fallback", () => {
  it("returns English when the active language is English", () => {
    expect(resolveLocalized({ en: "Organisation", ne: "संगठन" }, "en")).toBe("Organisation");
  });

  it("returns Nepali when active language is Nepali AND a Nepali string is present", () => {
    expect(resolveLocalized({ en: "SDE", ne: "वरिष्ठ डिभिजनल इन्जिनियर" }, "ne")).toBe(
      "वरिष्ठ डिभिजनल इन्जिनियर",
    );
  });

  it("FALLS BACK to English when Nepali is requested but absent (never fabricates)", () => {
    expect(resolveLocalized({ en: "Ilam Division Office" }, "ne")).toBe("Ilam Division Office");
    expect(resolveLocalized({ en: "Ilam Division Office", ne: "" }, "ne")).toBe(
      "Ilam Division Office",
    );
    expect(resolveLocalized({ en: "Ilam Division Office", ne: null }, "ne")).toBe(
      "Ilam Division Office",
    );
  });

  it("trims surrounding whitespace on the returned Nepali string", () => {
    expect(resolveLocalized({ en: "x", ne: "  क  " }, "ne")).toBe("क");
  });
});

describe("lookup — dictionary accessor with English fallback", () => {
  const en: Record<string, string> = { "a.b": "Alpha", "c.d": "Charlie" };

  it("uses the Nepali overlay when present for the ne locale", () => {
    const ne: Record<string, string> = { "a.b": "अल्फा" };
    expect(lookup<string>("a.b", "ne", en, ne)).toBe("अल्फा");
  });

  it("falls back to English when the Nepali overlay omits the key", () => {
    const ne: Record<string, string> = { "a.b": "अल्फा" };
    expect(lookup<string>("c.d", "ne", en, ne)).toBe("Charlie");
  });

  it("falls back to English when the Nepali overlay has an empty string", () => {
    const ne: Record<string, string> = { "a.b": "" };
    expect(lookup<string>("a.b", "ne", en, ne)).toBe("Alpha");
  });

  it("always returns English for the en locale, ignoring any overlay", () => {
    const ne: Record<string, string> = { "a.b": "अल्फा" };
    expect(lookup<string>("a.b", "en", en, ne)).toBe("Alpha");
  });

  it("returns the key itself as a last resort when it is missing from English", () => {
    // Simulates a mistyped/absent key — a visible dev signal, never a crash.
    const ne: Record<string, string> = {};
    expect(lookup<string>("z.z", "en", en, ne)).toBe("z.z");
  });
});

describe("t — bound to the seeded dictionaries", () => {
  it("returns the seeded English chrome for both locales while NE is translator-gated (empty)", () => {
    // NE_MESSAGES ships empty by design → English fallback in both locales.
    for (const lang of ["en", "ne"] as Lang[]) {
      expect(t("nav.settings", lang)).toBe("Settings");
      expect(t("settings.organisation", lang)).toBe("Organisation");
      expect(t("bilingual.nepaliNameNeeded", lang)).toBe("Nepali name needed");
    }
  });

  it("keeps NE_MESSAGES a strict subset of EN_MESSAGES keys (no orphan Nepali keys)", () => {
    const enKeys = new Set(Object.keys(EN_MESSAGES) as MessageKey[]);
    for (const key of Object.keys(NE_MESSAGES)) {
      expect(enKeys.has(key as MessageKey)).toBe(true);
    }
  });

  it("would surface a verified Nepali override without touching call sites", () => {
    // Proves the wiring: a value present in the overlay is used for `ne`.
    const overlay: Partial<Record<MessageKey, string>> = { "nav.settings": "सेटिङ" };
    expect(lookup("nav.settings", "ne", EN_MESSAGES, overlay)).toBe("सेटिङ");
    expect(lookup("nav.settings", "en", EN_MESSAGES, overlay)).toBe("Settings");
  });
});

describe("language coercion", () => {
  it("narrows valid languages and rejects others", () => {
    expect(isLang("en")).toBe(true);
    expect(isLang("ne")).toBe(true);
    expect(isLang("fr")).toBe(false);
    expect(isLang(null)).toBe(false);
  });

  it("coerces unknown values to English", () => {
    expect(coerceLang("ne")).toBe("ne");
    expect(coerceLang("fr")).toBe("en");
    expect(coerceLang(undefined)).toBe("en");
  });
});
