# Follow-up — the demo officer switcher is a one-way door (and lies about who you are)

> **Status:** 🔴 **OPEN — found 2026-07-16 while running [`docs/deployment/17_manual_browser_sweep.md`](../../../deployment/17_manual_browser_sweep.md) §C4.** · **Owner:** portal (`channels/ticketing-ui`) · **Priority:** **high for UAT / demo — blocks the sweep's most important section**; not a production security issue (bypass builds only).
> **Origin:** the sweep's §C4 ("Every tab at every role tier") instructs the tester to switch to `l1-officer@grm.local` and five other roles. **Doing so locks you out of admin with no UI path back.** §C4 is the section the sweep itself calls out as *"if you only have time for one part of this sweep, do C4"* — so this defect blocks the highest-value manual check we have.

## Symptom (as hit)

Switch from the default admin to any **non-admin** officer via the header switcher → then:

1. The switcher dropdown shows `API 403 /api/v1/users/roster: {"detail":"Admin role required"}`.
2. The header still reads **"DEMO GRM Admin"**.
3. The ticket queues appear **empty** — "my grievances are gone".
4. **There is no way back to admin from the UI.**

## Mechanism (verified 2026-07-16)

Three separate facts combine into the trap. None is a bug alone.

### 1. The switcher depends on an admin-only endpoint

`GET /api/v1/users/roster` is gated on `require_admin`:
- route: `ticketing/api/routers/users.py:965-977` (`_: CurrentUser = Depends(require_admin)`)
- gate: `ticketing/api/dependencies.py:313-320` → `HTTPException(403, "Admin role required")`

The switcher needs that roster to render its list (`app/providers/AuthProvider.tsx:232`, `components/AppShell.tsx:63-78`).

**⇒ The one control that switches identity depends on the privileges of the identity it is switching *away from*.** Switch to a non-admin and the control that would switch you back stops working.

### 2. The failure path does NOT clear the cookie — this is the actual defect

`app/providers/AuthProvider.tsx:264-269`:

```ts
} catch (e) {
  if (!cancelled) {
    setBypassRoster([]);
    setBypassRosterError(e instanceof Error ? e.message : "Failed to load roster");
    setUser(fallbackBypassToken());        // <-- claims super_admin
  }                                        // <-- but the officer cookie SURVIVES
}
```

Compare the sibling branch **twelve lines up** (`:260-263`), which gets it right:

```ts
} else {
  clearCookie(BYPASS_COOKIE);              // <-- self-heals
  setUser(fallbackBypassToken());
}
```

The pattern already exists. The catch branch simply omits it — so the roster 403 is **self-perpetuating**: the stale non-admin cookie causes the 403, and the 403 handler preserves the cookie that caused it. Every reload repeats it. The 24 h `max-age` (`:108`) is the only thing that eventually ends it.

### 3. The UI then lies about the effective identity

`fallbackBypassToken()` (`:17-26`) hardcodes:

```ts
name: "GRM Admin",
"custom:grm_roles": "super_admin",
```

So after the 403 the **portal believes you are super_admin** — it renders the admin header and admin tabs. Meanwhile the surviving `grm_bypass_user` cookie is still being turned into `x-internal-user-id` / `x-internal-role` headers by the proxy (`app/api/v1/[...path]/route.ts:53-68`), so **every API call is still made as the non-admin officer**.

**⇒ Admin-looking UI, officer-scoped data.** That is why the queues look empty: not (only) legitimate scope filtering, but an inconsistent state where the client's idea of the user and the server's disagree. The "empty queue" is the *correct* answer to the *wrong* question.

### Why clearing the cookie works (the current escape hatch)

`ticketing/api/dependencies.py:186-194` — in bypass mode, with **no** `x-internal-*` headers:

```python
uid = x_internal_user_id or BYPASS_DEFAULT_OFFICER
role_keys=(x_internal_role or "super_admin").split(",")
```

⇒ no cookie ⇒ no headers ⇒ backend answers as **super_admin** ⇒ roster loads ⇒ `pickDefaultOfficer` (`:51-58`) deliberately prefers a **privileged** entry ⇒ admin restored.

```js
document.cookie = "grm_bypass_user=; path=/; max-age=0";
document.cookie = "grm_mock_user=; path=/; max-age=0";
location.reload();
```

Cookie names: `BYPASS_COOKIE = "grm_bypass_user"`, `LEGACY_MOCK_COOKIE = "grm_mock_user"` (`AuthProvider.tsx:14-15`).

## Scope — bypass builds only

`AUTH_BYPASS` gates the proxy's cookie handling (`app/api/v1/[...path]/route.ts:53`), and `settings.bypass_enabled` gates the backend's header trust (`dependencies.py:185`), which HR-01 pinned to `APP_ENV=dev` + `AUTH_MODE=bypass`. **Keycloak builds ignore the cookie entirely** (`route.ts:54-56` — the comment says so explicitly). So this is a **demo/UAT defect, not a production authz hole**. HR-01's fail-closed guarantees are unaffected.

## Definition of done

Ordered by value. **(1) alone unblocks the sweep** and is a one-line change.

1. **Clear the cookie in the catch branch** (`AuthProvider.tsx:264-269`) — mirror `:260-263`. A roster failure then self-heals to admin on the next load, and the door stops being one-way. **Smallest fix; do this first.**
2. **Stop the UI claiming a role it doesn't have.** After a roster failure the header should surface the error state (or the *cookie's* real identity), not a hardcoded `super_admin`. An admin-looking UI over officer-scoped data is worse than an honest error — it sent this session hunting for missing grievances.
3. **Make the switcher not depend on admin.** Either gate the roster on `get_authenticated_user` when `bypass_enabled` (it is a dev-only convenience endpoint in that mode), or give the switcher a non-admin list source. **This is the root fix** — (1) only makes the trap recoverable, it does not stop you falling in.
4. **Add a visible "reset to admin" control** in bypass builds. `setBypassUserCookie(null)` (`:95-101`) already does exactly this — it is exported and has no caller for the reset case. The escape hatch exists in code and is unreachable from the UI.
5. **Regression test.** The portal has no DOM harness (D-48, tracked in [`settings-tab-render-tests.md`](settings-tab-render-tests.md)) — which is precisely why a switcher this broken shipped unnoticed. At minimum, a vitest on `AuthProvider`'s roster-failure path asserting the cookie is cleared.

## Notes for whoever picks this up

- **`setBypassUserCookie(null)`** (`:95-101`) is exported, clears both cookies, and appears to have **no caller for the null case** — verify with a grep. Someone anticipated this reset and never wired a button to it. (Same shape as `check_form_function_name` in T3-01: the guard exists, unconnected.)
- **Don't "fix" the empty queue.** For a correctly-switched officer an empty/small queue is *right* — scope + SEAH + visibility filtering (HR-02). The bug is the identity mismatch, not the filtering. Note `docs/TODO.md` separately tracks that the seed creates `UserRole` rows but **no `OfficerScope` rows**, which would make a *legitimately* switched officer's queue empty too — expect that, and don't chase it as part of this.
- **The sweep doc is being amended** with the escape hatch in §C4 so C4 stays runnable before this is fixed.
