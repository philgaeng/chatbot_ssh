# OM-05 — Product truth and roadmap

> **kind:** feature (docs) · **profile:** chore+SPEC · **size:** M · **depends on:** Q-09
> Independent of the register — can run in parallel.

## Context

"MVP" appears **once** in the entire live spec tree. No document says what this system is in one place,
what is in the first release, what is explicitly out, or what condition constitutes *launched* — for a
system being handed to a government department and assessed as a Digital Public Good. Three audiences
(ADB, DOR, a DPG assessor) each ask this first, and today each answer is assembled by hand.

## Scope

1. **`PRODUCT.md`** (repo root) — what the system is, who it serves, its capabilities, its constraints,
   and its current status. **Assembly, not authoring**: the content exists across `CLAUDE.md`,
   `ticketing_system/00`–`01`, `deployment/01` and the DPG pack.
2. **Scope and launch definition** — MVP, explicit non-goals, and the observable conditions that make
   the DOR handover complete. Lives in `PRODUCT.md` or `ticketing_system/01`; do not create a third home.
3. **`docs/ROADMAP.md`** — ordered outcomes per Q-09, each with a *"what would change this"* line.

## Not in scope

Dates or delivery commitments (Q-09). Re-litigating locked decisions — `PRODUCT.md` describes, it does
not decide; forks belong in `DECISIONS.md`.

## Files

`PRODUCT.md` (new) · `docs/ROADMAP.md` (new) · `docs/README.md` (map + audience) · `CLAUDE.md`
(overview trimmed to a pointer) · `07_work_items.md` §11 row 2

## Acceptance

- [ ] A newcomer can answer "what is this, and what is in release 1?" from one file
- [ ] Every roadmap item carries its *what would change this* line
- [ ] `PRODUCT.md` contains no claim not already true in a live spec or marked `⚠ Not built`
- [ ] Audience declared on both; `doc_headers.py --check` green
