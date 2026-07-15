# Sprint — August 2026: Tier-3 Structural (CLOSED 2026-07-15)

> Branch `dev/tier3-structural` · Source: [`../reviews/devils_advocate_codebase.md`](../reviews/devils_advocate_codebase.md) §3 Tier 3
> Working docs archived at [`archive/2026-08_tier3_structural/`](archive/2026-08_tier3_structural/) — reassessment, 6 specs, PROGRESS (58 deviations), followups.
> **Score: ~76% → ~83%.** Target was "low-80s". **All five dimension targets met or beaten** — after a second pass closed the two that were short.
> The first close-out reported ~81% with two targets missed; both were then fixed rather than argued down. That history is kept below, because a sprint that grades itself should show the failing grade it started with.

## The headline, and it is not the refactors

**Tier 3 was sold as five structural refactors. It was three live bugs and two decompositions — and the sprint's own re-verification found four of the review's five rows materially wrong before a line was written.** Two of those four were wrong in ways that would have caused a regression if implemented as prescribed.

What shipped, in one line each:

| | |
|---|---|
| **T3-01** | An **HTTP 500 on SEAH intake** and a silent mainline failure with wrong slot state — both repaired. Introspection deleted; `get_buttons` was **dead code**, not a twin bug, so it was deleted rather than fixed. |
| **T3-02** | `run_flow_turn` **1,485 → 150 lines (−90%)**; the `if/elif` chain replaced by a dict table; the 303-line monster split; two dead branches deleted. **The whole dead-air class closed by one postcondition** — 4 instances, one of which the fix's own groundwork discovered. |
| **T3-03** | The voice-chunk race and a **silent truncation** path both killed. `channels/REST_webchat/` gained **a test suite where none existed**, plus CI, in the same commit. |
| **T3-04** | The PII boundary unified **in `backend/`, where the review said it wasn't**. Ticketing now has **no accessor** for the encryption key. |
| **T3-05** | Settings `page.tsx` **4,372 → 301 lines**. Its headline benefit — bundle size — **is measured dead.** |
| **T3-06** | The least-protected path to grievance data got authn + a read audit + a contract. It is **still not an authorization chokepoint**, and says so. |
| **T3-07** | The `ticketing.*` ↔ `public.*` boundary rule amended to as-built and **pinned by tests** — after archaeology found both its goals had been abandoned in code months earlier. |
| **T3-08** | The `@integration` quarantine ended: **CI 364 → 897 tests (+533), 0 deselected.** Not in the original sprint. |

## Final verification (2026-07-15, CI's exact command)

`PYTHONPATH=. pytest tests/ticketing tests/orchestrator tests/actions tests/backend -q --maxfail=20 --strict-markers`
⇒ **960 passed / 7 skipped / 0 failed / 0 deselected** at the first close-out; **966 passed / 7 skipped** after the dead-air fix and p4 (+8 new tests, −2 deleted pins).

For scale: CI ran **364** tests with 390 deselected before T3-08; **897** after it; **960** at
close-out. **+596 gated tests across the sprint** — and the suites that grew most are the ones
that had nothing: `channels/REST_webchat/` (0 → 7 + a CI job), `components/settings/` (0 → 27),
`pii_vault` (0 → 36), and 505 previously-uncharacterized lines of `run_flow_turn` (0 → 12).

## Scorecard

| Dimension | Target | Landed | Note |
|---|---|---|---|
| REST webchat | 82 | **82** ✅ | Gained a test suite it never had. |
| Backend security | 85 | **85** ✅ | T3-04 + T3-06. Authz and rate-limit remain **deliberately visible** holes. |
| Portal architecture | 70 | **70** ✅ | 4,372 → 301 lines. The bundle claim is dead and credited at zero. |
| Conversation layer | 72 | **74** ✅ | Was **70** and short. The postcondition closed the dead-air class outright — 4 instances, not the 2 that were known. |
| Backend architecture | 76 | **76** ✅ | Was **73** and short. p4 landed: `run_flow_turn` −90%, the chain gone. |

**Both misses were fixed, not argued down.** The first close-out graded this sprint at ~81%
with conversation layer and backend architecture short, and said so plainly. That grade is
what identified the work; the work is what moved it. **A dimension is still not credited for
anything logged rather than done** — the authz gap (D-38) and the rate limit (D-31) remain
uncredited and visible.

## The five findings worth carrying forward

### 1. An invariant a codebase only *states* will fail once per site — and be found once per site

This is the sprint's most transferable finding, and it took four instances to see it.

| | Where | Caught by p1's terminal `else`? | By p4's table? |
|---|---|---|---|
| D-08 | unrecognized **state** falls off the chain | ✅ that is what p1 fixed | ✅ (it is the default) |
| D-51 | `add_more_info_flow` completes; the action no-ops on an unset `story_route` | ❌ state *recognized* | ❌ lookup succeeds |
| D-52 | unrecognized **`active_loop`**; the session wedges | ❌ state *recognized* | ❌ lookup succeeds |
| D-59 | SEAH flag off: `next_state` set, nothing dispatched | ❌ state *recognized* | ❌ lookup succeeds |

`state_machine.py:1629` *states* the rule — "re-show choices so we never return empty
messages" — and enforces it nowhere. So it failed at four sites and was found at four sites,
by four different routes, over two sprints. **It was never four bugs. It was one unenforced
invariant.**

**Fixed at the boundary that owns it:** `run_flow_turn` now asserts its own postcondition —
no turn returns zero messages; log at error with everything needed to locate it, then
recover. One guard, four instances, and the next one is caught by construction.

**Two things made it safe, and both were process, not cleverness:**

- **The precondition was measured.** Both followups demanded it before anyone wrote the
  guard: *weigh this against the legitimately-silent turns*. Instrumenting all three of
  `run_flow_turn`'s returns across 208 tests found **3 zero-message turns, all 3 bugs**;
  `attachment_ids_sync` and the `/introduce` restart never return empty. **There was no
  legitimate silence to protect** — which is what made *recovering*, not merely logging, safe:
  the blast radius is exactly the set of turns already broken.
- **That measurement found D-59** — an instance in shipped code that nobody knew about,
  whose test had been green for months because it asserts `next_state` and never looks at
  the messages, while its sibling two functions below does. **Reading would not have found
  it. Measuring did.** Which is the same lesson as §3, arriving from a new direction.

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
| ~~[`run-flow-turn-handler-table`](archive/2026-08_tier3_structural/followups/run-flow-turn-handler-table.md) (p4)~~ | ✅ **DONE.** `run_flow_turn` −90%, the chain gone. The re-sizing was settled by doing it: an **M**, not the spec's S. |
| ~~[`add-more-info-silent-turn`](archive/2026-08_tier3_structural/followups/add-more-info-silent-turn.md) (D-51) · [`unknown-active-loop-silent-fallback`](archive/2026-08_tier3_structural/followups/unknown-active-loop-silent-fallback.md) (D-52)~~ | ✅ **DONE** — plus D-59, which the fix's own groundwork found. One postcondition, four instances. Both followups recommended exactly this over point fixes; both were right. |
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
- **When you delete a bug, delete its pin — and leave a pointer where it stood.** Both characterization tests said in their own docstrings: *if this fails, the bug was fixed; delete it, don't relax it.* Both were deleted on exactly that signal. A pin that outlives its bug is just a failing test with a story.
- **A whitelist is a hand-list wearing a parser's clothes.** p4's first dependency pass *did* use the AST — and still missed three real dependencies, because it filtered through a set of names I typed from memory. D-50's fourth instance, and it caught me. Resolve against real globals, not against what you expect to matter.
- **A deferral needs all three: PROGRESS row + `followups/<slug>.md` + TODO row, in the same commit** — and `git ls-files` it, because two of this sprint's followups passed all three checks while being untracked.
