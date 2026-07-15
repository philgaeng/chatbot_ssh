# Tier-3 reassessment — what the review got wrong

> **Read this before any Tier-3 ticket.** · Performed 2026-07-15 on `dev/tier3-structural` (fresh off `dev/tier2-quality` @ `87fbba86`).
> **Method:** four independent adversarial assessments (one per area), each required to produce file:line evidence and to *try to refute* the review's claim rather than confirm it. Every decisive claim below was then **re-verified by hand** — the agent findings alone were not trusted.
> **Source under assessment:** [`../../reviews/devils_advocate_codebase.md`](../../../reviews/devils_advocate_codebase.md) §3 Tier 3 (the 5-row table).

## Why this document exists

The Tier-3 table was written in the same pass as Tier-1 and Tier-2. Tier-1 and Tier-2 have since **shipped**, and the org-chart sprint landed in between. The Tier-3 rows were never re-verified against the resulting tree. When we did verify them, **four of five were materially wrong** — two of them wrong in ways that would have caused a regression if implemented as written.

Scoring the review honestly: it was **right about the code being bad** in all five places. It was wrong about *why*, *how much*, and — critically — *in what order*.

> **§6 was added later (2026-07-15) and is not about the review** — the review never examined the `ticketing.*` ↔ `public.*` boundary at all. It is here because §3's own follow-up finding did not survive the same scrutiny this document applies to everything else. **It carries a DECISION that supersedes `CLAUDE.md` §Data rules #1/#5, and a security finding (two unauthenticated grievance endpoints) that no review has ever caught.** If you are here for the boundary, the data rules, `grievance_content.py`, or the "single auditable PII boundary", **read §6 and ignore §3's closing paragraph.** New tickets: **T3-06** ([`05`](05-grievance-api-hardening-spec.md)), **T3-07** ([`06`](06-boundary-policy-spec.md)).

## Verdict table

| # | Review's claim | Verdict | Corrected finding |
|---|---|---|---|
| 1 | Decompose `run_flow_turn` (1,485 lines, CC≈120) into a state→handler table; delete dead branches — **L** | **Confirmed, complexity understated, effort overstated** | 1,485 exact ✓ but **CC = 189**, not ~120. Shape is *unusually* table-friendly. 2 dead branches provable. Real risk is one 304-line branch. → **M** |
| 2 | Split the 4,372-line settings page into per-tab components — **L** — "kills the hooks-crash class" | **Half-wrong** | Shell already clean (206 lines); hooks-crash **already fixed by HR-06 in Tier 1**; org sprint already extracted 7,748 lines. Purely mechanical now. → **S/M** |
| 3 | Route ticketing's PII decryption through the grievance API only; drop `DB_ENCRYPTION_KEY` — **M/L** | **Misdiagnosed; prescription order inverted and dangerous** | Not dual-pathed at all. Real defect is a backend omission. Executing as written silently blanks every officer contact card. → **M**, and it moves to `backend/` |
| 4 | Replace stack-introspection utterance lookup with explicit keys — **M** | **Scope wrong by 50×; probably a live bug** | 4 call sites, not ~200 (AST+MRO resolved, 0 unresolved). **3 of the 4 derive keys that do not resolve** ⇒ `ValueError`. **Reachability of those branches is UNTRACED** — decides Phase 1 (bug fix) vs Phase 3 (refactor), not whether the item exists. → **S** |
| 5 | Serialize voice-chunk uploads behind chunk-0's `upload_id` — **M** | **Correct** | Real, open, not mitigated by HR-07. Plus a second, unflagged silent-truncation path. → **M** |

---

## 1. `run_flow_turn` — confirmed, but the risk is somewhere else

**Measured:** `state_machine.py:819–2303` = **1,485 lines** (exact match to the review). File = **2,303** (exact). CC by AST count = **189** (134 `if` + 50 `BoolOp` short-circuits + 2 `except` + 1 loop + 1 comprehension) — the review's ~120 is **58% low**. Max nesting depth **9**; 97 `await`s.

**Shape — better than implied.** A flat 22-arm `if/elif state == "..."` chain at 4-space indent (`895`–`2292`), with:
- **Zero early returns inside the chain.** Only 3 `return`s exist in 1,485 lines: `876` and `893` (prologue, pre-dispatch) and `2303` (single common epilogue). Every branch falls through to one exit.
- **No fallthrough** — mutually exclusive `elif`s.
- **Only 4 cross-branch carriers:** `next_state` (78 assignments), `slot_updates` (accumulator), `dispatcher.messages` (accumulator), and read-mostly inputs (`session`/`domain`/`intent`/`latest_message`). Each branch builds its **own** `SessionTracker` + `CollectingDispatcher` (27 of each), so per-branch locals cannot leak.
- **The handler pattern already exists in-file.** Helpers at `435`, `450`, `491`, `509`, `537`, `621`, `712`, `816` already have the target signature `(session, dispatcher, domain, slot_updates, latest_message) -> next_state`. `_begin_location_method` (`494`) returning `"location_method"` (`509`) is a working handler today. **The seam is proven and partially migrated, not hypothetical.**

**Dead branches — 2 confirmed, verified by hand:**

| Branch | Lines | Proof |
|---|---|---|
| `form_dust` | 1039–1050 | `grep -rn '"form_dust"'` repo-wide returns exactly 2 hits: `state_machine.py:1039` (the comparison itself) and `form_loop.py:332` — where it is an **`active_loop`** value, a different namespace. Nothing writes it as a state. `_begin_road_hazard_intake` (`712`) unconditionally sets `next_state = "form_road_hazard"` even for `prefill_subtype="dust"` (called at `957`). Body is a duplicate of `form_road_hazard`. |
| `submit_grievance` | 1522–1540 | Same: repo-wide, the string appears **only** as its own comparison at `1522`. Nothing assigns it. |

Both proofs are airtight because **nothing outside `state_machine.py` writes `session["state"]`** (verified repo-wide; only tests do).

**REFUTED — SEAH branches are NOT dead.** `_is_seah_enabled()` (`159`) defaults `"true"`; both arms ship and are tested (`965` enabled, `973` flag-off; `test_orchestrator_api.py:130` sets false, `conftest.py:30` sets true). Deleting them would be a regression. Likewise `location_consent`/`location_method`/`grievance_review`/`map_location` look unassigned to a naive grep but are reached via helpers that *return* the state string (`491`, `509`, `537`, `435`) — **not dead**.

**NEW — latent bug the review missed.** There is **no terminal `else`** (verified via AST). An unrecognized `state` silently returns unchanged state with **zero messages** — dead air for the user. This is also a prerequisite for a table (a dict lookup needs a default).

**Where the risk actually is — the review's emphasis is backwards:**

| Branch | Lines | Coverage |
|---|---|---|
| `status_check_form` (`1555`) | **304** — 22% of the function, depth 9 | entry-level only (`test_form_loop.py`, `test_modify_grievance_flow.py`); interior `1562`–`1858` is the least-protected, highest-complexity code in the file |
| `add_more_info_flow` (`1859`), `add_missing_info_otp_flow` (`2015`), `add_missing_info_flow` (`2118`) | **205 combined** | **zero** state references in any test |

The table buys you 22 one-line dict entries. The complexity lives in one branch with thin coverage. **Get characterization tests on `1562`–`1858` before touching it.**

**Method note (recorded because it nearly inverted the finding):** an early `awk` scan reported *no* branches at all, because gawk treats `\b` as a backspace character, not a word boundary. Do not trust `awk`+`\b` on this codebase.

---

## 2. Settings page — the review is half-wrong

**The org sprint already did the hard part.** `components/settings/` is now **7,748 lines across 27 files** (`org/`, `officers-v2/`, `overview/`, `projects/`, staffing, go-live, project-types).

**The shell is already correct.** `app/settings/page.tsx:4167–4372` — `SettingsPage` is a **206-line** component doing role-gated tab routing and delegation. Every hook is called unconditionally *before* the `if (!isAdmin)` early return.

**Two review claims are dead:**
- **"Kills the hooks-crash class"** — already killed by **HR-06 in Tier 1** (see `2026-07_hardening/PROGRESS.md` HR-06: "Settings hooks-order fixed (0 `rules-of-hooks` errors)"). There is no violation left to fix.
- **"L effort"** — no longer true.

**What actually remains** — six tab clusters still defined inline (line numbers @ 2026-07-15):

| Block | Lines | ~Size |
|---|---|---|
| Workflows (`StepForm`, `WorkflowEditor`, `WorkflowNotificationsPanel`, `NewWorkflowModal`, `WorkflowsTab` + 6 helpers) | 765–2172 | ~1,410 |
| Projects (`ProjectsSection`, `ProjectCreateModal`, `ProjectEditor`, `PackageRow`, `PackageCreateModal`) | 2426–3776 | ~1,350 |
| Roles (`RoleEditModal`, `RoleCreateModal`, `RolesTab`) | 166–564 | ~440 |
| `SystemConfigTab` + JSON defaults | 3777–4123 | ~350 |
| `LocationsSection` | 2173–2425 | ~253 |
| `AdminAccessTab` | 565–764 | ~200 |

**The seams are clean.** Every shared symbol was mapped; only **two** cross cluster lines:
- `RoleCreateModal` (defined `308`) — used by `RolesTab` (`460`) **and** the workflows `StepForm` (`871`).
- `ProjectWorkflowsEditor` (defined `1144`, workflows cluster) — used by `ProjectEditor` (`3099`, projects cluster).

Both resolve as ordinary imports. `friendlyError` (34 uses across every block) becomes a shared util. `statusBadge`/`typeBadge`/`workflowTrackOf` are workflows-cluster-internal.

**Honest remaining benefit:** bundle size, reviewability, parallel work. **Not** crash-class elimination — that is already banked.

---

## 3. PII — misdiagnosed, and the prescription would have caused an outage

### The claim is refuted: there is no dual path

`ticketing/services/pii_vault.py:49–73` is the **only** decryption site in ticketing. The decisive detail — **there is no `FROM` clause**:

```python
text("SELECT pgp_sym_decrypt(decode(:ct, 'hex'), :key) AS decrypted")
```

It passes a ciphertext **already in hand** plus `settings.db_encryption_key`. Ticketing uses Postgres as a **pgcrypto oracle**, not as a PII datastore: no complainant table, no `public.*` PII row, no join. The engine (`ticketing/models/base.py:15-25`) happening to point at the same DB is what makes the trick work.

So *"decrypts directly from the DB, bypassing the grievance API"* is **false**. Every ciphertext fed to `decrypt_ciphertext` **came from** the API. Trace `routers/tickets/pii.py:55 → 73 → 81`: fetch via API → unwrap → `grievance_pii_for_officer_card` → `reveal_field` → `decrypt_ciphertext`. The vault is **post-processing on API output**, not a competing retrieval path.

**Correct characterization: one fetch path, split decryption responsibility.**

### The real root cause — a backend omission the review never diagnosed

`backend/services/database_services/grievance_manager.py:153–181` — `get_grievance_by_id` JOINs `complainants` and returns `_parse_database_result(results[0])`, which (`base_manager.py:729-734`) **only parses JSON — it never decrypts**. Its sibling `get_grievance_by_complainant_phone` **does** call `self._decrypt_sensitive_data(complainant)` (`grievance_manager.py:537`).

**⇒ `GET /api/grievance/{id}` returns pgcrypto hex ciphertext** for the four `ENCRYPTED_FIELDS` (`base_manager.py:63-68`: `complainant_phone`, `complainant_email`, `complainant_full_name`, `complainant_address`).

`pii_vault.py` is a **client-side workaround for a server-side bug**. Its own module docstring admits it:

> *"The grievance GET endpoint may return pgcrypto hex ciphertext when fields were not decrypted server-side."*

**`CLAUDE.md:121` ("Grievance API — primary data source, handles PII decryption") is aspirational and factually false today.** `docs/seah/02_vault_privacy_and_reveal.md:58` documents the `pii_vault.py` hack as as-built.

### The SEAH escape hatch does not exist

The hypothesis that would have made the review *wrong to even attempt* — a ticketing-owned SEAH vault legitimately needing its own key — is **dead**:
- `docs/seah/02_vault_privacy_and_reveal.md:13` — "One data domain in `public.*` for standard **and** SEAH"
- `:20` — vault = `public.grievance_vault_payloads`
- `:7`/`:23` — `complainants_seah`/`grievances_seah` were **dropped** (`pub004`)
- `:48` — SEAH PII uses the *same* `DB_ENCRYPTION_KEY` / `complainant_manager` scheme (decision D-16)
- `:101` — `public.*` owns "vault content **and key policy**"; `:103` — forbidden: "direct PII" in ticketing

Corroborated in code: `grep` for PII columns in `ticketing/models/` returns nothing but `ticket.py:6` ("NO PII stored").

### Why the review's order is dangerous

Drop `DB_ENCRYPTION_KEY` from ticketing **first**, as the review says, and `looks_like_ciphertext` → `scrub_pii_value` silently maps every contact field to `None` (`pii_vault.py:44-45`). Officers see "—" on every standard contact card, **with no error**. The failure is invisible.

**And it is guarded by nothing:**
- **No test imports `pii_vault`.** Not one. `decrypt_ciphertext`, `reveal_field`, `scrub_pii_value`, `grievance_pii_for_officer_card` are entirely uncovered.
- `tests/ticketing/test_ticket_access_matrix.py:68` probes `GET /tickets/{id}/pii` for **authz only** — it never mocks `get_grievance_detail`, so it hits the `except` branch (`pii.py:56-68`) and asserts against the null-filled `_backend_unavailable` dict. **It would pass identically whether decryption works or is deleted.**

### Effort and blast radius

The review sized M/L. The *fix* is ~1 line. The **work** is the blast radius: `get_grievance_by_id` has **~20 non-test callers** across `backend/actions/` (forms, intake, outro, dispatch), `backend/api/routers/grievance.py`, `backend/services/LLM_services.py`, `postgres_services.py`, and the orchestrator conftest. Making it decrypt changes what all of them receive. This is squarely CLAUDE.md's *"stable shared services — modify only with clear intent + tests"*.

**⇒ M**, and it lives in `backend/`, not `ticketing/`.

### Also found — a genuine violation the review missed

> **⚠️ SUPERSEDED BY §6 (2026-07-15). Read §6 before acting on this paragraph.** The framing below — "violation", to be fixed by routing reads through the API — **does not survive scrutiny**. Measured: the rule it cites protects a goal both sides of the codebase abandoned long ago; the API it would route to is unauthenticated, unlogged and unaudited; and the migration would be a *security downgrade* that converts a PII-free query into a PII-bearing one. The surface is also **11 statements across 5 tables including 3 writes**, not the 3 reads listed here. The boundary policy was decided on 2026-07-15 — see §6 → *DECISION*.

`ticketing/services/grievance_content.py:22-38` reads `public.grievances` **directly via ticketing's own DB session**, selecting `grievance_description` (the raw narrative). Callers: `engine/ticket_actions.py:210`, `routers/tickets/crud.py:469`. Ticketing also directly reads `public.file_attachments` (`routers/tickets/files.py:91`, `api/ticket_access.py:167`).

This violates data rules #1/#5 (CLAUDE.md §Data rules) **more than `pii_vault` ever did**. "Single auditable PII boundary" is **not** restored by touching `pii_vault` alone. → [`followups/ticketing-cross-schema-direct-reads.md`](followups/ticketing-cross-schema-direct-reads.md).

---

## 4. Utterances — scope wrong by 50×, and (probably) a live bug

> **Corroborated independently (2026-07-15).** A second assessment — the agent that did the H2-08 utterance-mapping work during Tier 2 — reached the same conclusions from the opposite direction (it knew the mapping data; this pass knew the call graph). It independently identified **the same three failing sites and the same `form_otp` control**, the same two-mechanism/MRO split, and the same `file_name` derivation as the real refactorability blocker. Two independent passes converging on the same three sites is the strongest evidence in this document.
>
> **It also corrected this pass twice** — see §Corrections below. Its framing of the core problem is better than the original and is adopted here: **with introspection keys you cannot determine statically whether a lookup resolves.** That is not a caveat weakening the finding; it *is* the finding.

### There are two `get_utterance` implementations; the review conflated them

| Impl | Key derivation | Call sites |
|---|---|---|
| `base_mixins.py:303` (`ActionHelpersMixin`) | `self.name()` — **already explicit** | **196** |
| `base_classes.py:118` (`BaseFormValidationAction`, line 74) | `inspect.currentframe().f_back.f_code.co_name` — **introspection** | **4** |

`BaseAction` (`base_classes.py:21`) inherits the explicit mixin; `ProfileAwareAskAction`, `BaseOtpAction`, `BaseActionSubmit` all extend `BaseAction`. Only `BaseFormValidationAction` **overrides** with introspection.

**⇒ 4 call sites, not ~200. The M sizing came from assuming the latter.**

#### How the count was settled (method — reproduce before trusting)

The two assessments initially disagreed: **4 / 196** (this pass) vs **6 / 180** (the H2-08 pass). Settled by full **AST + MRO resolution** over `backend/actions/` — parse every `ClassDef`, walk bases by name to find which base provides `get_utterance`/`get_buttons`, and attribute each `self.get_*` call site to the implementation its MRO actually selects:

```
TOTAL self.get_utterance/get_buttons call sites: 200
  via BaseFormValidationAction (INTROSPECTION): 4
  via ActionHelpersMixin (EXPLICIT self.name()):  196
  unresolved: 0
```

**Do not grep this question.** `ValidateFormOtp(bases=['BaseFormValidationAction', 'BaseOtpAction'])` is a multiple-inheritance case where the leftmost base's override wins — a grep for the file or the method name gets it wrong. The 0-unresolved result is what makes the count trustworthy: every site is attributed, none guessed.

**The count was never load-bearing.** 4 vs 6 does not move the effort estimate; both passes independently concluded *below M*. It is recorded because the *method* matters for the `file_name` follow-up, which needs the same resolution over ~200 sites.

### 3 of the 4 are broken at runtime — verified by hand against the live mapping

`get_utterance_base` **raises `ValueError`** on a missing key (`utterance_mapping_rasa.py:2310-2312`).

| Call site | Derived key | Exists in `UTTERANCE_MAPPING`? |
|---|---|---|
| `forms/form_otp.py:352` | `validate_otp_input` | ✅ resolves |
| `forms/form_grievance_complainant_review.py:495` | `validate_grievance_cat_modify` | ❌ **missing → ValueError** |
| `forms/form_seah_1.py:199` | `validate_sensitive_issues_follow_up` | ❌ **missing → ValueError** |
| `forms/form_story_main_route_step.py:33` | `validate_language_code` | ❌ **missing — `form_story_main_route_step` is not even a top-level mapping key** |

These sit on **error/re-prompt branches** only — which is exactly why nobody noticed.

### ⚠️ OPEN QUESTION — reachability is NOT traced

**The three keys provably do not resolve. Whether the branches that call them are reachable at runtime is UNTRACED.** They may be dead, or swallowed upstream. **Do not describe this item as a confirmed live bug until the trace is done.**

An earlier draft of this document asserted that `form_grievance_complainant_review.py:495` was "reachable AND swallowed". That was wrong and is retracted: what was verified is the **swallow mechanism**, not the **reachability** of the branch. The distinction is recorded because it is the kind of overreach this document exists to prevent.

What *is* established, per site:

| Site | Key resolves? | Wrapped in `try/except`? | Branch reachable? |
|---|---|---|---|
| `form_grievance_complainant_review.py:495` | ❌ no | ✅ **yes** — `try:` at `:493`, `except Exception` at `:525` → `SKIP_VALUE` + `LLM_GENERATED` | **UNTRACED** |
| `form_seah_1.py:199` | ❌ no | **UNCHECKED** | **UNTRACED** |
| `form_story_main_route_step.py:33` | ❌ no | **UNCHECKED** | **UNTRACED** |
| `form_otp.py:352` | ✅ yes (control) | — | — |

**The uncertainty is the indictment, not a weakness in the finding.** With introspection keys you *cannot answer this statically* — which is precisely the argument for explicit keys, and precisely why the H2-08 integrity tests (which validate the mapping **data**) cannot catch it. A finding that can only be resolved by manual runtime tracing is the definition of an unmaintainable lookup.

**This decides the ticket's phase, not its existence:**
- **Reachable** ⇒ T3-01 stays **Phase 1** as a latent-bug fix; log per the deferral rule.
- **Dead or fully swallowed** ⇒ T3-01 demotes to **Phase 3** as a pure refactorability item, and the three branches become a *dead-code* finding in their own right.

Either way the deliverable is unchanged: explicit keys + the call-site-walking test.

**Trace guidance** (~10 min): start with `ValidateMenuForm.validate_language_code` (`form_story_main_route_step.py:33`) — the cleanest case. It is reachable iff `language_code` can be filled with a value outside `["en","ne"]`, so the question reduces to whether that slot is button-only or accepts free text. It is also the one where the **file key is absent entirely**, not merely the action key. Then check whether `form_seah_1.py:199` and `form_story_main_route_step.py:33` sit inside a `try/except` — only the category-review site has been checked.

### The silent swallow — confirmed mechanism, unconfirmed impact

`form_grievance_complainant_review.py:493` opens a `try:`; `:525` catches `except Exception` → logs → returns `SKIP_VALUE` + `LLM_GENERATED`. **If** that branch is reachable, then when a user is *happy with their category selection* the confirmation utterance throws, is caught, and the form **silently returns the wrong state** — the user never sees the message and a missing utterance is laundered into a skip.

The swallow is verified. The "if" is the open question above. Note the swallow is independently worth fixing regardless of the trace result: a bare `except Exception` that converts *any* failure into a `SKIP_VALUE` is a bug-concealer by construction.

### Evidence it has already bitten

- **Dead defensive scaffolding:** `check_form_function_name` (`base_mixins.py:313`) is a key-existence checker that is **defined and never called anywhere**. Someone built the guard for exactly this problem and never wired it up.
- **Historical fix:** commit `7e3dae34` "Add missing form_contact invalid-phone utterance."
- **The "can't extract a helper" claim is proven, not hypothetical:** contact validators were extracted to `services/contact/validators.py`; being module-level functions they could no longer use `self.get_utterance()`, and were forced onto explicit keys via `contact_utterance(...)` (`services/contact/utterances.py:6`). **The refactor-hostility already forced the workaround — H2-08 built the target pattern.**

### Also found — `get_buttons` carries the same introspection, but it is DEAD CODE

`base_classes.py:126` — `BaseFormValidationAction.get_buttons` uses the same `f_back.f_code.co_name` introspection. The review never mentioned it.

**Corrected 2026-07-15.** An earlier draft of this document claimed it "has the identical flaw — same fix, same pass." **That is wrong.** The AST+MRO resolution shows **zero of the 200 call sites reach it**:

```
introspection by method: Counter({'get_utterance': 4})     # <-- no get_buttons
explicit by method:      Counter({'get_utterance': 120, 'get_buttons': 76})
```

All 76 `get_buttons` calls resolve through `ActionHelpersMixin` (explicit `self.name()`). The `get_buttons` calls that *appear* in the four introspection-site files are red herrings — they live in **sibling `Ask*` classes** in the same module, on a different base:

| File | Class | Base | Method |
|---|---|---|---|
| `form_otp.py` | `ValidateFormOtp` | `BaseFormValidationAction`, `BaseOtpAction` | `get_utterance` @ `:352` ← **introspection** |
| `form_otp.py` | `ActionAskOtpConsent`, `ActionAskOtpInput` | `BaseOtpAction` → `BaseAction` → `ActionHelpersMixin` | `get_buttons` @ `:60`, `:85` ← **explicit** |
| `form_seah_1.py` | `ValidateFormSeah1` | `BaseFormValidationAction` | `get_utterance` @ `:199` ← **introspection** |
| `form_seah_1.py` | `ActionAskFormSeah1*` (×4) | `BaseAction` | `get_buttons` @ `:289`, `:321`, `:335` ← **explicit** |

**⇒ `BaseFormValidationAction.get_buttons` (`base_classes.py:126`) is unreachable. Delete it — do not "fix" it.** Deleting is free and removes an introspection site that would otherwise re-seed the bug class the moment someone adds the first caller.

This correction is why the count method matters: a file-level grep sees `get_buttons` in `form_seah_1.py` next to a broken `get_utterance` and concludes they share a fate. They do not.

### The bigger implicit key — deferred

`file_name` is derived from `self.__class__.__module__.split(".")[-1]` (`base_mixins.py:63`), and this applies to **all ~200** call sites, not just the 4. **Move a class to another file and its copy silently breaks.** If the goal is genuinely "makes the chatbot refactorable", *this* is the valuable target — and it is genuinely M+. → [`followups/utterance-file-name-derivation.md`](followups/utterance-file-name-derivation.md).

### Test net — exists but has exactly the wrong shape

`tests/actions/test_seah_utterance_integrity.py` (H2-08, 54 tests) is parametrized over `SEAH_FORMS = ["form_seah_2", "form_seah_focal_point"]` and walks the **dict**, not the **call sites**. It would not have caught any of the 3 failures — `form_seah_1` isn't in `SEAH_FORMS`, and no test asserts that a call site's *derived* key resolves. **That asymmetry is why the bugs survived H2-08.**

**This is not a criticism of H2-08.** H2-08's scope was the utterance **data** for SEAH, and it delivered it: the broken NE was repaired, the drifted duplicate blocks were merged into one shared dict, and 54 integrity checks now assert every SEAH utterance resolves in `en`+`ne`, that `ne != en`, and that victim/focal share a block. That work is sound and done. The **lookup mechanism** was never in its scope and remains untouched — which is exactly why the two findings are complementary rather than overlapping, and why H2-08's research is evidence *for* this item.

### Corrections to this document (2026-07-15)

Logged rather than silently edited, because a reassessment document that hides its own errors is worth nothing:

| # | Claim as first written | Correction | Source |
|---|---|---|---|
| C-1 | "`get_buttons` has the identical flaw — same fix, same pass." | **Wrong.** Zero call sites reach it; it is **dead code**. Delete, don't fix. | AST+MRO resolution (this session) |
| C-2 | "`form_grievance_complainant_review.py:495` is reachable AND swallowed." | **Overreach.** The *swallow* is verified; **reachability is untraced** for all three sites. | Second assessment (H2-08 agent) |
| C-3 | Call sites "4 / 196" vs a second pass's "6 / 180". | **4 / 196 confirmed** by AST+MRO, 0 unresolved. Not load-bearing — both passes concluded *below M* regardless. | AST+MRO resolution |

C-2 is the one that matters. It came from the second assessment refusing to assert reachability it hadn't traced — the same discipline this document demands of the source review. The framing it supplied ("with introspection keys you cannot tell statically whether a lookup resolves") is stronger than the original argument and has been adopted above.

---

## 5. Voice chunks — the review is correct

### Protocol

- Chunker: `channels/REST_webchat/modules/voiceNote.js` (MediaRecorder, `CHUNK_TIMESLICE_MS = 1000` at `:8`)
- Transport + retry: `channels/REST_webchat/modules/voiceChunkUpload.js`
- Endpoints: `POST /upload-voice-chunk`, `/upload-voice-complete` (`config.js:24-26`)
- Handler: `backend/api/routers/files.py:390-482` · Core: `backend/services/file_server_core.py:302-333`

Chunk 0 mints the id: a chunk with no `upload_id` is only legal at `chunk_index == 0` (`files.py:423-436`), which calls `create_voice_chunk_session()` and returns `upload_id` (`files.py:466`). Chunks 1..N **must** carry it. The server is **strict-sequential**, appending to one `.part` file: `chunk_index < expected` → `{"duplicate": True}` (`file_server_core.py:315-316`); `chunk_index > expected` → `ValueError("chunk_out_of_order")` → **409** (`:317-318`, `files.py:451-452`).

### The race

Uploads fire **fully concurrently** — no `await`, no queue (`voiceNote.js:121-127`, inside `ondataavailable`, every 1 s):

```js
const index = chunkIndex;
chunkIndex += 1;
void uploadRecordingChunk(event.data, index).catch((error) => {
```

The only join is at *stop*: `await Promise.all(pendingChunkUploads)` (`:220`). Nothing serializes chunk 1 behind chunk 0 during recording.

It is the **"no id"** variant (not wrong-id, not duplicate-session). `uploadRecordingChunk` reads module-level `uploadId` at call time (`:75`), assigned only inside chunk 0's `.then()` (`:85-89`). If chunk 0's response hasn't returned by t=2000 ms, `uploadId` is still `null` and `voiceChunkUpload.js:67` simply omits the field → `files.py:423-428` → **400 `"upload_id required for chunk_index > 0"`**.

### Why retry does not save it — the load-bearing detail

`uploadVoiceChunk` builds the `FormData` **once** (`voiceChunkUpload.js:65-74`) and the retry closure re-posts that frozen body (`:76` → `withRetry` at `:37-49`):

```js
return withRetry(() => postVoiceChunk(formData));
```

All 3 attempts (800/1600 ms backoff) resend an **identical id-less body** and 400 each time — even though `uploadId` became available meanwhile. **The retry is structurally incapable of healing this race.**

Then `isIgnorableLateChunkError` (`voiceNote.js:25-35`) matches only `"upload session expired"`, `"not found"`, `"out of order"`, or `isStopping && (404|409)`. `"upload_id required for chunk_index > 0"` matches **none** → error propagates → `:123-127` → `stopRecording(..., "upload_error")` → `resetUploadState()` (`:206-212`).

**Concrete failure:** on a link with RTT > 1 s the user taps record; at the 2-second mark chunk 1 is built id-less, 400s three times over ~2.4 s, and **the entire recording is aborted and discarded** with a generic upload error. Deterministic on 2G/3G, invisible on dev wifi — which is why it survived.

### HR-07's send lock does NOT cover this — decisive

`app.js:59-64` says so outright:

```js
/** In-flight text-send lock: blocks a double-submit (double Enter / double click)
 *  until the orchestrator response resolves... */
let isSending = false;
```

Its only guard is gated on a non-empty **text** `message` (`app.js:934`: `if (message && isSending) return;`), set/cleared only around `window.safeSendMessage(message)` (`:959-962`). `beginSendLock` disables `sendButton` (`:910`) — not the record button. `voiceNote.js` never imports or consults it; `grep -rn 'isSending|sendLock'` hits **only** `app.js`. **This item is not already done.**

### Server behavior — rejects, doesn't corrupt

Id-less chunk>0 is rejected before session creation (`files.py:423-428`); out-of-order before the append (`file_server_core.py:317-318`). Failure mode is **hard-fail / data loss, not corruption**. Not benign — the flagship feature just dies.

### NEW — a second, unflagged bug: silently truncated voice notes

`isIgnorableLateChunkError`'s `"out of order"` match (`voiceNote.js:32-34`) is **unconditional** — not gated on `isStopping`/`uploadFinalized`. A 409 mid-recording that exhausts its 3 retries is silently swallowed (`:92-95` returns `null`), the chunk is lost forever, and every later chunk then 409s against a now-permanently-behind `next_chunk_index` → `completeVoiceUpload` **succeeds** and produces a **silently truncated** voice note. Serializing the queue eliminates this class too.

### Tests

Happy-path only, sequential, single-threaded: `tests/backend/test_fastapi_files.py:251` (`test_upload_voice_chunk_and_complete`), `:313` (`test_upload_voice_chunk_duplicate_is_idempotent`). **No test sends chunk 1 without an `upload_id`; none exercises concurrency or out-of-order. There is no JS test suite for `channels/REST_webchat/` at all.**

---

## 6. The boundary itself — reassessed (added 2026-07-15, after §3)

> **Why this section exists.** §3 closed by flagging `ticketing/services/grievance_content.py` as *"a genuine violation the review missed"* and deferring it to [`followups/ticketing-cross-schema-direct-reads.md`](followups/ticketing-cross-schema-direct-reads.md). Both took for granted that the rule being violated is sound, and that routing the read through the grievance API would improve matters. **Neither holds.** This section supersedes §3's "Also found" paragraph and the followup's stated justification.
>
> **Trigger:** the observation that this repo was built by *two* AI systems in parallel — Claude on `ticketing/`, Cursor on the chatbot — and that some boundaries might be artifacts of that split rather than architecture.
> **Method:** three independent assessments (git/doc archaeology · a full measured inventory of every cross-boundary touch · deployment + API reality), each required to produce file:line evidence. Every decisive claim below was **re-verified by hand**. Two agent claims were refuted and are recorded in §Corrections rather than carried.

### The hypothesis is half right — and the half it gets wrong matters more

**Rules #1/#2 (no joins, no cross-schema FK) are NOT an artifact.** They predate `CLAUDE.md` by 5.5 weeks. `docs/ticketing_system/04_ticketing_schema.md` @ `7b696559` (**2026-03-11**), verbatim:

> - **Isolation**: keep ticketing data in its **own schema / table group** (no cross-FKs into existing grievance tables).
>
> This makes it easy later to:
> - Move ticketing to a **separate database** by copying only the ticketing schema and changing the connection string, and
> - Keep the chatbot working if ticketing is offline or removed.

That is real architecture — future service/DB extraction plus blast-radius containment — written when the only agent in the room was human. **The decisive disconfirmation:** when the two-tool split was retired (`a371e4a4`, 2026-06-23), that commit dissolved the DO-NOT-TOUCH directory walls and rewrote the worktree model to *"no longer required"* — and **left the data rules untouched**. A pure coordination device would have been relaxed in that same commit. The rules read as arbitrary fiat today only because a doc reorg (`21631051`, 2026-06-02) **deleted the rationale** and left the bare rule behind.

**Rules #3/#4/#5 (the PII rules) ARE an artifact, and `pii_vault.py` is their scar.** They appear fully-formed in the first `CLAUDE.md` (`09140c02`, 2026-04-20) with **no rationale — and none was ever written anywhere in the repo's history.** That same commit shipped two things that explain them:

- **`.claudeignore`** — *"Claude Code must not read or modify any file listed here"* — listing `backend/api/`, `backend/services/`, `backend/task_queue/`, `scripts/database/`.
- **`docs/claude-tickets/context/existing-services.md:9`** — a **hand-written** substitute for the code Claude was forbidden to read: *"Primary data source. **Handles pgcrypto decryption of PII.** Never query `public.complainants` directly from ticketing."*

**That sentence was false when written and is still false** (§3 proves it: `get_grievance_by_id` never decrypts). It is the direct ancestor of `CLAUDE.md:121`. The causal chain is complete: Claude built against a *described* contract → hit ciphertext at runtime → could not fix `backend/services/`, which `.claudeignore` forbade it to open → wrote `pii_vault.py`, a client-side decrypt using the shared DB as a pgcrypto oracle. **`pii_vault.py` is not a design decision. It is scar tissue from a tool-access boundary.** T3-04 is still right to remove it — but it removes a *workaround*, not an architectural choice.

Note the original rule was also **narrower and better**: *"never query `public.complainants`"* — the PII table specifically. `CLAUDE.md`'s *"No SQL joins from `ticketing.*` into `public.*`"* is an over-generalization of it, and it is that broadened rule — not the PII-scoped one — that `grievance_content.py` violates.

### The finding that outranks the archaeology: the rules are vestigial

The March rationale states two goals. **Both are already dead in the code, in both directions, and neither death was noticed:**

| March 2026 goal | Status | Evidence (hand-verified) |
|---|---|---|
| "Move ticketing to a separate database by … changing the connection string" | **Impossible** | Ticketing issues **11 statements against `public.*` across 5 tables — 3 of them writes**: `UPDATE public.file_attachments` (`services/archiving.py:198`), `DELETE FROM public.grievance_classification_taxonomy` (`services/grievance_categories_catalog.py:147` — unqualified full-table wipe), `INSERT INTO …` (`:150`). |
| "Keep the chatbot working if ticketing is offline or removed" | **False** | The chatbot's **intake location validation** reads `ticketing.locations` + `ticketing.location_translations` — `backend/shared_functions/location_validator.py:100` (via its **own** `psycopg2.connect`), plus ~10 sites in `location_mapping.py` (`:69,85,123,141,224,…`). Remove ticketing and chatbot intake breaks. |

And the rule with the most teeth — *"`public.complainants` … never touch"* — is violated by a **Celery beat job every 2 minutes**: `ticketing/tasks/grievance_sync.py:178` `LEFT JOIN public.complainants c`. (In fairness, it extracts only `c.location_code`, not PII.) Neither the review nor the followup noticed.

**There is no enforcement mechanism of any kind.** One Postgres, one database (`app_db` — the `grievance_db` in `env.local` is dead config, overridden by every compose `environment:` block), and **one role (`user`) shared by backend, ticketing, and every Celery worker**. Only `ops` is privilege-separated (`ops_app`). `scripts/ops/create_scoped_roles.sql` is opt-in and inactive — and as written would grant ticketing `SELECT` on `public.grievances` only, i.e. **1 of the 5 tables it actually touches**, breaking the other four paths. The boundary's entire enforcement is comment headers on migration files.

**⇒ The rules were genuine architecture serving a real goal. The goal was abandoned in the code, by both sides, without anyone amending the rules.** That — not the AI split — is the actual finding.

### The followup's justification is inverted — do not execute it as written

[`followups/ticketing-cross-schema-direct-reads.md:50`](followups/ticketing-cross-schema-direct-reads.md) rests its option (a)/(c) on:

> *"**Auditability:** reads that go through `GET /api/grievance/{id}` **are** loggable, authorizable, and rate-limitable at one place."*

**Measured: none of the three is implemented.** The verb should be *"could be"*.

| | `GET /api/grievance/{id}` | Ticketing's "violating" direct read |
|---|---|---|
| **Authn** | **None** — `def get_grievance(grievance_id: str):` (`backend/api/routers/grievance.py:249-250`), no `Depends`. The `PATCH` 30 lines below **does** have `Depends(_ticketing_auth_check)` (`:283-288`). | Keycloak JWT — `Depends(get_authenticated_user)` (`routers/tickets/crud.py:430`) |
| **Authz** | **None** | `assert_ticket_visibility` — HR-02 SEAH + jurisdiction gate (`crud.py:446`) |
| **Audit** | **None.** No read-audit table exists in `backend/`; the success path has zero logger calls. | `REVEAL_ORIGINAL` / admin audit events (`routers/tickets/pii.py:124-141`) |

**⇒ Routing `grievance_content.py` through the API *as it exists today* is a security DOWNGRADE** — it replaces an authenticated, jurisdiction-gated read with an anonymous HTTP call, and discards the caller identity any future audit record would need. It would also turn a **PII-free** query (`_GRIEVANCE_SELECT` touches zero complainant columns) into a **PII-bearing** one, since the API response carries name/phone/email/address ciphertext. That is the opposite of the stated goal.

Two further corrections to the followup:
- **Its DoD item 2 is already done.** The API serves **9/9** of the fields `grievance_content.py` selects (via `SELECT g.*`, `grievance_manager.py:154-167`), and ticketing **already** reads `grievance_description` over HTTP today (`services/resolved_summary_builder.py:139-150`). Nothing needs building. What is missing is a **contract**: the endpoint has no `response_model`, so migrating would trade a pinned 9-column list for an untyped dict — *weaker* drift protection, not stronger.
- **The unpriced cost is `grievance_sync.py`.** It pages `public.grievances` 500 rows at a time every 2 minutes; the grievance API has **no list or bulk endpoint at all**. Folding it in (as the followup suggests at `:67`) means building one.

### DECISION (2026-07-15) — boundary policy

Taken by the project owner on the evidence above. **Supersedes CLAUDE.md §Data rules #1 and #5 as written.** This resolves the followup's DoD item 1, which correctly escalated it as *"a locked-architecture question — it needs an explicit decision, not an implementer's judgment call."* Implemented by **T3-07** ([`06-boundary-policy-spec.md`](06-boundary-policy-spec.md)) and **T3-06** ([`05-grievance-api-hardening-spec.md`](05-grievance-api-hardening-spec.md)).

1. **Drop the "no joins into `public.*`" rule.** It has been false for months, it protects a goal both sides abandoned, it has no enforcement, and honoring it today would *degrade* security. `grievance_content.py`, `files.py`, `ticket_access.py`, `archiving.py`, `grievance_categories_catalog.py` and `grievance_sync.py` are **legitimized as-built** — to be re-expressed as a documented, drift-guarded read/write contract rather than prosecuted as violations. → **T3-07**
2. **Keep "no cross-schema FK."** Verified zero today across `ticketing/models/` and `ticketing/migrations/versions/` — the only link is the soft `String(64)` `grievance_id` plus the `uq_tickets_grievance_id_active` partial index (HR-03). Cheap, holds, and it is the part that actually preserves extraction optionality and keeps the three migration streams independent. → guard test in **T3-07**
3. **Keep "no complainant PII columns in `ticketing.*`."** Verified zero today. This is the one PII rule that earns its keep on its own merits, independent of all the above. → guard test in **T3-07**
4. **Keep T3-04 unchanged.** Key custody — `DB_ENCRYPTION_KEY` in exactly one process — is real and independent of the retrieval-path question. The spec's four-commit order stands.
5. **New: T3-06 — harden `GET /api/grievance/{id}`.** authn + authz + read audit + `response_model`, plus authn on `POST /api/grievance/{id}/status`. This is the **prerequisite** for the API ever being a credible audit chokepoint; until it lands, "route reads through the API" is not on the table. → [`05-grievance-api-hardening-spec.md`](05-grievance-api-hardening-spec.md)

**The endgame the followup asked for is met by amendment, not by enforcement:** CLAUDE.md and the code will agree because the docs are corrected to describe what is actually built, with the two rules that genuinely hold pinned by tests.

### Security finding — surfaced by this pass, in no review

`POST /api/grievance/{grievance_id}/status` (`backend/api/routers/grievance.py:202-203`) is **unauthenticated**, mutates grievance state, and fires SMS + email to the complainant (`:227` → `_send_status_update_notifications`). `GET /api/grievance/{grievance_id}` (`:249`) is unauthenticated and returns the full record including `grievance_description`. Both are bound to the host at `docker-compose.grm.yml:117` (`5001:5001`). They are **not** proxied by prod nginx (no `location /api/grievance` block — only `/api/v1/` for ticketing), so internet reachability depends on the EC2 security group — **unverified from the repo, and worth checking directly.** → T3-06.

### Corrections — agent claims refuted by hand-verification

Recorded per this document's standing practice. Both would otherwise have shipped as facts.

| # | Claim as reported | Verdict |
|---|---|---|
| C-4 | "`env.local` is committed and contains a live OpenAI key, AWS access key/secret, `DB_ENCRYPTION_KEY`, and SMTP password." | **FALSE — not carried.** `git ls-files env.local` → not tracked; `.gitignore:105` ignores it. The agent read the local working-tree file and inferred it was in git. **No secrets are in the repo.** |
| C-5 | "`GET /api/grievance/{id}` — PII decrypted server-side." | **FALSE — not carried.** Contradicted by the third assessment *and* by §3's hand-trace: `_parse_database_result` (`base_manager.py:729-734`) parses JSON and never decrypts. The agent read a client-side docstring, not the code. |

---

## Consequences for the review document

[`../../reviews/devils_advocate_codebase.md`](../../../reviews/devils_advocate_codebase.md) §3 Tier-3 table is **known-wrong as written**. A correction pointer has been added to it referencing this document; the table itself is corrected at sprint close-out (per the sprint README's DoD), together with the re-score.

Specific corrections owed at close-out:
1. Tier-3 effort column: `M/M/L/M/L` → `S/M/M/M/S-M`.
2. `run_flow_turn` CC: ~120 → **189**.
3. "Split the settings page … kills the hooks-crash class" → hooks-crash was closed by HR-06; benefit is bundle/reviewability.
4. "PII decryption still dual-pathed in ticketing" → **not dual-pathed**; backend `get_grievance_by_id` omits decryption.
5. §2 "New top findings" bullet 2 and §1 backend-security "Remaining weakest point" both repeat the dual-path claim → same correction.
