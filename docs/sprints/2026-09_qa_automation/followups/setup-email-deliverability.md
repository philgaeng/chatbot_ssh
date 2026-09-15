# `GRM-133` · `GRM-134` — officer setup emails reach Spam, and a mail scanner opens their link

**Opened 2026-09-15** while verifying `GRM-130` on staging with the owner. Logged in
[`SPINE.md`](../../../SPINE.md) per the standing deferral rule. Neither is fixed. `GRM-133` needs an
owner decision on the sending address.

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
3. **The same sender is on every host:** `SMTP_SERVER` is in `.env.shared` and `SMTP_FROM` is a shared
   secret, so **production very likely sends from the same address**. Not checked on the DOR host.

The spam headers from the received email (`X-Spam-*`, `Authentication-Results`) would confirm which
rule fired. Read the headers only: the body holds a live setup link.

### The fix, when picked up

- **In code, cheap:** a `grm` email theme with a plain subject that names the service (e.g. *Set your
  password for the GRM officer portal*), who sent it and why, and the same link. Set
  `emailTheme: grm` in `setup_realm_login_theme`.
- **Owner / DOR decision, the one that matters most:** send from a mailbox **on the portal's own
  domain**, with SPF, DKIM and DMARC for it. For production that is a `dor.gov.np` address. For staging,
  a `facets-ai.com` one. Until then every setup email arrives from a personal address with a link to
  another domain.

## `GRM-134` — a mail scanner opens the setup link before the officer does

### Measured on staging, 2026-09-15

29 s after the setup email to the `adb.org` address was sent, `57.155.170.164` (Microsoft) requested the
action-token link with a desktop Chrome user agent, and followed it to `required-action`. That is how
Microsoft 365 link scanning (Defender Safe Links) behaves. **The grm login theme moves the scanner
forward on its own:** `info.ftl` auto-continues past Keycloak's *"Perform the following actions"* page
(`16_auth_keycloak.md` §3), which was added so officers skip a click.

### Not measured

Whether that visit **uses up the link**. If Keycloak treats the execute-actions token as single-use, or
the scanner's visit binds it to the scanner's session, every officer on a scanned mailbox (ADB, and
probably DOR) will find their setup link already expired or used. Measure on a local realm first:
open the link in one client, stop at the password form, then open it in another client.

### The fix, if it is consumed

Make the first page need a human action: drop the auto-continue so the officer clicks *Continue*.
Scanners fetch pages but do not click.
