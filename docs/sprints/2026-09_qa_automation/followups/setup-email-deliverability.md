# `GRM-133` · `GRM-134` — officer setup emails reach Spam, and a mail scanner opens their link

**Opened 2026-09-15** while verifying `GRM-130` on staging with the owner. Logged in
[`SPINE.md`](../../../SPINE.md).

**State, 2026-09-16:** `GRM-133` has its email template (built, tested, not deployed). The sender switch
waits on the owner copying production's mail credentials. `GRM-134` was measured and is **not a
problem**; the escaping defect it found is fixed.

## `GRM-133` — setup emails are filed as spam

### Measured on staging, 2026-09-15

Same relay (`mail.infomaniak.com:587`), same sender (`"GRM" <philippe@gaeng.fr>`), same mailboxes:

| Email | Relay reply | Where it went |
| --- | --- | --- |
| Plain delivery check, to `philippe@gaeng.fr` and `philgaeng@pm.me` | `250 queued` | **Inbox**, both (owner confirmed) |
| Keycloak setup email to `philippe@gaeng.fr` (15:41 UTC) | accepted (admin event, no error) | **Infomaniak Spam** (owner confirmed) |
| Keycloak setup emails to the same two addresses (14:24, 14:26 UTC) | accepted | not found by the owner, Spam likely |
| Keycloak setup email to an `adb.org` address (14:22 UTC) | accepted | delivered: a Microsoft IP opened its link 29 s later (`GRM-134`) |

So the relay and the app work, and the **setup email itself** is what gets filtered. `GRM-130` is not
the cause: before `GRM-130` no setup email left staging at all.

### Why, as far as can be seen from here (inferred, not read from a spam report)

1. **The email is Keycloak's default template** (`emailTheme: keycloak`): subject *Update Your Account*,
   body *"Your administrator has just requested that you update your … account … Update Password"*, and
   a sign-in link. That is the text of a typical credential-phishing email.
2. **The sender's domain is not the link's domain.** From `gaeng.fr`, a personal domain, while the link
   points to `nepal-gms-chatbot.facets-ai.com`. `gaeng.fr`'s SPF (`include:spf.infomaniak.ch -all`) and
   DMARC (`p=reject`) are correct, so this is mismatch and reputation, not a broken record.
3. ⛔ ~~Production very likely sends from the same address~~ — **wrong, corrected by the owner
   2026-09-15:** production already sends as `info@grm-chatbot-nepal.org`. The shared `SMTP_*` in
   `secrets.enc.env` were reconciled from staging, but each host reads its own `env.local`.

The spam headers from the received email (`X-Spam-*`, `Authentication-Results`) would confirm which
rule fired. Read the headers only: the body holds a live setup link.

### The fix

- ✅ **Built 2026-09-16:** a `grm` email theme (`emailTheme: grm`, set by `setup_realm_login_theme`).
  Subject *Set your password for GRM Ticketing*, plain wording for officers reading English as a second
  language, and a *Set my password* button. Rendered by a local Keycloak into Mailpit and read back.
  Pinned by `tests/ticketing/test_keycloak_themes.py`.
- ⏳ **Owner decision, 2026-09-15: staging and production send as `info@grm-chatbot-nepal.org`**, with
  production's credentials. The domain is on Infomaniak with SPF (`include:spf.infomaniak.ch -all`) and
  DMARC (`p=reject`). The owner copies the credentials to staging; then recreate `backend` and
  `ticketing_api`, re-apply the realm SMTP, and send a setup email to an owned mailbox: inbox or Spam?
  The link still points at another domain than the sender's; whether that alone keeps it in Spam is
  what that test will show.

## `GRM-134` — a mail scanner opens the setup link before the officer does

### Measured on staging, 2026-09-15

29 s after the setup email to the `adb.org` address was sent, `57.155.170.164` (Microsoft) requested the
action-token link with a desktop Chrome user agent, and followed it to `required-action`. That is how
Microsoft 365 link scanning (Defender Safe Links) behaves. **The grm login theme moves the scanner
forward on its own:** `info.ftl` auto-continues past Keycloak's *"Perform the following actions"* page
(`16_auth_keycloak.md` §3), which was added so officers skip a click.

### Measured on a local realm, 2026-09-16 — the link is NOT used up

Local Keycloak with the `grm` theme, realm SMTP pointed at a throwaway Mailpit (restored after), throwaway
users (deleted). Each scenario used a fresh setup link. The scanner and the officer each had their own
browser session.

| Scanner behaviour | What the officer then gets from the same link |
| --- | --- |
| none (control) | password form → password saved → forwarded to the GRM login |
| fetches the link only | the same |
| fetches it **and runs the auto-continue script**, reaching the password form (what staging's log shows) | the same |

Keycloak confirmed each account then had a password and nothing pending. **No fix needed.**

### Found by the same measurement, and fixed

The auto-continue wrote its URL HTML-escaped into a `<script>`, where `&amp;` stays literal, so Keycloak
received `amp;client_id` and `amp;tab_id` and ignored them (staging's nginx log shows the same). It worked
anyway. `info.ftl` now uses `?js_string?no_esc`; the three scenarios were re-run on the fixed theme with
the same result.
