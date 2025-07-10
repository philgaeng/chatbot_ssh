import csv
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utterance_mapping_rasa import UTTERANCE_MAPPING

output_file = 'utterances.csv'

with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['form', 'action', 'utterance_number', 'en', 'ne'])
    for form, actions in UTTERANCE_MAPPING.items():
        for action, content in actions.items():
            if not isinstance(content, dict):
                # Optionally print or log skipped actions
                # print(f"Skipped: {form} - {action} (content is not a dict)")
                continue
            utterances = content.get('utterances', {})
            for utter_num, utter in utterances.items():
                # Some utterances use string keys (e.g., 'grievance_id'), skip those for now
                if not isinstance(utter_num, int):
                    continue
                en = utter.get('en', '')
                ne = utter.get('ne', '')
                writer.writerow([form, action, utter_num, en, ne])
print(f'Utterances exported to {output_file}') 