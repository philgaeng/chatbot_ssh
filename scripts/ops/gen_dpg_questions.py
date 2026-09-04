#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate `docs/dpg/02_questions.md` from the questions embedded in `00_compliance_status.md`.

The questions live under the indicator they belong to, in the assessment, because that is where the
evidence for them is. This script extracts them so the consultant-facing list is *derived* rather
than a second hand-maintained copy — the same arrangement as `.env.example` and
`declared_env_vars()`, and for the same reason: two copies of one list is two reconciliation passes.

    python3 scripts/ops/gen_dpg_questions.py            # write 02_questions.md
    python3 scripts/ops/gen_dpg_questions.py --check    # exit 1 if it is out of date

`tests/repo/test_dpg_questions_generated.py` runs the second form, so drift fails the build rather
than being noticed later by a reader.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs" / "dpg" / "00_compliance_status.md"
TARGET = ROOT / "docs" / "dpg" / "02_questions.md"

SECTION = re.compile(r"^## (?:(\d+)\. )?(.+)$")
QUESTION = re.compile(r"^- \*\*(Q-(\d{2})-\d{2})\b")


def extract(text: str) -> list[tuple[str, str, list[str]]]:
    """Return [(section_heading, question_id, lines)] in document order."""
    section = ""
    section_no: str | None = None
    out: list[tuple[str, str, list[str]]] = []
    current: list[str] | None = None

    for line in text.splitlines():
        heading = SECTION.match(line)
        if heading:
            current = None
            section_no, title = heading.group(1), heading.group(2).strip()
            section = (
                f"Indicator {section_no} — {title}"
                if section_no and "Process" not in title
                else title
            )
            continue

        question = QUESTION.match(line)
        if question:
            qid, indicator = question.group(1), question.group(2)
            expected = section_no or ""
            # Process questions use Q-00-xx and live in the section that has no indicator number.
            ok = indicator == expected.zfill(2) or (
                indicator == "00" and "Process" in section
            )
            if not ok:
                raise SystemExit(
                    f"{SOURCE.name}: {qid} sits under '{section}'. "
                    f"A question's number is derived from its indicator — move the question or "
                    f"renumber it, do not let them disagree."
                )
            current = [line]
            out.append((section, qid, current))
            continue

        if current is not None:
            # A question bullet ends at the next top-level bullet, heading, or rule.
            if line.startswith("- ") or line.startswith("#") or line.startswith("---"):
                current = None
            else:
                current.append(line)

    return out


def source_as_of(text: str) -> str:
    """The `As of YYYY-MM-DD` date from the assessment.

    ⚠ **Derived, not generated at run time.** Stamping today's date would make this file change
    on every regeneration and turn the drift test into noise. The questions are exactly as fresh
    as the assessment they are extracted from, so that is the honest date to carry.
    """
    match = re.search(r"\*\*As of (\d{4}-\d{2}-\d{2})\*\*", text)
    return match.group(1) if match else "unknown"


def render(questions: list[tuple[str, str, list[str]]], as_of: str = "unknown") -> str:
    blocking = sum(1 for _, _, lines in questions if "🔴" in lines[0])
    parts = [
        "# Questions for the DPG consultant",
        "",
        # The status block every document in docs/dpg/ carries. It is emitted HERE rather than
        # hand-added to the output, because a header patched into a generated file is stripped by
        # the next regeneration — which is exactly what happened on 2026-09-04.
        "**Status:** evidence pack — cited by the DPG assessment.",
        f"**Last updated:** {as_of} · derived from `00_compliance_status.md`; regenerate rather than edit",
        "",
        "> ⚠ **Generated file — do not edit.** These questions live under the indicator they belong to",
        "> in [`00_compliance_status.md`](00_compliance_status.md), next to the evidence behind them.",
        "> This file is extracted from it by `scripts/ops/gen_dpg_questions.py`, and",
        "> `tests/repo/test_dpg_questions_generated.py` fails the build if the two disagree.",
        "> **To change a question, edit `00_compliance_status.md` and regenerate.**",
        ">",
        f"> **{len(questions)} questions**, of which **{blocking} are marked 🔴** — we cannot finish the",
        "> work without those.",
        ">",
        "> **Numbers are derived from structure**: `Q-04-02` is the second question about indicator 4,",
        "> and `Q-00-xx` are process questions belonging to no indicator. Inserting a question therefore",
        "> never renumbers another one.",
        ">",
        "> **These are deliberately short and open.** The evidence behind each sits in the section it was",
        "> extracted from. The judgement is yours — a question that arrived pre-argued would be asking you",
        "> to check our reasoning rather than to give us yours.",
        "",
        "---",
        "",
    ]

    section = None
    for title, _qid, lines in questions:
        if title != section:
            section = title
            parts.append(f"## {title}")
            parts.append("")
        parts.extend(line.rstrip() for line in lines)
        while parts and parts[-1] == "":
            parts.pop()
        parts.append("")

    return "\n".join(parts).rstrip() + "\n"


def main() -> int:
    source = SOURCE.read_text(encoding="utf-8")
    questions = extract(source)
    if not questions:
        raise SystemExit(f"{SOURCE.name}: no questions found — the extraction pattern has drifted.")

    rendered = render(questions, as_of=source_as_of(source))
    check = "--check" in sys.argv

    if check:
        existing = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
        if existing != rendered:
            print(
                f"{TARGET.relative_to(ROOT)} is out of date with {SOURCE.name}.\n"
                f"Regenerate it:  python3 scripts/ops/gen_dpg_questions.py",
                file=sys.stderr,
            )
            return 1
        print(f"{TARGET.name} is up to date ({len(questions)} questions).")
        return 0

    TARGET.write_text(rendered, encoding="utf-8")
    print(f"Wrote {TARGET.relative_to(ROOT)} — {len(questions)} questions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
