# Sprint — August 2026: Tier-3 Structural

> **Status: ACTIVE** · Branch: `dev/tier3-structural` · Source: [`docs/reviews/devils_advocate_codebase.md`](../../reviews/devils_advocate_codebase.md) §3 Tier 3
> **Read [`00-reassessment.md`](00-reassessment.md) before any ticket.** The Tier-3 table in the source review was re-verified against the tree on 2026-07-15 and **four of its five items were materially wrong**. The tickets below reflect the corrected findings, not the review's text.
> Goal: close the five Tier-3 findings as re-scoped. Target: overall ~76% → low-80s (conversation layer 60→72, backend security 80→85, backend architecture 68→76, portal architecture 62→70, webchat 73→82).
> Estimated total effort: ~1.5 engineer-weeks including tests (the review's estimate of 3×M + 2×L was inflated — see §Effort correction).

## The headline

**Tier 3 is not five structural refactors. It is (at least) two live bugs, one probable third, and two decompositions.** Three of the five items are latent user-facing defects wearing refactor clothes:

| Item | Defect hiding inside it | Confirmed? |
|---|---|---|
| Voice chunks | The whole recording aborts and is discarded when RTT > 1 s; a second path yields silently truncated notes | ✅ **confirmed** — traced end to end |
| `run_flow_turn` | No terminal `else` — an unrecognized state returns zero messages (dead air) | ✅ **confirmed** — AST-verified, no `else` exists |
| Utterance lookup | 3 of 4 call sites derive keys that don't resolve ⇒ `ValueError`; one is wrapped in a bare `except Exception` that would launder it into a `SKIP_VALUE` | ⚠️ **keys confirmed missing; branch reachability UNTRACED** — see below |

Those land first. They are also the smallest.

> **⚠️ One open question gates T3-01's phase.** The three utterance keys provably do not resolve, but **whether their branches are reachable at runtime has not been traced** — they may be dead or swallowed upstream. Reachable ⇒ T3-01 stays Phase 1 as a bug fix. Dead/swallowed ⇒ it demotes to Phase 3 as pure refactorability work and the branches become a dead-code finding. **The deliverable is identical either way.** ~10 min to resolve; see [`00-reassessment.md`](00-reassessment.md) §4 → *Reachability is NOT traced* for the trace guidance. **Do not describe T3-01 as a confirmed live bug until this is answered.**
>
> The uncertainty is itself the argument for the item: **with introspection keys you cannot determine statically whether a lookup resolves.**

## Tickets

| ID | Title | Area | Effort | Spec |
|---|---|---|---|---|
| T3-01 | Explicit utterance keys + repair the 3 broken keys + `get_buttons` | chatbot actions | S | [01-conversation-layer-spec.md](01-conversation-layer-spec.md) §1 |
| T3-02 | `run_flow_turn`: dead branches, terminal `else`, `status_check_form` split, handler table | orchestrator | M | [01-conversation-layer-spec.md](01-conversation-layer-spec.md) §2 |
| T3-03 | Serialize voice-chunk uploads behind chunk-0's `upload_id` | REST_webchat | M | [02-webchat-voice-spec.md](02-webchat-voice-spec.md) |
| T3-04 | Unify the PII boundary: decrypt server-side, delete ticketing's vault workaround | backend + ticketing | M | [03-pii-boundary-spec.md](03-pii-boundary-spec.md) |
| T3-05 | Extract the six remaining settings tab clusters out of `page.tsx` | ticketing-ui | S/M | [04-portal-settings-spec.md](04-portal-settings-spec.md) |

## Execution order & workstreams

Phased deliberately: **bugs before decompositions**, because the bugs are user-facing and the decompositions are the risk.

```
Phase 1 — the live bugs (land first, smallest, highest user value)
  A: T3-01 utterances       ← independent (backend/actions/)
  C: T3-03 voice chunks     ← independent (channels/REST_webchat/)
  B: T3-02 part 1 only      ← dead branches + terminal else (31 lines + 1 else)

Phase 2 — PII boundary
  D: T3-04                  ← STRICT ORDER: backend decrypt + test FIRST, then delete
                               ticketing's workaround, then drop the key. See spec §Order.

Phase 3 — the decompositions
  E: T3-05 settings         ← independent (mechanical, low risk)
  B: T3-02 parts 2-4        ← characterization tests → status_check_form → handler table
                               STRETCH GOAL. Do not start before parts 2's tests are green.
```

**Conflict notes:**
- T3-01 and T3-02 both touch the chatbot but different trees (`backend/actions/` vs `backend/orchestrator/`) — no conflict.
- T3-02 part 1 is severable and should land in Phase 1 even if parts 2-4 slip. It is 31 deleted lines + one `else`.
- T3-04 touches `backend/services/database_services/grievance_manager.py`, a **stable shared service** with ~20 callers (CLAUDE.md §Service boundaries). It is the only ticket here that can regress the live chatbot.

## Effort correction

The review sized this sprint at 3×M + 2×L. Measured against the tree:

| Item | Review | Actual | Why it moved |
|---|---|---|---|
| Utterances | M | **S** | 4 call sites, not ~200 — 196 already use the explicit path |
| Settings split | L | **S/M** | The org sprint already extracted 7,748 lines; the shell is already clean |
| `run_flow_turn` | L | **M** | Table-friendly shape, only 4 shared carriers, handler pattern already exists in-file |
| PII | M/L | **M** | The fix is ~1 line + a test net that does not exist yet |
| Voice | M | **M** | Correct as sized |

**The review's one *under*-estimate:** `run_flow_turn`'s cyclomatic complexity is **189**, not the claimed ~120 (58% worse). Its line count (1,485) is exact.

## Conventions (binding for all agents)

- Work on `dev/tier3-structural`. **Never touch `main`.** See CLAUDE.md git workflow.
- **Build and run only with Docker.** Never `pip install`, `uvicorn`, or run migrations natively (CLAUDE.md §Docker). Host CLIs are read-only.
- Every ticket ships **with its tests in the same commit**. The test requirements in each spec are acceptance criteria, not suggestions.
- **No behavior changes outside the ticket's scope.** If you find an adjacent bug, log it in [`PROGRESS.md`](PROGRESS.md) → Deviations and open a `followups/<slug>.md` + a TODO.md row — **do not fix it**. See the standing rule in [`../README.md`](../README.md).
- **Line numbers in these specs are as of `dev/tier3-structural` @ 2026-07-15 — re-locate before editing.** They will drift, especially in `state_machine.py` and `page.tsx`.
- Update [`PROGRESS.md`](PROGRESS.md) at every commit (status + checklist ticks + deviations).
- When the sprint closes: write `docs/sprints/2026-08_tier3_structural.md` (summary, Tier-2 pattern), move this folder to `docs/sprints/archive/`, update [`../README.md`](../README.md), and re-score [`../../reviews/devils_advocate_codebase.md`](../../reviews/devils_advocate_codebase.md).

## Definition of done (sprint level)

- [ ] All 5 tickets ✅ in PROGRESS.md with tests passing in CI
- [ ] CI green on `dev/tier3-structural` (pytest + tsc + eslint + vitest + build)
- [ ] T3-01 reachability trace done and its phase confirmed (**gates whether T3-01 is a bug fix or a refactor** — do this first, it is ~10 min)
- [ ] Every confirmed live bug is demonstrably fixed, each with a test **verified red on pre-fix code** (the HR-04 standard)
- [ ] Manual verification checklists in each spec executed (recorded in PROGRESS.md, or explicitly marked pending-human)
- [ ] Every deferral logged: `followups/<slug>.md` + a TODO.md 🔵 TECH DEBT row, same commit
- [ ] Devil's advocate codebase doc re-scored; its **Tier-3 table corrected** (it is currently wrong — see 00-reassessment.md)

## Known-carried debt (opened by this sprint, deliberately not fixed here)

| Item | Follow-up |
|---|---|
| `file_name` derived from module name — the *real* refactorability blocker, ~200 sites, M+ | [`followups/utterance-file-name-derivation.md`](followups/utterance-file-name-derivation.md) |
| Ticketing reads `public.grievances` / `public.file_attachments` directly via its own session — violates data rules #1/#5 | [`followups/ticketing-cross-schema-direct-reads.md`](followups/ticketing-cross-schema-direct-reads.md) |

Plus the inherited Tier-1/Tier-2 pending-human items (browser/Keycloak sweeps, CI-on-integration) — see [`../2026-08_tier2_quality.md`](../2026-08_tier2_quality.md) §Leftovers. **This sprint does not clear those.**
