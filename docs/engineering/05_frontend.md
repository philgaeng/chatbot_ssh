# Frontend standard — officer portal

**Status:** authoritative (2026-09-06). Rules for **code** in `channels/ticketing-ui/` (Next.js 16 App Router, React 19, TypeScript, Tailwind v4).
**Last updated:** 2026-09-07 — §9a gains **rule 9a.4**: once a screen ships, the shipped screen is the wireframe baseline and a mockup of it is retired rather than maintained. The `ui/04` row is marked **superseded** rather than merely stale, closing `GRM-064`. Earlier: §9a added: the design gate (G-DESIGN) is written down, having been followed once by instinct and recorded nowhere; plus what the two committed `ui/*.html` mockups bind, and what they do not.
**This doc does not cover visuals or wording.** Two standards already own those and win on their subjects:

| Subject | Owner |
|---|---|
| Colour, icons, tokens, WCAG floors, badges, spacing patterns | [`ui/02_design_system.md`](../ticketing_system/ui/02_design_system.md) |
| Every user-facing string, vocabulary, tone, dates | [`ui/05_ui_copy_style.md`](../ticketing_system/ui/05_ui_copy_style.md) |
| Routes, screens, queue/thread behaviour (the *spec*) | [`ui/01_ui_spec.md`](../ticketing_system/ui/01_ui_spec.md) |

> ⚠ **Next.js 16 is not the Next.js in your training data.** APIs, conventions and file structure differ. Read the relevant guide in `node_modules/next/dist/docs/` before writing App Router code, and heed deprecation notices. (This is also the whole content of `channels/ticketing-ui/AGENTS.md`.)

---

## 1. Who this is for

Every screen is used by a Nepali government official — competent, experienced, **reading English as a second language, not technical**, often on a low-end Android or a budget monitor in glare, sometimes on an intermittent connection. That single fact drives most rules below: legibility floors, explicit loading/error states, offline-tolerant behaviour, no cleverness.

---

## 2. Structure

```
channels/ticketing-ui/
  app/            Routes (App Router). One folder per route; `page.tsx` is thin.
    api/          Server route handlers — the API proxy lives here
    providers/    React context providers (auth, …)
    m/            Mobile app routes  → lib/mobile-routes.ts maps desktop ↔ mobile
  components/
    ui/           Primitives (Badge, ErrorCard, SlaCountdown, VaultReveal)
    shared/       Cross-cutting behaviour (Bilingual, ErrorNotice, RoleLabel, SeverityBadge)
    thread/       Ticket thread
    settings/ reports/ tickets/ mobile/    Feature components
  lib/            All non-render logic: api client, auth, i18n, pure helpers, hooks
  middleware.ts   Route guarding
```

**Rule 2.1 — `page.tsx` composes; it does not compute.** A route file wires components and hooks together. Business logic goes to `lib/`, presentation to `components/`.
*Why, from this codebase:* `app/settings/page.tsx` reached **4,372 lines** before being cut to 301 in Tier-3. That file was unreviewable, and the bugs in it were invisible. Under ~300 lines per route file, no exceptions without a reason in the PR.

**Rule 2.2 — Logic that can be pure, is pure, and lives in `lib/`.** Tile counting, SLA urgency, command parsing, error formatting, jurisdiction filtering are pure functions today (`queueTiles.ts`, `threadCommands.ts`, `user-messages.ts`, `officerJurisdiction.ts`). That is what makes them testable without a DOM. Keep the pattern.

**Rule 2.3 — A component in `components/ui/` knows nothing about the domain.** It takes props and renders. Domain-aware components go in the feature folder.

**Rule 2.4 — Promote to `shared/` on the third use**, not the first. Two call sites is a coincidence; three is a pattern.

---

## 3. Data access

**Rule 3.1 — All backend calls go through `lib/api.ts`.** No `fetch()` in a component, ever.
*Why:* auth headers, token refresh, session-expiry handling, and error normalization live in one place. A stray `fetch` silently skips all four and logs the user out at the worst moment.

**Rule 3.2 — Requests use relative paths** (`/api/v1/...`). They are proxied server-side by `app/api/v1/[...path]/route.ts`, which reads `TICKETING_API_URL` **at request time** so Docker service names work without being baked into the image. Never put an absolute API URL in client code, and never "fix" a proxy problem by opening CORS.

**Rule 3.3 — Response types in `lib/api.ts` mirror the backend Pydantic models by hand.** They are a contract with no compiler enforcing it: **change both sides in the same commit** ([03 §3.6](03_api_layer.md#3-schemas-pydantic-v2)).

**Rule 3.4 — Every fetch has three rendered states: loading, error, empty.** Not two. On a rural connection the loading state is what the officer looks at most, and a silent empty list is indistinguishable from a failure.

**Rule 3.5 — Never trust the client for authorization.** Hiding a button is UX; the server decides. Every gated action must fail correctly if called directly.

**Rule 3.6 — Fetch in a hook, not in a component body.** Shared fetching lives in a `use*` hook in `lib/` (`useTicketThread.ts`), so the same data flow serves desktop and `/m` without a second implementation.

---

## 4. React & rendering

**Rule 4.1 — Server Component by default; `"use client"` only when the component needs interactivity, browser APIs, or context.**
*Honest current state:* 108 of 112 components are client components, because auth is browser-held PKCE OIDC. Treat that as the **status quo, not the target** — new leaf components that only render data should not add `"use client"`. Do not restructure existing ones as a side quest.

**Rule 4.2 — State lives at the lowest level that needs it.** Lift only when a second consumer appears. No global store for what one screen owns.

**Rule 4.3 — Derive, don't duplicate.** If a value can be computed from props or fetched data, compute it. A second `useState` mirroring server data is a desync waiting to happen.

**Rule 4.4 — Lists have stable keys from the domain** (`ticket_id`), never the array index.

**Rule 4.5 — Effects are for synchronizing with something outside React.** Not for computing values, not for chaining state updates.

**Rule 4.6 — No `any`.** `unknown` plus a narrow is the escape hatch. A `// @ts-expect-error` is a **deferral** and must be logged ([04 §8](04_testing.md#8-when-you-cannot-test-it-now)).

**Rule 4.7 — Optimistic updates need a rollback path.** On a flaky connection an optimistic action that silently fails leaves the officer believing a grievance was escalated when it wasn't.

---

## 5. Errors, loading, empty

**Rule 5.1 — Errors reach the user through `formatUserFacingError` + `ErrorNotice`/`ErrorCard`.** Never a raw message, status code, or JSON body. → [`ui/05`](../ticketing_system/ui/05_ui_copy_style.md) rule 5

**Rule 5.2 — An error tells the user what to do next.** "Could not load tickets. Check your connection and try again." — with a retry control.

**Rule 5.3 — Route-level `error.tsx` and `global-error.tsx` are the safety net, not the plan.** Handle expected failures where they happen.

**Rule 5.4 — Empty state = what it is + the one next action.** "No locations linked yet. Search to add one."

**Rule 5.5 — A destructive or consequential action confirms, stating the effect in one line.**

---

## 6. Auth

**Rule 6.1 — Keycloak PKCE OIDC. Identity handling stays in `lib/auth/`** (`oidc-auth.ts`, `token-storage.ts`, `session-expired.ts`) and `app/providers/AuthProvider.tsx`. Nothing else parses or stores a token.

**Rule 6.2 — Token refresh and session expiry are handled inside `lib/api.ts`**, once, for every call.

**Rule 6.3 — Route guarding is `middleware.ts` + the auth provider.** Role checks in a component are a UX affordance on top, never the control.

**Rule 6.4 — `cognito-auth.ts` is dead weight from the superseded plan** — Keycloak is the as-built system ([`16_auth_keycloak.md`](../deployment/16_auth_keycloak.md)). Don't build on it; delete it when you're in there.

---

## 7. Performance on the target device

**Rule 7.1 — Assume a low-end Android and an intermittent connection.** Ship less JS; avoid a heavy library for a small job.

**Rule 7.2 — No new UI or icon library.** Lucide via `@/lib/icons`, Tailwind v4. Adding a component library is an architecture decision, not a convenience. → [`ui/02`](../ticketing_system/ui/02_design_system.md)

**Rule 7.3 — Paginate every list at the API; never fetch-all-and-filter-in-the-browser.**

**Rule 7.4 — Images through `next/image`; no unbounded uploads without a client-side size check.**

---

## 8. Accessibility (non-negotiable, this is a government service)

**Rule 8.1 — WCAG AA contrast floors from [`ui/02 §3`](../ticketing_system/ui/02_design_system.md).** `text-gray-600` is the floor for any text that carries information; `text-gray-400` is decoration only.

**Rule 8.2 — Colour is never the only signal.** Pair every colour with a word or an icon — low literacy, colour blindness, and cheap monitors all break colour-only meaning. → [`ui/05`](../ticketing_system/ui/05_ui_copy_style.md) rule 6

**Rule 8.3 — Keyboard reachable, visible focus, semantic HTML.** A `<div onClick>` is a bug. Buttons are `<button>`, links are `<a>`.

**Rule 8.4 — Every input has a real `<label>`; every icon-only control has an accessible name.**

**Rule 8.5 — Tap targets ≥ 44px on `/m` routes.**

---

## 9. i18n

**Rule 9.1 — English is the source of record for the officer portal.** Nepali (`<Bilingual>`, `lib/i18n/`) applies to complainant-facing surfaces and to name fields where a real `_ne` value exists.

**Rule 9.2 — Never fabricate Nepali.** No machine translation into the UI.

**Rule 9.3 — Dates on officer/admin surfaces are Bikram Sambat only** — `15 Shrawan 2082 BS`. No Gregorian on screen.

**Rule 9.4 — No string concatenation to build a sentence.** Word order differs; build whole strings.

---

## 9a. The design gate (G-DESIGN)

**Fires when a UI surface changes shape** — a new screen, a screen reorganised, or a component whose
information architecture changes. Not for restyling inside an existing layout.

⚠ **This gate was followed once, correctly, by instinct — the settings redesign — and then existed
nowhere.** That is the failure mode this section closes: a process that lives only in the memory of
whoever ran it last is not a gate, and the next person reinvents a worse version of it.

**Six steps, in order. Each one is cheap to redo and expensive to skip.**

| # | Step | Produces | Why it is before the next one |
|---|---|---|---|
| 1 | **Brief** | what the screen is for, who uses it, what they are trying to finish | Everything downstream is unfalsifiable without it |
| 2 | **IA** | the objects on the screen and their containment — what nests inside what | Getting containment wrong is the one mistake a visual pass cannot rescue |
| 3 | **Wireframe** | layout and hierarchy, no colour, no final copy | Colour arrives early enough to hide a bad hierarchy; keep it out |
| 4 | **Direction** | the visual pass against [`ui/02`](../ticketing_system/ui/02_design_system.md) — tokens, palette, icons | The design system decides this, not the screen |
| 5 | **State + responsive contract** | loading · error · empty · dense-data · the 360 px case | These are half the work and they are where "done" screens fail review |
| 6 | **Implementation contract, frozen** | the props, the API shape, the copy strings | ⭐ **Frozen before build starts.** Unfrozen, the contract drifts during implementation and the spec becomes a description of whatever was easiest |

**Rule 9a.1 — A mockup is a `.html` file committed next to the spec it serves**, in
[`../ticketing_system/ui/`](../ticketing_system/ui/). *Why: it opens in a browser from a clone, it
diffs, it survives the tool that produced it, and it cannot 404 the way a hosted preview does. A
mockup that lives in a chat window or a hosted artifact is gone the moment anyone needs it most.*

**Rule 9a.2 — Say what a mockup binds, and what it does not.** A mockup binds **IA and layout** —
steps 2, 3 and 5. It does **not** bind colour values, copy, or component structure: those are owned by
[`ui/02`](../ticketing_system/ui/02_design_system.md), [`ui/05`](../ticketing_system/ui/05_ui_copy_style.md)
and the implementation contract respectively. *Why: a mockup read as binding on everything makes the
design system advisory, which is backwards.*

The two live mockups, and what each binds:

| Mockup | Binds | Read with |
|---|---|---|
| ~~[`ui/04_projects_packages_redesign.html`](../ticketing_system/ui/04_projects_packages_redesign.html)~~ — *"KL Road · Project setup (redesign)"* | ⚠ **SUPERSEDED 2026-09-07 — binds nothing.** The shipped screen (`Settings → Projects & packages`) is the baseline; the file is kept as the historical record of the redesign decision and carries a banner saying so | [`04_projects_packages_ux_review.md`](../ticketing_system/ui/04_projects_packages_ux_review.md) · closed `GRM-064` |
| [`ui/06_workflows_step_cast_editor.html`](../ticketing_system/ui/06_workflows_step_cast_editor.html) — *"Workflows — step cast editor"* | The step/cast editing model: which roles a step casts, and how exclusions read | [`01_ui_spec.md`](../ticketing_system/ui/01_ui_spec.md) |

**Rule 9a.3 — A stale mockup is marked stale where it is cited, not silently left to mislead.** *Why:
a mockup is trusted precisely because it is concrete; a wrong one is therefore more expensive than no
mockup at all, and it is the artifact least likely to be re-read by whoever changed the design.*

**Rule 9a.4 — Once a screen ships, the shipped screen is the wireframe baseline, and a mockup of it
is retired rather than maintained.** A change to a live screen states its **delta** against what
renders today; step 3 produces a new `.html` only for a surface that exists on no shipped screen.
*Why: a mockup earns its cost when it decides a shape nobody has seen. Redrawing a screen that opens
in a browser today is transcription — and a transcribed mockup is the artifact most likely to go
stale again, because nobody re-reads it after the screen moves. Worked example: `ui/04` above went
stale exactly this way; ✅ **applied 2026-09-07** by the `settings-ui` lane, whose six items bind to
shipped routes and whose one genuinely new surface — a filter bar over a tree — still owes a
committed wireframe.*

---

## 10. Definition of done — a screen

- [ ] `npx tsc --noEmit` clean, `npx eslint .` clean (no new suppressions)
- [ ] `npm test` passes; new pure logic in `lib/` has a unit test
- [ ] Loading, error, and empty states all render
- [ ] Copy checked against [`ui/05`](../ticketing_system/ui/05_ui_copy_style.md) §2 + §4 (canonical vocabulary)
- [ ] Colours/tokens/icons from [`ui/02`](../ticketing_system/ui/02_design_system.md); no new hue family, no emoji as icon
- [ ] Keyboard reachable; contrast floors met; colour never the only signal
- [ ] `lib/api.ts` types match the backend schema, changed in the same commit
- [ ] Mobile route considered (`lib/mobile-routes.ts`) or explicitly out of scope in the PR
- [ ] [`ui/01_ui_spec.md`](../ticketing_system/ui/01_ui_spec.md) updated if behaviour changed
- [ ] If the surface changed **shape**, the design gate (§9a) ran — and its implementation contract was frozen *before* the build, not written afterwards to match it

---

## 11. Known deviations — do not extend

| Deviation | Where | Target |
|---|---|---|
| Direct `lucide-react` imports | `NoteBubble.tsx`, `FilterChips.tsx`, `SlaCountdown.tsx` | import aliases from `@/lib/icons` |
| Off-palette hues (`purple`, `teal`, `emerald`, `sky`, `yellow`, `indigo`) | `mobile-constants.ts`, `NoteBubble.tsx`, `queue/page.tsx` | the 5-family palette in [`ui/02 §2`](../ticketing_system/ui/02_design_system.md) |
| 🌐 literal emoji on translation strips | `NoteBubble.tsx` | `IconTranslation` |
| Duplicate SLA/urgency helpers | `lib/mobile-constants.ts` vs `lib/design-tokens.ts` | converge on `design-tokens.ts` |
| Dead Cognito auth module | `lib/auth/cognito-auth.ts` | delete |
| Boilerplate README | `channels/ticketing-ui/README.md` (still create-next-app text) | replace with a real one |
