# UI copy & plain-language guide (officer / admin portal)

**Status:** authoritative (2026-07-30). The **single source for on-screen wording** in `channels/ticketing-ui`. Consolidates the cross-cutting "Language / legibility pass" ([DESIGN §2.3](../../sprints/2026-07_org_chart_positions/DESIGN-settings-redesign.md)) and the de-jargon decisions from the Projects & packages review ([ui/04 §13](04_projects_packages_ux_review.md), [doc 12 §6.2](../12_workflows_configuration.md)).
**Referenced by:** [docs/README.md](../../README.md) and [02_design_system.md](02_design_system.md).
**Scope:** governs **user-facing strings** (labels, help text, buttons, empty states, errors). Internal specs may use precise technical terms (e.g. "seat", "tier") *with a definition*; those terms should not surface verbatim in the UI.

> **Worked reference:** the Projects & packages mockup [`04_projects_packages_redesign.html`](04_projects_packages_redesign.html) is kept consistent with this guide.

> **⚑ WHO WE WRITE FOR — Nepali government officials.** Every screen is read by a career civil servant in a Nepal district or ministry office: capable and experienced, but reading **English as a second language** and **not technical**. So the standard for all copy is **simple, short, and straightforward** — plain everyday words, one idea per sentence, no cleverness. **When two words both fit, always choose the simpler, more common one.** If a sentence needs a second read, rewrite it. This is the primary test for everything below.

---

## 1. Audience & language

- **The reader is a Nepali government official** — a career civil servant in a district or ministry office. Competent and experienced, but reading **English as a second language** and **not technical**. Write **plain, short, concrete English; when two words fit, use the simpler, more common one.** This is the primary test for every string. (Q-AUD-1, [ui/04 §2](04_projects_packages_ux_review.md).)
- **English is the source of record.** The Nepali (`ne`) overlay via `<Bilingual>` is for **complainant-facing** surfaces and **name fields** where a real `_ne` exists — **not** the admin editor (Q-LOC-1). Never fabricate Nepali.
- **Dates: Bikram Sambat only** on these surfaces (Q-LOC-2). Format `15 Shrawan 2082 BS`. No Gregorian on-screen.

## 2. Voice & tone (the rules)

1. **Plain words over jargon.** If a career GoN officer wouldn't say it, don't write it — see the glossary (§4).
2. **Sentence case.** Not Title Case; ALL CAPS only for tiny eyebrow labels.
3. **Active voice; name the outcome.** A button says what it does ("Save", "Activate", "Assign"); the toast confirms it ("Saved", "Project activated").
4. **Short.** One idea per sentence; help text ≈ ≤15 words.
5. **No developer copy** (F10/F11): no slugs, table/field names, HTTP codes, or "run migrations". Roles via `RoleLabel` (slug → `display_name`); errors via `formatUserFacingError` + one `ErrorNotice` — never raw `API 409 {…}`.
6. **Severity in words, not colour alone** (F11): write "Blocks go-live", don't rely on a red dot. (Low-literacy + colour-blind + cheap monitors.)
7. **Define or avoid acronyms** on first use — the one exception is **SEAH**, kept as-is by decision (Q-TERM-3).
8. **Give the one-line *why*** where a rule isn't obvious ("A default is used for grievances that don't match any category").
9. **Responsibility → "in charge of".** For *who is responsible for something*, write **"in charge of X"** — natural bureaucratic English that matches "officer in charge (OIC)". Avoid **"manages X"** (vague) and **"handles X"** (informal). Long-form alternative: "responsible for X". For an *action* an officer performs, use the plain active verb instead (**works · resolves · escalates · reassigns · oversees**), not a responsibility phrase.
10. **No description when it's self-explanatory.** If a button or section title already carries the meaning (a canonical §4.1 word does the work), add **no** help text. Add a line only when it prevents a real error or ambiguity — then one short sentence, reusing glossary words. Every extra sentence is a tax on a second-language reader. *(This is why, e.g., the position picker has no explanatory caption.)*

## 3. Buttons & actions

- Label = the outcome, imperative: **Save · Save & next · Next · Cancel · Activate · Deactivate · Assign · Invite & assign · Override with this officer · Create a new position**.
- Consequential/destructive actions get a one-line confirm stating the effect: *"Stop accepting new grievances? Existing tickets are unaffected — you can reactivate anytime."*

## 4. Glossary — preferred wording (avoid → use)

**Must** (these are jargon/metaphor; do not surface them):

| Avoid (internal / jargon) | Use on screen |
|---|---|
| cast · the ladder · shared staffing | **staffing** / "who works each level" |
| tier (as a UI word) | the **role's name** (author-named, e.g. "Safeguard Officer") |
| Actor / Handles it (generic) | the workflow's **named role** for that step |
| catch-all / default binding | **"used when nothing else matches"** |
| binding · slot (internal) | **workflow** / **level** |
| stream · intake stream (dead model, [12 §1](../12_workflows_configuration.md)) | **workflow** — the name the admin gave it |
| intake route (internal) | **"chatbot menu"** — the menu the complainant picked |
| seat · anchor | **position** (position type @ office) |
| handler pool · provenance | **"whoever handles Level N"** |
| reach (as a control label) | **"Search area"** |
| taxonomy | **categories** |
| entity | **organization** |

**Recommended** (plainer is better; confirm before a project-wide rename):

| Current | Plainer |
|---|---|
| "Inherited from project" | "Same as project" |
| "Overridden here" | "Set for this lot" |
| "Unstaffed" | "Not staffed" |
| "applies to every lot unless overridden" | "used for every lot unless you set a different one" |

**Keep — correct domain terms:** lot · package · chainage (Km) · GRC *(expand once: Grievance Redress Committee)* · implementing agency · donor · province / district / municipality · SEAH.

### 4.1 Canonical vocabulary — one word per concept (project-wide)

Use the **same word for the same thing on every screen.** This short list is the shared vocabulary; extend it (don't fork it) when a new recurring concept appears.

| Concept | Use | Don't use |
|---|---|---|
| A person's complaint (the record) | **grievance** | complaint, issue, case, ticket † |
| The person who filed it | **complainant** | citizen, user, grievant |
| A GRM staff member | **officer** | user, agent, staff, actor |
| A partner body (DOR, ADB, contractor) | **organization** | org, entity, agency, party |
| A financed road intervention | **project** | scheme, programme |
| A lot / contract within a project | **package** (a.k.a. **lot**) | segment |
| Admin geography | **province · district · municipality** | region, zone, area |
| The escalation chain | **workflow** | flow, process, pipeline |
| A stage in a workflow | **level** (L1–L4) | step †, stage |
| The people set to work the levels | **staffing** | cast, roster |
| A job at a level (workflow-named) | **role** (its author name, e.g. "Safeguard Officer") | tier, actor |
| A titled seat an officer holds | **position** | seat, post |
| Put an officer on a level | **assign** | allocate, attach, map |
| Bring a new officer into the system | **invite** | add user, onboard, register |
| Make the project live | **activate** | publish, enable |
| The readiness checks before activating | **go-live** | launch readiness |
| Move a grievance up a level | **escalate** | bump, promote |
| Give a grievance to another officer | **reassign** | transfer, hand off |
| Oversee a level (alerted on escalation; can reassign) | **oversees** (verb) · **supervisor** (noun) | manage, manager, handles escalations, handler |
| End a grievance with an outcome | **resolve** | close, complete |

† *Internal / code term — never surface it:* "ticket" (code name for a grievance record), "step" (code name for a level).
**Decided 2026-07-30:** always **grievance** (never "case") and **resolve** (never "close"); "ticket" stays code-only.

- **Empty state** = what it is + the single next action: *"No locations linked yet. Search to add one."* — no dev copy.
- **Error** = what went wrong + how to fix, no codes (route through `ErrorNotice`).
- **Help text** sits under the section/field title; one plain sentence.

## 6. Dates & numbers

- Bikram Sambat only: `15 Shrawan 2082 BS`. Chainage `Km 0+000`. Use tabular numerals where digits align in columns.

## 7. Enforcement

- Any user-facing string goes through the helpers above (`RoleLabel`, `formatUserFacingError`/`ErrorNotice`, `<Bilingual>` where `_ne`).
- New/changed screens: check copy against §2 + §4 before merge.
