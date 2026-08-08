# Documentation lifecycle

**Status:** ‹authoritative› (‹YYYY-MM-DD›). What each kind of document is for, which one wins when two disagree, and **when in-flight work is promoted into the live specification.**

> This is the most portable document in the kit — the model below is stack-agnostic. Fill in the folder names and it works as written.

---

## 1. The four tiers

Every document is in exactly one tier. The tier decides its authority.

| Tier | Where | Authority | Answers |
|---|---|---|---|
| **1 — Live specification** | `docs/‹domain›/` | **Authoritative.** The only tier to build from. | *What does the system do, today?* |
| **1b — Engineering standards** | `docs/engineering/`, `docs/‹ui›/` | **Authoritative.** Binding on every change. | *How do we build it?* |
| **2 — Reviews** | `docs/reviews/` | **Point-in-time opinion.** Never a build source. | *Where are we weak, as of a date?* |
| **3 — In-flight work** | `docs/‹sprints›/‹unit›/` | Authoritative **only** for work in progress there. | *What are we changing, and why?* |
| **10 — Archive** | `docs/**/archive/` | **Read-only history. Never cited as authority.** | *What did we used to believe?* |

**Rule 1.1 — Conflict order:** the **code** beats every document; **live spec** beats an in-flight doc; an in-flight doc beats **archive**; **archive never wins**.

**Rule 1.2 — An agent building a feature reads tiers 1 and 1b, plus the in-flight folder if one is open.** It does not read archive except to answer "why is it like this?".

**Rule 1.3 — Operational logs are not specifications.** The build log (chronological, per commit) and the backlog (open gaps) never describe intended behaviour. Don't put a spec in them; don't put a build log in a spec.

---

## 2. The lifecycle of one change

```
    ┌─ 3. IN-FLIGHT ──────────────┐        ┌─ 1. LIVE SPEC ────────────┐
    │ DESIGN-*.md   (why + shape) │        │ what the system does now  │
    │ NN-<task>.md  (the work)    │──────▶ │ + honesty markers         │
    │ tracker       (deviations)  │  fold  │                           │
    │ followups/    (deferred)    │        └────────────┬──────────────┘
    └──────────────┬──────────────┘                     │ superseded
                   │ work unit closes                   ▼
                   ▼                          ┌─ 10. ARCHIVE ──────────┐
        one-page summary + originals archived  │ read-only history      │
                                               └────────────────────────┘
```

**In-flight documents are not drafts of live specs.** Their durable content is *folded into* the live spec; the in-flight document then becomes history. Keep a "where the durable content lives now" table in every closing summary.

---

## 3. Promotion — the rule

> **Promote per task, at merge, gated on "the spec matches the code" — not on end-to-end testing. Then mark honestly what has not been verified.**

**Rule 3.1 — The unit of promotion is the task, not the work unit.** The live-spec edit is written **in the same pull request as the code that makes it true.** Code, tests, and specification merge together or not at all.

**Rule 3.2 — The gate is agreement with the code**, demonstrated by CI green with nothing deselected. It is **not** the end-to-end pass.

**Rule 3.3 — Unverified behaviour is promoted anyway, with a marker** (§4). It is not withheld.

**Rule 3.4 — Every in-flight document that will change a live spec declares it up front**, so promotion is never a rediscovery job:

```markdown
**Amends:** `docs/‹domain›/‹NN_spec›.md` §4, §6.2 · `docs/‹domain›/‹NN_other›.md` §3
```

**Rule 3.5 — At close:** write the one-page summary with the "where the durable content lives now" table, move originals to `archive/`, confirm nothing durable is stranded. A work unit that closes with durable content only in its own folder is not closed.

### Why not "promote after end-to-end testing"

It is the intuitive answer and it is wrong, for four reasons:

1. **The gap is where staleness is born.** Weeks can pass between merge and E2E. In that window every reader — human or agent — builds against a description of the *old* behaviour. That is worse than an unverified line.
2. **E2E never runs for most changes**: configuration, permissions, admin screens, migrations, reports. Gating on it means those are never documented at all.
3. **A gate does not prevent false claims; only honesty does.** On a real project, a specification asserted a security property that was untrue for months; an entire client-side workaround was built because agents believed it. No verification gate caught that. A verification *marker* would have.
4. **Deferred documentation is documentation that doesn't get written.** The commit where you still remember the reasoning is the only cheap moment.

**What end-to-end testing *does* gate:** the marker (it clears it) and the **release**. Shipping unverified behaviour is a separate decision from documenting it.

### 3a. Where the state lives: **the branch is the version**

There is no need for a spec versioning scheme, because version control already provides one and it is exact:

| Branch | Its `docs/` describes |
|---|---|
| ‹production branch› | what is in **production** |
| ‹staging branch› | what is on **staging** |
| `feat/*` | what **that branch** does, including code merged nowhere else |

**Rule 3a.1 — A live-spec statement is true *relative to its branch*.** That is the whole model. Never put version numbers inside documents, and never keep a parallel "as-built vs target" pair — both rot, and version control does it better and for free.

**Rule 3a.2 — Never edit a shared branch's specification ahead of the code.** If the work slips or is dropped, that branch now describes something that does not exist and everyone builds against fiction. This is the single most common way documentation loses trust.

**Rule 3a.3 — Releases are tagged, so any past state is recoverable exactly:**

```bash
git show ‹v1.2.0›:docs/‹domain›/‹spec›.md      # the spec for what shipped in that release
git log --oneline -- docs/‹domain›/‹spec›.md   # why it changed, and with which code
```

**Rule 3a.4 — Small, frequent merges bound the drift.** Staleness is capped by branch lifetime: a branch open two days can be two days stale; one open six weeks can be six weeks wrong. This is the main practical argument for small pull requests.

**Rule 3a.5 — A doc-only change with no code** — a clarification, writing down behaviour you just verified, a broken link — needs no branch and no gate. There is nothing unbuilt to misrepresent.

### 3b. The timeline, worked

*Specs written at t1; work at t2 decides to change them; code lands at t5.*

| When | In-flight folder (tier 3) | Live spec on the shared branch (tier 1) | Live spec on the feature branch |
|---|---|---|---|
| **t1** | — | describes the system | — |
| **t2** — decision made | `DESIGN-‹slug›.md` holds the intent + `**Amends:** …§4` | **unchanged**, plus one `⏳ Changing` pointer line | — |
| **t3** — in progress | task doc, tracker | unchanged | edited alongside the code |
| **t5** — pull request merges | tracker records deviations | **now updated** — the edit arrived with the code | (merged) |
| **t6** — E2E pass | — | `⚠ Not verified` markers cleared | — |
| **close** | summary + archive | audited (§3c) | — |
| **abandoned** | DESIGN marked `Not pursued — ‹reason›` | `⏳` line removed. **It never lied.** | branch deleted; the edit dies with it |

### 3c. What "reconcile at close" actually is

Because reconciliation happened per pull request, close is an **audit, not a rewrite** — twenty minutes:

- [ ] Nothing durable stranded in the in-flight folder
- [ ] Every `⏳ Changing` pointer removed or resolved
- [ ] Every honesty marker still accurate (things get verified without anyone clearing the marker)
- [ ] Every tracked deviation fixed, recorded as a `⚠ Deviates` marker, or logged as debt
- [ ] Originals archived with forwarding lines

**Rule 3c.1 — A large gap at audit is a signal about the process, not just a chore.** It means edits were not riding their pull requests. Fix the habit, not only the document.

---

## 4. Honesty markers

The mechanism that makes early promotion safe.

| Marker | Means | Cleared by |
|---|---|---|
| *(nothing)* | Built, tested, verified. The default. | — |
| `⏳ Changing — ‹link› (‹work unit›)` | A decision exists, **the code does not yet**. The text below is still true and still what you build against. | the pull request that lands it |
| `⚠ Not verified end-to-end` | Merged, automated tests green, nobody has driven it through the interface | whoever verifies, with the date |
| `⚠ Partially built — ‹what is missing›` | Some of the described behaviour exists | the task that finishes it |
| `⚠ Not built — planned ‹unit›` | Intent only — usually means it should not be in a live spec yet | the task that builds it |
| `⚠ Deviates — ‹what the code does› (‹id›)` | Code and spec disagree, and the code is right | fixing the code, or rewriting the spec |

**The two families do different jobs.** `⏳` is a **forward pointer** on a statement that is *still true*. `⚠` marks a statement that is **not fully true today**. Never use `⏳` for merged code or `⚠` for an intention.

**Rule 4.1 — Never write a claim you have not verified.** If you did not read the code or run it, say so. A confident false line is trusted, built upon, and discovered only when something breaks.

**Rule 4.2 — Clearing a marker is a deliberate edit**, by whoever verified, with the date.

**Rule 4.3 — An implementation-status table beats prose** for a partly-built specification.

---

## 5. How to write a rule

**Rule 5.1 — The reason travels with the rule.** Every rule states its *why* in one line, and the why moves whenever the rule moves.
*Why:* on a real project a documentation reorganization deleted the rationale behind a boundary rule and left the bare rule. It then read as arbitrary fiat for months while both sides quietly violated it. **A rule without its reason decays into cargo cult** — obeyed pointlessly, or discarded silently.

**Rule 5.2 — A rule that isn't enforced isn't a rule.** Link the pinning test, the CI gate, or the review checklist. If there is none, write *"Not currently enforced — review-time only."*

**Rule 5.3 — Record the *decision*, not just the outcome**, when a real fork was taken: what was chosen, what was rejected, and what would change the answer.

**Rule 5.4 — Document known deviations explicitly**, in a "do not extend" table with a command that finds them. An undocumented deviation reads as permission.

**Rule 5.5 — Delete confidently.** A document describing something that no longer exists is not harmless history; it is a trap. Archive it, or delete it and let version control hold the history.

---

## 6. Anatomy of a live specification

```markdown
# ‹Subject›

**Status:** authoritative (YYYY-MM-DD). ‹what this supersedes›
**Scope:** ‹what it governs — and what it doesn't›
**Reads with:** ‹sibling specs›
**Code:** ‹the paths that implement it›

## 1. …
```

**Rule 6.1 — Status header with a date on every document.** A document with no date is untrustworthy by construction.
**Rule 6.2 — A "code entry points" table** on anything describing implemented behaviour — someone will need to check whether it is still true; make that cheap.
**Rule 6.3 — Numbered sections**, so other documents can cite `§4.2` and stay citable.
**Rule 6.4 — One subject per file; every folder has an index** saying what is in it and what wins.
**Rule 6.5 — FILL:** naming conventions for each tier. Numbers are addresses — **never renumber a shipped document.**
**Rule 6.6 — Links are relative and checked in CI.** Moving a file means fixing inbound links in the same commit.
**Rule 6.7 — Write for the human first.** Tables over paragraphs, imperatives over description, examples over abstraction. If a sentence needs a second read, rewrite it.

---

## 7. Reviews

**Rule 7.1 — A review is an opinion at a date, never a build source.**
**Rule 7.2 — Every accepted finding becomes a backlog row or a task**, keeping the finding id so the trail survives.
**Rule 7.3 — A rejected finding is written down with the reason.** On a real project a reassessment found **4 of 5** review items were wrong; without that write-up they would have been re-raised at the next review. Rejections are as valuable as acceptances.

---

## 8. Archive

**Rule 8.1 — Archive when superseded, not when finished.** A document still describing live behaviour stays live however old it is.
**Rule 8.2 — Archived documents are read-only.** Don't edit them to be correct; they record what was believed.
**Rule 8.3 — Nothing in archive is cited as authority**, and the archive index says so.
**Rule 8.4 — Archiving needs a forwarding address**: a "superseded by → ‹live spec›" line at the top, and an index mapping folder → original location.

---

## 9. Definition of done — documentation

- [ ] The live spec matches what the code now does
- [ ] Unverified behaviour carries an honesty marker
- [ ] Every new rule has its reason and its enforcement point (or an admission there is none)
- [ ] Every deferral logged, same commit
- [ ] The build log updated
- [ ] Relative links resolve
- [ ] If a document moved: forwarding line added, inbound links fixed
