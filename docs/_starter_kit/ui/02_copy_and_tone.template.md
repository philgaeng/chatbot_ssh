# ‹Product› — Copy & tone guide

**Status:** ‹authoritative | draft› (‹YYYY-MM-DD›). The **single source for on-screen wording**.
**Companion:** `‹docs/…/01_design_system.md›` owns **pixels**. This doc owns **words**.
**Scope:** every user-facing string — labels, buttons, help text, empty states, errors, notifications, emails. Internal specifications may use precise technical terms *with a definition*; those terms must not surface in the interface.

> **How to use this template.** `‹…›` = substitute. **FILL:** = decide and record the reason. §0 and §4.1 first — they determine everything else, and both are painful to retrofit.

---

## 0. Who we write for

**FILL:** Two or three sentences describing the actual reader. Language proficiency, domain expertise, technical literacy, and how much attention they have. Then state the standard that follows from it.

> *Worked example:* "**⚑ WHO WE WRITE FOR — ‹government officials›.** Every screen is read by ‹a career civil servant in a district office›: capable and experienced, but reading **‹English as a second language›** and **not technical**. So the standard is **simple, short, straightforward** — plain everyday words, one idea per sentence, no cleverness. **When two words both fit, choose the simpler, more common one.** If a sentence needs a second read, rewrite it."

This paragraph is the primary test for every string in the product. Put it at the top, in bold, and appeal to it in review instead of arguing taste.

---

## 1. Language & locale

**Rule 1.1 — One source-of-record language. FILL:** ‹language›. Every other locale is a translation *of it*, never an independent edit.

**Rule 1.2 — Never fabricate a translation.** No machine translation into shipped UI, and no invented term in a language you don't have a reviewer for. A wrong translation in a government or medical interface is worse than English.

**Rule 1.3 — Dates. FILL:** ‹format and calendar — e.g. `15 Shrawan 2082 BS`, or `3 Aug 2026`›. State whether more than one calendar may appear, and where. Ambiguous formats (`03/08/26`) are banned outright — half your users read it as March.

**Rule 1.4 — Numbers, currency, units. FILL:** ‹grouping, decimal separator, currency position, unit format›.

**Rule 1.5 — No string concatenation to build a sentence.** Word order differs between languages; build whole strings with named placeholders (`"{count} tickets overdue"`), never `count + " tickets overdue"`.

---

## 2. Voice — the rules

1. **Plain words over jargon.** If your reader in §0 wouldn't say it, don't write it. See the glossary (§4).
2. **Sentence case.** Not Title Case. ALL CAPS only for tiny eyebrow labels.
3. **Active voice, and name the outcome.** A button says what it does ("Save", "Send", "Activate"); the confirmation says it happened ("Saved", "Invitation sent").
4. **Short.** One idea per sentence. Help text ≤ ‹15› words.
5. **No developer copy.** No slugs, table or field names, HTTP status codes, stack traces, or "run migrations". Route every error through the shared formatter and error component.
6. **Severity in words, not colour alone.** Write "Blocks release" — don't rely on a red dot. *(This is an accessibility rule as much as a copy rule.)*
7. **Define or avoid acronyms** on first use. List the exceptions explicitly.
8. **Give the one-line *why*** where a rule isn't obvious: *"A default is used when nothing else matches."*
9. **Address the user as "you"; refer to the system as "we" sparingly, or not at all.**
10. **No description when it's self-explanatory.** If the title already carries the meaning, add **no** help text. Add a line only when it prevents a real error. Every extra sentence is a tax on a second-language reader — and users learn to skip screens that over-explain.

---

## 3. Patterns by element

| Element | Rule | Good | Bad |
|---|---|---|---|
| **Button** | The outcome, imperative | "Save", "Invite", "Activate" | "Submit", "OK", "Proceed" |
| **Destructive confirm** | One line stating the effect, then the verb | "Delete this ‹record›? This cannot be undone." | "Are you sure?" |
| **Toast / confirmation** | Past tense, the same word as the button | "Saved", "Invitation sent" | "Operation completed successfully" |
| **Empty state** | What it is + the single next action | "No ‹items› yet. ‹Verb› to add one." | "No data" |
| **Error** | What went wrong + how to fix it. No codes. | "Could not load ‹items›. Check your connection and try again." | "Error 500: internal server error" |
| **Help text** | One plain sentence, under the field title | "Used when nothing else matches." | A paragraph |
| **Loading** | Say what is loading if it exceeds ~1s | "Loading ‹items›…" | A bare spinner |
| **Field label** | Noun phrase, sentence case, no colon | "Phone number" | "Enter Your Phone Number:" |
| **Required / optional** | Mark the rarer one only | — | Marking every field |

**Rule 3.1 — An error message that a user cannot act on is a bug**, not a message. If there is no action, say what happens next: "We've logged this. Try again in a few minutes."

**Rule 3.2 — Never blame the user.** "That email address isn't recognised", not "You entered an invalid email".

---

## 4. Glossary

### 4.1 Canonical vocabulary — one word per concept, project-wide

**This is the most valuable table in the document.** Use the same word for the same thing on every screen, in the code, in the schema, and in the specifications. Extend it — never fork it — when a new recurring concept appears.

**FILL:** one row per core domain concept.

| Concept | Use | Don't use |
|---|---|---|
| ‹the central record› | **‹word›** | ‹synonyms that have appeared› |
| ‹the person outside the org› | **‹word›** | ‹…› |
| ‹the person inside the org› | **‹word›** | ‹…› |
| ‹the main process› | **‹word›** | ‹…› |
| ‹a stage in that process› | **‹word›** | ‹…› |
| ‹the act of moving it forward› | **‹word›** | ‹…› |
| ‹the act of ending it› | **‹word›** | ‹…› |

*Why this matters more than it looks:* synonyms are how one team ends up with two mental models of the same object. When the interface says "case", the API says "ticket", and the database says "grievance", every conversation and every code review pays a small tax forever — and new joiners believe they are three different things.

**Rule 4.1 — Mark code-only terms explicitly.** Some internal names cannot be renamed cheaply. List them and forbid them on screen:

> † *Internal / code term — never surface it:* `‹ticket›` (code name for ‹the record›), `‹step›` (code name for ‹a level›).

**Rule 4.2 — Record the date a term was decided.** "Decided ‹YYYY-MM-DD›: always ‹word A›, never ‹word B›" ends the argument permanently.

### 4.2 Avoid → use

Jargon, metaphor, and internal shorthand that must not reach a screen:

| Avoid (internal / jargon) | Use on screen |
|---|---|
| ‹internal metaphor› | ‹plain word› |

### 4.3 Keep — correct domain terms

Words that *look* like jargon but are the right, precise term for this domain, and that your users already use. **FILL:** ‹list›. Expanding an acronym once on first use is usually enough.

---

## 5. Notifications & long-form

**Rule 5.1 — A notification says who did what, to what, and what you should do.** "‹Officer› ‹escalated› ‹REF-123›. It's now assigned to you."

**Rule 5.2 — Email subject lines are scannable and prefixed** with the reference where one exists.

**Rule 5.3 — The same event uses the same wording in every channel** — in-app, email, SMS. Three phrasings of one event read as three events.

**Rule 5.4 — SMS gets the reference and one instruction.** No links that require a login the recipient doesn't have.

---

## 6. Enforcement

**Rule 6.1 — Every user-facing string goes through the shared helpers:** the role/label formatter, the error formatter and error component, the translation wrapper. A raw string in a component bypasses every rule above.

**Rule 6.2 — New or changed screens: copy is checked against §2 and §4 before merge.** Add it to the pull-request checklist — this is a review gate, not an automated one, and saying so is more honest than pretending a linter catches it.

**Rule 6.3 — Status labels here and in the design-system token file are the same decision.** Change both in one commit.

**FILL:** any automated checks you add — a banned-words lint, a check that no component contains a literal string outside the i18n layer, a spell-check in CI.

---

## 7. Known deviations — do not extend

| Deviation | Where | Target |
|---|---|---|
| ‹wording that predates this guide› | ‹path or search command› | ‹the rule› |

**Rule 7.1 — A project-wide rename is a decision with a cost.** List a proposed rename here as "recommended" until it is approved, rather than half-applying it — half a rename is worse than neither word.
