# Sprint summary — Org chart & positions / Settings redesign (2026-07)

> As-built record at sprint close (2026-07-13). Detail + per-commit deviations live in [`PROGRESS.md`](PROGRESS.md); this is the one-page overview. Branch `dev/organisation`.

## What shipped

### Phase 1 — Backend (all DB-validated in Docker; single linear Alembic chain)

| Area | Ticket | Proof |
|---|---|---|
| Backend hardening (authz/validation/data-integrity) | SH-1..6 | `8e55e65a`..`290711d9` |
| Org forest (`parent_organization_id`, `org_category`, `unit_type`, territory, `display_name_ne`) + `descendant_org_ids` CTE + CSV import | OC-01 | migration `m3o5q7s9`; `services/org_tree.py`, `routers/locations.py` |
| Position types + position→role matrix + `/position-types` (+ holders roster) | OC-02 | migration `o5q7s9u1`; `routers/position_types.py` |
| Officer positions + invite pre-fill + per-`(project,step)` supervisor resolver | OC-03 | migration `s9u1w3y5`; `routers/officer_positions.py`, `services/supervisor.py` |
| Chart behaviours + SEAH leak-proofing | OC-04 | `services/chart_behaviors.py`, `engine/escalation.py` |
| 4-tier admin ladder (`super`/`org`/`project`/`officer_admin`) + org-scoped catalog + attenuated delegation | SH-7 | migration `q7s9u1w3`; `services/admin_access.py` |
| Org dedup soft-flag | SH-4 | `services/org_dedup.py`, `POST /organizations/duplicate-candidates` |
| **doc-13 project participants** (`implementing_agency_org_id` + `project_donors`) + **OC-04 §5.6 donor last-step-informed guardrail** (auto-populate cast, go-live **A5/C5** blocks, SEAH suppression) | doc-13 | migration `u1w3y5a7`; `services/donor_guardrail.py`; `06d96266` |
| Backend pre-req (donor CRUD, role owner-org, position holders) | — | `ad1ee1aa` |
| Frame-11/12 gaps: officer lifecycle (soft-deactivate + open-case guard + roster search) + org search + delete-impact | — | migration `w3y5a7c9`; `ec5d8dcd` |

### Phase 2 — Frontend (Next.js 16; `next build` green)

| Area | Ticket | Proof |
|---|---|---|
| i18n scaffolding (`<Bilingual>` + EN/NE) | RB-1 | `35e43d06` |
| Per-frame build sheets (13 frames) | RB-0 | `agents/build-sheets/frame-{01..13}.md`; `f1dda901` |
| Design-system + plain-language foundation (`lib/trackFilter`, `lib/labels`, `design-tokens.ORG_ROLE_BADGE`, `components/shared/*`; all banned hues purged) | RB-2 | `f1dda901` |
| Client `lib/api.ts` modernized + `country_admin` **live-bug fix** across the tree | pre-req | `b6fc2e63` |
| Org-chart surfaces (tree editor + CSV, position types, review-holders), invite-as-result flow, doc-13 participants surface, officer deactivate | RB-4/RB-3 | `components/settings/{org,officers-v2,projects}/`; `af95c321` + this commit |

**Tests:** 383 passed / 5 skipped (env-gated), `next build` compiles + generates all pages. CI note: run `make wsl-seed-full` before `make test-ticketing`.

## Deliberately deferred (documented — candidates for the devil's-advocate round)

- **Contract migration** to physically drop the legacy `project_actor_roles` / `org_role` / `routing_org_role` (kept during the expand phase; routing already reads `implementing_agency_org_id`).
- **Org merge** (Frame 12) — high-risk multi-table re-home + move-open-cases; needs the tree UI + browser validation to drive it.
- **RB-2 remaining extraction** — the Workflows cluster (StepForm/WorkflowEditor/RolesTab), the ProjectEditor body, and the Platform cluster are still inline in `page.tsx` (down from 4,723 → ~4,344 lines).
- **Transactional multi-scope invite** (SH-3), **notification write-gating server enforcement** (Frame 09), **share-subtree / orphan-re-home** (Frame 07), server-side officer directory search wiring (endpoint exists; UI still client-filters at demo scale).
- **Not browser-tested** — every Phase-2 surface is `tsc`/`next build`-validated only; UX/rendering correctness is for the review + browser pass.
