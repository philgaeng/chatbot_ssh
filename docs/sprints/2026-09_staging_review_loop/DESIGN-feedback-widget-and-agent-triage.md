# DESIGN — In-context feedback on staging, and agent triage on top of it

> **Status:** Feasibility evaluation, **2026-09-04**, branch `integration/stage`. **Not an approved
> sprint. No code written.** Tier 3 per [`engineering/06_documentation_lifecycle.md`](../../engineering/06_documentation_lifecycle.md) §1 —
> authoritative for nothing until a sprint opens against it.
> **Method:** every claim below was checked in the tree; file paths are cited rather than recalled.

Two ideas were put forward:

1. **A per-page feedback tool in the staging (review) app** — a chatbot/notifier-style widget that lets
   a reviewer leave a comment *in context*, attach a screenshot / sketch / drawing, plain or annotated,
   and have that become a ticket for review and fix.
2. **An agent on top of it** — when a ticket is created, an agent judges its complexity and either
   applies the change on staging automatically or routes it for human review, *"since staging changes
   can be made safely."*

---

## 1. Verdict

| | Verdict | Size |
|---|---|---|
| **Part 1 — the widget** | ✅ **Feasible, and cheaper than it looks.** One mount point, one router, one sink. Zero new runtime dependencies if annotation is built on clipboard-paste + `<canvas>` instead of a screenshot library. Its one blocker — PII in screenshots — is **answered by holding synthetic-only data on staging** (§2.4). | **3–4 days** + ½ d |
| **Part 2 — agent triage → PR** | ✅ **Feasible in its PR-drafting form** — agent classifies, opens a branch, CI gates it, a human merges. | **3–5 days**, after part 1 |
| **Part 2 — agent applies + verifies in a sandbox, *before* staging** | 🟡 **Feasible — and the sandbox is the cheap half.** A pre-staging tier removes every blast-radius objection at once, and the repo can already build the whole stack from nothing. The cost is **not** the environment: it is that **nothing in this tree can tell the agent its UI fix worked** (§3.6). | sandbox **2–3 d** · verification **is the real cost** |
| **Part 2 — agent applies directly on *staging*, unattended** | 🔴 **Still not recommended, for reasons unrelated to the sandbox.** `integration/stage` is the branch promoted to `main`, the box is production's configuration source, and it is the environment the reviewers are reviewing in (§3.2). | — |

Two findings shape everything below, and **neither is about the agent**:

- **Part 1's hard part was never the widget, it was the screenshot** — an image of the officer UI
  carries complainant PII no redactor in this repo can touch. Closed by keeping staging synthetic
  rather than by redacting images (§2.4), which also unlocks the better triage agent: one that may
  look at the picture.
- **Part 2's hard part is not "where does the agent write" — a sandbox answers that cheaply. It is
  "how does the agent know it worked."** This project has **no browser automation of any kind**, and
  the tickets a feedback widget produces are overwhelmingly visual. `tsc`, `eslint`, `next build` and
  897 backend tests cannot see a misaligned button (§3.6).

---

## 2. Part 1 — the in-context feedback widget

### 2.1 What already exists (so does not need building)

| Need | Already there | Where |
|---|---|---|
| **One place to mount a global widget** | `AppShell` wraps every route from the root layout | [`AppShell.tsx`](../../../channels/ticketing-ui/components/AppShell.tsx), [`app/layout.tsx:38`](../../../channels/ticketing-ui/app/layout.tsx) |
| **Page/tab context for the comment** | `usePathname()` is already imported in the shell; desktop nav + mobile tabs are declared tables (`NAV`, `MOBILE_TABS`) | `AppShell.tsx` |
| **Reviewer identity** | `useAuth()` (Keycloak `sub`/name), or the `grm_bypass_user` cookie in a bypass build | `app/providers/AuthProvider`, [`lib/auth/runtime-config.ts`](../../../channels/ticketing-ui/lib/auth/runtime-config.ts) |
| **Transport to the API, no CORS** | Catch-all proxy `/api/v1/*` → `TICKETING_API_URL`, resolved at request time | [`app/api/v1/[...path]/route.ts`](../../../channels/ticketing-ui/app/api/v1) |
| **Multipart upload + persistent storage** | `POST /tickets/{id}/attachments` with `UploadFile`; `uploads_data:/app/uploads` is mounted on `ticketing_api` | [`routers/tickets/files.py`](../../../ticketing/api/routers/tickets/files.py), [`docker-compose.grm.yml:136`](../../../docker-compose.grm.yml) |
| **A composer/notes UI vocabulary to copy** | `ComposeBar`, `NoteBubble`, `NotificationBell` | [`components/thread/`](../../../channels/ticketing-ui/components/thread) |

### 2.2 What has to be built

| Piece | Shape | Est. |
|---|---|---|
| `FeedbackWidget` (floating button → panel) | Client component mounted once in `AppShell`, gated on a build flag | 1 d |
| Screenshot + annotation | Clipboard paste (`onPaste` → `File`) or `getDisplayMedia()`, drawn to a `<canvas>` with rect/arrow/blur tools, exported as PNG blob | 1–1.5 d |
| `POST /api/v1/review-feedback` | New router; multipart (text, page path, route, viewport, user agent, reviewer, image) | 0.5 d |
| Sink → a ticket | GitHub Issues via REST, server-side token (see D1) | 0.5 d |
| Staging-only gate + docs + tests | Build-arg flag, a router test, a `docs/deployment/` note | 0.5 d |

### 2.3 The three decisions that shape it

**D1 — Where does the "ticket" live? → Recommend GitHub Issues, not `ticketing.tickets`.**
`ticketing.tickets` is the grievance domain, not a task tracker: `grievance_id`, `organization_id`
and `current_workflow_id` are all `nullable=False` ([`models/ticket.py:53,65,81`](../../../ticketing/models/ticket.py)),
and every row is swept by the SLA watchdog, the queue tile counts and the quarterly XLSX. A UI-bug
row would be a fake grievance in a government GRM's own reporting. The alternative — a table in
`ops.*` — is more work than it looks: `ops` has **no HTTP surface** (it is an APScheduler process,
`python -m ops.scheduler`), and having `ticketing` write `ops.*` breaks the three-stream ownership
rule in [`CLAUDE.md`](../../../CLAUDE.md) / [`deployment/07_migrations_policy.md`](../../deployment/07_migrations_policy.md).
**GitHub Issues costs no schema, no migration and no new stream, and it is where part 2 wants to read
from anyway.** The image goes to the uploads volume; the issue links to it.

**D2 — How is the screenshot captured? → Clipboard paste + a `<canvas>` overlay. No library.**
The UI has **four runtime dependencies** (`next`, `react`, `react-dom`, `lucide-react`) and a nightly
licence classifier that dispositions every new one ([`ops/licences.py`](../../../ops/licences.py), DPG
indicator 2). `html2canvas` is MIT and would pass, but it *re-renders the DOM* rather than capturing
the screen — it disagrees with the real page on exactly the CSS a reviewer is complaining about.
Native `getDisplayMedia()` (staging is TLS) is higher fidelity and free. Annotation is ~200 lines of
canvas.

**D3 — Does the widget ship to production? → No. Compile it out.**
Same pattern as `AUTH_BYPASS`: a `NEXT_PUBLIC_*` build flag read in one module, so the widget is
absent from a production build rather than hidden in it.

### 2.4 The PII question, and the answer given to it (2026-09-04)

A screenshot of a ticket page contains the complainant's name, the raw `grievance_description`
(read live on every ticket view), and possibly the revealed phone. This project maintains an explicit
[PII egress inventory](../../dpg/pii-egress-inventory.md); the closest analogue — **E9, the uploads
volume (voice, photos)** — is marked *"unchanged, and **unclosable**"*, because images are not redactable.

**The decision taken is to remove the PII from staging rather than to redact the screenshots** —
staging holds truncated / synthetic data only. This is the right answer, and it is **less of a change
than it sounds**, because the convention it needs already exists:

- `ticketing/seed/mock_tickets.py` already authors the synthetic corpus under the reserved
  `GRV-2025-*` / `CPL-2025-*` ID space.
- [`scripts/ops/prod_sync_remove_mock_data.sql`](../../../scripts/ops/prod_sync_remove_mock_data.sql)
  already deletes exactly that ID space across 12 tables in both schemas.

So the invariant is the **inversion of a rule the repo already enforces**: today "everything with the
mock prefix is deleted on the way to prod"; the addition is "on staging, **nothing without it may
exist**". Three cheap pieces, ~½ day total:

| Piece | Shape |
|---|---|
| **Policy** | Staging grievance data comes from the seeder only. Real narratives never authored there. |
| **Scrub** | The existing SQL, inverted — delete where the ID does *not* match the reserved prefix. |
| **Assertion** | A twelfth `ops` check next to the existing eleven: count rows outside the prefix, `_emit(... CRIT)` if non-zero. ~15 lines in [`ops/checks.py`](../../../ops/checks.py), and it alerts through the existing deduped alert path. |

The assertion is the part that matters. **Staging is a live intake endpoint**, so this is a property
that drifts rather than a state you reach: one UAT session with a real phone number for OTP, one
restore, and it is quietly false again. A one-time truncate is not the control; the check is.

⚠ **Two residuals this does *not* cover — worth knowing, not blocking:**

1. **Staff identities stay real, by design.** The staging→prod sync copies **`public` + `ticketing` +
   `keycloak` + the uploads volume** and removes only the `GRV-`/`CPL-` prefixed rows
   ([`aws_to_prod_db_sync.sh:2`](../../../scripts/ops/aws_to_prod_db_sync.sh)) — because staging is where
   production's realm, org chart and officer roster are *authored*. So the officer names and emails on
   staging are the real ones, and they appear in any screenshot of settings/users, the cast editor, the
   roster, or a ticket thread. Materially lower stakes than a complainant narrative — a grievant in a
   GRM is a person alleging harm and carries retaliation risk; a staff name on an org chart does not —
   but it means the claim is "no complainant PII in screenshots", not "no personal data".
2. **The uploads volume is synthetic only if the seeder puts synthetic files there.** Voice notes and
   photographs attached during a UAT session are real recordings of real voices, and the prefix scrub
   deletes rows, not files.

**What this buys, beyond unblocking the widget:** with staging synthetic, **a model may read the
screenshot**. That is not a footnote — a visual bug report whose image the triage agent cannot open is
most of the value thrown away. It moves phase 2 from "classify the text" to "look at the page and say
what is wrong with it".

---

## 3. Part 2 — the agent

### 3.1 What genuinely makes this plausible here

- **The safety net already exists.** CI runs five gates — 172 backend test files against a real
  Postgres with all three Alembic streams, plus `tsc --noEmit` / `eslint` / `next build` for the UI
  ([`.github/workflows/ci.yml`](../../../.github/workflows/ci.yml)). An agent's patch would be judged
  by a harness the project already trusts, and the push triggers already include `integration/**`.
- **The deploy is already scripted and idempotent** — `make aws-deploy` does fetch → checkout
  `integration/stage` → rebuild the named services → run all three migration streams
  ([`Makefile`](../../../Makefile), `REMOTE_DEPLOY_CORE`).
- **Triage is the easy half.** Classifying "copy tweak / CSS / needs a product decision", detecting
  duplicates, and writing a reproduction from the page path + screenshot is well within reach and
  carries almost no risk, because it writes labels, not code.

### 3.2 Why *staging* cannot be the sandbox (and therefore why a tier below it is the answer)

| The assumption | What is actually true here |
|---|---|
| Staging is a sandbox | `integration/stage` is the **branch that is promoted to `main`**, and `main` is what DOR production runs. An agent committing to staging is committing to the thing that becomes production. |
| Staging data is disposable | True for **grievance rows** once §2.4 lands — and false for everything else on the box: `prod-sync-db-from-aws` **replaces production's Postgres, Keycloak realm and uploads volume from here**. The configuration is not disposable; it is production's source. |
| Breaking staging costs nothing | Staging **is the review environment**. Breaking it blocks the very reviewers whose feedback started the loop. |
| CI will catch a bad change | CI runs, but **branch protection was never enabled** — it is still an open manual item in the hardening sprint ([`2026-07_hardening/PROGRESS.md:61`](../../sprints/2026-07_hardening/PROGRESS.md)): *"require `backend-tests`, `ui-checks`, `docs-links` as required checks … Not performed by this agent."* Today a push to `integration/stage` with red CI is merely *noticed*, not *blocked*. |

None of these is fatal — they are the reason the agent needs **its own environment below staging**,
which is what §3.6 prices. Note that a sandbox neutralises rows 1–3 outright, and row 4 remains worth
fixing on its own account: **enabling branch protection is a ten-minute repo-admin action** that is
worth doing whether or not any of this gets built.

### 3.3 What is missing infrastructurally

**No runner in this project holds deploy credentials.** CI's only secret is `HF_TOKEN`. Deploys are
push-from-laptop over SSH (Tailscale-reachable box). So "an agent applies the change on staging"
requires a new privileged identity — either a CI job holding an SSH/Tailscale key, or a runner on the
staging host with repo-write. That host also runs the grievance database and Keycloak, so that
identity would immediately be **the most privileged principal in the project**, created to fix CSS.

Also worth knowing before scoping a "just change the copy" whitelist: **UI copy is not centralised**.
`lib/i18n/messages.ts` is 73 lines of scaffolding by design (Nepali is translator-gated); the strings
a reviewer will complain about are inline literals spread across ~172 TS/TSX files (~35.6k lines).
There is no cleanly isolated low-risk file set to whitelist today.

### 3.4 The shape that is feasible

```
widget → GitHub issue → agent triage (labels, dupes, reads the screenshot, repro)   ← build first
                              │
                              └─▶ agent branches + patches, applies in the SANDBOX   ← §3.6
                                        │
                                  verify: CI gates  +  headless browser screenshot
                                        │            (the missing capability)
                                        └─▶ PR carries: reviewer's shot | agent's shot | diff
                                                  │
                                            human merges ─▶ integration/stage ─▶ make aws-deploy
```

The sandbox moves the agent's writes off the promotion branch, so "unattended" becomes a statement
about the **sandbox**, not about staging. Promotion out of the sandbox stays a human merge — and that
is not a concession, it is where the reviewer sees the before/after pair and closes their own ticket.

### 3.5 Two costs that are easy to forget

- **Agent commits must stay greppable.** This repo's discipline is evidence-based — `PROGRESS.md`
  updated per commit, the standing deferral-logging rule ([`sprints/README.md`](../../sprints/README.md)).
  Agent commits need a trailer identifying the run and the issue, and **an agent must not author the
  PROGRESS entry that certifies its own change**.
- **A wrong auto-fix is more expensive than no fix**, because it consumes the reviewer's trust in the
  loop that produced it. Triage-only has no such failure mode.

### 3.6 The sandbox tier — what it actually costs

The proposal is a fourth environment **below** staging, so the ladder becomes:

| Tier | Branch | Data | Who may write | Purpose |
|---|---|---|---|---|
| **sandbox** *(new)* | `sandbox/<issue>` | seeded, synthetic, thrown away | **the agent** | apply + verify a candidate fix |
| **staging** | `integration/stage` | synthetic (§2.4), but the **config** is production's source | humans (merge) | reviewers, UAT, demo |
| **production** | `main` | real | humans (promotion) | DOR |

**The environment itself is the cheap part — 2–3 days.** The repo can already build the whole stack
from nothing (`make wsl-up`, `make wsl-seed-full`, `mock_tickets.py`), which is precisely the property
a disposable environment needs and most projects lack. Three things are missing:

| Gap | Evidence | Work |
|---|---|---|
| **No compose project isolation** | `COMPOSE_PROJECT_NAME` appears **nowhere** in the Makefile, `env.local` or any compose file — a second stack on one host collides on container names, networks and volumes | ½ d |
| **Five host ports are hardcoded** | `5001`, `8000`, `5002`, `3001`, `8080:80` in [`docker-compose.grm.yml`](../../../docker-compose.grm.yml) / [`docker-compose.yml`](../../../docker-compose.yml), and [`check_grm_ports`](../../../Makefile) asserts `3001`/`5002` literally | ½ d |
| **~15 containers per stack** | base (9) + GRM overlay (6), including a second Postgres and a second Keycloak | sizing, below |

**Where it runs — the one open input.** Co-locating on the staging EC2 is cheapest but shares a host
with the environment reviewers depend on, so it needs headroom the sandbox can never eat.
⚠ **Not measured:** the box was unreachable at the time of writing (Tailscale `offline`, public IP
timing out on banner exchange), so RAM/CPU/disk headroom is unknown. Options, best-first once that is
known: **(a)** second compose project on the staging host — cheapest, needs the isolation work above and
a hard resource cap; **(b)** a small dedicated instance — clean, costs money; **(c)** ephemeral per-issue
stack, created and destroyed per run — the right end state, most orchestration; **(d)** the dev WSL box,
which already runs the full stack — free, but not always-on.

#### The gap the sandbox does *not* close, and it is the important one

**A sandbox gives the agent somewhere safe to apply a change. It does not give it any way to know the
change was correct.** There is **no browser automation anywhere in this repository** — no Playwright,
Puppeteer, Cypress or Selenium in any `package.json` or `requirements*.txt`. The gates that exist —
`tsc --noEmit`, `eslint`, `next build`, 897 backend tests — prove a UI change *compiles*. They cannot
see a button that now overlaps its label, which is exactly the class of ticket a screenshot-based
feedback widget produces. This is the same gap that leaves HR-07's browser sweep sitting as a
**pending-human** item a sprint later.

So the honest sequencing is: **the verification capability is the prerequisite, not the sandbox.**
An agent that applies a visual fix and cannot look at the result is guessing, and a sandbox makes
guessing cheap rather than making it correct. Concretely, the sandbox is worth building when it is
paired with: a headless browser that loads the changed page, drives the reported reproduction, and
captures a screenshot; the agent comparing that against the reviewer's original screenshot; and the
pair attached to the PR so the human merge is a *look*, not a re-test.

⭐ **That capability is worth having regardless of this feature** — it closes HR-07, it gives the
officer UI its first end-to-end coverage, and it turns "reviewers find visual regressions" into a
gate. If only one thing on this page gets built, this is the one with value independent of the agent.

---

## 4. Recommended phasing

| Phase | Work | Est. | Gate to the next phase |
|---|---|---|---|
| **0** | Decide **D1** (issue sink). Land the **synthetic-staging invariant** — seed-only policy, inverted scrub, `ops` assertion check (§2.4). Enable branch protection. | ½–1 d | The assertion check reports `ok` on staging |
| **1** | Widget + endpoint + GitHub issue sink, staging-only build, annotator with a blur tool (still wanted — staff names, §2.4 residual 1), E14 row added to the egress inventory stating the synthetic-data precondition. | 3–4 d | Reviewers actually use it |
| **2** | Triage-only agent: label, deduplicate, **read the screenshot**, write a reproduction, propose a fix **in the issue as text**. No code written. | 3–5 d | Its proposed fixes are right often enough to be worth applying |
| **3** | **Verification capability** — headless browser, loads a route, drives a reproduction, captures a screenshot. Closes HR-07 as a side effect. | 3–5 d | It catches a regression a human missed |
| **4** | **Sandbox tier** — `COMPOSE_PROJECT_NAME` + parameterised ports + a seeded, disposable stack (§3.6). | 2–3 d | Stands up and seeds from nothing, twice in a row |
| **5** | Agent branches, patches, applies in the sandbox, attaches before/after screenshots to a PR. Human merges. | later | Track record from phase 2 |
| **—** | Unattended apply + deploy **directly on staging**. | **not recommended** | Superseded by phases 3–5 — there is no reason to want it once a sandbox exists |

## 5. What would change the verdict

- **Synthetic-only staging data — decided 2026-09-04 (§2.4).** This closes the PII objection to part 1
  and lets the triage agent read screenshots. It does **not** close the auto-apply objection: that one
  is about `integration/stage` being the branch promoted to `main` and about the box being production's
  configuration source, neither of which is a statement about grievance rows.
- **A sandbox tier below staging — proposed 2026-09-04 (§3.6).** Its own compose project, off the
  promotion branch, *not* the box production syncs its Keycloak realm and uploads from. This closes the
  blast-radius objection to auto-apply, and it is genuinely cheap here (2–3 d) because the stack already
  builds and seeds from nothing.
- **⭐ What is then still missing, and is the actual gate: a way to verify a UI change.** With no browser
  automation in the tree, a sandbox lets an agent apply a visual fix it cannot see the result of.
  **Build the verification before the sandbox** — it is the item on this page with the clearest value
  even if the agent is never built.
- **Branch protection with required checks** turns "CI is the safety net" from a hope into an invariant.
