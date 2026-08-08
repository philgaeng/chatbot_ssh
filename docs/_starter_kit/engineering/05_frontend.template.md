# Frontend standard

**Status:** ‹authoritative› (‹YYYY-MM-DD›).
**Stack: FILL:** ‹framework + version, language, styling›.
**This doc covers code.** Visuals belong to `‹ui/01_design_system.md›`, wording to `‹ui/02_copy_and_tone.md›`, screen behaviour to `‹the UI spec›`. A screen must satisfy all of them.

> **FILL — framework version warning.** If your framework version differs materially from what a model was trained on, say so in bold at the top, and point at the bundled documentation. Agents confidently write last-year's API otherwise.

---

## 1. Who uses this

**FILL:** two sentences — device class, screen quality, connection reliability, language proficiency, attention. This drives the loading/error rules, the legibility floors, and the offline tolerance below. Copy it from the design system §0 so both documents agree.

---

## 2. Structure

**FILL** your layout, then keep these boundaries:

**Rule 2.1 — Route files compose; they do not compute.** A route wires components and hooks; business logic goes to the logic folder, presentation to components.
*Why:* on a real project one route file reached **4,372 lines** before being cut to 301. It was unreviewable, and the bugs inside it were invisible. **FILL** a ceiling (‹~300 lines›) and require a stated reason to exceed it.

**Rule 2.2 — Logic that can be pure, is pure, and lives outside components.** Calculations, parsing, filtering, formatting, permission derivation. This is what makes them testable without a DOM.

**Rule 2.3 — Primitive components know nothing about the domain.** Props in, pixels out. Domain-aware components live in their feature folder.

**Rule 2.4 — Promote to shared on the third use, not the first.** Two call sites is a coincidence.

---

## 3. Data access

**Rule 3.1 — All backend calls go through one client module.** No ad-hoc fetching in a component, ever. *Why:* auth headers, token refresh, session expiry, and error normalization live in one place; a stray call silently skips all four and logs the user out at the worst moment.

**Rule 3.2 — FILL:** how requests reach the backend (relative paths + server-side proxy, or absolute URLs + CORS) and **why**. Never "fix" a proxy problem by opening CORS.

**Rule 3.3 — Client types mirror the server's models.** Nothing enforces this at compile time: **change both sides in the same commit.**

**Rule 3.4 — Every fetch renders three states: loading, error, empty.** Not two. On a slow connection the loading state is what the user sees most, and a silent empty list is indistinguishable from a failure.

**Rule 3.5 — Never trust the client for authorization.** Hiding a control is user experience; the server decides. Every gated action must fail correctly when called directly.

**Rule 3.6 — Shared fetching lives in a hook**, so one data flow serves every surface (desktop, mobile, embedded) instead of being reimplemented per screen.

---

## 4. Components & state

**Rule 4.1 — FILL:** your server/client component policy, or your rendering strategy. If the current codebase mostly violates the ideal, say so and mark it **status quo, not target** — an unstated gap gets copied.

**Rule 4.2 — State lives at the lowest level that needs it.** Lift only when a second consumer appears. No global store for what one screen owns.

**Rule 4.3 — Derive, don't duplicate.** A second copy of server data in local state is a desync waiting to happen.

**Rule 4.4 — List keys come from the domain**, never the array index.

**Rule 4.5 — Effects synchronize with something outside the framework.** Not for computing values, not for chaining state updates.

**Rule 4.6 — No escape hatches from the type system.** A suppression comment is a **deferral** and must be logged.

**Rule 4.7 — Optimistic updates need a rollback path.** On a flaky connection, an optimistic action that silently fails leaves the user believing something happened that didn't. **FILL:** name the action in your product where this would be worst.

---

## 5. Errors, loading, empty

**Rule 5.1 — Errors reach the user through one formatter and one error component.** Never a raw message, status code, or response body.
**Rule 5.2 — An error says what to do next**, with a retry control where retrying helps.
**Rule 5.3 — Framework-level error boundaries are a safety net, not the plan.** Handle expected failures where they happen.
**Rule 5.4 — Empty state = what it is + the one next action.**
**Rule 5.5 — Consequential actions confirm, stating the effect in one line.**

---

## 6. Auth

**Rule 6.1 — FILL:** the mechanism, and where identity handling lives. Nothing outside that folder parses or stores a token.
**Rule 6.2 — Token refresh and session expiry are handled once, inside the API client**, for every call.
**Rule 6.3 — Route guarding is centralized.** Role checks inside components are an affordance on top, never the control.

---

## 7. Performance

**Rule 7.1 — Assume the device and connection from §1.** Ship less; avoid a heavy library for a small job.
**Rule 7.2 — No new UI or icon library without a recorded decision.** → ‹design system›
**Rule 7.3 — Paginate at the API; never fetch-all-and-filter-in-the-browser.**
**Rule 7.4 — Optimize images; bound upload sizes client-side.**

---

## 8. Accessibility

**Rule 8.1 — Contrast floors from the design system §2.2** apply to every information-carrying element.
**Rule 8.2 — Colour is never the only signal.** Pair with a word or icon.
**Rule 8.3 — Semantic HTML, keyboard reachable, visible focus.** A clickable `<div>` is a bug.
**Rule 8.4 — Real labels on every input; accessible names on icon-only controls.**
**Rule 8.5 — Touch targets ≥ 44px on mobile surfaces.**
**FILL:** your conformance target and how it is checked.

---

## 9. Internationalization

**Rule 9.1 — FILL:** the source-of-record language and which surfaces are translated.
**Rule 9.2 — Never fabricate a translation.** No machine translation into shipped UI.
**Rule 9.3 — FILL:** date, number, and currency formats. Never ambiguous numeric dates.
**Rule 9.4 — No string concatenation to build a sentence.** Word order differs between languages.

---

## 10. Definition of done — a screen

- [ ] Type-check and lint clean, no new suppressions
- [ ] Tests pass; new pure logic has a unit test
- [ ] Loading, error, and empty states all render
- [ ] Copy checked against the copy guide, including the canonical vocabulary
- [ ] Tokens and icons from the design system; no new hue family
- [ ] Keyboard reachable; contrast floors met; colour never the only signal
- [ ] Client types match the server, changed in the same commit
- [ ] Other surfaces (mobile, print, email) handled or explicitly out of scope in the pull request
- [ ] The UI spec updated if behaviour changed

---

## 11. Known deviations — do not extend

| Deviation | Where | Target |
|---|---|---|
| ‹…› | ‹path or command› | ‹rule› |
