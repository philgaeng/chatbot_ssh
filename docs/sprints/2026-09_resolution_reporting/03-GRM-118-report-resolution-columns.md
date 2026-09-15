# `GRM-118` — the Excel says how a case was classified, not what was done or by whom

**Origin:** user request (client, 2026-09-15) · **Lane:** `resolution-reporting` · **Reported:** 2026-09-15
**Design:** [`DESIGN-resolution-reporting.md`](DESIGN-resolution-reporting.md) §1, §3.4, §6

## Kind

**`feature`** — question 1: [`09`](../../ticketing_system/09_reports_and_report_builder.md) §4 has no
*Resolved by* field.

## Profile

| ✓ | Question | Fires |
|---|---|---|
| ✔ | Changes user-visible behaviour | `G-PRODUCT` · `G-SPEC` · `G-VERIFY` |
| ✗ | A UI surface changes shape | — a column in existing tables and exports; the report screen's column picker lists it automatically |
| ✗ | Schema changes | — |
| ✔ | PII · auth · SEAH · complainant channel · new egress | `G-SENSITIVE` — SEAH rows in a forwarded file |
| ✔ | API or event shape changes | `G-CONTRACT` — report row shape gains a key |
| ✔ | Deployed | `G-RELEASE` |
| ■ | always | `G-TEST` |

> **profile:** `Backend feature` +CONTRACT **+SENSITIVE** · **gates:** PRODUCT · SENSITIVE · CONTRACT · SPEC · TEST · VERIFY · RELEASE
> **model:** Opus · **size:** S

## Blocked by

- ⏳ **Q-05** — the column key. The item below is written for the recommendation (keep
  `resolution_category`); if the owner chooses the rename, add the read-side alias to all three
  readers named in Q-05 before anything else.
- **`GRM-116`** and **`GRM-117`** merged — this item reads the snapshot labels they write.

## The change

In [`ticketing/services/report_rows.py`](../../../ticketing/services/report_rows.py):

1. `_fetch_auxiliary_maps` reads, from the latest `RESOLVED` payload, `resolution_category_label`
   and `resolution_actor_label` alongside the code it reads today.
2. `build_report_row`:
   - `resolution_category` → the snapshot label, else `resolution_category_label(code)`, else blank
   - `resolution_actor` → the snapshot label; **`Not recorded`** when resolved but the payload has no
     actor; blank when not resolved
3. `FIELD_LABELS`: `resolution_category` → **Resolution action**; `resolution_actor` → **Resolved by**.
4. `resolution_actor` added to `DEFAULT_REPORT_COLUMNS` (right after `resolution_category`),
   hence to `ALL_DATA_EXPORT_COLUMNS`, and to `GROUP_BY_KEYS`. **Not** to `PUBLIC_REPORT_COLUMNS`.
5. `report_summary.py`: the pie's key label becomes *Resolution action*.
6. ⚠ **Saved quarterly templates** keep the columns they were saved with — an existing template does
   not gain *Resolved by* until someone edits it. Say this in `09` §2.5 rather than migrating
   templates behind their owners' backs.

## Files it may touch

- `ticketing/services/report_rows.py` · `ticketing/services/report_summary.py` · `ticketing/services/pivot_table.py`
- `channels/ticketing-ui/components/reports/SummaryTab.tsx` · `app/reports/page.tsx` (labels only, if hard-coded)
- Specs (G-SPEC, same PR): `09` §2.5 · §4 · §12 (pie label)

## Gates — evidence

- **G-SENSITIVE** — DESIGN §6 checks 1, 2, 4:
  - a case resolved with a person's name in the resolution text: **no report column contains it**
  - a reader without SEAH visibility, or with it but without `include_seah`: **no SEAH row**, so no SEAH action or actor
  - `resolution_actor ∉ PUBLIC_REPORT_COLUMNS` — pinned by a test, so adding it later is a visible decision
- **G-TEST** — row values for: resolved with actor; resolved before the lane (`Not recorded`); open
  (blank); an event whose snapshot label differs from the current list label (snapshot wins); pivot
  grouped by `resolution_actor`; the quarterly 4-sheet workbook has both headers.
- **G-VERIFY** — download the overview Excel and the quarterly export from the browser; both columns
  present and filled for a case resolved through `GRM-117`.

## Non-goals

A case summary column (DESIGN §1). The public share. Migrating saved templates.

## Register line

```
| `GRM-118` — the Excel says how a case was classified, not what was done or by whom | feature | Backend feature +CONTRACT +SENSITIVE | `blocked` | S | resolution-reporting | … |
```
