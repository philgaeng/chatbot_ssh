# SPDX-License-Identifier: Apache-2.0
"""
T-34-a — a grievance narrative passed to a logger does not appear in the emitted record.

**The acceptance item this is, verbatim:** *"A test proving a grievance narrative passed to a logger
does not appear in the emitted record."*

**Why a filter and not a list of fixed call sites.** DPG-30 found at least twelve log sites carrying
complainant data and DPG-34 fixed the ones it could name — but naming them is not a control. The
thirteenth is written by whoever adds the next call site, and they will not have read the inventory.
A filter installed once, centrally, is the only version that stays true.

⚠ **It is a backstop, not a licence.** Call sites should still log identifiers rather than values;
`db_debug_log`'s helpers remain the first line. These tests pin the backstop, not permission.

Spec: docs/sprints/2026-08-llm/04-pii-redaction-spec.md §DPG-34
"""
from __future__ import annotations

import logging

import pytest

from backend.logger.pii_filter import PiiRedactingFilter, install

NARRATIVE = (
    "Er. Rajesh Shrestha refused to spray the road. Call 9812345678, ward 5 Duhabi."
)


@pytest.fixture()
def logger_and_records():
    """A logger with the filter installed and a handler that keeps what was emitted."""
    logger = logging.getLogger("test_pii_filter_" + str(id(object())))
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.filters.clear()

    emitted: list[str] = []

    class Capture(logging.Handler):
        def emit(self, record):
            # Format the way a real handler does — this is what reaches the file and stdout.
            emitted.append(self.format(record))

    handler = Capture()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    install(logger)
    return logger, emitted


# ═════════════════════════════════════════════════════════════════════════════
# The acceptance item
# ═════════════════════════════════════════════════════════════════════════════


def test_a_narrative_logged_as_the_message_does_not_reach_the_record(logger_and_records):
    logger, emitted = logger_and_records
    logger.info(NARRATIVE)

    assert emitted, "nothing was emitted"
    assert "Rajesh Shrestha" not in emitted[0]
    assert "9812345678" not in emitted[0]
    assert "<PERSON_1>" in emitted[0]


def test_a_narrative_passed_as_a_FORMAT_ARGUMENT_does_not_reach_the_record(logger_and_records):
    """⭐ The case a naive filter misses, and the shape of nearly every site DPG-30 found.

    `logger.info("phone: %s", phone)` leaves `record.msg` clean and the PII in `record.args`. A
    filter that rewrote only `msg` would pass this straight through while looking like it worked.
    """
    logger, emitted = logger_and_records
    logger.info("validating: %s", NARRATIVE)

    assert "Rajesh Shrestha" not in emitted[0]
    assert "9812345678" not in emitted[0]


def test_multiple_arguments_are_all_covered(logger_and_records):
    logger, emitted = logger_and_records
    logger.warning("%s called about %s", "Er. Rajesh Shrestha", "ward 5 Duhabi")

    assert "Rajesh Shrestha" not in emitted[0]


@pytest.mark.parametrize(
    "message",
    [
        "task started",
        "Updated grievance with ID: GR-20260715-KOJH-579E, rows affected: 1",
        "classification_trigger_enqueued grievance_id=GR-1 task_id=abc",
    ],
)
def test_ordinary_operational_lines_pass_through_unchanged(message, logger_and_records):
    """⚠ The filter must not damage the logs it does not need to touch.

    Grievance ids, task ids and counts are exactly what a call site SHOULD be logging, and a filter
    that mangled them would push people back toward logging values instead.
    """
    logger, emitted = logger_and_records
    logger.info(message)

    assert emitted[0] == message


# ═════════════════════════════════════════════════════════════════════════════
# It is installed where it claims to be
# ═════════════════════════════════════════════════════════════════════════════


def test_the_filter_is_installed_on_the_logger_not_a_handler():
    """A handler-level filter is missed by any handler added later — and `_setup_logger` adds two."""
    from backend.logger.logger import TaskLogger

    task_logger = TaskLogger(service_name="test_install_check")
    assert any(isinstance(f, PiiRedactingFilter) for f in task_logger.logger.filters), (
        "TaskLogger's logger has no PII filter — every service that logs through it is unprotected"
    )


def test_installing_twice_does_not_stack_filters():
    """`TaskLogger` is constructed per task; a non-idempotent install would add one filter per task."""
    logger = logging.getLogger("test_idempotent_install")
    logger.filters.clear()
    install(logger)
    install(logger)
    install(logger)

    assert sum(isinstance(f, PiiRedactingFilter) for f in logger.filters) == 1


# ═════════════════════════════════════════════════════════════════════════════
# Failure behaviour — the part that decides whether this is safe to install globally
# ═════════════════════════════════════════════════════════════════════════════


def test_a_redaction_failure_suppresses_the_content_rather_than_leaking_it(monkeypatch):
    """⚠ Two ways to get this wrong, and both are worse than the bug.

    Raising from a filter drops the record in most configurations — turning a privacy control into
    an availability incident, and losing the very line someone is reading during one. Letting the
    original through is a leak. So: never raise, and never emit content whose redaction is unknown.
    """
    import backend.services.pii_service as svc

    def boom(_text):
        raise RuntimeError("recogniser exploded")

    monkeypatch.setattr(svc, "redact_for_model", boom)

    record = logging.LogRecord(
        name="x", level=logging.INFO, pathname=__file__, lineno=1,
        msg=NARRATIVE, args=(), exc_info=None,
    )
    assert PiiRedactingFilter().filter(record) is True, "the record must not be dropped"
    assert "Rajesh Shrestha" not in record.getMessage()
    assert "suppressed" in record.getMessage()


def test_a_very_long_record_is_bounded_but_still_redacted():
    """A pathological line must not hang the process — and must not slip through untouched either.

    Skipping oversized records would let the biggest payloads past, which is the wrong way round.
    """
    from backend.logger.pii_filter import _MAX_SCAN_CHARS

    record = logging.LogRecord(
        name="x", level=logging.INFO, pathname=__file__, lineno=1,
        msg=NARRATIVE + ("x" * (_MAX_SCAN_CHARS + 500)), args=(), exc_info=None,
    )
    PiiRedactingFilter().filter(record)
    out = record.getMessage()

    assert "Rajesh Shrestha" not in out
    assert "beyond the redaction bound" in out, "the truncation must be visible, not silent"
