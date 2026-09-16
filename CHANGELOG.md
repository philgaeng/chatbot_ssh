# Changelog

Releases of the GRM ticketing platform (Kakarbhitta–Laukahi Road, ADB Loan 52097-003).

**A version is cut when, and only when, a build is deployed to production.** Nothing else cuts one —
not a merge, not a staging deploy, not a schedule. Scheme: `vYYYY.MM.DD`, with `.N` for a second
release the same day. The policy, the reasoning, and the deploy gate that enforces it are in
[`docs/deployment/20_release_and_versioning.md`](docs/deployment/20_release_and_versioning.md).

Entries are **written for someone who uses or oversees the system** — a DOR change-control reader, an
ADB reviewer, an assessor — not for the next engineer. Seed an entry with
`git log --oneline <previous-tag>..<new-tag>` (`make release-tag` prints the exact command), then edit
it into what changed for a user. The commit log stays the record for engineers; this file is not a
second copy of it.

Each release's tag also carries its specifications: `git show <tag>:docs/…` returns the documentation
that was true for that release, because a spec edit rides the same commit as the code that makes it
true.

---

## Unreleased

⚠ **No release has been cut yet.** The nine tags in this repository (`archive/branches/…`,
`backup-before-split`) are **branch archives, not releases**, and are deliberately not backfilled as
such — an invented tag would claim a spec tree describes a deploy nobody verified it against.

The first entry below appears when the first production deploy runs under the policy above.

<!--
Template for a release entry:

## v2026.09.06

**Deployed to production:** 2026-09-06 · **Tag:** `v2026.09.06`

### Added
- What a user can now do that they could not before.

### Changed
- Behaviour that already existed and now works differently. Say what someone should expect to see.

### Fixed
- What was broken, in terms of what the user experienced — not the internal cause.

### Security
- Disclosed only after the fix is deployed (SECURITY.md). Describe the exposure, not the exploit.

### Operational notes
- Migrations run, downtime taken, anything DOR needs to know before or after the window.
-->
