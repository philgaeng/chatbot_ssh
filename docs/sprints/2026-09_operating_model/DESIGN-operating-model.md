# DESIGN — The operating model: how work is born, classified and gated

**Audience:** internal — excluded from the public repository (lifecycle §10.4).
**Status:** 📋 proposed — not approved. Tier 3.
**Amends:** creates [`docs/engineering/07_work_items.md`](../../engineering/07_work_items.md) · amends [`engineering/00_engineering_index.md`](../../engineering/00_engineering_index.md), [`05_frontend.md`](../../engineering/05_frontend.md) §design gate, [`06_documentation_lifecycle.md`](../../engineering/06_documentation_lifecycle.md) §4, [`../../../AGENTS.md`](../../../AGENTS.md)
**Source material:** `resources/01-assessment-generic-prompt.md`, `resources/02-assessment-vs-our-project.md`, `resources/03-work-item-model.md` — three assessments written 2026-09-04 against an external project-kickoff prompt. This document is their conclusion; the reasoning stays there. ⚠ **`resources/` is untracked as of this commit** — it also holds the third-party prompt those assessments review, and the working repository is public today. Committing it is [A-5](PROGRESS.md); until then the citations above are local paths, not repository paths.

---

## 1. Why this sprint exists

An external reference prompt (a Codex project-kickoff contract) was reviewed against this repository on
2026-09-04. The review found the project **ahead of it on craft and enforcement, and behind it on
planning and intake** — and found one layer missing from *both*: how a piece of work is born,
classified, and routed to the right amount of process.

Three findings drive the scope.

**1.1 — "What is next" has no single answer, and the sources disagree.**

- `docs/TODO.md` (133 KB, header *"Last reviewed: 2026-07-04"*) names the active sprint as **Tier-1
  Hardening (July)** and the queued one as **Tier-2 (August)**. Both finished. `docs/sprints/README.md`
  says the August LLM sprint is in progress with two September sprints proposed. Two months apart, same
  question.
- `docs/PROGRESS.md` contradicts **itself**: its header (2026-09-03) reports *"Sprints 2 and 3 deployed
  to AWS staging"*, while its own **"In progress / next"** section still lists staging deploy as
  outstanding.
- `docs/TODO.md` still carries a **"🔴 WEEK 3 — Must fix before demo (May 10)"** section with unstruck
  items, four months after that demo shipped.

**1.2 — Work has five intake vocabularies and no shared identifier.**

| Fragment | Where | Classifies | Serves |
|---|---|---|---|
| Issue templates — `bug` / `enhancement` + a 7-value Area | `.github/ISSUE_TEMPLATE/` | external reports | outside contributors |
| **Sensitive-path checklist** — SEAH · PII · egress · schema | `.github/PULL_REQUEST_TEMPLATE.md` | blast radius, **at merge** | reviewer |
| Sprint tickets — `HR-01`, `DPG-46`, `QA-04c` | `docs/sprints/<sprint>/` | planned internal work | agents |
| Deviations + `followups/` + TODO **🔵 TECH DEBT** | trackers, `TODO.md` | found mid-flight, and deferred | whoever remembers |
| Triage vocabulary — copy / layout / data / product-decision | `2026-09_review_feedback_loop/` (proposed) | reviewer feedback | a future agent |

Consequences, both live today: **a bug has no home** — it either justifies a sprint folder (too heavy)
or is fixed invisibly — and **the ID space has collided**: `D-001`…`D-008` are decisions in
`DECISIONS.md`; `D-56`, `D-57`, `D-64` are deviations in `TODO.md`. Eight further prefixes are in use
(`DPG` 38, `TP` 12, `SH` 9, `QA` 9, `T3` 8, `H2` 8, `HR` 7, `CL` 4).

**1.3 — We compute blast radius at the moment it is too late to act on it.**

`.github/PULL_REQUEST_TEMPLATE.md` already asks the right question — *"If this PR touches a sensitive
path, tick and explain: SEAH visibility · PII boundary · Data egress · Schema."* At PR time the answer
changes nothing: the design is written, the model was already chosen, the tests exist or do not. Asked
at **intake**, the same list selects the model, the reviewer, the tests and the gates. **It is the same
checklist, moved.**

## 2. The shape of the answer

> **What kind of thing it is** decides where it is filed and who says yes.
> **What it touches** decides how much process it gets.

Collapsing those two axes is what made Jira heavy: ceremony attached to the label means a four-line fix
on the SEAH intake path gets less scrutiny than a new admin column. Attached to blast radius it is right
by construction — and it is a rule this project already applies to model selection, in `AGENTS.md`.
This sprint applies it to process.

Full model: [`engineering/07_work_items.md`](../../engineering/07_work_items.md) — five kinds, a
four-question triage test, nine gates that **all already exist**, six derived profiles, a definition of
ready per kind, and two state fields instead of one.

**⭐ The standard adds no new checks.** It decides which existing ones apply, and moves that decision
from merge to intake.

## 3. What deliberately does not change

- **Sprint folders, `DESIGN-*.md`, `QUESTIONS.md`, trackers, `followups/`, close-and-archive.** Unchanged.
- **The documentation lifecycle** — tiers, promotion at merge, honesty markers, "the branch is the version".
- **The branch and commit strategy.**
- **CI, the test pyramid, the PR checklist.**

The visible day-to-day change is narrower than it sounds: **most bugs and small deviations stop entering
sprint folders at all** (a register row and a PR), and sprints go back to being what they are good at —
a themed batch sharing one design and one questions register.

## 4. Why the standard is written before the register is built

Rule 9 of the engineering index forbids a doc claim that is not yet true, so writing a standard for
unbuilt machinery needs justification.

1. **The sprint otherwise has no definition of done.** A list of eleven gaps with individual estimates
   cannot say whether the sprint succeeded. A standard can: *the repository satisfies it, or it does not.*
2. **We already watched the cost of not doing it.** The second assessment proposed `SPINE.md` as a flat
   task list; the third turned it into a register with kinds, profiles and two state fields —
   structurally different. Building first would have meant building twice.
3. **The honesty mechanism already exists.** [`07_work_items.md`](../../engineering/07_work_items.md)
   §11 lists every rule the repository does not satisfy, each mapped to the ticket that closes it. The
   sprint's definition of done is **clear §11**.

## 5. Why the standard lives in `docs/engineering/`, not in `_starter_kit/`

The starting proposal was to write these rules into `docs/_starter_kit/`. Two reasons not to:

- **Nothing routes a reader there.** `AGENTS.md` and `CLAUDE.md` both point at
  `docs/engineering/00_engineering_index.md`; `docs/README.md` describes the starter kit as *"for reuse
  on a new project"*. A north star outside the reading path is exactly the failure this project measured
  on 2026-09-04 — the header rule scored **7 of 7** inside the folder where it was written and **40 of
  80** everywhere else.
- **The starter kit's credibility comes from being extracted from something that works**, not authored
  as an ideal. That is the property distinguishing it from the reference prompt under review. Authoring
  there first inverts it.

So: write it where it binds, extract it after it has held (OM-08).

## 6. Scope boundary

**In:** the standard; the register and its test; the roadmap and product-scope documents; moving the
sensitive-path question to intake; the four amendments to existing standards; the starter-kit extraction.

**Out:** classifying the ~40 open `TODO.md` rows (they are classified as scheduled — 07 §11.9);
adopting a tracker (gated on `D-002`, see [`QUESTIONS.md`](QUESTIONS.md) Q-02); any code change outside
`tests/repo/`; renumbering historical IDs (07 §8.2).

## 7. Risk

**The standard becomes another well-written unenforced rule.** This is the repository's documented
failure mode, and the evidence in §1.1 says the risk is real: `TODO.md` went unreviewed for two months
while remaining the file everything pointed at.

**The guard is that OM-03 is not optional.** A register nobody validates becomes the *sixth* fragment in
§1.2 — and the one that looks most authoritative. If this sprint ships OM-02 without OM-03, it has made
the problem worse.
