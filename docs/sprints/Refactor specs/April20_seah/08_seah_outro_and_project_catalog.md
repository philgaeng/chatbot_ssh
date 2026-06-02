# 08 - SEAH post-submit outro & project catalog (implementation spec)

## Objective

Single place for **pre-implementation** decisions on:

1. **Project intake v2** — DB-backed project list and chatbot UX.
2. **Post-submit SEAH outro** — variant messages after successful submit.
3. **Reference data** — `seah_contact_points` for referral / center copy.
4. **Slot split** — routing vs “contact actually captured” for outro and ticketing.

**Sibling specs:** `00`, `01`, `02`, `03`, `07`  
**Follow:** `docs/Refactor specs/AGENT_INSTRUCTIONS.md`

---

## Executive summary (what to build, in order)

| # | Workstream | Outcome |
|---|------------|---------|
| 1 | **Slots** | Add `seah_anonymous_route`, `seah_contact_provided`; migrate reads off overloaded `sensitive_issues_follow_up` for routing/outro; resolve focal complainant identity (**one** `seah_anonymous_route` vs separate `seah_complainant_anonymous_route` — see §B). |
| 2 | **DB** | Tables: **`projects`** (or agreed name), **`seah_contact_points`**, optional **`government_agency`** + M2M; migrations + seed. |
| 3 | **Forms** | Replace free-text project step with picker + `/project_pick{"id":"<uuid>"}`; validators set `project_uuid` on grievance payload; drop **`seah_project_identification`** / **`seah_not_adb_project`** from chatbot surface (infer `adb` from project row in DB/reporting). |
| 4 | **Submit + payload** | `submit_seah_to_db` / `seah_payload`: include `project_uuid`, optional `seah_contact_point_id`, `seah_contact_provided`, `seah_anonymous_route`. |
| 5 | **Outro** | After successful **`action_submit_seah`**: invoke **`action_seah_outro`** (rename from `action_outro_sensitive_issues`); same turn as submit; on DB error show error **and** short safety line; resolve outro variant + merge **`seah_contact_points`** row into template. |
| 6 | **Copy** | `utterance_mapping_rasa.py`: variant keys per §Outro keys; en/ne; legal pass on focal reporter vs complainant wording (**B4.2**). |
| 7 | **Cleanup** | Deprecate old story-only outro paths; update `domain.yml`, `action_registry`, `stories.yml`, `01`/`02`/`03`. |

---

## Current code (baseline)

| Area | Today |
|------|--------|
| Project | `form_seah_2` / `form_seah_focal_point_2`: free text, `cannot_specify`, `not_adb_project`; `seah_not_adb_project` boolean. |
| Submit | **`ActionSubmitSeah`** → `seah_public_ref` message only; **no** mandatory outro from state machine. |
| Outro class | **`ActionOutroSensitiveIssues`**: only `seah_not_adb_project` → utterance 1 vs 2; **stories**, not full SEAH matrix. |

**Target:** state machine always chains **successful** SEAH submit → **`action_seah_outro`** (renamed implementation of current class or successor).

---

# Part A — Project catalog (decisions summary)

### A. Decisions (locked for v1)

| Topic | Decision |
|--------|-----------|
| **A1.1** Model | **One** project table (not split ADB/national tables). |
| **A1.2** Primary key | **UUID** PK; project short code exists as data, not PK. |
| **A1.3** Names | **`name_en`**, **`name_local`** on same row (language-agnostic columns). |
| **A1.4** Agency | **v1:** `government_agency` table; minimal seed (e.g. Nepal — Department of Roads). |
| **A1.5** Agency ↔ project | **Many-to-many** (junction table). |
| **A2.1** Geo filter | Match catalog rows by **`province`** first (per stakeholder); document if district/municipality added later. |
| **A2.2** Zero matches | Allow **free text** and/or **cannot specify** escape (no national-only list required for v1 if not needed). |
| **A2.3** Many matches | **Out of scope for v1** (low volume assumption). |
| **A2.4** Inactive | Add **`inactive_at`** (date) when project is marked inactive; default query **active only**. |
| **A3.1** Legacy slots | **Deprecate** `seah_project_identification` for intake; persist **`project_uuid`** (and optional display snapshot in payload). |
| **A3.2** Payload | **`/project_pick{"id":"<uuid>"}`** |
| **A3.3 / A3.4** `not_adb_project` | No separate chatbot slot; **infer** non-ADB (or flags) from **project row** in DB / reporting. |

### A. Reference — suggested `projects` columns (extend in migrations)

Minimum beyond PK: `project_uuid`, `name_en`, `name_local`, `province`, `adb` (boolean), **`inactive_at`** (nullable), agency M2M, any fields needed for filters. Exact DDL is an implementation PR; this spec locks **behavior** above.

### A4 / A5 — Ops & engineering

- **Ops / analytics:** ticketing system owns dashboards; chatbot stores **UUID + payload snapshot** for investigators.
- **Engineering:** read API for projects (shared with picker); cache policy **TBD** in service layer.

---

# Part B — Post-submit outro & slots

## B — Slot model: routing vs contact

| Slot | Purpose | Rule |
|------|---------|------|
| **`seah_anonymous_route`** | **Routing only** (which steps run). | Mirrors today’s anonymous vs identified **path**. Set when user commits path in **`form_seah_1`**; **`state_machine`** / `required_slots` should read this (after migration from `sensitive_issues_follow_up`). Type: **boolean** (`true` = anonymous route) **or** string `anonymous` / `identified` — **pick one** in implementation and document in `01`. |
| **`seah_contact_provided`** | **Outro / ticketing** | **`false`** by default. **`true`** iff **`complainant_phone`** or **`complainant_email`** holds a **non-skipped, validated** value after contact/OTP steps. |

**Migration:** dual-write from `sensitive_issues_follow_up` → `seah_anonymous_route` until all readers switch; keep old slot in payload if needed for audit.

**Focal (open):** If complainant identity in **`form_seah_focal_point_1`** must differ from initial route, add **`seah_complainant_anonymous_route`**; otherwise **reuse** `seah_anonymous_route` when complainant path is chosen. **Decide before coding O1 copy.**

---

## B0 — Outro variants (O1–O5) and canonical predicates

**Outro keys** (utterance tree, `action_seah_outro`): `focal_default`, `victim_limited_contact`, `victim_contact_ok`, `not_victim_anonymous`, `not_victim_identified`. Optional: `focal_not_adb` **removed** from product surface if `not_adb` is only a DB flag on project; reintroduce only if copy still needs it.

| ID | Product case | Predicate (canonical for implementation) |
|----|----------------|-------------------------------------------|
| **O1** | Focal point | `seah_victim_survivor_role == focal_point` |
| **O2** | Victim/survivor, limited reachability | `seah_victim_survivor_role == victim_survivor` **AND** ( `seah_anonymous_route` **OR** `seah_contact_provided == false` **OR** `complainant_consent == false` **OR** `seah_contact_consent_channel` in (`none`, `email`) ) — **`email` channel = no phone follow-up** (stakeholder **B0.1**). |
| **O3** | Victim/survivor, phone follow-up agreed | `seah_victim_survivor_role == victim_survivor` **AND** `seah_contact_provided` **AND** `complainant_consent == true` **AND** `seah_contact_consent_channel` in (`phone`, `both`) — includes **phone-only** (no email) when channel is `phone` (**B0.2**). |
| **O4** | Not victim/survivor, anonymous route | `seah_victim_survivor_role == not_victim_survivor` **AND** `seah_anonymous_route` |
| **O5** | Not victim/survivor, identified route | `seah_victim_survivor_role == not_victim_survivor` **AND** **not** `seah_anonymous_route` (if boolean: `seah_anonymous_route == false`) |

**B0.4 (complainant consent false):** Use **same variant family as O2** (limited contact / referral emphasis) unless legal later splits a dedicated key.

**Resolver:** implement **`resolve_seah_outro_variant(tracker) -> str`**; unit-test the matrix above including phone-only, email-only, both skipped.

---

## B1 — When & how to run outro

| Decision | Value |
|----------|--------|
| **B1.1** Trigger | **Same turn** as submit: message order = submit confirmation (with `seah_public_ref`) **then** outro body (or merged template—avoid duplicate ref if **B3.2** says no repeat). |
| **B1.2** Submit failure | Error message **+** one short safety / referral line (static or minimal lookup). |
| **B1.3** Action | **Rename** `action_outro_sensitive_issues` → **`action_seah_outro`**; update registry, stories, mappings; **deprecate** old name after transition. |

---

## B2 — Content & legal

| Item | Decision |
|------|-----------|
| **B2.1** Copy owner | **TBD** legal/ADB sign-off; use clear placeholders until approved. |
| **B2.2** Referral data | **`seah_contact_points`** table (§B2.2 schema); message **assembled** from matched row. |
| **B2.3** O3 tone | Example: contact will be attempted **using the channel agreed** (e.g. phone on the number provided); final wording + **PII in logs** policy: **TBD**. |
| **B2.4** No row match | **Generic fallback** utterance placeholder, e.g. user may visit the nearest SEAH contact point; optional **national default row** in DB for consistency. |
| **B2.5** 30s close | **TBD** (frontend vs bot); not blocking outro text. |

### B2.2 — Table `seah_contact_points` (schema)

| Column | Notes |
|--------|--------|
| `seah_contact_point_id` | PK (UUID or serial). |
| `province`, `district`, `municipality`, `ward` | Text; nullable rightward for broader rows. |
| `project_uuid` | Nullable FK to project catalog. |
| `seah_center_name`, `address`, `phone` | Text for user-facing message. |
| `opening_days`, `opening_hours` | **Free text** v1. |
| `is_active` | **boolean, default `true`** at v1. |
| `sort_order` | Optional; tie-break with `seah_contact_point_id`. |

**Lookup:** best match by `project_uuid` then ward → municipality → district → province; **fallback** = generic utterance (and/or one seeded national row).

**Payload:** optionally persist `seah_contact_point_id` on submit payload for audit (**`03`**).

---

## B3 — Buttons

| Decision | Value |
|----------|--------|
| **B3.1** | Reuse **`BUTTONS_CLEAN_WINDOW_OPTIONS`** (or equivalent) after outro unless product restricts. |
| **B3.2** | **Do not** repeat `seah_public_ref` in outro if submit line already shows it (single mention). |

---

## B4 — Focal outro

| Decision | Value |
|----------|--------|
| **B4.1** Sub-variants | Start with **single O1 template** + optional inserted sentences from slots (`seah_focal_reporter_consent_to_report`, etc.) unless legal requests separate keys. |
| **B4.2** Wording | Messages must **distinguish reporter vs complainant** where relevant; **legal** will refine wording. |

---

## B5 — Engineering checklist

- [ ] `resolve_seah_outro_variant` + tests (slot matrix).
- [ ] Rename **`action_seah_outro`**; wire **`state_machine`** after successful `action_submit_seah`.
- [ ] **`02`:** all variant utterances **en** + **ne**; template strings for `seah_contact_points` fields.
- [ ] **`01`:** document `seah_anonymous_route`, `seah_contact_provided`, `project_uuid`, optional `seah_contact_point_id`.
- [ ] **`03`:** payload fields + DDL notes for `projects`, `seah_contact_points`, junctions.
- [ ] Deprecate obsolete story actions / duplicate outro behavior.

---

## Open items before merge (short list)

1. **Focal:** one vs two “anonymous route” slots (§B).
2. **B2.3:** final O3 sentence + logging/masking rules.
3. **B2.5:** timer ownership.
4. **Project DDL:** final column list + seed ownership.
5. **Normalization:** string comparison for province/district (case, diacritics) in lookup helper.

---

## Acceptance criteria (implementation phase)

1. Project table + picker + **`project_uuid`** on SEAH persist path.
2. **`seah_contact_points`** seeded, lookup + template in outro for variants that need center block (**O2**, **O4**, at minimum).
3. **O1–O5** each has signed-off **en/ne** copy (or approved placeholder).
4. Successful submit always triggers **`action_seah_outro`** without duplicate ref noise.
5. **`01` / `02` / `03`** updated; old outro action name removed from active paths.

---

## Changelog

- **2026-04-22:** Initial spec through contact-points table.
- **2026-04-22:** Slot split `seah_anonymous_route` / `seah_contact_provided`; B2.2 `seah_contact_points`.
- **2026-04-23:** **Pre-implementation pass:** executive summary + ordered workstreams; consolidated Part A/B decisions; fixed tables/markdown; canonical O1–O5 predicates (incl. phone-only → **O3**); B1/B3/B4/B5 decisions; `is_active` on contact points; removed stray text; open items + acceptance criteria tightened.
