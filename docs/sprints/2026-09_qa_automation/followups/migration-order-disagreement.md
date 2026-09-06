# Follow-up — CI and the Makefile run the three migration streams in different orders

**Logged:** 2026-09-06, as QA-02 landed (it was asked to preserve the Makefile's order, not to
reconcile the two). **Owner:** database · **Status:** open, tracked as `GRM-079`. ⚠ **Nothing is
known to be broken** — this is an unexplained disagreement, which is a different thing.

## The disagreement

| Source | Order |
|---|---|
| [`.github/workflows/ci.yml`](../../../../.github/workflows/ci.yml) | public → ticketing → ops |
| `Makefile` — `REMOTE_DEPLOY_CORE`, `REMOTE_DEPLOY_FULL`, `migrate_all` | **ticketing → public → ops** |
| [`07_migrations_policy.md`](../../../deployment/07_migrations_policy.md) § *May5 SEAH rollout* | ticketing → public (ops not mentioned) |

Both orders demonstrably work: CI is green on its order every run, and every deploy this project
has done used the other one.

## Why neither QA-02 nor QA-05 touched it

⭐ **Because reordering a deploy's migrations as a side effect of an image change is how a schema
surprise ships.** QA-02 preserved the Makefile's order exactly; QA-05 was told to copy
`backend-tests`' steps verbatim, since those provably work against the same seed. Each ticket
kept the order its own path already used, and neither invented a third.

## What would settle it

The schema rules say the three streams **never share ownership of a table**
([`CLAUDE.md`](../../../../CLAUDE.md) § *Migration traceability*), which suggests order cannot
matter — but *"suggests"* is not a basis for changing a deploy, and a rule being written down is
not evidence that the code obeys it.

The cheap, decisive experiment, on a scratch database:

1. Migrate an empty database in each order, dump both schemas, diff them. Identical ⇒ order is
   genuinely free and the disagreement is cosmetic.
2. If they differ, the diff names the dependency, and *that* is the finding.

⚠ **Check `public`'s dependency on `ticketing.locations` first.** The chatbot's intake location
validation reads that table through its own connection (CLAUDE.md § *Data rules*, amended
2026-07-15), which is exactly the shape of thing that would make one order right and the other
lucky.

## Definition of done

- [ ] Both orders run from empty on a scratch database, schemas dumped and diffed
- [ ] One order is chosen, with the evidence recorded
- [ ] `ci.yml`, the Makefile and `07_migrations_policy.md` all state it — the disagreement is
      three places saying different things, so the fix is not done until all three agree
- [ ] If order genuinely does not matter, **say so explicitly** in the policy doc rather than
      leaving a reader to wonder which one is load-bearing
