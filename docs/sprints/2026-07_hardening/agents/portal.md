# Agent runbook — HR-06: Portal robustness

**Branch:** `hardening/hr-06-portal` off `integration/seah-claude` · **Model:** Sonnet (medium effort — mechanical UI plumbing) · **Spec:** [`../04-portal-robustness-spec.md`](../04-portal-robustness-spec.md) · Read [`README.md`](README.md) common rules first. All work in `channels/ticketing-ui/`.

## Mission

Kill the portal's three silent failure modes: queue pages that render "empty" when the API is down, a verified hooks-order crash in settings for project admins, and the absence of any error boundary. Plus seed the first unit tests.

## Steps

1. **Baseline:** `npm ci`, then `npx tsc --noEmit` (expect clean) and `npx eslint . 2>&1 | grep rules-of-hooks` (expect exactly 2 errors in `app/settings/page.tsx`). If HR-05 already merged an eslint baseline change, pull it in.
2. **Settings crash first** (smallest, highest severity): in `app/settings/page.tsx`, find the early non-admin `return` (~line 4590) sitting above a `useMemo` (~4599) and `useEffect` (~4612). Move the hooks above the return. Re-run eslint: 0 `rules-of-hooks` errors. Do NOT split the page or touch anything else in this 4,700-line file.
3. **Error boundaries:** add `app/error.tsx` and `app/global-error.tsx` (client components; message + "Try again" via `reset()` + link to `/queue`; style with existing Tailwind idioms — look at how empty states are styled in `app/queue/page.tsx`).
4. **List error states + seq guard** per spec §1 on the five pages (`app/queue`, `app/tickets`, `app/escalated`, `app/m/queue`, `app/m/tickets/[id]`). Pattern: replace `.catch(console.error)` with `setError`, render an error card with a Retry button distinct from the empty state, and guard with a `seqRef` counter so stale responses can't overwrite newer ones. Keep the helper local and dependency-free (no SWR/react-query — Tier-2 decision).
5. **Notification-rules fetches** (`app/settings/page.tsx` ~1666-1696): add typed `getNotificationRules`/`saveNotificationRules` to `lib/api.ts` (follow the file's section-header conventions and `apiFetch<T>` pattern), replace the raw `fetch` calls, surface save failure to the user.
6. **Vitest seed:** add `vitest` as a devDependency + `npm test` script. Extract the queue tile/deadline math (`effectiveDeadline`, tile bucketing in `app/queue/page.tsx` ~51-87, ~234-250) into `lib/queueTiles.ts` — pure move, queue page imports it, zero behavior change. Write 3 tests: `formatUserFacingError` strips API noise; the image-gate message mapping; tile buckets satisfy `actionNeeded ≥ dueToday + overdue` with boundary cases (deadline now, +23h, +25h, past). If HR-05's workflow exists on your base, add the `npm test` step to the ui job (coordinate via PROGRESS if not).
7. **Verify:** `npx tsc --noEmit`, `npx eslint .` (0 hooks errors), `npm test` green, `npm run build` completes. Execute the spec's manual verification list against the local stack (`docs/deployment/DOCKER.md`; bypass auth mode) and record results in `../PROGRESS.md`.

## Constraints

- No new runtime dependencies (vitest is dev-only). No page splits, no state-management adoption, no AbortController sweep beyond the seq guards — Tier-2/3.
- Visual changes limited to the new error cards and boundary pages; match existing design (see `docs/ticketing_system/ui/02_design_system.md` — icon rules, palette, no emoji).
- Don't fix other eslint warnings/errors you encounter; log notable ones in PROGRESS deviations.

## Done means

All HR-06 checklist boxes ticked in `../PROGRESS.md`; tsc/eslint/test/build all green; manual checks (API-down cards, project_admin settings, boundary render, rules-save error) recorded.
