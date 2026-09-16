# Release and versioning

**Status:** authoritative (2026-09-06). How a release is cut, what its tag guarantees, and the gate that makes it happen.
**Last updated:** 2026-09-06 — created. ⚠ **The policy is written and the gate is wired; no release has been cut yet** — the first tag appears at the first production deploy after this date. See §7.
**Audience:** public.
**Reads with:** [`../engineering/06_documentation_lifecycle.md`](../engineering/06_documentation_lifecycle.md) §3a (the branch is the version) · [`../engineering/07_work_items.md`](../engineering/07_work_items.md) §3 (`G-RELEASE`) · [`../DECISIONS.md`](../DECISIONS.md) (D-009 · **D-011**, which records why not semver and what would reverse it).

---

## 1. The gate

**A version is cut when, and only when, a build is deployed to production. Nothing else cuts one.**

*Why this and not a release cadence: the production deploy is already the decision that matters — someone
weighed the risk and pressed the button. Attaching the tag to that moment costs nothing extra and cannot
drift from reality. A tag cut on a schedule, or on a merge to `main`, describes an intention rather than
an event, and a version that describes an intention is ceremony.*

Consequences, stated plainly:

- **Staging deploys do not cut tags.** Staging exists to be wrong.
- **A merge to `main` does not cut a tag.** `main` is an integration target, not a release.
- **Not every commit reaches a version.** The tag names what was deployed, not what was written.

## 2. The scheme — `vYYYY.MM.DD`, with `.N` for a second release the same day

```
v2026.09.06        the release deployed to production on 2026-09-06
v2026.09.06.1      a second release the same day (a hotfix, usually)
```

**The rejected alternative was semver** ([D-011](../DECISIONS.md)), and the reason is worth keeping: semver's `major.minor.patch`
encodes a **compatibility promise to an integrator**, and this system has no integrators. Nothing
consumes the GRM as a library; the one interface anybody calls is the HTTP API, and that already carries
its own version in the path (`/api/v1/`), independent of any release number. So semver's central
judgment — *is this a major?* — would have no correct answer here, and a decision with no correct answer
gets made arbitrarily and then defended. That is how a version becomes ceremony.

What the date scheme gives the three actual consumers:

| Consumer | What they ask | What the tag answers |
|---|---|---|
| **DOR change control** | "Which version is running, and when did it change?" | Directly — the tag *is* the date |
| **A DPG assessor** | "Is this a versioned release with a changelog?" | A tag, a `CHANGELOG.md` entry, and a spec tree that matches |
| **Us, rolling back** | "What was running before this?" | The previous tag, sorted correctly by string order |

⚠ **Do not backfill tags for past releases.** Nine tags already exist (`archive/branches/…`,
`backup-before-split`) and none is a release — they are branch archives. The first release tag is the
first release cut under this policy. *Why: an invented tag claims a spec tree describes a deploy nobody
verified it against, which is precisely the guarantee §4 exists to make true.*

## 3. Who cuts it

**The person running the production deploy**, on the machine running it, before the deploy proceeds. The
gate in §5 refuses to deploy otherwise.

## 4. What the tag guarantees

**The spec tree at that tag describes what that release does.**

This is [`06`](../engineering/06_documentation_lifecycle.md) §3a — *"the branch is the version"* — applied
to a release instead of a branch. It is what makes this command meaningful:

```bash
git show v2026.09.06:docs/ticketing_system/12_workflows_configuration.md
```

It works because the spec edit rides the same commit as the code (§3), so a tag on a deployed commit
necessarily carries the specs that were true for it. **The guarantee is a consequence of an existing
rule, not a new promise** — which is the only kind worth making.

## 5. The gate is in the Makefile, and skipping it is loud

Every `prod-deploy*` target depends on `release-check`:

```bash
make release-tag      # cut the tag for today (refuses if one already exists for this commit)
make prod-deploy      # refuses unless HEAD carries a release tag
```

`release-check` fails with an explanation and the command to fix it. **There is exactly one escape
hatch, and it announces itself:**

```bash
make prod-deploy HOTFIX=1
```

which prints a banner saying a tag is owed **today** and proceeds. *Why an escape hatch at all: a gate
that cannot be bypassed during an incident gets bypassed by editing the Makefile at 2am, and that edit
is never reverted. An explicit, loud, logged bypass is safer than a gate people learn to route around.*
*Why it is not silent: this repository has shipped a decorative gate twice, and both times the gate
existed and simply did not run.*

⚠ **The tag is required, not cut automatically by the deploy.** *Why: a deploy that tags on entry leaves
a tag describing a release that then failed halfway; a deploy that tags on success cannot tag the commit
if the deploy died. Requiring the tag first means it names a commit somebody deliberately chose to
release — and a failed deploy leaves a tag that is simply not deployed anywhere yet, which is harmless
and visible.*

## 6. `CHANGELOG.md` — hand-written at tag time, seeded from git

```bash
git log --oneline <previous-tag>..HEAD
```

is the **seed**, not the entry. Someone edits it into what changed *for a user of the system* before it
goes in `CHANGELOG.md`.

*Why not generated: the audience is DOR's change control and a DPG assessor, and this repository's commit
subjects are written for the next agent — accurate, long, and about internal mechanisms. A generated
changelog would be faithful and unreadable to both readers who matter. At this volume — a handful of
production deploys — the human edit is minutes, and a generator would need its own pinning test to stop
it drifting from the tags, which is a second mechanism to maintain for no gain.*

## 7. ⚠ Not yet verified end-to-end

**No release tag exists as of 2026-09-06.** The policy is written, and the gate and the tag mechanics
are exercised. What has **not** happened is a production deploy under it:

| Claim | State | Proven by |
|---|---|---|
| The gate refuses a deploy with no tag | ✅ **proven** | Run against this repository, which has no release tag: it refuses and prints the fix |
| `HOTFIX=1` bypasses loudly | ✅ **proven** | Run — it prints the banner and proceeds |
| `make release-tag` cuts `vYYYY.MM.DD`, refuses a second cut on the same commit, and increments `.N` on the same day | ✅ **proven** | Exercised in a throwaway clone, so no release tag was invented in this repository |
| The changelog seed names the previous **release**, never one of the nine branch-archive tags | ✅ **proven** | ⭐ Caught as a real defect by that same test — the first implementation named `archive/branches/20260506/feat/seah-sensitive-intake` |
| `git show <tag>:docs/…` returns the spec for that release | ✅ **mechanism proven** | Run against a tag in the clone; unproven only for a *real* production release |
| The gate does not obstruct a real deploy | ⚠ **unproven** | The first production deploy |
| The tag names something actually running at DOR | ⚠ **unproven** | The first production deploy |

Per [`06`](../engineering/06_documentation_lifecycle.md) §4a this policy sits at verification
`implemented`, not `verified in production`. **Clearing this section is the job of whoever cuts the first
tag** — with the date.
