# Follow-up — the OTP is written to the application log at INFO, next to the phone number it authenticates

> **Raised:** 2026-08-27, building [DPG-30](../04-pii-redaction-spec.md#dpg-30).
> **Status:** 🔴 **OPEN — and this one should not wait for the redaction filter.**
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

## Why this is not just another F-6 row

The redaction work treats logs as a **privacy** problem — grievance text reaching a place it should
not. This is that, **and an access-control problem as well.**

The status-check flow authenticates a complainant with *phone + OTP*. Both halves are now in the
application log, at INFO, correlated by session, within the OTP's validity window. Anyone who can read
logs — which is a much larger set than anyone who can read the database, because logs get tailed,
copied into bug reports and pasted into chat — can complete that authentication.

**That is why it should not wait for DPG-34's filter.** A filter is the right long-term control and it
is a whole ticket; deleting a credential from a log is two lines and needs no design.

## ⭐ And one of the three is a redaction that never fires

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
