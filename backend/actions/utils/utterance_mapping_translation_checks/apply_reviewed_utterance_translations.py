#!/usr/bin/env python3
"""Apply team-reviewed Nepali utterances (column E) from mapped_translated xlsx."""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

import openpyxl

_SCRIPT_DIR = Path(__file__).resolve().parent
_RASA_PATH = _SCRIPT_DIR.parent / "utterance_mapping_rasa.py"
_DEFAULT_XLSX = (
    _SCRIPT_DIR
    / "mapping_translated"
    / "utterances_260508_mapped_translated.xlsx"
)

_SENSITIVE_ISSUES_ACTIONS = frozenset(
    {
        "action_ask_form_grievance_complainant_review_sensitive_issues_follow_up",
    }
)

_KEY_OPEN_RE = re.compile(r"""^['"]([^'"]+)['"]:\s*\{\s*$""")
_UTTERANCES_OPEN_RE = re.compile(r"""^['"]utterances['"]:\s*\{\s*$""")
_UTTER_NUM_RE = re.compile(r"^(\d+):\s*\{\s*$")
_NE_LINE_RE = re.compile(r"""^['"]ne['"]:\s*(.+?)\s*,?\s*$""")


def load_updates(xlsx_path: Path) -> dict[tuple[str, str, int], str]:
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.active
    updates: dict[tuple[str, str, int], str] = {}
    for row in range(2, ws.max_row + 1):
        if ws.cell(row, 6).value != "To update":
            continue
        ne_reviewed = ws.cell(row, 5).value
        if ne_reviewed is None or not str(ne_reviewed).strip():
            continue
        form = ws.cell(row, 1).value
        action = ws.cell(row, 2).value
        num = ws.cell(row, 3).value
        if not form or not action or num is None:
            continue
        updates[(str(form), str(action), int(num))] = str(ne_reviewed)
    wb.close()
    return updates


def _format_ne_literal(value: str) -> str:
    if "\n" in value:
        escaped = value.replace("\\", "\\\\")
        return f'"""{escaped}"""'
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _parse_ne_value(raw: str) -> str:
    node = ast.parse(f"x = {raw}", mode="exec")
    return node.body[0].value.value  # type: ignore[attr-defined]


def _resolve_target_action(action: str) -> str:
    if action in _SENSITIVE_ISSUES_ACTIONS:
        return "SENSITIVE_ISSUES_UTTERANCES_AND_BUTTONS"
    return action


def _try_apply_key(
    lines: list[str],
    key: tuple[str, str, int],
    new_ne: str,
    *,
    current_form: str | None,
    current_action: str | None,
    utterances_indent: int | None,
    current_utter_num: int | None,
    utter_block_indent: int | None,
    idx: int,
    line: str,
    stripped: str,
    indent: int,
) -> bool:
    """Replace ne on current line if key matches. Returns True if applied."""
    form, action, num = key
    target_action = _resolve_target_action(action)
    if current_form != form or current_action != target_action or current_utter_num != num:
        return False
    if utter_block_indent is None:
        return False
    if not (utter_block_indent <= indent <= utter_block_indent + 8):
        return False

    if stripped.startswith("'ne':") or stripped.startswith('"ne":'):
        if '"""' in stripped or "'''" in stripped:
            return False
        m = _NE_LINE_RE.match(stripped)
        if not m:
            return False
        old_raw = m.group(1).rstrip().rstrip(",")
    else:
        return False

    try:
        if _parse_ne_value(old_raw) == new_ne:
            return False
    except SyntaxError:
        return False

    lines[idx] = f"{line[:indent]}'ne': {_format_ne_literal(new_ne)},\n"
    return True


def apply_updates_to_source(
    source: str, updates: dict[tuple[str, str, int], str]
) -> tuple[str, list[str], list[str], list[tuple[str, str, int]]]:
    updates = dict(updates)
    lines = source.splitlines(keepends=True)
    applied: list[str] = []
    skipped: list[str] = []

    current_form: str | None = None
    current_action: str | None = None
    utterances_indent: int | None = None
    current_utter_num: int | None = None
    utter_block_indent: int | None = None

    def reset_action() -> None:
        nonlocal current_action, utterances_indent, current_utter_num, utter_block_indent
        current_action = None
        utterances_indent = None
        current_utter_num = None
        utter_block_indent = None

    def reset_utterances() -> None:
        nonlocal utterances_indent, current_utter_num, utter_block_indent
        utterances_indent = None
        current_utter_num = None
        utter_block_indent = None

    idx = 0
    while idx < len(lines):
        line = lines[idx]
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        if indent <= 4 and stripped.startswith("}"):
            current_form = None
            reset_action()
            idx += 1
            continue

        if _UTTERANCES_OPEN_RE.match(stripped):
            if current_action == "SENSITIVE_ISSUES_UTTERANCES_AND_BUTTONS":
                utterances_indent = indent
                current_utter_num = None
                utter_block_indent = None
            elif current_action:
                utterances_indent = indent
                current_utter_num = None
                utter_block_indent = None
            idx += 1
            continue

        if stripped.startswith("'profile_utterances':") or stripped.startswith(
            "'buttons':"
        ):
            reset_utterances()
            idx += 1
            continue

        m = _KEY_OPEN_RE.match(stripped)
        if m:
            name = m.group(1)
            if name not in ("utterances", "buttons", "profile_utterances"):
                if indent == 4:
                    current_form = name
                    reset_action()
                elif 4 < indent <= 12 and current_form:
                    if name == "SENSITIVE_ISSUES_UTTERANCES_AND_BUTTONS":
                        current_form = "__sensitive_issues__"
                        current_action = name
                        reset_utterances()
                    else:
                        current_action = name
                        reset_utterances()
            idx += 1
            continue

        m = _UTTER_NUM_RE.match(stripped)
        if (
            m
            and utterances_indent is not None
            and utterances_indent + 4 <= indent <= utterances_indent + 8
        ):
            current_utter_num = int(m.group(1))
            utter_block_indent = indent
            idx += 1
            continue

        if utter_block_indent is not None and indent < utter_block_indent:
            current_utter_num = None
            utter_block_indent = None

        if (
            (stripped.startswith("'ne':") or stripped.startswith('"ne":'))
            and '"""' in stripped
            and current_form
            and current_action
            and current_utter_num is not None
        ):
            form = current_form
            action_name = current_action
            if current_form == "__sensitive_issues__":
                for (f, a, n), val in list(updates.items()):
                    if _resolve_target_action(a) == action_name and n == current_utter_num:
                        form, action_name, num = f, a, n
                        new_ne = val
                        break
                else:
                    idx += 1
                    continue
            else:
                num = current_utter_num
                key = (form, action_name, num)
                if key not in updates:
                    # also try with original sensitive action keys
                    key = next(
                        (
                            k
                            for k in updates
                            if k[2] == num
                            and _resolve_target_action(k[1]) == action_name
                            and k[0] == form
                        ),
                        key,
                    )
                if key not in updates:
                    idx += 1
                    continue
                new_ne = updates[key]

            start = idx
            block = [line]
            idx += 1
            while idx < len(lines):
                block.append(lines[idx])
                if '"""' in lines[idx] and idx > start:
                    break
                idx += 1
            old_raw = "".join(block).split(":", 1)[1].strip().rstrip(",")
            try:
                if _parse_ne_value(old_raw) != new_ne:
                    prefix = line[:indent]
                    lines[start] = f"{prefix}'ne': {_format_ne_literal(new_ne)},\n"
                    for clear_i in range(start + 1, idx + 1):
                        lines[clear_i] = ""
                    applied.append(f"{form}/{action_name}/{num}")
                    updates.pop(key, None)
            except SyntaxError:
                skipped.append(f"{form}/{action_name}/{num}: multiline parse error")
            idx += 1
            continue

        for key, new_ne in list(updates.items()):
            if _try_apply_key(
                lines,
                key,
                new_ne,
                current_form=current_form,
                current_action=current_action,
                utterances_indent=utterances_indent,
                current_utter_num=current_utter_num,
                utter_block_indent=utter_block_indent,
                idx=idx,
                line=line,
                stripped=stripped,
                indent=indent,
            ):
                applied.append(f"{key[0]}/{key[1]}/{key[2]}")
                del updates[key]
                break

        idx += 1

    if updates:
        source = "".join(lines)
        source, fallback_applied, updates = apply_inline_fallback(source, updates)
        applied.extend(fallback_applied)
        lines = source.splitlines(keepends=True)

    return "".join(lines), applied, skipped, list(updates.keys())


def _load_mapping_ne(form: str, action: str, num: int) -> str:
    _REPO_ROOT = _SCRIPT_DIR.parents[3]
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    from backend.actions.utils.utterance_mapping_rasa import (
        SENSITIVE_ISSUES_UTTERANCES_AND_BUTTONS,
        UTTERANCE_MAPPING,
    )

    if action in _SENSITIVE_ISSUES_ACTIONS:
        return SENSITIVE_ISSUES_UTTERANCES_AND_BUTTONS["utterances"][num]["ne"]
    return UTTERANCE_MAPPING[form][action]["utterances"][num]["ne"]


def classify_remaining(
    updates: dict[tuple[str, str, int], str],
) -> tuple[list[tuple[str, str, int]], list[tuple[str, str, int]], list[tuple[str, str, int]]]:
    """Return (already_applied, needs_update, lookup_errors) for keys the parser missed."""
    already_applied: list[tuple[str, str, int]] = []
    needs_update: list[tuple[str, str, int]] = []
    lookup_errors: list[tuple[str, str, int]] = []

    for key, expected in updates.items():
        form, action, num = key
        try:
            actual = _load_mapping_ne(form, action, num)
        except (KeyError, TypeError, IndexError):
            lookup_errors.append(key)
            continue
        if actual.strip() == expected.strip():
            already_applied.append(key)
        else:
            needs_update.append(key)
    return already_applied, needs_update, lookup_errors


def apply_inline_fallback(
    source: str,
    updates: dict[tuple[str, str, int], str],
) -> tuple[str, list[str], dict[tuple[str, str, int], str]]:
    applied: list[str] = []
    remaining = dict(updates)
    for key, new_ne in list(remaining.items()):
        form, action, num = key
        target = _resolve_target_action(action)
        pattern = re.compile(
            rf"((?:'|\"){re.escape(target)}(?:'|\")\s*:\s*\{{[^{{}}]*?"
            rf"['\"]utterances['\"]\s*:\s*\{{{num}\s*:\s*\{{[^{{}}]*?"
            rf"['\"]en['\"]\s*:\s*[^,]+,\s*['\"]ne['\"]\s*:\s*)"
            rf"((?:\"\"\"[\s\S]*?\"\"\"|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'))(\s*\}})",
            re.DOTALL,
        )
        match = pattern.search(source)
        if not match:
            continue
        try:
            if _parse_ne_value(match.group(2)) == new_ne:
                del remaining[key]
                continue
        except SyntaxError:
            continue
        replacement = match.group(1) + _format_ne_literal(new_ne) + match.group(3)
        source = source[: match.start()] + replacement + source[match.end() :]
        applied.append(f"{form}/{action}/{num}")
        del remaining[key]
    return source, applied, remaining


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xlsx", type=Path, default=_DEFAULT_XLSX)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    all_updates = load_updates(args.xlsx)
    source = _RASA_PATH.read_text(encoding="utf-8")
    new_source, applied, skipped, parser_missed = apply_updates_to_source(
        source, all_updates
    )

    print(f"Loaded {len(all_updates)} 'To update' rows with reviewed Nepali")
    print(f"Would change (parser): {len(applied)}")
    if skipped:
        print(f"Skipped during parse: {len(skipped)}")

    if parser_missed:
        already_ok, still_need, lookup_errors = classify_remaining(
            {k: all_updates[k] for k in parser_missed}
        )
        if already_ok:
            print(f"Already match column E in mapping: {len(already_ok)}")
        if still_need:
            print(f"WARNING: still differ from column E: {len(still_need)}")
            for key in still_need[:15]:
                print(f"  {key}")
            if len(still_need) > 15:
                print(f"  ... and {len(still_need) - 15} more")
        if lookup_errors:
            print(f"WARNING: could not locate in mapping: {len(lookup_errors)}")
            for key in lookup_errors[:10]:
                print(f"  {key}")

    if args.dry_run:
        _, still_need, lookup_errors = classify_remaining(all_updates)
        if not applied and not still_need and not lookup_errors:
            print("Nothing to do — all reviewed translations are already in utterance_mapping_rasa.py.")
            return 0
        return 1 if still_need or lookup_errors else 0

    if not applied:
        _, still_need, lookup_errors = classify_remaining(all_updates)
        if not still_need and not lookup_errors:
            print("No changes to write (already up to date).")
            return 0
        print("No textual changes applied; re-run without --dry-run after fixing parser gaps.")
        return 1

    _RASA_PATH.write_text(new_source, encoding="utf-8")
    print(f"Wrote {_RASA_PATH}")
    _, still_need, lookup_errors = classify_remaining(all_updates)
    return 1 if still_need or lookup_errors else 0


if __name__ == "__main__":
    sys.exit(main())
