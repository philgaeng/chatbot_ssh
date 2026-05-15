import csv
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_SCRIPT_DIR))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.actions.utils.utterance_mapping_rasa import UTTERANCE_MAPPING

MAX_BUTTONS_PER_SET = 5

_OUTPUT_DIR = os.path.join(_SCRIPT_DIR, "new_mappings")
os.makedirs(_OUTPUT_DIR, exist_ok=True)
output_file = os.path.join(_OUTPUT_DIR, "buttons.csv")

header = ["form", "action"]
for set_idx in range(1, 4):
    header.append(f"button_set_{set_idx}")
    for btn_idx in range(1, MAX_BUTTONS_PER_SET + 1):
        header.extend([f"en_{set_idx}_{btn_idx}", f"ne_{set_idx}_{btn_idx}"])

with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(header)

    for form, actions in UTTERANCE_MAPPING.items():
        for action, content in actions.items():
            if not isinstance(content, dict):
                continue
            buttons = content.get("buttons", {})
            if not isinstance(buttons, dict):
                continue

            row = [form, action]
            for set_idx in range(1, 4):
                btn_set = buttons.get(set_idx) or buttons.get(str(set_idx))
                if btn_set is None:
                    row.extend([""] + [""] * (MAX_BUTTONS_PER_SET * 2))
                    continue
                if not isinstance(btn_set, dict):
                    row.extend([set_idx] + [""] * (MAX_BUTTONS_PER_SET * 2))
                    continue
                row.append(set_idx)
                en_buttons = btn_set.get("en", [])
                ne_buttons = btn_set.get("ne", [])
                for j in range(MAX_BUTTONS_PER_SET):
                    if j < len(en_buttons):
                        en_title = en_buttons[j].get("title", "")
                        ne_title = (
                            ne_buttons[j].get("title", "")
                            if j < len(ne_buttons)
                            else ""
                        )
                        row.extend([en_title, ne_title])
                    else:
                        row.extend(["", ""])

            if any(cell for cell in row[2:]):
                writer.writerow(row)

print(f"Buttons exported to {output_file}")
