import csv
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utterance_mapping_rasa import UTTERANCE_MAPPING

# Maximum number of buttons to support
MAX_BUTTONS = 5

# Create header row with dynamic columns
header = ['form', 'action']
for i in range(1, MAX_BUTTONS + 1):
    header.extend([f'en_{i}', f'ne_{i}'])

output_file = 'buttons.csv'

with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(header)
    
    for form, actions in UTTERANCE_MAPPING.items():
        for action, content in actions.items():
            if not isinstance(content, dict):
                # Optionally print or log skipped actions
                # print(f"Skipped: {form} - {action} (content is not a dict)")
                continue
            buttons = content.get('buttons', {})
            if not isinstance(buttons, dict):
                continue
                
            # Initialize row with form and action
            row = [form, action]
            
            numbers = buttons.keys()
            
            for i in numbers:
                row.append(i) # add the button number
                if type(buttons.get(i, {})) == dict:
                    en_buttons = buttons.get(i, {}).get('en', [])
                    ne_buttons = buttons.get(i, {}).get('ne', [])
                    for j in range(len(en_buttons)):
                        en_title = en_buttons[j].get('title', '') if j < len(en_buttons) else ''
                        ne_title = ne_buttons[j].get('title', '') if j < len(ne_buttons) else ''
                        row.extend([en_title, ne_title])
                else:
                    continue
            if len(row) > 4:
                writer.writerow(row)

print(f'Buttons exported to {output_file}') 