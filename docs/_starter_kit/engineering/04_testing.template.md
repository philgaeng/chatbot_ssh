# Testing standard

**Status:** ‹authoritative› (‹YYYY-MM-DD›).
**Tooling: FILL:** ‹backend runner›, ‹frontend runner›, ‹linter›, ‹type-checker›.

---

## 1. What tests are for here

**FILL:** name the three or four failure modes that would actually hurt — the ones that would cost money, safety, trust, or a person's privacy. Be specific to this product.

> *Worked example:* "a record becomes invisible to the person who must act on it · someone sees a record they must not see · personal data crosses a boundary · a deadline is computed in the wrong timezone and a breach is never reported."

**We test those hardest, and we do not chase a coverage number.** Coverage is a diagnostic — *"which branch has nobody ever run?"* — never a target. Made a target, it produces tests that assert the code does what the code does.

---

## 2. Levels

| Level | Needs | Use it for |
|---|---|---|
| **Unit** | nothing | pure logic: rules, formatters, calculations, permission matrices |
| **Service / integration** | ‹a real database› | use cases through the service layer |
| **Contract / API** | ‹a real database› | status codes, authorization, response shape, data exposure |
| **Pinning / policy** | varies | architectural rules that must not erode (§4) |
| **Frontend unit** | nothing | pure helpers and hooks |
| **End-to-end / manual** | ‹browser, human› | what you have deliberately **not** automated — write down what and why |

**Rule 2.1 — Test through the service layer by default.** That is where the logic lives; such a test needs no HTTP client and stays valid when the route changes.

**Rule 2.2 — Test through the API when the *contract* is what's under test.** Then assert on the wire shape, never on internals.

**Rule 2.3 — Never mock your own database.** → §3.

---

## 3. Integration tests are not optional

**Rule 3.1 — An integration marker declares a *dependency*, not a quarantine.** CI provisions the dependency precisely so these run. **Never** deselect them to make a build green.

*Why, and this is not hypothetical:* on a real project these were deselected "temporarily". A test rotted unnoticed for months while CI paid the full provisioning cost and gated nothing with it. Re-enabling took the suite from 364 to 897 tests for sixteen extra seconds.

**Rule 3.2 — A failing integration test means the fixtures and the test have drifted. That drift is the bug.** Fix one or the other; never deselect.

**Rule 3.3 — Assert on the *set*, not on one identity**, wherever the system chooses among equivalent options (load balancing, ranking, round-robin). "The assignee is one of the eligible ‹people›", never "the assignee is ‹specific person›" — otherwise the test is a false failure every time the fixture data grows.

**Rule 3.4 — Tests clean up what they create**, with an identifiable prefix so leaked rows are obvious and never collide with fixture data.

**Rule 3.5 — Never mutate shared fixture data.** Create your own. A test that edits a shared fixture breaks every test after it, in an order-dependent way that is miserable to debug.

**Rule 3.6 — FILL:** if you use a lighter database in tests than in production, say why and what that costs you. (Usually the honest answer is: don't. A green suite on a different engine is a false green.)

---

## 4. Writing a good test

**Rule 4.1 — The name states the behaviour and the expectation.** `test_‹action›_‹condition›_‹expected›`, not `test_thing_2`.

**Rule 4.2 — Arrange / Act / Assert, visibly separated. One behaviour per test.** Several assertions describing one behaviour is fine.

**Rule 4.3 — Assert on behaviour, not implementation.** "The ‹record› is now at ‹state› and an event exists", not "this private function was called once". Implementation assertions break on every refactor and catch nothing.

**Rule 4.4 — A bug fix ships with the test that fails without it.** Write the failing test *first* — otherwise you cannot know it tests the fix.

**Rule 4.5 — Test the boundary, not the middle:** empty, one, the maximum, one past it, null, wrong timezone, the transition that must be refused.

**Rule 4.6 — Mock only what you don't own.** Third-party services at the client boundary. Your own database and services: never — mocked internals let two real components drift while every test stays green.

**Rule 4.7 — No sleeps, no dependence on the wall clock.** Inject or freeze time. A test that depends on "now" fails at midnight and passes in the morning, and nobody ever debugs it.

**Rule 4.8 — No inter-test ordering.** Each test passes alone and in any order.

---

## 5. Pinning tests — the rules that guard the rules

Some rules are too important to leave to review. A pinning test fails when code and documentation disagree.

**FILL:** one row per architectural invariant.

| Guards | Test |
|---|---|
| ‹the data boundary› | ‹path› |
| ‹fail-closed auth› | ‹path› |
| ‹the permission matrix› | ‹path› |
| ‹the route inventory› | ‹path› |

**Rule 5.1 — When a pinning test fails, the default assumption is that *you* broke the rule**, not that the test is stale. Updating a snapshot is a deliberate act, in its own commit, with its own reason.

**Rule 5.2 — A new architectural rule ships with its pin, or it isn't a rule.** Unenforced rules survive about two sprints. If you cannot pin it, say so where you write it.

---

## 6. Frontend tests

**Rule 6.1 — Colocate tests with the code they test.**
**Rule 6.2 — Extract pure logic out of components and unit-test it.** Calculations, parsing, formatting, filtering — pure functions, tested without a DOM.
**Rule 6.3 — Don't snapshot rendered markup.** It churns on every design change and asserts nothing about behaviour.
**Rule 6.4 — Type-check and lint are tests.** A type suppression or a downgraded lint rule is a **deferral** (§8).

---

## 7. Running them

**FILL:** the commands, and which one is closest to CI.

| Command | Runs |
|---|---|
| ‹…› | ‹…› |

**FILL: what CI runs, in order** — provisioning, migrations, fixtures, the suite, frontend gates, doc link check. Make it copy-pasteable so a developer can reproduce a CI failure locally.

**Rule 7.1 — Strict markers on.** An unregistered marker is an error, so a typo cannot silently skip a suite.

---

## 8. When you cannot test it now

**Rule 8.1 — Skipping, quarantining, expected-failure, a downgraded lint rule, a suppression comment, or a type escape is a *deferral*** — and a deferral that is not logged is a defect. In the **same commit**: a tracked follow-up document (measured inventory + definition of done) **and** a one-line row in the tech-debt backlog.

**Rule 8.2 — Untested-by-decision is fine; untested-by-silence is not.** A written manual test plan is a legitimate decision. An untested path nobody mentioned is how a production 500 ships.

**Rule 8.3 — Say what you skipped**, in the pull request and the build log. "Tests pass" after deselecting a suite is a false report.

---

## 9. Definition of done — testing

- [ ] New logic tested at the level where the logic lives
- [ ] Bug fix has a test that fails without the fix
- [ ] New route: authorization matrix row + route inventory updated
- [ ] New architectural rule: pinning test, or an explicit note that there is none
- [ ] CI green with **nothing** deselected, downgraded, or suppressed
- [ ] Any deferral logged, same commit
