# Sprint — July 2026: Org Chart & Positions

> **Status: PLANNED** · Feature source: [`docs/ticketing_system/16_org_chart_and_positions.md`](../../ticketing_system/16_org_chart_and_positions.md) (Agreed design, not yet implemented)
> Runs **in parallel with** [`2026-07_hardening`](../2026-07_hardening/) — see [§ Parallel-safety](#parallel-safety-with-the-hardening-sprint) for the two coordinated seams.
> Goal: put the Nepal ministry org chart, position titles, and the position→role matrix into the system so setup admins stop minting one role per seat, and so officers appear as "SDE, Jhapa Division Office" instead of `site_safeguards_focal_person`.
> **Best-practice mandate:** this is new-feature work, so we build in the devil's-advocate lessons *from the first commit* rather than hardening them later — see [`agents/README.md`](agents/README.md) § "Best practices baked in".

## Why this sprint carries extra scrutiny

The feature creates **new admin endpoints on a government PII system** (`/position-types`, `/organizations/import`, `/users/{id}/positions`, `/users/{id}/supervisor`), it **generates `user_roles` + `officer_scopes`** from positions (permission-correctness), and its reporting-line behaviors must **never leak SEAH case existence** (spec §6). Those are precisely the three finding-classes the July 2026 codebase review flagged (ungated endpoints, authz correctness, SEAH-wall holes). Every runbook here therefore ships gated endpoints, an authz matrix, and SEAH-leak tests as **acceptance criteria, not follow-ups**.

## Tickets

| ID | Title | Area | Effort | Spec |
|---|---|---|---|---|
| OC-01 | Org tree: extend `ticketing.organizations` (parent, unit_type, territory, `display_name_ne`) + CSV import | ticketing schema + API | M | [01-org-tree-and-positions-spec.md](01-org-tree-and-positions-spec.md) §1 |
| OC-02 | `ticketing.position_types` + position→role matrix + `/position-types` CRUD | ticketing schema + API | M | [01-org-tree-and-positions-spec.md](01-org-tree-and-positions-spec.md) §2 |
| OC-03 | `ticketing.officer_positions` + invite pre-fill + supervisor resolver | ticketing API + services | L | [02-officer-positions-and-invite-spec.md](02-officer-positions-and-invite-spec.md) |
| OC-04 | Chart-driven behaviors (visibility, assignment ranking, escalation-notify) + SEAH leak-proofing | ticketing engine | L | [03-chart-behaviors-and-seah-spec.md](03-chart-behaviors-and-seah-spec.md) |
| OC-05 | Portal org-chart UI — **superseded**: paused and folded into the Settings rebuild (Handover B · RB-4) after the OC-06 pivot | ticketing-ui | L | [04-portal-org-chart-ui-spec.md](04-portal-org-chart-ui-spec.md) (historical) |
| OC-06 | Admin-setup UX/UI evaluation (org → officers → workflow → projects) — **done**, published `ui/03_admin_setup_flow_evaluation.md` | design/eval doc | M | [05-admin-setup-ux-evaluation.md](05-admin-setup-ux-evaluation.md) |

## ▶ Current state — design DONE, build launching

OC-06 ([published report](../../ticketing_system/ui/03_admin_setup_flow_evaluation.md)) triggered a full Settings redesign. The **design phase is complete** — 5 independent devil's-advocate review rounds took it from a 48% baseline to **84% completeness / 74% ease-of-use**, all design blockers closed.

- **▶ [BUILD-HANDOVER.md](BUILD-HANDOVER.md) — the single entry point to build.** Read this first: locked decisions, the two-phase plan (SH-1..7 + OC-01..04 backend; RB-1..4 frontend), sequencing, and DoD.
- **Design artifacts (live, the build consumes these):** [DESIGN-settings-redesign.md](DESIGN-settings-redesign.md) (source of record) · [settings-wireframes.html](settings-wireframes.html) (13 frames) · [settings-state-atlas.html](settings-state-atlas.html) (14 surfaces) · [DESIGN-REVIEW.md](DESIGN-REVIEW.md) (the 5-round scores).
- **Design-phase handovers — ARCHIVED** (history; superseded by BUILD-HANDOVER): [A — UX brief](archive/HANDOVER-A-settings-ux-redesign-brief.md) · [B — hardening & rebuild plan (full ticket bodies)](archive/HANDOVER-B-settings-hardening-and-rebuild-plan.md) · [C — admin-model finalize & cleanup](archive/HANDOVER-C-admin-model-finalize-and-cleanup.md).

Net: **OC-01..04 (backend) proceed**; **OC-05 (UI) folded into RB-4**; **SH-1..7 hardening + admin-scope** start now; **RB-1..4 frontend rebuild is unblocked** (the design gate is met).

## Execution order & workstreams

Four agent runbooks (in [`agents/`](agents/)). **OC-06 runs first** — its findings shape OC-05.

```
OC-06 UX evaluation      ← START FIRST (doc only). Grounds the UI work; no code.
OC-01 → OC-02            ← backend-org-tree runbook. Additive schema + CRUD; migrations serialize (see below).
OC-03 → OC-04            ← backend-positions runbook. Depends on OC-01/02 tables existing.
OC-05                    ← portal runbook. After OC-01..04 land AND after hardening HR-06 (shared settings file).
```

Dependency graph: OC-01 and OC-02 have no ordering constraint between them except **migration head serialization**; OC-03 needs both tables; OC-04 needs OC-03's `officer_positions`; OC-05 needs the whole backend and the UX eval.

## Parallel-safety with the hardening sprint

Verified against the code (July 2026). The two sprints are **almost entirely disjoint**; there are exactly **two seams to coordinate**:

| Seam | Hardening side | Org-chart side | Rule |
|---|---|---|---|
| **Alembic head `g0h2i4j6`** | HR-03 adds `uq_tickets_grievance_id_active` off the head | OC-01/02/03 each add a revision off the head | **Serialize.** Land HR-03 first; chain the org-chart revisions after it. If HR-03 hasn't landed, chain on the actual `alembic heads` output and coordinate rebase via PROGRESS. Never fork the chain. |
| **`app/settings/page.tsx`** (4,717 lines) | HR-06 moves hooks above an early return at ~4590, told to "touch nothing else" | OC-05 adds an org-chart settings section | **Sequence + isolate.** Build OC-05 as new `components/settings/*` components (the pattern already exists — 12 of them); keep the `page.tsx` change to a ~5-line tab-wiring diff; land after HR-06. This honors the review's "stop growing the god-file" finding. |

Everything else is disjoint: hardening's auth (`dependencies.py`, new `ticket_access.py`), escalation (`escalation.py`, `tickets.py`), and non-settings portal pages do **not** overlap the org-chart surface (`organizations` model + `locations.py` router, new position models, invite flow in `users.py`, `auto_assign_officer` in `workflow_engine.py`). `auto_assign_officer` and hardening's `escalation.py` are different files despite both being "the engine" — no collision.

## Conventions (binding for all agents)

- Branch per workstream off `integration/seah-claude`: `orgchart/oc-01-02-tree`, `orgchart/oc-03-04-positions`, `orgchart/oc-05-portal`, `orgchart/oc-06-ux-eval`.
- **Never touch `main`.** See CLAUDE.md git workflow.
- Every ticket ships **with its tests in the same commit** — including an **authz matrix** for every new endpoint and **SEAH-leak tests** for every reporting-line behavior. These are acceptance criteria.
- Migrations: ticketing stream only (`ticketing/migrations/`), safety header required, real `downgrade()`, chained deliberately on the live head (coordinate with HR-03).
- New UI = new `components/settings/*` components. **Do not add inline code to `app/settings/page.tsx`** beyond tab wiring.
- Nepali display names (`display_name_ne`) are **translator-gated** exactly like SEAH copy — never invent Nepali text; mark rows for the translator.
- Update [`PROGRESS.md`](PROGRESS.md) at every commit (status + checklist ticks + deviations).

## Model selection

All-Opus sprint (high reasoning effort). Rationale in [`agents/README.md`](agents/README.md) § "Model selection". Short version: new admin endpoints on a PII system + scope generation + SEAH-leak-proofing = correctness- and security-critical throughout. The only Sonnet-eligible slice is the pure presentational tree/table rendering in OC-05 if it is split from the invite-pre-fill logic. **No Fable** — the one prose surface (Nepali labels) is translator-gated.

## Definition of done (sprint level)

- [ ] All 6 tickets ✅ in PROGRESS.md with tests passing in CI
- [ ] CI green on the integration branch (uses the HR-05 gate once it lands)
- [ ] Authz matrix covers every new endpoint × persona; SEAH-leak suite green
- [ ] `docs/ticketing_system/16_org_chart_and_positions.md` status flipped from "Agreed design — not yet implemented" to as-built, citing the migrations/routers that prove it
- [ ] The four §10 open questions in doc 16 resolved and recorded (Nepali columns done; vacancy/SEAH-author/history decisions logged)
- [ ] OC-06 UX evaluation published under `docs/ticketing_system/ui/` and its actionable findings triaged into OC-05 or a backlog note
