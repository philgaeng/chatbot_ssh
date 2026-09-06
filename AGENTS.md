# GRM Ticketing — Agent Instructions

**Read these files before any code decision:**

| File | Contains |
|------|----------|
| `docs/PROGRESS.md` | Current build status, demo DB state, deviations from spec, commit log, integration stubs |
| `docs/SPINE.md` | **What is next** — the register. Kinds, profiles and gates: `docs/engineering/07_work_items.md` |
| `docs/engineering/00_engineering_index.md` | **How we build** — DB, service layer, API, tests, frontend, doc lifecycle. Binding on every change. |
| `docs/deployment/DOCKER.md` | How to build, start, migrate, seed, and debug the containers |
| `CLAUDE.md` | Locked architecture decisions, hard boundaries, full spec |

Read `PROGRESS.md` first (what was *actually built*), then `SPINE.md` (what's next), then the **engineering standard for the layer you're touching**, then `CLAUDE.md` (the locked architecture).
Consult `DOCKER.md` any time you need to build or restart containers.

> Paths corrected 2026-08-03: the old `docs/claude-tickets/` folder was dissolved — its operational logs moved to the `docs/` root and the Docker runbook to `docs/deployment/`.

## Model selection

⭐ **The profile decides the model. `+SENSITIVE` ⇒ Opus, mechanically — there is no separate
judgment call.** The profile is derived at intake from six questions ([`docs/items/TEMPLATE.md`](docs/items/TEMPLATE.md) §3,
[`07_work_items.md`](docs/engineering/07_work_items.md) §4.1), and `G-SENSITIVE` fires on PII · auth ·
SEAH · a live complainant channel · a new external egress. *Why mechanically: §4.2 — every exception
ever granted on this list was granted on the basis of diff size, which does not correlate with risk.
Leaving it to judgment at the keyboard is how a four-line SEAH change gets written by the cheap model.*

Everything else goes by **difficulty and blast radius, not diff size**:

- **Opus (high reasoning effort)** — anything carrying `+SENSITIVE`; plus concurrency/transaction correctness, large behavior-preserving refactors, and any edit to a live complainant/SEAH channel. A four-line change to the SEAH intake is still Opus.
- **Sonnet (medium effort)** — mechanical config, CI/YAML, UI/error-state plumbing, and test scaffolding driven by an unambiguous spec.
- **Haiku** — trivial doc/text edits only; not for feature or fix workstreams. **Never for anything `+SENSITIVE`, whatever its size.**

Each sprint records a per-ticket model recommendation in its `agents/README.md` "Model selection" table, and each runbook header carries a `**Model:**` field. When in doubt on a PII/security/concurrency touchpoint, prefer Opus.

## Closing a session

**End every session with this block.** Six lines, in this order — it is what the next session reads
first, and it is the difference between resuming and re-deriving.

```
RESULT     one sentence: what is true now that was not true before
COMPLETED  the items closed, with their verification level (implemented / tested / deployed / verified)
LEFT OPEN  what was started and not finished, or found and not fixed — with its register id
NEXT ITEM  the id and title of what should be picked up, and why that one
READ FIRST the 2-3 files the next session needs before touching anything
START WITH the first concrete action, specific enough to run
```

*Why six lines and not a summary: a summary is written for the person who already has the context and
is useless to the one who does not. Each line above answers a question the next session would
otherwise spend its first ten minutes reconstructing — and `LEFT OPEN` is the one that decays fastest,
because an unfinished thing nobody named becomes an unfinished thing nobody knows about.*

⚠ **A finding that is only in the session summary is lost.** Anything worth the next session's time
gets a register row in [`docs/SPINE.md`](docs/SPINE.md) in the same commit — the summary points at the
row, never replaces it.

## What already exists — check before building it

This repository has more enforcement than it looks like. **Before writing a script or a check, look
here**; adding a second one that does the same job is how a rule ends up with two homes that disagree.

| Tool | Does | Run it |
|---|---|---|
| `scripts/ops/doc_headers.py` | Every live spec carries a dated header, and no commit edits a spec body without bumping it. Also derives provenance | `--check` · **`--check-staged`** · `--provenance` |
| `.githooks/pre-commit` | Runs `--check-staged` before the commit exists — the only moment the fix is one line rather than a rule violation. **Run `make hooks` once per clone** or it is inert | `make hooks` · bypass `git commit --no-verify` |
| `tests/repo/test_spine.py` | The register is well-formed: ids unique, allocator accurate, kinds valid, one `current` per lane, `blocked` rows name a blocker, `done` rows carry a verification level, **`ready` rows carry a profile** | `pytest tests/repo/test_spine.py` |
| `tests/repo/test_doc_code_refs.py` | Backticked code citations in docs point at files and lines that exist | `pytest tests/repo` |
| `tests/repo/test_doc_headers.py` | Nine checks on the header rule itself — every live spec dated, no future dates, no commit hash in a header, **rule 10.1** (no tier-1/1b doc links into `sprints/` or `reviews/`) and **rule 10.5** (no internal-only content in a public spec) | `pytest tests/repo` |
| `tests/ticketing/test_pii_boundary.py` | Ticketing holds no decryption path — the PII boundary cannot be reopened by accident | `pytest tests/ticketing` |
| `tests/ticketing/test_boundary_policy.py` | The `public.*` table set in `CLAUDE.md` matches what the code actually touches | `pytest tests/ticketing` |
| `scripts/ops/run_mutations.py` | Re-runs the repository's hand-authored mutation checks: *can this test still go red?* Turns a prose claim into a command, so a test that **stopped** catching its mutation is noticed | `python scripts/ops/run_mutations.py [--module <name>]` |
| `scripts/ops/security-preflight.sh` | Pre-deploy security sweep | before a deploy |
| `scripts/ops/restore_drill.sh` | Proves the backup restores, rather than assuming it | on the schedule in the ops docs |
| `scripts/ops/gen_dpg_questions.py` | Regenerates `dpg/02_questions.md` from `00_compliance_status.md`; pinned by a test | when compliance status changes |
| `scripts/ops/add_spdx_headers.py` | SPDX header on every new source file | before committing new files |
| `scripts/ops/npm_audit.sh` | npm advisories into the ops pipeline | scheduled |

⚠ **Not built yet:** the browser/E2E harness (QA-04). Until it lands, *"verified end-to-end"* means a
human drove it — [`docs/deployment/17_manual_browser_sweep.md`](docs/deployment/17_manual_browser_sweep.md),
60–75 minutes, and its warning is worth reading first.
