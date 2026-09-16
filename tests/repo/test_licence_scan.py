# SPDX-License-Identifier: Apache-2.0
"""
Licence-classifier pin (DPG-02 / Q-06).

The nightly `licence_scan` job is what keeps the DPG indicator-2 claim true as dependencies change.
Its whole value rests on one property: **an unrecognised licence must surface as a finding.** A
classifier that silently passes something proprietary reports a clean tree and is worse than no
scan at all, because it manufactures confidence.

`ops/licences.py` is imported directly — it has no redis or SQLAlchemy imports precisely so this
test runs anywhere, rather than being skipped wherever the full ops stack is not installed. A
compliance pin that skips is a compliance pin that does not exist.
"""
from __future__ import annotations

import pytest

from ops.licences import COPYLEFT_TOKENS, OSI_LICENCE_TOKENS, classify_licence, matches


@pytest.mark.parametrize(
    "licence",
    [
        "MIT",
        "MIT-0",
        "MIT License",
        "Apache-2.0",
        "Apache Software License",
        "BSD-3-Clause",
        "BSD License",
        "ISC License (ISCL)",
        "Python Software Foundation License",
        "The Unlicense (Unlicense)",
        "BSD-3-Clause AND TCL",
        "Apache-2.0 OR BSD-3-Clause",
    ],
)
def test_permissive_licences_are_not_findings(licence):
    """Real strings taken from this repo's own resolved tree — not invented examples."""
    severity, is_finding = classify_licence(licence)
    assert (severity, is_finding) == ("info", False), f"{licence!r} should pass silently"


@pytest.mark.parametrize(
    "licence",
    [
        "LGPL-3.0-or-later",                              # jwcrypto
        "GNU Library or Lesser General Public License (LGPL)",  # psycopg2-binary
        "Mozilla Public License 2.0 (MPL 2.0)",           # bidict, certifi
        "MPL-2.0 AND MIT",                                # tqdm
    ],
)
def test_weak_copyleft_is_recorded_but_not_fatal(licence):
    """LGPL/MPL are OSI-approved and fine as unmodified libraries — recorded, not alarmed."""
    assert classify_licence(licence) == ("warn", True)


@pytest.mark.parametrize(
    "licence",
    [
        "GPL-3.0",
        "AGPL-3.0",
        "SSPL-1.0",       # Redis 7.4+ / MongoDB — NOT OSI-approved
        "RSALv2",         # Redis Source Available Licence — NOT OSI-approved
        "Commercial - all rights reserved",
        "UNKNOWN",
        "UNLICENSED",     # npm's "no licence declared" — the opposite of `Unlicense`
        "",
        "   ",
    ],
)
def test_unapproved_or_absent_licences_are_high_findings(licence):
    """Strong copyleft, source-available, proprietary and absent all have to surface."""
    severity, is_finding = classify_licence(licence)
    assert is_finding is True, f"{licence!r} must surface as a finding"
    assert severity == "high", f"{licence!r} should be high, got {severity}"


def test_unlicensed_and_unlicense_are_not_confused():
    """One is a gap, the other is a public-domain grant. Merging them would hide a real finding.

    `UNLICENSED` is what npm reports for a package.json with no `license` field — which is exactly
    how `channels/ticketing-ui` reported before DPG-02 fixed it, while the repo root carried an
    Apache-2.0 LICENSE. That contradiction is the kind of thing this scan exists to catch.
    """
    assert classify_licence("UNLICENSED") == ("high", True)
    assert classify_licence("The Unlicense (Unlicense)") == ("info", False)


def test_substring_matching_would_pass_a_proprietary_licence():
    """⚠ The regression this pin exists for.

    `"PROPRIETARY LIMITED LICENSE"` contains the substring `MIT`. The first implementation used
    `token in text` and therefore classified it as OSI-approved — a proprietary dependency passing
    a compliance scan silently. Word boundaries fix it.

    Mutation check: change `matches()` back to `any(token in text for token in tokens)` and this
    goes red.
    """
    assert classify_licence("Proprietary Limited License") == ("high", True)
    assert not matches("PROPRIETARY LIMITED LICENSE", OSI_LICENCE_TOKENS)
    # ...while the licences that legitimately contain those tokens still match.
    assert matches("MIT-0", OSI_LICENCE_TOKENS)
    assert matches("LGPL-3.0-OR-LATER", COPYLEFT_TOKENS)


def test_copyleft_is_checked_before_the_permissive_allowlist():
    """`LGPL` appears in both token lists; order decides the answer.

    If the permissive check ran first, every LGPL package would classify as `info` and vanish from
    the findings table — the tree would look more permissive than it is.
    """
    assert "LGPL" in OSI_LICENCE_TOKENS and "LGPL" in COPYLEFT_TOKENS
    assert classify_licence("LGPL-3.0-or-later") == ("warn", True)


def test_token_lists_are_not_empty():
    """An empty allowlist would flag everything; an empty copyleft list would flag nothing."""
    assert len(OSI_LICENCE_TOKENS) >= 8
    assert len(COPYLEFT_TOKENS) >= 2
