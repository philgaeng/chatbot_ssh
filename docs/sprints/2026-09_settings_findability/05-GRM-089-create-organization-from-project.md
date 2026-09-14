# `GRM-089` — the project's Organizations pane can only pick an organization that already exists

**Origin:** user request (client, 2026-09-07) · **Lane:** `settings-ui` · **Reported:** 2026-09-07
**Design:** [`DESIGN-settings-findability.md`](DESIGN-settings-findability.md) §1, §3, §6

## Kind

**`feature`** — question 1: no live spec claims inline creation here.

## Profile

| ✓ | Question | Fires |
|---|---|---|
| ✔ | Changes user-visible behaviour | `G-PRODUCT` · `G-SPEC` · `G-VERIFY` |
| ✔ | A UI surface changes shape | `G-DESIGN` — **steps 5 and 6 only**: existing modal, existing pane |
| ✗ | Schema changes | — an org is created through the existing endpoint |
| ✗ | PII · auth · SEAH · complainant channel · new egress | — organizations are institutional records |
| ✗ | API or event shape changes | — |
| ✔ | Deployed | `G-RELEASE` |
| ■ | always | `G-TEST` |

> **profile:** `UI feature` · **gates:** PRODUCT · DESIGN · SPEC · TEST · VERIFY · RELEASE
> **model:** Opus · **size:** S

## The change

The "— choose an organization —" picker gains a **"Create a new organization"** affordance that opens
the existing [`OrgCreateModal`](../../../channels/ticketing-ui/components/settings/OrgCreateModal.tsx).

⭐ **On save the new organization is selected and linked, not merely created.** A modal that creates a
record and returns you to an empty picker has moved the work, not removed it — and the picker is a
long unsearchable `<select>` (20+ entries, several of them full joint-venture legal names running past
the dropdown's width), so "now find the one you just made" is the expensive half.

## Files it may touch

- [`components/settings/projects/ProjectPartnersSection.tsx`](../../../channels/ticketing-ui/components/settings/projects/ProjectPartnersSection.tsx) — the `adding` / `addingPkg` pickers (both project-wide and by-package)
- [`components/settings/OrgCreateModal.tsx`](../../../channels/ticketing-ui/components/settings/OrgCreateModal.tsx) — an `onCreated` callback if it does not already return the new record
- [`13_projects_and_packages.md`](../../ticketing_system/13_projects_and_packages.md) — G-SPEC

## Gates — evidence

- **G-DESIGN** — no wireframe (DESIGN §3: the shipped screen is the baseline; `GRM-064` is closed by
  marking the stale mockup superseded, not by redrawing it). What this owes is the **state contract**:
  what the pane shows while the modal is open, what happens on cancel, and what happens when creation
  succeeds but linking fails — three states, not two.
- **G-TEST** — the create-then-linked path, and the cancel path leaving the picker untouched.
- **G-VERIFY** — an e2e spec through the project console's Organizations pane.

## Non-goals

No change to what an organization is, to the org role catalog, or to the by-package linking model.
The parent picker inside the modal is unchanged.

## Register line

```
| `GRM-089` — the project's Organizations pane can only pick an organization that already exists | feature | UI feature | `ready` | S | settings-ui | … |
```

## Notes

The same dead-end exists in the opposite direction and is **already documented on screen**:
*"Link organizations to this project first (Projects & packages → Partner organizations), then invite
officers"* ([`OfficerJurisdictionForm.tsx:573`](../../../channels/ticketing-ui/components/settings/OfficerJurisdictionForm.tsx#L573)).
That copy becomes stale once this item and `GRM-090` land — **check it in the same pass.**
