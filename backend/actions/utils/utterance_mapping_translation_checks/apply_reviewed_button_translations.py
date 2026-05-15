#!/usr/bin/env python3
"""Apply reviewed Nepali button titles from buttons_*_translated.csv.

CSV layouts supported
---------------------
1. **Aligned headers** (preferred, after export fix):
   form, action, button_set_1, en_1_1, ne_1_1, en_1_2, ne_1_2, ...

2. **Legacy mislabeled headers** (old export — ignore header text, use positions):
   form, action, <set>, en, ne, en, ne, ...  (header row wrongly says en_1, ne_1, ...)

Locate rows with columns A=form, B=action, C=button set (legacy) or button_set_N blocks.
Nepali titles are always the *ne* values (second column of each en/ne pair).
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[3]
_RASA_PATH = _SCRIPT_DIR.parent / "utterance_mapping_rasa.py"
_BUTTONS_PATH = _SCRIPT_DIR.parent / "mapping_buttons.py"
_DEFAULT_CSV = _SCRIPT_DIR / "mapping_translated" / "buttons_260508_translated.csv"


@dataclass(frozen=True)
class ButtonTitleUpdate:
    form: str
    action: str
    button_set: int
    index: int
    en_title: str
    old_ne: str
    new_ne: str
    payload: str
    constant_name: str | None


def _parse_legacy_row(row: list[str]) -> tuple[str, str, list[tuple[int, list[tuple[str, str]]]]]:
    """form, action, then repeating: button_set, en, ne, en, ne, ..."""
    form, action = row[0], row[1]
    i = 2
    segments: list[tuple[int, list[tuple[str, str]]]] = []
    while i < len(row):
        while i < len(row) and not str(row[i]).strip():
            i += 1
        if i >= len(row):
            break
        btn_set = int(row[i])
        i += 1
        pairs: list[tuple[str, str]] = []
        while i < len(row):
            while i < len(row) and not str(row[i]).strip():
                i += 1
            if i >= len(row):
                break
            if str(row[i]).strip().isdigit() and int(row[i]) <= 20:
                nxt = i + 1
                while nxt < len(row) and not str(row[nxt]).strip():
                    nxt += 1
                if nxt < len(row) and not str(row[nxt]).strip().isdigit():
                    break
            if i + 1 >= len(row):
                break
            pairs.append((str(row[i]), str(row[i + 1])))
            i += 2
        segments.append((btn_set, pairs))
    return form, action, segments


def _parse_aligned_row(
    row: list[str], header: list[str]
) -> tuple[str, str, list[tuple[int, list[tuple[str, str]]]]]:
    form, action = row[0], row[1]
    col = {name: idx for idx, name in enumerate(header)}
    segments: list[tuple[int, list[tuple[str, str]]]] = []
    for set_idx in range(1, 4):
        set_key = f"button_set_{set_idx}"
        if set_key not in col or not str(row[col[set_key]]).strip():
            continue
        btn_set = int(row[col[set_key]])
        pairs: list[tuple[str, str]] = []
        for btn_idx in range(1, 6):
            en_key = f"en_{set_idx}_{btn_idx}"
            ne_key = f"ne_{set_idx}_{btn_idx}"
            if en_key not in col:
                break
            en_val = str(row[col[en_key]]) if col[en_key] < len(row) else ""
            ne_val = str(row[col[ne_key]]) if col[ne_key] < len(row) else ""
            if not en_val.strip() and not ne_val.strip():
                break
            pairs.append((en_val, ne_val))
        if pairs:
            segments.append((btn_set, pairs))
    return form, action, segments


def _detect_format(header: list[str]) -> str:
    if header and header[2].startswith("button_set_"):
        return "aligned"
    return "legacy"


def parse_button_row(row: list[str], header: list[str]) -> tuple[str, str, list[tuple[int, list[tuple[str, str]]]]]:
    if _detect_format(header) == "aligned":
        return _parse_aligned_row(row, header)
    return _parse_legacy_row(row)


def load_csv_updates(csv_path: Path) -> list[ButtonTitleUpdate]:
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    from backend.actions.utils.utterance_mapping_rasa import UTTERANCE_MAPPING
    import backend.actions.utils.mapping_buttons as mb

    updates: list[ButtonTitleUpdate] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if not row or row[0] == "form":
                continue
            form, action, segments = parse_button_row(row, header)
            try:
                buttons = UTTERANCE_MAPPING[form][action]["buttons"]
            except (KeyError, TypeError) as exc:
                raise KeyError(f"{form}/{action}: {exc}") from exc

            for btn_set, pairs in segments:
                ref = buttons.get(btn_set) or buttons.get(int(btn_set))
                if ref is None:
                    raise KeyError(f"{form}/{action}: missing button set {btn_set}")
                constant_name: str | None = None
                if isinstance(ref, str):
                    constant_name = ref
                    data = getattr(mb, ref)
                elif isinstance(ref, dict):
                    data = ref
                else:
                    raise TypeError(f"{form}/{action}/{btn_set}: unexpected {type(ref)}")

                en_list = data["en"]
                ne_list = data["ne"]
                for idx, (en_csv, ne_csv) in enumerate(pairs):
                    en_btn = en_list[idx]
                    ne_btn = ne_list[idx]
                    en_act = en_btn.get("title", "")
                    ne_act = ne_btn.get("title", "")
                    payload = ne_btn.get("payload", "")
                    if en_act.strip() != en_csv.strip():
                        raise ValueError(
                            f"{form}/{action}/{btn_set}[{idx}]: EN mismatch "
                            f"CSV en={en_csv!r} vs code={en_act!r}"
                        )
                    if ne_act.strip() == ne_csv.strip():
                        continue
                    updates.append(
                        ButtonTitleUpdate(
                            form=form,
                            action=action,
                            button_set=btn_set,
                            index=idx,
                            en_title=en_act,
                            old_ne=ne_act,
                            new_ne=ne_csv,
                            payload=payload,
                            constant_name=constant_name,
                        )
                    )
    return updates


def _format_title_literal(title: str) -> str:
    escaped = title.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _replace_title_in_source(
    source: str, old_ne: str, new_ne: str, payload: str
) -> tuple[str, bool]:
    if old_ne.strip() == new_ne.strip():
        return source, False
    payload_lit = re.escape(payload)
    old_lit = re.escape(old_ne)
    pattern = (
        rf'(\{{"title":\s*){old_lit}(\s*,\s*"payload":\s*{payload_lit}\s*\}})'
    )
    new_source, count = re.subn(
        pattern,
        lambda m: f'{m.group(1)}{_format_title_literal(new_ne)}{m.group(2)}',
        source,
        count=1,
    )
    return new_source, count == 1


def apply_updates(updates: list[ButtonTitleUpdate]) -> tuple[list[str], list[ButtonTitleUpdate]]:
    applied: list[str] = []
    failed: list[ButtonTitleUpdate] = []

    const_updates: dict[str, list[ButtonTitleUpdate]] = {}
    inline_updates: list[ButtonTitleUpdate] = []
    for u in updates:
        if u.constant_name:
            const_updates.setdefault(u.constant_name, []).append(u)
        else:
            inline_updates.append(u)

    buttons_source = _BUTTONS_PATH.read_text(encoding="utf-8")
    for const_name, group in const_updates.items():
        src = buttons_source
        for u in group:
            src, ok = _replace_title_in_source(src, u.old_ne, u.new_ne, u.payload)
            if ok:
                applied.append(f"{const_name} [{u.index}] ({u.form}/{u.action})")
            else:
                failed.append(u)
        buttons_source = src

    rasa_source = _RASA_PATH.read_text(encoding="utf-8")
    for u in inline_updates:
        rasa_source, ok = _replace_title_in_source(
            rasa_source, u.old_ne, u.new_ne, u.payload
        )
        if ok:
            applied.append(f"{u.form}/{u.action}/{u.button_set}[{u.index}]")
        else:
            failed.append(u)

    if applied:
        _BUTTONS_PATH.write_text(buttons_source, encoding="utf-8")
        _RASA_PATH.write_text(rasa_source, encoding="utf-8")

    return applied, failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=_DEFAULT_CSV)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        updates = load_csv_updates(args.csv)
    except (KeyError, ValueError, TypeError) as exc:
        print(f"ERROR loading CSV: {exc}")
        return 1

    print(f"Loaded {args.csv.name}")
    print(f"Button title changes needed: {len(updates)}")

    if not updates:
        print("Nothing to do — Nepali button titles already match the CSV.")
        return 0

    for u in updates[:10]:
        print(
            f"  {u.form}/{u.action} set {u.button_set}[{u.index}]: "
            f"{u.old_ne[:40]!r} -> {u.new_ne[:40]!r}"
        )
    if len(updates) > 10:
        print(f"  ... and {len(updates) - 10} more")

    if args.dry_run:
        return 0

    applied, failed = apply_updates(updates)
    print(f"Applied {len(applied)} title updates")
    if failed:
        print(f"WARNING: {len(failed)} replacements not found in source files")
        for u in failed[:10]:
            print(f"  {u.form}/{u.action} set {u.button_set}[{u.index}]")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
