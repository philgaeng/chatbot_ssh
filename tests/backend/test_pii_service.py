# SPDX-License-Identifier: Apache-2.0
"""
T-31-a … T-31-e — the deterministic PII layer (DPG-31).

**T-31-a is the single most important test in this sprint**: a phone number written in Devanagari
digits is detected. `९८४१२३४५६७` is a real Nepali phone number and an ASCII `\\d` pattern misses it
completely — a number sitting in plain text on its way to a third party, passing every test written
by an English speaker.

⚠ **Recall-first, by decision.** A missed name is a privacy breach; an over-redacted common noun is a
small classification cost. Where these tests choose, they choose the same way — and the false-positive
cases below pin the places where over-firing would actually hurt (a district the classifier needs).

⚠ **The output is pseudonymised, never "anonymised."** The mapping is kept, so the text remains
personal data. A test below greps this sprint's own documents for the wrong word, because that claim
is the one most likely to be repeated carelessly into a submission.

Spec: docs/sprints/2026-08-llm/04-pii-redaction-spec.md §DPG-31
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from backend.constants.nepali_pii_patterns import DEVANAGARI_TO_ASCII_DIGITS
from backend.services.pii_service import (
    ADDRESS,
    PERSON,
    PHONE,
    VEHICLE,
    find_pii,
    normalise_digits,
    redact_for_model,
    restore,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = REPO_ROOT / "tests/data/benchmark/general_classification.jsonl"


def _kinds(text: str) -> set[str]:
    return {s.kind for s in find_pii(text)}


# ═════════════════════════════════════════════════════════════════════════════
# T-31-a — Devanagari digits. The one that matters most.
# ═════════════════════════════════════════════════════════════════════════════


def test_a_devanagari_digit_phone_number_is_detected():
    """⭐ T-31-a. The defect this whole section exists for."""
    text = "सम्पर्क नम्बर ९८४१२३४५६७ मा फोन गर्नुहोस्"
    assert PHONE in _kinds(text), "a Devanagari-digit phone number was not detected"

    result = redact_for_model(text)
    assert "९८४१२३४५६७" not in result.text, "the number survived redaction"
    assert "<PHONE_1>" in result.text


def test_an_ascii_digit_phone_number_is_detected_too():
    """The obvious half — asserted so a fix for one script cannot silently break the other."""
    assert PHONE in _kinds("Contact 9812345678 for details")


def test_normalisation_is_length_preserving():
    """⚠ The property the offset arithmetic rests on.

    Offsets are computed on the normalised string and applied to the ORIGINAL. That is only sound
    while every mapping is one character to one character. This asserts it rather than trusting it —
    it stops being true the moment someone adds a multi-character entry to the table.
    """
    for original in ("०१२३४५६७८९", "९८४१२३४५६७", "मिश्रित ९८४ and 123", ""):
        assert len(normalise_digits(original)) == len(original)

    # ⚠ `str.maketrans` stores ORDINALS on both sides, so a multi-character replacement shows up
    # as a str value rather than an int. That is exactly the case that breaks offset alignment.
    assert all(
        isinstance(v, int) for v in DEVANAGARI_TO_ASCII_DIGITS.values()
    ), "a multi-character digit mapping would break offset alignment"


def test_normalisation_is_what_makes_devanagari_matching_work():
    """⚠ Pins the mechanism, because the obvious pin does not.

    A mutation that removes the Devanagari half of the numeric character class **survives** the rest
    of this file — and correctly so: `find_pii` normalises once, centrally, before any recogniser
    runs, so the dual-script class is redundant defence-in-depth rather than the working part. The
    class is kept (a future recogniser applied to un-normalised text would need it) but the honest
    statement is that **`normalise_digits` is what does the work**, and that is what this asserts.

    Recorded rather than counted as a kill — claiming one I did not get is how a ledger stops
    meaning anything (the T-23-b precedent).
    """
    text = "सम्पर्क नम्बर ९८४१२३४५६७"
    assert PHONE in _kinds(text)
    # The normalised form is what the pattern actually sees.
    assert "9841234567" in normalise_digits(text)
    assert "9841234567" not in text, "the original must be unchanged — only matching is normalised"


def test_offsets_from_the_normalised_string_land_correctly_on_the_original():
    """The end-to-end form of the same property: the span text matches the original, not the ASCII."""
    text = "फोन ९८४१२३४५६७ हो"
    spans = [s for s in find_pii(text) if s.kind == PHONE]
    assert spans, "no phone span found"
    span = spans[0]
    assert text[span.start : span.end] == span.text
    assert span.text == "९८४१२३४५६७", "the span carries the ASCII form, so offsets were misapplied"


# ═════════════════════════════════════════════════════════════════════════════
# T-31-b — the other recognisers
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Call +977 9841234567 now", PHONE),
        ("email me at ram.thapa@example.com", "EMAIL"),
        ("citizenship 12-01-75-01234", "ID_NUMBER"),
        ("His tipper ba 2 kha 1234 dumps spoil at night", VEHICLE),
    ],
)
def test_each_recogniser_fires(text: str, expected: str):
    assert expected in _kinds(text), f"{expected} not detected in {text!r}"


def test_the_vehicle_plate_matters_because_this_is_a_road_sector_grm():
    """§31.2 names this specifically, and it is not an afterthought.

    *"the contractor's tipper ba 2 kha 1234 dumps spoil at night"* identifies a vehicle, its owner,
    and often its driver.
    """
    result = redact_for_model("the contractor's tipper ba 2 kha 1234 dumps spoil at night")
    assert "ba 2 kha 1234" not in result.text


def test_a_devanagari_plate_is_detected_too():
    """Plates carry a Devanagari class token plus digits — the pattern needs §31.1 most of all."""
    assert VEHICLE in _kinds("ट्रक बा २ ख १२३४ राति ढुंगा फाल्छ")


# ═════════════════════════════════════════════════════════════════════════════
# T-31-c — person names, the three recognisers
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "text",
    [
        "Er. Rajesh Shrestha refused to come",           # honorific trigger
        "I spoke to the overseer Bikash Tamang",          # role-title trigger
        "My name is Hari Prasad Limbu",                   # self-identification
        "Mero naam Hari Prasad Limbu ho",                 # romanised self-identification
        "my neighbour Kamala Devi Chaudhary cannot read", # thar gazetteer, no trigger
        "मेरो नाम सीता कुमारी राई हो",                        # Devanagari self-identification
        "श्री रमेश अधिकारीले काम रोके",                        # Devanagari honorific
    ],
)
def test_person_names_are_detected(text: str):
    assert PERSON in _kinds(text), f"no person detected in {text!r}"


def test_the_named_official_is_the_case_that_matters_most():
    """§0: complaints naming officials are a large share of the useful ones, and that person never
    consented to anything. The honorific + role-title recogniser is aimed squarely at them."""
    result = redact_for_model("Er. Rajesh Shrestha and the overseer Bikash Tamang refused")
    assert "Rajesh Shrestha" not in result.text
    assert "Bikash Tamang" not in result.text


def test_a_title_alone_is_not_captured_as_a_name():
    """⚠ Regression: "The contractor Er. Rajesh Shrestha" captured `Er` as the name after
    `contractor`. Both tokens are titles; the name is further right."""
    result = redact_for_model("The contractor Er. Rajesh Shrestha refused")
    assert result.mapping, "nothing was detected at all"
    assert all(v.strip().rstrip(".") not in {"Er", "contractor"} for v in result.mapping.values())


def test_a_lowercase_verb_phrase_is_not_a_name():
    """⚠ Regression, and the reason case-insensitivity is scoped to the prefix.

    A blanket `re.IGNORECASE` made `[A-Z][a-z]+` match lowercase, so *"I am writing on behalf"*
    captured "writing on behalf" as a person.
    """
    result = redact_for_model("I am writing on behalf of my neighbour")
    assert "writing on behalf" not in result.mapping.values()


# ═════════════════════════════════════════════════════════════════════════════
# T-31-d — addresses, and the district that must survive
# ═════════════════════════════════════════════════════════════════════════════


def test_a_settlement_address_is_redacted():
    assert ADDRESS in _kinds("वडा नं ५ बुधबारे मा बस्छु")
    assert ADDRESS in _kinds("I live in ward 5 of Duhabi")


def test_a_bare_district_survives_because_the_classifier_needs_it():
    """⭐ §31.3, and the reason LOCATION is not blanket-redacted.

    A district name alone is not identifying, and the classifier derives district from the
    narrative. Redacting it would cost the signal and buy no privacy.
    """
    text = "Dust from the road works in Jhapa district is making my children sick"
    result = redact_for_model(text)
    assert "Jhapa" in result.text, "the district was redacted — the classifier needs it (§31.3)"


def test_an_address_span_stops_at_a_clause_boundary():
    """⚠ Regression: the Devanagari span ran past `।` into the next clause, over-redacting and
    round-tripping a sentence fragment."""
    text = "वडा नं ५ बुधबारे। सम्पर्क नम्बर ९८४१२३४५६७"
    result = redact_for_model(text)
    assert "सम्पर्क" in result.text, "the address span swallowed the following clause"


# ═════════════════════════════════════════════════════════════════════════════
# T-31-e — replacement semantics
# ═════════════════════════════════════════════════════════════════════════════


def test_the_same_value_gets_the_same_placeholder_within_a_document():
    """§31.3: fresh tokens per occurrence destroy the narrative structure the classifier uses."""
    text = "Er. Rajesh Shrestha promised to fix it, then Rajesh Shrestha refused to return."
    result = redact_for_model(text)
    assert result.text.count("<PERSON_1>") == 2, result.text
    assert "<PERSON_2>" not in result.text


def test_counters_are_per_document_not_process_global():
    """⚠ Two concurrent grievances must not share `<PERSON_1>`.

    A shared counter would make the mapping ambiguous and turn the placeholders into a
    cross-document correlation channel.
    """
    first = redact_for_model("Er. Rajesh Shrestha refused")
    second = redact_for_model("Er. Bikash Tamang refused")
    assert "<PERSON_1>" in first.text
    assert "<PERSON_1>" in second.text, "the counter leaked across documents"
    assert first.mapping["<PERSON_1>"] != second.mapping["<PERSON_1>"]


def test_placeholders_not_deletion():
    """The sentence keeps its shape, so the classifier still parses it."""
    result = redact_for_model("Er. Rajesh Shrestha refused to come")
    assert "<PERSON_1>" in result.text
    assert "refused to come" in result.text


def test_round_trip_is_lossless_for_text_containing_pii():
    text = "Mero naam Hari Prasad Limbu ho. Contact 9812345678. Ward 5, Duhabi."
    result = redact_for_model(text)
    assert restore(result.text, result.mapping) == text


def test_round_trip_is_lossless_for_text_containing_none():
    text = "Dust from the road works is making my children sick."
    result = redact_for_model(text)
    assert result.text == text
    assert result.mapping == {}
    assert restore(result.text, result.mapping) == text


def test_restore_handles_double_digit_tokens():
    """`<PERSON_10>` must not be corrupted by the substitution for `<PERSON_1>`."""
    mapping = {f"<PERSON_{i}>": f"Name{i}" for i in range(1, 12)}
    text = " ".join(mapping)
    assert restore(text, mapping) == " ".join(mapping[k] for k in mapping)


def test_the_result_repr_does_not_print_the_mapping():
    """⚠ A repr reaches logs and exception bodies without anyone choosing to put it there."""
    result = redact_for_model("Er. Rajesh Shrestha, 9812345678")
    assert "Rajesh" not in repr(result)
    assert "9812345678" not in repr(result)


# ═════════════════════════════════════════════════════════════════════════════
# Recall against the labelled benchmark spans — the measured number, not a vibe
# ═════════════════════════════════════════════════════════════════════════════


def _labelled_rows() -> list[dict]:
    return [
        row
        for row in (json.loads(line) for line in BENCHMARK.read_text(encoding="utf-8").splitlines())
        if row.get("pii")
    ]


def test_the_benchmark_actually_carries_labelled_spans():
    """Guards the vacuous pass: a recall test over zero rows is 100% and means nothing."""
    rows = _labelled_rows()
    assert len(rows) >= 5, f"only {len(rows)} labelled rows — the recall test below is near-vacuous"


def test_measured_recall_on_the_labelled_spans():
    """⭐ The number DPG-35 publishes, computed here so it cannot drift unnoticed.

    ⚠ The threshold is deliberately a FLOOR, not a target. It exists to catch a regression, not to
    certify the layer — the honest recall figure belongs in the DPG evidence pack with its method,
    and the residual is what must be disclosed, never an absence.
    """
    rows = _labelled_rows()
    total = 0
    found = 0
    missed: list[tuple[str, str, str]] = []

    for row in rows:
        redacted = redact_for_model(row["text"]).text
        for span in row["pii"]:
            total += 1
            if span["text"] not in redacted:
                found += 1
            else:
                missed.append((row["id"], span["type"], span["text"]))

    recall = found / total if total else 0.0
    assert total >= 10, f"only {total} labelled spans — too few to measure"
    assert recall >= 0.80, (
        f"deterministic recall {recall:.0%} ({found}/{total}) is below the 80% floor. "
        f"Missed: {missed}"
    )


def test_no_sprint_document_calls_the_output_anonymised():
    """⚠ The claim most likely to be repeated carelessly into a submission.

    The mapping is kept, so the text remains personal data. *Pseudonymised* is defensible and
    strong; *anonymised* will not survive scrutiny and would discredit the rest of the assessment.
    """
    targets = [
        REPO_ROOT / "backend/services/pii_service.py",
        REPO_ROOT / "docs/sprints/2026-08-llm/04-pii-redaction-spec.md",
        REPO_ROOT / "docs/dpg/pii-egress-inventory.md",
    ]
    # ⚠ Looks for the CLAIM, not the word. The word appears legitimately in three shapes that must
    # not trip this: the prohibition itself ("must not be called anonymised"), the name of the
    # separate DPG-32 anonymiser-service initiative, and prose contrasting the two terms. A plain
    # substring grep flagged all three on its first run — the markdown-grep trap in
    # `docs/dpg/HANDOVER.md` §6, one layer up.
    claim = re.compile(
        r"\b(?:is|are|been|fully|properly|now)\s+anonymi[sz]ed\b"
        r"|\banonymi[sz]ed\s+(?:text|data|grievance|grievances|output|narrative)\b",
        re.IGNORECASE,
    )
    negations = ("not ", "never ", "nobody ", "no document", "must not", "cannot", "rather than",
                 "instead of", "is not", "are not", "would not")
    offenders = []
    for path in targets:
        if not path.exists():
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not claim.search(line):
                continue
            low = line.lower()
            if any(n in low for n in negations):
                continue
            offenders.append(f"{path.name}:{i}: {line.strip()[:100]}")
    assert not offenders, (
        "output described as anonymised — the mapping is kept, so it is PSEUDONYMISED:\n"
        + "\n".join(offenders)
    )


# ═════════════════════════════════════════════════════════════════════════════
# The mapping is PII, and it must never travel with the text it dereferences
#
# ⚠ This is the clause the whole "only pseudonymised text crosses the border, and the
# re-identification key never leaves Nepal" claim rests on — and it is voided by a single
# careless `json.dumps`. Serialise the mapping into the same Celery payload, log line or
# cached blob as the redacted text and the argument collapses silently: the key travelled
# with the ciphertext.
# ═════════════════════════════════════════════════════════════════════════════


def test_the_result_is_not_json_serialisable_by_accident():
    """A dataclass, not a dict — so it cannot be `json.dumps`-ed into a payload without a decision.

    ⚠ This is a speed bump, not a wall, and is recorded as such: someone can still call
    `dataclasses.asdict`. What it prevents is the *accidental* case — a result object dropped into
    a task payload or a log line that happens to serialise whatever it is given.
    """
    import json as _json

    result = redact_for_model("Er. Rajesh Shrestha, 9812345678")
    with pytest.raises(TypeError):
        _json.dumps(result)


def test_redaction_does_not_log_the_mapping_or_the_originals(caplog):
    """The module logs counts and lengths, never values (rule 7.5)."""
    import logging

    text = "Er. Rajesh Shrestha, 9812345678, ward 5 Duhabi"
    with caplog.at_level(logging.DEBUG, logger="backend.services.pii_service"):
        result = redact_for_model(text)

    logged = " ".join(r.getMessage() for r in caplog.records)
    assert result.mapping, "nothing was detected, so this test proves nothing"
    for original in result.mapping.values():
        assert original not in logged, f"the original {original!r} reached the log"
    assert "9812345678" not in logged


def test_the_redacted_text_alone_cannot_be_reversed():
    """Without the mapping the placeholders are opaque — which is the property being claimed.

    If `restore` could recover anything from the text alone, "the key never leaves Nepal" would be
    a statement about nothing.
    """
    text = "Er. Rajesh Shrestha called from 9812345678"
    result = redact_for_model(text)

    assert restore(result.text, {}) == result.text
    assert "Rajesh" not in result.text
    assert "9812345678" not in result.text


# The callers that exist, and the recorded answer for each. ⚠ A new entry is not a formality:
# adding one means someone has decided that caller does not need the mapping across requests. If
# one ever does, §31.3's three constraints apply BEFORE it is added here (never in `ticketing.*`;
# same encryption, access control, audit and retention as the record it dereferences; a new leg on
# DPG-04's data-flow diagram).
KNOWN_CALLERS = {
    # DPG-33's two chokepoints. Both redact inside `call_llm` and discard the mapping in the same
    # frame — the output is never restored, because the STORED summary carries no names (owner,
    # 2026-08-27) and the complainant still sees their own words in `grievance_description`, which
    # is stored unredacted. So neither needs cross-request restore.
    "backend/services/llm_client.py",
    "ticketing/clients/llm_client.py",
}


def test_no_caller_needs_cross_request_restore_yet():
    """⚠ Acceptance item, recorded rather than assumed: is the mapping ever persisted?

    **Answer: no.** The two callers are DPG-33's chokepoints, and both discard the mapping in the
    frame that created it. Nothing restores, so nothing is persisted, so §31.3's constraints do not
    apply — and DPG-31's "the mapping is never persisted" holds by construction rather than by
    discipline.

    ⭐ **This test already earned its keep once.** It was written when there were no callers at all,
    and it went red the moment DPG-33 added two — forcing the question to be answered rather than
    inherited. It stays red for any caller not in `KNOWN_CALLERS`.
    """
    import shutil
    import subprocess

    if shutil.which("git") is None:
        pytest.skip("git unavailable — repository-hygiene check cannot run here (not a pass)")
    out = subprocess.run(
        ["git", "grep", "-l", "-E", r"redact_for_model|RedactionResult", "--", "backend/", "ticketing/"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    ).stdout.split()
    callers = {f for f in out if not f.endswith("pii_service.py")}
    unexpected = sorted(callers - KNOWN_CALLERS)
    assert not unexpected, (
        "pii_service has a NEW caller: " + ", ".join(unexpected) + ". Establish whether it needs "
        "restore() across requests. If it does, apply §31.3's three constraints BEFORE adding it "
        "to KNOWN_CALLERS — the mapping is a compact, high-value index of exactly the identifiers "
        "that were removed."
    )
