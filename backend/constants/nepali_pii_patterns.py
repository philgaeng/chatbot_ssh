# SPDX-License-Identifier: Apache-2.0

"""Nepali-specific token sets the deterministic PII layer matches against (DPG-31).

⚠ **This file is sensitive project data, not a publishable sample dataset.**

The `THAR_SURNAMES` list is the reason. **Nepali surnames carry caste and ethnicity**, so the list is
simultaneously the thing that makes the recogniser work and a compact index of ethnic markers. It is
here because redaction needs it; it must not be lifted into a README, an example notebook, or a
"sample data" directory, and it should not be extended casually — every addition is another name the
system will over-redact for everyone who shares it.

Kept in `constants/` per `docs/engineering/02_python_services.md` rule 7.3 (constants do not live at
the bottom of a service module), and kept separate from `pii_service.py` so the recogniser logic can
be read without scrolling past three hundred tokens.

Spec: docs/sprints/2026-08-llm/04-pii-redaction-spec.md §31.2b
"""
from __future__ import annotations

# ── Digits ───────────────────────────────────────────────────────────────────
# ⚠ 1:1 and length-preserving, deliberately. `pii_service` computes offsets on the normalised
# string and applies them to the original, which is only sound while every mapping is
# single-character → single-character. A test asserts it; do not add a multi-character entry.
DEVANAGARI_TO_ASCII_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

DEVANAGARI_DIGIT_CLASS = "०१२३४५६७८९"

# ── Honorifics and role titles (§31.2b, recogniser 1) ────────────────────────
# The token(s) after a title are almost always a name, and this is the *third-party official* case
# that carries the sharpest legal exposure: the engineer named in a complaint never consented to
# anything.
HONORIFICS_DEVANAGARI: tuple[str, ...] = (
    "श्री", "श्रीमती", "सुश्री", "डा.", "डाक्टर", "इन्जिनियर", "इञ्जिनियर",
)

# ⚠ `Er.` earns its place: it is the standard Nepali honorific for an engineer, and this is a
# road-works GRM. Dropping it because it looks unusual to an English reader would lose the single
# most common way a site engineer is named in these complaints.
HONORIFICS_ROMAN: tuple[str, ...] = (
    "Mr", "Mrs", "Ms", "Miss", "Dr", "Er", "Engineer", "Sir", "Madam", "Shri", "Shrimati",
)

# The domain's own titles. A complaint names people by role far more often than by honorific.
ROLE_TITLES_ROMAN: tuple[str, ...] = (
    "engineer", "sub-engineer", "sub engineer", "junior engineer", "JE", "overseer",
    "contractor", "supervisor", "ward chairperson", "chairperson", "chairman", "secretary",
    "ward secretary", "site engineer", "foreman",
)

ROLE_TITLES_DEVANAGARI: tuple[str, ...] = (
    "इन्जिनियर", "सब-इन्जिनियर", "ओभरसियर", "ठेकेदार", "सुपरभाइजर",
    "वडा अध्यक्ष", "अध्यक्ष", "सचिव", "नाइके",
)

# ── Family names (§31.2b, recogniser 2) ──────────────────────────────────────
# ⚠ SENSITIVE — see the module docstring. A surname hit is high precision *and* lets the recogniser
# take the adjacent token as the given name, which is why this list buys more than its length
# suggests.
THAR_SURNAMES_ROMAN: tuple[str, ...] = (
    "Shrestha", "Tamang", "Gurung", "Magar", "Rai", "Limbu", "Thapa", "Bhattarai",
    "Adhikari", "Poudel", "Paudel", "Karki", "Basnet", "Chaudhary", "Chaudhari", "Yadav",
    "Sah", "Shah", "Mandal", "Bhandari", "Dahal", "Khadka", "Pandey", "Sharma", "Acharya",
    "Ghimire", "Subedi", "Neupane", "Koirala", "Regmi", "Aryal", "Bhusal", "Lamichhane",
    "Maharjan", "Pradhan", "Joshi", "Rijal", "Sapkota", "Timilsina", "Baral", "Bista",
    "Giri", "Nepali", "Bishwakarma", "Pariyar", "Sunar", "Damai", "Sarki", "Tharu",
    "Rana", "Malla", "Katuwal", "Bogati", "Chettri", "Chhetri", "Kandel", "Marasini",
)

THAR_SURNAMES_DEVANAGARI: tuple[str, ...] = (
    "श्रेष्ठ", "तामाङ", "गुरुङ", "मगर", "राई", "लिम्बू", "थापा", "भट्टराई",
    "अधिकारी", "पौडेल", "कार्की", "बस्नेत", "चौधरी", "यादव", "साह", "मण्डल",
    "भण्डारी", "दाहाल", "खड्का", "पाण्डे", "शर्मा", "आचार्य", "घिमिरे", "सुवेदी",
    "न्यौपाने", "कोइराला", "रेग्मी", "अर्याल", "महर्जन", "प्रधान", "जोशी",
    "सापकोटा", "बराल", "बिष्ट", "गिरी", "विश्वकर्मा", "परियार", "क्षेत्री",
)

# ── Settlement qualifiers (§31.2c) ───────────────────────────────────────────
# A bare district is NOT identifying and the classifier needs it. A settlement-level address is a
# different object: these tokens are what mark one.
SETTLEMENT_QUALIFIERS_DEVANAGARI: tuple[str, ...] = (
    "गाउँ", "गाउं", "टोल", "वडा", "नगरपालिका", "गाउँपालिका", "महानगरपालिका",
    "उपमहानगरपालिका", "बस्ती", "चोक", "मार्ग", "घर नं", "घर नम्बर", "कित्ता",
)

SETTLEMENT_QUALIFIERS_ROMAN: tuple[str, ...] = (
    "gaun", "gaon", "tole", "tol", "ward", "nagarpalika", "gaunpalika",
    "municipality", "VDC", "basti", "chowk", "chok", "marg", "house no", "plot no",
)

# ⚠ Districts and provinces are DELIBERATELY absent from every list above. §31.3: the classifier
# derives district from the narrative, and a district name alone does not identify anyone. Adding
# them here would redact the signal the model needs and buy no privacy.

# ── Self-identification (§31.2b, recogniser 3) ───────────────────────────────
# Catches the opening line the voice channel guarantees — nobody speaking naturally observes the
# form's field boundaries.
SELF_ID_PREFIXES_ROMAN: tuple[str, ...] = (
    "my name is", "i am", "i'm", "this is", "mero naam", "mero nam", "ma ",
)

SELF_ID_PREFIXES_DEVANAGARI: tuple[str, ...] = (
    "मेरो नाम", "म ",
)
