<!--
  Security fixes: do not describe the vulnerability here before it is disclosed.
  Coordinate through the private channel in SECURITY.md first.
-->

## What changed

<!-- One or two sentences. -->

## Why

<!-- The problem this solves. Link the issue or the sprint ticket if there is one. -->

## How it was tested

<!--
  Commands and results, not "tested locally". Tests run in the container
  (docs/deployment/DOCKER.md) — host runs do not count.
-->

```
```

## Risks and rollback

<!-- What could break, and how to undo it. Write "none obvious" if that is genuinely true. -->

---

## Checklist

- [ ] The item this closes carries a **kind and a profile**, derived at intake ([`docs/items/TEMPLATE.md`](../docs/items/TEMPLATE.md))
- [ ] Branched from `main` (or the current integration branch) — **not committed on `main`**
- [ ] Built and run in Docker; tests run **in the container**
- [ ] Tests written **in this PR**, at the right level ([`docs/engineering/04_testing.md`](../docs/engineering/04_testing.md))
- [ ] CI green with nothing deselected
- [ ] No documentation claim I have not verified; `⚠ Not built` where the code does not do it yet
- [ ] Live spec, [`docs/PROGRESS.md`](../docs/PROGRESS.md) and [`docs/SPINE.md`](../docs/SPINE.md) updated as required
- [ ] Any deferral logged in `docs/sprints/<sprint>/followups/` **and** `docs/SPINE.md`, in this PR
- [ ] New source files carry an SPDX header (`scripts/ops/add_spdx_headers.py`)
- [ ] No real complainant data, contact details, or credentials in the diff, the fixtures, or this description

### Sensitive path — **confirm**, do not decide

⚠ **This list is no longer where the question gets asked.** It is answered at intake, on the item
([`docs/items/TEMPLATE.md`](../docs/items/TEMPLATE.md) §3), because that is the only moment the
answer can still change anything — it selects the model, the reviewer, the tests and the gates
([`07_work_items.md`](../docs/engineering/07_work_items.md) §4.3). By PR time all four are fixed.

**Item / register row:** `GRM-___` · **profile:** `____________`

- [ ] The profile above matches what this diff actually touches — **and if the diff grew into a
      sensitive path after intake, I went back and re-derived it rather than ticking a box here**

Carried by that profile (tick to confirm each one the item claimed, or say why it no longer applies):

- [ ] **Sensitive-workflow (SEAH) visibility** — queue filtering, role resolution, or ticket access
- [ ] **PII boundary** — anything that could put complainant PII into `ticketing.*`, a log, or a cache
- [ ] **Data egress** — a new call to a model provider, a new export, a new backup destination
- [ ] **Schema** — which Alembic stream owns it, and does it replay from empty?

<!--
  If the item said `+SENSITIVE`, this PR was written by Opus and its boundary tests were named
  before the work started. Isolation is reviewed separately from correctness.
  If any box above is newly true, the honest move is to re-derive the profile, not to explain it here.
-->
