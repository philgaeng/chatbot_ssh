# Devil's Advocate — Spec Completeness Review

> **Status:** July 2026, written against the reorganized spec tree (post `docs/` restructure).
> **Method:** four parallel documentation surveys (150+ files) cross-checked against the codebase (routers, models, 50 migrations across 3 streams, UI routes), plus the verification notes from the consolidation passes that produced `docs/seah/`, `docs/ticketing_system/16–18`, `docs/ticketing_system/ui/`, and the rewritten `docs/deployment/01–06`.
> **Stance:** deliberately adversarial. The point is to find where the specs would mislead a new engineer, a security auditor, or ADB — not to celebrate what's good. A companion review of the code itself is in [`devils_advocate_codebase.md`](devils_advocate_codebase.md).

---

## 1. Verdict in one paragraph

The spec tree is now unusually complete on **what was built** (domain, API, schema, workflows, UI) and unusually honest about migration ownership. Its weaknesses are of two kinds: **(a) specs that promise protections the code does not deliver** — worst in the SEAH/privacy area, where the reveal/audit machinery is specified as LOCKED but only partially exists — and **(b) whole spec categories that simply don't exist**: testing strategy, non-functional requirements, threat model, disaster recovery, and an i18n/translation policy for a bilingual government system. The first kind is dangerous because the docs *look* authoritative; the second because nobody notices a missing document.

**Spec completeness by area (adversarial scoring):**

| Area | Score | One-line justification |
|---|---|---|
| Ticketing domain/API/schema (02–04, 07–18) | **85%** | As-built and code-verified July 2026; residual drift in 12 (see §2.1) |
| Deployment & operations (01–16, DOCKER) | **80%** | Rewritten to as-built; DR/restore-drill and capacity remain thin (§4.4) |
| Shared services (00–12) | **85%** | Contracts spot-verified against routers; headers now match reality |
| Chatbot (rest_chatbot 00–04) | **80%** | Current; conversation-layer *internals* (state machine) undocumented (§4.6) |
| SEAH & privacy (seah/, 09_privacy) | **60%** | Model is specified precisely — but several LOCKED protections are unimplemented and the spec had to be annotated rather than the gap closed (§3.1) |
| UI (ticketing_system/ui/) | **75%** | Now consolidated; deviations table honest; no component-level contract for the two god-pages |
| Cross-cutting NFR/testing/security-process | **25%** | Mostly nonexistent (§4) |

---

## 2. Where specs and code still disagree (found, not fixed)

### 2.1 `12_workflows_configuration.md` is *ahead* of the code
The July restructure aligned 02/04 to the code, which exposed that **12 now carries residual fiction**: `slot_key`, a `workflow_slot` webhook field, and `tickets.workflow_version` do not exist; slots are actually `project_workflows.intake_route` + `classifications` JSON + `is_default`, and there is **no version snapshot column** on tickets. A workflow edit therefore changes the interpretation of historical tickets — 12 describes a versioning safety that the schema does not provide. **Risk:** an auditor reading 12 believes ticket history is version-pinned. It isn't. *Fix: correct 12, or implement the version snapshot it promises.*

### 2.2 Two sources of truth for role catalogs persist
`11_roles_and_permissions.md` is locked and current, but the archived April `context/grm-specification.md`, the demo brief, and role tables inside 02 can still be found by grep and quote `local_admin`/`mopit_rep`. CLAUDE.md now carries a supersession banner, but nothing *prevents* the stale role list from being copied into a new seed script. *Fix: single machine-readable role catalog (the `grm_roles` seed) referenced by all docs, never restated.*

### 2.3 Escalation spec vs engine
`Escalation_rules.md` was corrected (GRC_DECIDE removed), but the legacy `grc_decide()` helper still exists in `ticketing/engine/escalation.py` unexposed. A spec that says "removed in v1" over code that still ships the function invites reintroduction by a well-meaning contributor. *Fix: delete the dead helper or mark it in code.*

### 2.4 Location-code dialects
`LOCATION_CODES.md` (canonical `P1_MOR`) now wins on paper, but `NP_P1`/`NP_D006`-style codes survive in seed scripts, PROGRESS demo tables, and one seed log message. The specs describe a single dialect; the repo speaks three. *Fix: one migration-note appendix in LOCATION_CODES listing every legacy dialect and where it still lives.*

---

## 3. Specs that promise what the code doesn't do (highest-risk class)

### 3.1 SEAH reveal & audit — specified LOCKED, partially fictional
`docs/seah/02_vault_privacy_and_reveal.md` (honestly) had to include an implementation-status table because the May 2026 LOCKED spec was never fully built:

- **Reveal endpoints** (`POST /api/grievance/{id}/reveal(/close)`) do not exist in `backend/api/`; ticketing uses a proto fallback with a synthetic session.
- **Audit tables** (`grievance_reveal_sessions`, `grievance_sensitive_access_audit`) exist but **nothing writes to them** — the audit trail specified as immutable is currently empty by construction.
- **Vault narrative encryption**: `content_ciphertext` is stored **without** `pgp_sym_encrypt`; the per-sensitivity key envelope was never implemented (field-level complainant PII encryption *is* real).
- **Status-check leak**: `get_grievance_by_complainant_phone` has no `case_sensitivity` filter — the "SEAH cases are invisible to status check" policy is a spec assertion, not a query predicate.
- **Focal roster + OTP verification**: specified April 2026, never wired; the derived-summary/leakage pipeline in ticketing has no code.

**Why this is the #1 finding:** these are exactly the protections a safeguarding auditor would check, and until this month the docs asserted them without qualification. The spec tree now tells the truth, but the truth is a gap list. *Fix priority: status-check SEAH filter (1 line of SQL) → audit writes → narrative encryption → real reveal endpoints.*

### 3.2 Officer-portal security posture vs `13_security.md`
`13_security.md` reads as a completed controls index, but the codebase review found **fail-open auth** (unset `KEYCLOAK_ISSUER` ⇒ every request is a super_admin), attachment/PII endpoints missing SEAH/scope gates, and no CI to keep any of it true. The security doc indexes *features*, not *failure modes*; a reader cannot learn from it that a missing env var disables authentication. *Fix: add a "fail-closed guarantees" section to 13 and make the code match it.*

### 3.3 Unimplemented-but-specified features not always labeled
Now labeled correctly: `16_org_chart_and_positions.md` ("Agreed design — not yet implemented"), `features/settings_tab_projects_and_seah_contact_centers.md` (unbuilt, and its role names predate the locked admin ladder — it will be implemented wrong if followed as-is). Still fuzzy: `09_reports` §12 Summary-tab history (shipped, but the section still reads like a plan), TP-02 transcription (open in three different places with three different phrasings).

---

## 4. Specs that don't exist at all (the silent gaps)

1. **Testing strategy.** Nothing in `docs/` defines what must be tested, at what layer, or before which promotion. Reality follows: 0 UI tests, 0 escalation-engine tests, no CI, and a pytest suite with collection errors. The DB operating model demands "smoke tests before promoting to main" without defining them. *This is the single most consequential missing document.*
2. **Non-functional requirements.** No target for concurrent officers, ticket volume, grievance sync scale, page latency, or SMS/LLM cost ceilings. The 2-minute full-table grievance sync is spec-compliant today and will melt at 10⁵ grievances — no spec says when that's a violation.
3. **Threat model / abuse cases.** SEAH docs describe survivor-centered *flows*, but no document asks "what does a malicious officer, a subpoena, a stolen laptop, or a compromised CDN do to this system?" The REST_webchat loads unpinned CDN scripts on a page collecting SEAH reports — no spec forbids it.
4. **Disaster recovery & data lifecycle beyond archiving.** Backup *scripts* are documented (15, 14), and a restore drill script exists, but there is no RPO/RTO statement, no restore-verification cadence, and no spec for what happens to the PII vault in a restore-to-new-host scenario (`DB_ENCRYPTION_KEY` backup is mentioned; the *procedure test* isn't).
5. **i18n/translation policy.** A bilingual system for Nepali civil servants and complainants has: garbled Nepali in SEAH-critical strings, a portal with zero i18n scaffolding, English-only error paths in the webchat — and **no document that says who owns translations, how they're reviewed, or that the portal must ship in Nepali.** The `preferred_language` backend field exists with no UI consumer; no spec noticed.
6. **Conversation-layer internals.** `rest_chatbot/02_flow_spec.md` documents flow *topology*, but nothing documents the 1,485-line `run_flow_turn`, the two parallel form registries, or the stack-introspection utterance lookup — the highest-complexity code in the repo has the least architectural documentation.
7. **API versioning & deprecation.** `services/01_api_contracts.md` has a policy section for backend services; ticketing's `/api/v1/` has no stated compatibility contract with the UI or the chatbot dispatcher (the UI broke silently when report routes were renamed — nothing in the spec tree would have caught it).

---

## 5. Process findings (why drift happened, and will happen again)

- **Status headers rot fastest.** Three docs said "Proposed" for built systems; one said "Implemented" over "to implement" sections. Rule worth adopting: a status header may only say *As-built* if it cites the migration/router/file that proves it.
- **Sprint folders became a shadow spec tree.** The vault model, tier model, geography model, classification model, and the entire UI spec lived only in sprint/handoff files for 1–3 months. The July restructure fixed the stock; the *flow* problem remains — nothing in AGENTS.md/CLAUDE.md instructs "durable content must land in `docs/<area>/` in the same PR."
- **Nobody owns cross-doc consistency.** Every contradiction found (CLOSE/GRC_DECIDE, workflow shapes, location codes, queue tabs) was between two docs that were each individually "current." A quarterly grep-based consistency pass (or CI link/term checker) would have caught all of them.
- **`.local.yaml` committed against its own doc** (`12_environment_urls.md` says gitignored) — small, but it's a spec asserting a control that git disproves in one command.

---

## 6. Ranked recommendations

| # | Action | Effort | Payoff |
|---|---|---|---|
| 1 | Close the SEAH spec/code gaps (§3.1), starting with the status-check `case_sensitivity` filter and audit writes | S–M | Turns the strongest-looking spec area from fiction to fact; auditor-critical |
| 2 | Write `docs/testing_strategy.md` (layers, required suites, CI gate) and stand up the CI it demands | M | Every other spec becomes enforceable |
| 3 | Correct 12_workflows (or implement version snapshots) | S | Removes the last known code-vs-spec inversion |
| 4 | Add an NFR one-pager (volumes, latency, sync scale, cost ceilings) | S | Converts "it works in the demo" into a measurable contract |
| 5 | Add fail-closed guarantees to 13_security + threat-model appendix (officer-insider, env-var, CDN, restore scenarios) | M | Makes the security doc answer auditor questions |
| 6 | i18n policy doc + Nepali copy audit for SEAH strings | S | Directly user-facing for the primary audience |
| 7 | Adopt the two process rules from §5 (as-built citations; durable-content-in-same-PR) in CLAUDE.md/AGENTS.md | S | Slows the next drift cycle |

---

*Companion document: [`devils_advocate_codebase.md`](devils_advocate_codebase.md) — code quality scored in percent, with improvement impact estimates.*
