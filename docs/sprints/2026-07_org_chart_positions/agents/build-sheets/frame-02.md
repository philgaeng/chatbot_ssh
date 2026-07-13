# Build sheet — Frame 02 · Organisation — org tree

> RB-0 build sheet. Grounds wireframe Frame 02 in the NOW-REAL org API. Input to RB-2/3/4.
> **Data owner:** OC-01 (org tree + CSV + descendant CTE) · dedup soft-flag SH-4.
> **Real router:** `ticketing/api/routers/locations.py` (org CRUD lives here, **not** in a `organizations.py`), mounted at prefix `/api/v1` (`ticketing/api/main.py:117`).

---

## 1. Visual ref

- **Wireframe:** `settings-wireframes.html` Frame 02 (line 603, `#f2`).
- **Atlas:** `settings-state-atlas.html` Surface 02 (line 352) — Loading / Empty / Error(CSV) / Bilingual. Atlas 00 (state vocabulary) applies.
- **Layout (3–5 lines):** One `Organisation` tab with a three-item sub-nav (`Org tree` · `Position types` · `Officers`). The tree **replaces** the flat org list. It renders **two groups**: "Government reporting line" (a rooted subtree Ministry → Department → Division Office, each indented by depth with a unit-type chip and a territory chip) and "Independent organisations — own roots, own subtrees" (ADB donor root, contractor JV with its own sub-contractor child). Each row exposes `+ child`, `edit`, `⋯` on hover/focus. Node labels render bilingually (`EN / देवनागरी`); absent Nepali shows a "Nepali name needed" chip. Header actions: `Import CSV` + `+ Add unit`. Empty state gives real CTAs (`Add organisation` / `Import from CSV`), never migration copy.

---

## 2. Component subtree (DESIGN §3, `components/settings/org/`)

```
OrganisationTab.tsx            [extract]  sub-nav shell: Org tree · Position types · Officers
  └ OrgTree.tsx                [fold+new] REPLACES OrganizationsTab flat list; renders TWO groups —
                                          reporting-line subtree(s) + independent roots (§2.4). ex-OC-05 OrgTreeTab
      ├ OrgTreeNode.tsx        [new]      row: <Bilingual> label, unit_type chip, territory chip,
      │                                   inline [+ child] [edit] [⋯]; indented by depth
      ├ OrgEditor.tsx          [refactor] create/edit unit: name(EN)+display_name_ne, parent, unit_type,
      │                                   territory; hosts dedup soft-flag (§2.4); fixes F1/F18/F19
      └ OrgCsvImport.tsx       [new]      whole-file validate → preview → single-txn import (OC-01)
lib/orgTree.ts                 [new]      client tree build / flatten / descendant helpers (forest-aware)
lib/orgDedup.ts                [new]      (calls the server finder; client formats the soft-flag row)
shared/Bilingual.tsx           [new]      "EN / देवनागरी", EN fallback, never fabricates (D4)
shared/ErrorNotice.tsx         [new]      wraps lib/user-messages.ts formatUserFacingError
```

**Demolition source in the god-file** (`app/settings/page.tsx`): `OrgsSection` (line 2159 — holds `countries`, `editing`), `OrgEditor` (line 2190 — flat name/country/active fields + the **read-only S2 project-link panel** at ~2211–2246 that the redesign kills), and `OrganizationsTab` (`components/settings/OrganizationsTab.tsx:35`, the flat list). All three collapse into `OrgTree`/`OrgTreeNode`/`OrgEditor`.

---

## 3. Governing interaction rules (DESIGN §4.2, §2.4)

- **Reparent cycle-guard.** Move/`⋯` reparent calls `PATCH /organizations/{id}` with `parent_organization_id`. Server rejects a cycle (422 "Reparenting would create a cycle …", `locations.py:648-652`). UI surfaces via `ErrorNotice`; keep the picker open. (Full move UI is Frame 12; Frame 02 owns `+ child` create + edit.)
- **Subtree category cascade.** `org_category` is set at the **root** and **inherited**; a child cannot set its own (422, `locations.py:671-677`). On create-with-parent, do **not** send `org_category` (inherited); on a root, send it. Reparenting cascades the new root's category to the whole subtree server-side (`locations.py:685-693`) — the UI must re-fetch the subtree after a move.
- **CSV import (parent-by-key, unit_type, org_category, territory, `_ne`).** `OrgCsvImport` posts the whole file to `POST /organizations/import`. Columns (from `download_org_csv_template`, `locations.py:822-824`): `organization_id, name, parent_organization_id, org_category, unit_type, country_code, territory_location_code, territory_includes_children, display_name_ne`. Server **validates the whole file first** (required fields, domains, parent resolution, cycles, category inheritance), then upserts **parents-first in one transaction** (idempotent by `organization_id`). On any error: **nothing is written**, 422 `{message, errors[]}` — render each row error via `ErrorNotice` (atlas: "Row 4 — office type 'district' isn't one we use", "Row 7 — parent 'DoR2' doesn't exist yet"), never a raw dump. Offer a `dry_run=true` preview first.
- **Dedup soft-flag (SH-4).** On create in `OrgEditor`, before/at save call `POST /organizations/duplicate-candidates`; if candidates return, show "Possible duplicate: {name} · Use existing / Create anyway" — **never a hard block** (creation stays on `POST /organizations`, unaffected). Match reasons come back in `reasons[]` (distinctive name tokens w/ stoplist, corporate email domain, fuzzy address).
- **Root-creation gating (§2.5, defense-in-depth).** Creating an **institutional** root (`government`/`local_government`/`donor`) is super_admin only (server 403, `locations.py:414-423`); a `third_party` root (contractor) is delegable. UI should gate the "+ Add organisation / new root" affordance by tier (reads admin-context), but the server is the source of truth.
- **Devanagari names creatable (F1/F19).** The client must **not** lock Create on Devanagari input. `organization_id` is derived server-side (ASCII, SH-6) when omitted; the Nepali name lives in `display_name_ne`. The id shown must be the id sent.

---

## 4. Concrete endpoints (all `/api/v1`, real)

| Method + path | Payload | Response / notes |
|---|---|---|
| `GET /organizations` | query: `country?`, `active_only=true`, `root_id?` (subtree via descendant CTE), `tree?` (depth-first order) | `OrganizationResponse[]`. Auth required. `locations.py:335`. **`tree=true` + `root_id` power lazy-load** (Frame 12). |
| `POST /organizations` | `OrganizationCreate` (see below) | 201 `OrganizationResponse`. Gated `MANAGE_ORG_STRUCTURE`. Validations 422/403/409 per §3. `locations.py:366`. |
| `POST /organizations/duplicate-candidates` | `{name, email?, address?, country_code?, exclude_organization_id?, limit=8}` | `DuplicateCandidateItem[]` `{organization_id, name, score, reasons[], name_score, email_domain_match, address_score, country_code, org_category, unit_type}`. Auth only (no write gate). `locations.py:501`. |
| `PATCH /organizations/{id}` | `OrganizationUpdate` (field-presence semantics; explicit null detaches to root) | `OrganizationResponse`. Gated + scope. Cycle guard 422, category cascade. `locations.py:582`. |
| `DELETE /organizations/{id}` | — | 204, or 409 guards (§ Frame 12). `locations.py:701`. |
| `GET /organizations/import/template.csv` | — | CSV (`PlainTextResponse`). Gated. `locations.py:814`. |
| `POST /organizations/import` | multipart: `file` (UploadFile), `dry_run` (Form bool) | `OrgImportResult {organizations_upserted, dry_run, errors[]}`; 422 `{message, errors[]}` on reject. `locations.py:834`. |
| `GET /roles?kind=&workflow_track=` | — | `GrmRole[]` — for label resolution only. `users.py:142`. |
| `GET /countries` | — | `CountryResponse[]` — for the country picker. `locations.py:906`. |

**`OrganizationResponse` / `OrganizationCreate` fields** (`locations.py:243-304`): `organization_id, name, country_code, is_active, default_language="ne", parent_organization_id, org_category, unit_type, territory_location_code, territory_includes_children, display_name_ne, email, address, created_at, updated_at`.

**Valid enums (real):** `UNIT_TYPES` (`ticketing/models/organization.py:18`): ministry, department, directorate, provincial_office, division_office, province_assembly, municipality, development_partner, company (+ any others in that tuple). `ORG_CATEGORIES` (`organization.py:17`): `government, local_government, donor, third_party`. `INSTITUTIONAL_CATEGORIES` (`org_tree.py:34`) = government/local_government/donor (super-only roots); `DELEGABLE = third_party`.

### `[GAP]` — endpoints this frame needs that do NOT exist
- **`[GAP]` client wrappers in `lib/api.ts`.** The endpoints exist server-side but `lib/api.ts` (api.ts:1722-1757) is stale: `OrganizationItem`/`OrganizationCreate`/`OrganizationUpdate` interfaces are **missing every tree field** (parent/org_category/unit_type/territory*/display_name_ne/email/address); `listOrganizations(country?)` (api.ts:1736) **does not pass `root_id`/`tree`/`active_only`**; and there is **no wrapper** for `duplicate-candidates`, `organizations/import`, or `import/template.csv`. RB-4 must add these (api.ts is `[refactor]` in §3). Endpoints themselves: **present, not a server gap.**
- **`[GAP]` server-side tree search / `q` param on `GET /organizations`.** Frame 02 is the 4-node happy path so it's fine, but the "Find an office by name" search Frame 12 relies on has **no `q` filter** on `GET /organizations` (the *locations* GET has one; orgs does not). Flag for Frame 12.

---

## 5. Tokens / labels contract (DESIGN §7.C, §7.E)

- **Labels, never slugs.** `unit_type` → "Division Office", `org_category` → "Government" / "Development partner" / "Company", `visibility_mode` → plain — via a single `lib/labels.ts` display map, each with `_ne`. **No code identifier or math symbol ever renders** (no `descendant_org_ids`, no `∪`; "attenuated" is a spec word). The authz note renders as prose ("Only an Organisation admin can change the reporting line; project owners add their own contractors").
- **`<Bilingual>`** on every node label / name field where `display_name_ne` is present; EN fallback otherwise; absent `_ne` → **"Nepali name needed"** chip (not "mark for translator"). Never fabricate.
- **Colors via `lib/design-tokens.ts`** only (unit-type chips = blue family; territory chip its own token). No banned hues (orange/yellow/indigo/purple/teal/sky — `design-tokens.ts:28-33`), `text-gray-600` floor, **no emoji**. Lucide icons via `@/lib/icons`.
- **Friendly errors** through `formatUserFacingError` (`lib/user-messages.ts:145`) wrapped in one `ErrorNotice` — for CSV row errors, create 409/422, cycle 422. No raw `API 409 {…}`.

---

## 6. Data owner

| Path | Ticket |
|---|---|
| Org tree read/CRUD, `root_id`/`tree`, CSV import, descendant CTE | **OC-01** |
| Dedup soft-flag (`duplicate-candidates`), delete guards, country validation | **SH-4** |
| Root-creation gating + subtree admin scope (403s) | **SH-7** |
| ASCII id derivation / Devanagari names | **SH-6** |

---

## 7. Open gaps / risks for RB-2/3/4

1. **`lib/api.ts` is the real work item** — endpoints exist; the typed wrappers + interfaces are stale and must be rebuilt to carry the tree fields and the new params. This is the single biggest client task for the frame.
2. **Forest grouping is a client concern.** The API returns one flat/`tree`-ordered list; the split into "Government reporting line" vs "Independent roots" is done client-side by `org_category ∈ INSTITUTIONAL vs third_party/donor` and `parent = null`. `lib/orgTree.ts` owns this. Confirm the exact grouping rule (donor is institutional for root-gating but shown under "Independent organisations" in the wireframe — group by "is it under a government root?" not by category alone).
3. **Category cascade re-fetch.** After a reparent, the server silently rewrites `org_category` on the whole subtree; the client must refetch the affected subtree or it will show stale categories.
4. **CSV `territory_includes_children` type.** Column is a boolean-ish string in CSV; confirm the parser's truthy set (`org_import_core.parse_org_csv`) so the template/help text matches.
5. **Next.js 16 caveat** (`channels/ticketing-ui/AGENTS.md`): "This is NOT the Next.js you know" — read `node_modules/next/dist/docs/` before writing components; do not assume training-data conventions.
</content>
