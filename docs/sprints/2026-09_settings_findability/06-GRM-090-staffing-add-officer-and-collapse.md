# `GRM-090` — staffing shows every level expanded, so the two blockers are below the fold

**Origin:** user request (client, 2026-09-07) · **Lane:** `settings-ui` · **Reported:** 2026-09-07
**Design:** [`DESIGN-settings-findability.md`](DESIGN-settings-findability.md) §2.3, §5, §6

## Kind

**`feature`** — question 1: no live spec claims either behaviour.

## Profile

| ✓ | Question | Fires |
|---|---|---|
| ✔ | Changes user-visible behaviour | `G-PRODUCT` · `G-SPEC` · `G-VERIFY` |
| ✔ | A UI surface changes shape | `G-DESIGN` — **progressive disclosure changes the pane's IA** |
| ✗ | Schema changes | — |
| ✗ | PII · auth · SEAH · complainant channel · new egress | ⚠ **see the check below before agreeing** |
| ✗ | API or event shape changes | — |
| ✔ | Deployed | `G-RELEASE` |
| ■ | always | `G-TEST` |

> **profile:** `UI feature` · **gates:** PRODUCT · DESIGN · SPEC · TEST · VERIFY · RELEASE
> **model:** Opus · **size:** S

⚠ **The `G-SENSITIVE` row was checked, not skipped** (rule 4.2 — never waived by kind or by size).
The Staffing pane has a **SEAH tab**, and SEAH staffing is cast-only and admin-configurable but never
admin-readable. **The answer is no** because this item changes disclosure and adds a modal that
already exists, and touches no visibility rule. ⭐ **It becomes yes the moment the collapsed header's
summary text is derived from anything inside a sensitive workflow's cast** — the collapsed summary
must count slots, never name officers, on the SEAH tab.

## The change

1. **Add an officer inline.** The staffing pane opens the existing
   [`ProjectOfficerModal`](../../../channels/ticketing-ui/components/settings/ProjectOfficerModal.tsx),
   and on save the new officer is **assigned to the slot that opened it**, not merely created.
2. **Levels collapse**, using the disclosure pattern packages already use
   ([`PackageRow.tsx`](../../../channels/ticketing-ui/components/settings/projects/PackageRow.tsx)) —
   the client asked for this by name.

⭐ **Default state is the design decision** (DESIGN §2.3): **collapsed, except a level with an unmet
required slot.** The collapsed header carries the count **in words** — *"Needs an officer"* — never a
bare red dot ([`ui/05`](../../ticketing_system/ui/05_ui_copy_style.md) rule 6). Collapse-everything
hides the exact thing the pane exists to surface; the live KL Road project has two such blockers.

The existing **last-level-first** order (L4 → L1) is unchanged, and its documented reason — *"the
upper ladder is the stable part you settle once"* — is the same reason those levels collapse well.

## Files it may touch

- [`components/settings/projects/CastStaffing.tsx`](../../../channels/ticketing-ui/components/settings/projects/CastStaffing.tsx) — the level cards, the disclosure state, the unmet-required computation
- [`components/settings/projects/ProjectCastSection.tsx`](../../../channels/ticketing-ui/components/settings/projects/ProjectCastSection.tsx) — per-workflow tabs, if disclosure state is held there
- [`components/settings/ProjectOfficerModal.tsx`](../../../channels/ticketing-ui/components/settings/ProjectOfficerModal.tsx) — assign-on-create callback
- [`12_workflows_configuration.md`](../../ticketing_system/12_workflows_configuration.md) · [`13_projects_and_packages.md`](../../ticketing_system/13_projects_and_packages.md) — G-SPEC

## Gates — evidence

- **G-DESIGN** — no wireframe (DESIGN §3). Owes the **frozen contract**: disclosure state shape, the
  unmet-required predicate, and the exact collapsed-header strings from `ui/05`.
- **G-TEST** — the default-state predicate is the thing worth a unit test: a level with an unmet
  **required** slot opens; a level whose only empty slots are optional stays closed.
- **G-VERIFY** — e2e through the project console's Staffing pane, both a blocked and a fully staffed
  project. ⚠ **Do not drive officer *provisioning*** — `GRM-075` records why the suite stops short
  (a real Keycloak account and a real set-password email per run), and `GRM-074` means the invite
  path dead-ends on a fresh database anyway.

## Non-goals

No change to the last-level-first order, to `staff_per_package`, to the cast model, or to SEAH
visibility. No change to what the go-live panel counts.

## Register line

```
| `GRM-090` — staffing shows every level expanded, so the two blockers are below the fold | feature | UI feature | `ready` | S | settings-ui | … |
```

## Notes

⚠ **Interaction with the go-live panel.** *"2 blockers before go-live"* and the rail's `FIX 2` are the
other renderings of the same fact this item is about to collapse. If a level is closed **and** the
blocker text is inside it, the count in the rail becomes the only surviving signal — which is why the
count moves onto the collapsed header rather than being hidden with the rest.
