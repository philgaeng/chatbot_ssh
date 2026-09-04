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

- [ ] Branched from `main` (or the current integration branch) — **not committed on `main`**
- [ ] Built and run in Docker; tests run **in the container**
- [ ] Tests written **in this PR**, at the right level ([`docs/engineering/04_testing.md`](../docs/engineering/04_testing.md))
- [ ] CI green with nothing deselected
- [ ] No documentation claim I have not verified; `⚠ Not built` where the code does not do it yet
- [ ] Live spec, [`docs/PROGRESS.md`](../docs/PROGRESS.md) and [`docs/SPINE.md`](../docs/SPINE.md) updated as required
- [ ] Any deferral logged in `docs/sprints/<sprint>/followups/` **and** `docs/SPINE.md`, in this PR
- [ ] New source files carry an SPDX header (`scripts/ops/add_spdx_headers.py`)
- [ ] No real complainant data, contact details, or credentials in the diff, the fixtures, or this description

### If this PR touches a sensitive path, tick and explain

- [ ] **Sensitive-workflow (SEAH) visibility** — queue filtering, role resolution, or ticket access
- [ ] **PII boundary** — anything that could put complainant PII into `ticketing.*`, a log, or a cache
- [ ] **Data egress** — a new call to a model provider, a new export, a new backup destination
- [ ] **Schema** — which Alembic stream owns it, and does it replay from empty?

<!-- Explain any ticked box here. These get reviewed for isolation, not just correctness. -->
