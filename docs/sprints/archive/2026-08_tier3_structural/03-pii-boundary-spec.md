# T3-04 — Unify the PII boundary (M)

> Workstream D · Branch `dev/tier3-structural` · **Phase 2 — land after the Phase-1 bug fixes.**
> Evidence: [`00-reassessment.md`](00-reassessment.md) §3. **⚠️ The source review misdiagnosed this item and prescribed an order that causes a silent outage. Read §3 before writing a line.**
> Line numbers as of `dev/tier3-structural` @ 2026-07-15 — re-locate before editing.

---

## ⚠️ Read this first — the review is wrong

The review says: *"Route ticketing's PII decryption through the grievance API only; drop `DB_ENCRYPTION_KEY`. Restores the single auditable PII boundary."* (M/L)

**Three corrections:**

1. **There is no dual path.** `ticketing/services/pii_vault.py:49-73` — the only decryption site in ticketing — has **no `FROM` clause**:
   ```python
   text("SELECT pgp_sym_decrypt(decode(:ct, 'hex'), :key) AS decrypted")
   ```
   It decrypts a ciphertext **already in hand**, obtained **from the grievance API**. Ticketing uses Postgres as a **pgcrypto oracle**, not as a PII datastore — no complainant table, no `public.*` PII row, no join. Nothing bypasses the API. The correct characterization is **one fetch path, split decryption responsibility**.

2. **The real defect is in the backend.** `backend/services/database_services/grievance_manager.py:153-181` — `get_grievance_by_id` returns `_parse_database_result(results[0])`, which (`base_manager.py:729-734`) **only parses JSON — it never decrypts**. Its sibling `get_grievance_by_complainant_phone` **does** call `self._decrypt_sensitive_data(complainant)` (`:537`). So `GET /api/grievance/{id}` returns **pgcrypto hex ciphertext** for the four `ENCRYPTED_FIELDS` (`base_manager.py:63-68`). `pii_vault.py` is a **client-side workaround for a server-side omission** — its own docstring admits it. **`CLAUDE.md:121` ("Grievance API … handles PII decryption") is aspirational and false today.**

3. **The review's order causes a silent outage.** Drop the key from ticketing first and `looks_like_ciphertext` → `scrub_pii_value` maps every contact field to `None` (`pii_vault.py:44-45`). Officers see "—" on every standard contact card, **with no error**. And **no test would catch it** (see §Test debt).

**There is no SEAH escape hatch.** The hypothesis that a ticketing-owned SEAH vault legitimately needs its own key is dead: `docs/seah/02_vault_privacy_and_reveal.md` puts the vault in `public.grievance_vault_payloads` (`:20`) under the **same** `DB_ENCRYPTION_KEY` (`:48`, decision D-16); `complainants_seah`/`grievances_seah` were **dropped** (`:7`, `:23`, migration `pub004`); `public.*` owns "vault content **and key policy**" (`:101`) and "direct PII" in ticketing is forbidden (`:103`). No PII columns exist in `ticketing/models/` (only `ticket.py:6` "NO PII stored").

**⇒ The review's goal is right. Its diagnosis, its location, and its ordering are wrong.** The fix belongs in `backend/`.

---

## Test debt — this is the actual risk

- **No test imports `pii_vault`.** Not one. `decrypt_ciphertext`, `reveal_field`, `scrub_pii_value`, `grievance_pii_for_officer_card` are **entirely uncovered**.
- `tests/ticketing/test_ticket_access_matrix.py:68` probes `GET /tickets/{id}/pii` for **authz only** — it never mocks `get_grievance_detail`, so it hits the `except` branch (`routers/tickets/pii.py:56-68`) and asserts against the null-filled `_backend_unavailable` dict. **It passes identically whether decryption works or is deleted.**

**⇒ The very first commit of this ticket is a test, not a fix.**

---

## Order (BINDING — do not reorder)

Each step is its own commit. Do not proceed to the next until the current one is green.

```
1. TEST FIRST   — assert the officer card returns PLAINTEXT for a standard ticket.
                  Must pass on today's code (the vault workaround makes it pass).
                  This test is the safety net for steps 2-4. Without it you are
                  flying blind into a silent, invisible regression.

2. BACKEND FIX  — get_grievance_by_id decrypts server-side.
                  Step 1's test must STILL pass (now for the right reason).

3. DELETE       — remove ticketing's vault workaround.
                  Step 1's test must STILL pass (now via the API alone).

4. DROP KEY     — remove db_encryption_key from ticketing config + compose.
                  Step 1's test must STILL pass.
```

The invariant: **step 1's test is green at every commit.** If it ever goes red, the boundary is broken and you stop.

---

## Step 1 — the test net (commit 1)

New file `tests/ticketing/test_pii_boundary.py`:
- [ ] `GET /tickets/{id}/pii` for a **standard** ticket, with `get_grievance_detail` **mocked to return realistic API output**, returns **plaintext** `complainant_name` / `phone_number` / `email` / `address` — not `None`, not hex. **This is the regression guard for the whole ticket.**
  > Mock at the `grievance_api` client boundary (`ticketing/clients/grievance_api.py:37-48`), and parametrize the mock's payload over **ciphertext** (today's reality) and **plaintext** (post-step-2 reality) so the same test proves both. This is what makes it survive steps 2-4 unchanged.
- [ ] SEAH ticket ⇒ contact fields masked (`None`) per TP-15 — unchanged behavior, pinned so steps 2-4 can't quietly alter SEAH masking.
- [ ] Direct unit coverage for `grievance_pii_for_officer_card` (both `mask_sensitive_contact` arms) and `scrub_pii_value` / `looks_like_ciphertext` — currently zero.
- [ ] The reveal path: `grievance_reveal_content` (`pii_vault.py:146-154`) and `begin_reveal_session` (`clients/grievance_api.py:218`).

## Step 2 — backend decrypt (commit 2)

1. `grievance_manager.py:170` — `get_grievance_by_id` calls `self._decrypt_sensitive_data(...)` on the complainant columns before returning, mirroring `get_grievance_by_complainant_phone:537`.
   > Careful: `get_grievance_by_id` returns a **JOINed** row (`g.*` + `c.*`), not a bare complainant. `_decrypt_sensitive_data` (`base_manager.py:281`) operates on a dict keyed by the `ENCRYPTED_FIELDS` names, which **are** the joined column names — verify this on real data in-container, don't assume.
2. **Verify the fallback path too**: on JOIN failure the method falls back to `get_grievance_core_by_id` (`:181`). Confirm whether that path returns complainant columns at all; if it does, it needs the same treatment.
3. `base_manager.py:352` already shows a `self._decrypt_sensitive_data(grievance)` precedent — follow the established shape.

### ⚠️ Blast radius — this is a stable shared service

`get_grievance_by_id` has **~20 non-test callers**. CLAUDE.md §Service boundaries: *"stable shared services — modify only with clear intent + tests"*. **This is the only Tier-3 ticket that can regress the live chatbot.**

Verify each caller tolerates plaintext (most certainly want it — they render it to the user). **Grep the full list before committing**; at 2026-07-15 it was:

| Area | Callers |
|---|---|
| `backend/api/routers/grievance.py` | `:111`, `:206`, `:253`, `:307` |
| `backend/actions/forms/` | `form_modify_grievance.py:27,88,141,162,200`, `form_status_check.py:383` |
| `backend/actions/` | `action_outro.py:212`, `grievance_intake/classification.py:46`, `grievance_intake/sensitive.py:88`, `services/submit/classification.py:45`, `services/status_check/grievance_lookup.py:74`, `utils/ticketing_dispatch.py:96` |
| `backend/services/` | `LLM_services.py:478`, `postgres_services.py:195,634,795`, `grievance_manager.py:382` (self-call) |

- [ ] **Look specifically for double-decryption**: any caller that *already* decrypts what it receives will now decrypt plaintext. Check `_decrypt_sensitive_data`'s behavior on a non-ciphertext input — if it raises or corrupts, those callers break. **This is the most likely way this ticket breaks the chatbot.**
- [ ] `utils/ticketing_dispatch.py:96` matters especially — it feeds ticket intake. Confirm no PII starts landing in `ticketing.*` as a result (data rule #3). **This ticket must not cause PII to be cached into `ticketing.tickets`.**
- [ ] Run the **full** `tests/actions` + `tests/orchestrator` suites (baseline: 173 passed / 1 skipped) **and** `tests/backend`.

## Step 3 — delete the workaround (commit 3)

- [ ] Delete `decrypt_ciphertext` and `reveal_field` from `pii_vault.py`; `reveal_field` call sites collapse to plain passthrough.
- [ ] **Keep** `scrub_pii_value` / `looks_like_ciphertext` as a **defense-in-depth assertion**, not a masking behavior: if ciphertext ever reaches the officer card again, that is a **bug** and should be loud. Recommendation: log at `error` and return `None` (fail-closed on PII, consistent with HR-01's posture) — but **do not** silently mask. Record the decision in PROGRESS.md.
- [ ] `ticketing/models/base.py` engine import in `pii_vault.py` (`:16`) becomes unused — remove.

## Step 4 — drop the key (commit 4)

- [ ] Remove `db_encryption_key` from `ticketing/config/settings.py:47`.
- [ ] Remove `DB_ENCRYPTION_KEY` from the ticketing service's env in the compose stacks + `env.local` template. **Leave it on `backend`** — it is legitimately owned there (`base_manager.py:57`, `complainant_manager.py:43`, `scripts/database/init.py:203`).
- [ ] Update `docs/deployment/13_security.md` + `docs/seah/02_vault_privacy_and_reveal.md:58` (which documents the `pii_vault.py` hack as as-built) to reflect the unified boundary.
- [ ] **Fix `CLAUDE.md:121`** — the claim "Grievance API — primary data source, handles PII decryption" becomes true at step 2. It is currently false. Leave a note in PROGRESS.md that it *was* false.

---

## Tests (acceptance, sprint level)

- [ ] `tests/ticketing/test_pii_boundary.py` green at **every one of the 4 commits** (the invariant).
- [ ] A test asserting `ticketing/` no longer references `db_encryption_key` (grep-style guard, mirroring the `_KNOWN_UNAUTH_READS` sweep pattern from `authz-gaps-h2-03`) — prevents the key creeping back.
- [ ] Backend: a test that `get_grievance_by_id` returns **plaintext** for encrypted fields. **Verify red pre-fix** (the HR-04 standard).
- [ ] Full `tests/ticketing` green (baseline: **545 passed / 5 skipped / 0 xfailed**).
- [ ] Full `tests/actions` + `tests/orchestrator` green (baseline: **173 passed / 1 skipped**).

## Manual verification

- [ ] Officer portal, standard ticket: complainant card shows a **real name/phone/email/address** (not "—", not hex). This is the check the whole ticket exists for.
- [ ] Officer portal, SEAH ticket: contact fields masked; reveal flow still works.
- [ ] Chatbot: file a grievance end-to-end, then status-check it — the modify/status flows read `get_grievance_by_id` and must still render correctly (blast-radius check).
- [ ] `docker compose ... up` with `DB_ENCRYPTION_KEY` **absent from ticketing's env**: ticketing serves normally and PII still renders (proves the key is genuinely unused).

---

## Out of scope — log, don't fix

**`grievance_content.py` cross-schema direct read.** `ticketing/services/grievance_content.py:22-38` reads `public.grievances` **directly via ticketing's own DB session**, selecting `grievance_description` (the raw narrative). Callers: `engine/ticket_actions.py:210`, `routers/tickets/crud.py:469`. Ticketing also directly reads `public.file_attachments` (`routers/tickets/files.py:91`, `api/ticket_access.py:167`).

This violates data rules #1/#5 **more than `pii_vault` ever did**, and it means **"single auditable PII boundary" is not fully restored by this ticket**. It is nonetheless a **separate concern** (narrative/file content, not PII decryption), with a different blast radius (HR-02's `require_file_access` was deliberately built on the file read), and folding it in would double this ticket's risk.

→ Tracked: [`followups/ticketing-cross-schema-direct-reads.md`](followups/ticketing-cross-schema-direct-reads.md) + TODO.md row. **State this limitation explicitly in the sprint summary** — do not claim the boundary is fully unified.
