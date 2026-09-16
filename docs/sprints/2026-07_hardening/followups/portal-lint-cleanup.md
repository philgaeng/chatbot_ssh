# Follow-up — portal ESLint cleanup

> **Status:** open (unstarted) · **Owner:** portal · **Priority:** low (no CI gate impact — all warnings, 0 errors)
> **Origin:** the "future portal lint-cleanup ticket" referenced repeatedly in the Tier-1 hardening deviations ([`../PROGRESS.md`](../PROGRESS.md) HR-05/HR-06) but never actually created. This file **is** that ticket.

## Why this exists

HR-05 (CI pipeline) reserved the ESLint **error** channel for crash-class findings only (`react-hooks/rules-of-hooks`). To do that, several pre-existing rule families were downgraded to `warn` in `channels/ticketing-ui/eslint.config.mjs` (see the dated comment at :17–31) so they stay **surfaced but non-gating**. CI runs `eslint . --max-warnings=-1`, so warnings never fail the build — they just accumulate silently. This ticket is where that debt is paid down.

## Current inventory (measured 2026-07-13, `npx eslint .`)

**143 warnings, 0 errors.** By rule:

| Rule | Count | Nature | Auto-fixable? |
|---|---|---|---|
| `react-hooks/set-state-in-effect` | 77 | `setState` synchronously in an effect body (cascading-render advisory) | No — manual |
| `typescript-eslint/no-unused-vars` | 39 | dead locals/imports/params | Partly (`--fix` for some) |
| `react-hooks/exhaustive-deps` | 15 | missing/extra effect deps | No — manual (verify intent) |
| **Unused `eslint-disable` directives** | 4 | disable comments that no longer suppress anything | **Yes — `eslint --fix`** |
| `react/no-unescaped-entities` | 3 | literal `'`/`"` in JSX text | Yes (`--fix`) |
| `react-hooks/static-components` | 3 | component defined during render (React-19-compiler advisory) | No — manual |
| `react-hooks/purity` | 2 | `Date.now()` in render (`app/queue/page.tsx`) | No — manual |
| `react-hooks/immutability` | 2 | in-place mutation in render/hook | No — manual |

One of the 4 unused-disable directives is the example that surfaced during H2-01: `app/providers/AuthProvider.tsx` — the `getUserPreferences` effect's `// eslint-disable-line react-hooks/exhaustive-deps` (≈line 354) is redundant (the effect only calls a module import + a stable setter). It predates H2-01 and was left untouched under that ticket's no-scope-creep rule.

## Definition of done

- [ ] `npx eslint .` → **0 warnings** (or every remaining warning has an inline justification comment).
- [ ] The 4 unused-disable directives removed (`eslint --fix` handles these + `no-unescaped-entities`).
- [ ] `no-unused-vars` (39) cleared — delete dead code or `_`-prefix intentionally-unused params.
- [ ] The React-19-compiler advisories (`set-state-in-effect` 77, `static-components`, `purity`, `immutability`, `exhaustive-deps`) triaged: fix the real ones; for any deliberately kept, a scoped inline `eslint-disable-next-line` **with a reason** (not the blanket config downgrade).
- [ ] Once a family is clean, **flip it back to `error`** in `eslint.config.mjs` so it can't silently regress — this is the real endgame (undo the HR-05 blanket downgrades one family at a time).
- [ ] `tsc --noEmit` + `npm run build` still green; CI unchanged.

## Approach

Cheapest-first, one PR per slice so review stays small:

1. **Mechanical (minutes):** `eslint . --fix` → clears the 4 unused directives + 3 `no-unescaped-entities`. Verify build.
2. **Dead code:** the 39 `no-unused-vars` — mostly delete; underscore-prefix the few intentional params.
3. **`purity`/`immutability`/`static-components` (7 total):** small, localized refactors (e.g. hoist `Date.now()` out of render into a `useMemo`/prop).
4. **`set-state-in-effect` (77) + `exhaustive-deps` (15):** the bulk. Best done alongside the Tier-3 settings-page split (`app/settings/page.tsx` is the densest source) rather than as isolated churn.
5. **Lock it in:** re-enable each cleaned family as `error` in `eslint.config.mjs`.

## Notes

- Do **not** just delete warnings by widening the config downgrades — that hides debt. The direction is warn → fixed → error.
- Steps 1–3 are safe standalone. Step 4 pairs naturally with the settings-page decomposition (Tier 3), so consider sequencing it there rather than as a separate large diff.
