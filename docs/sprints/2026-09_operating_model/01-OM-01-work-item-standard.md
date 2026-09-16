# OM-01 — The work-item standard

> **kind:** feature (process) · **profile:** chore+SPEC · **size:** M · **depends on:** nothing · **blocks:** everything
> **Status: ✅ landed** with the sprint's first commit. Listed so the register has a worked first row.

## Scope

Create [`docs/engineering/07_work_items.md`](../../engineering/07_work_items.md): three levels, five
kinds, the four-question triage test, nine gates, six derived profiles, definition of ready per kind,
two state fields, identity rules, and where an item lives.

## Not in scope

Building anything the standard describes. That is OM-02 through OM-07, and the standard's **§11 lists
every rule the repository does not yet satisfy**, mapped to the ticket that closes it.

## Acceptance

- [x] `07_work_items.md` exists, passes `python scripts/ops/doc_headers.py --check`
- [x] Every rule carries its *why* (engineering rule 7)
- [x] §11 "Known deviations" names each unbuilt rule and its closing ticket
- [x] Nothing in it claims to be in force
- [ ] Referenced from `00_engineering_index.md` — **OM-06**
