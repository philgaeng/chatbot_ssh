# Sprint — August 2026: Tier-3 Structural (CLOSED 2026-07-15)

> Branch `dev/tier3-structural` · Source: [`../reviews/devils_advocate_codebase.md`](../reviews/devils_advocate_codebase.md) §3 Tier 3
> Working docs archived at [`archive/2026-08_tier3_structural/`](archive/2026-08_tier3_structural/) — reassessment, 6 specs, PROGRESS (58 deviations), followups.
> **Score: ~76% → ~81%.** Target was "low-80s". Landed in band, but **not** by hitting every target — see §Scorecard.

## The headline, and it is not the refactors

**Tier 3 was sold as five structural refactors. It was three live bugs and two decompositions — and the sprint's own re-verification found four of the review's five rows materially wrong before a line was written.** Two of those four were wrong in ways that would have caused a regression if implemented as prescribed.

What shipped, in one line each:

| | |
|---|---|
| **T3-01** | An **HTTP 500 on SEAH intake** and a silent mainline failure with wrong slot state — both repaired. Introspection deleted; `get_buttons` was **dead code**, not a twin bug, so it was deleted rather than fixed. |
| **T3-02** | `run_flow_turn` **1,485 → 1,175 lines (−21%)**; the dead-air bug closed; two dead branches deleted; the 303-line monster split. **p4 (the table) not done** — its estimate does not survive measurement. |
| **T3-03** | The voice-chunk race and a **silent truncation** path both killed. `channels/REST_webchat/` gained **a test suite where none existed**, plus CI, in the same commit. |
| **T3-04** | The PII boundary unified **in `backend/`, where the review said it wasn't**. Ticketing now has **no accessor** for the encryption key. |
| **T3-05** | Settings `page.tsx` **4,372 → 301 lines**. Its headline benefit — bundle size — **is measured dead.** |
| **T3-06** | The least-protected path to grievance data got authn + a read audit + a contract. It is **still not an authorization chokepoint**, and says so. |
| **T3-07** | The `ticketing.*` ↔ `public.*` boundary rule amended to as-built and **pinned by tests** — after archaeology found both its goals had been abandoned in code months earlier. |
| **T3-08** | The `@integration` quarantine ended: **CI 364 → 897 tests (+533), 0 deselected.** Not in the original sprint. |

## Final verification (2026-07-15, CI's exact command)

`PYTHONPATH=. pytest tests/ticketing tests/orchestrator tests/actions tests/backend -q --maxfail=20 --strict-markers`
⇒ **960 passed / 7 skipped / 0 failed / 0 deselected** (4m00s).

For scale: CI ran **364** tests with 390 deselected before T3-08; **897** after it; **960** at
close-out. **+596 gated tests across the sprint** — and the suites that grew most are the ones
that had nothing: `channels/REST_webchat/` (0 → 7 + a CI job), `components/settings/` (0 → 27),
`pii_vault` (0 → 36), and 505 previously-uncharacterized lines of `run_flow_turn` (0 → 12).

## Scorecard — including what was missed

| Dimension | Target | Landed | Why |
|---|---|---|---|
| REST webchat | 82 | **82** ✅ | The one target beaten on merit — it gained a test suite it never had. |
| Backend security | 85 | **85** ✅ | T3-04 + T3-06. Authz and rate-limit remain **deliberately visible** holes. |
| Portal architecture | 70 | **70** ✅ | 4,372 → 301 lines. The bundle claim is dead and credited at zero. |
| Conversation layer | 72 | **70** ❌ | Characterizing **found two more dead-air bugs** (D-51/D-52), pinned not fixed. |
| Backend architecture | 76 | **73** ❌ | p4 did not land; the chain is still 20 inline `elif`s. |

**A dimension is not credited for work that was logged rather than done.** Two targets missed, stated as missed.

## The five findings worth carrying forward

### 1. "Never return empty messages" is a convention this codebase states and never enforces

Three instances of one class surfaced this sprint. **Only the first is fixed.**

| | Where | Caught by the terminal `else`? |
|---|---|---|
| D-08 | unrecognized **state** falls off the chain | ✅ that is what p1 fixed |
| D-51 | `add_more_info_flow` completes; the action no-ops on an unset `story_route` | ❌ the state is *recognized* |
| D-52 | unrecognized **`active_loop`** silently runs status form 1; session wedges | ❌ the state is *recognized* |

`state_machine.py:1629` *states* the convention. Nothing enforces it, so each site fails separately and is found separately — and **p4's handler table cannot catch D-51/D-52 either**: the dict lookup succeeds, the default never fires. **A `run_flow_turn` postcondition — no turn returns zero messages — subsumes all three, and is cheaper than p4 and worth more.** If one thing from this sprint gets done next, make it that.

### 2. The engineering held; the bookkeeping did not

Three adversarial auditors re-verified every "done" claim. **The engineering survived**: 14/14 T3-01/T3-03 claims held under attempted refutation; T3-07's 11-statement/5-table/3-write census reproduced **exactly** under an independently-written AST collector; T3-05's "verbatim extraction" survived a line-multiset diff of all 7 move commits; D-48's tests were confirmed non-vacuous by re-running both named mutations.

**The record of it did not.** Five defects, four of them *claims about verification*:

- **15 cited commit hashes were unreachable from HEAD** — a rebase left them on a local-only branch. No work lost (`patch-id` matched 1:1), but `git show 25223408` failed for anyone auditing, and the trail would evaporate with that ref.
- **Two followup docs were in no commit** — linked from PROGRESS *and* TODO, present on disk, untracked. The standing rule was satisfied **in appearance**; the `docs-links` CI gate was red on HEAD.
- **`PROVINCE_L1_POOL` "sourced from `demo_officers`"** — false; a hand-typed set. Its stated benefit did not exist, and it was one roster change from rotting by the exact mechanism it was written to prevent.
- **CLAUDE.md rule 1 "Pinned by a test which fails when the code and this list disagree"** — false; nothing opened CLAUDE.md.
- **An "inherited debt" row asserting a quarantine that T3-08 had removed** — contradicting four other places in the same document.

**Three of the five were made *true* rather than softened** (the option T3-04 took for `CLAUDE.md:121`): the pool is now derived, CLAUDE.md's table is now genuinely parsed and gated, the hashes now resolve.

> **The lesson is this sprint's own, turned on itself.** §6 warned that *"a rule without its reason decays into cargo cult."* The sibling: **a claim that merely asserts enforcement decays the same way, but invisibly — because everyone believes a test has their back.** Every false claim was written by the same passes that did the real, verified engineering. Verification and *claims about* verification are different artifacts, and only one of them was being checked.

### 3. Structural questions must be answered structurally — the fourth, fifth and sixth instances

The sprint learned this repeatedly, from different directions:

- **D-14** — the call-site count: settle by **AST+MRO, never grep** (two assessments disagreed 4 vs 6 until the AST settled it).
- **D-42** — the SQL census: scope the collector to `text()` **arguments**, because English prose is clause-shaped. A FROM-anchored regex found **13** "statements" where 11 execute — it was parsing a docstring.
- **D-50** — portal imports: resolve by **parsing**, not by eye. A hand-listed import set missed `getOrgRoles`; `tsc` is a backstop that fires late and only for *missing* symbols, never stale ones.
- **D-06** — `get_buttons` "has the identical flaw" was **grep-shaped reasoning**. AST+MRO: 0 of 200 call sites reach it. It was dead code.

### 4. Reachability guesses have a bad record here — trace them

D-13 estimated T3-01's three sites as *"error/re-prompt branches only, which is why nobody noticed."* Traced: one was a **mainline** branch, another an **HTTP 500** on the SEAH intake flow. The estimate was not merely wrong, it was wrong in the direction that mattered. **This is why D-51/D-52's reachability is logged as unproven rather than dismissed.**

### 5. Repo-level reasoning and infrastructure reality point in opposite directions

T3-06 spent four commits authenticating `:5001` — which the firewall already closed (D-25, read live from the AWS account, not inferred). The port it leaves **open** (`:8000`, orchestrator `/message`) has **no auth at all** (D-35). **Only checking both surfaced it.** Neither the repo nor the console would have told you alone.

## Deliberately carried debt (all logged: followup + TODO row + PROGRESS)

| Item | Why it is not done |
|---|---|
| [`run-flow-turn-handler-table`](archive/2026-08_tier3_structural/followups/run-flow-turn-handler-table.md) (p4) | STRETCH; **re-sized S → M** — 19 arms / ~1,058 lines still inline. The table is its last 5%. |
| [`add-more-info-silent-turn`](archive/2026-08_tier3_structural/followups/add-more-info-silent-turn.md) (D-51) · [`unknown-active-loop-silent-fallback`](archive/2026-08_tier3_structural/followups/unknown-active-loop-silent-fallback.md) (D-52) | Characterization **records** behaviour; fixing under a net you just wrote is how you change what you meant to measure. **Fix both with the postcondition.** |
| [`grievance-api-rate-limiting`](archive/2026-08_tier3_structural/followups/grievance-api-rate-limiting.md) (D-31 + D-39) | No reusable limiter reaches `:5001` (nginx does not proxy it). Unthrottled **and** unaudited on rejection is what makes key brute-force cheap *and* invisible. |
| [`orchestrator-port-8000-open`](archive/2026-08_tier3_structural/followups/orchestrator-port-8000-open.md) (D-35) | Out of T3-06's scope. Lower severity than it reads — `/message` is the public chatbot entry — but it bypasses nginx: **no TLS, no rate limit, on a path that triggers LLM spend.** |
| [`utterance-file-name-derivation`](archive/2026-08_tier3_structural/followups/utterance-file-name-derivation.md) (D-02) | ~200 sites. **The real refactorability blocker** the review's utterance row was actually aiming at. |
| [`voice-chunk-session-store-is-process-local`](archive/2026-08_tier3_structural/followups/voice-chunk-session-store-is-process-local.md) (D-16) | Not a live bug. Works only because uvicorn runs with no `--workers`; adding one silently breaks voice notes. |
| [`settings-tab-render-tests`](archive/2026-08_tier3_structural/followups/settings-tab-render-tests.md) (D-48) · [`dead-project-workflow-select`](archive/2026-08_tier3_structural/followups/dead-project-workflow-select.md) (D-47) | No DOM harness exists **at all** — a dependency decision, not a verbatim move. |
| **Authz on `GET /api/grievance/{id}`** (D-38) | **Not implementable with a service key.** Needs the officer's JWT propagated through ticketing (token exchange), a design change. |
| **Prod (DOR) firewall unverified** (D-26) | Not this AWS account. No repo artifact can answer it. |
| **The `563` vs `567` figures** (D-58) | Recorded, **not explained** — the obvious hypothesis is *disproven*. Inventing a cause is how D-44 shipped a wrong mechanism. |

## Still pending-human (one browser session clears all of it)

D-24 (T3-01 EN/NE re-prompts) · D-17 (T3-03 Slow-3G) · D-33 (T3-06 rendered UI) · D-49 (T3-05 tabs × roles) · D-56 (T3-04 rendered card) — **plus** the inherited H2-01/02/06/08 and HR-07 sweeps. **Largely pre-empted:** T3-01's probe drove both live sites in EN *and* NE; T3-06 and T3-04 were both driven end-to-end through real clients against rebuilt containers. What remains is genuinely the rendered UI.

## Method notes for the next sprint

- **Write characterization tests from probes, not from reading.** Reading tells you what someone *meant*. Both of this sprint's new bugs surfaced because the probe disagreed with the code's apparent intent.
- **Move code by line range, never retype it** (D-50), and prove it: T3-02 p3's extraction is verified by a line-multiset diff — 288/288 moved lines reappear verbatim.
- **A guard that cannot go red is not a guard.** Every guard this sprint ships is mutation-verified against the real tree (D-41), and the ones that read a file assert they found their anchor — a guard that silently finds nothing is worse than none.
- **Report the measurement, not the hope** (D-46). The settings bundle did not move; the sprint says so, three times, and credits it at zero.
- **A deferral needs all three: PROGRESS row + `followups/<slug>.md` + TODO row, in the same commit** — and `git ls-files` it, because two of this sprint's followups passed all three checks while being untracked.
