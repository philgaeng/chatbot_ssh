# T3-07 — Amend the data rules to as-built; pin the two that hold (S)

> Workstream F · Branch `dev/tier3-structural` · **Phase 3 — docs + guard tests. No runtime behavior changes.**
> Evidence + the decision itself: [`00-reassessment.md`](00-reassessment.md) §6. **Read §6 first.**
> Line numbers as of `dev/tier3-structural` @ 2026-07-15 — re-locate before editing.

---

## What this ticket does

Makes `CLAUDE.md` and the code agree — **by correcting the docs, not the code**. Per §6's decision (2026-07-15), the "no joins into `public.*`" rule is dropped; the no-FK and no-PII-columns rules are kept and pinned with tests.

**This ticket changes no runtime behavior.** It deletes no query, moves no read, adds no HTTP hop. If you find yourself editing a `text()` select, you are in the wrong ticket.

## Why (one paragraph — the full argument is §6)

The rule *"No SQL joins from `ticketing.*` into `public.*`"* was written in March 2026 to serve two goals: extract ticketing to its own DB by changing a connection string, and keep the chatbot alive if ticketing is removed. **Both goals are already dead in the code** — ticketing issues 11 statements against `public.*` including 3 writes, and the chatbot's intake location validation reads `ticketing.locations` directly. The rule has no enforcement (one DB, one role), has been false for months, and honoring it today would *degrade* security (§6 → *the followup's justification is inverted*). An undocumented exception to a LOCKED rule is worse than a documented one — the followup doc's own words.

---

## Step 1 — amend `CLAUDE.md` §Data rules (commit 1)

Current text (`CLAUDE.md:157-161`, verified 2026-07-15 — re-locate before editing):

```
1. No SQL joins from `ticketing.*` into `public.*`
2. No foreign keys from `ticketing.*` into `public.*`
3. PII (name, phone, email, address) NEVER stored in `ticketing.*`
4. `ticketing.tickets` caches non-PII at creation: …
5. Officer detail view fetches PII fresh via `GET /api/grievance/{id}`
```

- [ ] **Rule 1 → replaced** by a documented read/write contract. It must state: ticketing may read and write named `public.*` tables through its own session; the set is **closed and enumerated**; adding to it is a deliberate change, not a default. Enumerate the 5 tables measured in §6: `grievances`, `file_attachments`, `grievance_classification_taxonomy`, `complainants` (join-only, non-PII columns), `grievance_parties`.
- [ ] **Rule 2 → kept, unchanged.** Add: pinned by a test (step 2).
- [ ] **Rule 3 → kept, sharpened.** The valuable form is the *original* one from `docs/claude-tickets/context/existing-services.md:129` — no complainant PII **columns** in `ticketing.*`, and `public.complainants` is not a PII source for ticketing. Add: pinned by a test (step 2).
- [ ] **Rule 4 → kept**, but note the honest caveat: `grievance_summary` is free text and *can* contain self-disclosed PII. It is cached by design (`models/ticket.py:57-59`); `grievance_description` deliberately is **not** (`grievance_content.py:86` writes only summary/categories/location). That asymmetry is intentional — say so, so nobody "fixes" it.
- [ ] **Rule 5 → amended.** It is true for *complainant PII* (and becomes properly true when T3-04 lands). It is **not** true for grievance content — say so plainly.
- [ ] **Fix `CLAUDE.md:121`** — *"Grievance API — primary data source, handles PII decryption"*. **Coordinate with T3-04 step 4**, which also owns this line; whichever lands second must not revert the other. Until T3-04's step 2, the claim is false (§3).
- [ ] Add a dated pointer to §6 so the *rationale* survives this time. **The failure mode this ticket exists to prevent is `21631051`** — the June 2026 doc reorg that deleted the March rationale and left the bare rule, which is why the rule read as arbitrary fiat for a year. A rule without its reason decays into cargo cult.

## Step 2 — pin the two rules that hold (commit 2)

Both currently hold and are worth keeping. Neither is enforced by anything today.

- [ ] **No cross-schema FK.** Test asserts no `ForeignKey` in `ticketing/models/` or `ticketing/migrations/versions/` targets `public.*`. Verified zero at 2026-07-15 — **the test must be green on today's code.** (Not a red-pre-fix test: it pins an invariant, it does not fix a bug. Say so in the docstring so the next reader doesn't "fix" it.)
- [ ] **No complainant PII columns in `ticketing.*`.** Test asserts no column named for `complainant_full_name` / `complainant_phone` / `complainant_email` / `complainant_address` exists in any `ticketing/models/*.py`. Also green today.
- [ ] **Contract-drift guard** for the enumerated `public.*` reads: the columns each `text()` select names still exist in `public.*`. This absorbs the standing `grievance_sync.py` hardcoded-column-list TODO row (same family — §6, and TODO.md 🔵 TECH DEBT). **Close that row in this commit.**
  > Model it on the CL-01 schema-baseline gate and the `_KNOWN_UNAUTH_READS` sweep from `authz-gaps-h2-03`: a closed allowlist that fails when reality drifts from it. The allowlist *is* the contract — that is what makes rule 1's replacement enforceable rather than aspirational.

## Step 3 — update the downstream docs (commit 3)

- [ ] `docs/ticketing_system/04_ticketing_schema.md:4` — bare rule; **restore the March rationale** (§6 quotes it verbatim) and note which half is now retired and why.
- [ ] `docs/deployment/09_privacy.md:25-27` — its "Worktree and schema ownership (LOCKED)" heading motivates the rule by *parallel worktrees*, a workflow retired in June 2026 (`CLAUDE.md:40`). Re-motivate or retire.
- [ ] `docs/ticketing_system/03_ticketing_api_integration.md` — document the read/write contract (the followup's DoD item 3).
- [ ] `docs/ticketing_system/00_ticketing_overview_and_questions.md:42` — restates the PII rules as a principle; align.
- [ ] Close [`followups/ticketing-cross-schema-direct-reads.md`](followups/ticketing-cross-schema-direct-reads.md) with the decision + a §6 pointer, and retire its TODO.md row.
- [ ] `scripts/ops/create_scoped_roles.sql:50` — the comment *"Ticketing reads (not writes) the grievance source rows for sync"* is **factually wrong** (3 writes — §6), and the grants cover **1 of 5** tables ticketing touches. The script is opt-in and inactive, so this is a doc fix, not an outage — **but adopting it as written would break 4 paths.** Fix the comment and the grants together, or mark the script explicitly unsafe-as-written.

---

## Tests (acceptance)

- [ ] No-cross-schema-FK guard — green on today's code.
- [ ] No-complainant-PII-columns guard — green on today's code.
- [ ] Contract-drift guard over the enumerated `public.*` reads — green; **verify it goes red** if you rename a column in a scratch DB (prove the guard guards).
- [ ] Full `tests/ticketing` green (baseline: **545 passed / 5 skipped / 0 xfailed**).
- [ ] No runtime file changed. `git diff --stat` should show docs + tests only.

## Explicitly out of scope

- **Migrating any read to the API.** Blocked on T3-06, and per §6 not currently desirable.
- **Adopting `create_scoped_roles.sql`.** Real privilege separation is a genuine improvement and a genuine project — it needs the grants to match the measured 5-table surface first. → log as a followup if you want it on the board.
- **`DB_ENCRYPTION_KEY` custody.** That is T3-04.
