# QA-04 — Playwright harness against a seeded stack

> **Stream B · 4.5–6 days (04a+b+c+d), +2–3 d if QA-04c tier 2 stays in · independent of Stream A — can start today**
> ✅ **Q-06…Q-12 answered 2026-09-04** — decisions are inline; [`QUESTIONS.md`](QUESTIONS.md) keeps the reasoning.
> ⚠ **Revised 2026-09-04 after a completeness review** — three additions: the `package.json` edit is
> not isolated from Stream A's image, three parameterised routes have no seeded value, and two QA-04d
> items cost money or take the stack down.
> **QA-04a is one agent. QA-04b/c/d fan out to one agent each, only after 04a lands.**

## Context

**Nothing in this project can look at a page.** No Playwright, Puppeteer, Cypress or Selenium appears in
any `package.json` or `requirements*.txt`. The existing gates — `tsc --noEmit`, `eslint`, `next build`,
897 backend tests, 12 UI unit-test files (all pure logic under `lib/`, none touching a rendered page)
— prove a change *compiles*. The officer UI is **180 TS/TSX files, 22 routes** with no end-to-end
coverage at all.

Three things already exist that make this much cheaper than it looks:

- **Seeding from nothing works and is already in CI.** `import_locations_json` (~837 nodes) then
  `mock_tickets --reset` — the exact commands are in `ci.yml`'s *"Seed KL Road locations + demo
  workflows"* step, and `--reset` is what makes it deterministic.
- **Auth can be bypassed without Keycloak.** A bypass build reads a `grm_bypass_user` cookie
  (`{user_id, role_keys[], organization_id}`) which the Next proxy converts to `X-Internal-*` headers.
  A test sets that cookie and *is* that officer — no login, no OIDC, no Keycloak container.
- **Health endpoints exist** for readiness gating: `ticketing_api` `/health`, `grm_ui` root < 500.

## Scope

| Sub-ticket | What | Est. | Agent |
|---|---|---|---|
| **QA-04a** | The harness: config, fixtures, auth, readiness, artifacts, **one** canary spec | 1.5–2 d | one |
| **QA-04b** | Officer-UI route smoke — all 22 routes | ~1 d | one, after 04a |
| **QA-04c** | Driven flows — tier 1 (the five) then tier 2 (**"all the flows"**, Q-09) | 1–1.5 d **+2–3 d** | one, after 04a |
| **QA-04d** | Webchat sweep (HR-07's never-run items), through nginx | 1–1.5 d | one, after 04a |

**04b/c/d touch disjoint files** (`e2e/smoke/`, `e2e/flows/`, `e2e/webchat/`) and share only the
fixtures 04a creates. That is what makes them safe to **develop** in parallel — three agents, no merge
conflicts. ⚠ It does **not** make them safe to **run** in parallel against one stack: they share a
database and a set of containers, and 04d's dead-backend item is destructive. Development parallelism
and runtime parallelism are different claims; see QA-04d.

## Files

| File | Change | Ticket |
|---|---|---|
| `channels/ticketing-ui/playwright.config.ts` | **new** — projects (desktop + mobile), `E2E_BASE_URL`, artifacts, `testDir: e2e` | 04a |
| `channels/ticketing-ui/e2e/global-setup.ts` | **new** — readiness poll, auth-mode assertion | 04a |
| `channels/ticketing-ui/e2e/fixtures/officer.ts` | **new** — `asOfficer(roleKeys, userId?)` cookie fixture | 04a |
| `channels/ticketing-ui/e2e/fixtures/seed.ts` | **new** — the single place naming every seeded id the suite relies on | 04a |
| `channels/ticketing-ui/e2e/queue.spec.ts` | **new** — the canary | 04a |
| `channels/ticketing-ui/package.json` | **`@playwright/test`** as a pinned devDependency + an `e2e` script | 04a |
| `channels/ticketing-ui/.dockerignore` | add `e2e/`, `playwright.config.ts`, `test-results/`, `playwright-report/` | 04a |
| `channels/ticketing-ui/e2e/smoke/*.spec.ts` | **new** — 22 routes | 04b |
| `channels/ticketing-ui/e2e/flows/*.spec.ts` | **new** — tier 1 (five), then tier 2 groups, one file each | 04c |
| `channels/ticketing-ui/e2e/webchat/*.spec.ts` | **new** — HR-07's items, via nginx | 04d |
| `channels/ticketing-ui/.gitignore` | ignore `test-results/`, `playwright-report/` | 04a |
| `docs/engineering/04_testing.md` | an e2e section: what belongs here vs unit vs integration, and how to run it | 04a |

⚠ **`vitest.config.ts` must keep ignoring `e2e/`.** Its `include` is `**/*.test.ts`, so `*.spec.ts`
files are already outside it — **verify that rather than assuming**, because a vitest run that picks up
a Playwright spec fails in a way that reads like a broken test, not a misconfiguration.

⚠ **The `package.json` edit is not as isolated as it looks — it reaches into Stream A's image.**
The README says Stream B touches only `e2e/` plus a devDependency. But `channels/ticketing-ui/Dockerfile`
runs a full `npm ci` in the builder stage (`:14`, dev dependencies included) and then `COPY . .`, so
whatever Stream B adds is installed **during the UI image build** — on the 3825 MB host QA-01 exists to
protect. Three consequences, all cheap if handled up front and confusing if not:

1. **Depend on `@playwright/test`, not `playwright`.** The bare `playwright` package downloads browser
   binaries in a postinstall — several hundred MB, inside the Docker build.
2. **Set `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` in the builder stage** as a belt-and-braces guard, with a
   comment saying the image never runs tests.
3. **Add `e2e/` to `channels/ticketing-ui/.dockerignore`** — today it lists only `node_modules`, `.next`,
   `.git`, `*.log`, `.DS_Store`, `Thumbs.db`, so specs would otherwise be copied into the image.

Coordinate 1 and 2 with Stream A rather than editing the Dockerfile unilaterally — it is QA-01's file.

## QA-04a — the harness (this is the blocking piece)

**Deliver a harness plus exactly one canary spec.** Coverage is 04b/c/d. Do not write 30 specs against a
harness nobody has reviewed.

| Piece | Detail |
|---|---|
| Location | **`channels/ticketing-ui/e2e/`** + `playwright.config.ts` beside it |
| Naming | e2e files are **`*.spec.ts`** — vitest's `include` is `**/*.test.ts` and the two must not collide |
| Base URL | `E2E_BASE_URL` env, default `http://localhost:3001` — never a hardcoded host |
| Global setup | poll `ticketing_api` `/health` and the UI root until ready or a bounded timeout; **fail with a clear message**, never hang |
| Auth | **bypass build for the whole suite** — no Keycloak container. A Keycloak login smoke test is deferred to its own job, later |
| Reached via | **direct to `grm_ui:3001`** for the officer UI (the webchat goes through nginx — see QA-04d) |
| Identity fixture | `asOfficer(roleKeys, userId?)` — sets the `grm_bypass_user` cookie; officer ids come from the seeded roster, not literals invented in the test |
| Projects | desktop chromium + **one mobile device** (mobile is in v1, smoke only) |
| Artifacts | screenshot + trace **on failure**; screenshot on demand for every route in the smoke pass. **No pixel-diff gate in v1** — captures only |
| Canary spec | load `/queue` as a seeded officer, assert a known seeded ticket is visible, capture a screenshot |
| Docs | `docs/engineering/04_testing.md` gains an e2e section: what belongs here vs unit vs integration |

**Determinism is the whole game.** The seed must run with `--reset` before a suite, assertions key off
seeded ids (`GRV-2025-*`), and nothing may depend on wall-clock date or on rows left by a previous run.
A flaky e2e suite is worse than none — it trains everyone to ignore a red build.

## QA-04b — officer-UI route smoke (fan-out, ~1 d)

All **22** `page.tsx` routes, loaded as an appropriately-roled seeded officer: assert no 5xx, no
uncaught console error, no Next error boundary, and capture a screenshot per route. Routes requiring
admin get an admin cookie; the rest an officer cookie.

**Five routes are parameterised, and three of the five have no seeded value to use.** This is the part
of 04b that is not an hour's work, so budget it before starting:

| Route | Where the parameter comes from |
|---|---|
| `/tickets/[id]`, `/m/tickets/[id]` | ✅ seeded — `mock_tickets` ids, via `e2e/fixtures/seed.ts` |
| `/closure/[token]` | ⚠ **not seeded.** The token is `ticket_resolved_summaries.closure_public_token`, and `mock_tickets.py` creates no such row. It exists only after a ticket is resolved *and* a closure summary is generated — which runs the LLM builder (`ticketing/services/resolved_summary_builder.py`, `ticketing/tasks/llm.py`) |
| `/reports/view/[token]`, `/reports/public/[token]` | ⚠ **not seeded.** Tokens come from `ticketing/services/report_shares.py`; nothing in the seed calls it |

⭐ **The fix is a fixture, not a hardcoded token, and not an LLM call in a smoke test.** Have
`e2e/fixtures/seed.ts` create what it needs through the API — a report share is a plain call; a closure
row should be inserted directly (or its summary stubbed) rather than driving a paid model on every
smoke run. **If you cannot make a route deterministic and free, skip it with a named reason in the
spec file** and record the gap in `PROGRESS.md`'s "Routes covered / 22" row. A smoke suite that
quietly excludes three routes while reporting 22 is the failure this sprint exists to stop.

⚠ **Three of the 22 are auth routes whose bypass-build behaviour is not "the page renders".**
`/login` takes an `AUTH_BYPASS` branch (`app/login/page.tsx:123`); `/auth/callback` finds no OAuth
params and redirects to `/login?error=…`; `/login/reset-password` is a Keycloak flow. **Assert the
redirect, not the render** — otherwise the specs encode a bug report as a requirement, the same trap
QA-04d is warned about below.

## QA-04c — the driven flows (fan-out)

⚠ **Scope changed 2026-09-04.** This ticket said *"the five, decided"*. The owner's answer to
[Q-09](QUESTIONS.md#q-09--how-much-of-the-officer-ui-does-v1-cover) is **"lets do all the flows"** — so
the five are a **floor, not the scope**. That is a real expansion and it is priced below; the five stay
listed because they are the ones that must work first, not because the rest are optional.

**Tier 1 — the original five. Land these first; they are the harness's proof.**
queue → open ticket → internal note · escalate · resolve + closure summary · settings → create/edit an
officer · reports → generate an XLSX.

**Tier 2 — the rest of "all the flows", enumerated so "all" means something.** Derived from the
actions and settings sections that actually exist in the app; **verify against the tree before
starting** and add anything this list missed, since it will have moved:

| Group | Flows |
|---|---|
| Ticket actions | `ACKNOWLEDGE` · `ASSIGN` / reassign · `GRC_CONVENE` · `WITHDRAW` — the action panel's full set alongside escalate/resolve |
| Queue & search | tab switching (Actor / Supervisor / High Priority / All Tickets), tile filters, search and filter combinations |
| Settings | officers (`officers-v2`), roles, workflows, projects & packages, org, platform, project types, quarterly-report schedule, go-live panel |
| Reports | generate · share link (`report_shares`) · public view |
| Mobile | `/m/*` stays **smoke only** — [Q-10](QUESTIONS.md#q-10--is-the-mobile-surface-in-v1) is unchanged |

**Estimate: 1–1.5 d for tier 1, plus ~2–3 d for tier 2** — driven flows cost roughly a day per small
group, which is the number Q-09 was answered against. ⚠ **Say so in `PROGRESS.md` before starting**: if
that pushes the sprint past what is wanted, tier 2 is the part to split into its own ticket, and it
splits cleanly because each group is a separate spec file.

⭐ **Two things do not change with the expansion.** Determinism still governs — a flaky suite is worse
than none, and thirty flows give it thirty chances. And the **order** still matters: tier 1 lands and
gets reviewed before tier 2 is written, for exactly the reason 04a delivers one canary rather than
thirty specs against an unreviewed harness.

## QA-04d — the webchat sweep (fan-out, ~1–1.5 d) — ✅ **in scope**

⚠ **A different surface** — `channels/REST_webchat/`, plain JS + socket.io served through nginx, not the
Next app. HR-07's code is merged and in the tree; its **7-item manual sweep was never run** and its
checkbox is still open in `2026-07_hardening/PROGRESS.md`. Automate those items: EN/NE switch, image
upload, voice note, map pin, status check, **send-lock under a dead backend (the 15 s failsafe release)**,
filed-banner rendering, SEAH route entry, session-id persistence and `/clear_session` rotation.

⚠ Read HR-07's deviation rows first: a refresh **does not** resume an in-progress intake — the
orchestrator hard-resets on `/introduce` **by design**. Assert id stability and rotation, *not*
resumption, or you will write a test that encodes a bug report as a requirement.

**Two items in that list are not like the others, and they set the shape of the sub-ticket:**

- ⚠ **Voice note goes through ASR — a live, paid model call.** `backend-tests` deliberately excludes
  `@live_llm` because *"it costs money"*, and `dpg-platform-independence` is the one job that spends,
  gated on a token and explicitly **not** a required check. A webchat suite that transcribes audio on
  every PR contradicts both. **Stub the ASR response** (fixture audio → a canned transcript at the
  service boundary) and assert the **UI** contract — recorder state, chunk upload order, the message
  landing in the thread. If you cannot stub it, mark the item deferred with a reason rather than
  making the whole suite cost money per run. The same question applies to any EN/NE item that hits
  `MODEL_TRANSLATE`.
- ⚠ **"Send-lock under a dead backend" requires stopping the `backend` container mid-run.** That is a
  destructive, stack-wide action: any 04b/04c spec running concurrently against the same stack will
  fail for an unrelated reason, and the failure will look like flake. **The README's parallelism claim
  is about disjoint *files*, which is not the same as disjoint *runtime*.** Put this item in its own
  Playwright project with `fullyParallel: false` and a serial worker, or — better — simulate the dead
  backend at the network layer (`page.route()` to abort the orchestrator call) and never touch the
  container. Prefer the second: it is deterministic, it needs no privileges in CI, and it tests the
  15 s failsafe release rather than Docker.

**Its stack is bigger than 04b/04c's.** The webchat is served by nginx from **bind-mounted working-tree
files**, and its messages traverse `orchestrator` → `backend` → celery. See QA-03 scope 4 for the
service set; do not assume `ephemeral-up` gives you the chatbot half unless it was asked for.

## Not in scope

**Pixel-diff baselines** — v1 captures, it does not gate. Baselines are a *later decision*, not a
deferred obligation; do not leave a TODO implying they are owed. **Any Keycloak login flow** beyond the
single smoke test, which lands later in its own job. Load or performance testing. Editing CI — that is QA-05, and **Stream B must not touch `ci.yml`**.

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
- **The bypass build is a build variant**, not a runtime flag (QA-02 publishes it as `ui:<sha>-bypass`).
  Running the suite against a Keycloak-built image will fail confusingly — assert the mode in global
  setup and fail with *"this suite needs an AUTH_MODE=bypass build"*.
- **Seed drift.** If `mock_tickets.py` changes, specs keyed to its ids break. Keep the coupling explicit
  and small: a single `e2e/fixtures/seed.ts` naming every seeded id the suite relies on.
