# Operating-model sprint — open questions

**Audience:** internal — excluded from the public repository (lifecycle §10.4).

> **How to use this file.** Every question is one I could not settle from the repository alone. Each
> carries **my recommendation**, and several carry a fact I verified so you are not answering blind.
> **Write your answer on the `> **Answer:**` line** — "follow reco" is a complete answer where you agree.
>
> ✅ **ALL ANSWERED 2026-09-04.** Q-01…Q-07 answered by the owner — **OM-02 and OM-03 are unblocked.**
> Q-08…Q-10 were left blank and are proceeding on their recommendations, marked as such inline.

---

## Blocking OM-02 — the register

### Q-01 · One register file, or one per lane?

**Verified:** the tree currently holds a tracker per sprint folder (4 live) plus `TODO.md` plus
`sprints/README.md` — seven files that partially answer "what is next", which is the problem.

- **One file** (`docs/SPINE.md`): a single answer, easy to test, merge conflicts when two agents add
  rows at once.
- **One per lane**: fewer conflicts, but re-creates the fragmentation this sprint exists to end.

**Recommendation:** **one file.** Merge conflicts on a register are *correct behaviour* — two agents
claiming the same ID should collide loudly, and rows are one line each so the conflict is trivial.

> **Answer:**one file

### Q-02 · Do we adopt a tracker, and when?

**Verified:** `philgaeng/chatbot_ssh` is **public** (checked 2026-09-04 by the review-feedback-loop
sprint). Public issues on a platform receiving SEAH reports means bug reports, screenshots and reviewer
comments are world-readable. `D-002` (private working repo + generated public copy) is **decided,
implementation pending**.

⚠ **This is the same question as the review-feedback-loop sprint's open decision D1** (*"Where the
ticket lives: GitHub Issues … Confirm, or pick a private tracker"*). Answering here settles both.

**Recommendation:** **sequence it.** (1) Build the register in the repo now — it needs no tool and it is
the part agents consume. (2) Land `D-002`. (3) Then GitHub Issues + Projects as the inbox, with the
register **generated** from it in CI and pinned by a test (07 §9.3 — the pattern `dpg/02_questions.md`
already proves). (4) Re-evaluate Linear only if the GitHub board proves painful in daily use — it buys
UI, not capability, and its opinions are strong enough that we would adapt to it more than it to us.

> **Answer:** ✅ **2026-09-04 — follow the sequence, and step (2) is decided.** The working repository
> goes **private** ([D-010](../../DECISIONS.md)) on GitHub Team, one seat (~$4/month — measured against
> ~750 billed CI minutes/month today, ~1,500–2,500 after the QA sprint, against 2,000 free). The public
> repository becomes a **versioned release artifact** cut on production deploy ([D-009](../../DECISIONS.md)),
> not a continuous mirror. **GitHub Issues + Projects** is therefore the tracker, once the flip has
> happened — it is safe only after it. Linear stays a later re-evaluation, not a plan.
> ✅ **And the flip is done** — 2026-09-04, verified `gh repo view` → `PRIVATE`. **OM-07 is unblocked.**

### Q-03 · What happens to `docs/TODO.md`?

**Verified:** 133 KB, last reviewed 2026-07-04, contains ~40 open rows mixed with completed work back to
April, a stale "must fix before demo (May 10)" section, and stale active/queued sprint pointers.

- **Split** into a backlog file and a debt register, both kept.
- **Absorb** into the register: open rows become items (as they are scheduled — 07 §11.9), completed
  history moves to `sprints/archive/`, and `TODO.md` retires behind a forwarding line.

**Recommendation:** **absorb.** Keeping a second list is how the seventh file gets created. ⚠ The
`🔵 TECH DEBT` rows are the exception worth care — they are the index the standing deferral rule writes
into, and `sprints/README.md` promises a future clean-up sprint against *"a complete, measured list"*.
They must land in the register as `kind: debt`, not be dropped.

> **Answer:**absorb

### Q-04 · Does `docs/PROGRESS.md` survive, and in what form?

**Verified:** 43 KB. Its **narrative** sections (what shipped, why, deviations, the "quick state"
recovery block) are genuinely valuable and have no replacement. Its **"In progress / next"** section is
the one that contradicts the file's own header (DESIGN §1.1).

**Recommendation:** **keep it, minus one section.** `PROGRESS.md` stays the build narrative and the
deviations record; **"In progress / next" is deleted** and replaced by a pointer to the register. One
file answers "what is next"; a different file answers "how did we get here".

> **Answer:**follow reco

---

## Blocking OM-03 — the test

### Q-05 · Who assigns the kind, and when?

- **At filing**, by whoever files it — fast, sometimes wrong.
- **At triage**, a separate step before an item can become `ready`.

**Recommendation:** **filer proposes, owner confirms at `ready`.** Rule 2.4 already says
classification is cheap and revisable, so a wrong initial guess costs a re-label. Requiring a separate
triage step before anything can be filed is how items stop being filed.

> **Answer:**follow reco

### Q-06 · Are `done` items kept in the register or removed?

**Recommendation:** **kept until the quarter closes, then moved to an archive section** in the same
file. Removing immediately loses the ability to answer "what shipped this month" without git
archaeology; keeping forever grows the file unbounded and slows every read.

> **Answer:**move to archive

### Q-07 · How is a `GRM-###` ID allocated when two agents work in parallel?

**Recommendation:** **the register file is the allocator** — take the next number, and let git surface a
double-claim as a merge conflict. ⚠ The alternative (a counter file, or a script) adds machinery to
prevent a conflict that is one line to resolve and that we *want* to be visible.

> **Answer:**follow reco

---

## Non-blocking — these change scope, not the start

### Q-08 · Does a chore need a register row at all?

⚠ **The standard is currently ambiguous here** and this question exists because writing it surfaced the
tension: §1.2 says small work is *"a register row and a PR"*, while §5 gives a chore's artifacts as
*"a one-line rationale in the commit"*.

**Recommendation:** **no row for a chore.** A register that fills with dependency bumps stops being
read, and rule 6.1's whole claim is that every row is actionable. A chore is a PR and nothing else.
Whichever way this is answered, **07 §1.2 and §5 must be made to agree** — that edit is part of OM-02.

> **Answer:** ⚠ **No answer given 2026-09-04. Proceeding on the recommendation above** — it is reversible and blocks nothing. Say the word and it flips.

### Q-09 · What horizon does `docs/ROADMAP.md` use?

- **Quarters with dates** — legible to ADB and DOR, and wrong within a month.
- **Ordered outcomes with no dates** — "next / after / someday" — honest, less legible externally.

**Recommendation:** **ordered outcomes, no dates**, each with a *"what would change this"* line (the
field that makes a `DECISIONS.md` entry re-evaluable). ⚠ If an external commitment needs dates, that is
a different document with a different audience — do not make the internal roadmap carry it.

> **Answer:** ⚠ **No answer given 2026-09-04. Proceeding on the recommendation above** — it is reversible and blocks nothing. Say the word and it flips.

### Q-10 · Does this sprint govern itself?

**Recommendation:** **yes — dogfood it.** OM-01…OM-08 get kinds, profiles and verification levels from
day one, and land in the register as OM-02's first rows. If the model is awkward on the sprint that
invented it, that is the cheapest possible moment to find out.

> **Answer:** ⚠ **No answer given 2026-09-04. Proceeding on the recommendation above** — it is reversible and blocks nothing. Say the word and it flips.
