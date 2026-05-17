# GRM canonical location codes (Nepal)

**Status:** Locked for migration (preferred over CBS numeric-only geo codes).  
**Related:** [02_ticketing_domain_and_settings.md](02_ticketing_domain_and_settings.md), [04_ticketing_schema.md](04_ticketing_schema.md), `ticketing.locations`, `ticketing.package_locations`, officer scopes, QR scan flow (`docs/COMMIT_STRATEGY.md`).

---

## 1. Why a custom scheme

The official statistics authority uses **numeric** geographic identifiers. They are correct for census and surveys but are **hard for officers and complainants to read, remember, or cross-check** in the field. This project uses **short, human-readable CAPS mnemonics** as the **canonical `location_code`** (and related hierarchy) in `ticketing.*`, seeds, and routing.

CBS / NSO / HLCIT codes may still be stored as **optional external references** for interoperability (future column or JSON), but **assignment, workflow, UI filters, and QR-linked package locations** align on the codes below.

---

## 2. Province codes

- **Seven provinces:** `P1` … `P7` (always **CAPS**).
- **Alignment:** `P1` = Koshi, … `P7` = Sudurpashchim (same numbering as common **ISO 3166-2:NP** province subdivision `NP-P1` … `NP-P7`, without the `NP-` prefix in our internal key).
- Use these as the **province level** in the location tree and in composed codes where needed.

---

## 3. District codes (within a province)

- For each **district** under a province, derive a mnemonic from the **district name** (use one agreed romanization for Nepali → Latin, e.g. the English / official short name used in admin lists).
- **Default:** first **three** letters of that name, **CAPS** (e.g. Morang → `MOR`, Jhapa → `JHA`).
- **Collision** (two districts in the **same** province share the same first three letters): use **four** letters for both colliding names (or for the second only — document the generator rule once; prefer **consistent length** for the pair to avoid ambiguity).
- **Further collision:** rare; resolve with a numeric suffix (e.g. `MOR`, `MO2`) so seeding never blocks.

Districts are **unique within a province** for this rule; the full canonical key for a district row should be **unambiguous in the tree** (see §4).

---

## 4. Canonical form in the database

- **`location_code`** (PK / FK across ticketing) is the **canonical** identifier after migration.
- Recommended pattern for **machine keys** (example — adjust to match your exact hierarchy levels):

  | Level        | Example pattern   | Notes                                      |
  | ------------ | ----------------- | ------------------------------------------ |
  | Province     | `P1` … `P7`       | Top of tree for Nepal                      |
  | District     | `P1_MOR`, `P1_JHA`| `Province` + `_` + district mnemonic (CAPS)|
  | Municipality | `P1_MOR_<MUN>`    | Extend with a short muni mnemonic or code  |

Exact composition for municipalities and wards can follow the same **CAPS + underscore** convention; define a one-time **import/seed generator** so no hand-assigned drift.

- **`parent_location_code`** must use the **same** scheme so `includes_children` and assignment logic stay correct.
- **Legacy codes** (e.g. old `NP_P1`, `NP_D006` from prior imports): remove or keep only in a **`legacy_code` / `external_ref`** field during migration; **do not** mix legacy and new codes on live `location_code` rows.

---

## 5. Seeds and officer scopes

- Update **`ticketing/seed/*.py`** (e.g. `kl_road_standard.py`, `mock_tickets.py`) so every `location_code`, `LOC_*` constant, workflow assignment, and **`officer_scopes`** row references **only** canonical codes.
- Re-run location import / migration so **`ticketing.locations`** matches the same table.

---

## 6. QR codes and chatbot intake

- QR stickers encode an **opaque token**; the **scan API** returns `package_id`, `project_code`, `location_code`, etc. After migration, **`location_code`** (and any label derived from `ticketing.locations`) must follow this document.
- **Operational checklist when codes go live:**
  1. Migrate `ticketing.locations` and `ticketing.package_locations` to canonical codes.
  2. Update seeds and environments.
  3. **Regenerate** printable QR assets from Settings if **URLs, labels, or printed text** embed human-readable place strings that must match the new scheme (token strings may be unchanged, but field teams often re-print for clarity).
  4. Smoke-test: `GET /api/v1/scan/{token}` returns expected `location_code`; chatbot submit → `POST /api/v1/tickets` → auto-assign sees matching `officer_scopes`.

See **QR Token Scan Flow** in `docs/COMMIT_STRATEGY.md`.

---

## 7. Generator discipline

- Implement a **small script** (recommended) that: loads the district list per province, applies §2–§3 rules, outputs the full code table, and fails on unresolved collisions.
- **Stability:** treat `location_code` as a stable ID; renames of display names in the UI should not churn codes. If government structure changes (split/merge), use an explicit migration with a mapping table.

---

## 8. Sign-off

| Role        | Notes |
| ----------- | ----- |
| Product     | Readability (CAPS mnemonics) over CBS numerics for operational use |
| Engineering | Canonical `location_code`; seeds + `package_locations` + scopes + QR scan contract |
