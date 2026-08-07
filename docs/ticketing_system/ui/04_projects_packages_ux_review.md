# Projects & Packages tab — UX/UI design review (Nepal audience)

**Status:** 🟢 Working reference — **Draft 2 (2026-07-24, first review pass done)**. Built from live screenshots + code grounding. This is the **shared reference point** for iterating on the Projects & packages editor screen. Phil's answers are inline (`Response:`); Claude's review replies are inline too (`Claude →`). Decisions are logged in §B. Two original findings were **retracted on review** (QR discoverability; Nepali translation for this screen) and one **narrowed** (role labels) — retractions are kept inline, not deleted, so the reasoning survives. **All Draft-2 questions resolved.** Since then (2026-07-30) the D4 mockup work produced new **staffing-assignment decisions** (position-first assignment + author-named / mandatory tiers), folded in at **§13** — authoritative in [doc 13 §5A](../13_projects_and_packages.md) / [doc 12 §6.2](../12_workflows_configuration.md). Mockup: §7.

**Screen under review:** Settings → **Projects & packages** → a single project (e.g. *Kakarbhitta-Laukahi Road*).
**Related:** [03_admin_setup_flow_evaluation.md](03_admin_setup_flow_evaluation.md) (OC-06 — whole admin flow), [13_projects_and_packages.md](../13_projects_and_packages.md) (as-built spec), [12_workflows_configuration.md](../12_workflows_configuration.md), [16_org_chart_and_positions.md](../16_org_chart_and_positions.md), [11_roles_and_permissions.md](../11_roles_and_permissions.md).
**Audience premise (refined on review):** doc 16 §5.2's "**GoN civil servants, low IT literacy**" governs the *complainant / chatbot* surface. **This admin editor is org-admin-only** (Q-AUD-1) — English-fluent regular web users — so it's judged against a capable-but-non-technical admin: *not* low-literacy, *not* a SaaS power-user.

**House style (inherited from OC-06):** strengths stated first so the criticism is credible; friction ranked by real user impact; claims code-grounded with `file:line` where possible; inferences marked **[verify]**.

---

## 0. How to use this doc

- **Question legend:** 🔵 OPEN (needs Phil) · ✅ DECIDED (see Decisions log) · 🟡 DEFERRED (parked, logged).
- Every shortcoming carries a **Q-id** (e.g. `Q-LOC-1`). Answer by Q-id; §A collects them all in one table for a single pass.
- "Candidate directions" are **options, not recommendations-as-decisions** — they exist so the question is concrete. Phil drives the fork (per project convention).
- When a question is answered, move it to §Decisions log and update the dimension section.

---

## 1. What the screen is today (baseline)

**Route / code map** (so we know what we're editing):

| Region on screen | Component | Notes |
| --- | --- | --- |
| Tab shell (`Organizations & officers / Workflows / Projects & packages / Settings`) | [`app/settings/page.tsx`](../../../channels/ticketing-ui/app/settings/page.tsx) | Projects lives under the `projects` main tab, and is the landing. **`Setup & go-live` was removed 2026-08-07** — it re-listed every project's go-live checks in a second layout one click from the console that owns them, so it could only agree with the console by accident. |
| Go-live status panel ("6 blockers · can't activate yet") | [`ProjectGoLivePanel.tsx`](../../../channels/ticketing-ui/components/settings/ProjectGoLivePanel.tsx) | **Listed in rail order, ungrouped** (2026-08-07). A check's `section` is the pane that fixes it, so reading down the list is reading down the rail. The old `group` taxonomy (Routing / Commercial / Officers / Geography / Metadata) answered a different question than the nav, put "Package locations" three headings from Packages, and is deleted from the API response. |
| Per-project frame (identity, workflows, messaging, actors, locations, packages) | [`ProjectEditor.tsx`](../../../channels/ticketing-ui/components/settings/projects/ProjectEditor.tsx) | `Grievance workflows` :423 · `Messaging` :464 · `Project actors` :556 · `Linked locations` :649 · `Packages` :682 · override callout :697 |
| Project-wide cast (L1–L4 Actor/Supervisor/Participants) | [`ProjectCastSection.tsx`](../../../channels/ticketing-ui/components/settings/projects/ProjectCastSection.tsx), [`CastStaffing.tsx`](../../../channels/ticketing-ui/components/settings/projects/CastStaffing.tsx) | "shared ladder", "every lot inherits it" |
| Package/lot rows | [`PackageRow.tsx`](../../../channels/ticketing-ui/components/settings/projects/PackageRow.tsx), [`PackageCreateModal.tsx`](../../../channels/ticketing-ui/components/settings/projects/PackageCreateModal.tsx) | Lot code / name / km range / package actors |
| Bilingual infra (exists, **not used on this screen**) | [`lib/i18n/resolve.ts`](../../../channels/ticketing-ui/lib/i18n/resolve.ts), `<Bilingual>` | EN source-of-record + optional `ne` overlay; used in [`PositionTypesPanel.tsx:228`](../../../channels/ticketing-ui/components/settings/org/PositionTypesPanel.tsx#L228) |

**The screen, top to bottom (one long vertical scroll):** SEAH-access banner → title + `Deactivate` link → **Go-live status** checklist → **Description** → **Grievance workflows** (label / published workflow / Default toggle / classifications multiselect / Save workflows) → **Messaging** (Officer SMS toggle / Save messaging) → **Project actors** (org + role-on-project + Add officer; + New organization) → **Linked locations** (search province/district/municipality) → **Project-wide cast** (L1 Site Safeguards → L4 Legal, each with Actor / Supervisor / Participants + assign) → **Packages** (override callout + expandable lot cards: code / name / description / package actors).

### What already works — the keep-list (don't regress these)

1. **"Lot" / "Package"** are correct DOR/ADB civil-works contract terms — a road engineer thinks in exactly these units. Keep.
2. **Chainage** ("Km 0+000 to Km 45+000") is native road-engineer language.
3. **Location search spanning province / district / municipality** matches Nepal's federal structure.
4. **Implementing Agency / Donor** roles map to the ADB project org chart (and match the 2026-07 participants simplification in [13 §note](../13_projects_and_packages.md)).
5. **QR intake** — a top-level main-menu feature for all users (roadside signboard → scan → file). *(Draft 1 wrongly called this "under-sold"; retracted — see D8.)*
6. **A go-live checklist exists at all** — good guardrail against silent misconfiguration; the problem is severity signalling (D5), not the concept.
7. **The bilingual overlay exists** — but is **not needed on this admin screen** (org-admin audience is English-fluent; Q-AUD-1). It serves complainant-facing / lower-literacy surfaces.

---

## 2. Audience model — who is this actually for?

The spec says "GoN civil servants, low IT literacy." I hypothesised a **split audience** below; **Phil's answers collapse it** — this screen is org-admin-only (Q-AUD-1) and that population is English-fluent. The split is kept here as the record of what was considered:

- **Audience A — ADB-fluent safeguards consultants / PIU setup staff.** Comfortable with "Implementing Agency", "GRC", "lot". Present during setup. Will cope with most of the current UI.
- **Audience B — DOR / municipal / ward staff who inherit the system after consultants leave.** Lower English + IT literacy. This is who lives inside the tool long-term and who the spec premise targets. Yet they are all educated in English and use English websites regularly so no need to translate.

> **✅ Q-AUD-1 — Who do we optimise the Projects & packages editor for?**
>Response (c) explicitly two modes already specced for org_admin and super_admin - this screen is only for admins
> **Claude →** Locks the audience to **org-level admins, English-fluent** — this is what retires the D1 *translation* finding.
>
> **✅ Q-AUD-2 — Lifecycle:** Is project *setup* a one-time consultant task, or will DOR/municipal staff routinely re-configure (add lots, restaff) over the project's life? Response :Project are made only by org-level staff. Lower ranks may just invite officers for given positions
> **Claude →** Config is **revisited over the project's life** by org admins — so D4 keeps a free-form editor, not a wizard-as-primary.

---

## 3. Review dimensions (the lenses)

Proposed scoring lenses. We rate the screen (and later, each redesign) against these. Reorder/drop as you like.

| # | Dimension | The question it answers | Verdict |
| --- | --- | --- | --- |
| **D1** | Language & localisation | Can a Nepali-first user read, and does it fit Nepal's calendar/scripts/place-names? | N/A — English-only screen; BS dates only |
| **D2** | Terminology & mental model | Do the words match how a DOR/PIU officer thinks, or impose software/theatre metaphors? | OK — author-named tiers (§13) |
| **D3** | Configuration-model comprehensibility | Can a user predict what the inherit/override cast model will do? | OK — badges + position-first (§13) |
| **D4** | Information architecture & density | Is one giant scroll with fragmented saves the right container? | OK — two-pane console |
| **D5** | System status & feedback | Does go-live tell the user what actually blocks activation vs. what's cosmetic? | OK — binary pass/blocker |
| **D6** | Error prevention & safety | Where can a low-IT user silently break routing or fat-finger a destructive action? | OK — guard + inline validation |
| **D7** | Data entry & search | Does input/search survive Devanagari and messy place-name romanisation? | Data entry limited to super-admin from proven sources |
| **D8** | Domain fit & discoverability | Are Nepal-critical features (QR intake, real GRM roles) surfaced or buried? | Good |
| **D9** | Accessibility & device/network reality | Does it hold up on cheap monitors, small screens, patchy district connectivity? | 14″ laptop benchmark |

---

## 4. D1 — Language & localisation

**Current state.** Screen chrome is 100% hardcoded English ([`ProjectEditor.tsx:423–697`](../../../channels/ticketing-ui/components/settings/projects/ProjectEditor.tsx#L423)). A bilingual overlay **exists and is proven** elsewhere ([`resolve.ts`](../../../channels/ticketing-ui/lib/i18n/resolve.ts): EN = source-of-record, `ne` = optional, never fabricated; live in `PositionTypesPanel`) but this screen opts out. **No Bikram Sambat handling anywhere in the source** — only one `toLocaleDateString()` in the whole UI, so every date the tool ever shows is Gregorian.

**Shortcomings (revised on review):**
1. ~~**English-only chrome for a low-IT-literacy Nepali user**~~ — **RETRACTED (Q-AUD-1):** this editor is org-admin-only and that audience is English-fluent. No translation needed here.
2. **Gregorian-only** — Nepal's fiscal year is Shrawan–Ashad; "quarterly" reports and any go-live/report date won't line up with GoN/DOR cycles. **← the one live localisation item; English fluency does *not* resolve a calendar mismatch.**
3. ~~**The overlay is half-adopted**~~ — **RETRACTED for this screen:** the `ne` overlay is for complainant-facing / lower-literacy surfaces, not this admin editor. Opting out here is correct, not inconsistent.

> **✅ Q-LOC-1 — Nepali UI scope → (a) leave English-only.** Admins are English-fluent (Q-AUD-1); names are entered in English/roman (Q-SEARCH-2). Do **not** adopt `<Bilingual>` on this screen.
> **✅ Q-LOC-2 — Bikram Sambat → BS-only.** Response (2026-07-30): keep **Bikram Sambat only** (not dual). All dates on this screen and in reports render in BS. *(AD can be added later only where a specific donor-facing export needs it — non-blocking.)*- LETS KEEP bc ONLY to avoid confusion
> **✅ Q-LOC-3 — Priority → moot for translation** (nothing to sequence); collapses into Q-LOC-2, which is dates-only.

---

## 5. D2 — Terminology & mental model

**Current state.** The UI leaks internal engineering names. Three unrelated metaphor families collide: **theatre** ("Project-wide **cast**"), **physical** ("the shared **ladder**"), **software/OO** ("every lot **inherits** it", "Default **catch-all**", workflow "**binding**"). Roles are abstracted to generic primitives — **Actor** ("owns & works the case") / **Supervisor** ("escalation / reassign") / **Participants** ("informed + notes") — instead of the real GRM titles (Site Safeguards Focal Person, PD/PIU, GRC Chair/Member) the officer actually knows. Other terms of art on-screen: "taxonomy", "classifications", "intake paths", "re-route after category edit", "reassignment authority", "field tiers". "SEAH" appears as a bare acronym in the red banner.

**Shortcomings (ranked):**
1. **"Actor / Supervisor / Participants" forces a translation step** — the officer must map "Actor → our focal person" on every row of every level.
2. **Metaphor soup** (cast/ladder/lot/tier/inherit) raises load for zero domain benefit — these are our words, not theirs.
3. **Bare "SEAH" acronym** on the most sensitive workflow — worst place to be terse.
4. **"Default (catch-all)" / "binding"** are DB/routing concepts surfaced raw.

> **✅ Q-TERM-1 — Role labels (narrowed).** Replace generic tiers with real GRM titles on-screen? (a) show real title primary, keep Actor/Supervisor as sub-caption · (b) real titles only · (c) keep generic (they're intentionally workflow-agnostic — if so, *why*, so we stop re-litigating). Note the 2026-07 participants simplification already reshaped this model ([13 §note](../13_projects_and_packages.md)). Response : I intentionally does not use the ADB safeguards wording in the workflow so the workflow can be used for any types of projects. We have mostly eliminated roles to avoid this trap. What you seem to be inclined to is to ressucitate roles so we can assign match abstract categories such as actor to Safeguard Officer Level 1 for the Step 1 of a ADB project for instance - please reply on this
>
> **Claude → No — I am not asking to resurrect roles, and I'd keep your abstraction.** Re-coupling the engine to a fixed role catalog (Actor → "Safeguards Officer L1") is exactly the trap you avoided — it welds the workflow to ADB-safeguards semantics and breaks reuse across hazards / CA / SEAH / other donors. **Keep Actor / Supervisor / Participants in the engine.** What I under-credited: the domain meaning is *already* delivered by the **workflow's level names** ("Level 1 – Site Safeguards", "GRC", "Legal Institutions") — workflow *content*, not hardcoded roles — so the officer reads "Actor" *under* "Level 1 – Site Safeguards" plus the sub-caption ("owns & works the case"), which is enough. **D2 #1 is retracted.** The only residual (not a roles feature): UX quality rides on authors naming levels well — a workflow with "Step 1 / Step 2" levels would make the generic tiers opaque, so the lever is a soft "level has no descriptive name" check at authoring time. ✅ **Q-TERM-2 (de-jargon)** and ✅ **Q-TERM-3 (keep "SEAH")** accepted.
> **⤷ Evolved 2026-07-30 (§13):** superseded — the workflow **author names each tier per level** ("Safeguard Officer", "GRC Chairman") and the staffing UI shows *those* names, not "Actor / Supervisor". The 4-tier abstraction stays **engine-only**. See [doc 12 §6.2](../12_workflows_configuration.md).
> **✅ Q-TERM-2 — De-jargon pass.** OK to rename the leaked engineering terms in UI copy (cast→staffing, catch-all→"used when nothing else matches", inherit→"applies to every lot unless overridden")? Any terms that must stay verbatim for training/ToR alignment? Response: OK
> **✅ Q-TERM-3 — SEAH.** Expand on first use / tooltip? Confirm the exact Nepali-appropriate phrasing for a sensitive topic (this is a sensitivity call, not just copy). Response: SEAH is ok

---

## 6. D3 — Configuration-model comprehensibility (inherit / override)

**Current state.** Project-wide cast staffs L1–L4 once; "every lot inherits it"; a yellow callout ([`ProjectEditor.tsx:697`](../../../channels/ticketing-ui/components/settings/projects/ProjectEditor.tsx#L697)) explains a package actor "replaces the project-wide actor with the **same role** on that lot only." This is object-oriented inheritance exposed to a non-programmer.

**Shortcomings (ranked):**
1. **Silent inheritance is invisible** — a lot with no officer *listed* may be fully staffed by inheritance, or genuinely empty; the UI doesn't distinguish "inherited from project" vs. "overridden here" vs. "unstaffed" at a glance. This is exactly where mis-staffing (→ grievance routes to nobody) will hide.
2. **Two-layer reasoning** — the user must hold project-default + per-lot-override in their head to answer "who gets this lot's L1 case?"
3. **The explanation is a paragraph, not the UI** — if a callout has to explain the model in prose, the model isn't showing itself.

> **✅ Q-CAST-1 — Surface inheritance state.** Should each lot level show an explicit badge — `Inherited: <name>` / `Overridden: <name>` / `⚠ Unstaffed`? (There's already an "⚠ L1 actor unstaffed" badge per the git log — extend that vocabulary to inheritance?)
> **✅ Q-CAST-2 — Is per-lot override actually used at demo/early stage,** or is project-wide staffing the 95% case? If the latter, we can collapse override behind an "advanced" affordance and simplify the default view. Response: in real life, level 1 and probably level 2 are at package level while level 3 and 4 are at project level for a mid size project. the current design provides flexibility to handle these case. plus one package may be in a district difficult of access or another province and have his own L3 for instance while 3 other packagees share the same L3.
>
> **Claude → decision.** Your answer makes override the **norm** (L1/L2 package-level, L3/L4 project-level, plus the remote-package-with-its-own-L3 case) — which kills the "hide override behind advanced" idea and *raises* the priority of **✅ Q-CAST-1 = yes**: every lot level shows an explicit badge — **`Inherited: <name>` / `Overridden: <name>` / `⚠ Unstaffed`** — so "who works this lot's L1?" is answerable at a glance. Bonus: your L1/L2-package + L3/L4-project pattern is a natural **default template** to pre-apply on lot creation and cut clicks. 

---

## 7. D4 — Information architecture & density

**Current state.** Everything for a project is one long vertical scroll (go-live → description → workflows → messaging → actors → locations → cast → nested lots). Saves are fragmented: distinct **"Save workflows"** and **"Save messaging"** buttons, while actors/locations/cast appear to persist per-action **[verify — trace save paths in `ProjectEditor.tsx`]**.

**Shortcomings (ranked):**
1. **Ambiguous save model** — "did my change save?" is unanswerable at a glance when some sections have Save buttons and others auto-persist. High risk of lost work for a cautious low-IT user.
2. **No overview/progress spine** — the only structure is the go-live panel at the very top; after scrolling past it the user has no "where am I / what's left."
3. **Long-scroll re-find cost** — editing lot 5's staffing means scrolling the whole page each time.

> **✅ Q-IA-1 — Container.** Keep single scroll, or move to (a) sub-tabs/accordion sections with a sticky spine · (b) a left in-page nav mirroring go-live groups · (c) a guided stepper for first-time setup, free-form after. Tie to Q-AUD-2. Response: I want your expert reco here
> **✅ Q-IA-2 — Save model.** Unify to one explicit "Save project" with dirty-state indicator, or make everything auto-save with clear "Saved ✓" feedback? (Pick one; mixed is the current problem.) - Response: Your reco here.
>
> **Claude → Q-IA-1 reco: keep the single page; promote the go-live panel into a sticky spine.** Not sub-tabs (they hide go-live status while you fix cast — wrong for a "make it all green" task); not a wizard-as-primary (config is *revisited*, per Q-AUD-2). Scaffolding is already half-built — `sectionRefs` + `jumpToSection` exist ([ProjectEditor.tsx:117](../../../channels/ticketing-ui/components/settings/projects/ProjectEditor.tsx#L117)) and the go-live "Fix" links already jump. So: **pin the go-live panel as a left rail (≥1280px) / top bar (14″ fallback), make it progress + nav, and make long sections (cast, packages) collapsible.** One move fixes "where am I" (D4) *and* the go-live UX (D5).
> **Claude → Q-IA-2 reco: consistent, explicit, per-section save with dirty/saved state.** Not one global "Save project" (couples everything onto one flaky-4G round-trip); not full auto-save (restaffing is consequential — silent persist on a dropping link half-writes state). Generalise the *existing* "Save workflows / Save messaging" pattern to every section: **"Unsaved changes" pill → Save → "Saved ✓"**, plus warn-on-leave when dirty. Sole exception: the activate/deactivate toggle stays immediate (D6).
>
> **🎨 Prototype (2026-07-30) — [interactive mockup: `04_projects_packages_redesign.html`](04_projects_packages_redesign.html)** (open in a browser — standalone, no server). The mockup **refines the reco one step further**: instead of a single collapsible page, it uses a **two-pane console** — a sticky left rail that *fuses the go-live checklist with section nav* (each row carries a binary pass/blocker/optional dot + value summary) and a right pane showing **one section at a time**. This kills the scroll more decisively than collapsing, and it neutralises my original anti-tab objection ("tabs hide go-live status") because the rail shows every section's status permanently. Built on the real app palette (light-only, blue/red/amber/green/violet per `02_design_system.md`) and embeds the locked decisions: **binary go-live** (D5), **Inherited/Overridden/⚠ Unstaffed** badges (D3), **per-section save state** (D4), **guarded Deactivate** (D6), **BS dates** (Q-LOC-2), and the 2026-07-30 staffing model (**§13**): **author-named tiers**, the **position-first two-step picker** (position → person), **seat anchor + Reassign**, and the **narrow-first scope stepper**. **Done since:** per-lot override in Packages (same §5A two-step) + "required" badges on author-marked tiers; the **authoring side** is mocked in [`06_workflows_step_cast_editor.html`](06_workflows_step_cast_editor.html). **Next:** port the mockups to the real components (`ProjectEditor.tsx` + the Workflows step editor).

---

## 8. D5 — System status & feedback (go-live)

**Current state.** Panel reads **"9 passed · 4 warnings"** next to a green **"Can activate · Tickets OK"**. Four yellow warnings (Default workflow, SEAH workflow, Classification coverage, Project locations) each say "Fix"; "Package QR tokens" is grey/optional. All warnings render with the same weight.

**Shortcomings (ranked):**
1. **Mixed signal** — green "Can activate" beside four yellow "Fix" warnings. Can I go live or not? A cautious user freezes; a hurried one learns to ignore all yellow.
2. **No severity model** — "Default workflow" (routing silently falls through if unset) looks identical to "QR tokens (optional, cosmetic)." Consequence of ignoring each is invisible.
3. **No "what happens if I activate now"** — the cost of going live with warnings is unstated.

> **✅ Q-GL-1 — Severity tiers.** Split warnings into **Blocks activation / Degrades quietly / Optional**, with distinct visuals + a plain-language consequence per item? Confirm which current checks are truly blocking vs. advisory (I can derive from [`project_go_live.py`](../../../ticketing/services/project_go_live.py) once you confirm intent).
> **✅ Q-GL-2 — Language.** Should each check carry a one-line "why this matters / what breaks" in Nepali-simple English (+ `ne`)?
Response: we need to review our warnings with simple pass or go, no warnings anymore
>
> **Claude → ✅ decided (Q-GL-1/2).** Collapse the 3-tier idea to **binary: every check is either a hard blocker (must be green to activate) or it leaves the gate entirely** — no middle "warning". Reclassify the four current yellows (to confirm against [`project_go_live.py`](../../../ticketing/services/project_go_live.py)): *Default workflow* = **blocker** (routing falls through without it); *SEAH workflow* = blocker **only if** the project has a SEAH stream, else N/A; *Classification coverage* = **not** a blocker when a Default catch-all exists (that is what the catch-all is for); *Project locations* = blocker **if** routing needs it. QR drops off entirely (not this screen — D8). A blocked check states the one thing to fix; no severity prose.
> **⤷ Update (2026-07-30):** the key staffing gate is now *"every step's **required** cast tiers staffed"* (actor always; plus author-marked supervisor/participant/observer), not "every level has ≥1 officer" — see [doc 13 §7 A4](../13_projects_and_packages.md) and §13.

---

## 9. D6 — Error prevention & safety

**Current state.** **`Deactivate`** is a plain text link immediately beside the project title, no visible confirmation guard **[verify]**. Silent inheritance (D3) is itself a safety issue. Multiselects (classifications) and org/officer assignment offer little in-context validation feedback beyond the go-live panel far above.

**Shortcomings (revised on review):**
1. **`Deactivate` guard + placement** — **[verified]** one-click toggle with **no confirmation** ([`toggleActive`, ProjectEditor.tsx:121](../../../channels/ticketing-ui/components/settings/projects/ProjectEditor.tsx#L121)), sitting next to the title. But it is **reversible** (flips `is_active` back) — so *not* destructive; "destructive-ish" was too strong. Fix = placement + a light guard, not danger-zone treatment.
2. **Silent misconfiguration** — unstaffed/inherited lots (D3) and unset default workflow (D5) fail quietly, not loudly. (Addressed by Q-SAFE-2 = yes + the go-live blockers in D5.)

> **✅ Q-SAFE-1 — Deactivate.** Add confirmation + state what deactivation does to in-flight tickets? Move it out of the title bar (into an overflow/danger zone)? Rename to something unambiguous in EN/NE? Response: what world do you suggest in English?
>
> **Claude → keep the word "Deactivate"** — it pairs cleanly with the panel's existing **"Activate"** and admins know it. The label isn't the problem; **placement + a one-line guard** are. Move it off the title bar to sit beside the go-live Activate action, and add a confirm: *"Stop accepting new grievances? Existing tickets are unaffected — you can reactivate anytime."* If you want a softer verb, **"Pause intake"** is the honest alternative (it literally stops intake), but I'd keep Activate/Deactivate for symmetry. ✅ **Q-SAFE-2 (inline field validation) = yes**, noted.
> **✅ Q-SAFE-2 — Inline validation.** Should errors surface *at the field* (e.g. "no L1 officer for this lot") in addition to the top go-live panel? Response: Yes

---

## 10. D7 — Data entry & search

**Current state.** Location search box: "Search province, district or municipality…". Officer/org/project names are free text. No romanisation-tolerance or Devanagari-normalisation logic seen in source **[verify]**.

**Shortcomings (ranked):**
1. **Place-name romanisation** — Kakarbhitta / Kakadbhitta / Kakarvitta / काकडभिट्टा. If search is exact Latin match, admins "fail" to find locations that exist → duplicate/blank entries.
2. **Devanagari round-trip** — can officer/project/lot names be *entered* and *displayed* in Devanagari cleanly (search, sort, truncation)? Unverified.

> **✅ Q-SEARCH-1 — Location search tolerance.** Do we need fuzzy/alias matching + Devanagari↔romanised search over the location table? (Depends on whether the seeded location set already carries `name_ne`/aliases — I can check.) Response : Yes - we already have the helpers in place
> **✅ Q-SEARCH-2 — Devanagari input.** Are project/lot/officer names expected in Nepali, English, or both? (Feeds Q-LOC-1c.) - Response: Englisg or roman scripts
>
> **Claude →** ✅ Then the build task is just **wiring the existing helpers into the location search box** and confirming it's live — not new logic. And English/roman-only names mean **no Devanagari input path** is needed, which reinforces Q-LOC-1 = English-only. (Data entry limited to super-admin from proven sources further shrinks the risk — your D7 note.)

---

## 11. D8 — Domain fit & discoverability

**Current state.** **Per-package QR tokens** are buried at the bottom of Geography, greyed as "Optional". Real GRM role identity is hidden behind generic tiers (D2). "Implementing agency / Donor" folded into the actors table (recent, good — [git `8233a36b`]).

**Shortcomings (revised on review):**
1. ~~**QR intake under-sold**~~ — **RETRACTED (Q-DOM-1): Claude was wrong.** QR is a top-level main-menu feature for all users; I misread a go-live checklist row as the feature's home. Struck.
2. ~~**GRM roles hidden**~~ — **RETRACTED (see D2 / Q-TERM-1):** the generic tiers are intentional; level names carry the domain meaning. Struck.

> **✅ Q-DOM-1 — QR prominence.** Promote per-package QR to a first-class feature (with print/preview)? Is QR actually in the demo/field plan, or speculative? (Sets whether we invest.) Response: This is completely a wrong assessment. QR are accessible from the main menu to any users. All users have access to QR codes, it is at the same level than Settings/
>
> **Claude →** Conceded — my assessment was wrong. QR is a **top-level main-menu feature** available to all users; the "Package QR tokens" line I flagged is only an *optional config check inside the go-live panel*, not the feature's home. D8 struck.

---

## 12. D9 — Accessibility & device / network reality

**Current state.** Status conveyed via green/yellow/grey dots + text labels. Heavy single page. Target deployment includes district offices with cheaper hardware and patchy connectivity.

**Shortcomings (ranked):**
1. **Colour-carrying-meaning** — green-vs-yellow dot distinction is subtle on low-quality monitors; text labels partially rescue it but the at-a-glance signal is colour.
2. **Heavy page + fragmented saves** amplify pain on slow connections (D4) — a dropped save mid-scroll loses work.





> **✅ Q-A11Y-1 — Do we set an accessibility/device floor** (min contrast, non-colour status cues, works on ~1366px + slow 3G) as an explicit acceptance criterion for the redesign, or defer? Response: connection speed is more slow 4G than slow 3G so I dont think is a major issue. People use basic sub 1000 USD laptops, with 14 inch screens, so that should be our benchmark
>
> **Claude → ✅ floor locked: 14″ / ~1366px, sub-$1000 laptop, slow 4G.** Bandwidth de-prioritised; the real acceptance criterion is **fits and stays usable at 1366px** — which is also why D4 keeps sections collapsible. Colour-only status (shortcoming #1) stays a minor note: keep text labels alongside the dots.

---

## 13. Staffing assignment — decisions folded in (2026-07-30)

Made during the D4 mockup work; they postdate Draft 2. **Authoritative** in [doc 13 §5A](../13_projects_and_packages.md) (assignment) and [doc 12 §6.2](../12_workflows_configuration.md) (workflow cast) — summarised here so this review stays the single reference.

- **Q-STAFF-1 — Position-first, two-step assignment.** Filling any staffing slot is **position → person**: choose the seat (position type @ org unit) within a **narrow-first location scope** (the package's municipality, auto-climbing to district → province until officers exist; admin can widen/narrow), then the officer holding it. Escape hatches: **invite** into the position if vacant; **create** the position if missing. No free officer search, no competing CTAs. → doc 13 §5A.
- **Q-STAFF-2 — Author-named + mandatory tiers.** The workflow author **names each cast tier per step** (`tier_labels`, e.g. L1 actor = "Safeguard Officer", L3 actor = "GRC Chairman") and **marks which of supervisor / participant / observer are mandatory** (`required_tiers`); the **actor is always required**. The staffing UI shows the author names, never generic tier words. **Go-live blocks on any *required* tier unstaffed** (doc 13 §7 A4). → doc 12 §6.2.
- **Supersedes Q-TERM-1's "keep Actor/Supervisor labels":** the display now uses the author's per-tier names; the 4-tier abstraction stays **engine-only**.
- **Continuity:** a filled slot records the **anchored seat** + the officer; on transfer, **Reassign** re-points the seat's new holder in one step.

**Mockup coverage:** Staffing pane rebuilt to all of this (author-named slots, position-first picker, seat anchor + Reassign, narrow-first scope stepper). **Done since (2026-08-02):** the per-lot **override in Packages** now uses the same §5A two-step, and **"required" badges** show on author-marked tiers — both former "pending" items are complete. The **authoring side** — where the workflow author binds roles, names each tier, and marks required — is mocked at [`06_workflows_step_cast_editor.html`](06_workflows_step_cast_editor.html) (doc 12 §6.2).

---

## Appendix A — Consolidated question list (answer by id)

| Q-id | Dim | Question (short) | Answer |
| --- | --- | --- | --- |
| Q-AUD-1 | — | Optimise for consultant / DOR-staff / two modes? | ✅ Org-admins only; two modes already specced |
| Q-AUD-2 | — | Setup one-time or recurring? | ✅ Recurring; org-level only (lower ranks just invite officers) |
| Q-LOC-1 | D1 | Nepali UI scope? | ✅ (a) English-only — no `<Bilingual>` here |
| Q-LOC-2 | D1 | Bikram Sambat dates? | ✅ **BS-only** (not dual) |
| Q-LOC-3 | D1 | Localisation priority? | ✅ Moot for translation; folds into Q-LOC-2 |
| Q-TERM-1 | D2 | Real GRM titles vs. generic tiers? | ✅ **Evolved (§13):** author names each tier per level; UI shows those names; abstraction engine-only |
| Q-TERM-2 | D2 | De-jargon UI copy? | ✅ OK |
| Q-TERM-3 | D2 | SEAH phrasing? | ✅ Keep "SEAH" as-is |
| Q-CAST-1 | D3 | Inherited/Overridden/Unstaffed badges? | ✅ Yes (higher priority — override is the norm) |
| Q-CAST-2 | D3 | Override common or edge-case? | ✅ The **norm** (L1/L2 pkg, L3/L4 project) |
| Q-IA-1 | D4 | Single scroll vs. tabs/stepper? | ✅ Single page + sticky go-live spine + collapsible sections |
| Q-IA-2 | D4 | Save model? | ✅ Per-section explicit save + dirty/"Saved ✓" |
| Q-GL-1 | D5 | Go-live severity tiers? | ✅ **Binary** pass/blocker — no warnings |
| Q-GL-2 | D5 | Per-check consequence copy? | ✅ Blocked check states the one fix; no severity prose |
| Q-SAFE-1 | D6 | Deactivate word/guard? | ✅ Keep "Deactivate"; fix placement + add guard |
| Q-SAFE-2 | D6 | Inline field validation? | ✅ Yes |
| Q-SEARCH-1 | D7 | Fuzzy/Devanagari location search? | ✅ Yes — wire existing helpers |
| Q-SEARCH-2 | D7 | Names in NE / EN / both? | ✅ English/roman only |
| Q-DOM-1 | D8 | Promote per-package QR? | ✅ Retracted — QR already top-level |
| Q-A11Y-1 | D9 | Device/accessibility floor? | ✅ 14″/1366px, slow 4G |
| Q-STAFF-1 | §13 | How is a staffing slot filled? | ✅ **Position → person**, narrow-first scope; invite/create hatches (doc 13 §5A) |
| Q-STAFF-2 | §13 | Which tiers are named / required? | ✅ Author names + marks mandatory per step; actor always (doc 12 §6.2) |

## Appendix B — Decisions log

_Reviewed 2026-07-24 (Draft 2). Format: Q-id · decision · rationale._

- **Q-AUD-1/2** — Audience is **org-admins only**, English-fluent, who reconfigure over the project's life. → retires D1 translation; keeps D4 free-form (not wizard).
- **Q-LOC-1/3** — **English-only** on this screen; no `<Bilingual>` adoption. Names in English/roman.
- **Q-LOC-2** — **BS-only.** All dates render in Bikram Sambat (not dual); AD added later only if a donor-facing export needs it.
- **Q-TERM-1** — **Keep the Actor/Supervisor/Participants abstraction** in the engine; do **not** resurrect roles. D2 #1 retracted. **Evolved 2026-07-30 (§13):** the UI now shows the **author's per-tier name** per level ("Safeguard Officer", "GRC Chairman"), not "Actor/Supervisor"; the abstraction stays engine-only.
- **Q-TERM-2** — **De-jargon approved** (cast→staffing, catch-all→"used when nothing else matches", inherit→"applies to every lot unless overridden").
- **Q-TERM-3** — Keep "SEAH" as-is.
- **Q-CAST-1/2** — Override is the **norm**; surface **Inherited / Overridden / ⚠ Unstaffed** badges per lot level; consider an L1/L2-package + L3/L4-project default template.
- **Q-IA-1** — **Single page + sticky go-live spine** (reuse existing `jumpToSection`) + collapsible sections. No sub-tabs, no wizard-as-primary.
- **Q-IA-2** — **Consistent per-section explicit save** with dirty + "Saved ✓" state; warn-on-leave. Toggle stays immediate.
- **Q-GL-1/2** — Go-live becomes **binary pass/blocker**, no warning tier; reclassify the four current yellows; blocked checks state the single fix.
- **Q-SAFE-1** — Keep the word **"Deactivate"** (pairs with "Activate"); fix **placement + add a one-line confirm**. Verified: currently no guard, but reversible.
- **Q-SAFE-2** — **Inline field-level validation = yes**, alongside the go-live gate.
- **Q-SEARCH-1/2** — Wire **existing search helpers** into the location box; English/roman names only (no Devanagari input).
- **Q-DOM-1** — **Retracted** (Claude error): QR is already a top-level, all-user feature.
- **Q-A11Y-1** — Device floor: **14″ / ~1366px, sub-$1000 laptop, slow 4G**.
- **Q-STAFF-1 (2026-07-30)** — **Position-first, two-step** assignment (position → person), **narrow-first** location scope (municipality auto-climbing to district/province), invite/create escape hatches. → doc 13 §5A.
- **Q-STAFF-2 (2026-07-30)** — Workflow author **names each tier per step** and **marks supervisor/participant/observer mandatory** (actor always required); go-live gates on **required** tiers. → doc 12 §6.2.
- **Q-WF-1 (2026-08-02)** — **"Stream" is dead.** The screen shows **one card per workflow**: a **name the admin chooses** + the **published workflow** it uses — the project never inherits the workflow's own name. The fixed slot vocabulary (safeguards/hazards/CA/SEAH) had already been dropped in code (migration `c5e7f9a1`); the mockup was following a stale doc 12. → doc 12 §1/§2, doc 13 §5B, [ui/05 §4](05_ui_copy_style.md).
- **Q-WF-2 (2026-08-02)** — **Default first, then the rest.** The default workflow is its own block at the top ("used when nothing else matches"); everything else is added under it. Choosing it is step 1 of the section.
- **Q-WF-3 (2026-08-02)** — **Classifications is no longer a section.** Category routing lives **on the workflow card** it applies to (chips), next to the chatbot menu, so all routing for a project is one screen. → doc 13 §5 order (9 sections → 8), §5B.
- **Retractions kept inline for the record:** D1 #1/#3 (translation), D2 #1 (role labels — narrowed then superseded by §13), D8 #1/#2 (QR + roles).

## Appendix C — One-sentence thesis

After review, the language axis largely **falls away for this screen** (org-admin audience is English-fluent). What remains, ranked: make the **inherit/override staffing model visible** (D3 — override is the *norm*, so this is now the top fix), give go-live **binary clarity** (D5), turn the go-live panel into a **sticky nav spine** with a **consistent save model** (D4), **de-jargon** the copy (D2), and guard **Deactivate** (D6). The last open decision is now closed: dates are **Bikram Sambat–only** (Q-LOC-2). Two Draft-1 findings were wrong and are retracted (QR discoverability; and the role-label critique, which the intentional workflow-agnostic abstraction correctly answers). **Folded in 2026-07-30 (§13):** staffing is **position-first** (position → person, narrow-first scope) and tiers are **author-named + author-marked-mandatory** — which is how the D2 terminology critique is ultimately resolved.
