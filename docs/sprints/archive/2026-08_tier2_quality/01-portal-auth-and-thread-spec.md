# H2-01 / H2-06 — Portal: OIDC refresh + shared ticket-thread hook

> Workstream C · Branch `tier2/h2-01-06-portal` · Sequential: H2-01 then H2-06.
> All paths under `channels/ticketing-ui/`. Evidence: ticketing-ui review in [`docs/reviews/devils_advocate_codebase.md`](../../reviews/devils_advocate_codebase.md). Line numbers are July-2026 snapshots — re-locate before editing.

---

## 1. H2-01 — OIDC refresh-grant in `apiFetch`

### Problem (verified)

- The refresh token is **stored but never used**: `lib/auth/token-storage.ts:47-49` persists access/id/refresh tokens; grep confirms zero refresh-grant code anywhere. No silent renew.
- At access-token expiry (Keycloak default 5–15 min), `AuthProvider.tsx:309-317` hard-redirects to `/login?reason=session_expired`, and `apiFetch` mid-flight does the same via `handleSessionExpired()` — an officer typing a long case note **loses their work**.
- Clock-skew check is inverted-lenient: `lib/auth/session-expired.ts:28` treats a token as valid 30 s *past* expiry (guaranteeing a 401 window) instead of refreshing early.
- 401 detection is substring matching on error text (`session-expired.ts:46-52`, e.g. `lower.includes("credentials")`) — false-positive logouts possible.
- Adjacent small defects to fix while in the file: `state` generated with `Math.random()` (`oidc-auth.ts:19-22`, used :51) while `code_verifier` correctly uses `crypto.getRandomValues`; no `nonce` on the auth request (:58-66); `state` in localStorage but `code_verifier` in sessionStorage (:52/:55) so a cross-tab login completes with an empty verifier (:78 `?? ""`).

### Change

1. **Refresh grant** in `lib/auth/oidc-auth.ts`: `refreshTokens()` posting `grant_type=refresh_token` to the Keycloak token endpoint (same endpoint discovery the code-exchange uses). Store rotated tokens via the existing token-storage helpers.
2. **Single-flight**: one in-flight refresh promise shared by all callers (module-level `refreshPromise` — concurrent 401s must not fire N refreshes; Keycloak's refresh-token rotation makes the second refresh with the old token fail).
3. **Proactive + reactive wiring in `apiFetch`** (`lib/api.ts:214-236`):
   - Before request: if access token expires within 60 s ⇒ await refresh (fixes the inverted skew check — correct `session-expired.ts:28` accordingly).
   - On 401 response: await single-flight refresh, **retry the request once**; only if refresh itself fails ⇒ `handleSessionExpired()`.
   - Replace substring-based 401 sniffing with the actual HTTP status where `apiFetch` has it (it does — it's the fetch wrapper).
4. **`AuthProvider` periodic check** (:309-317): attempt refresh instead of redirecting; redirect only on refresh failure.
5. **Logout** (`oidc-auth.ts:114-146`): revoke the refresh token (Keycloak revocation/logout endpoint with `refresh_token`) before the front-channel redirect, including the `sessionStale` path.
6. **Small fixes**: `rand()` → `crypto.getRandomValues`; add `nonce` to the auth request and check it in the callback's id-token decode; put `state` and `code_verifier` in the **same** storage (sessionStorage) so cross-tab logins fail cleanly at the state check instead of with an empty verifier.
7. **Out of scope** (log in PROGRESS, don't do): moving tokens out of localStorage (cookie/BFF architecture change), multi-tab storage-event sync, deleting `cognito-auth.ts` if not already done in HR-06.

### Tests (acceptance)

Vitest (infra from HR-06):
- [ ] `refreshTokens` single-flight: 3 concurrent callers ⇒ exactly 1 token-endpoint POST (mock fetch).
- [ ] `apiFetch` 401 → refresh → retry-once → success path; and 401 → refresh fails → `handleSessionExpired` called exactly once.
- [ ] Near-expiry (`exp - 60s < now`) triggers proactive refresh before the request.
- [ ] Expired-past-skew token no longer treated as valid (regression test on the corrected check).
- [ ] `tsc --noEmit` + eslint clean; CI green.

### Manual verification (record in PROGRESS)
- [ ] Against local Keycloak (auth profile, `docs/deployment/DOCKER.md`): set access-token lifespan to 1 min in the realm, log in, keep the tab open 5+ min while typing a note ⇒ no redirect, note submits successfully; network tab shows refresh POSTs.
- [ ] Logout ⇒ refresh token rejected on manual replay (curl the token endpoint with the old refresh token ⇒ error).

---

## 2. H2-06 — Shared `useTicketThread` hook

### Problem (verified)

Desktop `app/tickets/[id]/page.tsx` and mobile `app/m/tickets/[id]/page.tsx` duplicate ~350–450 lines of page-orchestration logic each, already drifting:

| Duplicated logic | Desktop | Mobile | Drift |
|---|---|---|---|
| `filteredEvents` switch | 847-860 | 780-792 | desktop has an extra `"system"` case — mobile silently differs |
| `submitEscalation` | 938-962 | 880-902 | — |
| `submitResolve` | 972-990 | 941-959 | — |
| `mentionParticipants` | 878-887 | 836-845 | — |
| `handleNoteOrReport` incl. `#assign` regex | 1191-1224 | 987-1021 | desktop computes `assignMatch` before clearing input, mobile after |
| `refreshFiles`, `ensureAcknowledged`, `viewerIds/viewerTiers` | various | various | — |

Two copies of a 40-line command parser is a bug farm; leaf components (`components/thread/*`) are already shared — only the orchestration layer is duplicated.

### Change

1. New `lib/useTicketThread.ts`: one hook owning ticket load/reload, events + `filteredEvents` (chip filtering — **one** switch, keep the desktop `"system"` case), files, viewers/tiers, mention participants, acknowledge-ensure, and the mutation handlers (`submitNote`, `submitEscalation`, `submitResolve`, `submitCallReport`, reassignment). Pure logic + state; no JSX.
2. New `lib/threadCommands.ts`: extract the `#assign`/`#inspect` hash-command parsing into a pure function (`parseThreadCommand(input) → {kind, args, rest}`) — resolve the desktop/mobile ordering drift to the **desktop** behavior (compute match before clearing input) and document why in a comment.
3. Both pages consume the hook; page files keep only layout/JSX and page-specific UI state (sheets vs panels). Expected net deletion: ~300+ lines.
4. Zero behavior change except the two documented drift resolutions (mobile gains the `"system"` filter case; mobile adopts desktop command ordering). List both in PROGRESS deviations as intentional.

### Tests (acceptance)

- [ ] Vitest unit tests for `parseThreadCommand`: `#assign @name reason`, `#inspect`, plain note, malformed input, the clear-order regression case.
- [ ] Vitest unit test for the event chip filter: same input events ⇒ identical output on the shared function for every chip incl. `system`.
- [ ] `tsc --noEmit` + eslint + `npm run build` green.

### Manual verification (record in PROGRESS)
- [ ] Desktop and mobile ticket pages: load, filter chips (all), add note, `#assign`, escalate with image gate, resolve, task card, viewers bar — behavior identical to pre-refactor (side-by-side against `integration/seah-claude` build).
