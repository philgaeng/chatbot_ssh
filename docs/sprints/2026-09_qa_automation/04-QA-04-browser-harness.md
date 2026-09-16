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
| `channels/ticketing-ui/e2e/fixtures/officer.ts` | **new** — `asOfficer(officer)` cookie fixture. ⚠ **Signature changed from the sketched `asOfficer(roleKeys, userId?)`** — measured 2026-09-06, the server *discards* caller-supplied role keys (`enrich_user` substitutes DB-effective roles), so a role-keys-first signature lets a spec appear to grant itself a capability, change nothing, and pass for the wrong reason | 04a |
| `channels/ticketing-ui/e2e/fixtures/seed.ts` | **new** — the single place naming every seeded id the suite relies on | 04a |
| `channels/ticketing-ui/e2e/queue.spec.ts` | **new** — the canary | 04a |
| `channels/ticketing-ui/package.json` | **`@playwright/test`** as a pinned devDependency + an `e2e` script | 04a |
| `channels/ticketing-ui/.dockerignore` | add `e2e/`, `playwright.config.ts`, `test-results/`, `playwright-report/` — **and `.env*`**, added in passing as prevention (the image was verified clean first; the mechanism it closes is Next reading `.env.local` during the builder's `COPY . .`). ⚠ Not the same as [Q-18](QUESTIONS.md#q-18--does-the-image-contain-envlocal), which is the **root** context and QA-02's | 04a |
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

1. **Depend on `@playwright/test`, not `playwright`.** ~~The bare `playwright` package downloads browser
   binaries in a postinstall — several hundred MB, inside the Docker build.~~
   ⚠ **CORRECTED 2026-09-06 by QA-04a — the reason was false, the recommendation still holds.** All
   three tarballs were unpacked at the pinned version: **`playwright`, `playwright-core` and
   `@playwright/test` declare no install script at all.** Browsers arrive only from an explicit
   `npx playwright install`. Confirmed by running the builder stage's `npm ci` in `node:20-alpine`: no
   `ms-playwright` cache directory, and **+18.4 MB on a 726 MB `node_modules` (+2.5 %)**. Depend on
   `@playwright/test` because it *is* the test runner — not because the other one downloads anything.
2. ~~**Set `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` in the builder stage**~~ ⚠ **DEFERRED TO QA-01 by
   QA-04a, deliberately.** It guards a hazard measured not to exist at `1.63.0`, and the version is
   pinned **exactly** (no `^`), so it cannot change without a visible edit. QA-04a therefore did **not**
   touch the Dockerfile at all. **QA-01: add `ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` when you
   restructure that stage**, and write the honest reason — *future-proofing against an unpin* — rather
   than the postinstall story above, which would become a false comment in a live file.
3. **Add `e2e/` to `channels/ticketing-ui/.dockerignore`** — today it lists only `node_modules`, `.next`,
   `.git`, `*.log`, `.DS_Store`, `Thumbs.db`, so specs would otherwise be copied into the image.
   ✅ Done, plus `.env*` — see the `Files` table row.

~~Coordinate 1 and 2 with Stream A rather than editing the Dockerfile unilaterally — it is QA-01's file.~~
✅ **Resolved without a Dockerfile edit** (see 1 and 2). The file stays entirely QA-01's.

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
| Identity fixture | `asOfficer(officer)` — sets the `grm_bypass_user` cookie; officers come from the seeded roster, never literals invented in the test. ⚠ Not `(roleKeys, userId?)` — see the `Files` row |
| Projects | desktop chromium + **one mobile device** (mobile is in v1, smoke only) |
| Artifacts | screenshot + trace **on failure**; screenshot on demand for every route in the smoke pass. **No pixel-diff gate in v1** — captures only |
| Canary spec | load `/queue` as a seeded officer, assert a known seeded ticket is visible, capture a screenshot |
| Docs | `docs/engineering/04_testing.md` gains an e2e section: what belongs here vs unit vs integration |

**Determinism is the whole game.** The seed must run with `--reset` before a suite, assertions key off
seeded ids (`GRV-2025-*`), and nothing may depend on wall-clock date or on rows left by a previous run.
A flaky e2e suite is worse than none — it trains everyone to ignore a red build.

> ⚠ **`--reset` is for a disposable stack only, and one more thing is not deterministic.** On the
> owner's dev database `mock_tickets --reset` is forbidden ([`KICKOFF.md`](KICKOFF.md) §5) — it takes
> projects, organizations and officers with it. So a local run works against whatever the seed left,
> and the suite must tolerate that. It does: assertions key off `grievance_id` and assignee.
> **What is *not* stable even after a fresh `--reset` is ticket status** — the SLA watchdog rewrites it
> as the stack ages (measured: `GRV-2025-001` seeded `IN_PROGRESS`, found `ESCALATED`). `ticket_id` is
> a fresh `uuid4()` per seed run and must be resolved at runtime. Both rules live in
> `e2e/fixtures/seed.ts`; the demo-side consequence is `GRM-070`.

## QA-04b — officer-UI route smoke (fan-out, ~1 d) — ✅ **done 2026-09-06, 22 / 22**

> **28 specs, ~15 s, green twice in a row.** 17 desktop routes in `e2e/smoke/`, 5 mobile in
> `e2e/mobile/`. Every route asserts *content*, not just HTTP 200 — a Next route returns 200 while
> its client component throws, so a status-only smoke suite reports green on a blank page.
> ⚠ **One partial, named:** `/closure/[token]`'s happy path runs against a stubbed API response;
> its invalid-token state runs against the real one. Reason and cost in
> [`PROGRESS.md`](PROGRESS.md) under *"Parameterised routes skipped, and why"*.
> ⭐ **It found two defects and fixed one.** `POST /api/v1/reports/share` was HTTP 500 on any
> database where nobody had shared a report before (`GRM-071` — fixed, 5 tests, 2 mutation records);
> `/qr-codes` sends every package's intake token to `api.qrserver.com` (`GRM-072` — filed, stubbed
> in the spec, not fixed in passing). **Needing the feature to work in order to test it is what
> found the 500** that two sprints of manual sweeps had not.

All **22** `page.tsx` routes, loaded as an appropriately-roled seeded officer: assert no 5xx, no
uncaught console error, no Next error boundary, and capture a screenshot per route. Routes requiring
admin get an admin cookie; the rest an officer cookie.

> ⚠ **"No uncaught console error" needed a definition before it could be code.** The browser logs
> every non-2xx subresource as a console error, and three routes produce one **on their correct
> path**. The gate is: an uncaught exception, a `console.error` from application code, or the error
> boundary — with handled resource failures *recorded* as an artifact rather than failed on. See
> `e2e/fixtures/smoke.ts` and [`04_testing.md`](../../engineering/04_testing.md) §6a rule 6a.9.

**Five routes are parameterised, and three of the five have no seeded value to use.** This is the part
of 04b that is not an hour's work, so budget it before starting:

| Route | Where the parameter comes from | ✅ How it was covered |
|---|---|---|
| `/tickets/[id]`, `/m/tickets/[id]` | ✅ seeded — `mock_tickets` ids, via `e2e/fixtures/seed.ts` | `resolveTicketId()` at run time — `ticket_id` is a fresh `uuid4()` per seed, so it is never hardcoded |
| `/closure/[token]` | ⚠ **not seeded.** The token is `ticket_resolved_summaries.closure_public_token`, and `mock_tickets.py` creates no such row. It exists only after a ticket is resolved *and* a closure summary is generated — which runs the LLM builder (`ticketing/services/resolved_summary_builder.py`, `ticketing/tasks/llm.py`) | ⚠ **Partial.** Invalid token → real API, real 404, real "link is invalid" state. Happy path → `page.route()` stub. **Direct insert was not available**: `tasks/llm.py` **retries rather than degrades** without a model (`if not llm_out: raise self.retry(...)`), so no free path writes the row, and giving a Playwright process a database driver for one page is a worse coupling |
| `/reports/view/[token]`, `/reports/public/[token]` | ⚠ **not seeded.** Tokens come from `ticketing/services/report_shares.py`; nothing in the seed calls it | ✅ **Real tokens**, via `createReportShare()`. ⭐ This is what found `GRM-071`: the endpoint returned **500** on any database where nobody had shared before |

⭐ **The fix is a fixture, not a hardcoded token, and not an LLM call in a smoke test.** Have
`e2e/fixtures/seed.ts` create what it needs through the API — a report share is a plain call; a closure
row should be inserted directly (or its summary stubbed) rather than driving a paid model on every
smoke run. **If you cannot make a route deterministic and free, skip it with a named reason in the
spec file** and record the gap in `PROGRESS.md`'s "Routes covered / 22" row. A smoke suite that
quietly excludes three routes while reporting 22 is the failure this sprint exists to stop.

⚠ **Three of the 22 are auth routes whose bypass-build behaviour is not "the page renders".**
`/login` takes an `AUTH_BYPASS` branch (`app/login/page.tsx:123`); ~~`/auth/callback` finds no OAuth
params and redirects to `/login?error=…`~~; `/login/reset-password` is a Keycloak flow. **Assert the
redirect, not the render** — otherwise the specs encode a bug report as a requirement, the same trap
QA-04d is warned about below.

> ⚠ **CORRECTED 2026-09-06 — that describes the Keycloak build.** On the **bypass** build this suite
> runs against, `AuthProvider` starts `isAuthenticated` `true` unconditionally, so `/auth/callback`'s
> first effect wins and it lands on **`/queue`**; `/login` does the same, from `app/login/page.tsx:45`.
> Measured. `e2e/smoke/redirects.spec.ts` asserts the bypass behaviour and names the Keycloak branch
> so nobody "fixes" it later — that branch belongs to the login smoke test deferred to its own job
> (Q-07). ⭐ **Same root cause as the readiness race QA-04a shipped and fixed:** the transient render
> before the redirect is what both mistakes trusted.

## QA-04c — the driven flows (fan-out)

⚠ **Scope changed 2026-09-04.** This ticket said *"the five, decided"*. The owner's answer to
[Q-09](QUESTIONS.md#q-09--how-much-of-the-officer-ui-does-v1-cover) is **"lets do all the flows"** — so
the five are a **floor, not the scope**. That is a real expansion and it is priced below; the five stay
listed because they are the ones that must work first, not because the rest are optional.

**Tier 1 — the original five. Land these first; they are the harness's proof.** ✅ **DONE 2026-09-06.**
queue → open ticket → internal note · escalate · resolve + closure summary · settings → create/edit an
officer · reports → generate an XLSX.

> **9 specs in `e2e/flows/`, green twice in a row.** Every state-changing flow acts on a ticket it
> created (`e2e/fixtures/ticket.ts`), never on a seeded one — escalating a seeded ticket is
> irreversible and would rewrite a demo scenario.
>
> ⭐ **Three findings, and all three came from *driving* rather than reading.**
> `GRM-073` — escalate and resolve **hard-block** without a photo, on both sides, while `CLAUDE.md`
> says *"warning encouraged but not blocked"*; no live spec records the real rule.
> `GRM-074` — on a **freshly seeded** database the officer-invite flow dead-ends: every seeded
> position type is restricted to a unit type no seeded organisation has.
> `GRM-075` — officer *provisioning* is deliberately not driven (it would create a real Keycloak
> account and send mail per run); [followed up](followups/officer-provisioning-not-driven-by-e2e.md).
>
> ⚠ **Two adjustments the ticket did not anticipate.** The officer flow is *"create/edit"*, and
> neither half is driven to completion — provisioning has the side effect above, and editing a
> seeded officer is a seed mutation. What **is** driven is the directory, its search, the invite
> cascade and the admin gate. And the XLSX export had to be **filtered** before it would run at all:
> `report_limits.max_export_rows` is 100 and a busy stack returns HTTP 400.

**Tier 2 — the rest of "all the flows", enumerated so "all" means something.** Derived from the
actions and settings sections that actually exist in the app; **verify against the tree before
starting** and add anything this list missed, since it will have moved:

> ✅ **DONE 2026-09-07 — and the list below was wrong in three places, which is what
> *"verify against the tree before starting"* was for.** Measured against
> `ticketing/engine/ticket_actions.py`'s `ACTION_HANDLERS`:
> **`ASSIGN` does not exist** (the nearest is `REASSIGNMENT_REQUESTED`, a *request*, TP-12);
> **`WITHDRAW` is not an officer action** — `WITHDRAW_REQUEST` is a complainant inbound *event
> intent*, raised from the chatbot side, not from the action panel; and the list **misses
> `FIELD_REPORT`**, which is a real handler with its own compose card. The real set is
> `ACKNOWLEDGE · ESCALATE · RESOLVE · NOTE · FIELD_REPORT · REASSIGNMENT_REQUESTED · GRC_CONVENE`.
>
> **Delivered: 17 further specs, 64 in total, green twice in a row.**
> *Queue & search* — tabs, tile filter and its chip, search, `/escalated`.
> *Settings* — all nine sections open and render (the group's own list named component
> directories, not what the UI shows; the four top tabs and their sub-tabs are enumerated in the
> spec).
> *Ticket actions* — a case walked **L1 → L2 → L3 and convened at the GRC**, covering
> ACKNOWLEDGE at each level, ESCALATE twice, GRC_CONVENE, and the auto-reassignment between
> levels that had no coverage at all.
> *Reports* — both share views, and the public projection asserted to differ from the internal one.
>
> ⭐ **It found `GRM-084`: the GRC chair cannot convene a GRC hearing.** The control is gated on
> a legacy `grc_chair` role key that the cast model no longer issues, so demo scenario 1's
> headline step works only for the super admin. The escalation chain is correct; the gate is not.
>
> ⬜ **Not driven, deliberately:** `FIELD_REPORT` and `REASSIGNMENT_REQUESTED` (each opens its own
> compose card and deserves its own spec rather than a rushed one at the end of a group), and
> every settings *edit* — several are one-way on a system with no delete path, so driving them
> needs the disposable-stack story, which `make ephemeral-up` now provides.

| Group | Flows |
|---|---|
| Ticket actions | ~~`ACKNOWLEDGE` · `ASSIGN` / reassign · `GRC_CONVENE` · `WITHDRAW`~~ — see the correction above |
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

## QA-04d — the webchat sweep (fan-out, ~1–1.5 d) — ✅ **DONE 2026-09-06: 6 of 10 items + 1 partial**

> **9 specs in `e2e/webchat/`, green twice in a row**, through nginx on `:8080` as
> [Q-12](QUESTIONS.md#q-12--does-the-e2e-stack-go-through-nginx-or-straight-to-the-ui-container) requires.
> ✅ **Both items HR-07's tracker calls *"must be human-verified (behavioral)"* are now driven:**
> a double Enter sends exactly one `POST /message`, and a backend that never answers releases the
> composer via the 15 s failsafe — **simulated with `page.route()`, no container stopped**, so
> nothing else in the suite fails for an unrelated reason.
> Also covered: EN/NE (asserted on the *menu*, not the bilingual greeting), SEAH route entry
> **including the swap of "Close session" for "Close browser tab"**, status check, session-id
> persistence + rotation (**not** resumption — HR-07's own caveat), SRI load-cleanliness in a real
> browser, and a **partial** image-upload item (picker, preview, and the hold-until-a-case notice).
>
> ⚠ **Four items are deferred, not done** — the upload itself, the voice note, the map pin and the
> filed banner. All four need an intake driven to a filed case, which runs the classifier: a paid
> call per run, plus a real grievance filed per run on a system with no erasure path. Tracked as
> `GRM-077` with three ways to unblock: [`followups/webchat-items-needing-a-filed-case.md`](followups/webchat-items-needing-a-filed-case.md).
>
> ⭐ **And it found something bigger than its own scope.** Blocking egress in a browser showed the
> webchat **cannot function without three foreign CDNs** — socket.io, leaflet and exifr — while
> still rendering a page that looks fine. On a firewalled production host that is a silently
> degraded complainant channel (`GRM-076`). ⚠ **HR-07 pinned those scripts with SRI, which answers
> tampering and not availability.**
>
> ⚠ **HR-07's checkbox is deliberately NOT ticked here.** [QA-05](05-QA-05-ci-gate-and-coverage.md)
> owns it, *"with the run link as evidence — do not tick it because the tests exist; tick it because
> they ran and passed"*. They pass locally; no CI job runs them yet.

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

## Acceptance (04a) — ✅ **all met 2026-09-06**, each against a run, not a reading

- [x] `npx playwright test` green against a locally seeded stack, twice in a row, with no shared state between runs — 2 passed in 5.3 s, then 3.4 s; and again in 3.6 s against a **freshly rebuilt** `grm_ui` image
- [x] The canary fails informatively when the stack is down (clear readiness error, not a 30 s hang) — pointed at a dead port: fails in **6 s** with the probe, the last error, and the fix command. The auth-mode branch was exercised separately by pointing `E2E_BASE_URL` at a non-bypass target: *"this suite needs an AUTH_MODE=bypass build … the grm_bypass_user cookie for grc-chair@grm.local resolved to admin@grm.local instead"*
- [x] `asOfficer()` demonstrably changes what the UI shows (two roles, two different queues) — the GRC chair's Actor tab holds `GRV-2025-001`; the site officer's holds `GRV-2025-005` and **not** `GRV-2025-001`
- [x] Screenshots land as artifacts; a trace is produced on a deliberately failed assertion — `queue-grc-chair.png` (1280×720) on the green run; `trace.zip` + `test-failed-1.png` + `error-context.md` after breaking an assertion on purpose and reverting it
- [x] Playwright added as a **devDependency** with a pinned version (`"@playwright/test": "1.63.0"` — exact, no `^`); browsers via `npx playwright install --with-deps chromium`, documented in `04_testing.md` §6a and in `playwright.config.ts`'s header
- [x] `docs/engineering/04_testing.md` updated (§6a, eight rules); `PROGRESS.md` deviations logged (seven rows)

⭐ **Two gates came free and are worth knowing before writing 04b/c/d:** `tsconfig.json` includes
`**/*.ts` and `ui-checks` runs `npx eslint .` over the whole directory, so **CI already type-checks and
lints every spec** — a spec that does not compile fails the build today, before QA-05 exists. And
`vitest`'s `include` (`**/*.test.ts`) was **verified** not to collect `*.spec.ts`: `npm test` still
reports 12 files / 104 tests.

## Risks

- **Flakiness is the failure mode**, not defects. Use web-first assertions and role/label selectors —
  never `waitForTimeout`, never CSS-class selectors that a Tailwind refactor will silently break.
- **The bypass build is a build variant**, not a runtime flag (QA-02 publishes it as `ui:<sha>-bypass`).
  Running the suite against a Keycloak-built image will fail confusingly — assert the mode in global
  setup and fail with *"this suite needs an AUTH_MODE=bypass build"*.
- **Seed drift.** If `mock_tickets.py` changes, specs keyed to its ids break. Keep the coupling explicit
  and small: a single `e2e/fixtures/seed.ts` naming every seeded id the suite relies on.
