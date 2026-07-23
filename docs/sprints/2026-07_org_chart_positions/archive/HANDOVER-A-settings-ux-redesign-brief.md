# Handover A — Settings redesign: UX/UI brief

> **⚠ ARCHIVED (design phase) — superseded by [../agents/BUILD-HANDOVER.md](../agents/BUILD-HANDOVER.md)** (the build entry point). Kept for history; the plan is carried forward there.

> **Owner:** design track (intended for a **cowork** session) · **Locks first** — the frontend rebuild ([Handover B](HANDOVER-B-settings-hardening-and-rebuild-plan.md) Part 2) implements whatever this brief produces.
> **Status:** brief ready for design · produces: a full UX/UI redesign of the admin Settings surface **with wireframes**.
> **▶ Design output:** [`DESIGN-settings-redesign.md`](../DESIGN-settings-redesign.md) — DRAFT for review. §1–§4 (six D-forks resolved, IA map, component tree, interaction specs for the 3 hard patterns) are the **milestone that unblocks Handover B Part 2**; §5 wireframes are produced as two rendered decks: [`settings-wireframes.html`](../settings-wireframes.html) (happy path + variants) and [`settings-state-atlas.html`](../settings-state-atlas.html) (all states). Extends the original mandate with the org model (§2.4, forest + contractor dedup) and admin model (§2.5, subtree-scoped `org_admin`).
> **Grounded by:** [`docs/ticketing_system/ui/03_admin_setup_flow_evaluation.md`](../../../ticketing_system/ui/03_admin_setup_flow_evaluation.md) (OC-06). Read it in full first — this brief distils it, it does not replace it.

---

## 0. The mandate (read this first)

Redesign the **admin Settings surface end-to-end** — Organizations, Officers, Workflows & roles, Projects & packages, plus the org-chart surfaces (tree, position types, invite-by-position). **You have explicit permission to break up the 4,723-line `app/settings/page.tsx` and re-cut the information architecture from scratch.** The goal is a surface a **Government-of-Nepal civil servant with low IT literacy** can complete without getting stranded — the current one was scored **48%** on daily-driver UX by the devil's-advocate review, and OC-06 found six inter-tab seams where the target user stalls.

**This supersedes the original OC-05 approach.** OC-05 was scoped as bolt-on components with a "~5-line `page.tsx` wiring" constraint *specifically to avoid* a big refactor. That constraint is now retired: we are doing the big refactor. OC-05's screens (org-tree editor, position-type editor, invite pre-fill, display surfaces) **fold into this redesign** as surfaces of the new Settings, not patches on the old one. See [Handover B](HANDOVER-B-settings-hardening-and-rebuild-plan.md) for how the two tracks sequence.

## 1. Who you are designing for

- **Primary user:** GoN civil servant, **low IT literacy**, doing first-time setup of a ministry's grievance system. Not a power user; will not infer hidden steps.
- **Bilingual:** English + Nepali (Devanagari). The data model is **Nepali-first** (`default_language="ne"`), but the current UI is 100% hardcoded English with **zero i18n scaffolding** (OC-06 §6). Design for bilingual from the start.
- **Context:** budget screens, glare, variable connectivity. The existing design research (`docs/ticketing_system/ui/01_ui_spec.md` §10) drove the WCAG-AA palette — respect it.
- **The promise we're keeping (doc 16 §5.2):** setting up an officer should be **one comprehensible action**, not a seven-decision puzzle. That promise is the north star of this redesign.

## 2. Scope

**In scope:** the four setup journeys as *one coherent flow*, plus the org-chart surfaces. The seams *between* tabs matter as much as the tabs — OC-06's failure mode is "I finished tab A, now what?", not a single broken screen.

**Out of scope:** the officer daily-driver experience (queue, ticket detail, thread) — that's a separate surface with its own eval. Touch it only where a Settings decision changes a shared component.

## 3. Non-negotiable constraints

These are fixed; design **within** them — do not reinvent them.

- **Design system** ([`ui/02_design_system.md`](../../../ticketing_system/ui/02_design_system.md)): Lucide icons via `@/lib/icons` semantic aliases only; **5 hue families** (blue/red/amber/green/violet) + gray/slate; the eliminated hues (`orange/yellow/indigo/purple/teal/sky`) are **banned** — OC-06 F24 found them scattered and duplicated, do not carry them forward; **WCAG AA** text (`text-gray-600` floor for information); **no emoji** as icons; use `lib/design-tokens.ts` tokens, never raw Tailwind color soup.
- **Nepali is translator-gated:** render `display_name_ne` (and any `_ne` field) **when present**, fall back to English when absent, and **never fabricate Nepali text**. Mark absent strings for the translation sheet.
- **The backend data model is fixed** by OC-01..04 (doc 16): org tree (`parent_organization_id`, `unit_type`, territory), `position_types` with a `default_role_key` matrix, `officer_positions`, the supervisor resolver. Design the UI that *consumes* this model — don't redesign the model.
- **Enforcement truths you must not contradict** (doc 16): positions are **descriptive** and *generate* `user_roles` + `officer_scopes` at invite time — they never replace them; **escalation targets the next workflow step's role pool**, the reporting line never redirects it; **SEAH cases must stay invisible** to standard reporting-line features (doc 16 §6).
- **Assume the backend hardening lands** ([Handover B](HANDOVER-B-settings-hardening-and-rebuild-plan.md) Part 1): design for a world where server-side validation rejects orphan states. Do **not** design UI whose only job is to prevent an orphan the server will soon reject — design the happy path and surface the server's rejection well.

## 4. Current-state pain (what to fix) — from OC-06

The evaluation's six seams and top-5 friction, condensed. Full evidence with `file:line` is in the OC-06 report §1, §3, §4.

1. **Inviting one officer is 7 disjoint decisions** (OC-06 F5): pick a role from the *full unfiltered catalog* by slug, know which org sits on the project, and have pre-linked that org in *another tab* first. This is the flagship thing to fix.
2. **A Nepali-named org is un-creatable** from the UI (F1): the client locks the Create button on Devanagari input.
3. **The seams strand the user** (S1/S2/S5, F8): the org editor's project panel is *read-only* (you can't give an org a role there); a workflow silently won't appear on a project if you forgot to Publish; the invite org list is empty unless the org was pre-linked elsewhere.
4. **The UI speaks developer** (F10/F11): "Run Alembic migrations" in an empty state; raw `API 409 {…json…}` errors; role **slugs** (`site_safeguards_focal_person`) instead of labels; severity shown by **color only**.
5. **Silent wrong-track/orphan bindings** (F2/F3) the admin can't tell are broken; and **the UI invites actions it will 403** (F12, project_admin sees enabled buttons that always reject).
6. **Stale go-live checklist** (F9): it doesn't refresh after most edits, so it lies.

## 5. Target patterns to design around (the spine — not full prescriptions)

Design these; the exact pixels are your call.

1. **Invite-as-result, not a fourth form.** Picking a tree node → position should show the **human-readable outcome** — e.g. *"SDE, Jhapa Division Office → acts as Site Safeguards Focal · covers Jhapa district"* — with role/org/scope pre-filled but **hidden behind an "Adjust" disclosure**. The override badge appears only when the admin opens Adjust and changes the matrix default. Every pre-filled value shows its provenance ("from position: SDE"). This is the make-or-break of the whole org-chart feature (OC-06 §7).
2. **One org surface.** The org **tree replaces the flat list** — since every org becomes a tree node, there should not be two org editors. Inline row affordances (add child, edit, set territory) on the tree.
3. **Position types are a set-once catalog, not a top tab.** ~20–50 rows, edited rarely. Give it secondary weight (a panel under org or roles), not a peer tab. Don't grow the top-level tab count for a rarely-touched surface.
4. **Guided seams.** Every read-only rollup becomes an *action* ("This org has no project role yet → Add one"). Surface publish state on workflows. Carry the "org must be linked to the project" prerequisite *into* the invite flow instead of dead-ending on it. At the end of each journey, tell the user the next step.
5. **Plain language everywhere.** Human role **labels**, not slugs. Friendly errors (a formatter already exists — `lib/user-messages.ts` — and is unused). **Text** severity labels beside color ("Blocking" / "Warning"). No migration/seed instructions in end-user empty states.
6. **Empty states with real CTAs**, and a single **"here's the one thing blocking go-live"** summary rather than two terse verdicts.

## 6. Open design forks — decide these (with context + a lean)

State a decision for each; these shape the IA before wireframing.

| # | Fork | Context | Lean |
|---|---|---|---|
| D1 | **How many top tabs, and does the org tree absorb the flat list?** | Today: 4 main tabs; org list + editor are separate; devil's-advocate hates the sprawl. | Tree **replaces** the flat list; keep top tabs ≤ 4; fold position-types under org/roles. |
| D2 | **Invite: how much stays visible after pre-fill?** | The whole "one action" promise rides on this. | Show the outcome card; hide role/org/scope behind "Adjust"; badge on override only. |
| D3 | **"Review holders" prompt: informational or actionable?** | Editing a position type's `default_role_key` does **not** re-sync existing holders (doc 16 §4). A bare "12 holders won't change" notice leaves the admin at "…so what?" | Offer an **opt-in "review & re-sync these N holders"** action, reconciled with the transfer-refresh flow — don't leave it purely informational. |
| D4 | **Nepali: bilingual-inline now, or store-only?** | `_ne` columns ship in OC-01/02, but there's no i18n renderer. | Render bilingual inline where `_ne` present (e.g. "SDE / वरिष्ठ…") with EN fallback — high value for this audience, cheap. (Full i18n infra is a Handover-B ticket.) |
| D5 | **Workflows & roles: merge into one guided flow?** | Today they're sibling sub-tabs with no cross-link; the step→role binding is the central seam (S1). | Consider a single "workflow → steps → bind role" flow where the role picker shows only valid-for-track roles and **explains why a role is excluded** (wrong track). |
| D6 | **Go-live: where does the checklist live and how does it read?** | Today at editor top, stale, color-only, two terse verdicts. | Co-locate fixes; live-refresh; one plain-language "next blocker" line. |

## 7. Deliverables expected from this design track

1. **New IA map** — the tab/surface structure, with every inter-tab jump from OC-06 §1 either eliminated or made an explicit guided step.
2. **Wireframes per journey** — Organizations (tree), Officers (invite-as-result), Workflows & roles, Projects & go-live — including **empty, loading, error, and bilingual** states, not just the happy path.
3. **A component inventory / new component tree** — the concrete components the rebuild ([Handover B](HANDOVER-B-settings-hardening-and-rebuild-plan.md) Part 2) will build, so the demolition of `page.tsx` has a target shape to build toward.
4. **Interaction specs** for the three hard patterns: invite-as-result (pre-fill + Adjust + override badge), the tree editor (create child / territory / CSV import), and the step→role binding (valid-only picker + "why excluded").
5. **The six D-forks resolved**, recorded in this file or a linked decision log.

## 8. What NOT to do

- Don't fabricate Nepali strings. Don't invent new color families or resurrect the banned hues.
- Don't redesign the backend data model or the enforcement model (positions → roles/scopes; escalation → step role pool; SEAH invisibility).
- Don't design UI whose only purpose is to block an orphan state the server will reject once Handover-B Part 1 lands — surface the rejection instead.
- Don't ship a redesign that still requires the user to carry a value (role key, org id, location code) in their head across surfaces — that's the failure this whole effort targets.

## 9. Handshake with Handover B

This brief is the **north star**; [Handover B](HANDOVER-B-settings-hardening-and-rebuild-plan.md) is the build. Two things run **in parallel with your design** and you can assume they land: (a) the **backend hardening** (validation/authz/data-integrity — Part 1), and (b) the **org-chart backend** (OC-01..04). The **frontend rebuild** (Part 2) is **gated on this brief** — it implements the IA and component tree you produce. When you finalize the component tree (deliverable 3), that's the signal Part 2 can start.
