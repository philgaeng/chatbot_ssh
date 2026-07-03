# HR-06 — Portal Robustness (list error states, settings crash, error boundary)

> Workstream D · Branch `hardening/hr-06-portal` · Independent; coordinate with HR-05 on the eslint gate.
> All paths under `channels/ticketing-ui/`. Evidence: [`docs/reviews/devils_advocate_codebase.md`](../../reviews/devils_advocate_codebase.md) §2.4–2.5. Re-locate line numbers before editing.

## Problems (verified)

1. **Silently empty queue** — list pages swallow load failures into the empty state, indistinguishable from "no tickets", no retry. For an SLA tool this is a missed-deadline machine:
   - `app/tickets/page.tsx:77` — `.catch(console.error)`
   - `app/escalated/page.tsx:57` — same
   - `app/m/queue/page.tsx:130` — same
   - `app/queue/page.tsx` — same load pattern (verify)
   - `app/m/tickets/[id]/page.tsx:738-742` — load error ⇒ blank "not found"-ish render
2. **Verified crash**: `app/settings/page.tsx:4590-4616` — early `return` for non-admins **before** `useMemo` (:4599) and `useEffect` (:4612). ESLint confirms 2 × `react-hooks/rules-of-hooks` errors. A `project_admin` whose rights arrive async via `getAdminContext()` (`AuthProvider.tsx:213-220, 272-276`) renders once as non-admin then re-renders admin ⇒ "Rendered more hooks than during the previous render" ⇒ white page.
3. **No error boundary anywhere** — no `error.tsx` files in the repo; any render crash is a blank screen.
4. Notification-rules save silently ignores failure and bypasses auth headers: `app/settings/page.tsx:1666-1696` — raw `fetch` without `authHeaders()`, `catch { /* ignore */ }`. (In scope because it's a 401-swallowing sibling of the same class.)

## Change

1. **Shared list-load pattern**: add a tiny `useListLoad` helper (or inline per page — keep it simple, no new deps): `{ data, loading, error, reload }`, where the fetch `.catch` sets `error` instead of logging. Each affected page renders an error card ("Couldn't load tickets — Retry") when `error` is set, distinct from the empty state. Add a monotonic sequence guard (`seqRef`) so a stale response can't overwrite a newer one (the tab-switch race — zero `AbortController` exists today; the seq guard is the minimal fix).
   - Apply to: `app/queue/page.tsx`, `app/tickets/page.tsx`, `app/escalated/page.tsx`, `app/m/queue/page.tsx`, `app/m/tickets/[id]/page.tsx` (error state instead of blank).
2. **Settings crash**: move the `useMemo`/`useEffect` at :4599/:4612 above the early return at :4590 (hooks must be unconditional). Fix any other `rules-of-hooks` error eslint reports in the file. Do **not** attempt the page split (Tier-3).
3. **Error boundaries**: add `app/error.tsx` (client component: message + "Try again" via `reset()` + link to `/queue`) and `app/global-error.tsx`. Match existing Tailwind styling; use `lib/user-messages.ts` tone.
4. **Notification-rules fetches** (`app/settings/page.tsx:1666,1688,1690`): route through `lib/api.ts` (add typed `getNotificationRules`/`saveNotificationRules` using `apiFetch`), surface save failures to the user (reuse the page's existing error/toast pattern).

## Tests (acceptance)

Testing infra is intentionally minimal (no test runner exists — HR-05 adds tsc/eslint gates; a full vitest adoption is Tier-2):

- [ ] `npx eslint . ` ⇒ **0 `react-hooks/rules-of-hooks` errors** (the CI gate from HR-05 enforces this permanently).
- [ ] `npx tsc --noEmit` clean.
- [ ] **Vitest starter** (this ticket does add the seed, ~15 min): `vitest` + 3 unit tests for pure logic already flagged as untested — `lib/user-messages.ts` (`formatUserFacingError` strips `API 422 /path:` noise; maps the image-gate case) and the queue `effectiveDeadline`/tile bucketing math (export it from `app/queue/page.tsx` into `lib/queueTiles.ts` to make it testable — pure refactor, no behavior change). Wire `npm test` and add the job step to HR-05's workflow (coordinate).

## Manual verification (record in PROGRESS)

- [ ] Stop `ticketing_api`, load `/queue`, `/tickets`, `/escalated`, `/m/queue` ⇒ each shows the error card with Retry; restart API, Retry recovers without a full reload.
- [ ] Log in as a `project_admin` (or simulate: bypass mode with admin context arriving async) and open `/settings` ⇒ no crash, correct tabs.
- [ ] Throw deliberately in a page component (temporary) ⇒ `error.tsx` renders instead of a white page; remove the throw.
- [ ] Edit notification rules with the API down ⇒ visible error, no silent success.
