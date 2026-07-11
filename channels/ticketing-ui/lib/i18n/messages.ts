/**
 * i18n/messages.ts — the EN/NE message dictionaries + a typed accessor (RB-1).
 *
 * `EN_MESSAGES` is the source of record and is COMPLETE — every key has an English
 * string. `NE_MESSAGES` is a *partial* Nepali overlay. It is INTENTIONALLY (near-)empty:
 * per DESIGN §D4 and the sprint README, Nepali chrome copy is **translator-gated and must
 * never be fabricated**. Any key missing from `NE_MESSAGES` falls back to English via
 * `lookup()`. When a translator supplies a verified Nepali string, it is added here keyed
 * by `MessageKey` and lights up with no other code change.
 *
 * This is scaffolding: a small seeded set of common nav / settings / action chrome — the
 * pattern to grow, not a full translation pass (that is the wider RB-2/3/4 sweep).
 */

import { type Lang, lookup } from "./resolve";

// ── English source of record (complete) ──────────────────────────────────────
export const EN_MESSAGES = {
  // App chrome
  "app.name": "GRM Ticketing",

  // Sidebar / mobile navigation (common labels)
  "nav.tickets": "Tickets",
  "nav.reports": "Reports",
  "nav.qrCodes": "QR Codes",
  "nav.settings": "Settings",
  "nav.projectSetup": "Project setup",
  "nav.help": "Help",
  "nav.signOut": "Sign out",
  "nav.queue": "Queue",
  "nav.all": "All",
  "nav.tasks": "Tasks",

  // Settings information architecture — 4 domain tabs + Setup landing (DESIGN §2.1 / D1)
  "settings.title": "Settings",
  "settings.setupAndGoLive": "Setup & go-live",
  "settings.organisation": "Organisation",
  "settings.workflowsAndRoles": "Workflows & roles",
  "settings.projects": "Projects",
  "settings.platform": "Platform",

  // Common actions / states
  "common.loading": "Loading…",
  "common.save": "Save",
  "common.cancel": "Cancel",
  "common.edit": "Edit",
  "common.delete": "Delete",
  "common.add": "Add",
  "common.close": "Close",
  "common.confirm": "Confirm",
  "common.back": "Back",
  "common.next": "Next",

  // Bilingual affordance (DESIGN §7.C) — chip shown when a Nepali name is absent
  "bilingual.nepaliNameNeeded": "Nepali name needed",
} as const;

export type MessageKey = keyof typeof EN_MESSAGES;

/**
 * Nepali overlay — a *partial* map over MessageKey.
 * TRANSLATOR-GATED: leave keys absent until a verified Nepali string exists. Never invent
 * Nepali here (DESIGN §D4). Absent / empty ⇒ English fallback (see `lookup`).
 */
export const NE_MESSAGES: Partial<Record<MessageKey, string>> = {
  // (empty by design — awaiting translator-verified Nepali chrome copy)
};

/** Translate a chrome message key for the active language, with English fallback. */
export function t(key: MessageKey, lang: Lang): string {
  return lookup(key, lang, EN_MESSAGES, NE_MESSAGES);
}
