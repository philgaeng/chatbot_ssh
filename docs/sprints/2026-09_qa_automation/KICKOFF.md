# KICKOFF — QA & build pipeline sprint

**Audience:** internal — the opening brief for the agent running this sprint.
**Written:** 2026-09-06, from `dev/operating-model`, by the session that committed this sprint's spec pass.
**Read this once, then work from the tickets.** Everything below is either state you cannot see from
the files, or a trap that would cost you an hour to discover.

---

## 1. Where you are

**Branch: `dev/qa-automation`.** Pushed, and **green on all five required CI checks** as of 2026-09-06
— `backend-tests`, `ui-checks`, `webchat-checks`, `docs-links`, `dpg-platform-independence`. That is
the first green build on any branch since 2026-09-04, so if CI goes red, **you did it** — do not
assume it was already broken.

This branch also carries the operating-model sprint's commits (merged in, not cherry-picked). That is
deliberate and it means **this branch cannot be merged independently of that work**. Both go to
`integration/stage` together, and the owner merges **only when a sprint is complete** — do not open a
merge PR mid-sprint.

⚠ **The sprint's specs were rewritten on 2026-09-04 and only committed on 2026-09-06.** If you have
been looking at these files on another branch, you have been reading the old ones.

## 2. Read in this order

1. [`DESIGN-qa-and-build-pipeline.md`](DESIGN-qa-and-build-pipeline.md) — why, and the seams a
   completeness review found. **Read it first; the tickets assume it.**
2. [`README.md`](README.md) — the five tickets, estimates, streams.
3. [`QUESTIONS.md`](QUESTIONS.md) — Q-01…Q-19. **Q-01…Q-15 are answered and folded into the ticket
   that needs each one**, so a ticket is workable from its own spec. Read the answers anyway for
   Q-02, Q-09 and Q-16.
4. Your ticket.
5. [`../../engineering/00_engineering_index.md`](../../engineering/00_engineering_index.md) — how we
   build, and the **reference pack** for the area you are touching.

## 3. The one open decision — Q-16, and it blocks one ticket only

**[Q-16 — which commits get an image](QUESTIONS.md#q-16--which-commits-get-an-image) is unanswered and
is the owner's call.** QA-02 proposed building on `main` + `integration/**`; QA-05 pulls
`IMAGE_TAG=<this commit's sha>`. Both cannot hold: on a pull request no such tag exists, so the e2e
job fails for a reason that has nothing to do with the change under test.

**It blocks QA-05. It does not block the sprint.** QA-01, QA-02, QA-03 and QA-04 all start without it.
⭐ **It is also the cost dial** — building on every `dev/**` push versus only `integration/**` + `main`
is the difference between staying in the free tier and paying overage. Put the recommendation in front
of the owner early; do not improvise around it inside QA-05.

## 4. What can start today

| Stream | Tickets | Note |
|---|---|---|
| **A** | QA-01 → QA-02 → QA-03 | Sequential. QA-01 is ½ day and is the outage fix |
| **B** | QA-04a → then 04b / 04c / 04d fan out | **Independent of stream A — can start today** |
| join | QA-05 | After QA-02, QA-03, QA-04a — **and after Q-16** |

**If you are one agent, start with QA-04a.** It is the longest pole, it unblocks three parallel
sub-tickets, and it is the capability the rest of the project is waiting on: nothing in this
repository can look at a page today, so *"verified end-to-end"* currently means 60–75 minutes of the
owner clicking through [`../../deployment/17_manual_browser_sweep.md`](../../deployment/17_manual_browser_sweep.md).
QA-04b is what retires that.

## 5. Things that will cost you an hour if you learn them the hard way

**⚠ QA-02's premise inverted, and the ticket has been rewritten but re-read the answer.** GHCR was
free because the repository was public. [D-010](../../DECISIONS.md) made it **private** on 2026-09-04,
so packages are private and storage and egress are metered. **Do not start QA-02 from the pre-D-010
reasoning.** This is tracked as A-6 in [`PROGRESS.md`](PROGRESS.md).

**⚠ Never run `ticketing.seed.mock_tickets --reset` on the dev database.** It wipes and re-seeds,
taking projects, organizations and officers with it, and the owner's local setup must survive. If the
stack refuses ticket intake with *"Add a Level 1 officer … for these packages"*, the fix is additive:

```bash
docker exec nepal_chatbot-backend-1 python -m ticketing.seed.ensure_officer_coverage          # report
docker exec nepal_chatbot-backend-1 python -m ticketing.seed.ensure_officer_coverage --apply  # write
```

Measured 2026-09-06: five missing rows were failing twenty `tests/ticketing` tests. See
[`../../deployment/02_setup.md`](../../deployment/02_setup.md) §4.

**⚠ Two local test failures are container artifacts, not your bug.** `tests/repo/test_spdx_headers.py`
fails inside the backend container because the image has **no `git` binary**; it passes on the host and
in CI. `tests/backend/test_benchmark_set.py` fails when the dev DB's taxonomy has drifted from the
authored CSV — CI seeds from the CSV and passes. Run `tests/repo` on the host, the rest in the container.

**⚠ `resources/` is gitignored by decision** (A-5, 2026-09-06). Citations to `resources/01`–`03` in the
operating-model sprint are local paths and resolve for nobody. Do not "fix" them by committing the folder.

**⚠ The `docs-links` CI job checks every relative link in `docs/` and every backticked path in the root
`*.md`.** It is cheap to run locally and it *will* catch a link to a file that only exists on another
branch. Extract it from `.github/workflows/ci.yml` and run it before you push.

## 6. The operating model now applies — lightly, and here is exactly how much

A work-item standard landed on 2026-09-06:
[`../../engineering/07_work_items.md`](../../engineering/07_work_items.md), with the register at
[`../../SPINE.md`](../../SPINE.md) and an intake form at [`../../items/TEMPLATE.md`](../../items/TEMPLATE.md).

**⚠ Whether this sprint retrofits itself to that standard is an OPEN owner decision** (A-3 in the
operating-model sprint's tracker). The standing recommendation is **at the sprint's close, not
mid-flight** — retrofitting five tickets that are ready to start buys nothing and delays them. **Work
your tickets as written.** What does apply to you from day one:

- **Run `make hooks` once.** A pre-commit hook refuses a commit that edits a live spec's body without
  bumping its `**Last updated:**` header. Bypass is `git commit --no-verify`, and say why in the message.
- **Anything you find that is not your ticket gets a row in [`../../SPINE.md`](../../SPINE.md)**, in the
  same commit — take the next free `GRM-###` from the ⚠ line near the top of that file. A finding that
  lives only in a session summary is lost.
- **Model selection is not a judgment call where `+SENSITIVE` applies** — PII, auth, SEAH, the live
  complainant channel, a new external egress ⇒ Opus, mechanically. `AGENTS.md` § *Model selection*.
  For this sprint that fires on **QA-04d** (the webchat sweep drives the complainant channel) and on
  anything in QA-02 that moves credentials or registry auth.
- **A production deploy now cuts a version tag** and `make prod-deploy` refuses without one
  ([`../../deployment/20_release_and_versioning.md`](../../deployment/20_release_and_versioning.md)).
  QA-02 changes how deploys work — read that before touching the deploy path.

## 7. What only the owner can do — ask early, they are intermittent

Two of these need the DOR production host, and the owner's access to it is intermittent. **Ask on day
one**, because one of them halves QA-02's build cost:

| # | Ask | Why it matters |
|---|---|---|
| **A-1** | `uname -m` on the DOR prod host | If `aarch64`, QA-02 drops amd64 and **every image build halves**. Until answered, multi-arch is the safe default (Q-02's recorded answer) |
| **A-2** | `curl -sI https://ghcr.io/v2/` from the DOR prod host | Decides whether prod can pull at all, or needs `docker save`/`load` or an internal mirror |
| **Q-16** | The decision in §3 | Blocks QA-05 and sets the CI cost |

⚠ **A-3 in [`PROGRESS.md`](PROGRESS.md) is stale.** It warns that
`strict_required_status_checks_policy` is `false`; it was turned **on** 2026-09-06 and verified through
the API. A PR must now be up to date with its base before it can merge. Left unedited in that file
deliberately — rewriting another session's tracker entry from outside its context is how two records
start disagreeing — so trust this line over that one.

## 8. Definition of done for the sprint

From [`README.md`](README.md) and the tickets, in one place:

- Images are built once in CI and pulled by the hosts — no host builds the Next.js image on a 4 GB box
- A deploy cannot take staging off the network for 40 minutes (QA-01's actual incident, `GRM-008`)
- Playwright runs against a seeded stack and covers all 22 officer-UI routes
- The e2e job runs in CI and is a required check
- **HR-07's manual sweep is retired** — or the parts still manual are named, with the reason
- Every deferral logged in `followups/` **and** [`../../SPINE.md`](../../SPINE.md), same commit

**Do not merge to `integration/stage` until the sprint is complete.** That is the owner's practice and
it is why this branch exists.
