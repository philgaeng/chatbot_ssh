# Operating-model sprint — progress

**Audience:** internal — excluded from the public repository (lifecycle §10.4).

> **Status: OM-01, OM-02 and OM-03 landed — Stream A is closed.** ✅ **Q-01…Q-07 answered 2026-09-04.**
> **The register is validated**: `tests/repo/test_spine.py` runs nine checks in CI, each proven to fail.
> **OM-04, OM-06 and OM-09 landed 2026-09-06.** `07` §11 rows 3, 4, 5 and 6 are closed — the standard is **mostly in force**,
> with only row 2 (no roadmap — OM-05) and row 8 (tracker unwired — OM-07) open.
> **OM-05, OM-09 ready and independent; OM-07 unblocked.** ⚠ OM-05 needs owner input: what the MVP is, and what "launched" means.
> Tracker skeleton — fill as work lands, not at the end.
> Sprint: [`README.md`](README.md) · Why: [`DESIGN-operating-model.md`](DESIGN-operating-model.md) · Questions: [`QUESTIONS.md`](QUESTIONS.md)

## Ticket status

| Ticket | Stream | State | Verification | Branch | Notes |
|---|---|---|---|---|---|
| OM-01 standard | — | ✅ done | `implemented` — *the standard is not in force; §11 is the gap list* | `dev/operating-model` | Landed with the sprint's first commit |
| OM-02 register | A | ✅ done | `implemented` | `dev/operating-model` | [`SPINE.md`](../../SPINE.md) · 64 rows absorbed from `TODO.md` · `PROGRESS.md` § *In progress / next* deleted · 07 §1.2/§5 reconciled |
| OM-03 test | A | ✅ done | `tested` | `dev/operating-model` | `tests/repo/test_spine.py` — **9 checks, each proven to fail on the defect it exists for** by a mutation sweep. ⚠ The sweep caught **two holes review had not**: `startswith` let a `chore+SENSITIVE` profile satisfy the *kind* check, and every non-`GRM` row (`OM-*`, `QA-*`, `HR-*`) was invisible to every field check. It also caught a **substantive miss** — four rows described as "promoted to the Register" existed only in the security view |
| OM-04 intake gate | B | ✅ done | `tested` | `dev/operating-model` | [`docs/items/TEMPLATE.md`](../../items/TEMPLATE.md) — six derivation questions at intake · PR template **confirms** a profile instead of asking · `+SENSITIVE` ⇒ Opus mechanical in `AGENTS.md` · **check 10 in `test_spine.py`**: a `ready`/`current` row with no profile fails, proven two ways (blank cell, `—` placeholder) |
| OM-05 product + roadmap | B | ⬜ ready | — | — | ✅ can start (Q-09 reco is safe) |
| OM-06 amendments | B | ✅ done | `tested` | `dev/operating-model` | Four amendments, each in its owner — reference packs + rule 11 (`00`), design gate (`05` §9a), verification ladder (`06` §4a), session close + **verified** tooling inventory (`AGENTS.md`). ⭐ A fifth thing the ticket did not ask for: the inventory, because an agent writing a second checker for a rule that already has one is how a rule gets two homes that disagree. Closes `07` §11 rows 5 and 6 |
| OM-07 tracker | join | ⛔ blocked | — | — | **Blocker: QA-04** — owner decision 2026-09-06. Not a dependency: OM-02 cleared its real blocker. It is a **sequencing** call, and the reason is in the deviations log |
| OM-09 release + versioning | B | ✅ done | `implemented` | `dev/operating-model` | `deployment/20_release_and_versioning.md` · `CHANGELOG.md` · [D-011](../../DECISIONS.md) · Makefile gate on all four `prod-deploy*` paths. ⚠ **`implemented`, not `tested`** — a release gate cannot be proven without a release. ⭐ Testing it in a throwaway clone **caught a real defect**: the changelog seed named a branch-archive tag as the "previous release" |
| OM-08 starter kit | — | ⬜ proposed | — | — | ⛔ last |

## Open actions that are not tickets

| # | Action | Owner | Why it matters |
|---|---|---|---|
| A-1 | **Answer Q-01…Q-07** | owner | Two of eight tickets cannot start. Six of the ten questions have a recommendation that is safe to accept with one word |
| A-2 | ✅ **Decided 2026-09-04** — [D-009](../../DECISIONS.md) (public repo = versioned release artifact, cut on prod deploy) and [D-010](../../DECISIONS.md) (working repo private, GitHub Team ~$4/mo). ✅ **Implemented the same day** — the repository is private, verified `gh repo view` → `PRIVATE`. **OM-07 is unblocked**; only OM-02 precedes it | owner | — |
| A-3 | **Decide whether the QA sprint adopts this model mid-flight or at its close** | owner | QA-01…05 predate the standard. Recommendation: **at close** — retrofitting a sprint that is ready to start buys nothing and delays it |
| A-6 | ⚠ **Re-open the QA sprint's [Q-01](../2026-09_qa_automation/QUESTIONS.md)** — its GHCR answer was *verified on the premise that the repo is public*. D-010 inverts that premise: private repo → private packages → metered storage and egress. Amended in place 2026-09-04; **QA-02 must not start on the old answer** | QA-02 agent | The sprint's own cost and secret model depends on it |
| A-7 | **Confirm which commits get an image** ([QA Q-16](../2026-09_qa_automation/QUESTIONS.md)) is now also the **cost dial** | owner | Building on every `dev/**` push vs only `integration/**` + `main` is the difference between comfortably inside the free tier and paying overage |
| A-9 | ✅ **DONE 2026-09-06** — `strict_required_status_checks_policy` is `true` on the `Main` ruleset, verified by reading it back through the API (`enforcement: active`, `refs/heads/main` + `refs/heads/integration/*`, all five checks and the other three rules intact). ⚠ The API write was refused (403) — the `gh` fine-grained PAT can read rulesets but not administer them; the owner set it in the UI. *Was:* **Turn on `strict_required_status_checks_policy`** ("Require branches to be up to date before merging") on the `Main` ruleset — **false** today, so a PR can merge on checks that passed against a stale base. **It matters more here than on a typical solo project**, because [`07_work_items.md`](../../engineering/07_work_items.md) §7.3–7.4 explicitly runs parallel streams: two green PRs from different streams can both merge and leave the base red | owner | One checkbox. The cost is rebasing a PR when its base moves |
| A-8 | ⭐ **After this sprint closes: verify `ops` actually detects the npm advisories** — owner decision 2026-09-04 routed the `next@16.2.6` finding to the ops pipeline rather than jumping the queue. Three things must be true before that routing means anything: ops is deployed where it is supposed to run; `scripts/ops/npm_audit.sh` is scheduled so npm findings reach `NPM_AUDIT_JSON` at all; and someone reads `ops.dependency_findings`. **⚠ ops is report-only by design and will never fix it** — the routing is about *detection*, and the fix stays a work item. If ops does not catch it, that is an ops bug and becomes its own item | owner + ops | A real security finding is the only honest test of a monitoring pipeline. This one sat correctly described in one document and on no work list for a day |
| A-5 | ✅ **DECIDED 2026-09-06 — `resources/` is NOT committed**, and it is now in `.gitignore` with the reason inline so the decision cannot quietly reverse itself. The third-party kickoff prompt is someone else's work and committing it would redistribute it; the assessments are inputs, and their conclusions already live in `DESIGN-operating-model.md` and `DECISIONS.md`. ⚠ Accepted consequence: the `resources/01`–`03` citations are local paths and resolve for nobody else — said plainly where they are cited. *Was:* **Decide whether `resources/` is committed** | owner | It holds the three assessments this sprint is built on — and the **third-party prompt** they review. ⚠ The repository is private as of 2026-09-04, so committing no longer publishes it — **but [D-009](../../DECISIONS.md) means a public release repo is coming**, and the prune list, not an oversight, must be what keeps someone else's document out of it |
| A-4 | **Confirm the eight uncommitted QA-sprint doc edits' home** | owner | They travelled onto this branch with the switch and are deliberately not committed here — they belong to the QA sprint |

## Measurements to record (the sprint is not done without these)

| What | Why it matters | Value |
|---|---|---|
| Register rows at seed, by kind | Tells us whether the taxonomy fits the work we actually have | — |
| `TODO.md` size before / after | The 133 KB file is the symptom; the number is the evidence it moved | — |
| Files that claim to answer "what is next", before / after | Target is **1**. It is 7 today | — |
| §11 rows closed / 9 | The sprint's actual definition of done | 0 / 9 |
| Checks in `test_spine.py`, and one proven failure each | A check nobody proved can fail is decoration | **10 / 10** |
| Tickets closed / 9 | The sprint's own progress | **6 / 9** — OM-01…04, 06, 09. Left: OM-05 (owner input), OM-07 (behind QA-04), OM-08 (behind OM-05) |

## Deviations log

| Date | Ticket | Deviation / adjacent finding | Action |
|---|---|---|---|
| 2026-09-06 | OM-07 | ⭐ **Owner decision: OM-07 goes behind QA-04.** OM-02 had cleared OM-07's only real blocker, so this is **sequencing, not dependency** — and it is recorded because a `blocked` row whose blocker is a preference reads as a dependency to the next agent, which is exactly how an ordering choice becomes invisible received wisdom. **The reason:** OM-07 wires a tracker — plumbing, no external risk — while QA-04 is what makes the verification ladder ([`06`](../../engineering/06_documentation_lifecycle.md) §4a, written the same day) reachable at all. Today that ladder's top rung costs 60–75 minutes of human clicking every time, which is why HR-07 has sat `ready` for weeks and why `GRM-001` has no cheap verification path | OM-07 `blocked`, unblock condition named: QA-04a + QA-04b land. ⚠ Needs the QA sprint approved first — every QA row still reads *(sprint not approved)* |
| 2026-09-04 | — | ⭐ **Empirical answer to an open unknown: rulesets DO enforce on a private repo owned by a personal account.** The research found GitHub's docs and community reports disagreeing, users reporting a *"won't be enforced until you move to a Team or Enterprise organization"* banner. It did not apply here — `enforcement: active` stuck and read back through the API. **This removes one of the three reasons to move the repo into an organization**; the other two (an eventual DOR handover, and the GHCR image paths QA-02 bakes into the Makefile and compose files) still stand on their own | Recorded so the org decision rests on two real reasons rather than three, one of which was folklore |
| 2026-09-04 | OM-01 | **Writing the standard surfaced an internal contradiction in itself**: §1.2 says small work is "a register row and a PR" while §5 gives a chore's artifact as a commit line only. Left in deliberately rather than silently picked — it is a real fork about what the register is for | Raised as [Q-08](QUESTIONS.md#q-08--does-a-chore-need-a-register-row-at-all); OM-02 must reconcile §1.2 and §5 whichever way it is answered |

## Acceptance — sprint level

- [ ] **Exactly one file answers "what is next"**, and every file that used to points at it
- [ ] **`07_work_items.md` §11 is empty** — or every remaining row names the ticket that will close it and why it was not this sprint · *6 of 9 closed; rows 2 (OM-05) and 8 (OM-07) open, row 9 deliberate*
- [x] `tests/repo/test_spine.py` is green, and has been **proven to go red** on a malformed register
- [x] The sensitive-path question is answered at intake; the PR template confirms rather than asks
- [ ] `PRODUCT.md` answers "what is this and what is in release 1" without assembly
- [ ] The four amendments live in the standards that own their concerns — **nothing duplicated into `07`**
- [ ] `_starter_kit/` carries the generic model, with every rule's *why* intact
- [ ] `doc_headers.py --check` and the `docs-links` CI job green with nothing deselected
