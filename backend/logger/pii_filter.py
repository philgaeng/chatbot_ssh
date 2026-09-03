# SPDX-License-Identifier: Apache-2.0

"""A logging filter that pseudonymises PII before a record is ever emitted (DPG-34).

**Why a filter and not a rule.** DPG-30 found at least twelve log sites carrying complainant data,
and DPG-34 fixed the ones it could name. Naming them is not a control: the thirteenth is written by
whoever adds the next call site, and they will not have read the inventory. A filter installed once,
centrally, cannot be forgotten by a future call site — which is the only version of this that stays
true.

⚠ **It is a backstop, not a licence.** A call site should still log identifiers rather than values —
`grievance_id`, not the narrative. This filter exists because "should" is not a mechanism, not to
make careless logging safe. `db_debug_log`'s helpers remain the first line.

⚠ **Formatted output, not raw args.** The filter rewrites `record.msg` after formatting, because PII
routinely arrives through `%s` arguments rather than the literal message. Rewriting only `msg` would
leave `logger.info("phone: %s", phone)` untouched — the exact shape of the sites DPG-30 found.

**Cost, and why the cheap pre-check is there.** Running the full recogniser set on every record would
put ~15 regexes on the hot path of a system that logs heavily. `_might_contain_pii` is a single cheap
scan that lets the overwhelming majority of records — *"task started"*, *"Updated grievance with ID"*
— through untouched. Only a record with a digit, an `@`, or a Devanagari character pays for the full
pass.

Spec: docs/sprints/2026-08-llm/04-pii-redaction-spec.md §DPG-34
"""
from __future__ import annotations

import logging
import re

# The cheap gate. A record with none of these cannot contain a phone, an email, an ID, a plate, or
# any Devanagari text — and a Roman name without one of them is what the recogniser's own
# title/gazetteer rules are for, so the gate deliberately admits letters too when a capital is
# present. Ordered so the commonest exit (plain ASCII status lines) is the first miss.
_CHEAP_GATE = re.compile(r"[0-9@ऀ-ॿ]|[A-Z][a-z]+\s+[A-Z][a-z]+")

# ⚠ Guard against pathological input. A filter that hangs on a 5 MB log line takes the process with
# it, and a truncated record is strictly better than a stalled worker. Records longer than this are
# redacted up to the bound and marked, rather than skipped — skipping would let the biggest payloads
# through untouched, which is the wrong way round.
_MAX_SCAN_CHARS = 20_000


class PiiRedactingFilter(logging.Filter):
    """Rewrites a record's formatted message with PII replaced by placeholders.

    Installed on the logger, not on a handler: a handler-level filter is missed by any handler added
    later, and this codebase adds a file handler and a console handler in two places.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            self._redact(record)
        except Exception:  # noqa: BLE001
            # ⚠ NEVER let redaction break logging. A filter that raises silently drops the record
            # in most configurations, which would turn a privacy control into an availability
            # incident and lose the very line someone is trying to read during one.
            #
            # ⚠ But do not let the original through either: a record that could not be redacted is
            # a record whose contents are unknown. Replace it and say so.
            record.msg = "⚠ log record suppressed: PII redaction failed (see DPG-34)"
            record.args = ()
        return True

    @staticmethod
    def _redact(record: logging.LogRecord) -> None:
        message = record.getMessage()
        if not message or not _CHEAP_GATE.search(message):
            return

        # Imported lazily: `backend.logger` is imported by nearly everything, and a module-level
        # import of the service layer here would make the logging package depend on it. This is the
        # circular-import exemption `02_python_services.md` rule 7.2 allows, with the reason.
        from backend.services.pii_service import redact_for_model

        scanned = message[:_MAX_SCAN_CHARS]
        result = redact_for_model(scanned)
        if not result.mapping:
            return

        redacted = result.text
        if len(message) > _MAX_SCAN_CHARS:
            redacted += f"… ⚠ [{len(message) - _MAX_SCAN_CHARS} chars beyond the redaction bound]"

        # The formatted message replaces both, so the args cannot re-introduce what was removed.
        record.msg = redacted
        record.args = ()


def install(logger: logging.Logger) -> None:
    """Attach the filter once. Idempotent — `TaskLogger` is constructed per task."""
    if any(isinstance(f, PiiRedactingFilter) for f in logger.filters):
        return
    logger.addFilter(PiiRedactingFilter())
