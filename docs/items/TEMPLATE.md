# Item — `GRM-###` <title>

**Audience:** internal — the intake form for the register (lifecycle §10.4).

> **Copy this file, fill it top to bottom, then paste the *Register line* into
> [`docs/SPINE.md`](../SPINE.md).** The questions are in this order for a reason: each one's answer
> feeds the next, and the last one is the register row. Governed by
> [`engineering/07_work_items.md`](../engineering/07_work_items.md).
>
> ⚠ **The whole point of this file is that it is filled at INTAKE.** At PR time every answer below is
> already fixed — the design is written, the model was chosen, the tests exist or do not (07 §4.3).
> The PR template *confirms* what is decided here; it is no longer the first time anyone asks.

**Where it lives.** GitHub Issues is decided but **not wired** (07 §11 row 8 · OM-07), so an item
lives here — `docs/items/GRM-###-<slug>.md` — or in its sprint folder when it belongs to one. Small
items need no file at all: the register row *is* the item. **Write a file when a gate below demands
an artifact** (a design note, a questions register, a boundary-test list).

---

## 1. Identity

| Field | Value |
|---|---|
| **Id** | `GRM-###` — take the next free id from [`SPINE.md`](../SPINE.md); the file is the allocator (Q-07) |
| **Title** | Say what is wrong or missing, not what to build. A title that names the fix hides the problem |
| **Origin** (07 §2.5) | user request · review finding · incident · agent discovery · external requirement (ADB / DPG / DOR) |
| **Lane** | which stream owns it — `operating-model`, `qa`, `hardening`, `dpg`, `standing` |
| **Reported** | YYYY-MM-DD |

## 2. Kind — four questions, in order (07 §2.2)

Answer in order and **stop at the first one that resolves.** Classification is cheap and revisable
(§2.4) — a wrong label costs a re-label, never a re-plan.

| # | Question | If yes |
|---|---|---|
| 1 | Does a live spec already claim this behaviour? | **No → `feature`.** Yes → continue |
| 2 | Does the code disagree with that spec? | Spec is right → **`bug`**. Spec is wrong → **`deviation`** |
| 3 | Is anything a user could observe changing? | No → **`chore`** |
| 4 | Are we choosing not to fix it now? | Yes → **`debt`** — and the deferral rule applies: `followups/<slug>.md` **and** a register row, same commit |

> **kind:** `<one of feature / bug / deviation / debt / chore>`
> **why this kind:** <one line — which question resolved it>

⚠ **§2.3:** if you are fixing a `bug` and find yourself editing a spec, it was never a bug — it is a
`deviation`. Reclassify it. That edit is the moment the fork appears.

## 3. Profile — six questions, computed not chosen (07 §4.1)

**Tick every one that is true.** The gates are the sum; the profile is the preset that matches.

| ✓ | Question | Fires |
|---|---|---|
| ☐ | Does it change user-visible behaviour? | `G-PRODUCT` · `G-SPEC` · `G-VERIFY` |
| ☐ | Does a UI surface change shape? | `G-DESIGN` |
| ☐ | Does the schema change? | `G-DATA` |
| ☐ | **Does it touch PII · auth · SEAH · a live complainant channel · a new external egress?** | **`G-SENSITIVE`** |
| ☐ | Does an API or event shape change? | `G-CONTRACT` |
| ☐ | Is it deployed? | `G-RELEASE` |
| ■ | *(always)* | `G-TEST` |

⭐ **`G-SENSITIVE` is never waived by kind or by size (§4.2).** A one-line change to the SEAH intake
is not a chore. Every exception ever granted here was granted on diff size, which does not correlate
with risk. **If you hesitated on that row, the answer is yes.**

> **profile:** `<UI feature / backend-feature / schema-migration / bug / deviation / chore>`
> `<+SENSITIVE / +INCIDENT>` `<−GATE for any the preset includes and this item does not need>`
> **gates:** `<the list above>`

## 4. Model — decided by the profile, not by judgment

| Profile carries | Model |
|---|---|
| **`+SENSITIVE`** | **Opus, high reasoning effort — mechanically, no separate call** |
| UI feature · backend-feature · schema-migration | Opus |
| bug · deviation | Opus unless the fix is provably local |
| chore (no modifier) | Sonnet |

> **model:** `<Opus / Sonnet>` — *if `+SENSITIVE` is ticked above, this cell reads Opus. There is no
> judgment step; that is the point of deriving it.*

## 5. Ready? (07 §6)

An item enters the register **only when it is ready** — a register whose every row is actionable is
worth reading. Everything before that is an inbox entry.

- [ ] **Kind assigned** (§2)
- [ ] **Profile derived** (§3) — ⚠ *enforced: `tests/repo/test_spine.py` fails a `ready` or `current` register row with an empty profile*
- [ ] **Model follows from the profile** (§4)
- [ ] Every gate the profile fires has a named artifact, or a stated reason it does not apply
- [ ] Size is `XS / S / M / L` — **`XL` is not a size, it means "split this"** (§7.5)
- [ ] If `blocked`: the blocker **and** the unblock condition are named (§7.1)

## 6. The register line — paste this into `SPINE.md`

```
| `GRM-###` — <title> | <kind> | <profile> | `ready` | <size> | <lane> | <one line: why now, and the first action> |
```

**Two state fields, never one (§7.1).** `state` is where it sits in the queue
(`proposed → ready → current → merged → done`, plus `blocked` / `dropped`). `verification` is how
true it is (`planned → implemented → tested → applied locally → deployed → verified in production`).
An item is `done` only when its verification meets what its profile requires (§7.2) — **a chore is
done at `tested`; a UI feature is not done at `deployed`.**

---

## 7. Notes — the reasoning, not the plan

<!--
  What is actually wrong, what you measured, and what you decided NOT to do.
  Move a rule's reason with the rule: a rule without its reason decays into cargo cult.
-->
