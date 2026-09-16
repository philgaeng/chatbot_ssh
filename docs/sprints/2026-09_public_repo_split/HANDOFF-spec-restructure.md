# HANDOFF — restructure the specs for the public/private split

**Status:** instructions, **2026-09-04**, branch `integration/stage` · **for the agent currently updating the specs**
**Binding policy this implements:** [`engineering/06_documentation_lifecycle.md`](../../engineering/06_documentation_lifecycle.md) **§10** — *added today, read it before you touch another spec.*
**Decision behind it:** [`DECISIONS.md`](../../DECISIONS.md) D-002.

---

## 1. What changed under you, in three files

You are mid-flight on a spec pass. Three things landed while you were working; none of them undo your
work, but **§10 changes what "finished" means for every spec you touch from now on.**

| File | Change |
|---|---|
| [`engineering/06_documentation_lifecycle.md`](../../engineering/06_documentation_lifecycle.md) | **New §10 — Audience.** Six rules. §10.1 is the one that changes your work. Also three new §9 DoD items. |
| [`CLAUDE.md`](../../../CLAUDE.md) | Engineering row now names §10 so nobody misses it |
| [`DECISIONS.md`](../../DECISIONS.md) | **New, public** — the home for provenance you are about to strip out of specs. Seeded with two entries; you will add more |

## 2. The principle, and why it is not just tidying

> **A live spec describes the system at time T. It needs no reference to how it got there.**

The repository is splitting: private working repo (all tiers) + **public** repo (tier 1 + 1b only). So a
spec that links into `docs/sprints/` is not merely untidy — after the split **that link is a 404 for
every reader outside the team.**

⚠ **The trap, and the reason this is a handoff rather than a one-line rule:** the fastest way to satisfy
§10.1 is to delete the links. **Do not.** Several specs currently *carry their reasoning by reference* —
the rule is in the spec, the argument is in a sprint doc. Delete the pointer and you get a rule with no
reason, which is precisely the decay [`06 §5.1`](../../engineering/06_documentation_lifecycle.md) exists
to prevent and which [`CLAUDE.md`](../../../CLAUDE.md) calls out by name (*"a rule without its reason
decays into cargo cult"*). **The operation is a fold, not a delete.**

## 3. Your worklist — measured 2026-09-04, not estimated

**28 of 99 tier-1/1b documents carry 93 links into `sprints/` or `reviews/`.**

| Folder | Links | Note |
|---|---|---|
| `docs/ticketing_system/` | **51** | The bulk. `13_projects_and_packages.md` alone has **21** |
| `docs/dpg/` | 16 | Compliance pack — public on its own merits, so these matter |
| `docs/deployment/` | 15 | ⚠ **includes `17_manual_browser_sweep.md` (2), `18_sops_migration_handover.md` (3), `19_incident_response.md` (2) — specs you created in this pass.** The rule applies to new work, not only legacy |
| `docs/engineering/` | 5 | Includes `00_engineering_index.md` |
| `docs/README.md` | 4 | The tree index |
| `docs/services/` | 2 | |

Reproduce the list at any time:

```bash
python3 - <<'PY'
import os,re,collections
from urllib.parse import unquote
import sys; sys.path.insert(0,"scripts/ops")
from doc_headers import SPEC_DIRS, ROOT_DOCS, EXCLUDE_PARTS   # reuse — never re-declare
PRUNE=("docs/sprints/","docs/reviews/"); per=collections.Counter()
files=[os.path.join(r,f) for d in SPEC_DIRS for r,_,fs in os.walk(d)
       if not EXCLUDE_PARTS & set(r.split(os.sep)) for f in fs if f.endswith(".md")] + list(ROOT_DOCS)
for p in files:
    for m in re.finditer(r"\]\(([^)#\s]+)\)", open(p).read()):
        t=unquote(m.group(1)).split("#")[0]
        if t.startswith(("http","mailto:")): continue
        if os.path.normpath(os.path.join(os.path.dirname(p),t)).startswith(PRUNE): per[p]+=1
for p,c in per.most_common(): print(f"{c:3}  {p}")
print(f"\n{len(per)} files · {sum(per.values())} links")
PY
```

## 4. The fold procedure — one link at a time

For each citation, **open the target and decide which of three things it is.** The decision is about the
*content*, not the link:

| The sprint doc holds… | Do this | Result |
|---|---|---|
| **The reason a rule exists** (one or two sentences of argument) | **Fold it into the spec**, beside the rule, in your own words. Drop the link. | Spec is self-contained; §5.1 satisfied |
| **A fork that was taken** — A chosen over B, with a rejected alternative | **Write a `D-NNN` entry in [`DECISIONS.md`](../../DECISIONS.md)** (chosen / rejected / what would change the answer). Link to *that* from the spec if the spec needs it. | Provenance public, spec clean |
| **Working detail** — who built it, ticket numbers, dated progress, measurements of a past state | **Drop the link. Add nothing.** | It was never spec content |

**Judgement call, stated plainly:** if you cannot tell which bucket a citation is in after reading the
target, it is bucket 1 — fold it. An over-long spec is a smaller failure than a rule nobody can justify.

**Worked example — the shape to copy.** `CLAUDE.md`'s data-rules section already does this correctly:
the amended rule states its own reason inline *and* says what the old reason was and why it went. That
is a fold done well; it reads completely without opening anything.

⚠ **Do not edit anything under `docs/sprints/` or `docs/reviews/` while folding.** They are tier 3 and
tier 2 — a dated record. You are copying reasoning out, not curating it. (`06` §8.2.)

## 5. Folder restructure

1. **Every `docs/*/README.md` declares its audience** in the status header, per §10.4:
   `**Audience:** public` for tier 1/1b (`ticketing_system`, `services`, `rest_chatbot`, `seah`,
   `deployment`, `engineering`, `dpg`, `models`), `**Audience:** internal` for `sprints/`, `reviews/`,
   and any `archive/`.
2. **`docs/README.md` gains an audience column** in its index tables, so the split is visible from the
   map rather than only from each folder.
3. **`PROGRESS.md` and `TODO.md` are internal** (§10.4) — they are operational logs (§1.3). Leave them
   where they are; the publish filter excludes them.
4. **Do not create the public repo or a publish script.** Out of scope here — that is D-002's
   implementation and it needs decisions you do not have. Your job is to make the tree *ready* for it.

## 6. Enforcement — the rule is not done until it is pinned

Add a test to [`tests/repo/test_doc_headers.py`](../../../tests/repo/test_doc_headers.py):
**no tier-1/1b document links into `docs/sprints/` or `docs/reviews/`.**

- **Reuse `SPEC_DIRS`, `ROOT_DOCS` and `EXCLUDE_PARTS` from [`scripts/ops/doc_headers.py`](../../../scripts/ops/doc_headers.py).**
  Do **not** declare a second list. A hand-maintained mirror of a rule is a documented failure mode in
  this repo — it is why `CLAUDE.md`'s boundary table is now parsed by its test instead of copied.
- The failure message names the file and the offending link, so the fix is obvious without a re-run.
- ⚠ **Land the test in the same commit as the last fold, not before.** A test that is red on arrival
  teaches people to walk past gates — the exact argument already recorded in `06` §6.1a.

## 7. What not to do

1. **Do not delete a citation without folding its reason** (§4 above). This is the one that matters.
2. **Do not renumber a spec.** Numbers are addresses (`06` §6.5).
3. **Do not add version numbers or an "as-built vs target" pair** — `06` §3a.1 forbids it; the branch is the version.
4. **Do not turn `DECISIONS.md` into a changelog.** One entry per real fork, with a rejected alternative. Git is the changelog.
5. **Do not assume pruning `docs/` makes the tree publishable.** The staging IP lives in `Makefile`, an
   nginx conf, `scripts/ops/aws_to_prod_db_sync.sh` and a tracked `.claude/settings.local.json`; the
   instance id is in `TODO.md`. Out of scope for you — **but say so in `PROGRESS.md`** so it is not
   mistaken for done.

## 8. Sequencing with your in-flight work

- **Finish the spec you are on**, then apply §10 to it before moving on — do not batch the folds into a
  separate pass at the end. Batched cleanups are what §3.1 (*"the spec edit rides its PR"*) is against.
- **Take `docs/ticketing_system/` first** — 51 of 93 links, and `13_projects_and_packages.md` is a third
  of them on its own.
- **`docs/dpg/` last, and carefully.** It is public, it is being read by an external assessor, and its
  citations are *evidence* — several point at follow-ups that substantiate a compliance claim. Those are
  bucket 2 (decision-log) or bucket 1 (fold the measurement into the claim), almost never bucket 3.

## 9. Done when

- [ ] The reproduce script in §3 prints **0 files · 0 links**
- [ ] Every folded reason reads completely **without** the link that used to carry it — spot-check five at random
- [ ] `DECISIONS.md` has an entry for every fork encountered, each with a rejected alternative
- [ ] Every `docs/*/README.md` declares an audience; `docs/README.md` shows it in the index
- [ ] The pinning test is green and fails when a sprint link is deliberately reintroduced
- [ ] `06` §9 DoD satisfied for every spec touched — including the header bump (§6.1a)
- [ ] `PROGRESS.md` records the out-of-scope residue from §7.5
