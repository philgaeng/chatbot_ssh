# Design review — Settings redesign (devil's-advocate)

> **Method:** two independent adversarial reviewer agents, cold read of the design package (no involvement in producing it), each scoring one axis with `frame/pin/§/file` evidence. Run 2026-07-08.
> **Under review:** [`DESIGN-settings-redesign.md`](DESIGN-settings-redesign.md) + [`settings-wireframes.html`](settings-wireframes.html) + [`settings-state-atlas.html`](settings-state-atlas.html), against the OC-06 baseline (old design = **48%** on daily-driver UX) and the locked model (doc 11 / doc 16).

## Scores

| Axis | R1 | R2 | R3 | R4 | R5 (post-HANDOVER-C) | Trajectory |
|---|---|---|---|---|---|---|
| **Completeness** | 57% | 70% | 77% | 80% | **84%** | 48→…→84 |
| **Ease of use** | 60% | 66% | 70% | 73% | **74%** | 48→…→74 |

**Round-5 verdict — design phase closed.** Both round-4 blockers **CLOSED** (doc 11 self-contradiction gone; `org_category` has a real schema home). Round-5 surfaced only org-scoped-catalog *propagation* gaps (position_types owner column, Frame 04 owner filter, availability-rule acceptance, System/Global chip redundancy) — **all fixed in the round-5 follow-up** (doc 16 §3.2 owner column; Frame 04 "owned by Jhapa — not here" exclusion + Frame 08 "System · everywhere / Custom · Jhapa & below"; doc 11 §11 item 3d + SH-7 catalog-filter acceptance; §7 officer_admin note; `org_category`/`unit_type` warn-not-block guard). **Remaining is not design:** English-only chrome (deferred RB-1), inherent Frame 04/07 density, and the 5 filed build-time items + the unbuilt backend (SH-7, OC-01..04, RB-1..4). Ease-of-use has **plateaued** (+1) because the ceiling is deferred/intrinsic. **Recommendation: stop the re-score loop; the design/spec package is done at 84/74 (from 48). Next work is the build.**

**Round-4 verdict:** the admin model now hangs together across doc 11 §2 / DESIGN §2.5 / Frame 07 / atlas s6 (real 3-tier appoint selector, plain-language root-creation gate, de-slugged mock UI). Blocker closed at the design surface. Remaining, per round-4 review: **(a) self-inflicted** — doc 11 §4/§5/§6/§8/§11 still on the stale 3-key/`country_code` model with no `officer_admin` (the §2 rewrite didn't propagate → doc 11 self-contradicts); `org_category` has no data home in doc 16; two residual slugs (atlas CSV "`division_office`", s6 caption "any org_admin"). **(b) design decision — RESOLVED:** any-depth org_admin catalog authoring → **org-scope the catalog** (a role/workflow/position-type is available at its owning org level + below). **(c) build-time → RB tickets:** admin audit-log UI, dual-hat invite collision, workflow level-delete in-flight guard, CSV import schema, project country-validation. **Design phase declared done at 80/73**; execution handed off — see [`HANDOVER-C-admin-model-finalize-and-cleanup.md`](archive/HANDOVER-C-admin-model-finalize-and-cleanup.md).

**Round-3 verdict:** four of six round-2 findings genuinely closed (workflow structure editing, atlas 10–13 coverage, merge + in-flight semantics, SEAH correction). **Two did not fully close:** (a) the §2.5 root/sub-tier split was **relabeled, not operationalized** — no rule for what makes an admin "root" in the §2.4 forest, no data flag, no appoint-form selector — and it now **conflicts with doc 11 §2 (LOCKED)** which reserves appointment to super/country tiers with no middle tier; (b) the "de-slugged all mock UI" claim was **overstated** (2 residual `org_admin` on Frame 07 + atlas s6, and a "Whitelist"/"Share"/"whitelisted" cross-deck mismatch) — since **fixed in the post-re-score cleanup**. Remaining real gaps: no admin **audit-log** surface, **dual-hat invite** (add 2nd position / re-invite same email → Keycloak conflict) undrawn, **workflow level-delete** has no in-flight guard, **CSV import schema** + **project country-validation semantics** unspecified.

### Round-4 — admin-model blocker RESOLVED (2026-07-08)

The round-2/3 blocker (admin model relabeled, not operationalized; conflicts with doc 11 §2 LOCKED) is closed by a user decision:
- **4-tier ladder** (strict subset): **super_admin / org_admin (subtree, *any depth* — the only tier below super that authors the catalog) / project_admin (contractors + staffing, no catalog) / officer_admin (invite officers only)**. `country_admin` retired → `org_admin`.
- **`org_category` actor types** — government / local_government / donor / third_party — give "root" a **concrete definition** (the missing piece): a new institutional root (gov/local-gov/donor) is **super-only**; third_party (contractors) is delegable. This is what distinguishes roots in the §2.4 forest.
- **doc 11 §2 UPDATED** to this ladder (the stale LOCKED spec was the real problem) + a §3–§8 bridging note. So "conflicts with doc 11" is gone — the design and the spec now agree.
- Applied to Frame 07 + atlas s6 (appoint one of three tiers; institutional roots super-only), §2.5, §2.4, §4.4, decision log.

**Still open (build-time detail, → RB tickets):** admin audit-log UI, dual-hat invite, workflow level-delete in-flight guard, CSV import schema, project country-validation semantics.

**Round-1 verdict** — Completeness: build-ready for the deeply-specified surfaces, not the four journeys end-to-end (creation/authoring/lifecycle/SEAH named but not specified). Ease-of-use: beats 48% on fixed frictions but stacks conceptual load and leaks identifiers on screen.

**Round-2 verdict (re-score, verified against the files, not the review doc):** the remediation is real — B (creation/authoring) and F (lifecycle/SEAH) genuinely closed, first-run spine works, atlas grew, vocab unified. But the pass **introduced new issues and left C incomplete**, capping the uplift. See "Round-2 findings" below.

### Round-2 findings (what the remediation introduced or left)

- **[BLOCKER] Self-contradictory admin-authority model** — §2.5's table says `org_admin` *cannot* author workflows/roles/position-types (super only), but IA §2.1, doc 11 §2.2/§3.3, and Frames 04/06/08 (pin 35) show `country/org_admin` editing exactly those. Since `org_admin` *is* the renamed `country_admin`, the spec both grants and denies the same capability. **Fix: reconcile — org_admin (standard, at a country/ministry root) authors the catalog; deeper org_admins don't.**
- **[BLOCKER/MAJOR] No workflow step add / remove / reorder** — Frame 04 edits one step + clones a template; a custom/blank workflow can't be built (add level, delete level, reorder).
- **[SEVERE-UX / MAJOR] C-pass incomplete — Frame 07 + atlas s6 leak `org_admin`/`project_admin`/`super_admin` slugs in the product UI** (only Frame 01 topbar was de-slugged); "matrix default" survives on Frame 08 flow + Frame 03 caption; bare "track" chips recur without the promised tooltip.
- **[MAJOR] New Frames 10–13 have no atlas state coverage** — "every surface, all states" still false for the four newest (and riskiest) surfaces.
- **[MAJOR] Org merge + in-flight-ticket semantics undefined** — merge is a one-liner (no conflict handling); transfer/deactivate/org-delete never address open cases already assigned to that officer/org.
- **[MODERATE / correctness] SEAH invisibility over-stated** — Frame 13 says "no SEAH officers appear here at all," but doc 16 §6 shares the chart *for directory purposes* (SEAH officers appear as people; only SEAH **case existence** must not leak). Blanket-hiding people is likely wrong.
- **[MODERATE] Flagship Admin-access (Frame 07) still designer-jargon** ("whitelist a subtree", "attenuated", "at/below your node") + gated on unbuilt SH-7 / the `country_admin→org_admin` migration (scoped as "a note").
- Minor: directory SEAH filter offered to a viewer who shouldn't see it (F11); dual-hat officers unhandled (invite + manage assume one position); Frame 08 permission grid looks editable in the headline (locked treatment only in atlas s8); "Next: <step>" thread promised in §7.A but not rendered.

### Round-3 fixes (all round-2 findings addressed)

| Round-2 finding | Fix | Where |
|---|---|---|
| **§2.5 authz contradiction** (blocker) | Split org_admin into **root tier** (catalog owner, own track — the old country_admin) vs **sub tier** (consumes catalog); reconciled §2.1 gating + pin 35 | §2.5 table + §2.1 + Frame 07/08 pins |
| **No workflow step add/remove/reorder** | Added a **Levels** rail (add / reorder / remove a level) + "Start blank" path | Frame 04 pin 53 |
| **Frame 07 / atlas slug leak** (severe) | De-slugged all mock UI: `org_admin`→"Organisation admin", `project_admin`→"Project admin", `super_admin`→"super admin", "Whitelist a subtree"→"Share an organisation", "attenuated"/"matrix default"/bare "track" removed from screens | Frame 07/08/03/04 + atlas s3/s4/s6 |
| **No atlas states for Frames 10–13** | Added atlas Surfaces **10–13** (create-project, officer lifecycle, org lifecycle, SEAH) | atlas s10–s13 (14 surfaces total) |
| **Merge + in-flight tickets undefined** | Merge re-homes officers/links/children, moves open cases, flags territory/country conflicts; delete/deactivate/transfer **require reassigning open cases first** | Frame 11/12 pins 54–55 + §7.F1/F2 |
| **SEAH invisibility over-stated** (correctness) | Corrected: only SEAH *case existence* is hidden; **SEAH officers appear as people** (chart shared for directory, doc 16 §6) | Frame 13 pin 50 + atlas s13 + §7.F4 |
| Minors | Frame 08 permission grid dimmed + "read-only" lock note in headline; directory SEAH filter gated to SEAH-capable admins (pin 45); dual-hat note (pin 46); "Next: …" strip (pin 56) | Frames 08/11/10 |

> **All A/B/C/E/F round-2 findings closed.** Wireframes 9→**13 frames / pins 1–56**; atlas 10→**14 surfaces**. Remaining: the *systematic* C label-map is still an RB-build task (spec-rail annotations intentionally keep identifiers); D (bilingual chrome) deferred. A **round-3 re-score** would confirm the movement.

**Genuine strengths both confirmed:** invite outcome card + provenance + inline S5 "Link it and continue" (Frame 03) collapses the #1 friction; friendly errors replace raw 409 JSON; text severity beside colour.

## Findings and remediation status

Legend: ✅ done · 🖼️ wireframed + spec'd · 📝 spec'd (render pending) · ⏸️ deferred by decision.

| # | Finding (condensed) | Key evidence | Remediation | Status |
|---|---|---|---|---|
| **A** | **Day-one landing undesigned** — the go-live spine is *per-project* ("KL Road is 1 step…"); on an empty system nothing anchors it. The "always names the next step" thesis only shown on a near-finished project. | Frame 01, atlas s1 | `§7.A` first-run mode: zero-data ordered checklist (Add ministry → Workflows & roles → Project → Officers → Go live); per-project spine is mode 2. **Frame 01 first-run variant (pin 40) + spec.** | 🖼️ |
| **B** | **Creation/authoring flows unspecified** — no workflow SLA/escalation timing, no project & package creation, no workflow→project link, no clone-a-template. Completeness **blockers**. | Frame 04/05, tree `[extract]` | `§7.B`. **B2** SLA + escalation target (Frame 04 pin 41); **B1** project+package create (Frame 10); **B3** workflow→project link, published-only (Frame 10); **B4** clone-a-template (Frame 04 variant, pin 51). | 🖼️ ✅ |
| **C** | **Jargon back on screen** — `unit_type`/project-role slugs as chips, `descendant_org_ids` + literal "∪" shown, "track"/"the matrix"/"attenuated" undefined. Contradicts own F11. | Frames 02/05/06/07 | `§7.C` hard rule (no code identifiers / math symbols). **Applied:** unit_type & project-role → labels; scope line → prose ("your office and every office beneath it…"); "attenuated" removed; "the matrix" → "default role for this position"; "/ —" → "Nepali name needed"; track → "Standard grievances / SEAH". | 🖼️ (worst offenders; full sweep in RB build) |
| **D** | **English-only chrome** for a Nepali-first user. | D4, brief §1 | **Deferred by decision** — stays the RB-1 i18n ticket. | ⏸️ |
| **E** | **Self-inflicted inconsistencies** — atlas covered 6/9 surfaces; "Handler"≠"Handles it"; Frame 09 defaults contradict proto in-app-only; `country_admin` vs `org_admin`. | atlas, Frame 04/08/09/01 | `§7.E`. **Atlas now covers 9 surfaces (added Position types, Roles, Notifications).** Vocabulary unified on the cast's plain phrases (Frame 08 "job in a step"). Frame 09 proto-phasing banner. `country_admin` → "Organisation admin" (Frame 01). | 🖼️ ✅ |
| **F** | **Lifecycle & scale gaps** — officer transfer/edit/deactivate, org delete/re-parent/merge, directory + tree search/pagination at ~5,000 staff, SEAH setup + invisibility surfaces, admin revoke/bootstrap/orphan. | §2.5, Frames 02/07, doc 16 §6 | `§7.F` (F1–F5). **Frame 11** (officer directory at scale + manage/transfer/deactivate), **Frame 12** (org "⋯" lifecycle + SH-4 guard + tree at scale), **Frame 13** (SEAH setup + invisibility), **Frame 07 variant** (revoke/bootstrap/orphan-rehome). | 🖼️ ✅ |

## What changed in this remediation pass

- **DESIGN doc:** new **§7** (A/B/C/E/F specs) + 5 decision-log rows; §4.5 / §7.E vocabulary reconciled; §7.A/§7.B/§7.C/§7.E marked `[wireframed]`, §7.B-rest/§7.F `[spec-only]`.
- **Wireframes deck (9 frames):** Frame 01 first-run variant + admin naming + de-coded "Fix" link; Frame 04 SLA + escalation target; Frame 08 vocabulary; Frame 09 proto banner; jargon labels across Frames 02/05/06/07. Pins now 1–41.
- **State atlas (10 surfaces):** added Position types, Roles, Notifications state sets; scope-line + "/ —" copy de-jargoned.

## Still open (next build increment)

1. **Full C sweep** — the label map (`lib/labels.ts`) applied everywhere during RB-2/RB-3, not just the worst offenders hit here. (Spec-rail annotations still carry technical identifiers for engineers — intentional.)
2. **D (bilingual chrome)** — RB-1, when scheduled.

> **A/B/C/E/F remediation landed** (2026-07-08): wireframes deck grew from 9 → **13 frames** (pins 1–52) — added first-run spine, project & workflow creation, officer/org lifecycle at scale, and SEAH; atlas grew to **10 surfaces**. All findings except D are now 🖼️ wireframed + spec'd (C to worst-offender depth). **Re-running the two devil's-advocate agents is the natural next checkpoint** — it should show both scores move.
