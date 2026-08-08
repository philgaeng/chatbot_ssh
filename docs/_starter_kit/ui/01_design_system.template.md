# ‹Product› — Design System

**Status:** ‹authoritative | draft› (‹YYYY-MM-DD›). The **single source for the visual system**: colour, type, space, icons, tokens, component inventory.
**Companion:** `‹docs/…/02_copy_and_tone.md›` owns **words**. This doc owns **pixels**. Neither overrides the other; a screen must satisfy both.
**Applies to:** all components in `‹path/to/frontend›`.

> **How to use this template.** `‹…›` = substitute a value. **FILL:** = make a decision and write down the reason. Fill sections 1–4 before the first screen ships; 5–9 can follow the first week of real UI.

---

## 0. Who uses this interface

**FILL:** Describe the actual user in three or four sentences — role, expertise, language, and the physical conditions they work in (device, screen quality, lighting, connection). Be concrete; a persona is useless, an observation is not.

> *Example from a real project:* "A career civil servant in a district office. Capable and experienced, but reading English as a second language and not technical. Works on a budget monitor in glare, or a low-end Android, sometimes on an intermittent connection."

This paragraph is the tie-breaker for every judgment call below. When two options both look fine, the one that serves this reader wins. Write it first; everything else is downstream.

---

## 1. Constraints (the short version)

The purpose of a design system is to **remove choices**, not to offer them. Each rule below narrows the space so that two people — or two agents — building two screens a month apart produce the same thing.

| Constraint | This project |
|---|---|
| Colour families | ‹N› + neutrals — see §2 |
| Icon library | ‹one library› — see §5 |
| Type scale steps | ‹N› — see §3 |
| Spacing scale | ‹e.g. 4px base› — see §4 |
| Component library | ‹name, or "none — own primitives"› |
| Styling approach | ‹e.g. utility CSS / CSS modules / CSS-in-JS› |

**FILL:** Adding a colour family, icon library, or component library later is an **architecture decision**, not a convenience. Say so here, so an agent knows it must ask.

---

## 2. Colour

### 2.1 The palette

**FILL:** Choose **four to six** semantic families plus neutrals. More than six and nothing means anything; fewer than four and you cannot distinguish danger from warning.

| Family | Meaning — *the semantic, not the hue* | Tokens |
|---|---|---|
| **‹Primary›** | Primary actions, links, active state, information | ‹scale, e.g. `blue-50…800`› |
| **‹Danger›** | Destructive, error, overdue, ‹domain-critical state› | ‹scale› |
| **‹Warning›** | Needs attention, approaching a limit | ‹scale› |
| **‹Success›** | Completed, healthy, resolved | ‹scale› |
| **‹Accent›** | ‹one narrowly-scoped meaning — name it› | ‹scale› |
| **Neutral** | Text, borders, surfaces, disabled | ‹scale› |

**Rule 2.1 — Colour carries meaning, and each family has exactly one.** If you cannot name the meaning in three words, you don't need the family.

**Rule 2.2 — Eliminated hues.** List every hue that must *not* appear, with its replacement. Without this table, a near-duplicate creeps in every sprint.

| Don't use | Use instead |
|---|---|
| ‹hue› | ‹family› |

**Rule 2.3 — Colour is never the only signal.** Pair it with a word, an icon, or a shape. Colour-blind users, low-literacy users, cheap monitors, and greyscale printouts all break colour-only meaning. *(This one rule prevents more real-world failures than the rest of §2 combined.)*

### 2.2 Contrast floors — non-negotiable

**Rule 2.4 — WCAG AA is the floor**, not the aspiration: 4.5:1 for body text, 3:1 for large text and meaningful non-text.

| Token | Contrast on ‹background› | Use for |
|---|---|---|
| ‹text-strong› | ‹ratio› ✅ | Headings, key values |
| ‹text-body› | ‹ratio› ✅ | Body, section content |
| ‹text-secondary› | ‹ratio› ✅ | **Floor for any text that carries information** |
| ‹text-muted› | ‹ratio› ⚠ | Placeholders and disabled fields ONLY |
| ‹text-faint› | ‹ratio› ❌ | Decorative separators and disabled icons ONLY |

Draw the line explicitly — it is the single most-cited rule in review:

```
‹text-secondary›  ←  floor for anything a user needs to read
‹text-muted›      ←  placeholder / disabled only, never metadata
```

---

## 3. Typography

**Rule 3.1 — One family for UI, at most one for code/data.** A second display face is a decision, not a flourish.

| Step | Size / weight / line-height | Use |
|---|---|---|
| ‹display› | ‹…› | Page title |
| ‹heading› | ‹…› | Section heading |
| ‹body› | ‹…› | Default |
| ‹small› | ‹…› | Metadata, help text |
| ‹micro› | ‹…› | Badges, eyebrow labels only |

**Rule 3.2 — Body text has a minimum size.** **FILL:** ‹14px / 16px›. Below it, the user in §0 cannot read the screen at arm's length. Small text is not a way to fit more in — it is a way to lose the reader.

**Rule 3.3 — Tabular numerals wherever digits align in a column.** Proportional digits make a table of numbers unreadable.

**Rule 3.4 — Line length capped** at roughly ‹60–75› characters for prose.

---

## 4. Spacing, layout, density

**Rule 4.1 — One spacing scale**, ‹4px›-based. Never a one-off `margin: 13px`.

**Rule 4.2 — Density is a stated choice.** **FILL:** ‹compact (data-dense operational tool) | comfortable (occasional use)›, and why. Mixing densities across screens makes an application feel like two applications.

**Rule 4.3 — Touch targets ≥ 44×44px** on any surface reachable from a phone.

**Rule 4.4 — Content has a max width**; full-bleed text on a wide monitor is unreadable.

---

## 5. Icons

**Rule 5.1 — One icon library. FILL:** ‹library›. No second library, no mixed sets, no emoji.

**Rule 5.2 — Never import an icon directly. Import a semantic alias** from `‹lib/icons›`:

```
// Correct — the alias says what it means, and one edit swaps it everywhere
import { IconSave, IconDelete } from "‹@/lib/icons›";

// Wrong — invisible dependency, and a rename becomes a hunt
import { Check, Trash2 } from "‹icon-library›";
```

*Why:* semantic aliases survive an icon swap and make intent greppable. Adding an icon = add one alias export, then import the alias.

**Rule 5.3 — Size by context**, not by eye:

| Context | Size |
|---|---|
| Navigation | ‹18› |
| Inline with body text | ‹15› |
| Badge / label prefix | ‹12› |

**Rule 5.4 — No emoji as UI chrome.** Emoji render differently on every platform (worst on Android and older Windows), cannot be coloured or sized to match, and misalign with text. Map every emoji you are tempted to use to an icon or a component.

**Rule 5.5 — Every icon-only control has an accessible name.** An icon without a label is a guess for a sighted user and silence for a screen reader.

---

## 6. Semantic tokens

**Rule 6.1 — Components use semantic tokens, never raw colour values or utility classes.** One file (`‹lib/design-tokens›`) exports them.

```
‹text›       // { heading, body, secondary, muted }
‹primary›    // action colours
‹danger› ‹warning› ‹success›
‹STATUS_BADGE›   // domain status → { bg, text }
‹STATUS_LABELS›  // domain status → the word shown (must match the copy guide)
```

*Why:* a raw `bg-blue-600` in forty components is forty edits and one missed. A token is one edit. It also forces you to name the *meaning*, which is where inconsistency actually starts.

**Rule 6.2 — Status/state maps live in the token file, not inline.** Every domain state gets exactly one badge style and exactly one label, project-wide.

| ‹Status› | Label | Colour |
|---|---|---|
| ‹CODE› | ‹"Word"› | ‹family/shade› |

**Rule 6.3 — Labels here must match the canonical vocabulary** in the copy guide §4.1. This table and that one are the same decision expressed twice; when they disagree, screens disagree.

---

## 7. Component inventory

**Rule 7.1 — Three tiers, and the boundary is knowledge:**

| Tier | Location | Knows about the domain? |
|---|---|---|
| **Primitives** | `‹components/ui›` | **No.** Props in, pixels out |
| **Shared** | `‹components/shared›` | Cross-cutting behaviour used by ≥3 features |
| **Feature** | `‹components/‹feature››` | Yes — owned by one area |

**Rule 7.2 — Promote to shared on the third use, not the first.** Two call sites is a coincidence; three is a pattern. Premature sharing produces a component with nine boolean props that nobody dares change.

**Rule 7.3 — Every interactive component defines all its states** before it ships: default, hover, focus (**visible**), active, disabled, loading, error, empty.

**Rule 7.4 — Every data view renders three states.** Loading, error, empty — not just the happy path. On a slow connection the loading state is what the user looks at most, and a silent empty list is indistinguishable from a failure.

---

## 8. Accessibility

**Rule 8.1 — Semantic HTML.** Buttons are `<button>`, links are `<a>`. A clickable `<div>` is a bug: no keyboard, no focus, no screen reader.

**Rule 8.2 — Keyboard reachable, with a visible focus indicator.** Never remove focus outlines without replacing them.

**Rule 8.3 — Every input has a real, associated label.** Placeholder text is not a label — it disappears exactly when the user needs it.

**Rule 8.4 — Contrast floors from §2.2 apply to icons and borders too**, not only text.

**Rule 8.5 — Respect `prefers-reduced-motion`.**

**FILL:** Name your conformance target (‹WCAG 2.1 AA›) and how it is checked (‹automated axe pass in CI | manual sweep per release›). An unchecked target is decoration.

---

## 9. Known deviations — do not extend

Every codebase drifts from its design system. Undocumented drift reads to the next contributor as permission.

| Deviation | Where | Target state |
|---|---|---|
| ‹what disagrees with this doc› | ‹file/path, or a command that finds them› | ‹the rule it should follow› |

**Rule 9.1 — Reconcile when you touch the file**, not as a separate project. A "design system migration" sprint never gets funded; a one-line fix while you're already in the file always does.

---

## 10. Changing this document

- A new rule needs its **reason** in one line, or the next reader will discard it.
- A new colour family, icon library, or component library is an **architecture decision** — record what was chosen, what was rejected, and what would change the answer.
- Update the "Known deviations" table in the same commit as any rule change; otherwise the rule ships already-violated.
