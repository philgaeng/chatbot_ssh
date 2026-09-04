# Testing standard

**Status:** authoritative (2026-08-03). What we test, at which level, and what CI enforces.
**Applies to:** `tests/` (Python, pytest) and `channels/ticketing-ui/**/*.test.ts` (Vitest).
**Reads with:** [`pytest.ini`](../../pytest.ini) — the marker contract, with its history — and `.github/workflows/ci.yml`.

---

## 1. What tests are for here

This system takes grievances from people in rural Nepal, some of them SEAH cases, and routes them to named officials under an SLA. The failure modes that matter are **not** "the button is the wrong colour":

- a ticket becomes invisible to the officer who must act on it,
- an officer sees a case they must not see,
- complainant PII crosses a boundary,
- an SLA clock is computed in the wrong timezone and a breach is never reported.

**So we test the boundaries and the state machine hardest, and we do not chase a coverage number.** Coverage is a diagnostic ("which branch has nobody ever run?"), never a target — a target produces tests that assert the code does what the code does.

---

## 2. The shape of the suite

| Level | Where | Needs | Use it for |
|---|---|---|---|
| **Unit** | `tests/ticketing/test_admin_access.py`, `lib/*.test.ts` | nothing | pure logic: permission matrices, formatters, tile computation, date maths |
| **Service / integration** | most of `tests/ticketing/` | seeded Postgres | use cases through the service layer: assignment, escalation, jurisdiction, archiving |
| **API** | `tests/ticketing/test_authz_matrix_extended.py`, route tests | seeded Postgres | the contract: status codes, authz, response shape |
| **Pinning / policy** | `test_boundary_policy.py`, `test_pii_boundary.py`, `route_snapshot.txt` | varies | architectural rules that must not erode |
| **Frontend unit** | `channels/ticketing-ui/lib/*.test.ts` | nothing | hooks, pure helpers, command parsing |
| **Manual browser sweep** | [`17_manual_browser_sweep.md`](../deployment/17_manual_browser_sweep.md) | a human | what we have deliberately **not** automated yet |

**Rule 2.1 — Test through the service layer, not the router, by default.** The service function is where the logic lives ([02 §1](02_python_services.md#1-the-architecture-named)); testing it needs no `TestClient` and stays valid when the route changes.

**Rule 2.2 — Test through the API when the *contract* is the thing under test** — status codes, authz, serialization, PII exposure. Then assert on the wire shape, not on internals.

**Rule 2.3 — There is no mocking of our own database.** See §3.

---

## 3. Integration tests are not optional

**Rule 3.1 — `@pytest.mark.integration` declares a dependency, not a quarantine.** CI seeds the database *precisely so these run*. **Never** add `-m "not integration"` to make a build green.

*Why, measured:* between 2026-07 and T3-08 they were deselected. `test_officer_assignment.py` rotted unnoticed (D-44) while CI paid the full seeding cost and gated nothing with it. Removing the quarantine took CI from 364 to 897 tests for +16 seconds. The full note is in [`pytest.ini`](../../pytest.ini) — read it before touching a marker.

**Rule 3.2 — A failing integration test means the seed and the test have drifted. That drift is the bug.** Fix one or the other; do not deselect.

**Rule 3.3 — Assert on the *pool*, never on one identity.** Officer assignment ranks by active ticket load, so a DB with accumulated tickets legitimately picks a different officer than a fresh seed. Assert "the assignee is one of the L1 officers for Jhapa", never "the assignee is `officer_3`".

**Rule 3.4 — Tests clean up what they create.** Use the fixtures in `tests/ticketing/conftest.py`; create with the `_uid()` prefix so leaked rows are identifiable and never collide with seed data.

**Rule 3.5 — Never mutate seed rows.** Create your own. A test that edits `KL_ROAD_STANDARD` breaks every test that runs after it, in an order-dependent way that is miserable to debug.

---

## 4. Writing a good test

**Rule 4.1 — The name states the behaviour and the expectation.** `test_escalation_skips_tickets_already_at_final_level`, not `test_escalation_2`.

**Rule 4.2 — Arrange / Act / Assert, visibly separated.** One behaviour per test. Multiple asserts are fine when they describe one behaviour.

**Rule 4.3 — Assert on behaviour, not implementation.** "The ticket is now at L2 and an escalation event exists", not "`_advance_step` was called once". Implementation asserts break on every refactor and catch nothing.

**Rule 4.4 — A bug fix ships with the test that fails without it.** Write the failing test *first* — otherwise you cannot know it tests the fix. Reference the deviation id in the test docstring where one exists (`D-44`, `HR-01`).

**Rule 4.5 — Test the boundary, not the middle.** Empty list, one item, the maximum, one past the maximum, null, wrong timezone, the transition that must be refused.

**Rule 4.6 — Mock only what you don't own.** Keycloak, SNS, SMTP, the LLM: mock at the `clients/` boundary. Our own database, our own services: never.
*Why:* mocked internals let two real components drift while every test stays green.

**Rule 4.7 — No sleeps, no wall-clock dependence.** Inject the clock or freeze it. A test that depends on "now" fails at 23:59 UTC and passes in the morning, which nobody ever debugs.

**Rule 4.8 — No inter-test ordering.** Each test passes alone and in any order.

---

## 5. Pinning tests — the rules that guard the rules

Some rules are too important to leave to review. These are pinned by a test that fails when code and documentation disagree:

| Guards | Test |
|---|---|
| Closed set of `public.*` tables ticketing may touch, and which it writes — parsed from the CLAUDE.md table | `tests/ticketing/test_boundary_policy.py` |
| No complainant PII in `ticketing.*`; no decryption accessor exists | `tests/ticketing/test_pii_boundary.py` |
| Auth fails closed when a secret is missing | `tests/ticketing/test_fail_closed_auth.py` |
| Every route's permission set | `tests/ticketing/test_authz_matrix_extended.py` |
| The route inventory itself | `tests/ticketing/route_snapshot.txt` |

**Rule 5.1 — When a pinning test fails, the default assumption is that *you* broke the rule**, not that the test is stale. Updating the snapshot is a deliberate act that belongs in its own commit with its own reason.

**Rule 5.2 — A new architectural rule ships with its pin, or it isn't a rule.** An unenforced rule survives about two sprints. If you cannot pin it, say so where you write it.

### 5a. Mutation checks — the answer to *"can this test go red?"*

**Rule 5.3 — A test that cannot go red is not a test, and the proof is a mutation check.** Make the specific edit to production code the test claims to catch, run the suite, watch it fail, revert. This is not ceremony: in one working session it caught a **decorative test three separate times** — a test that exercised the *helper* and never the call sites (the call site was the whole finding); one that scanned *any* dict with the right key, so the neighbouring branch satisfied it on the wrong branch's behalf; and one driving *the wrong method entirely*, so the fix sat on a code path the defect does not use. No review found any of the three.

**Rule 5.4 — Record the mutation as data, not as prose.** A sentence in a commit message cannot be re-run, so nobody can reproduce it and a test that *stops* catching its mutation goes unnoticed while the ledger still reads ✅. Records live in `tests/mutations/<test module>.yml`, one file per test module, and the runner is `scripts/ops/run_mutations.py`:

```yaml
- id: T-31-e-global-counter
  target: backend/services/pii_service.py
  find: "    counters: dict[str, int] = {}"     # must occur EXACTLY ONCE
  replace: '    counters: dict[str, int] = globals().setdefault("_MUTANT_COUNTERS", {})'
  tests: tests/backend/test_pii_service.py
  expect: kills                                 # or `survives` — see 5.5
  min_failures: 3                               # optional; asserts the ledger's "3 red"
  runner: container                             # optional; + `container:` for OpenAI-importing suites
  why: >
    Two concurrent grievances must not share <PERSON_1> — a shared counter makes the mapping
    ambiguous and turns placeholders into a cross-document correlation channel.
```

```bash
python scripts/ops/run_mutations.py                       # every record
python scripts/ops/run_mutations.py --module test_pii_service
python scripts/ops/run_mutations.py --list                # no edits, no test runs
```

**Rule 5.5 — ⭐ `expect: survives` is a first-class outcome, and a `why` is mandatory on it.** Some mutations *should* survive. `T-31-a-dual-script-digit-class` is the worked example: removing the Devanagari half of the digit class changes no behaviour, because `find_pii` normalises centrally *before* any recogniser runs — the dual-script class is redundant defence-in-depth, and removing the **normalisation** is what kills. A runner that demanded every mutation kill would force someone to delete a useful safety net or fake the record, so the runner asserts the **recorded expectation** and rejects a `survives` with no explanation of what *does* kill.

**Rule 5.6 — A record that stops reproducing is a finding; write it up rather than adjusting it.** It means one of two things and both matter: the test stopped catching its mutation, or the original claim was wrong.

**Rule 5.7 — Targeted mutations only; do not reach for `mutmut` or `cosmic-ray`.** Generic tools emit thousands of mutants — flip `+` to `-` — and the value here is in the hand-authored ones that encode a specific real defect: *"the OTP is logged again"*, *"the district is redacted"*, *"expiry is checked after the match"*. No generic tool produces those, because they are statements about **this system's failure modes**, written by whoever just fixed one. 3,000 mutants would bury the 30 that mean something.

**Rule 5.8 — It is deliberately NOT a CI gate.** Every mutation is a full suite run, and a slow gate is the gate nobody watches (D-26, learned over ten red days). The current set is ~20 s for 30 records, but a third of them need a live Compose stack, which CI does not have. Run it before a release, or when touching a pinned invariant.

⚠ **Two traps the runner enforces so you do not have to remember them.** It restores with `git checkout --` in a `finally` rather than a copy in `/tmp`, and therefore **refuses to run when a file a record mutates has uncommitted work** — the restore would destroy it. And `find` must occur **exactly once**: an anchor that also matches a comment, a docstring, or a second call site mutates two places and tests something nobody wrote down. Prefer anchors that include indentation and surrounding syntax.

---

## 6. Frontend tests

**Rule 6.1 — Vitest, colocated** (`lib/queueTiles.test.ts` next to `lib/queueTiles.ts`).

**Rule 6.2 — Pure logic is extracted from components and unit-tested.** Tile counting, SLA urgency, thread command parsing, error formatting are all pure functions today — keep them that way. → `lib/queueTiles.ts`, `lib/threadCommands.ts`, `lib/user-messages.ts`

**Rule 6.3 — Don't snapshot-test rendered markup.** Snapshots of JSX churn on every design change and assert nothing about behaviour.

**Rule 6.4 — Type-check and lint are tests.** CI runs `npx tsc --noEmit` and `npx eslint . --max-warnings=-1`. A `// @ts-expect-error` or a downgraded lint rule is a **deferral** and must be logged (§8).

---

## 7. Running them

| Command | Runs |
|---|---|
| `make test-ticketing` | ticketing suite **in the container** — closest to CI |
| `make test-ticketing-host` | same on the host (needs `make dev-grm-deps`, DB on `:5433`, migrations + seed) |
| `make test-ticketing-unit` | the no-DB subset |
| `npm test` (in `channels/ticketing-ui`) | Vitest |
| `npx tsc --noEmit && npx eslint .` | the frontend gates |
| `python scripts/ops/run_mutations.py` | the mutation records (§5a) — **not** in CI, run deliberately |

DB credentials for host tests come from compose, never `env.local` — `tests/ticketing/_host_env.py` (D-36).

**What CI runs** (`.github/workflows/ci.yml`): all three migration streams from empty → public-schema consistency gate → seed locations + demo workflows → `pytest tests/ticketing tests/orchestrator tests/actions tests/backend -q --maxfail=20 --strict-markers` → frontend type-check, lint, unit tests, build → markdown link check under `docs/`.

**Rule 7.1 — `--strict-markers` is on.** An unregistered marker is an error, so a typo'd `@pytest.mark.integraton` can't silently skip.

---

## 8. When you cannot test it now

**Rule 8.1 — Skipping, quarantining, `xfail`, downgrading a lint rule, `# noqa`, or `@ts-expect-error` is a deferral**, and a deferral that is not logged is a defect. In the **same commit**: a follow-up doc at `docs/sprints/<sprint>/followups/<slug>.md` (measured inventory + definition of done) **and** a one-line row in [`TODO.md`](../TODO.md) under 🔵 TECH DEBT.
*Why:* an unlogged deferral is indistinguishable from a bug nobody noticed — the marker is in the code, where only the next reader of that line will find it, and the debt never reaches a list anyone plans from.

**Rule 8.2 — Untested-by-decision is fine; untested-by-silence is not.** The manual browser sweep is a legitimate, written decision. An untested path nobody mentioned is how the SEAH intake shipped an HTTP 500.

**Rule 8.3 — Say what you skipped, in the PR and in `PROGRESS.md`.** "Tests pass" when a suite was deselected is a false report.

---

## 9. Definition of done — testing

- [ ] New logic has a test at the level where the logic lives (service, not router, by default)
- [ ] A bug fix has a test that fails without the fix
- [ ] New route: authz matrix row + route snapshot updated
- [ ] New architectural rule: pinning test, or an explicit note that there is none
- [ ] Every new test mutation-checked, and the mutation recorded in `tests/mutations/` (§5a) — not only in the commit message
- [ ] CI green with **nothing** deselected, downgraded, or suppressed
- [ ] Any deferral logged in `followups/` + `TODO.md`, same commit
