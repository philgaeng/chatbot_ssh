# `GRM-131` — anyone who knew an invited officer's email could take the account

**Opened 2026-09-15** while fixing `GRM-130`, **measured and fixed the same day** at the owner's request.
Logged in [`SPINE.md`](../../../SPINE.md). **Kind:** `bug` · **+SENSITIVE** (auth) · 🔴 high.
What is still owed is at the end: a clean-up on each realm.

## What was true

`keycloak_create_user` (`ticketing/services/officer_admin.py`) created every invited or appointed
officer as an **enabled** Keycloak user, with `UPDATE_PASSWORD` pending and a temporary password of
`temp_password or "GrmDemo2026!"`. The officer UI never sends `temp_password`, so every real account
got the demo password — the one [`16_auth_keycloak.md`](../../../deployment/16_auth_keycloak.md) §4
publishes for the `@grm.local` demo officers.

## Measured, 2026-09-15

On the **local** Keycloak (same realm setup), with throwaway `@grm-probe.invalid` users, all deleted after:

| Account | Browser login (`ticketing-ui` auth endpoint) |
| --- | --- |
| Setup pending, temporary password, **right** password | `302` to *set a new password*; the new password is saved and Keycloak **redirects to the officer UI with an auth code** |
| Same account, wrong password (control) | *Invalid username or password* |
| Setup pending, **no** password | *Invalid username or password* |

So an invitee's email was all it took to set the account's password before the officer did, and
sign in with whatever roles the invite carried. Officers normally sign in through the password grant on
`ticketing-api`, which Keycloak refuses while setup is pending. That path was never the problem:
Keycloak's own browser login is the one that takes a temporary password.

**On staging:** a setup email Keycloak refused (`GRM-130`) had left one such account behind: enabled,
setup pending, no ticketing row. **Not counted:** how many other exposed accounts staging and production
hold. Listing them would print officers' emails, so the clean-up command reports counts only.
**Local holds 3.**

## What was fixed

- **No password on a new account.** The setup email sets the first one. `temp_password` is gone from
  the invite API and the UI type.
- **A refused setup email deletes the account that call created**, never an account that already
  existed.
- **Re-sending setup to an account that never finished it removes any password on it.** An officer who
  finished setup keeps theirs. A disabled account being re-invited loses its old password. Before, it
  was overwritten with the demo one.
- **`keycloak_setup --clear-invite-passwords [--apply]`** repairs existing realms. It skips demo
  officers and logs counts only.

**Tests:** `tests/ticketing/test_invited_account_has_no_password.py`, 10 tests. Seven mutations each
turn a test red: a password on create; no delete on a failed email; resend never strips; resend always
strips; a returning account keeps its password; the clean-up touching demo officers; the dry run
applying. **On real Keycloak:** an invite refused by Keycloak left no account; after the clean-up's
delete step, the takeover login on an old-style account was refused.

## Owed, per realm, after the deploy

1. `python -m ticketing.auth.keycloak_setup --clear-invite-passwords` — read the counts.
2. The same command with `--apply`.
3. Re-run step 1: `with_password` should be `0`.

⚠ An officer who was given the demo password as a workaround (plausible on staging, where setup emails
failed under `GRM-130`) will be unable to sign in afterwards, and needs **Send setup email**.

## Not in scope, noted

The `@grm.local` demo officers still use the published demo password, by design. Production strips
them (`scripts/ops/prod_sync_remove_mock_data.sql`). Staging keeps them, including `admin@grm.local`
as `super_admin`. That is safe only while staging holds no real data and demo passwords were changed
or never used.
