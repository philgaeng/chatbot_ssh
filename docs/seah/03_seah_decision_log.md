# 03 — SEAH Decision Log (condensed)

**Status:** As-built, July 2026 — statuses verified against code on `integration/seah-claude`.
**Last updated:** 2026-07-04 · ⚠ backfilled from git 2026-09-04; not re-verified against the code
**Sources consolidated:** `docs/sprints/archive/Refactor specs/April20_seah/00_seah_sensitive_flow_spec.md` (stakeholder Q&A A1–K42), `01_seah_route_and_slots.md` (pressure-test answers), `07_seah_focal_point_flow.md`, `08_seah_outro_and_project_catalog.md` (Part A/B); `docs/sprints/archive/Refactor specs/May5_seah/07_phase2_decision_questions.md` (Q1–Q17), `09_updated_seah_workflow.md`; `docs/sprints/archive/Refactor specs/March 5/14_sensible_content_detection_and_flow..md`.

Format: **Decision — rationale — status.** Statuses: ✅ Implemented · 🔁 Superseded (by a later decision) · 🕐 Planned (decided, not built) · ❓ Open/TBD.

Flow details: [01_seah_intake_flow.md](01_seah_intake_flow.md) · storage/privacy: [02_vault_privacy_and_reveal.md](02_vault_privacy_and_reveal.md).

---

## A. Scope and routing (April 2026)

| # | Decision | Rationale | Status |
|---|----------|-----------|--------|
| A-1 | Dedicated SEAH route on the main menu (`/seah_intake`), feature-flagged (`ENABLE_SEAH_DEDICATED_FLOW`). | Controlled rollout on a feature branch. | ✅ |
| A-2 | Legacy sensitive-detection fallback hard-switched into the new SEAH flow (detection merges into `form_seah_1`; `form_sensitive_issues` retired). | One flow, no drift. | ✅ |
| A-3 | "Not an ADB project" still completes a confidential SEAH submission (no early referral-only terminal). | Preserve triage record. | ✅ |
| A-4 | File uploads inside SEAH intake. | — | ❓ TBD (not offered today) |
| A-5 | "Not sensitive content" exit lands the user at the **main menu**. | Clear off-ramp. | ✅ |

## B. Fields, skips, identity (April 2026)

| # | Decision | Rationale | Status |
|---|----------|-----------|--------|
| B-6 | Canonical non-disclosure value is the project-standard `skipped` / `SKIP_VALUE` (not `NA`/`prefer not to say` variants). | Storage consistency. | ✅ |
| B-7 | Ask **both** phone and email, each independently skippable (no "at least one contact" rule). | Non-coercive. | ✅ victim-identified path (⚠️ anonymous path collects phone only — see F-31) |
| B-8 | Names stored as free-text `complainant_full_name` (no first/last split). | Matches existing model. | ✅ |
| B-9 | Anonymous users still get structured location questions; copy vetted as defensible. | Ops needs minimum geography. | ✅ (reduced to province→district→municipality in the current flow) |
| B-10 | "Anonymous" copy vs persisted data (location, narrative, optional channel) was vetted — not over-promising. | Legal review. | ✅ |

## C. Focal-point verification (April 2026)

| # | Decision | Rationale | Status |
|---|----------|-----------|--------|
| C-11 | Validate focal identity immediately during intake (roster match), retry then offline-verification fallback. | Gatekeeping without blocking. | 🕐 Planned — roster lookup never wired; slots `seah_focal_lookup_status`/`seah_focal_verification_status` are pass-through only |
| C-12 | Focal OTP channel = SMS, reusing the existing sender; failed OTP ⇒ allow submission tagged `unverified_focal_point`. | Don't block reports. | 🕐 Planned (no OTP anywhere on SEAH branch today) |
| C-13 | Focal reporter **phone is mandatory** (skip rejected); name asked **before** phone. | Focal must be reachable/verifiable. | ✅ (May 2026 update) |
| C-14 | Focal flow drops all complainant profiling: consent-to-report, complainant name/phone/email/location, and the follow-up contact-channel question removed. | Direct victim contact can be unsafe. | ✅ (supersedes the April20 07 staged complainant-capture design 🔁) |
| C-15 | `seah_focal_learned_when`: free text, officer validates manually. | No friction. | 🔁 Superseded — implemented as button enum (`learned_within_24h`…`learned_over_7d`, skippable) |
| C-16 | No extra detail required when referred-to-support = No; keep intake non-probing. | Survivor-centered. | ✅ |
| C-17 | Focal matching is against known **focal points**, not complainants. | Correct roster. | 🕐 (depends on C-11) |

## D. Storage model (April 2026 → superseded May 2026)

| # | Decision | Rationale | Status |
|---|----------|-----------|--------|
| D-18 | Separate SEAH storage: copy of grievance/complainant tables (`grievances_seah`/`complainants_seah`), dedicated `SEAH-…` case id, public-safe reference token (`seah_public_ref`). | Initial segregation instinct. | 🔁 **Superseded by phase 2** (E-block): canonical tables + vault; legacy tables dropped in `pub004`; `grievance_id` is the only reference |
| D-19 | Encryption for SEAH fields = same as main flow (pgcrypto field-level on phone/email/name/address). | One posture. | ✅ |
| D-20 | No migration/backfill needed for previously flagged sensitive grievances (test data only). | Dev-only data. | ✅ (pub004 still backfilled defensively) |

## E. Phase-2 canonical/privacy decisions (May 2026, Q1–Q17 — all LOCKED)

| # | Decision | Rationale | Status |
|---|----------|-----------|--------|
| E-1 | Canonical internal id = `grievance_id` for standard + SEAH (Q1). | One reference everywhere. | ✅ |
| E-2 | `seah_public_ref` replaced by the canonical id shown directly; no backward compatibility (Q2). | Simplicity. | ✅ |
| E-3 | Id format enforced in app, not DB constraint (Q3). | Flexibility. | ✅ |
| E-4 | ≥1 `grievance_parties` row per grievance, default role `victim_survivor` (Q4). | Role context always exists. | ✅ |
| E-5 | Exactly one `is_primary_reporter = TRUE` per grievance (Q5). | Enforced by partial unique index. | ✅ |
| E-6 | Anonymous SEAH: `complainant_id` NULL allowed, party row still required (Q6). | Role without identity. | ✅ |
| E-7 | Role enum: `victim_survivor`, `witness`, `relative_or_representative`, `seah_focal_point`, `reporter_other`; chatbot encodes 3, officers can set the rest (Q7). | Bounded vocabulary. | ✅ |
| E-8 | Hard-stop writes to legacy SEAH tables immediately after migration; tables dropped in the same series (Q8, Q15). | Clean dev state. | ✅ |
| E-9 | Stop writing `seah_payload` snapshot; vault payloads only (Q9). | Single sensitive store. | ✅ |
| E-10 | Vault (`grievance_vault_payloads`) is the sole source of truth for original narrative (Q10). | No duplication. | ✅ (`grievance_description` NULL on SEAH rows) |
| E-11 | Public↔ticketing contract: versioned JSON schema; required ingest fields `grievance_id`, `case_sensitivity`, non-PII routing, `summary_profile_version`, `safe_summary` (Q11–Q12). | Deny-by-default payloads. | 🕐 partially — webhook sends non-PII payload; formal versioned schema + safe_summary pipeline pending |
| E-12 | Reveal policy inputs include `party_role` + `is_primary_reporter` (Q13). | Contextual authorization. | 🕐 (policy engine not built) |
| E-13 | SEAH reveal tightening = lower TTL + lower quotas + stronger alerts (no dual-approval) (Q14). | Baseline proportionality. | 🕐 TTL 60s vs 120s in proto client; quotas/alerts pending |
| E-14 | Rollback for the phase-2 migration = DB snapshot restore only (Q16). | High-change migration. | ✅ (empty `downgrade()`) |
| E-15 | Phase-2 completion gate: canonical tables live, parties in use, no legacy writes, ticketing consumes only approved payloads, reveal/audit matrix passes (Q17). | Definition of done. | 🕐 first four ✅; reveal/audit matrix pending |

## F. Notifications, follow-up, UX (April + May 2026)

| # | Decision | Rationale | Status |
|---|----------|-----------|--------|
| F-21 | No-SMS policy applies to **complainant-facing** messages only (internal ops SMS allowed elsewhere). | Safety without crippling ops. | ✅ |
| F-22 | No OTP verification on any SEAH branch — phone collected without proof-of-possession. | Survivors may borrow phones. | ✅ |
| F-23 | SEAH status check completely disabled for end users; no chatbot modification flow. | No traceable follow-up surface. | ✅ policy / ⚠️ phone-based status-check query lacks a `case_sensitivity` filter (gap — see doc 01 §10) |
| F-24 | Show the case reference on-screen after submit. | User needs a receipt. | ✅ (reference = `grievance_id`; the April "public-safe token" answer 🔁 superseded by E-2) |
| F-25 | 30s auto-close timer optional, frontend-controlled. | Not blocking. | ❓ not implemented |
| F-26 | Follow-up is investigator-managed per `seah_contact_consent_channel` (`phone`/`email`/`both`/`none`), asked only when a validated contact path exists. | Consent-scoped contact. | ✅ |
| F-27 | Wrong/shared-phone fallback: direct user to nearest SEAH centre in the outro. | Non-digital fallback. | ✅ (support-centre block from `seah_service_providers`) |
| F-28 | Witness (not-victim) without victim consent: ask immediate-danger, then exit **without filing**, showing real support centres when location is known. | Consent-first filing. | ✅ (May 2026; no distinct urgent branch for danger=yes — ❓ TBD) |
| F-29 | Persistent Close Browser / Close Session controls in the webchat composer (not chat-message buttons); Close Browser ≠ secure erasure, Close Session is authoritative. | Shoulder-surfing safety. | ✅ (`close_controls_mode` from orchestrator) |
| F-30 | No session resume for SEAH (shared-device risk); partials are not persisted as cases — only submitted sessions create records. | Privacy of partial reports. | ✅ |
| F-31 | May 2026 flow updates: updated confidentiality intro, "Rewrite the summary" wording, name-before-phone for focal, optional email question in anonymous flow, risk multi-select via Done/Skip, single "End session" button. | Stakeholder comment pass. | ✅ except the anonymous-flow **email question** (not asked — deviation) and phone-before-name on the identified victim path |
| F-32 | Utterances maintained directly in `utterance_mapping_rasa.py` (en + ne); support-centre locations/phones in DB. | One content source. | ✅ |
| F-33 | Languages: en + ne, locked at flow start. | Parity with main flow. | ✅ |
| F-34 | Referral copy: best-guess text now, official SEAH-team list later; placeholders where unapproved. | Don't block on content. | ✅ mechanism / ❓ final validated list still pending |

## G. Project catalog and outro (April 2026, spec 08)

| # | Decision | Rationale | Status |
|---|----------|-----------|--------|
| G-35 | One `projects` table, UUID PK, `name_en`/`name_local`, `adb` flag, `inactive_at`, province-first geo filter, `/project_pick{"id":…}` payload; `not_adb` inferred from the project row. | Structured project intake. | ✅ table + validator + picker code; 🔁 the **picker UI is currently disabled** — product switched the ask to a yes/no "perpetrator employed by an ADB project?" question (buttons kept for quick restore) |
| G-36 | Project enum keeps `cannot_specify` (not `not_sure`); free-text escape allowed. | Backward consistency. | ✅ |
| G-37 | `seah_anonymous_route` (routing) split from `seah_contact_provided` (reachability) — stop overloading `sensitive_issues_follow_up`. | Clean outro/ticketing predicates. | ✅ |
| G-38 | Outro runs in the same turn as submit (`action_seah_outro` chained after `action_submit_seah`); no duplicate reference in the outro; on submit failure show error + short safety line. | Single coherent close. | ✅ chained + no duplicate ref; ❓ failure safety-line not verified |
| G-39 | Outro variants O1–O5 keyed on role × anonymity × contact × consent; `email`-only channel counts as limited contact. | Message accuracy. | ✅ resolver implemented (`resolve_seah_outro_variant`); 🔁 live outro streamlined to focal vs contact-provided + nearest-centre block |
| G-40 | `seah_contact_points` reference table with ward→province fallback lookup and generic fallback utterance; matched id persisted for audit. | Location-aware referral. | ✅ (now primarily `seah_service_providers` via migration `pub009`; `seah_contact_points` retained as fallback — both app/DDL ownership to clean up) |

## H. Sensitive-content detection (March 2026, two-bucket policy)

| # | Decision | Rationale | Status |
|---|----------|-----------|--------|
| H-41 | Two buckets: **sensitive content** = gender/sexual harassment only (`sexual_assault`, `harassment`) → sets `grievance_sensitive_issue`, routes to SEAH flow; **high priority** = `land_issues`, `violence` → flag for ADB follow-up, stay in normal flow. | Route only what needs the confidential flow. | ✅ |
| H-42 | Lightweight LLM task `detect_sensitive_content_task` fires in the background on every grievance text addition; result persisted; keyword detector is the fallback at Submit. | Fast + resilient detection. | ✅ |
| H-43 | Keyword detector returns `confidence` and string `level`; `action_required` only for sensitive bucket at CRITICAL/HIGH. | Interface hygiene. | ✅ |
| H-44 | Orchestrator uses the same form-based pattern as other flows for the sensitive branch. | Consistency. | ✅ (routes into `form_seah_1`; the March-era `form_sensitive_issues` state is 🔁 superseded) |

## I. Open items (consolidated)

- Focal roster lookup + SMS OTP verification (`unverified_focal_point` tagging) — C-11/C-12/C-17.
- Authoritative reveal endpoints, policy engine, audit writes, quotas/alerting — doc 02 §5–6.
- Derived-summary pipeline with leakage/coverage blockers — doc 02 §4.
- Status-check query guard `case_sensitivity != 'seah'` — F-23 gap.
- Urgent-safety branch when witness reports immediate danger — F-28.
- Anonymous-flow email question — F-31 deviation.
- Vault narrative field-level encryption + per-sensitivity keys — doc 02 §3 gap.
- Final validated support-service list and legal sign-off of SEAH copy — F-34.
- SEAH data retention period and exclusion from non-prod logs/analytics (April Q41–42) — ❓ TBD.
- Rate-limiting / abuse signals specific to `seah_intake` — deferred to a security audit.
- Migration ownership for `projects` and `seah_contact_points` (currently app DDL) — tech debt.
