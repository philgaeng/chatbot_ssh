# Work items — intake, classification, and gates

**Status:** authoritative (2026-09-06) — ⚠ **adopted, mostly in force.** §11 rows 1, 3, 4, 5, 6 and 7 are closed; **rows 2 and 8 are not** — there is still no roadmap (OM-05) and the tracker is available but unwired (OM-07). §11 lists exactly which, and what closes each. Nothing here supersedes an existing standard; it decides **which of them apply to a given piece of work, and when that is decided.**
**Last updated:** 2026-09-06 — §11 rows 5 and 6 close: the design gate is written into `05_frontend.md` §9a and the verification ladder into `06` §4a. Earlier the same day, rows 3 and 4 closed: the register test runs in CI (ten checks), and the sensitive-path question moved to intake — rule 4.3 is in force, with an empty profile on a `ready` row now a test failure. Earlier: sprint citations removed (lifecycle §10.1 — this is a public spec); §1.2/§5 reconciled (a chore gets no register row, Q-08); §11 rows 1 and 7 close with `SPINE.md`. Earlier: `G-RELEASE` gains the version-tag requirement; §11 row 8 closes on D-009/D-010.
**Audience:** public.
**Reads with:** [`00_engineering_index.md`](00_engineering_index.md) (the ten rules and the shared definition of done) · [`06_documentation_lifecycle.md`](06_documentation_lifecycle.md) (tiers, promotion, honesty markers) · the standing deferral rule (the standing deferral rule).

---

## The one idea

> **What kind of thing it is** decides where it is filed and who says yes.
> **What it touches** decides how much process it gets.

Those are two axes and they must not be collapsed. Ceremony attached to the *label* — "bugs get the light process" — gets it backwards: a four-line fix on the SEAH intake path deserves more scrutiny than a new admin column. Attached to **blast radius**, it is right by construction, and it is the rule this project already applies to model selection ([`../../AGENTS.md`](../../AGENTS.md): *"A four-line change to the SEAH intake is still Opus"*). This standard applies it to process.

**This adds no new checks.** Every gate in §3 already exists somewhere in this folder, in the PR template, or in CI. What changes is that the applicable set is **derived at intake**, when it can still shape the plan, instead of being remembered at merge.

---

## 1. Three levels

**Rule 1.1 — There are exactly three levels: roadmap, lane, item.** More levels is Jira; fewer cannot express "why are we doing this at all".

| Level | Grain | Home |
|---|---|---|
| **Roadmap** | outcomes, quarters | `docs/ROADMAP.md` ⚠ *not built* |
| **Lane** | a sprint (a themed batch sharing one design and one questions register), **or** the standing lane | `docs/sprints/<sprint>/`, or no folder at all — every lane's items appear in [`SPINE.md`](../SPINE.md) |
| **Item** | one unit of merge — one PR, one observable outcome, one gate profile | a row in the register; a spec file only if its profile requires one |

**Rule 1.2 — Not everything gets a sprint.** A sprint is for work that shares a design and a set of questions. A bug or a small deviation goes in the **standing lane**: a register row and a PR, with no folder, no design note and no questions register. ⭐ **A chore gets no row at all** — a PR and a one-line rationale (decided 2026-09-04): a register that fills with dependency bumps stops being read, and rule 6.1's whole claim is that every row is actionable. ⚠ **Exception, found on first use: a chore carrying `+SENSITIVE` DOES get a row.** `GRM-001` is a dependency bump — the most chore-shaped change there is — and it carries a middleware bypass in the officer portal. Rule 4.2 says the modifier is never waived by kind or by size; a no-row rule that swallowed it would waive it by kind through the back door. *Why: before this rule, small work had two options — justify a sprint folder, or be invisible. Both are wrong, and the second is what actually happened.*

**Rule 1.3 — A sprint is a view over items, not a second registry.** Sprint folders hold the detail; the register holds every open item across all lanes. *Why: five separate registries is the condition this standard exists to end (§11).*

## 2. The five kinds

**Rule 2.1 — Every item has exactly one kind, assigned at intake.**

| Kind | Definition | Who says yes |
|---|---|---|
| **Feature** | The system does not do this yet. A live spec will gain content. | the owner |
| **Bug** | The system does not do what a **live spec already says** it does. | nobody — a bug is pre-approved |
| **Deviation** | The **spec** is wrong: the code does something the spec does not describe, or the design proved wrong mid-build. Resolves by moving *either* the code or the spec. | the owner, on the fork only: which side moves |
| **Debt** | Known-wrong-but-working, deliberately deferred. | already decided at deferral; needs scheduling only |
| **Chore** | No behaviour change: dependency bumps, CI, refactor with no semantic change, doc fixes. | nobody |

**Rule 2.2 — The kind is decided by four questions, in order:**

1. **Does a live spec already claim this behaviour?** No → **Feature.** Yes → continue.
2. **Does the code disagree with that spec?** Yes, and the spec is right → **Bug.** Yes, and the spec is wrong → **Deviation.**
3. **Is anything a user could observe changing?** No → **Chore.**
4. **Are we choosing not to fix it now?** Yes → **Debt** — and the standing deferral rule applies: `followups/<slug>.md` **and** a register row, in the same commit (the standing deferral rule).

**Rule 2.3 — If you are fixing a bug and find yourself editing a spec, it was not a bug — it was a deviation. Reclassify it.** *Why: that edit is the moment the fork appears, and a fork decided silently inside a bugfix is how a spec acquires a change nobody agreed to. Bugs carry no spec gate precisely so that this cannot happen by accident.*

**Rule 2.4 — Classification is cheap and revisable.** Getting it wrong costs a re-label, never a re-plan. *Why: hesitation at intake is how items stop being filed at all, and an unfiled item is worse than a misfiled one.*

**Rule 2.5 — Record the origin** alongside the kind: user request · review finding · incident · agent discovery · external requirement (ADB / DPG / DOR). *Why: it is the only way to audit whether reviews and incidents actually produce work. They do here — HR-01…07 trace to `reviews/devils_advocate_codebase.md`, and QA-01 to the 2026-09-04 deploy outage — and that property is worth being able to demonstrate.*

## 3. The nine gates

| Gate | Fires when | What it requires | Defined in |
|---|---|---|---|
| **G-PRODUCT** | user-visible behaviour is new or changes | a design note; a questions register where **each question carries a recommendation**; blocking questions answered before work starts | sprint `DESIGN-*.md` + `QUESTIONS.md` |
| **G-DESIGN** | a UI surface changes shape | brief → IA → wireframe → direction → state/responsive contract → **implementation contract frozen before build** | [`05_frontend.md`](05_frontend.md) |
| **G-DATA** | the schema changes | correct Alembic stream; replays from empty; no FK from `ticketing.*` into `public.*`; no PII in `ticketing.*` | [`01_database.md`](01_database.md) |
| **G-SENSITIVE** | PII · auth · SEAH · a live complainant channel · a new external egress | Opus; boundary tests named in the item; isolation reviewed **separately from correctness** | [`../../CLAUDE.md`](../../CLAUDE.md) data rules · `.github/PULL_REQUEST_TEMPLATE.md` |
| **G-CONTRACT** | an API or event shape changes | the contract updated, plus an explicit compatibility statement | [`03_api_layer.md`](03_api_layer.md) · [`../services/01_api_contracts.md`](../services/01_api_contracts.md) |
| **G-SPEC** | any behaviour change | an `Amends:` line naming spec + section; the edit rides the same PR | [`06_documentation_lifecycle.md`](06_documentation_lifecycle.md) §3 |
| **G-TEST** | always | the right level per the pyramid. For a **bug**, a failing regression test written **first** | [`04_testing.md`](04_testing.md) |
| **G-VERIFY** | user-visible behaviour | E2E / browser evidence, **or** an explicit `⚠ Not verified end-to-end` marker | [`06_documentation_lifecycle.md`](06_documentation_lifecycle.md) §4 |
| **G-RELEASE** | anything deployed | migration order; rollback note; staging before production; smoke check. **A production deploy cuts a version tag** ([D-009](../DECISIONS.md)) ⚠ *not built — OM-09* | [`../deployment/03_operations.md`](../deployment/03_operations.md) |

## 4. Deriving the profile

**Rule 4.1 — The gate profile is computed at intake from six questions, not chosen.**

```
Does it change user-visible behaviour?      → G-PRODUCT · G-SPEC · G-VERIFY
Does a UI surface change shape?             → G-DESIGN
Does the schema change?                     → G-DATA
Does it touch PII / auth / SEAH /
  a complainant channel / a new egress?     → G-SENSITIVE
Does an API or event shape change?          → G-CONTRACT
Is it deployed?                             → G-RELEASE
(always)                                    → G-TEST
```

**Rule 4.2 — ⭐ G-SENSITIVE is never waived by kind or by size.** A one-line change is not a chore if it touches that list. *Why: this is the whole point of deriving from blast radius. Every exception ever granted here has been granted on the basis of diff size, which is not correlated with risk.*

**Rule 4.3 — The sensitive-path question is answered at intake, not at merge.** ✅ **In force 2026-09-06** — the PR template keeps its checklist as a **confirmation** and names the item and profile it confirms; it is no longer the first time anyone asks. *Why: at PR time the answer changes nothing — the design is written, the model was already chosen, the tests already exist or do not.*

## 5. The six profiles

Presets produced by §4. A preset is what people actually use; the derivation is what makes it defensible.

| Profile | Gates | Artifacts | Typical size |
|---|---|---|---|
| **UI feature** | PRODUCT · **DESIGN** · SPEC · TEST · VERIFY · RELEASE (+DATA/CONTRACT if applicable) | design note · questions answered · frozen implementation contract · spec edit · e2e case | L |
| **Backend feature** | PRODUCT · SPEC · TEST · VERIFY · RELEASE (+DATA · +CONTRACT usually) | design note · questions answered · spec edit · integration test | M–L |
| **Schema / migration** | **DATA** · SPEC · TEST · RELEASE | migration in the owning stream · replay-from-empty evidence · spec edit · rollback note | S–M |
| **Bug** | **TEST** · VERIFY · RELEASE | reproduction · failing test first · fix · **no spec edit** (see 2.3) | S |
| **Deviation** | PRODUCT *(the fork only)* · **SPEC** · TEST (+ DATA / SENSITIVE / CONTRACT as they apply) | which spec + section · which side moves and why · a [`../DECISIONS.md`](../DECISIONS.md) entry if it is a real fork | S–M |
| **Chore** | TEST | a one-line rationale in the commit — **and no register row** (§1.2) | XS |

Read **Bug** against **Deviation**: a bug carries no spec gate because the spec was right; a deviation is almost nothing but a spec gate because the spec was wrong. The four-question test tells you which one you are in, and everything else follows.

**Modifiers, applied on top of any profile:**

- **+SENSITIVE** — per rule 4.2.
- **+INCIDENT** — work born from a production failure. Adds a timeline, and a **"what would have caught this"** line which becomes its own item. *Why: QA-01 is this shape — its scope is "make the failure mode survivable and loud", while the actual cause became QA-02. Splitting the two is what stops an incident fix from quietly becoming an architecture project.*

## 6. Definition of ready

**Rule 6.1 — An item enters the register only when it is ready. Everything before that is an inbox entry, not a plan.** *Why: a register whose every row is actionable is worth reading; Jira's failure mode was 800 rows in which nobody could find the twelve that mattered.*

| Kind | Ready means |
|---|---|
| **Feature** | design note written · every **blocking** question answered · profile assigned · non-goals stated · the files it may touch listed |
| **Bug** | a reproduction · **the spec line it violates** (if you cannot name one, it is a deviation) · expected vs actual |
| **Deviation** | which spec, which section · the proposed resolution (code moves, or spec moves) · whether it is a real fork needing a `DECISIONS.md` entry |
| **Debt** | measured inventory · definition of done · endgame — *already required by the standing deferral rule* |
| **Chore** | a one-line rationale. Nothing else. |

**Rule 6.2 — The ready bar is higher here than on a human team, deliberately.** A person holding a half-specified ticket asks a question and loses ten minutes. **An agent cannot cheaply ask a clarifying question mid-run** — it stops, or it guesses, and a guess may not surface for weeks. Readiness is the highest-leverage quality control in this standard. The September QA sprint sets the bar: fifteen questions answered in a day, each folded into the ticket that needed it, *"so an agent works from its spec alone."*

## 7. Two states, never one

**Rule 7.1 — Scheduling state and verification level are separate fields.**

- **Scheduling:** `proposed → ready → current → merged → done`, plus `blocked` (names the blocker **and** the unblock condition) and `dropped` (names the reason; contributes no effort).
- **Verification:** `planned → implemented → tested → applied locally → deployed → verified in production`.

**Rule 7.2 — An item reaches `done` only when its verification level meets what its profile requires.** A UI feature is not done at `deployed`; a chore is done at `tested`. *Why: we already make this distinction constantly, in prose — "merged but the browser sweep never ran", "deployed and it ran blind for five hours", "decided, not yet enforced". A field can be counted; a sentence cannot.*

**Rule 7.3 — Exactly one item is `current` per lane** — not per project. *Why: this repository runs parallel agent streams (QA Stream A and Stream B). A single global `current` would make that either impossible or a lie.*

**Rule 7.4 — Every lane with more than one `current` declares the files each stream owns.** *Why: file ownership is the only thing that keeps parallel agents from silently overwriting one another; the QA sprint's Stream A/B split is the worked example.*

**Rule 7.5 — Size is `XS / S / M / L / XL`, and `XL` is not a size — it is a defect meaning "split this".** *Why: that is the one function of estimation that survives agent-executed work, where variance is dominated by how well the item was specified rather than by how large it is. Days are a human unit; do not promise them.*

## 8. Identity

**Rule 8.1 — A new item gets one monotonic ID: `GRM-###`. Kind, lane and profile are fields, never prefixes.** *Why: an item's kind can change during triage (rule 2.3), and an ID that encodes the kind then lies. We already run ten prefix schemes, and `D-` means both a decision (`D-001`…`D-008`) and a deviation (`D-56`, `D-57`, `D-64`).*

**Rule 8.2 — History keeps its prefixes. Never renumber.** `HR-03`, `DPG-46`, `QA-04c` and `T3-04` stay as they are. *Why: they are cited across the tree, in commit messages, and in the DPG evidence pack; renumbering would break every one of those references to buy tidiness.*

## 9. Where an item lives

**Rule 9.1 — A tracker holds *scheduling* state. The repository holds *specification* state. Nothing an agent must build from lives outside the repository.** *Why: it follows from two rules we already have. "The branch is the version" ([`06`](06_documentation_lifecycle.md) §3a) cannot be expressed by a tracker; and "the spec edit rides the same commit as the code" is impossible if the spec is behind an API.*

| Layer | Home |
|---|---|
| Inbox — raw reports, reviewer feedback, half-formed ideas, duplicates | tracker |
| Conversation — "is this real?", "did you mean X?" | tracker |
| **Register** — every *ready* item: id · kind · profile · scheduling state · verification level · size · lane · owner | **repo** — [`docs/SPINE.md`](../SPINE.md) ✅ |
| **Item spec** — only where the profile requires one | **repo** — sprint folder, or `docs/items/` |
| **Roadmap** | **repo** — `docs/ROADMAP.md` ⚠ *not built* |

**Rule 9.2 — The join between tracker and repo is the item ID, and no field is duplicated across that line.** *Why: duplicated fields are what turns a tracker integration into a two-way sync that nobody can keep honest.*

**Rule 9.3 — If a tracker is adopted, the register is *generated* from it in CI and pinned by a test.** *Why: the pattern is already proven here — `docs/dpg/02_questions.md` is generated from `00_compliance_status.md` and `tests/repo/test_dpg_questions_generated.py` fails the build on drift. Humans get a board; agents get a file; drift becomes impossible rather than merely discouraged.*

## 10. Definition of done — lane level

At sprint close, the existing audit ([`06`](06_documentation_lifecycle.md) §3c) gains one mechanical input:

- [ ] Every item in the lane reached the verification level its profile requires, **or** is recorded as `dropped` with a reason, **or** carries an honest marker naming what is unverified.

*Why: "did we remember everything?" is not a question a checklist can answer. "Does every row meet its profile?" is.*

---

## 11. Known deviations — do not extend

⚠ **This standard is adopted and not yet in force.** Everything below is true on 2026-09-04 and is the work of the operating-model sprint (the operating-model sprint (internal)).

| # | Not yet true | Closed by |
|---|---|---|
| 1 | ✅ **Closed 2026-09-04.** [`docs/SPINE.md`](../SPINE.md) exists; `TODO.md` is retired behind a forwarding stub and its 64 open rows are the register's backlog. ⚠ **Nothing validates it yet** — see row 3. | OM-02 |
| 2 | **There is no roadmap.** `docs/ROADMAP.md` does not exist, and no document defines the MVP or what "launched" means. | OM-05 |
| 3 | ✅ **Closed 2026-09-04.** `tests/repo/test_spine.py` exists and runs in CI — **ten checks, each proven to fail** on the defect it exists for: duplicate ids · a stale allocator line · an unknown kind · a `blocked` row with no blocker · two `current` items in one lane · a `done` row with no verification · a security view citing an item the register does not hold · dead `followups/` links · **a `ready` row with no profile** (added 2026-09-06 with row 4). ⚠ It checks that the register is *well-formed*, never whether the plan is good — a checker that judged content would be wrong often enough to get muted. | OM-03 |
| 4 | ✅ **Closed 2026-09-06.** The six derivation questions are asked at intake on the item form; the PR template now **confirms** the profile rather than deciding it, and names the item and profile it is confirming. `+SENSITIVE` ⇒ Opus is stated mechanically in `AGENTS.md`, not left to judgment at the keyboard. **Enforced, not merely written:** a `ready` or `current` register row with an empty profile fails `tests/repo/test_spine.py`. | OM-04 |
| 5 | ✅ **Closed 2026-09-06.** [`05_frontend.md`](05_frontend.md) §9a: six steps — brief → IA → wireframe → direction → state/responsive contract → **implementation contract frozen before build** — plus what the two committed `ui/*.html` mockups bind and what they do not, and the rule that a mockup is a file next to its spec rather than a hosted preview that can 404. | OM-06 |
| 6 | ✅ **Closed 2026-09-06.** [`06`](06_documentation_lifecycle.md) §4a carries the ladder for *items* beside the honesty markers for *documents*, with the crosswalk between them — an item at `implemented` or `tested` still reads `⚠ Not verified end-to-end` in its spec, because CI is neither a browser nor a server. | OM-06 |
| 7 | 🟡 **Partly closed 2026-09-04** — the deferral trail and the sprint trackers now resolve to one register. **Three vocabularies still coexist** and share no identifier: the issue templates (`bug`/`enhancement` + Area), the PR sensitive-path list, sprint ticket IDs, the deviations/`followups`/TODO debt trail, and the triage vocabulary proposed by the review-feedback-loop sprint. | OM-02, OM-07 |
| 8 | **The tracker is decided and now available, but not wired.** [D-010](../DECISIONS.md) is ✅ **done** — the repository went private 2026-09-04 — so **GitHub Issues + Projects** is usable. Nothing is generated from it yet, and rule 9.3's pinning test does not exist. | OM-07 |
| 9 | **The standard binds new items only.** The 64 rows absorbed from `TODO.md` into [`SPINE.md`](../SPINE.md) § *Backlog* carry an id and a home, **not a classification** — kind, profile and state are confirmed when each is scheduled — the filer proposes a kind, the owner confirms it at `ready`. *A deliberate scope decision, not an oversight.* | — |
