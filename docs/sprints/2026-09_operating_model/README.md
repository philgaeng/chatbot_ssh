# Sprint — Operating model (September 2026)

**Audience:** internal — excluded from the public repository (lifecycle §10.4).

> **Status:** 📋 **Proposed — not approved.** Tier 3 per [`engineering/06_documentation_lifecycle.md`](../../engineering/06_documentation_lifecycle.md) §1.
> **Why:** [`DESIGN-operating-model.md`](DESIGN-operating-model.md) — read it first.
> ⚠ **Q-01…Q-07 are unanswered and block OM-02 and OM-03.** OM-01 has landed; OM-04, OM-05 and OM-06
> can start today. See [`QUESTIONS.md`](QUESTIONS.md).

## Goal, in one sentence

**Decide what kind of thing a piece of work is, and how much process it gets, at the moment it arrives
rather than at the moment it merges** — and put the answer in one register that a test keeps honest.

## Tickets

| # | Ticket | Size | Depends on | Can start |
|---|---|---|---|---|
| [OM-01](01-OM-01-work-item-standard.md) | The work-item standard (`engineering/07_work_items.md`) | M | — | ✅ **landed** |
| [OM-02](02-OM-02-the-register.md) | The register (`docs/SPINE.md`); `TODO.md` and `PROGRESS.md` reconciled | L | OM-01 · Q-01…Q-04 | ⛔ blocked on questions |
| [OM-03](03-OM-03-register-test.md) | `tests/repo/test_spine.py` — the enforcement point | S | OM-02 · Q-05…Q-07 | ⛔ after OM-02 |
| [OM-04](04-OM-04-sensitive-path-at-intake.md) | Sensitive-path question moved from merge to intake | S | OM-01 | ✅ now |
| [OM-05](05-OM-05-product-and-roadmap.md) | `PRODUCT.md`, scope + launch definition, `ROADMAP.md` | M | Q-09 *(reco is safe)* | ✅ now |
| [OM-06](06-OM-06-standard-amendments.md) | Reference packs · design gate · verification ladder · session close | M | OM-01 | ✅ now |
| [OM-07](07-OM-07-intake-and-tracker.md) | Unify intake; wire the tracker | M | OM-02 · Q-02 | ⛔ after OM-02 — ✅ **no longer gated**, repo is private |
| [OM-09](09-OM-09-release-and-versioning.md) | Release + versioning: a tag is cut on production deploy | M | D-009 · D-010 *(both decided)* | ✅ now |
| [OM-08](08-OM-08-starter-kit-extraction.md) | Extract the generic model into `_starter_kit/` | S | OM-01…OM-06 | ⛔ last |

**Total ~6–7 days** for one person; **~4–5 elapsed** with the two streams below in parallel.

## How this splits across agents

```
 Stream A — the register                    Stream B — the standards
 (docs/SPINE.md · TODO · PROGRESS)          (engineering/* · AGENTS.md · PRODUCT · ROADMAP)
 ─────────────────────────────────          ────────────────────────────────────────────────
 OM-02 ─▶ OM-03                             OM-04   OM-05   OM-06   OM-09   (independent of each other)
    │                                                  │
    └────────────────┬─────────────────────────────────┘
                     ▼
              OM-07  (gated on D-002)  ─▶  OM-08
```

**Two rules that make the parallelism safe** (07 §7.4 — a lane with two `current` items declares file
ownership):

1. **Stream A owns `docs/SPINE.md`, `docs/TODO.md`, `docs/PROGRESS.md`, `docs/README.md`.**
   **Stream B owns `docs/engineering/*`, `AGENTS.md`, `PRODUCT.md`, `docs/ROADMAP.md`,
   `.github/*`.** The one shared file is `docs/engineering/07_work_items.md` §11 — both streams tick
   rows there. **Tick only your own row**; do not restructure the table.
2. **Stream B does not wait for Stream A.** OM-04/05/06 touch nothing the register touches.

## Branch

```
integration/stage
   └── dev/operating-model          ← the sprint branch (this one)
         ├── om/a-register          ← Stream A: OM-02 → OM-03
         └── om/b-standards         ← Stream B: OM-04 · OM-05 · OM-06
```

⭐ The sprint branch is under `dev/` for a mechanical reason: `ci.yml` triggers pushes on `main`,
`integration/**`, `dev/**` and `dpg/**` only. A docs-heavy branch outside those prefixes would get
`docs-links` and `test_doc_headers` **only through a pull request** — and this repository has twice
shipped a gate that ran on nobody's machine.

## Conventions binding on every agent here

- [`engineering/07_work_items.md`](../../engineering/07_work_items.md) — **this sprint's own subject, and
  binding on it** (Q-10): every ticket above already carries a kind, a profile and a size.
- [`engineering/06_documentation_lifecycle.md`](../../engineering/06_documentation_lifecycle.md) — tiers,
  promotion at merge, honesty markers. Every doc this sprint touches gets its `**Last updated:**` bumped
  in the same commit; run `python scripts/ops/doc_headers.py --check` before committing.
- **The standing deferral rule** ([`../README.md`](../README.md)): anything scoped out, suppressed or
  downgraded gets a `followups/<slug>.md` **and** a register row (or `TODO.md` row until OM-02 lands),
  in the same commit.
- Record every deviation in [`PROGRESS.md`](PROGRESS.md) as you go, not at the end.

## Files in this folder

| File | What |
|---|---|
| [`DESIGN-operating-model.md`](DESIGN-operating-model.md) | Why — the three findings, the shape of the answer, what deliberately does not change |
| [`QUESTIONS.md`](QUESTIONS.md) | 10 open questions, each with a recommendation. Q-01…Q-07 block work |
| [`PROGRESS.md`](PROGRESS.md) | Tracker — status, deviations, measurements |
| `01`–`08` | The ticket specs |

**Source material:** `resources/01`–`03` — the three assessments of 2026-09-04 that produced this sprint.
They are the reasoning; this folder is the plan.
