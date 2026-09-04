# DESIGN — The review feedback loop (widget → issue → triage)

> **Status:** Proposed, **2026-09-04**, branch `integration/stage`. **Not an approved sprint. No code
> written.** Tier 3 per [`engineering/06_documentation_lifecycle.md`](../../engineering/06_documentation_lifecycle.md) §1.
> **Method:** every claim was checked in the tree; file paths are cited rather than recalled.
> **Sibling sprint:** [`../2026-09_qa_automation/DESIGN-qa-and-build-pipeline.md`](../2026-09_qa_automation/DESIGN-qa-and-build-pipeline.md) —
> the build pipeline and browser verification, split out of this evaluation on 2026-09-04 because it
> is larger, more foundational, and **valuable whether or not any of this ships**.

The idea, as put: **a per-page feedback tool in the staging (review) app** — a chatbot/notifier-style
widget that lets a reviewer leave a comment *in context*, attach a screenshot / sketch / drawing, plain
or annotated, and have it become a ticket for review and fix; then **an agent** that judges the
ticket's complexity and either applies the change or routes it for review.

---

## 1. Verdict

| | Verdict | Size |
|---|---|---|
| **The widget** — in-context comment + annotated screenshot → issue | ✅ **Feasible, and cheaper than it looks.** One mount point, one router, one sink; zero new runtime dependencies. Its only blocker — PII in screenshots — is answered by holding **synthetic-only data on staging** (§2.4). | **3–4 d** + ½ d |
| **Triage agent** — labels, duplicates, reads the screenshot, writes a reproduction, proposes the fix *as text* | ✅ **Feasible, and the best value on this page.** It writes no code, so it has no blast radius, and it is most of the win. | **3–5 d** |
| **Agent applies the fix** | ⏸ **Deferred, not rejected — it depends on the QA sprint.** A sandbox is cheap; knowing the fix worked is not. Nothing in this repo can look at a page (§3.3). | after QA |
| **Agent applies + deploys on *staging*, unattended** | 🔴 **Not recommended, for reasons unrelated to data or sandboxes.** `integration/stage` is the branch promoted to `main`, and the box is production's configuration source (§3.2). | — |

**The finding that shaped the split:** part 1's hard problem was never the widget, it was the
screenshot — an image of the officer UI carries complainant PII no redactor in this repo can touch.
That is closed by keeping staging synthetic (§2.4). Part 2's hard problem is not *where the agent
writes* — it is *how it knows the change was right*, and that turned out to be a whole sprint of its
own, now sitting in [`2026-09_qa_automation/`](../2026-09_qa_automation/).

---

## 2. The widget

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
most of the value thrown away. It moves the triage agent (§3) from "classify the text" to "look at the
page and say what is wrong with it".
---

## 3. The agent

### 3.1 What is feasible now — triage, and it is most of the value

An agent that reads a new issue and writes back to it is unblocked today, needs no environment, and
carries no risk because **it writes no code**:

- classify (copy / layout / data / needs a product decision) and label;
- detect duplicates against open issues;
- **open the screenshot** — possible only because staging is synthetic (§2.4);
- turn "this looks wrong" into a reproduction: route, role, seeded ticket id, steps;
- name the file and the likely fix in a comment, for a human to accept or discard.

The one design rule: **an agent must not author the `PROGRESS.md` entry that certifies its own
change**, and its commits carry a trailer naming the run and the issue, so agent-authored work stays
greppable. This repo's discipline is evidence-based ([`sprints/README.md`](../README.md) standing
deferral rule); an agent that writes its own report card erodes exactly that.

### 3.2 Why *staging* is not where an agent may apply changes

| The assumption | What is actually true here |
|---|---|
| Staging is a sandbox | `integration/stage` is the **branch promoted to `main`**, and `main` is what DOR production runs. |
| Staging data is disposable | True for **grievance rows** once §2.4 lands; false for everything else — `prod-sync-db-from-aws` replaces production's Postgres, **Keycloak realm** and uploads volume **from this box**. The configuration is not disposable; it is production's source. |
| Breaking staging costs nothing | Staging **is** the review environment. Breaking it blocks the reviewers whose feedback started the loop. |
| CI will catch a bad change | CI runs, but **branch protection was never enabled** — still an open manual item ([`2026-07_hardening/PROGRESS.md`](../2026-07_hardening/PROGRESS.md)). A red-CI push to `integration/stage` is noticed, not blocked. **Ten minutes of repo-admin work, worth doing regardless.** |

A sandbox below staging answers rows 1–3 cheaply. Row 4 should be fixed on its own account.

### 3.3 Why "agent applies the fix" waits for the QA sprint

**A sandbox gives the agent somewhere safe to apply a change. It gives it no way to know the change
was correct.** There is no browser automation in this repository, and the gates that exist prove a UI
change *compiles*, not that it looks right — which is exactly the class of ticket this widget produces.
An agent applying a visual fix it cannot see the result of is guessing, and a sandbox only makes
guessing cheap.

⚠ **And the sandbox itself cannot go where it would have been cheapest.** Incident `2431da51`
(2026-09-04) measured the staging host at **3825 MB, no swap, 14 containers, 96 MB free at failure** —
a single Next.js build livelocked it for 41 minutes. A second stack there is not a sizing question.

Both of those — a browser that can look, and images that can run anywhere without building on a
3.8 GB box — are [the QA sprint](../2026-09_qa_automation/DESIGN-qa-and-build-pipeline.md). When it
lands, this phase becomes: agent branches → patches → applies in an ephemeral stack → **attaches the
reviewer's original screenshot next to its own post-fix screenshot** on the PR → a human merges by
*looking*, not by re-testing.

---

## 4. Phasing for this sprint

| Phase | Work | Est. | Gate to the next |
|---|---|---|---|
| **0** | Decide **D1** (issue sink). Land the **synthetic-staging invariant** — seed-only policy, inverted scrub, `ops` assertion check (§2.4). Enable branch protection. | ½–1 d | The assertion check reports `ok` on staging |
| **1** | Widget + endpoint + GitHub issue sink, staging-only build, annotator with a blur tool, E14 row added to the egress inventory stating the synthetic-data precondition. | 3–4 d | Reviewers actually use it |
| **2** | Triage-only agent (§3.1). No code written by it. | 3–5 d | Its proposed fixes are right often enough to be worth applying |
| **3** | *Blocked on the QA sprint* — agent patches in an ephemeral stack, before/after screenshots on the PR, human merges. | later | QA-04 + QA-02 landed |

**Total for this sprint: 7–10 days**, phases 0–2.

## 5. Decisions needed before phase 1

| # | Decision | Recommendation |
|---|---|---|
| **D1** | Where the ticket lives | **GitHub Issues** — no schema, no migration, no fourth Alembic stream, and it is where the triage agent reads from (§2.3). ⚠ **Verified 2026-09-04: `philgaeng/chatbot_ssh` is a PUBLIC repository**, so issues and any attached screenshot are **world-readable**. That is defensible only because §2.4 makes staging synthetic — but it is a decision, not a detail: reviewer comments ("this is confusing", "wrong for DOR") also become public. **Confirm, or pick a private tracker.** |
| **D2** | How the screenshot is captured | **Clipboard paste / `getDisplayMedia()` + a `<canvas>` annotator.** No library (§2.3) |
| **D3** | PII posture | **Synthetic-only staging**, enforced by an `ops` check rather than a one-time truncate (§2.4) — ✅ *decided 2026-09-04* |
| **D4** | Does the widget ship to production? | **No** — compiled out by build flag, same pattern as `AUTH_BYPASS` |
