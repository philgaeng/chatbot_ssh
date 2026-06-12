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
_SENSITIVE_CONST_RE = re.compile(
    r"^SENSITIVE_ISSUES_UTTERANCES_AND_BUTTONS\s*=\s*\{", re.MULTILINE
)


def load_updates(xlsx_path: Path) -> dict[tuple[str, str, int], str]:
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.active
    updates: dict[tuple[str, str, int], str] = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or row[0] is None:
            continue
        if len(row) < 6 or row[5] != "To update":
            continue
        ne_reviewed = row[4]
        if ne_reviewed is None or not str(ne_reviewed).strip():
            continue
        form, action, num = row[0], row[1], row[2]
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


def _skip_string(source: str, index: int) -> int:
    quote = source[index]
    if source[index : index + 3] in ("'''", '"""'):
        triple = source[index : index + 3]
        end = source.find(triple, index + 3)
        return end + 3 if end >= 0 else len(source)
    index += 1
    while index < len(source):
        if source[index] == "\\":
            index += 2
            continue
        if source[index] == quote:
            return index + 1
        index += 1
    return len(source)


def _skip_paren(source: str, index: int) -> int:
    depth = 0
    while index < len(source):
        char = source[index]
        if char in ("'", '"'):
            index = _skip_string(source, index)
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return len(source)


def _brace_block(source: str, open_index: int) -> tuple[int, int]:
    depth = 0
    index = open_index
    while index < len(source):
        char = source[index]
        if char in ("'", '"'):
            index = _skip_string(source, index)
            continue
        if char == "(":
            index = _skip_paren(source, index)
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return open_index, index + 1
        index += 1
    raise ValueError(f"Unclosed '{{' at index {open_index}")


def _find_key_block(
    source: str, key: str, start: int = 0, end: int | None = None
) -> tuple[int, int] | None:
    end = end if end is not None else len(source)
    pattern = re.compile(rf"(['\"]){re.escape(key)}\1\s*:\s*\{{")
    match = pattern.search(source, start, end)
    if not match:
        return None
    return _brace_block(source, match.end() - 1)


def _find_utterances_block(source: str, action_block: tuple[int, int]) -> tuple[int, int] | None:
    action_start, action_end = action_block
    match = re.search(
        r"""['"]utterances['"]\s*:\s*\{""", source[action_start:action_end]
    )
    if not match:
        return None
    return _brace_block(source, action_start + match.end() - 1)


def _find_utterance_block(
    source: str, utterances_block: tuple[int, int], num: int
) -> tuple[int, int] | None:
    utterances_start, utterances_end = utterances_block
    region = source[utterances_start:utterances_end]
    for pattern in (rf"\{{{num}\s*:\s*\{{", rf"\b{num}\s*:\s*\{{"):
        match = re.search(pattern, region)
        if match:
            open_index = utterances_start + match.end() - 1
            return _brace_block(source, open_index)
    return None


def _find_ne_value_range(
    source: str, utterance_block: tuple[int, int]
) -> tuple[int, int, str] | None:
    block_start, block_end = utterance_block
    match = re.search(r"""['"]ne['"]\s*:\s*""", source[block_start:block_end])
    if not match:
        return None
    value_start = block_start + match.end()
    first = source[value_start]
    if first in ("'", '"'):
        value_end = _skip_string(source, value_start)
    elif first == "(":
        value_end = _skip_paren(source, value_start)
    else:
        return None
    return value_start, value_end, source[value_start:value_end]


def _replace_ne_value(source: str, value_start: int, value_end: int, new_ne: str) -> str:
    return source[:value_start] + _format_ne_literal(new_ne) + source[value_end:]


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

        if (
            (stripped.startswith("'ne':") or stripped.startswith('"ne":'))
            and "(" in stripped
            and current_form
            and current_action
            and current_utter_num is not None
            and utter_block_indent is not None
            and utter_block_indent <= indent <= utter_block_indent + 8
        ):
            form = current_form
            action_name = current_action
            num = current_utter_num
            key = (form, action_name, num)
            if current_form == "__sensitive_issues__":
                for (f, a, n), val in list(updates.items()):
                    if _resolve_target_action(a) == action_name and n == num:
                        key = (f, a, n)
                        new_ne = val
                        break
                else:
                    idx += 1
                    continue
            elif key not in updates:
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
            paren_depth = stripped.count("(") - stripped.count(")")
            while idx < len(lines) and paren_depth > 0:
                block.append(lines[idx])
                paren_depth += lines[idx].count("(") - lines[idx].count(")")
                idx += 1
            old_raw = "".join(block).split(":", 1)[1].strip().rstrip(",")
            try:
                if _parse_ne_value(old_raw) != new_ne:
                    prefix = line[:indent]
                    lines[start] = f"{prefix}'ne': {_format_ne_literal(new_ne)},\n"
                    for clear_i in range(start + 1, idx):
                        lines[clear_i] = ""
                    applied.append(f"{key[0]}/{key[1]}/{key[2]}")
                    updates.pop(key, None)
            except SyntaxError:
                skipped.append(f"{key[0]}/{key[1]}/{key[2]}: paren parse error")
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


def _locate_ne_range(
    source: str, form: str, action: str, num: int
) -> tuple[int, int, str] | None:
    if action in _SENSITIVE_ISSUES_ACTIONS:
        const_match = _SENSITIVE_CONST_RE.search(source)
        if not const_match:
            return None
        const_block = _brace_block(source, const_match.end() - 1)
        utterances_block = _find_utterances_block(source, const_block)
        if not utterances_block:
            return None
        utterance_block = _find_utterance_block(source, utterances_block, num)
        if not utterance_block:
            return None
        return _find_ne_value_range(source, utterance_block)

    form_block = _find_key_block(source, form)
    if not form_block:
        return None
    action_block = _find_key_block(source, action, form_block[0], form_block[1])
    if not action_block:
        return None
    utterances_block = _find_utterances_block(source, action_block)
    if not utterances_block:
        return None
    utterance_block = _find_utterance_block(source, utterances_block, num)
    if not utterance_block:
        return None
    return _find_ne_value_range(source, utterance_block)


def apply_inline_fallback(
    source: str,
    updates: dict[tuple[str, str, int], str],
) -> tuple[str, list[str], dict[tuple[str, str, int], str]]:
    applied: list[str] = []
    remaining = dict(updates)
    for key, new_ne in list(remaining.items()):
        form, action, num = key
        located = _locate_ne_range(source, form, action, num)
        if not located:
            continue
        value_start, value_end, old_raw = located
        try:
            if _parse_ne_value(old_raw) == new_ne:
                del remaining[key]
                continue
        except SyntaxError:
            continue
        source = _replace_ne_value(source, value_start, value_end, new_ne)
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
        if parser_missed:
            _, still_need, lookup_errors = classify_remaining(
                {k: all_updates[k] for k in parser_missed}
            )
        else:
            still_need, lookup_errors = [], []
        if not applied and not still_need and not lookup_errors:
            print("Nothing to do — all reviewed translations are already in utterance_mapping_rasa.py.")
            return 0
        if applied:
            print(f"Ready to apply {len(applied)} change(s) on write.")
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
