# Follow-up — a credential is written to the application log, and the OTP has no expiry at all

> **Raised:** 2026-08-27, building [DPG-30](../04-pii-redaction-spec.md#dpg-30).
> **Status:** 🟡 **OPEN.** ⚠ **Downgraded from 🔴 the same day it was raised** — the original framing
> claimed a completed impersonation and that was wrong. See §*What this is not*.
> **Size:** XS. Two lines deleted, one line changed.

---

## The finding

`backend/actions/forms/form_otp.py:312`, in `validate_otp_input`:

```python
self.logger.info(f"{self.name()} - Received value: {slot_value}")
```

`slot_value` is **the one-time password the complainant just typed.** Line `:343` logs it again on the
invalid-format path. Both at **INFO**, so both are on in every environment.

In the same log stream, at the same level:

- `backend/actions/services/contact/phone.py:27` logs the complainant's phone on **every** validation,
  and `:38` again on the invalid path;
- `backend/actions/forms/form_status_check.py:76` logs the phone on the status-check path.

## ⚠ What this is **not** — the original claim was wrong

This followup first said the logged OTP, beside the logged phone, *"is enough to complete a
status-check impersonation."* **It is not, and the claim was made without tracing whether the value is
usable.**

Verification is `otp_matches(slot_value, tracker.get_slot("otp_number"))` (`form_otp.py:349-352`): the
expected value lives in **that conversation's own slot**. An attacker running their own session holds
their own `otp_number`, so a leaked OTP string authenticates nothing on its own. Exploiting it would
need session replay or hijack as well — a different finding, which nobody has established.

**Recorded rather than quietly edited**, because the failure mode is the more useful artefact: a
plausible attack chain was written down from the *shape* of the finding (credential + identifier in one
log) without checking the one thing that decides it — whether the secret is verified against
per-session state or global state. It is per-session. **Trace the check before writing the attack.**

## What survives, and is still worth doing

A credential is written to the application log at **INFO**. That stands as a finding on its own terms:
logs are tailed, copied into bug reports and pasted into chat far more casually than databases are, and
`len(slot_value)` provides every diagnostic the line currently gives. **Two lines, no design needed** —
it is cheap, it is just not urgent, and it should ride along with DPG-34 rather than pre-empting it.

## ⭐ Two things found while checking, both more interesting than the log line

**1. There is no expiry on the OTP. At all.**
`backend/actions/services/otp/verification.py` is three functions: generate six digits, check it is six
digits, `input == expected`. **No timestamp, no TTL, no expiry check anywhere in the path.** The bound
is the lifetime of the conversation slot, not a clock.

This matters because *"an OTP stops working after a few minutes"* is the natural assumption — it is
what the name implies, and it is what makes logging one feel survivable. Here it is not true, and no
document says so. ⚠ **Do not treat "add a TTL" as an obvious fix**: it changes live intake behaviour
for every complainant on a slow connection, and it needs the owner's call on the window.

**2. `otp_number` is not cleared on successful verification.**
The success branch (`form_otp.py:352-364`) sets `otp_input`, `otp_status`, `otp_verified` and
`otp_resend_count` — and never `otp_number: None`. The accepted secret stays in session state after it
has served its purpose. Clearing it is a one-line change and strictly reduces exposure.

## ⚠ Open question — flagged, not claimed

When SMS delivery fails, `form_otp.py:121` does `dispatcher.utter_message(text=message_sms)`: **the OTP
is printed into the chat window**, as the designed fallback. On intake that may be fine. On the
**status-check** path — where the OTP's job is to prove the person controls the phone tied to the
grievance — printing it to whoever typed the number would defeat the control entirely, and the DOIT
gateway has **no fallback transport** since the SNS path was deleted (2026-08-24), so "SMS is down" is
a single condition that reaches this branch.

**Someone should trace whether the status-check flow hits it.** Deliberately not asserted here: the
last claim in this document made without tracing was the one that had to be retracted.

## ⭐ And one of the three log sites is a redaction that never fires

`form_status_check.py:76`:

```python
_sv = slot_value if not isinstance(slot_value, str) else (slot_value[:20] + "..." if len(slot_value) > 20 else slot_value)
self.logger.info("validate_complainant_phone: entry | slot_value=%s", _sv)
```

A Nepali mobile number is **10 digits**. The truncation triggers at 21 characters, so **it never fires
and the full number is logged.** A reviewer skimming the file sees `[:20]` and reads it as mitigated.

This is worth generalising into DPG-34's method: **grep for bounds and check whether they can be
reached.** A guard that is real code and permanently false is worse than no guard, because it stops
anyone looking again.

## What would close it

1. **Delete `form_otp.py:312` and `:343`.** If the diagnostic is genuinely useful, log
   `len(slot_value)` and the validation outcome — never the value. There is no debugging question that
   needs the digits.
2. **`form_status_check.py:76`** — drop `slot_value` from the line, or replace the dead truncation with
   `text_len_for_log`, the precedent already used on the SEAH path (`LLM_services.py:616`, `:647`).
3. **`phone.py:27`, `:38`** — same treatment. Already tracked as part of F-6; listed here so the three
   are fixed in one pass rather than three.
4. Then let **DPG-34's logging filter** be the backstop for what the next call site does, rather than
   the first line of defence for what this one already does.

## Related

- [`pii-egress-inventory.md`](../../../dpg/pii-egress-inventory.md) §3 — the full log-site table (at least twelve)
- [`privacy-assessment.md`](../../../dpg/privacy-assessment.md) — finding **F-6**
- [`../04-pii-redaction-spec.md#dpg-34`](../04-pii-redaction-spec.md#dpg-34) — where the filter lands
- [`../../../TODO.md`](../../../TODO.md) — the backlog row
