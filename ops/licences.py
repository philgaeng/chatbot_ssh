# SPDX-License-Identifier: Apache-2.0

"""
Licence classification for the ops dependency scan (DPG-02 / Q-06).

Pure logic, deliberately in its own module: `ops/security.py` imports redis, SQLAlchemy and the ops
models, so a test that reached the classifier through it could only run where the full ops stack is
installed. Splitting the decision from the I/O keeps it unit-testable anywhere — see
`tests/repo/test_licence_scan.py`, and `docs/engineering/02_python_services.md` §"entrypoints hold
no logic".

**What this is for.** DPG indicator 2 requires an approved open licence, and that is a claim about
the *whole dependency tree* which has to stay true as dependencies change. This classifier is the
thing that notices when it stops being true. It runs nightly (`ops/scheduler.py`), writes to
`ops.dependency_findings`, and is report-only — it never blocks a deploy.
"""
from __future__ import annotations

import re

# OSI-approved identifiers we expect in this tree. The point is NOT to encode the whole SPDX list —
# it is to make anything unfamiliar surface as a finding that a human then dispositions. A tight
# allowlist that occasionally flags a benign licence fails in the right direction; a permissive one
# that silently passes a proprietary licence does not.
#
# Deliberately ABSENT so they always surface: GPL and AGPL (strong copyleft — fine for a service
# behind a process boundary like Redis, not fine linked into this codebase), SSPL and RSAL (not
# OSI-approved at all), and anything unparseable.
OSI_LICENCE_TOKENS: tuple[str, ...] = (
    "MIT",
    "BSD",
    "APACHE",
    "ISC",
    "PSF",
    "PYTHON SOFTWARE FOUNDATION",
    "MPL",
    "MOZILLA PUBLIC LICENSE",
    "LGPL",
    "UNLICENSE",
    "ZLIB",
    "POSTGRESQL",
)

# Weak copyleft: OSI-approved and acceptable as an unmodified library dependency, but it carries
# conditions the others do not, so it is recorded at `warn` rather than passing silently. Today
# this covers psycopg2-binary (LGPL with a linking exception), jwcrypto, certifi and bidict.
COPYLEFT_TOKENS: tuple[str, ...] = ("LGPL", "MPL", "MOZILLA PUBLIC LICENSE")

# No licence at all. `UNLICENSED` is npm's marker for "no licence declared" and is the opposite of
# `Unlicense`, the public-domain dedication — one is a gap, the other is a grant. Do not merge them.
_ABSENT = {"UNKNOWN", "NONE", "UNLICENSED"}


def matches(text: str, tokens: tuple[str, ...]) -> bool:
    """Whole-word token match against an upper-cased licence string.

    ⚠ Substring matching is wrong here and it fails *silently*: `"PROPRIETARY LIMITED LICENSE"`
    contains `"MIT"`, so a naive `token in text` classifies a proprietary licence as OSI-approved
    and the nightly scan reports clean. Word boundaries keep `MIT-0` and `MIT License` matching
    while `LIMITED` does not. This is pinned by a test; do not "simplify" it back.
    """
    return any(re.search(rf"\b{re.escape(token)}\b", text) for token in tokens)


def classify_licence(licence: str) -> tuple[str, bool]:
    """Classify a licence string.

    Returns ``(severity, is_finding)`` where severity is ``info`` | ``warn`` | ``high``:

    * ``high``  — absent, unparseable, or not recognised as OSI-approved. **Blocks the indicator-2
      claim until dispositioned**, which is why an unfamiliar string lands here rather than passing.
    * ``warn``  — weak copyleft (LGPL, MPL). Acceptable as an unmodified library, worth recording.
    * ``info``  — permissive and OSI-approved; not recorded as a finding.
    """
    text = (licence or "").upper().strip()
    if not text or text in _ABSENT:
        return "high", True
    if matches(text, COPYLEFT_TOKENS):
        return "warn", True
    if matches(text, OSI_LICENCE_TOKENS):
        return "info", False
    return "high", True
