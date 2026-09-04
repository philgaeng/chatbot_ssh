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

- [ ] A production deploy cannot complete without a tag, and **skipping is loud, not silent**
- [ ] `git show <tag>:docs/…` returns the spec for that release — verified by running it
- [ ] The scheme records its rejected alternative (`DECISIONS.md`, or inline with the reason)
- [ ] `docs/README.md` no longer says the policy is deferred
- [ ] No tags invented for past releases

## Risks

- **A version scheme chosen without a consumer.** Ask what the version is *for* — DOR's change control,
  a DPG assessor, or our own rollback — before picking. The answer decides date-based vs semver.
- **The gate blocks a hotfix.** Say explicitly what an emergency deploy does. "Tag afterwards, same
  day" is a legitimate answer; "skip quietly" is not.
