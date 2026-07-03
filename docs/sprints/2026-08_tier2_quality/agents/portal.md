# Agent runbook — H2-01 + H2-06: Portal auth & thread hook

**Branch:** `tier2/h2-01-06-portal` off `integration/seah-claude` · **Spec:** [`../01-portal-auth-and-thread-spec.md`](../01-portal-auth-and-thread-spec.md) · Read [`README.md`](README.md) first. Order: H2-01 → H2-06. All work in `channels/ticketing-ui/`.

## Mission

End officer data loss at token expiry by actually using the stored refresh token (single-flight refresh + retry-once in `apiFetch`), then delete the ~350-line duplicated orchestration layer between the desktop and mobile ticket pages via one shared hook.

## H2-01 steps

1. Read the whole auth surface first: `lib/auth/oidc-auth.ts`, `token-storage.ts`, `session-expired.ts`, `AuthProvider.tsx`, and `apiFetch` in `lib/api.ts` (~214-236). Confirm the review's findings still hold (refresh token stored, never used; hard redirect at expiry; inverted skew check; substring 401 sniffing; Math.random state; no nonce; split-storage state/verifier).
2. Implement per spec §1 in order: `refreshTokens()` + single-flight → `apiFetch` proactive (60 s early) + reactive (401 → refresh → retry once) → `AuthProvider` periodic check refreshes instead of redirecting → logout revocation → small fixes (CSPRNG state, nonce, same-storage).
3. Keycloak specifics to verify against the local realm (auth profile per `docs/deployment/DOCKER.md`): token endpoint path, whether refresh-token rotation is on (it changes the single-flight failure mode — handle "invalid_grant" on a rotated token as session-expired), logout/revocation endpoint shape. Cross-check `docs/deployment/16_auth_keycloak.md`.
4. Vitest per spec (mock fetch; no live Keycloak in unit tests). `tsc` + eslint + build green.
5. Manual per spec: 1-minute token lifespan realm setting, 5-minute typing session, no data loss; revoked-refresh replay rejected. Record in `../PROGRESS.md`. Reset the realm lifespan afterwards.

## H2-06 steps

1. Diff the two pages side by side (`app/tickets/[id]/page.tsx` ~1,707 lines, `app/m/tickets/[id]/page.tsx`) and inventory every duplicated block (the spec's table lists the known ones; find the rest).
2. Build `lib/useTicketThread.ts` + `lib/threadCommands.ts` per spec §2. Resolve the two documented drifts to desktop behavior (extra `system` filter case; command-match-before-clear) and record both as intentional deviations in PROGRESS.
3. Convert the desktop page first, full manual pass; then mobile; then delete the dead duplicated code. Net deletion target ~300+ lines — report the actual diffstat in PROGRESS.
4. Vitest: `parseThreadCommand` cases + chip-filter parity. `tsc`/eslint/build green.
5. Manual side-by-side parity check per spec (run the old build from the base branch for comparison).

## Constraints

- No token-storage architecture change (localStorage stays — Tier-3 discussion), no state-management library, no page-file renames.
- Thread leaf components (`components/thread/*`) untouched.
- Keep `apiFetch`'s public signature stable — 153 endpoint functions depend on it.

## Done means

Both checklists ticked in `../PROGRESS.md` (incl. diffstat and manual results); CI green; realm settings restored.
