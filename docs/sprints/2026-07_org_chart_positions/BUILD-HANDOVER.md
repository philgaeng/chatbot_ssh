# Build handover — Settings redesign & org-chart: launch the build

> **This is the single entry point to build the redesigned admin Settings surface + the org-chart backend.** The design phase is **done** — 5 independent devil's-advocate review rounds took it from a 48% baseline to **84% completeness / 74% ease-of-use**, and every design blocker is closed. No design decisions are open; what follows is execution.
> **Supersedes** the three design-phase handovers (now in [`archive/`](archive/)): A (UX brief), B (hardening & rebuild plan — the detailed ticket text lives on there), C (admin-model finalize & cleanup, executed). This doc carries the *launch + sequencing*; read `archive/HANDOVER-B` for full ticket bodies.
> **Do NOT touch `main`.** Branch per workstream off `integration/seah-claude`. Ticketing stream only; every migration gets the safety header + a real `downgrade()`; **tests ship in the same commit** (authz matrix + SEAH-leak tests are acceptance, not follow-ups). See the sprint README §"Why this sprint carries extra scrutiny."

---

## 0. Read order (for a build agent)

1. **This doc** — the plan + sequencing + DoD.
2. **[`DESIGN-settings-redesign.md`](DESIGN-settings-redesign.md)** — the design source of record: IA §2, org model §2.4, **admin model §2.5**, interaction specs §4 (invite-as-result, tree editor, step→role cast, roles §4.4, notifications §4.5), remediation §7, and the **component tree §3** (the target shape `page.tsx` is demolished toward).
3. **Wireframes** (open locally, standalone HTML): [`settings-wireframes.html`](settings-wireframes.html) — 13 desktop frames, pins 1–56; **states**: [`settings-state-atlas.html`](settings-state-atlas.html) — 14 surfaces.
4. **Specs:** [`doc 11 §2`](../../ticketing_system/11_roles_and_permissions.md) (admin ladder), [`doc 16`](../../ticketing_system/16_org_chart_and_positions.md) (org tree + `org_category` + position types), doc 12 (workflows/notifications), doc 10/13/14 (settings/projects/platform).
5. **History:** [`DESIGN-REVIEW.md`](DESIGN-REVIEW.md) (the 5-round scores + every finding) and [`archive/`](archive/) (A/B/C).

---

## 1. Locked decisions (ground truth — condensed; full text in DESIGN + doc 11/16)

- **IA (D1):** 4 domain tabs (Organisation · Workflows & roles · Projects · Platform) + a **Setup & go-live landing** (first-run 5-step spine + per-project go-live). Tree replaces the flat org list; position-types + officers fold under Organisation. Zero net new top tabs. *(DESIGN §2.1–§2.3)*
- **Org model — forest (§2.4):** `parent_organization_id` is nullable; the GoN reporting line is one rooted subtree; **contractors and donors are independent roots**, and each root can be a **multi-level subtree**. Contractor create has a **fuzzy dedup soft-flag** (distinctive name tokens + corporate email + address), never a hard block.
- **Actor types — `org_category` (§2.4/§2.5, doc 16 §3.1):** `government` / `local_government` / `donor` / `third_party`, set at root, inherited. **New institutional root (gov/local-gov/donor) = super_admin only; `third_party` (contractors) delegable.**
- **Admin ladder — 4-tier strict subset (§2.5, doc 11 §2):** `super_admin` / `org_admin` (org-subtree, **any depth**; authors the catalog) / `project_admin` (contractors + staffing, no catalog) / `officer_admin` (invite/modify/revoke officers only). `country_admin` retired → `org_admin`. **Attenuated delegation.**
- **Org-scoped catalog (§4.4, doc 11 §3.3):** a role / workflow / position-type carries `owner_organization_id` and is available **at its owning org level and below** (`NULL` = global/system). Kills catalog proliferation.
- **Invite-as-result (D2, §4.1):** office → position → **outcome card**; role/org/scope behind "Adjust"; override badge only on override; provenance on every value; confirm before the irreversible Keycloak email.
- **Workflow = step "cast" (§4.3):** each step binds a cast — Handles it / Oversees / Kept informed / Can view (= `assigned_role_key` / `supervisor_role` / `informed_roles[]` / `observer_roles[]`) + SLA + escalation target; **valid-only picker** (track + owner-scope, with "why excluded"); **templates pre-fill the cast**.
- **Notifications derive from the cast (§4.5):** one per-track grid (`settings.notification_rules`); observers silent; proto = in-app only for officers.
- **Plain-language + design-system contract (§7.C):** labels not slugs on product surfaces; friendly errors via `lib/user-messages.ts`; text severity beside colour; 5 hue families + gray/slate, no banned hues, no emoji.
- **SEAH (doc 16 §6):** the chart is shared for directory purposes (SEAH officers appear as people); only SEAH **case existence** is hidden from standard reporting-line/Watching/notification surfaces.

---

## 2. Build plan — two phases (backend can start now; frontend is unblocked)

Full ticket bodies: [`archive/HANDOVER-B`](archive/HANDOVER-B-settings-hardening-and-rebuild-plan.md). This is the launch list + dependencies.

### Phase 1 — Backend (start now, parallel; UX-independent)

| Ticket | What | Depends on |
|---|---|---|
| **SH-1** | Wire scoped authz gates (org CRUD / project mutation / invite) off the fine-grained gates, not blanket `is_any_admin`; track-honoring | — |
| **SH-2** | Workflow step→role referential + track validation on write & publish (all 4 tiers) | — |
| **SH-3** | Invite path org/jurisdiction validation + atomic multi-scope (also OC-03 acceptance) | — |
| **SH-4** | Org lifecycle guards (delete `ProjectOrganization` count, `GET /organizations` auth, country validation) + **fuzzy dedup finder** | — |
| **SH-5** | Role delete guard counts tier fields (supervisor/informed/observer) | — |
| **SH-6** | Org-id charset policy (ASCII ids; Nepali in `display_name_ne`) | — |
| **OC-01** | Org tree: `parent_organization_id`, `unit_type`, **`org_category`**, territory, `display_name_ne`; **`descendant_org_ids` CTE + cycle guard**; CSV import | serialize migration on live head (README §parallel-safety) |
| **OC-02** | `position_types` + matrix + `owner_organization_id`; `/position-types` CRUD | OC-01 |
| **OC-03** | `officer_positions` + invite pre-fill + supervisor resolver; routes through validated helpers (SH-3) | OC-01/02 |
| **OC-04** | Chart behaviors (display, visibility, prefer-own-office, escalation-notify) + **SEAH leak-proofing** | OC-03 |
| **SH-7** | **Hierarchical admin scope** — the 4 role keys (retire `country_admin`, add `officer_admin`); org-subtree scope-reach (a/b/c) + track; **`org_category` root-creation gating**; **attenuated delegation**; **org-scoped catalog** (`owner_organization_id` on roles/workflows/position-types + availability filter). Supersedes SH-1's flat gate + absorbs SH-1b. | **OC-01** (descendant helper) |

### Phase 2 — Frontend rebuild (design-gated — the gate is now met)

| Ticket | What | Depends on |
|---|---|---|
| **RB-1** | i18n scaffolding (this Next.js 16 build — read `node_modules/next/dist/docs/` per `channels/ticketing-ui/AGENTS.md`); EN/NE key structure + English fallback + `<Bilingual>`; never fabricate Nepali | can start early |
| **RB-2** | God-file demolition → the **component tree (DESIGN §3)**; design-token contract; single-source track-filter + a `lib/labels.ts` display map (finish the plain-language sweep, §7.C) | design tree (done) |
| **RB-3** | Rebuild the four flows per wireframes — Setup/first-run, Organisation (tree), Officers (invite-as-result), Workflows & roles (cast + valid-only picker), Projects & go-live | RB-2 |
| **RB-4** | Org-chart surfaces — tree editor + CSV import; position types; invite pre-fill outcome card; **org-scoped catalog owning-level in the role/step pickers**; typed `lib/api.ts` wrappers | OC-01..04, RB-2 |

### Open build items (spec'd in review; fold into the ticket noted)

| Item | One-line | Fold into |
|---|---|---|
| Admin **audit-log** UI | GET endpoint + read surface over `log_admin_audit()` ("who appointed/revoked/authored what, when") | RB-4 + a small API ticket |
| **Dual-hat invite** collision | email already an officer → "add a position" vs Keycloak 409 | RB-4 + OC-03 |
| **Workflow level-delete** in-flight guard | remove-a-level must guard tickets parked at that level | RB-3 |
| **CSV import schema** | columns/format for `POST /organizations/import` (parent-by-key, `unit_type`, `org_category`, territory, `_ne`) | OC-01 |
| **Project country-validation** | `country_code` vs `countries` table + org↔project consistency | SH-4 / B1 |

### Sequencing
```
NOW ─ Phase 1 backend (parallel):  SH-1..SH-6      OC-01 ─▶ OC-02 ─▶ OC-03 ─▶ OC-04
                                                     └────────────────▶ SH-7 (needs OC-01)
GATE MET ─ Phase 2 frontend:        RB-1 (early) ─▶ RB-2 ─▶ RB-3
                                                     └──────▶ RB-4 (needs OC-01..04)
```
**Migration-head coordination:** OC-01/02/03 + SH-schema tickets serialize on the live `alembic heads` (README §parallel-safety; PROGRESS "Migration head coordination"). Never fork the chain.

---

## 3. Definition of done (build)

- [ ] Phase 1: SH-1..7 + OC-01..04 green in CI, **authz matrix × persona × tree-position** + **SEAH-leak** + **org-scoped-catalog filter** (doc 11 §11 item 3d) tests passing.
- [ ] Phase 2: `page.tsx` decomposed to the DESIGN §3 component tree; the four flows + org-chart surfaces rebuilt per wireframes; design-token contract enforced; plain-language sweep (`lib/labels.ts`) applied everywhere.
- [ ] `country_admin` gone from **code** (seeds, `admin_access.py`, tests) — replaced by the 4-tier keys.
- [ ] doc 11 §8 / doc 16 status flipped to as-built, citing the migrations/routers that prove it.
- [ ] [`PROGRESS.md`](PROGRESS.md) updated every commit; sprint close checklist (README) done.

---

## 4. Conventions

- Branch per workstream off `integration/seah-claude` (README naming); **never touch `main`**.
- Migrations: ticketing stream only (`ticketing/migrations/`), safety header, real `downgrade()`, chained deliberately on the live head.
- New UI = new `components/settings/*` per the DESIGN §3 tree; enforce the design-token contract (no banned hues, no raw color soup, no emoji).
- Every ticket ships with its tests; **authz matrix** for every new endpoint and **SEAH-leak** tests for every reporting-line behavior are acceptance criteria.

---

## 5. Artifacts

**Live (the build consumes these):** [`DESIGN-settings-redesign.md`](DESIGN-settings-redesign.md) · [`settings-wireframes.html`](settings-wireframes.html) · [`settings-state-atlas.html`](settings-state-atlas.html) · [`DESIGN-REVIEW.md`](DESIGN-REVIEW.md) · [`PROGRESS.md`](PROGRESS.md) · specs doc 11/12/13/14/16 · sprint runbooks [`agents/`](agents/).

**Archived (design-phase history — superseded by this doc):** [`archive/HANDOVER-A`](archive/HANDOVER-A-settings-ux-redesign-brief.md) (UX brief) · [`archive/HANDOVER-B`](archive/HANDOVER-B-settings-hardening-and-rebuild-plan.md) (full SH/RB ticket bodies) · [`archive/HANDOVER-C`](archive/HANDOVER-C-admin-model-finalize-and-cleanup.md) (cleanup, executed).

**Session memory:** `~/.claude/projects/-home-philg-projects-nepal-chatbot/memory/` — `admin-model-4-tier-ladder.md`.
