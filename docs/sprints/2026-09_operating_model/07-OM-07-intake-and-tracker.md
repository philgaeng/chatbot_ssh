# OM-07 — Unify intake, and decide the tracker

> **kind:** feature (process) · **profile:** backend-feature minus DATA · **size:** M
> **depends on:** OM-02, Q-02 — ⚠ **and gated on `D-002`** (the working repo is public today)

## Context

Five intake vocabularies share no identifier ([`DESIGN`](DESIGN-operating-model.md) §1.2), and a sixth
arrives with the review-feedback-loop sprint. That sprint's **open decision D1** — *"Where the ticket
lives: GitHub Issues … Confirm, or pick a private tracker"* — is the same question as Q-02. **This
ticket settles both, and it must land before that sprint starts** or the triage agent will invent a
seventh vocabulary.

⚠ **`philgaeng/chatbot_ssh` is public.** Issues on a platform receiving SEAH reports would be
world-readable — bug reports, screenshots, and reviewer comments alike. `D-002` is what makes this safe.

## Scope

1. **Map the five vocabularies onto the five kinds.** The issue templates already carry the right
   distinction — the bug form reads *"behaves differently from what the documentation says it should"*,
   which **is** the bug/deviation test (07 §2.2). Make it explicit, and give the feedback-loop triage
   agent the same vocabulary rather than a private one.
2. **Record the decision** in `docs/DECISIONS.md` (chosen / rejected / what would change the answer),
   and update the feedback-loop DESIGN's D1 to point at it.
3. **If a tracker is adopted:** the register is **generated** from it in CI and pinned by a test — the
   pattern `dpg/02_questions.md` + `test_dpg_questions_generated.py` already proves (07 §9.3). The join
   is the item ID and **no field is duplicated across the line** (07 §9.2).
4. **Two trackers by design after `D-002`** — public issues on the mirror for outside contributors,
   private issues on the working repo. An accepted public report is triaged and re-filed internally.
   Say this once, in `CONTRIBUTING.md`.

## Not in scope

Building the feedback widget (that sprint owns it). Migrating historical issues.

## Acceptance

- [ ] One vocabulary; every fragment in DESIGN §1.2 maps onto it or is retired
- [ ] A `DECISIONS.md` entry exists with its *what would change the answer* line
- [ ] The feedback-loop sprint's D1 resolves to this decision rather than restating it
- [ ] If a tracker is adopted: the generator runs in CI and its pinning test fails on drift
- [ ] `CONTRIBUTING.md` explains the two-tracker split
