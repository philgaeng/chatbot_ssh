# SPDX-License-Identifier: Apache-2.0

"""Deterministic PII detection and reversible pseudonymisation of grievance free text (DPG-31).

⚠ **This is pseudonymisation, not anonymisation, and the distinction is load-bearing.** Because the
mapping is kept, the output remains personal data under GDPR-style analysis and under Nepal's
Individual Privacy Act. **No document may describe this output as "anonymised."** What can be said,
accurately: *only pseudonymised text crosses the border, and the re-identification key never leaves
Nepal.* An overstatement here would discredit every other claim in the privacy assessment.

**No ML, and no new dependency.** Plain regex and curated token lists, so this ships without DPG-32
(the NER layer, moved to its own initiative). DPG-32 raises recall; it is not the whole control, and
this module is not a placeholder for it.

**Tuned for recall, deliberately.** A missed name is a privacy breach; an over-redacted common noun
is a small classification cost. Where a rule is ambiguous it fires. That is the same asymmetry the
SEAH detector is built on, for the same reason.

Public surface:
    redact_for_model(text)          -> RedactionResult(text, mapping)
    restore(text, mapping)          -> str
    normalise_digits(text)          -> str

⚠ **The mapping is itself PII** — a compact, high-value index of exactly the identifiers that were
removed. It must never travel with the text it dereferences: not in a Celery payload, a log line, an
exception body, a cached context blob, or a backup that ships offsite. `RedactionResult` is a
dataclass and not JSON-serialisable by accident, which is deliberate.

Spec: docs/sprints/2026-08-llm/04-pii-redaction-spec.md §DPG-31
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Iterable, Mapping

from backend.constants.nepali_pii_patterns import (
    DEVANAGARI_DIGIT_CLASS,
    DEVANAGARI_TO_ASCII_DIGITS,
    HONORIFICS_DEVANAGARI,
    HONORIFICS_ROMAN,
    ROLE_TITLES_DEVANAGARI,
    ROLE_TITLES_ROMAN,
    SELF_ID_PREFIXES_DEVANAGARI,
    SELF_ID_PREFIXES_ROMAN,
    SETTLEMENT_QUALIFIERS_DEVANAGARI,
    SETTLEMENT_QUALIFIERS_ROMAN,
    THAR_SURNAMES_DEVANAGARI,
    THAR_SURNAMES_ROMAN,
)

logger = logging.getLogger(__name__)

# Placeholder families. `<PERSON_1>` rather than deletion: the sentence keeps its grammatical shape,
# so the classifier still parses it. Deleting words degrades classification noticeably; substituting
# a token barely does (§31.3).
PERSON = "PERSON"
PHONE = "PHONE"
EMAIL = "EMAIL"
ADDRESS = "ADDRESS"
ID_NUMBER = "ID_NUMBER"
VEHICLE = "VEHICLE"


@dataclass(frozen=True)
class PiiSpan:
    """One detected span, in ORIGINAL-string offsets."""

    start: int
    end: int
    kind: str
    text: str


@dataclass
class RedactionResult:
    """Redacted text plus the mapping needed to reverse it.

    ⚠ `mapping` is PII. Keep it out of anything that travels with `text` — see the module docstring.
    """

    text: str
    mapping: dict[str, str] = field(default_factory=dict)

    def __repr__(self) -> str:  # pragma: no cover - defensive
        # ⚠ Deliberate: the default dataclass repr would print every original value, and a repr
        # reaches logs and exception bodies without anyone choosing to put it there.
        return f"RedactionResult(text_chars={len(self.text)}, mapping_entries={len(self.mapping)})"


# ═════════════════════════════════════════════════════════════════════════════
# Public surface
# ═════════════════════════════════════════════════════════════════════════════


def normalise_digits(text: str) -> str:
    """Devanagari digits → ASCII, 1:1 and length-preserving.

    ⚠ **Normalising for matching must not normalise what is sent.** Offsets are computed on the
    normalised string and applied to the *original*, which is only sound while the mapping is
    single-character → single-character. `test_normalisation_is_length_preserving` asserts it; the
    property stops holding the moment someone adds a multi-character entry.
    """
    return text.translate(DEVANAGARI_TO_ASCII_DIGITS)


def find_pii(text: str) -> list[PiiSpan]:
    """Every span this layer recognises, de-overlapped, in document order.

    Pure — no I/O, no session — so it is cheap to test and reusable from a Celery task or a script
    (`02_python_services.md` rule 3.8).
    """
    if not text:
        return []
    normalised = normalise_digits(text)
    spans: list[PiiSpan] = []
    for finder in (
        _find_emails,
        _find_phones,
        _find_id_numbers,
        _find_vehicles,
        _find_person_names,
        _find_addresses,
    ):
        spans.extend(finder(text, normalised))
    return _resolve_overlaps(spans)


def redact_for_model(text: str) -> RedactionResult:
    """Replace detected PII with stable per-document placeholders.

    **Consistent within a document**: the same value always gets the same token, so
    *"<PERSON_1> promised to fix it, then <PERSON_1> refused to return"* keeps the narrative
    structure the classifier actually uses. Fresh tokens per occurrence would destroy it.

    ⚠ **Per-document counters, never process-global.** Two concurrent grievances must not share
    `<PERSON_1>` — that would make the mapping ambiguous and the placeholders a cross-document
    correlation channel.
    """
    if not text:
        return RedactionResult(text=text or "", mapping={})

    spans = find_pii(text)
    if not spans:
        return RedactionResult(text=text, mapping={})

    counters: dict[str, int] = {}
    seen: dict[tuple[str, str], str] = {}
    mapping: dict[str, str] = {}
    out: list[str] = []
    cursor = 0

    for span in spans:
        key = (span.kind, span.text.strip().casefold())
        token = seen.get(key)
        if token is None:
            counters[span.kind] = counters.get(span.kind, 0) + 1
            token = f"<{span.kind}_{counters[span.kind]}>"
            seen[key] = token
            mapping[token] = span.text
        out.append(text[cursor : span.start])
        out.append(token)
        cursor = span.end

    out.append(text[cursor:])
    redacted = "".join(out)

    # Identifiers and counts only — never the values (rule 7.5).
    logger.info(
        "redact_for_model: %d span(s) replaced, %d distinct placeholder(s), %d chars in / %d out",
        len(spans),
        len(mapping),
        len(text),
        len(redacted),
    )
    return RedactionResult(text=redacted, mapping=mapping)


def restore(text: str, mapping: Mapping[str, str]) -> str:
    """Put the originals back. Inverse of `redact_for_model` for text it produced.

    Longest token first, so `<PERSON_10>` is not corrupted by the substitution for `<PERSON_1>`.
    """
    if not text or not mapping:
        return text
    for token in sorted(mapping, key=len, reverse=True):
        text = text.replace(token, mapping[token])
    return text


# ═════════════════════════════════════════════════════════════════════════════
# Recognisers — private below the public surface (rule 3.4)
# ═════════════════════════════════════════════════════════════════════════════

_D = DEVANAGARI_DIGIT_CLASS
_ANY_DIGIT = rf"[0-9{_D}]"

# ⚠ Every numeric pattern matches BOTH digit systems. A `\d`-only pattern is the defect §31.1 exists
# for: a Nepali user types ९८४१२३४५६७ and an English-authored test never notices.
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")

# +977, then 10-digit mobiles on 97x/98x, then landlines with an area code. Ordered longest-first so
# a country code is not left stranded outside the span.
_PHONE_RES = (
    re.compile(rf"\+\s?977[\s-]?{_ANY_DIGIT}{{6,10}}"),
    re.compile(rf"\b9[78]{_ANY_DIGIT}{{8}}\b"),
    re.compile(rf"\b0\d{{1,2}}[\s-]?{_ANY_DIGIT}{{6,7}}\b"),
)

# Citizenship certificate numbers: district-issued, conventionally `NN-NN-NN-NNNNN` with separators
# that vary in practice. Kept loose on separators and anchored on the shape.
_CITIZENSHIP_RE = re.compile(
    rf"\b{_ANY_DIGIT}{{2,3}}[-/]{_ANY_DIGIT}{{2,3}}[-/]{_ANY_DIGIT}{{2,3}}[-/]{_ANY_DIGIT}{{3,6}}\b"
)

# Nepali vehicle plates: a zone/province token then a Devanagari class letter then digits — e.g.
# "ba 2 kha 1234", "बा २ ख १२३४". §31.2 calls this out specifically: in a ROAD-SECTOR GRM a plate
# identifies a vehicle, its owner and often its driver, and it needs the digit normalisation more
# than any other pattern here.
_VEHICLE_ZONES = "ba|na|ga|ko|lu|me|pra|se|su|ja|bhe|ka|kha|ga|gha"
_VEHICLE_RES = (
    re.compile(
        rf"\b(?:{_VEHICLE_ZONES})\s*{_ANY_DIGIT}{{1,3}}\s*[a-z]{{1,3}}\s*{_ANY_DIGIT}{{1,4}}\b",
        re.IGNORECASE,
    ),
    # ⚠ `[क-ह]` is CONSONANTS ONLY (U+0915–U+0939). A real zone token is `बा` — ब plus the vowel
    # sign ा (U+093E) — so a consonant-only class never matched an actual plate. The full
    # Devanagari block is what this needs.
    re.compile(rf"[ऀ-ॿ]{{1,4}}\s*{_ANY_DIGIT}{{1,3}}\s*[ऀ-ॿ]{{1,4}}\s*{_ANY_DIGIT}{{3,4}}"),
)


def _find_emails(original: str, normalised: str) -> list[PiiSpan]:
    return [
        PiiSpan(m.start(), m.end(), EMAIL, original[m.start() : m.end()])
        for m in _EMAIL_RE.finditer(normalised)
    ]


def _find_phones(original: str, normalised: str) -> list[PiiSpan]:
    spans: list[PiiSpan] = []
    for pattern in _PHONE_RES:
        for m in pattern.finditer(normalised):
            spans.append(PiiSpan(m.start(), m.end(), PHONE, original[m.start() : m.end()]))
    return spans


def _find_id_numbers(original: str, normalised: str) -> list[PiiSpan]:
    return [
        PiiSpan(m.start(), m.end(), ID_NUMBER, original[m.start() : m.end()])
        for m in _CITIZENSHIP_RE.finditer(normalised)
    ]


def _find_vehicles(original: str, normalised: str) -> list[PiiSpan]:
    spans: list[PiiSpan] = []
    for pattern in _VEHICLE_RES:
        for m in pattern.finditer(normalised):
            spans.append(PiiSpan(m.start(), m.end(), VEHICLE, original[m.start() : m.end()]))
    return spans


# ── Person names (§31.2b), three recognisers in descending precision ─────────

_NAME_TOKEN = r"[A-Z][a-z]+|[ऀ-ॿ]+"
_TITLES = tuple(HONORIFICS_ROMAN) + tuple(ROLE_TITLES_ROMAN)


def _find_person_names(original: str, normalised: str) -> list[PiiSpan]:
    """Title triggers, then the thar gazetteer, then self-identification.

    ⚠ **Given-name matching is deliberately absent.** Many Nepali given names double as common nouns
    — *Bahadur* (brave), *Maya* (affection), *Laxmi*, *Kumar* — so a given-name gazetteer alone
    over-fires on ordinary sentences. Given names are only ever captured by *extending* a match that
    a title or a surname already anchored.
    """
    spans: list[PiiSpan] = []
    spans.extend(_names_after_titles(original))
    spans.extend(_names_around_surnames(original))
    spans.extend(_names_after_self_id(original))
    return [s for s in spans if not _is_only_a_title(s.text)]


_TITLE_WORDS = {w.casefold().rstrip(".") for w in _TITLES + HONORIFICS_DEVANAGARI + ROLE_TITLES_DEVANAGARI}


def _is_only_a_title(candidate: str) -> bool:
    """A captured span that is nothing but a title is not a name.

    ⚠ Real case: *"The contractor Er. Rajesh Shrestha"* — `contractor` is a role title, so the
    recogniser captured `Er` as the name that follows it. Both tokens are titles; the name is
    further right, and the surname recogniser finds it.
    """
    words = [w for w in re.split(r"[\s.]+", candidate.strip()) if w]
    return bool(words) and all(w.casefold() in _TITLE_WORDS for w in words)


def _names_after_titles(text: str) -> list[PiiSpan]:
    spans: list[PiiSpan] = []
    roman = "|".join(re.escape(t) for t in _TITLES)
    # ⚠ The case-insensitivity is SCOPED to the title, not the whole pattern. A blanket
    # `re.IGNORECASE` makes `[A-Z][a-z]+` match lowercase, so "i am writing on behalf" captured
    # "writing on behalf" as a person name. Capitalisation is the signal here; do not widen it.
    pattern = re.compile(
        rf"\b(?i:{roman})\.?\s+((?:{_NAME_TOKEN})(?:\s+(?:{_NAME_TOKEN})){{0,2}})"
    )
    for m in pattern.finditer(text):
        spans.append(PiiSpan(m.start(1), m.end(1), PERSON, m.group(1)))

    dev_titles = "|".join(re.escape(t) for t in HONORIFICS_DEVANAGARI + ROLE_TITLES_DEVANAGARI)
    dev = re.compile(rf"(?:{dev_titles})\s+([ऀ-ॿ]+(?:\s+[ऀ-ॿ]+){{0,2}})")
    for m in dev.finditer(text):
        spans.append(PiiSpan(m.start(1), m.end(1), PERSON, m.group(1)))
    return spans


def _names_around_surnames(text: str) -> list[PiiSpan]:
    """A surname hit is high precision, and it licenses taking the tokens before it as given names."""
    spans: list[PiiSpan] = []
    roman = "|".join(re.escape(s) for s in THAR_SURNAMES_ROMAN)
    pattern = re.compile(rf"((?:[A-Z][a-z]+\s+){{0,2}}(?:{roman}))\b")
    for m in pattern.finditer(text):
        spans.append(PiiSpan(m.start(1), m.end(1), PERSON, m.group(1)))

    dev_surnames = "|".join(re.escape(s) for s in THAR_SURNAMES_DEVANAGARI)
    dev = re.compile(rf"((?:[ऀ-ॿ]+\s+){{0,2}}(?:{dev_surnames}))")
    for m in dev.finditer(text):
        spans.append(PiiSpan(m.start(1), m.end(1), PERSON, m.group(1)))
    return spans


def _names_after_self_id(text: str) -> list[PiiSpan]:
    """*"my name is X"*, `मेरो नाम X हो` — the opening line the voice channel guarantees."""
    spans: list[PiiSpan] = []
    roman = "|".join(re.escape(p.strip()) for p in SELF_ID_PREFIXES_ROMAN)
    # Same scoping as the title recogniser, and for the same reason.
    pattern = re.compile(
        rf"\b(?i:{roman})\s+((?:{_NAME_TOKEN})(?:\s+(?:{_NAME_TOKEN})){{0,2}})"
    )
    for m in pattern.finditer(text):
        spans.append(PiiSpan(m.start(1), m.end(1), PERSON, m.group(1)))

    dev = "|".join(re.escape(p.strip()) for p in SELF_ID_PREFIXES_DEVANAGARI)
    dev_re = re.compile(rf"(?:{dev})\s+([ऀ-ॿ]+(?:\s+[ऀ-ॿ]+){{0,2}})")
    for m in dev_re.finditer(text):
        spans.append(PiiSpan(m.start(1), m.end(1), PERSON, m.group(1)))
    return spans


# ── Addresses (§31.2c) ───────────────────────────────────────────────────────


def _find_addresses(original: str, normalised: str) -> list[PiiSpan]:
    """Settlement-level spans only.

    ⚠ **District and province are deliberately left intact.** The classifier derives district from
    the narrative (§31.3), and a district name alone does not identify anyone — redacting it would
    cost the signal and buy no privacy. What is caught is the settlement qualifier and the tokens
    around it: ward numbers, tole, gaun, municipality, house numbers.
    """
    spans: list[PiiSpan] = []
    dev_q = "|".join(re.escape(q) for q in SETTLEMENT_QUALIFIERS_DEVANAGARI)
    # Bounded in TOKENS, not characters. The first version capped at 20 characters and required a
    # clause boundary in a lookahead — so a 21-character address simply never matched, while a
    # short one swallowed the following clause. Counting tokens gets both cases right, and a token
    # class of letters-and-digits stops naturally at the danda `।` or a comma.
    # ⚠ At least ONE token after the qualifier, not zero. A bare `वडा` on its own is the word
    # "ward", not an address, and redacting it would fire on ordinary sentences.
    _addr_token = rf"[ऀ-ॿ0-9{_D}]+"
    dev = re.compile(rf"((?:{dev_q})(?:\s+{_addr_token}){{1,3}})")
    for m in dev.finditer(normalised):
        # ⚠ Require a DIGIT inside the span. Devanagari has no capitalisation to lean on, so
        # without this the window greedily takes any three words after the qualifier and
        # "वडा मा धेरै धूलो" — *"a lot of dust in the ward"* — is redacted as an address, on
        # every dust complaint that mentions a ward. A ward number or house number is what makes
        # it an address; the bare noun is ordinary prose.
        #
        # ⚠ **The cost is stated rather than hidden**: an unnumbered settlement address like
        # `बुधबारे टोल` is missed. That is the same residual the benchmark already names (bare
        # settlement names), and it is the right side to err on — over-redacting the word "ward"
        # damages the classifier on the commonest grievance in the corpus.
        if not any(ch.isdigit() for ch in normalised[m.start(1) : m.end(1)]):
            continue
        spans.append(PiiSpan(m.start(1), m.end(1), ADDRESS, original[m.start(1) : m.end(1)]))

    roman_q = "|".join(re.escape(q) for q in SETTLEMENT_QUALIFIERS_ROMAN)
    # Case-insensitivity scoped to the qualifier: a blanket flag let `[A-Z][a-z]+` match "in",
    # so "I live in ward 5" captured "in ward 5".
    #
    # ⚠ **Two alternatives, each requiring something concrete after or before the qualifier.** The
    # first version allowed zero trailing digits, so the bare word `ward` matched — and
    # "making children in the ward sick" was redacted as an address. A qualifier alone is a common
    # noun; it becomes an address when it carries a NUMBER ("ward 5") or names a PLACE
    # ("Duhabi municipality). Recall-first does not mean redacting the word "ward".
    roman = re.compile(
        rf"\b((?:[A-Z][a-z]+\s+(?i:{roman_q}))"
        rf"|(?:(?i:{roman_q})\.?\s*(?:no\.?\s*)?{_ANY_DIGIT}{{1,4}}[A-Za-z]*))\b"
    )
    for m in roman.finditer(normalised):
        spans.append(PiiSpan(m.start(1), m.end(1), ADDRESS, original[m.start(1) : m.end(1)]))
    return spans


# ── Overlap resolution ───────────────────────────────────────────────────────


def _resolve_overlaps(spans: Iterable[PiiSpan]) -> list[PiiSpan]:
    """Longest span wins; ties break toward the earlier start.

    ⚠ Necessary because the recognisers deliberately overlap — a self-identification match and a
    surname match will both fire on *"Mero naam Hari Prasad Limbu ho"*, and emitting both would
    produce nested placeholders and a mapping that cannot round-trip.
    """
    ordered = sorted(spans, key=lambda s: (s.start, -(s.end - s.start)))
    kept: list[PiiSpan] = []
    for span in ordered:
        if span.end <= span.start:
            continue
        if kept and span.start < kept[-1].end:
            # Overlaps the last kept span — replace it only if this one is strictly longer.
            if (span.end - span.start) > (kept[-1].end - kept[-1].start):
                kept[-1] = span
            continue
        kept.append(span)
    return kept
