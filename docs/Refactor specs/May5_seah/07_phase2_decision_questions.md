# Phase 2 Decision Questions (Public DB Revamp)

## Purpose

Lock unresolved architecture decisions before implementing phase 2 (single grievance table, single complainant table, party-role links).

Please answer each question directly (pick one option or write your own value).

---

## A. Canonical identifiers

### Q1. Canonical internal case identifier

Which field becomes the single canonical internal identifier for all cases (standard + SEAH)?

- [ ] A) `grievance_id` (recommended)
- [ ] B) `seah_case_id`
- [ ] C) New synthetic `case_id`
- [ ] D) Other: `____________________`

### Q2. Public-facing reference for SEAH

How should `seah_public_ref` behave after consolidation?

- [ ] A) Keep as public token mapped to canonical case id (recommended)
- [ ] B) Replace with canonical id directly
- [ ] C) Keep both visible to officers
- [ ] D) Other: `____________________`

### Q3. Uniqueness and format

Should canonical case IDs follow a strict format rule?

- [ ] A) Yes, enforce regex/format in DB constraint
- [ ] B) Yes, enforce in app only
- [ ] C) No strict format
- [ ] D) Other: `____________________`

If yes, specify format: `____________________`

---

## B. Party-role model (`grievance_parties`)

### Q4. Required party rows per case

What is the minimum required party linkage?

- [ ] A) At least 1 `grievance_parties` row for every grievance (recommended)
- [ ] B) Optional for non-SEAH, required for SEAH
- [ ] C) Optional for all
- [ ] D) Other: `____________________`

### Q5. Primary reporter rule

How many `is_primary_reporter = true` rows are allowed per grievance?

- [ ] A) Exactly 1 (recommended)
- [ ] B) At most 1
- [ ] C) Any number
- [ ] D) Other: `____________________`

### Q6. Anonymous SEAH intake rule

For anonymous SEAH, what is required?

- [ ] A) Allow `complainant_id = NULL` but require `party_role` row(s) (recommended)
- [ ] B) Require `complainant_id` always
- [ ] C) No `grievance_parties` row required if anonymous
- [ ] D) Other: `____________________`

### Q7. Role vocabulary lock

Approve role enum for phase 2?

- [ ] A) `victim_survivor`, `witness`, `relative_or_representative`, `seah_focal_point`, `reporter_other` (recommended)
- [ ] B) Add/remove roles: `____________________`

---

## C. Sensitive data and cutover behavior

### Q8. Cutover day rule for sensitive duplication

Once phase 2 starts, should we hard-stop writes of sensitive narrative to old SEAH fields/tables?

- [ ] A) Yes, hard-stop immediately after migration (recommended)
- [ ] B) Dual-write for a short window, then stop
- [ ] C) Keep dual-write indefinitely
- [ ] D) Other: `____________________`

If dual-write window: duration = `____________________`

### Q9. `seah_payload` treatment

How to handle `seah_payload` (full snapshot) after cutover?

- [ ] A) Stop writing it; move to vault payloads only (recommended)
- [ ] B) Keep writing but with aggressive redaction
- [ ] C) Keep unchanged
- [ ] D) Other: `____________________`

### Q10. Vault source of truth

Confirm source of truth for original narrative text:

- [ ] A) `public.grievance_vault_payloads` only (recommended)
- [ ] B) Vault + canonical grievance text fields
- [ ] C) Other: `____________________`

---

## D. Cross-worktree API contract

### Q11. Contract strictness

How should payload contracts between public and ticketing be managed?

- [ ] A) Versioned JSON schema with required/optional fields (recommended)
- [ ] B) Document-only contract, no schema enforcement
- [ ] C) Generated API client contract only
- [ ] D) Other: `____________________`

### Q12. Required fields for ticketing ingest

Select minimum required fields ticketing must always receive:

- [ ] `grievance_id`
- [ ] `case_sensitivity`
- [ ] non-PII routing (`country_code`, `location_code`, `organization_id`, `project_code`)
- [ ] `summary_profile_version`
- [ ] `safe_summary`
- [ ] other: `____________________`

---

## E. Reveal authorization and policy

### Q13. Should reveal policy include party-role context?

- [ ] A) Yes, include `party_role` and `is_primary_reporter` in policy inputs (recommended)
- [ ] B) No, role/scope/sensitivity is enough
- [ ] C) Other: `____________________`

### Q14. SEAH stricter reveal rule

Pick SEAH-specific tightening strategy:

- [ ] A) Lower TTL + lower quotas + stronger alerts (recommended baseline)
- [ ] B) Add mandatory dual-approval for SEAH reveals
- [ ] C) Allow by standard rule only
- [ ] D) Other: `____________________`

---

## F. Migration execution policy (dev environment)

### Q15. Legacy table handling in dev

After successful backfill and verification, should legacy SEAH tables be dropped in phase 2?

- [ ] A) Yes, drop in same migration series (recommended for clean dev state)
- [ ] B) Keep renamed/archive tables for one sprint
- [ ] C) Keep indefinitely
- [ ] D) Other: `____________________`

### Q16. Rollback strategy

Preferred rollback approach:

- [ ] A) DB snapshot restore only (recommended for high-change migration)
- [ ] B) Full down-migration support
- [ ] C) Hybrid (partial down + snapshot fallback)
- [ ] D) Other: `____________________`

---

## G. Completion gate for phase 2

### Q17. Accept phase 2 only when all are true?

- [ ] canonical single grievance table active
- [ ] canonical single complainant table active
- [ ] `grievance_parties` in use for all new cases
- [ ] no new writes to legacy SEAH tables
- [ ] ticketing consumes only approved non-PII + safe summary payloads
- [ ] reveal/audit policy checks pass for standard + SEAH matrix

If any additional acceptance gate is needed, list here:

`____________________________________________________________`

