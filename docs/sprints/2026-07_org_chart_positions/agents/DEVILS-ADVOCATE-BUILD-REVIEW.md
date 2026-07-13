# Devil's-advocate build review — Settings redesign & org-chart (as-built)

> **Purpose.** Re-run the adversarial review that closed the design phase (48 → **84/74**, [`DESIGN-REVIEW.md`](../DESIGN-REVIEW.md)), now against the **as-built code**, not the spec. Same method, same axes/lenses/severity, upgraded with a **fidelity/correctness** axis and a **full adversarial backend pass**.
> **Under review:** everything shipped in the `2026-07_org_chart_positions` sprint — see the manifest in §6. Read [`SPRINT-SUMMARY.md`](../SPRINT-SUMMARY.md) first for the as-built map + the deliberately-deferred list.

---

## 1. Method (inherited from the design-phase run)

- **Independent adversarial agents, cold read.** No reviewer may have produced the code under review. Each owns an **axis × scope** and reads against the source of record, not the summary docs.
- **Evidence discipline.** Every finding cites a concrete `file:line` / `route` / `commit` / **wireframe frame·pin** / **atlas surface** / `doc §`, plus a one-line **repro or spec-conflict**. No finding without a citation.
- **Verify against the code, not the claim.** The design round-2 caught an "overstated remediation" by re-reading the files. Do the same: a passing test is *evidence*, not *proof* — read the assertion, then try the path it *doesn't* cover. PROGRESS/SPRINT-SUMMARY claims are hypotheses to falsify.
- **Score, don't just list.** Each axis gets a %; regressions vs. the design-phase 84/74 are themselves findings.

## 2. Scoring axes

| Axis | Build-phase question | Baseline |
|---|---|---|
| **Completeness** | Is each spec'd surface actually **built + reachable**, or stubbed/dropped? Are the [`SPRINT-SUMMARY.md`](../SPRINT-SUMMARY.md) deferrals **justified** or a silently-cut in-scope requirement? Does every concept still have a data home end-to-end (UI → wrapper → route → model)? | design 84% |
| **Ease of use** | The A–F/§7.C lenses on the **rendered** components: labels-not-slugs actually applied (`lib/labels.ts`), `ErrorNotice` wired (no raw `API 4xx` strings), no banned hues, `<Bilingual>` on `_name` fields, text-severity-beside-colour, first-run/"next step" anchoring, conceptual load. | design 74% |
| **Fidelity & correctness** *(new — the design review couldn't test this)* | Does each component match its **wireframe frame + §4 interaction rule**? Real bugs: broken handlers, wrong API request/response shape, missing loading/empty/error state, races, stale state after mutation, unguarded 4xx. Does built **authz/SEAH** behaviour match the spec's claim? | new |

## 3. The lenses (sweep every one)

**Inherited A–F** (from `DESIGN-REVIEW.md`), now on the build:

- **A — Day-one / first-run.** Empty-system anchoring; is the go-live spine present and does it name the next step? (Frame 01, §7.A)
- **B — Creation / authoring.** Workflow SLA + escalation target, project+package create, workflow→project link, clone-a-template, org/position create. Built and wired? (Frames 04/05/10, §7.B)
- **C — Jargon on screen.** No code identifiers / math symbols / slugs in product UI; the `lib/labels.ts` plain-language contract actually applied *everywhere* (not just the RB-2 worst-offenders). (§7.C)
- **D — Bilingual chrome.** `<Bilingual>` on data `_name`/`display_name_ne`; EN fallback + "Nepali name needed"; never a fabricated Nepali string. (RB-1, §D4)
- **E — Self-inflicted inconsistency.** Vocabulary drift ("Handler" vs "Handles it"), cross-component mismatch, **spec self-contradiction**, stale `country_admin` anywhere, atlas/state coverage of the built states.
- **F — Lifecycle & scale.** Officer transfer/deactivate/reactivate with **open-case handling**, org delete/re-parent/merge, directory + tree **at ~5,000 staff** (client-filter vs server-search), SEAH setup + **invisibility** (case existence hidden, people visible — doc 16 §6), admin revoke/bootstrap/orphan-rehome.

**Build-specific G–I** (new; where code review earns its keep):

- **G — Correctness / bugs.** Trace each flow for real defects: wrong wrapper shape vs. the route's Pydantic model; missing `await`; unhandled promise; state not refetched after a mutation; a 409/422 that reaches the user as a raw string; an off-by-one/empty-list/null-field crash. Give inputs → wrong output.
- **H — Security / authz / SEAH-leak** *(adversarial — try to break it)*. The admin ladder (super/org/project/officer_admin, subtree scope): find a persona × endpoint that should be 403 but isn't, or vice-versa. The **SEAH leak vector**: can a donor (or any non-SEAH role) be cast/notified on a SEAH ticket via any path — the escalation cast, the informed/observer tiers, the supervisor-notify, the roster, the org chart? The **donor guardrail**: can go-live activate with a donor present but not informed, or on the SEAH track? The **open-case guard** and **enrich_user** deactivation choke point: any bypass?
- **I — Data-integrity / migrations.** The 6 new migrations (`m3o5q7s9`→`w3y5a7c9`): each has the safety header + a real `downgrade()`; the chain is **linear/single-head**; no PII in `ticketing.*`; no `ticketing.*`→`public.*` FK/join; the **expand-phase** back-compat (routing reads `implementing_agency_org_id` *and* the legacy `org_role`) is consistent; back-fills are correct; delete guards don't orphan rows.

**Severity:** `BLOCKER` · `MAJOR` / `SEVERE-UX` · `MODERATE` · `MINOR`, with a **correctness** flag for logic that is wrong (not merely rough) — SEAH-invisibility, authz, guardrail, data-integrity.

## 4. Scope, weighting, and agent assignment

**Full adversarial pass on both frontend and backend.** The backend is *not* claim-verified — it is attacked (passing tests are a starting point to find the untested path). Frontend carries the higher *unknown* risk (browser-untested), so it gets more reviewers; backend carries the higher *blast-radius* risk (authz/SEAH/data), so it gets a dedicated adversary who assumes the tests are insufficient.

| Agent | Owns | Primary axis · lenses |
|---|---|---|
| **FE-1** | Organisation surfaces — `components/settings/org/*` (OrgTree, OrgTreeNode, OrgEditor, OrgCsvImport, PositionTypesPanel, PositionTypeEditor, ReviewHoldersModal) | Fidelity+EoU · A/C/D/E/F/G, frames 02/06/12 |
| **FE-2** | Officers + Projects — `officers-v2/*` (invite-as-result + directory/lifecycle) + `projects/ProjectParticipants` | Fidelity+EoU · A/B/C/F/G, frames 03/11/05/10 |
| **FE-3** | Cross-cut — the RB-2 **contract** (`lib/{trackFilter,labels,design-tokens}`, `components/shared/*`), the `page.tsx` **integration shell + still-inline Workflows/Platform clusters**, SEAH visual, `lib/api.ts` wrapper↔route fidelity | EoU+Completeness · C/D/E/H(client), frames 04/08/09/01/13 + §7.C/E |
| **BE-1** | **Backend adversary** — routing, go-live A5/C5, donor guardrail + SEAH suppression, escalation cast, officer lifecycle + enrich_user, admin ladder/subtree scope | Correctness+Security · G/H/I (break it) |
| **BE-2** | **Data-integrity + completeness** — the 6 migrations + expand-phase consistency; then a completeness sweep: spec'd-but-missing/stubbed surfaces + the **deferred-list verdict** | Completeness+Integrity · E/F/I |

Two independent agents may share an axis to cross-check (the design method ran one-per-axis; here a second opinion on H/SEAH and on Completeness is worth the redundancy).

## 5. Deliverables

1. **Per-agent scorecard** — the axis %, movement vs. design 84/74 (with regressions called out), and a 1-paragraph verdict.
2. **Findings table** — severity-ranked, each row: `severity · lens · file:line/route/frame · one-line defect · repro-or-spec-conflict · suggested fix`. Confirmed defects only (re-read to confirm before filing).
3. **Deferred-list verdict** — for each `SPRINT-SUMMARY.md` deferral: *justified* / *should-have-been-in-scope (BLOCKER)* + why.
4. **Consolidated top-N** — the merged, de-duplicated, severity-ordered punch list that becomes the fix backlog.

## 6. Under review (manifest)

- **Sprint commits:** `06d96266` (doc-13+§5.6) · `f1dda901` (RB-0+RB-2 foundation) · `ad1ee1aa` (backend pre-req) · `b6fc2e63` (client pre-req + country_admin fix) · `ec5d8dcd` (Frame-11/12 gaps) · `af95c321` (frontend integration) · `460e2112` (sprint close); plus the earlier SH-1..7 / OC-01..04 / RB-1 commits in [`PROGRESS.md`](../PROGRESS.md).
- **Source of record to review against:** [`DESIGN-settings-redesign.md`](../DESIGN-settings-redesign.md) §3/§4/§7 · [`settings-wireframes.html`](../settings-wireframes.html) (13 frames, pins 1–56) · [`settings-state-atlas.html`](../settings-state-atlas.html) (14 surfaces) · [`DECISION-project-participants-and-supervision.md`](../DECISION-project-participants-and-supervision.md) · doc 11 / 13 / 16 · the RB-0 build sheets in [`build-sheets/`](build-sheets/) · [`SPRINT-SUMMARY.md`](../SPRINT-SUMMARY.md) + [`PROGRESS.md`](../PROGRESS.md).
- **How to run the code:** backend tests `make wsl-seed-full` then `make test-ticketing` (Docker); frontend `cd channels/ticketing-ui && npx tsc --noEmit` + the `grm_ui` image build. **Not browser-tested** — reviewers reason about rendered behaviour from the source + wireframes.

> **Standing rule:** file everything as evidence-cited findings; do not "fix while reviewing." The output is the punch list; remediation is a separate pass (mirrors the design phase's review → HANDOVER cycle).
