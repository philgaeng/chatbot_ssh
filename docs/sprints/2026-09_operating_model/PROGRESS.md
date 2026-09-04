# Operating-model sprint — progress

**Audience:** internal — excluded from the public repository (lifecycle §10.4).

> **Status: OM-01 landed; the rest not started.**
> ⚠ **Q-01…Q-07 unanswered** — they block OM-02 and OM-03. OM-04, OM-05 and OM-06 can start today.
> Tracker skeleton — fill as work lands, not at the end.
> Sprint: [`README.md`](README.md) · Why: [`DESIGN-operating-model.md`](DESIGN-operating-model.md) · Questions: [`QUESTIONS.md`](QUESTIONS.md)

## Ticket status

| Ticket | Stream | State | Verification | Branch | Notes |
|---|---|---|---|---|---|
| OM-01 standard | — | ✅ done | `implemented` — *the standard is not in force; §11 is the gap list* | `dev/operating-model` | Landed with the sprint's first commit |
| OM-02 register | A | ⬜ proposed | — | — | ⛔ Q-01…Q-04 |
| OM-03 test | A | ⬜ proposed | — | — | ⛔ after OM-02; **not optional** |
| OM-04 intake gate | B | ⬜ ready | — | — | ✅ can start |
| OM-05 product + roadmap | B | ⬜ ready | — | — | ✅ can start (Q-09 reco is safe) |
| OM-06 amendments | B | ⬜ ready | — | — | ✅ can start |
| OM-07 tracker | join | ⬜ proposed | — | — | ⛔ Q-02 **and `D-002`** |
| OM-09 release + versioning | B | ⬜ ready | — | — | ✅ can start — D-009/D-010 decided 2026-09-04 |
| OM-08 starter kit | — | ⬜ proposed | — | — | ⛔ last |

## Open actions that are not tickets

| # | Action | Owner | Why it matters |
|---|---|---|---|
| A-1 | **Answer Q-01…Q-07** | owner | Two of eight tickets cannot start. Six of the ten questions have a recommendation that is safe to accept with one word |
| A-2 | ✅ **Decided 2026-09-04** — [D-009](../../DECISIONS.md) (public repo = versioned release artifact, cut on prod deploy) and [D-010](../../DECISIONS.md) (working repo private, GitHub Team ~$4/mo). **Implementation still pending**: flipping the repo to private is what actually unblocks OM-07 | owner | — |
| A-3 | **Decide whether the QA sprint adopts this model mid-flight or at its close** | owner | QA-01…05 predate the standard. Recommendation: **at close** — retrofitting a sprint that is ready to start buys nothing and delays it |
| A-6 | ⚠ **Re-open the QA sprint's [Q-01](../2026-09_qa_automation/QUESTIONS.md)** — its GHCR answer was *verified on the premise that the repo is public*. D-010 inverts that premise: private repo → private packages → metered storage and egress. Amended in place 2026-09-04; **QA-02 must not start on the old answer** | QA-02 agent | The sprint's own cost and secret model depends on it |
| A-7 | **Confirm which commits get an image** ([QA Q-16](../2026-09_qa_automation/QUESTIONS.md)) is now also the **cost dial** | owner | Building on every `dev/**` push vs only `integration/**` + `main` is the difference between comfortably inside the free tier and paying overage |
| A-5 | **Decide whether `resources/` is committed** | owner | It holds the three assessments this sprint is built on — and the **third-party prompt** they review. The working repository is **public today**, so committing publishes someone else's document. The assessments alone are ours to commit; the prompt is not |
| A-4 | **Confirm the eight uncommitted QA-sprint doc edits' home** | owner | They travelled onto this branch with the switch and are deliberately not committed here — they belong to the QA sprint |

## Measurements to record (the sprint is not done without these)

| What | Why it matters | Value |
|---|---|---|
| Register rows at seed, by kind | Tells us whether the taxonomy fits the work we actually have | — |
| `TODO.md` size before / after | The 133 KB file is the symptom; the number is the evidence it moved | — |
| Files that claim to answer "what is next", before / after | Target is **1**. It is 7 today | — |
| §11 rows closed / 9 | The sprint's actual definition of done | 0 / 9 |
| Checks in `test_spine.py`, and one proven failure each | A check nobody proved can fail is decoration | — |

## Deviations log

| Date | Ticket | Deviation / adjacent finding | Action |
|---|---|---|---|
| 2026-09-04 | OM-01 | **Writing the standard surfaced an internal contradiction in itself**: §1.2 says small work is "a register row and a PR" while §5 gives a chore's artifact as a commit line only. Left in deliberately rather than silently picked — it is a real fork about what the register is for | Raised as [Q-08](QUESTIONS.md#q-08--does-a-chore-need-a-register-row-at-all); OM-02 must reconcile §1.2 and §5 whichever way it is answered |

## Acceptance — sprint level

- [ ] **Exactly one file answers "what is next"**, and every file that used to points at it
- [ ] **`07_work_items.md` §11 is empty** — or every remaining row names the ticket that will close it and why it was not this sprint
- [ ] `tests/repo/test_spine.py` is green, and has been **proven to go red** on a malformed register
- [ ] The sensitive-path question is answered at intake; the PR template confirms rather than asks
- [ ] `PRODUCT.md` answers "what is this and what is in release 1" without assembly
- [ ] The four amendments live in the standards that own their concerns — **nothing duplicated into `07`**
- [ ] `_starter_kit/` carries the generic model, with every rule's *why* intact
- [ ] `doc_headers.py --check` and the `docs-links` CI job green with nothing deselected
