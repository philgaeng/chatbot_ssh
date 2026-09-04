# QA-04 — Playwright harness against a seeded stack

> **Stream B · 3–4 days · depends on answers to [Q-06…Q-10](QUESTIONS.md) · independent of Stream A**
> **QA-04a is one agent. QA-04b/c/d fan out to one agent each, only after 04a lands.**

## Context

**Nothing in this project can look at a page.** No Playwright, Puppeteer, Cypress or Selenium appears in
any `package.json` or `requirements*.txt`. The existing gates — `tsc --noEmit`, `eslint`, `next build`,
897 backend tests, 11 UI unit tests — prove a change *compiles*. The officer UI is **172 TS/TSX files,
~35.6k lines, 22 routes** with no end-to-end coverage at all.

Three things already exist that make this much cheaper than it looks:

- **Seeding from nothing works and is already in CI.** `import_locations_json` (~837 nodes) then
  `mock_tickets --reset` — the exact commands are in `ci.yml`'s *"Seed KL Road locations + demo
  workflows"* step, and `--reset` is what makes it deterministic.
- **Auth can be bypassed without Keycloak.** A bypass build reads a `grm_bypass_user` cookie
  (`{user_id, role_keys[], organization_id}`) which the Next proxy converts to `X-Internal-*` headers.
  A test sets that cookie and *is* that officer — no login, no OIDC, no Keycloak container.
- **Health endpoints exist** for readiness gating: `ticketing_api` `/health`, `grm_ui` root < 500.

## QA-04a — the harness (this is the blocking piece)

**Deliver a harness plus exactly one canary spec.** Coverage is 04b/c/d. Do not write 30 specs against a
harness nobody has reviewed.

| Piece | Detail |
|---|---|
| Location | `channels/ticketing-ui/e2e/` + `playwright.config.ts` ([Q-06](QUESTIONS.md#q-06--where-do-the-e2e-tests-live)) |
| Naming | e2e files are **`*.spec.ts`** — vitest's `include` is `**/*.test.ts` and the two must not collide |
| Base URL | `E2E_BASE_URL` env, default `http://localhost:3001` — never a hardcoded host |
| Global setup | poll `ticketing_api` `/health` and the UI root until ready or a bounded timeout; **fail with a clear message**, never hang |
| Identity fixture | `asOfficer(roleKeys, userId?)` — sets the `grm_bypass_user` cookie; officer ids come from the seeded roster, not literals invented in the test |
| Projects | desktop chromium + one mobile device ([Q-10](QUESTIONS.md#q-10--is-the-mobile-surface-in-v1)) |
| Artifacts | screenshot + trace **on failure**; screenshot on demand for every route in the smoke pass ([Q-08](QUESTIONS.md#q-08--screenshots-artifacts-only-or-pixel-diffed-baselines)) |
| Canary spec | load `/queue` as a seeded officer, assert a known seeded ticket is visible, capture a screenshot |
| Docs | `docs/engineering/04_testing.md` gains an e2e section: what belongs here vs unit vs integration |

**Determinism is the whole game.** The seed must run with `--reset` before a suite, assertions key off
seeded ids (`GRV-2025-*`), and nothing may depend on wall-clock date or on rows left by a previous run.
A flaky e2e suite is worse than none — it trains everyone to ignore a red build.

## QA-04b — officer-UI route smoke (fan-out, ~1 d)

All **22** `page.tsx` routes, loaded as an appropriately-roled seeded officer: assert no 5xx, no
uncaught console error, no Next error boundary, and capture a screenshot per route. Parameterised
routes (`/tickets/[id]`, `/m/tickets/[id]`, `/closure/[token]`, `/reports/view/[token]`) need a seeded
id or token — get it from the API or the seed, never hardcode. Routes requiring admin get an admin
cookie; the rest an officer cookie.

## QA-04c — the driven flows (fan-out, ~1–1.5 d)

The flows named in [Q-09](QUESTIONS.md#q-09--how-much-of-the-officer-ui-does-v1-cover) — proposed:
queue → open ticket → internal note; escalate; resolve + closure summary; settings → create/edit an
officer; reports → generate an XLSX. **Confirm the list against Q-09's answer before starting**: these
should be the flows reviewers actually break, and the person answering knows that better than the code does.

## QA-04d — the webchat sweep (fan-out, ~1–1.5 d, only if [Q-11](QUESTIONS.md#q-11--does-closing-hr-07s-sweep-belong-in-this-sprint) says yes)

⚠ **A different surface** — `channels/REST_webchat/`, plain JS + socket.io served through nginx, not the
Next app. HR-07's code is merged and in the tree; its **7-item manual sweep was never run** and its
checkbox is still open in `2026-07_hardening/PROGRESS.md`. Automate those items: EN/NE switch, image
upload, voice note, map pin, status check, **send-lock under a dead backend (the 15 s failsafe release)**,
filed-banner rendering, SEAH route entry, session-id persistence and `/clear_session` rotation.

⚠ Read HR-07's deviation rows first: a refresh **does not** resume an in-progress intake — the
orchestrator hard-resets on `/introduce` **by design**. Assert id stability and rotation, *not*
resumption, or you will write a test that encodes a bug report as a requirement.

## Not in scope

Pixel-diff baselines (Q-08 — v1 captures, it does not gate). Any Keycloak login flow beyond the single
smoke test deferred in [Q-07](QUESTIONS.md#q-07--what-auth-mode-does-the-suite-run-against). Load or
performance testing. Editing CI — that is QA-05, and **Stream B must not touch `ci.yml`**.

## Acceptance (04a)

- [ ] `npx playwright test` green against a locally seeded stack, twice in a row, with no shared state between runs
- [ ] The canary fails informatively when the stack is down (clear readiness error, not a 30 s hang)
- [ ] `asOfficer()` demonstrably changes what the UI shows (two roles, two different queues)
- [ ] Screenshots land as artifacts; a trace is produced on a deliberately failed assertion
- [ ] Playwright added as a **devDependency** with a pinned version; browsers installed via `npx playwright install --with-deps` in a documented step
- [ ] `docs/engineering/04_testing.md` updated; `PROGRESS.md` deviations logged

## Risks

- **Flakiness is the failure mode**, not defects. Use web-first assertions and role/label selectors —
  never `waitForTimeout`, never CSS-class selectors that a Tailwind refactor will silently break.
- **The bypass build is a build variant** ([Q-04](QUESTIONS.md#q-04--the-ui-image-bakes-its-auth-mode--do-we-publish-two-variants)).
  Running the suite against a Keycloak-built image will fail confusingly — assert the mode in global
  setup and fail with *"this suite needs an AUTH_MODE=bypass build"*.
- **Seed drift.** If `mock_tickets.py` changes, specs keyed to its ids break. Keep the coupling explicit
  and small: a single `e2e/fixtures/seed.ts` naming every seeded id the suite relies on.
