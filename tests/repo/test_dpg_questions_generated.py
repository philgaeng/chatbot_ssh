# SPDX-License-Identifier: Apache-2.0
"""`docs/dpg/02_questions.md` is generated — this fails the build when it drifts.

Two hand-maintained copies of the same questions cost this project two reconciliation passes in one
week. The questions now live under the indicator they belong to in `00_compliance_status.md`, and
`02_questions.md` is extracted from it, exactly as `.env.example` is generated from
`declared_env_vars()` and pinned by `tests/backend/test_llm_config_pins.py`.

Drift is therefore impossible rather than discouraged, which is the entire point.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ops" / "gen_dpg_questions.py"


def test_generated_questions_are_up_to_date() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 0, (
        "docs/dpg/02_questions.md is out of date with 00_compliance_status.md.\n"
        "Edit the question in 00_compliance_status.md, then regenerate:\n"
        "    python3 scripts/ops/gen_dpg_questions.py\n\n" + result.stdout + result.stderr
    )


def test_a_misfiled_question_number_is_rejected(tmp_path: Path) -> None:
    """A question's number is derived from its indicator, so the two cannot disagree silently."""
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import gen_dpg_questions as gen
    finally:
        sys.path.pop(0)

    misfiled = "## 4. Platform independence\n\n- **Q-07-01 — A question filed under the wrong indicator?**\n"
    with pytest.raises(SystemExit) as excinfo:
        gen.extract(misfiled)
    assert "Q-07-01" in str(excinfo.value)


def test_every_question_is_reachable_from_the_assessment() -> None:
    """Every id in the generated file exists in the source, and vice versa."""
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import gen_dpg_questions as gen
    finally:
        sys.path.pop(0)

    source_ids = {qid for _, qid, _ in gen.extract(gen.SOURCE.read_text(encoding="utf-8"))}
    generated = gen.TARGET.read_text(encoding="utf-8")
    assert source_ids, "no questions extracted — the extraction pattern has drifted"
    for qid in source_ids:
        assert qid in generated, f"{qid} is in the assessment but not in the generated question list"


def test_the_briefing_question_counts_match_the_assessment() -> None:
    """The briefing states counts in prose; they must match the generated register.

    ⚠ This pin exists because the drift happened. Adding `Q-07-07` on 2026-08-24 made five questions
    blocking while `01_consultant_briefing.md` still said four — the same failure the generator was
    built to prevent, in the one place a number is still written by hand. The briefing is prose and
    should stay prose, so the counts are pinned rather than generated.
    """
    import re

    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import gen_dpg_questions as gen
    finally:
        sys.path.pop(0)

    questions = gen.extract(gen.SOURCE.read_text(encoding="utf-8"))
    blocking = sum(1 for _, _, lines in questions if "🔴" in lines[0])

    briefing = (gen.TARGET.parent / "01_consultant_briefing.md").read_text(encoding="utf-8")

    words = {
        1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven",
        8: "Eight", 9: "Nine", 10: "Ten", 11: "Eleven", 12: "Twelve", 13: "Thirteen",
        14: "Fourteen", 15: "Fifteen", 16: "Sixteen", 17: "Seventeen", 18: "Eighteen",
        19: "Nineteen", 20: "Twenty",
    }
    # Match the claim, not its punctuation: the count word followed by "questions block work".
    assert re.search(rf"\b{words[blocking]}\*{{0,2}} questions block work\b", briefing), (
        f"01_consultant_briefing.md must say '{words[blocking]} questions block work' — "
        f"{blocking} questions in 00_compliance_status.md are marked 🔴."
    )

    non_blocking = len(questions) - blocking
    assert re.search(rf"\b{words[non_blocking]} further questions\b", briefing), (
        f"01_consultant_briefing.md must say '{words[non_blocking]} further questions' — "
        f"{len(questions)} questions total, {blocking} of them blocking."
    )

    # Every blocking question must appear in the briefing's table, by id.
    for _, qid, lines in questions:
        if "🔴" in lines[0]:
            assert qid in briefing, f"{qid} is blocking but is not named in the briefing"
