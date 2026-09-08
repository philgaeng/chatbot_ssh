# Settings findability — questions

**Audience:** internal — excluded from the public repository (lifecycle §10.4).

> **How to use this file.** Every question is one that could not be settled from the code alone. Each
> carries a **recommendation**, and several carry a fact verified first so the answer is not blind
> ([07](../../engineering/07_work_items.md) §3, `G-PRODUCT`: *"a questions register where each
> question carries a recommendation"*).
>
> ✅ **Q-01 … Q-05 were answered by the owner on 2026-09-07.** Every answer is folded into the item
> that needs it, so an agent works from its spec alone ([07](../../engineering/07_work_items.md) §6.2).
> **Q-06 is open and blocks nothing** — it is a sequencing preference.

---

## Q-01 · Officers: structured filters, or just a wider search?

**Verified:** the directory's search matches three fields — `display_name`, `email`, `positions`
([`OfficersDirectory.tsx:156`](../../../channels/ticketing-ui/components/settings/officers-v2/OfficersDirectory.tsx#L156)).
But the same component **already computes** organization name, project codes and location scopes
client-side to render the "Project / area" column (`projectAreaCell`). So widening the search to the
columns an admin actually scans by is a few lines over data already in hand.

**Recommendation:** both, in that order and as two items — ship the widened search now (`GRM-087`,
XS), then build structured filters (`GRM-088`, M) reusing whatever `GRM-086` establishes for
organizations. At 57 officers search alone is enough; filters earn their place at 500.

> **Answer (2026-09-07):** follow reco.

## Q-02 · Organizations: filters *and* search, or search only? And which filters?

**Verified:** the org tab has **no** search and **no** filters today — the control does not exist in
[`OrgTree.tsx`](../../../channels/ticketing-ui/components/settings/org/OrgTree.tsx). The data for
every filter the client asked for is present on each node: `org_category` / `unit_type` (type),
`parent_organization_id` (parent), `territory_location_code` (area).

**Recommendation:** search that filters **in place, keeping ancestors visible**, plus **two** filters
— Type and Area. **Drop the parent-organization filter**: the tree *is* the parent relationship, so
the filter duplicates clicking a parent node while training the admin not to read the structure.

> **Answer (2026-09-07):** follow reco.

## Q-03 · Is the audience for these screens the rural complainant?

**Verified:** no — and the specs are explicit in both directions.
[`ui/05`](../../ticketing_system/ui/05_ui_copy_style.md) governs this surface: *"a career civil
servant in a Nepal district or ministry office, capable and experienced, but reading English as a
second language and not technical."*
[`ui/04 §2`](../../ticketing_system/ui/04_projects_packages_ux_review.md) goes further — the admin
editor is judged as capable-but-non-technical, *"not low-literacy, not a SaaS power-user"* — and
places the low-IT-literacy premise on the **complainant / chatbot** surface instead.

**Recommendation:** design to `ui/05`. Keep the two rules that carry over regardless of literacy —
severity in words rather than colour alone, and the simpler of two words — and do not import
low-literacy patterns this audience does not need.

> **Answer (2026-09-07):** `ui/05` is right.

## Q-04 · The mockup that binds this screen is stale. Refresh it, or bind to the shipped screen?

**Verified:** `GRM-064` records
[`ui/04_projects_packages_redesign.html`](../../ticketing_system/ui/04_projects_packages_redesign.html)
as stale — it still shows Locations and Packages as separate sections and organizations inside the
package card, none of which is what ships. `GRM-089` and `GRM-090` land on exactly that screen, so
`G-DESIGN` currently has nothing trustworthy to cite.

**Recommendation:** *(none offered — this was the owner's call to make.)*

> **Answer (2026-09-07):** the screenshots are live and should replace the mockup.

**Folded in:** the mockup is **marked superseded where it is cited** — a banner in the file itself and
a changed row in [`05_frontend`](../../engineering/05_frontend.md) §9a — rather than deleted or
hand-refreshed, per rule 9a.3. The shipped route becomes the wireframe baseline and each item states
its delta (DESIGN §3). ⚠ **One carve-out:** `GRM-086` adds a control surface that exists on no shipped
screen, so it still produces a committed `.html` wireframe before build. This closes `GRM-064`.

## Q-05 · "Workshop" in the tab order — a rename, or a typo?

**Verified:** no tab named Workshop exists; `MAIN_TABS` carries **Workflows**
([`page.tsx:52`](../../../channels/ticketing-ui/app/settings/page.tsx#L52)). A rename would be a
separate item — it touches the glossary, which lists "workflow" as the required on-screen word for
several internal terms.

> **Answer (2026-09-07):** typo — it is Workflows.

---

## Q-06 · Open — does `GRM-088` wait for `GRM-086` to ship, or only for its design?

**Blocks nothing.** Q-01 settled that officer filters reuse whatever organizations establish. What is
unsettled is whether that means the *shipped component* or the *frozen contract*. Waiting for the
component gives one implementation and no duplication; waiting only for the contract lets the two run
in parallel at the cost of a merge.

**Recommendation:** wait for the shipped component. `GRM-088` is the least urgent item in the lane
(Q-01: filters earn their place at 500 officers, and there are 57), so buying parallelism here spends
a merge conflict on the item that least needs to arrive early. `GRM-088` is `blocked` on `GRM-086` in
the register on that basis — reversible the moment this is answered otherwise.

> **Answer:**
