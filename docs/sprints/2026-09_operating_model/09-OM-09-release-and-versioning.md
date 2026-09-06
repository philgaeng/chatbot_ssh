# OM-09 — Release and versioning

> **kind:** feature (process) · **profile:** chore+SPEC+RELEASE · **size:** M
> **depends on:** [D-009](../../DECISIONS.md), [D-010](../../DECISIONS.md) — both decided 2026-09-04
> Independent of the register — can run in parallel with Stream B.

## Context

The public repository is a **versioned release artifact**, cut when a build reaches production (D-009),
and the working repository goes **private** (D-010). Neither is possible today:

- **The repository has never carried a release tag.** The nine tags that exist are branch archives
  (`archive/branches/…`, `backup-before-split`). Verified 2026-09-04.
- **No `CHANGELOG`**, and [`docs/README.md`](../../README.md) records that a release/versioning policy is
  *"deliberately deferred"*.
- ⚠ **[`engineering/06`](../../engineering/06_documentation_lifecycle.md) §3a.2 tells every reader to run
  `git show v1.2.0:<doc>`** to recover the spec for a past release — against a repository where that
  command has never had anything to find. A documented mechanism resting on nothing.

## Scope

1. **`docs/deployment/20_release_and_versioning.md`** — the policy:
   - **The gate: a version is cut when, and only when, a build is deployed to production.** Nothing
     else cuts one. *Why: it is already the decision that matters, so the tag costs nothing extra and
     cannot become ceremonial.*
   - The scheme (semver or date-based — **decide and record the rejected option**), what a
     major/minor/patch means for this system, and who cuts.
   - `CHANGELOG.md` — generated or hand-written, decided here.
   - What the tag guarantees: the spec tree at that tag describes what that release does. This is
     [`06`](../../engineering/06_documentation_lifecycle.md) §3a applied to a release rather than a branch.
2. **Wire it into `G-RELEASE`** ([`07_work_items.md`](../../engineering/07_work_items.md) §3) — a
   production deploy is not complete until the tag exists.
3. **The `Makefile` prod-deploy path** either cuts the tag or refuses to proceed without one. ⚠ It must
   not *silently* skip: a gate that does not run is decoration, and this repository has shipped that
   twice.
4. **Retire the dangling reference** — `06` §3a.2's `git show v1.2.0:<doc>` becomes true. Use a real
   tag in the example once one exists.

## Not in scope

Generating the public repository (that is the split ticket, in
[`../2026-09_public_repo_split/`](../2026-09_public_repo_split/)). Backfilling tags for past releases —
**do not invent history**; the first tag is the first release cut under this policy.

## Files

| File | Change |
|---|---|
| `docs/deployment/20_release_and_versioning.md` | **new** — the policy and the gate |
| `CHANGELOG.md` | **new**, if hand-written |
| `docs/engineering/07_work_items.md` | `G-RELEASE` gains the tag requirement |
| `docs/engineering/06_documentation_lifecycle.md` | §3a.2 example uses a tag that exists |
| `Makefile` | `prod-deploy` cuts or requires the tag |
| `docs/README.md` | deployment table + the "versioning policy deferred" line retired |

## Acceptance

- [x] A production deploy cannot complete without a tag, and **skipping is loud, not silent** — all four `prod-deploy*` targets depend on `release-check`; the one bypass is `HOTFIX=1` and prints a banner saying a tag is owed today. ⚠ **`prod-deploy-ops` is gated too** — it was the obvious hole: an ops-only path still ships code to production
- [x] `git show <tag>:docs/…` returns the spec for that release — **verified by running it, in a throwaway clone**, because running it here would have required inventing the release the ticket forbids. The mechanism is proven; a real production release is not
- [x] The scheme records its rejected alternative — both: inline in §2 and as [D-011](../../DECISIONS.md), which also records **what would reverse it** (a second system integrating as a library rather than over `/api/v1/`)
- [x] `docs/README.md` no longer says the policy is deferred — it names the policy, and keeps the governance-model half honestly deferred
- [x] No tags invented for past releases — the repository still has exactly its nine branch-archive tags, checked after every test run

## Risks

- **A version scheme chosen without a consumer.** Ask what the version is *for* — DOR's change control,
  a DPG assessor, or our own rollback — before picking. The answer decides date-based vs semver.
- **The gate blocks a hotfix.** Say explicitly what an emergency deploy does. "Tag afterwards, same
  day" is a legitimate answer; "skip quietly" is not.

## Done 2026-09-06 — at `implemented`, and why not `tested`

**A release gate cannot be proven without a release.** Everything testable was run: the gate refuses an
untagged deploy, `HOTFIX=1` bypasses loudly, `make release-tag` cuts `vYYYY.MM.DD`, refuses a second cut
on the same commit, increments `.N` on the same day, and `git show <tag>:docs/…` returns the spec. The
tag mechanics ran in a **throwaway clone** so that no release tag was invented here — § *Not in scope*
forbids exactly that, and the policy's own §2 repeats it.

⭐ **Running it caught a defect that reading it would not have.** The first implementation seeded the
changelog with `git describe --tags --abbrev=0 HEAD^`, which happily named
`archive/branches/20260506/feat/seah-sensitive-intake` as the "previous release" — one of the nine
branch archives the policy explicitly says are not releases. The gate would have shipped telling its
first user to diff against a branch backup from May. Fixed to filter on the release pattern.

**Two decisions, both recorded with their rejected alternative:**

- **Dated over semver** ([D-011](../../DECISIONS.md)) — semver encodes a compatibility promise to an
  integrator, and this system has none; `/api/v1/` already carries the only contract anyone calls.
- **Hand-written changelog over generated** — the audience is DOR change control and a DPG assessor,
  and this repository's commit subjects are written for the next agent: faithful and unreadable to both.

**What is left, and it is the honest residual:** the first production deploy clears `20_release_and_versioning.md`
§7 and moves this to `verified in production`. `06` §3a.2 also still warns that no tag exists — that
warning is correct today and is cleared by the same event.
