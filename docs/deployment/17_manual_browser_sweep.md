# 17 — Manual browser sweep (clears the pending-human debt)

> **One session, ~60–75 min.** Clears the browser-only checks carried since Tier 1:
> **D-17 · D-24 · D-33 · D-49 · D-56** (Tier 3) and the inherited **HR-07 · H2-02 · H2-06 · H2-08**.
> Everything else in these tickets is already automated and green in CI — this is the part a
> machine in the build env genuinely could not do.
>
> **Two items are NOT in this sweep** and are called out at the end: **H2-01** (needs a
> different auth build) and **HR-05** (GitHub settings, not a browser).

---

## ⚠️ Read this first — the one thing that will waste your evening

**Do not test the PII card on a seeded ticket.** Measured on the dev DB right now:

| | |
|---|---|
| tickets (not deleted) | **36** (30 standard, 6 SEAH) |
| …whose grievance row exists | 24 |
| …whose complainant has a **name** | **0** |

Every seeded ticket's contact card shows **"—"** for name/phone/email/address — because the
data isn't there, **not** because anything is broken. That is **indistinguishable from the
exact bug T3-04 fixed** (which blanked every card). Seeded data cannot tell "fixed" from
"broken" here.

**⇒ Part A files a fresh grievance *with contact details*, and Part C checks *that* ticket.**
That ordering is the whole reason the parts are in this order. Don't skip A and jump to C.

---

## 0 · Bring the stack up (~5 min)

```bash
cd ~/projects/nepal_chatbot
make wsl-up          # or: docker compose --env-file env.local -f docker-compose.yml -f docker-compose.grm.yml up -d
docker compose ps    # all services should read "healthy"
```

> **Rebuild if you have pulled since the sprint landed.** This stack **bakes source into
> images** — there are no bind-mounts, so a running container can serve code from before
> your last `git pull` and you will test the wrong thing (this bit the sprint twice):
> ```bash
> docker compose --env-file env.local -f docker-compose.yml -f docker-compose.grm.yml build backend orchestrator ticketing_api grm_ui
> make wsl-up
> ```

| What | URL |
|---|---|
| **Webchat** (complainant) | <http://localhost:8080/rest-webchat/> |
| **Officer portal** | <http://localhost:3001> |
| Orchestrator health | <http://localhost:8000/health> |

**Keep a log tail open in a second terminal.** Three of these checks are about things the UI
*doesn't* show you:

```bash
docker compose logs -f orchestrator backend ticketing_api | grep -iE "zero-message turn|unrecognized|ciphertext reached|ERROR"
```

**Nothing should appear here during a healthy sweep.** If `zero-message turn` appears, note
which step caused it — that is the dead-air guard firing, and it means a branch dispatched
nothing. It is a real finding, not noise.

---

## Part A · Webchat, English — file a grievance with contact details

**Clears: D-17 (Slow-3G voice) · D-24 (EN half) · HR-07 · and creates the ticket Part C needs.**

Open <http://localhost:8080/rest-webchat/> in a **fresh** tab (or hard-refresh — the page
sends `/introduce` on load, which resets the session).

### A1 · Language + menu
1. Click **English**.
2. ✅ The main menu renders with buttons.

### A2 · Voice note on Slow 3G — **D-17** *(do this before filing; it needs the throttle on)*

This is the T3-03 fix. Before it, a recording longer than ~1 s RTT **aborted and was
discarded**, and a second path produced **silently truncated** notes.

1. DevTools → **Network** → throttling → **Slow 3G**. *(Chrome: the dropdown that says "No throttling".)*
2. Start a grievance (**File a new grievance** → free-text step).
3. Record a voice note of **≥ 5 seconds** — say something you'll recognise, e.g. count "one… two… three… four… five".
4. Stop the recording.

| ✅ Pass | ❌ Fail |
|---|---|
| The note uploads and plays back **its full length** — you hear all five counts | Playback is short / cuts off (silent truncation) |
| No error banner | "Upload failed" / the recording vanishes |
| Log tail shows no `out of order` errors | `out of order` surfaced while still recording |

> **Why ≥5 s matters:** the race needs enough chunks for chunk *N* to start before chunk 0's
> `upload_id` comes back. A 2-second note may pass on a broken build.

5. **Turn throttling off** before continuing (the rest of the sweep is slow otherwise).

### A3 · Category review — **D-24, site 2** *(a mainline path, and it was silently broken)*

Continue filing. When the bot proposes **categories** for your grievance:

1. **Accept the selection as-is** (the "happy with these" / confirm option — do **not** modify).

| ✅ Pass | ❌ Fail (the pre-T3-01 bug) |
|---|---|
| A confirmation message renders and the form advances | **Zero messages** — the bot silently moves on |

Expected text (EN):
> `No category selected. skipping this step.`

> Before T3-01 this branch threw `ValueError`, got swallowed by a bare `except Exception`,
> and set the wrong slot state — **with no message at all**. Silence here is the bug.

### A4 · Provide contact details — **required for Part C**

Continue to the contact step and **enter real-looking details** (this is what Part C reads):

```
Name:    Sita Rai
Phone:   +9779812345678
Email:   sita.rai@example.np
Address: Ward 4, Birtamod
```

- Decline OTP if offered (skip verification) — it isn't needed for this sweep.
- Complete the location steps (Province **Koshi** → District **Jhapa** → Municipality **Birtamod**).
- Finish the review and **submit**.

5. ✅ **Write down the grievance ID** the bot gives you: `________________________`

> The ticket is created by webhook/sync within ~2 min. If it hasn't appeared in Part C, wait
> and refresh.

---

## Part B · Webchat, Nepali + SEAH

**Clears: D-24 (NE half) · H2-08 (SEAH EN/NE walk-through).**

### B1 · Nepali — **D-24**
1. Fresh tab → <http://localhost:8080/rest-webchat/> → click **नेपाली**.
2. Walk to the category review again and accept the selection.

| ✅ Pass | ❌ Fail |
|---|---|
| The confirmation renders **in Nepali** | English text, or nothing |

Expected text (NE):
> `यदि कुनै समूह चयन गरिएको छैन भने  यस चरणलाई छोड्नुहोस्‍।`

3. Skim the Nepali on the way through (**H2-08**): no tripled labels, no garbled address, no
   stray `ू`. Note anything odd — the SEAH strings were repaired in Tier 2 but only
   AI-reviewed.

### B2 · SEAH intake — **D-24 site 3: this was an HTTP 500** ⚠️

**The highest-value check in this sweep.** Before T3-01 this path returned **HTTP 500** on
the live SEAH intake flow.

1. Fresh tab → English → main menu → **SEAH / sensitive** option.
2. Choose the **victim / survivor** role.
3. At the **follow-up** prompt, send an **unrecognised free-text reply** — literally type:
   `asdf` and press enter.

| ✅ Pass | ❌ Fail (the pre-T3-01 bug) |
|---|---|
| A re-prompt renders and the chat continues | **HTTP 500** / the chat dies / a red error |

Expected text (EN):
> `Please choose anonymous grievance or grievance with contact details.`

4. Repeat in **Nepali**. Expected:
> `कृपया बेनामी गुनासो वा सम्पर्क विवरण सहितको गुनासो छनौट गर्नुहोस्‍।`

5. Finish the SEAH intake (any consistent answers) and **note its grievance ID**: `______________`

---

## Part C · Officer portal

Open <http://localhost:3001>. With `AUTH_MODE=bypass` (the default in `env.local`) you land
straight in — no login — via **"Continue to demo queue"**.

### C1 · The PII card on your fresh ticket — **D-56** ⭐

**This is the check T3-04 exists for.** Use the grievance ID from **A4** — *not* a seeded ticket
(see the warning at the top).

1. **All Tickets** → find the ticket for your grievance ID (search by it).
2. Open the ticket detail → the **complainant card**.

| ✅ Pass | ❌ Fail |
|---|---|
| **Sita Rai**, **+9779812345678**, **sita.rai@example.np**, **Ward 4, Birtamod** | "—" on every field *(the exact pre-T3-04 bug)* |
| | A long hex string like `c30d0407…` *(ciphertext leaking to an officer)* |

3. Check the log tail: `ciphertext reached the officer card` **must not** appear. If it does,
   the backend stopped decrypting — that is a real regression, and the message tells you where.

### C2 · SEAH ticket stays masked — **D-56 / TP-15**
1. Open the SEAH ticket from **B5** (or any 🔒 SEAH ticket).
2. ✅ Contact fields are **masked (—)**; the 🔒 badge and red left border render.
3. Click **Reveal contact** → ✅ the reveal flow works and the access is logged.

> Masking must hold **because it's SEAH**, not because the data is missing — which is why C1
> comes first: C1 proves the same pipeline *does* show PII for a standard ticket.

### C3 · Ticket detail + chatbot round-trip — **D-33**
1. On your ticket: ✅ grievance card, workflow stepper, SLA bar, event timeline all render.
2. **Acknowledge** it → ✅ the action succeeds and a timeline event appears.
3. Files: ✅ your voice note from **A2** is listed and plays.
4. Back in the **webchat**, run a **status check** on the grievance ID from A4:
   - ✅ Details render.
   - Try **Modify → add more info**, submit a detail.
   - ✅ **You get a message back** — silence here is D-51 (fixed; the log tail would show `zero-message turn`).

### C4 · Every tab at every role tier — **D-49 · H2-02 · H2-06**

The portal has a **role switcher** in the header (bypass builds only — it writes a
`grm_bypass_user` cookie the API proxy turns into an identity).

> ## 🚨 READ BEFORE YOU SWITCH — the switcher is a one-way door (**D-65**)
>
> **Switching to a non-admin officer locks you out of admin, and the UI will lie to you about it.**
> This is a known open bug, not something you did wrong. It bites on the *first* non-admin row
> in the table below.
>
> **What you'll see:** the dropdown shows `API 403 /api/v1/users/roster: {"detail":"Admin role
> required"}`, the header still says **"DEMO GRM Admin"**, and **your ticket queues look empty**.
>
> **Why:** the switcher's roster is admin-gated, so switching away from admin breaks the control
> that would switch you back. The failure path then displays a hardcoded `super_admin` identity
> **while the officer cookie survives** — so the UI thinks you're admin and the API still treats
> you as the officer. The empty queue is the *correct* answer to the *wrong* question. **Your
> data is fine.**
>
> ### 🔑 The escape hatch — paste in DevTools → Console, on the portal tab
>
> ```js
> document.cookie = "grm_bypass_user=; path=/; max-age=0";
> document.cookie = "grm_mock_user=; path=/; max-age=0";
> location.reload();
> ```
>
> *(Or: DevTools → Application → Cookies → delete **`grm_bypass_user`**.)*
>
> On reload the backend answers as super_admin (no cookie ⇒ no `x-internal-*` headers) and the
> portal re-picks a privileged officer. **You are back to admin.**
>
> ### ⇒ How to run C4 with the bug present
>
> **Do the escape hatch between *every* role.** The loop is:
>
> **switch → check the tabs → run the snippet → switch to the next role.**
>
> Do **`admin@grm.local` first** (it's the only one you can reach *from* a non-admin state
> without the snippet), and treat the snippet as step 0 of each row. It costs ~5 seconds.
>
> Full write-up: [`../sprints/archive/2026-08_tier3_structural/followups/demo-officer-switcher-one-way-door.md`](../sprints/archive/2026-08_tier3_structural/followups/demo-officer-switcher-one-way-door.md)

For each role below: switch, then click **My Queue → All Tickets → Escalated → GRC → Reports
→ Settings**.

| Role | Expect |
|---|---|
| `admin@grm.local` (super_admin) | Everything, incl. **Settings** and **GRC** |
| `country-admin@grm.local` (org_admin) | Admin surface; scoped to its org |
| `project-admin@grm.local` (project_admin) | Project scope; **no** org-level admin |
| `l1-officer@grm.local` (site L1, Morang) | Queue + tickets in scope; **no Settings** |
| `grc-chair@grm.local` (grc_chair) | **GRC** visible |
| `seah@grm.local` (seah_national_officer) | SEAH tickets visible **to this role only** |

| ✅ Pass | ❌ Fail |
|---|---|
| Every tab renders (no blank page, no crash) | A tab throws / white-screens |
| **Gating is unchanged** — non-admins see no Settings | An L1 can reach Settings |
| **A non-SEAH role never sees a 🔒 SEAH ticket** | SEAH leaks to a standard role |

> **An empty or small queue for a non-admin role is a PASS, not a finding.** Scope + SEAH +
> visibility filtering (HR-02) is *supposed* to hide tickets outside an officer's jurisdiction.
> Two separate reasons it may be **completely** empty, both known and neither a bug in what
> you're testing: **(a)** D-65 above — the API is still using the officer identity while the UI
> claims admin; **(b)** `docs/TODO.md` tracks that the seed creates `UserRole` rows but **no
> `OfficerScope` rows**, and an officer with zero scope rows matches nothing. **What you are
> checking here is that tabs *render* and that gating *holds* — not that tickets appear.**

> **Why this one is worth the clicks:** T3-05 moved **4,372 lines** out of `page.tsx` into 6
> clusters. `tsc`/`eslint`/`build`/vitest were green at every commit and the bodies were moved
> by line-range (never retyped) — but the portal has **no DOM test harness at all** (D-48), so
> *nothing automated has ever rendered these tabs*. This is the only thing standing between
> that refactor and a rendering regression.

5. **Settings** (as super_admin): click through each of the 6 tabs — **Admin Access ·
   Locations · System Config · Roles · Workflows · Projects**. ✅ Each renders and saves.

---

## Not in this sweep

| Item | Why | What it needs |
|---|---|---|
| **H2-01** — Keycloak token-expiry | The current stack is `AUTH_MODE=bypass`, so there are no tokens to expire. `NEXT_PUBLIC_*` are **baked at build time**, so this isn't a runtime toggle. | `AUTH_MODE=keycloak` + `KEYCLOAK_ISSUER=http://localhost:18080/realms/grm` in `env.local`, `docker compose --profile auth up -d keycloak`, **rebuild `grm_ui`**, then log in as a demo officer and idle past token expiry. Its own session. |
| **HR-05** — deliberate-failure + branch protection | Not a browser check — it is GitHub settings + a red CI run. | Push a deliberately-failing commit to a scratch branch; confirm CI goes red and that `main` refuses a direct push. |

---

## Recording the result

Update the checklist items in
[`../sprints/archive/2026-08_tier3_structural/PROGRESS.md`](../sprints/archive/2026-08_tier3_structural/PROGRESS.md)
(the `- [ ] Manual:` lines) and mark the deviations D-17/24/33/49/56 as cleared.

**If something fails, it is a finding, not a chore.** Log it the way the sprint logs
everything — a `followups/<slug>.md`, a `docs/TODO.md` 🔵 TECH DEBT row, **and** a PROGRESS
deviation, in the same commit. A deferral in fewer than three places goes invisible; that is
D-37, and this sprint re-learned it twice.

**Most of this is confirmation, not discovery** — and that is deliberate:

- **D-24** was pre-empted by driving both live sites in EN *and* NE directly and capturing the rendered strings (which is where the expected text above comes from).
- **D-33 / D-56** were driven end-to-end through **real clients against rebuilt containers**: a grievance seeded with real pgcrypto ciphertext at rest, read through the real HTTP API ⇒ plaintext, then through ticketing's real client ⇒ standard card populated, SEAH masked.
- **D-17** is guarded by a test verified red pre-fix — stronger than the manual check it substitutes for.

**D-49 is the genuine exception.** It has no automated equivalent: the deliverable *is* the
rendered UI, the portal has no DOM harness, and `page.tsx`'s role gating was never exercised.
**If you only have time for one part of this sweep, do C4.**
