# OM-02 — The register

> **kind:** feature (process) · **profile:** backend-feature minus DATA/CONTRACT · **size:** L
> **depends on:** OM-01, and Q-01…Q-04 answered · **blocks:** OM-03

## Context

Three documents disagree about what is next, and one contradicts itself
([`DESIGN`](DESIGN-operating-model.md) §1.1). This ticket creates the single answer.

## Scope

1. **`docs/SPINE.md`** — one row per *ready* item: `id · kind · title · profile · state · verification ·
   size · lane · owner`, plus a `done` section for the current quarter (Q-06).
2. **Seed it** from `sprints/README.md` (the live and proposed sprints), the four sprint trackers, and
   the `🔵 TECH DEBT` rows of `TODO.md`. Seeding is **not** a classification pass over all of
   `TODO.md` — 07 §11.9 is explicit that open rows are classified as they are scheduled.
3. **`TODO.md`** per Q-03. ⚠ The `🔵 TECH DEBT` rows are the index the standing deferral rule writes
   into and `sprints/README.md` promises a clean-up sprint against a *complete, measured* list — they
   must arrive as `kind: debt`, not be dropped.
4. **`PROGRESS.md`** per Q-04: delete "In progress / next", point it at the register, keep the narrative.
5. **Reconcile 07 §1.2 with §5** on whether a chore gets a row (Q-08).

## Not in scope

The roadmap (OM-05). Any tracker (OM-07). Classifying the ~40 non-debt `TODO.md` rows.

## Files

| File | Change |
|---|---|
| `docs/SPINE.md` | **new** — the register |
| `docs/TODO.md` | per Q-03; forwarding line if retired |
| `docs/PROGRESS.md` | "In progress / next" → pointer |
| `docs/README.md` | register added to the map; audience row |
| `docs/engineering/07_work_items.md` | §11 rows 1 and 7 updated; §1.2/§5 reconciled |
| `docs/sprints/README.md` | sprint table points at the register for status |

## Acceptance

- [ ] Exactly one file answers "what is next"; every other file that used to points at it
- [ ] Every live and proposed sprint ticket appears as a row
- [ ] Every `🔵 TECH DEBT` row appears as `kind: debt` with its `followups/` link intact
- [ ] The stale "WEEK 3 — must fix before demo (May 10)" section is archived, not deleted silently
- [ ] `PROGRESS.md` no longer contradicts itself
- [ ] `doc_headers.py --check` green; `docs-links` CI job green

## Risks

- **Seeding becomes a classification project.** It must not. If a `TODO.md` row cannot be classified in
  under a minute, it stays in `TODO.md` until someone schedules it.
- **The register becomes the sixth fragment.** Only OM-03 prevents this.
