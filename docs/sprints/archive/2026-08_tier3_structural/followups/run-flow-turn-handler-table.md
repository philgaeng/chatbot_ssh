# `run_flow_turn` handler table (T3-02 p4) — not done, and cheaper to size honestly

**Status:** ✅ **CLOSED 2026-07-15** — done, and the re-sizing was settled by doing it: it was an **M**.
> **Opened:** 2026-07-15 by **T3-02 p3** (D-53) · **Size:** M (**not** the S the spec assumed) · **Priority:** low — reviewability, not correctness

## Outcome

Shipped. `run_flow_turn`: **1,485 lines at sprint start → 150 (−90%)**; the 20-arm chain is
gone, 1,077 lines of it replaced by a dict lookup, a default and one call. 20 handlers, 20
table entries, p1's `_recover_from_unknown_state` as the default via a thin adapter.

**The re-sizing held.** Every one of this doc's DoD items had to happen before the "22
one-line entries" existed to write: 19 arms and ~1,058 lines extracted first. The spec's
"S / cheap, safe part" was measuring the last 5% of the job.

**The gate paid for itself.** p2's characterization net passed **unchanged** — 214 passed /
1 skipped before and after. A 1,025-line restructuring with zero behaviour change, and the
proof is the net, not the reviewer's confidence.

**Extraction proven verbatim**, per DoD item 2: all **1,025 non-blank moved lines reappear
verbatim** (modulo the 4-space dedent), 0 missing.

**A trap worth recording, because I walked into it.** DoD item 2 says resolve dependencies
by parsing (D-50). I did — but through a **hand-listed whitelist** of interesting names,
which silently hid three real dependencies (`msg_text`, `payload_raw`, `tracker`). A
whitelist is a hand-list wearing a parser's clothes; the second pass resolved free variables
against real module globals and found them. **D-50, fourth instance.**

**The real win is not the table.** Each handler now declares exactly the inputs its body
reads, which the chain structurally could not record — every arm had the whole of
`run_flow_turn`'s scope in reach whether it used it or not. Nothing said that
`_h_location_method` reads only `intent`, or that `_h_map_location` is the sole branch
depending on `msg_text`/`payload_raw`. Now the signatures do.

**And what it did NOT buy** (DoD item 5, honoured): no behaviour change, no correctness win,
no bundle/perf claim. In particular the table is blind to D-51/D-52/D-59 — a *recognized*
state that dispatches nothing passes the lookup and never reaches the default. That class is
owned by the turn postcondition, which landed first for exactly that reason. This doc
predicted it; it is now stated in the code so nobody re-derives it the hard way.

---

### Original finding (kept for the record)


## What was planned

T3-02 p4: *"replace the `if/elif` chain with a `dict[str, Handler]` dispatch + the part-1
`else` as the default. The table itself is the **cheap, safe part** — 22 one-line entries
against a proven signature. It buys reviewability, not correctness."* Marked **STRETCH** in
the sprint README.

## Why it is not done — the sizing rests on a premise p3 does not deliver

"22 one-line entries against a proven signature" is true **only if every branch already has
that signature**. p3 extracted **one** branch (`status_check_form`, the 303-line monster the
spec correctly identified as where the risk lives). The other 19 arms are still inline:

| | |
|---|---|
| arms in the chain | **20** |
| branch bodies still inline | **~1,058 lines** |
| arms > 40 lines still inline | `done` 120 · `modify_grievance_menu` 107 · `add_missing_info_otp_flow` 102 · `contact_form` 101 · `map_location` 94 · `main_menu` 92 · `form_seah_1` 72 · `otp_form` 65 · `add_missing_info_flow` 53 · `add_more_info_flow` 47 |

So p4 is not "write a table". It is **"extract 19 more branches, then write a table"** — the
table is the last 5% of it. The spec's own sequencing rationale is what makes this visible:
it sized p4 as cheap *because p1-p3 would have done the extraction work first*, but p3's
scope as written is `status_check_form` only.

**This is not an argument against p4** — it is an argument against doing it in the hour the
"S" estimate implies. Measured, it is an M.

## What p3 already banked

`run_flow_turn`: **1,485 → 1,175 lines (-21%)** across p1 + p3, chain integrity intact
(20 arms + the terminal `else`). The two handlers extracted
(`_status_check_route_intent`, `_status_check_run_active_form`) prove the convention scales
to the hardest branch in the file, which is the useful half of the evidence p4 needed.

## Do not expect p4 to fix the dead-air class

Worth stating because it is tempting: the table does **not** subsume D-51 or D-52. Both are
silences *inside* a recognized branch — the dict lookup succeeds, the default never fires.
See [`add-more-info-silent-turn.md`](add-more-info-silent-turn.md) and
[`unknown-active-loop-silent-fallback.md`](unknown-active-loop-silent-fallback.md); the
`run_flow_turn` postcondition proposed there is what actually closes that class, and it is
**cheaper than p4 and worth more**. If only one of the two gets done, do the postcondition.

## Definition of done

1. Characterize before extracting, branch by branch — p2's rule, and the reason p3 was safe.
   `done` (120), `modify_grievance_menu` (107) and `contact_form` (101) are the least-covered
   of the big ones; the three `add_*` are already characterized by p2.
2. Extract each arm to the in-file convention `(session, dispatcher, domain, slot_updates,
   latest_message) -> next_state`, extras keyword-only. **By line range, never retyped**
   (D-50), with a verbatim-multiset check per commit (p3's proof).
3. One branch per commit, gate green at each (the T3-05 discipline).
4. Only then the table, with T3-02 p1's `_recover_from_unknown_state` as the dict default —
   it already takes the handler signature, which is why p1 wrote it that way.
5. Expect no behaviour change and no bundle/perf win. **It buys reviewability. Claim nothing
   else** — D-46 is the sprint's cautionary tale about a refactor sold on a benefit it could
   not deliver.

## Related

- `01-conversation-layer-spec.md` §2 part 4 — the original plan
- D-46 — "the headline claim does not survive measurement"; do not repeat it here
