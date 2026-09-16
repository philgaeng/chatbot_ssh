# Agent runbook — OC-06: Admin-setup UX/UI evaluation

**Branch:** `orgchart/oc-06-ux-eval` off `integration/seah-claude` · **Model:** Opus (high effort — holistic cross-tab UX + permission audit) · **Spec:** [`../05-admin-setup-ux-evaluation.md`](../05-admin-setup-ux-evaluation.md) · Read [`README.md`](README.md) common rules first. **Run first — it shapes OC-05.** Doc-and-screenshots only, zero code.

## Mission

Evaluate the whole setup journey a Government of Nepal admin actually walks — **organizations → officers → workflows → projects** — as one flow, not four tabs. Produce a published, evidence-grounded evaluation that (a) ranks the friction for a low-IT-literacy user, (b) doubles as a persona/permission audit, and (c) verdicts whether the org-chart feature (OC-01..05) truly makes officer setup *one comprehensible action* before we build the UI.

## Steps

1. **Stand up the stack** (`docs/deployment/DOCKER.md`, bypass-auth mode) with seeded data. Confirm you can switch admin personas: `super_admin`, `org_admin` (standard), `org_admin` (seah), `project_admin`.
2. **Cold-start walk.** As each persona, do a full setup: build an org (tree if OC-01 merged, else flat), invite/staff officers with role+scope, configure a workflow + role bindings, create and go-live a project. Screenshot every screen and every dead-end. Live the clicks — do not evaluate from source alone.
3. **Map the journey** end-to-end: every screen, required field, inter-tab navigation jump, and every point where the admin must carry a value from a previous tab in their head (org id, role key, location code). Mark those hand-offs — they are the usual failure points for non-technical users.
4. **Score each journey** on discoverability, guidance/empty-states, error prevention (can they create an orphaned/invalid state?), reversibility, and Nepali readiness. Ground every finding in `file:line` or a screenshot.
5. **Permission audit:** verify each admin tier sees exactly the surface doc 11 (admin ladder) and doc 16 §7 grant. Any over- or under-exposed tab/action is both a UX and a security finding — flag prominently.
6. **Cross-reference structural risks:** the 4,717-line `app/settings/page.tsx`; the inconsistency between inline tabs (`WorkflowsTab` `page.tsx:1904`, `RolesTab` `:397`, `AdminAccessTab` `:548`) and the extracted `components/settings/*`; location-code dialects (specs review §2.4).
7. **Write the deliverable** `docs/ticketing_system/ui/03_admin_setup_flow_evaluation.md`: journey map, scored findings table (`id | journey | severity | finding | evidence | recommendation | owner`), top-5 low-IT-literacy friction points, orphaned-state catalogue (noting which OC-01..04 validations already close each), Nepali/i18n readiness note, and the "does org-chart actually help?" verdict.
8. **Feed forward:** file each blocker/major as an OC-05 acceptance item or a new backlog ticket in [`../PROGRESS.md`](../PROGRESS.md). If the invite pre-fill design looks like it won't simplify the flow, **say so before OC-05 starts.**

## Constraints

- No code changes — documentation and screenshots only.
- Evaluate the **as-built** state (+ any merged OC-01..04). Spec-vs-built disagreements are themselves findings.
- Adversarial house style (see `docs/reviews/devils_advocate_*`): real friction ranked by user impact, strengths stated so criticism stays credible.

## Done means

`03_admin_setup_flow_evaluation.md` published; findings table complete with evidence + owners; blockers/majors triaged into OC-05 or backlog in PROGRESS; org-chart verdict recorded **before** OC-05 begins.
