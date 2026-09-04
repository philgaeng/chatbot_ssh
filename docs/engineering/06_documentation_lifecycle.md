# Documentation lifecycle

**Status:** authoritative (2026-09-04). What each kind of document is for, which one wins when two disagree, and **when a sprint spec is promoted into the live specification.**
**Last updated:** 2026-09-04 — deferral rows move from the retired `TODO.md` to [`../SPINE.md`](../SPINE.md). Earlier: sprint citations folded — reasons kept inline, forks recorded in `DECISIONS.md` (lifecycle §10)
**Reads with:** [`../README.md`](../README.md) (the map of the tree) and [`../DECISIONS.md`](../DECISIONS.md) (the public record of forks taken).

---

## 1. The four tiers

Every document in `docs/` is in exactly one tier. The tier decides its authority.

| Tier | Where | Authority | Answers |
|---|---|---|---|
| **1 — Live specification** | `docs/<domain>/` — `ticketing_system/`, `services/`, `rest_chatbot/`, `seah/`, `deployment/` | **Authoritative.** The only tier an agent may build from. | *What does the system do, today?* |
| **1b — Engineering standards** | `docs/engineering/`, `docs/ticketing_system/ui/02` + `/05` | **Authoritative.** Binding on every change. | *How do we build it?* |
| **2 — Reviews** | `docs/reviews/` | **Point-in-time opinion.** Never a build source. | *Where are we weak, as of a date?* |
| **3 — Sprints** | `docs/sprints/<sprint>/` | **In-flight.** Authoritative *only* for work in progress in that sprint. | *What are we changing, and why?* |
| **10 — Archive** | `docs/sprints/archive/`, `docs/*/archive/` | **Read-only history. Never cited as authority.** | *What did we used to believe?* |

**Rule 1.1 — Conflict resolution, in order:** the **code** beats every document; **live spec** beats a sprint doc; a sprint doc beats **archive**; **archive never wins**. Where a live spec and `CLAUDE.md` disagree, the live spec wins and `CLAUDE.md` gets a superseded row (there is already a table for this).

**Rule 1.2 — An agent building a feature reads tier 1 and 1b, plus the sprint folder if one is open. It does not read archive** except to answer "why is it like this?".

**Rule 1.3 — Operational logs are not specs.** [`PROGRESS.md`](../PROGRESS.md) (what was actually built, per commit) and [`TODO.md`](../TODO.md) (open gaps and tech debt) are chronological and never describe intended behaviour. Don't put a spec in them; don't put a build log in a spec.

---

## 2. The lifecycle of one change

```
    ┌─ 3. SPRINT ─────────────────┐        ┌─ 1. LIVE SPEC ────────────┐
    │ DESIGN-*.md   (why + shape) │        │ what the system does now  │
    │ NN-<ticket>.md (the work)   │──────▶ │ + honesty markers         │
    │ PROGRESS.md   (deviations)  │  fold  │                           │
    │ followups/    (deferred)    │        └────────────┬──────────────┘
    └──────────────┬──────────────┘                     │ superseded
                   │ sprint closes                      ▼
                   ▼                          ┌─ 10. ARCHIVE ──────────┐
        summary at sprints/<date>_<name>.md   │ read-only history      │
        + originals to archive/               └────────────────────────┘
```

**Sprint docs are not drafts of live specs. Their durable content is *folded into* the live spec; the sprint doc then becomes history.** This is already the house practice — every sprint summary carries a "Where the durable content lives now" table. §3 makes the timing explicit.

---

## 3. Promotion — the rule (recommended, and now the standard)

> **Promote per ticket, at merge, gated on "the spec matches what the code does" — not on E2E. Then mark honestly what has not been verified end-to-end.**

**Rule 3.1 — The unit of promotion is the ticket, not the sprint.** The live-spec edit is written **in the same pull request as the code that makes it true.** Code, tests, and spec merge together or not at all.

**Rule 3.2 — The gate is agreement with the code**, demonstrated by CI green on that branch with nothing deselected. It is **not** the end-to-end / browser sweep.

**Rule 3.3 — Behaviour that has not been verified end-to-end is promoted anyway, with a marker** (§4). It is not withheld.

**Rule 3.4 — Every sprint doc that changes a live spec declares it up front**, so promotion is never a rediscovery job:

```markdown
**Amends:** `docs/ticketing_system/12_workflows_configuration.md` §4, §6.2 · `docs/ticketing_system/11_roles_and_permissions.md` §3
```

**Rule 3.5 — At sprint close**, write the one-page summary at `docs/sprints/<YYYY-MM>_<slug>.md` with the "Where the durable content lives now" table, move the originals to `archive/`, and confirm nothing durable is left behind. A sprint that closes with durable content still only in its folder is not closed.

### 3a. Where the state lives: **the branch is the version**

The obvious-looking alternative — "edit the live spec as soon as the sprint decides, reconcile at the end" — creates exactly the discrepancy it is trying to avoid: if the sprint slips or is abandoned, the spec on the shared branch now describes something that does not exist, and every agent reading it builds against fiction. **Do not do that.**

There is no need for a separate spec versioning scheme, because git already provides one and it is exact:

| Branch | Its `docs/` describes |
|---|---|
| `main` | what is in **production** |
| `integration/stage` | what is on **staging** |
| `feat/*` | what **that branch** does, including code merged nowhere else |

**Rule 3a.1 — A live-spec statement is true *relative to its branch*.** That is the whole versioning model. Never add `v1`/`v2` version numbers to a spec, or a parallel "as-built vs target" pair of documents — both rot, and git does it better and for free.

**Rule 3a.2 — Releases are tagged, so any past state is recoverable exactly:**

```bash
git show v1.2.0:docs/ticketing_system/12_workflows_configuration.md   # the spec for what shipped in 1.2.0
git log --oneline -- docs/ticketing_system/12_workflows_configuration.md   # why it changed, and with which code
```

**Rule 3a.3 — Small, frequent merges bound the drift.** Spec staleness is capped by how long a branch lives. A branch open for two days can be two days stale; one open for six weeks can be six weeks wrong. This is the main practical reason to keep pull requests small.

**Rule 3a.4 — A doc-only change with no code** (clarifying wording, writing down behaviour that already exists and you have just verified, fixing a broken link) does not need a feature branch or a gate. It goes straight in — there is nothing unbuilt to misrepresent.

### 3b. The timeline, worked

The question this answers: *specs are written at t1; a sprint at t2 decides to change them; the code lands at t5. What does each document say in between?*

| When | Sprint folder (tier 3) | Live spec on `main` (tier 1) | Live spec on the feature branch |
|---|---|---|---|
| **t1** — spec written | — | describes the system | — |
| **t2** — sprint decides a change | `DESIGN-<slug>.md` holds the intent + `**Amends:** …§4` | **unchanged**, plus one `⏳ Changing` pointer line to the DESIGN doc | — |
| **t3** — ticket in progress | `NN-<ticket>.md`, tracker | unchanged | edited alongside the code, as the code takes shape |
| **t5** — PR merges | tracker records deviations | **now updated** — the edit arrived with the code | (merged) |
| **t6** — E2E / browser sweep | — | `⚠ Not verified end-to-end` markers cleared | — |
| **sprint close** | summary + originals to `archive/` | audited (§3c) | — |
| **sprint abandoned** | DESIGN doc marked `Not pursued — <reason>` | `⏳` line removed. **It never lied.** | branch deleted; the spec edit dies with it |

### 3c. What "reconcile at sprint close" actually is

Because reconciliation happened per pull request, sprint close is an **audit, not a rewrite** — twenty minutes, not a day:

- [ ] Nothing durable is stranded in the sprint folder → the "Where the durable content lives now" table is complete
- [ ] Every `⏳ Changing` pointer the sprint raised has been removed or resolved
- [ ] Every honesty marker is still accurate (things get verified without anyone clearing the marker)
- [ ] Every deviation in the sprint tracker is either fixed, or recorded in the live spec as a `⚠ Deviates` marker, or logged in `followups/` + `SPINE.md`
- [ ] Originals moved to `archive/` with forwarding lines

**Rule 3c.1 — If the audit finds a large gap, that is a signal about the process, not just a chore.** It means edits were not riding their PRs. Fix the habit, not only the document.

### Why not "promote after E2E"

It is the intuitive answer and it is the wrong one here, for four reasons:

1. **The gap is where staleness is born.** Between merge and E2E there can be weeks and a dozen tickets. During that window every agent reads a live spec that describes the *old* behaviour and builds against it. That is a worse failure than an unverified line.
2. **E2E never runs for most changes.** Config, permissions, admin screens, migrations, reports. Gating on it means those never promote at all.
3. **We have already paid for this.** The `GET /api/grievance/{id}` "decrypts server-side" line sat in `CLAUDE.md` as fact for months before it was true, and an entire client-side decryption workaround grew inside ticketing because agents believed it. A verification *gate* did not prevent that. A verification *marker* would have.
4. **Deferred documentation is documentation that doesn't get written.** The commit where you still remember the reasoning is the only cheap moment.

### What E2E *does* gate

E2E and the [manual browser sweep](../deployment/17_manual_browser_sweep.md) gate **the marker, not the promotion** — they flip `⚠ Not verified end-to-end` to verified — and they gate **release**. Shipping to production on unverified behaviour is a separate decision from documenting it.

---

## 4. Honesty markers

Anything that describes intended-but-unproven behaviour carries its state inline. This is the mechanism that makes early promotion safe.

| Marker | Means | Cleared by |
|---|---|---|
| *(nothing)* | Built, tested, verified. The default — most lines. | — |
| `⏳ Changing — <link to the DESIGN doc> (<sprint>)` | A decision exists, **the code does not yet**. The text below it is still true and still what you build against. | the PR that lands the change |
| `⚠ Not verified end-to-end` | Code merged, unit/integration green; no human or E2E has driven it through the UI | whoever runs the sweep, with the date |
| `⚠ Partially built — <what is missing>` | Some of the described behaviour exists | the ticket that finishes it |
| `⚠ Not built — planned <sprint/ticket>` | Design intent only — usually means it should not be in a live spec yet at all | the ticket that builds it |
| `⚠ Deviates from spec — <what the code does> (<deviation id>)` | Code and spec disagree, and the code is currently right | fixing the code, or rewriting the spec to match |

**The two ⏳ / ⚠ families do different jobs.** `⏳ Changing` is a **forward pointer** on a statement that is still true — it stops someone building against text that is about to move. Everything with `⚠` marks a statement that is **not fully true today**. Never use `⏳` to describe merged code, and never use `⚠` to describe an intention.

**Rule 4.1 — Never write a claim you have not verified.** If you didn't read the code or run it, the sentence says so. A confident false line costs far more than an honest uncertain one — it is trusted, built upon, and only discovered when something breaks.

**Rule 4.2 — Clearing a marker is a deliberate edit**, made by whoever did the verification, with the date.

**Rule 4.3 — An implementation-status table beats prose** for a spec that is partly built. `docs/seah/02_vault_privacy_and_reveal.md` is the exemplar — copy its shape.

---

## 5. How to write a rule

**Rule 5.1 — The reason travels with the rule.** Every rule states its *why* in one line. When you amend, move, or delete a rule, its reason moves with it.
*Why:* a doc reorg deleted the rationale behind the `public.*` boundary rule and left the bare rule, which then read as arbitrary fiat for months while both sides quietly violated it. **A rule without its reason decays into cargo cult** — and cargo cult is either obeyed pointlessly or discarded silently.

**Rule 5.2 — A rule that isn't enforced isn't a rule.** Link the pinning test, the CI gate, or the review checklist. If there is none, say so: *"Not currently enforced — review-time only."* → [04 §5](04_testing.md#5-pinning-tests--the-rules-that-guard-the-rules)

**Rule 5.3 — Record the *decision*, not just the outcome**, when a real fork was taken: what was chosen, what was rejected, and what would change the answer. `docs/sprints/2026-07_org_chart_positions/DECISION-sensitive-workflows.md` is the shape.

**Rule 5.4 — Document known deviations explicitly**, in a "do not extend" table with a grep to find them. An undocumented deviation reads to the next agent as permission.

**Rule 5.5 — Delete confidently.** A doc that describes something that no longer exists is not harmless history; it is a trap. Archive it, or delete it and let git hold the history.

---

## 6. Anatomy of a live spec

```markdown
# <Subject>

**Status:** authoritative (YYYY-MM-DD). <what this supersedes, if anything>
**Scope:** <what it governs — and what it doesn't>
**Reads with:** <sibling specs>
**Code:** <the paths that implement it>

## 1. …
```

**Rule 6.1 — Status header on every doc**, with a date. A doc with no date is untrustworthy by construction. Two fields, because they answer different questions:

```markdown
**Last updated:** 2026-09-04 — <one line: what changed, or what was verified>
```

*Enforced by* [`tests/repo/test_doc_headers.py`](../../tests/repo/test_doc_headers.py) → `scripts/ops/doc_headers.py --check`. **Fix a gap with `--stamp`; never by hand across the tree.**

> ### ⚠ This rule was unenforced for a month, and the measurement is the argument
>
> Written 2026-08-03. Measured 2026-09-04, before the test existed:
>
> | | |
> |---|---|
> | Live specs with **no** header at all | **40 of 80** |
> | Docs dated at least as recently as their last commit | **3 of 98** |
> | `docs/engineering/` compliance | **7 of 7** |
>
> ⭐ **Obeyed in the folder the rule lives in, and essentially nowhere else** — Rule 5.2 demonstrated
> against the document that states it. The 81 backfilled headers carry
> commit date, not the backfill date**: stamping 81 documents "reviewed today" would have been 81
> claims nobody made (Rule 4.1). **Clearing that marker is a real review**, per Rule 4.2.

**Rule 6.1a — A commit that changes a spec's body must touch its header in the same commit.** Enforced, forward-only from 2026-09-04. *Why:* the alternative — checking that the header date is newer than the file's last commit — sounds equivalent and is a trap; it would have failed **95 of 98** documents on arrival, and a permanently red gate teaches people to walk past gates (D-26; and the `make help` deploy banner retracted 2026-09-03).

**Rule 6.2 — A "Code entry points" table** on any spec that describes implemented behaviour. Someone will need to check whether it's still true; make that cheap. ([`ui/README.md`](../ticketing_system/ui/README.md) does this well.)

**Rule 6.3 — Numbered sections**, so sprint docs and follow-ups can cite `§4.2` and stay citable.

**Rule 6.4 — One subject per file; every folder has a `README.md` index** that says what is in it and what wins.

**Rule 6.5 — Naming:** live specs `NN_snake_case.md` with a stable number (numbers are addresses — never renumber a shipped doc); sprint folders `YYYY-MM_slug/`; follow-ups `followups/kebab-slug.md`; decisions `DECISION-<slug>.md`; designs `DESIGN-<slug>.md`.

**Rule 6.6 — Links are relative and CI-checked.** The `docs/` link job fails the build on a broken relative link (archive excluded). Moving a file means fixing its inbound links in the same commit.

**Rule 6.8 — A doc never carries the commit hash it describes. Derive it.**

The natural header field is *"which commit does this spec describe"* — and it **cannot be written**, because the hash does not exist until after the content is committed. Every workaround costs more than the gap:

| Workaround | Why it is worse than the gap |
|---|---|
| Post-commit hook amends the file with the hash | Rewrites published history; breaks any branch or clone that already has the commit |
| The *next* commit writes the previous one's hash | Permanently one commit stale — and wrong at exactly the moment someone trusts it |
| A generated manifest of doc → hash, committed | Same staleness, plus a second file to drift, plus merge conflicts on every doc change |

So the header carries **only what git cannot infer** — tier, scope, and the date a human last reviewed the content — and the hash is derived on demand, where it is exact and free:

```bash
python scripts/ops/doc_headers.py --provenance    # every live spec → commit, date, subject
git log -1 --format='%h %ad %s' -- docs/services/02_grievance_service.md
git log --oneline -- docs/ticketing_system/12_workflows_configuration.md   # why it changed, with which code
```

*Why this is not a compromise:* §3a already establishes that **the branch is the version**. A spec statement is true relative to its branch, and `git show v1.2.0:<doc>` recovers any past state exactly. A hash in the header would be a worse copy of something git already stores perfectly. **Pinned** by `test_the_header_carries_no_commit_hash`, so a future well-meaning edit cannot quietly add a `Commit:` field.

**Rule 6.7 — Write for the human first.** These docs are read by a person deciding whether to trust the system, and by an agent deciding what to build. Tables over paragraphs, imperatives over description, examples over abstraction. If a sentence needs a second read, rewrite it.

---

## 7. Reviews

**Rule 7.1 — A review is an opinion at a date, never a build source.** It carries a status header saying what it was reviewing and when.

**Rule 7.2 — A review's findings become work or become nothing.** Every accepted finding becomes a `TODO.md` row or a sprint ticket, with the finding id kept so the trail survives.

**Rule 7.3 — A rejected finding is written down with the reason.** The 2026-08 Tier-3 reassessment found **4 of the review's 5 rows were wrong**; without that write-up they'd have been re-raised at the next review. Rejections are as valuable as acceptances.

---

## 8. Archive

**Rule 8.1 — Archive when superseded, not when finished.** A doc that still describes live behaviour stays live no matter how old.

**Rule 8.2 — Archived documents are read-only.** Don't edit them to be correct; they are a record of what was believed.

**Rule 8.3 — Nothing in archive is cited as authority**, and the archive folder's README says so.

**Rule 8.4 — Archiving requires a forwarding address:** the archived doc gets a "superseded by → <live spec>" line at the top, and the archive index maps folder → original location.

---

## 9. Definition of done — documentation

- [ ] The live spec matches what the code now does
- [ ] **Every spec the change touches has its `Last updated:` bumped in the same commit** (§6.1a) — `python scripts/ops/doc_headers.py --check` green
- [ ] Unverified behaviour carries an honesty marker (§4)
- [ ] Every new rule has its reason, and its enforcement point or an admission that it has none
- [ ] Every deferral logged in `followups/` + `SPINE.md`, **same commit**
- [ ] `PROGRESS.md` updated
- [ ] Relative links resolve (CI link job)
- [ ] If a doc moved: forwarding line added, inbound links fixed
- [ ] **No tier-1/1b doc links into `sprints/` or `reviews/`** (§10.1) — reason folded in, pointer dropped
- [ ] **A real fork taken? An entry in [`../DECISIONS.md`](../DECISIONS.md)** (§10.3), not a sprint citation in the spec
- [ ] **No host IP, instance id, incident narrative, secret or staff name in a tier-1 doc** (§10.5)

---

## 10. Audience — which documents are public

The repository is being split: a **private working repo** carrying every tier, and a **public repo**
carrying tier 1 + 1b plus the root open-source files. That makes *"who is this written for"* a property
every document has to carry, and it settles a question the tier model left open.

**The principle, in one line:** *a live spec describes the system at time T, and needs no reference to
how it got there.*

**Rule 10.1 — A tier-1 or tier-1b document must not link into tier 2 or tier 3** (`docs/reviews/`,
`docs/sprints/`). *Why:* a reader who must open a sprint folder to understand a rule is being asked to
reconstruct the project's history in order to read its present — and after the split that link is a 404
for everyone outside the team. **Enforcement:** a pinning test in
[`tests/repo/test_doc_headers.py`](../../tests/repo/test_doc_headers.py), reusing the existing
`SPEC_DIRS` list in [`scripts/ops/doc_headers.py`](../../scripts/ops/doc_headers.py) — **do not define a
second list**; a hand-maintained mirror of a rule is how this repo has been bitten before (see the
boundary-policy note in [`CLAUDE.md`](../../CLAUDE.md)).

**Rule 10.2 — Removing a citation is a *fold*, not a delete.** The reason moves into the spec body in
the same commit — this is §5.1 applied at the boundary. *Why:* a spec that loses a pointer and gains
nothing has been **damaged, not cleaned**; it becomes a rule with no reason, which §5.1 exists to
prevent. If the reason is too long to fold, it was a decision → 10.3.

**Rule 10.3 — Provenance lives in the decision log, not in the spec.** [`docs/DECISIONS.md`](../DECISIONS.md)
carries one dated entry per real fork: what was chosen, what was rejected, and what would change the
answer (§5.3's content, in a public-safe form). *Why:* the spec answers *"what is true?"*; the decision
log answers *"why not the alternative?"*; the sprint folder — internal — keeps the working detail. ⚠ It
is **not** a changelog of every edit: git already does that better, and §3a.1 already forbids version
numbers in specs.

**Rule 10.4 — Every `docs/` folder README declares its audience**, `public` or `internal`, in its
status header. Default: tier 1 and 1b are public; tier 2, tier 3, archive and the operational logs
(`PROGRESS.md`, `TODO.md`) are internal.

**Rule 10.5 — Internal-only content never enters a tier-1 doc:** host IPs and instance ids, incident
narratives, credential or secret material, named staff, and adversarial scoring. *Why:* these are what
make a document unpublishable, and finding them at publish time means rewriting a spec under time
pressure. ⚠ **Corollary — pruning folders does not remove this class.** The staging IP is in the
`Makefile`, an nginx conf, a script and a tracked `.claude/settings.local.json`; the instance id is in
`TODO.md`. A publish filter that only looks at `docs/` gives false confidence.

**Rule 10.6 — The public copy is generated, never hand-maintained.** A script plus an explicit prune
list, run from the private repo. *Why:* two hand-maintained trees diverge — that is not a prediction,
it is the same failure as every other mirror in this repo's history.
