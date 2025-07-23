"""
Utterance mapping dictionary for multilingual support (English and Nepali).
Structure:
{
    'form_name': {
        'action_name': {
            'utterances': {
                1: {'en': 'utterance1', 'ne': 'utterance1'},
                2: {'en': 'utterance2', 'ne': 'utterance2'},
                ...
            },
            'buttons': {
                1: BUTTONS_CONSTANT
            }
        }
    }
}
"""
from icecream import ic
# Button payload constants
BUTTON_AFFIRM = "/affirm"
BUTTON_DENY = "/deny"
BUTTON_SKIP = "/skip"
BUTTON_ANONYMOUS_WITH_PHONE = "/anonymous_with_phone"
BUTTON_RESEND = "/resend"
BUTTON_SUBMIT_DETAILS = "/submit_details"
BUTTON_ADD_MORE_DETAILS = "/add_more_details"
BUTTON_EXIT_WITHOUT_FILING = "/exit_without_filing"
BUTTON_SLOT_CONFIRMED = "/slot_confirmed"
BUTTON_SLOT_EDITED = "/slot_edited"
BUTTON_MODIFY_EMAIL = "/modify_email"
BUTTON_MODIFY_PHONE = "/modify_phone"
BUTTON_CANCEL_MODIFICATION = "/cancel_modification_contact"
BUTTON_RESTART = "/restart"
BUTTON_RESTART_PROCESS = "/restart_story{\"restart_type\": \"process\"}"
BUTTON_RESTART_STORY = "/restart_story{\"restart_type\": \"story\"}"
BUTTON_MAIN_MENU = "/main_menu"
BUTTON_TRY_AGAIN = "/restart_story{\"restart_type\": \"story\"}"
BUTTON_EXIT = "/exit"

# Button dictionary constants
BUTTONS_AFFIRM_DENY = {
    'en': [
        {"title": "Yes", "payload": BUTTON_AFFIRM},
        {"title": "No", "payload": BUTTON_DENY}
    ],
    'ne': [
        {"title": "हो", "payload": BUTTON_AFFIRM},
        {"title": "होइन", "payload": BUTTON_DENY}
    ]
}

BUTTONS_LANGUAGE_OPTIONS = {
    'en': [
        {"title": "Nepali / नेपाली", "payload": "/set_nepali"},
        {"title": "English / अंग्रेजी", "payload": "/set_english"}
    ],
    'ne': [
        {"title": "Nepali / नेपाली", "payload": "/set_nepali"},
        {"title": "English / अंग्रेजी", "payload": "/set_english"}
    ]
}

BUTTONS_SKIP = {
    'en': [
        {"title": "Skip", "payload": BUTTON_SKIP}
    ],
    'ne': [
        {"title": "छोड्नुहोस्", "payload": BUTTON_SKIP}
    ]
}

BUTTONS_CLEAN_WINDOW_OPTIONS = {
    'en': [
        {"title": "Close Browser", "payload": "/nav_close_browser_tab"},
        {"title": "Clear Session", "payload": "/nav_clear"}
    ],
    'ne': [
        {"title": "ब्राउजर बन्द गर्नुहोस्", "payload": "/nav_close_browser_tab"},
        {"title": "सत्र खाली गर्नुहोस्", "payload": "/nav_clear"}
    ]
}


BUTTONS_SLOT_SKIPPED = {
    'en': [
        {"title": "Skip", "payload": BUTTON_SKIP}
    ],
    'ne': [
        {"title": "छोड्नुहोस्", "payload": BUTTON_SKIP}
    ]
}

BUTTONS_CONTACT_CONSENT = {
    'en': [
        {"title": "Yes", "payload": BUTTON_AFFIRM},
        {"title": "Anonymous with phone", "payload": BUTTON_ANONYMOUS_WITH_PHONE},
        {"title": "No contact info", "payload": BUTTON_SKIP}
    ],
    'ne': [
        {"title": "हो", "payload": BUTTON_AFFIRM},
        {"title": "फोनसहित गुमनाम", "payload": BUTTON_ANONYMOUS_WITH_PHONE},
        {"title": "सम्पर्क जानकारी छैन", "payload": BUTTON_SKIP}
    ]
}

BUTTONS_PHONE_VALIDATION = {
    'en': [
        {"title": "Give Phone Number", "payload": BUTTON_AFFIRM},
        {"title": "File Grievance as is", "payload": BUTTON_DENY}
    ],
    'ne': [
        {"title": "फोन नम्बर दिनुहोस्", "payload": BUTTON_AFFIRM},
        {"title": "यसै रूपमा दर्ता गर्नुहोस्", "payload": BUTTON_DENY}
    ]
}

BUTTONS_OTP_VERIFICATION = {
    'en': [
        {"title": "Resend", "payload": BUTTON_RESEND},
        {"title": "Skip", "payload": BUTTON_SKIP}
    ],
    'ne': [
        {"title": "पुनः पठाउनुहोस्", "payload": BUTTON_RESEND},
        {"title": "छोड्नुहोस्", "payload": BUTTON_SKIP}
    ]
}

BUTTONS_GRIEVANCE_SUBMISSION = {
    'en': [
        {"title": "File as is", "payload": BUTTON_SUBMIT_DETAILS},
        {"title": "Add more details", "payload": BUTTON_ADD_MORE_DETAILS},
        {"title": "Restart the process", "payload": BUTTON_RESTART}
    ],
    'ne': [
        {"title": "यसै रूपमा दर्ता गर्नुहोस्", "payload": BUTTON_SUBMIT_DETAILS},
        {"title": "थप विवरण थप्नुहोस्", "payload": BUTTON_ADD_MORE_DETAILS},
        {"title": "प्रक्रिया पुनः सुरु गर्नुहोस्", "payload": BUTTON_RESTART}
    ]
}

BUTTONS_EMAIL_CONFIRMATION = {
    'en': [
        {"title": "Confirm Email", "payload": BUTTON_SLOT_CONFIRMED},
        {"title": "Try Different Email", "payload": BUTTON_SLOT_EDITED},
        {"title": "Skip Email", "payload": BUTTON_SKIP}
    ],
    'ne': [
        {"title": "इमेल पुष्टि गर्नुहोस्", "payload": BUTTON_SLOT_CONFIRMED},
        {"title": "अर्को इमेल प्रयास गर्नुहोस्", "payload": BUTTON_SLOT_EDITED},
        {"title": "इमेल छोड्नुहोस्", "payload": BUTTON_SKIP}
    ]
}

BUTTONS_CONTACT_MODIFICATION = {
    'en': [
        {"title": "Change Email ({current_email})", "payload": BUTTON_MODIFY_EMAIL},
        {"title": "Add Email", "payload": BUTTON_MODIFY_EMAIL},
        {"title": "Change Phone ({current_phone})", "payload": BUTTON_MODIFY_PHONE},
        {"title": "Add Phone", "payload": BUTTON_MODIFY_PHONE},
        {"title": "Cancel", "payload": BUTTON_CANCEL_MODIFICATION}
    ],
    'ne': [
        {"title": "इमेल परिवर्तन गर्नुहोस् ({current_email})", "payload": BUTTON_MODIFY_EMAIL},
        {"title": "इमेल थप्नुहोस्", "payload": BUTTON_MODIFY_EMAIL},
        {"title": "फोन परिवर्तन गर्नुहोस् ({current_phone})", "payload": BUTTON_MODIFY_PHONE},
        {"title": "फोन थप्नुहोस्", "payload": BUTTON_MODIFY_PHONE},
        {"title": "रद्द गर्नुहोस्", "payload": BUTTON_CANCEL_MODIFICATION}
    ]
}

BUTTONS_RESTART_OPTIONS = {
    'en': [
        {"title": "Restart the process", "payload": BUTTON_RESTART_PROCESS},
        {"title": "Restart the story", "payload": BUTTON_RESTART_STORY},
        {"title": "Go back to the main menu", "payload": BUTTON_MAIN_MENU}
    ],
    'ne': [
        {"title": "प्रक्रिया पुनः सुरु गर्नुहोस्", "payload": BUTTON_RESTART_PROCESS},
        {"title": "कथामा पुनः सुरु गर्नुहोस्", "payload": BUTTON_RESTART_STORY},
        {"title": "मुख्य मेनुमा फर्कनुहोस्", "payload": BUTTON_MAIN_MENU}
    ]
}



BUTTONS_FALLBACK = {
    'en': [
        {"title": "Try Again", "payload": BUTTON_TRY_AGAIN},
        {"title": "Restart the process", "payload": BUTTON_RESTART_PROCESS},
        {"title": "Restart the story", "payload": BUTTON_RESTART_STORY},
        {"title": "File Grievance as Is", "payload": BUTTON_SUBMIT_DETAILS},
        {"title": "Exit", "payload": BUTTON_EXIT}
    ],
    'ne': [
        {"title": "पुनः प्रयास गर्नुहोस्", "payload": BUTTON_TRY_AGAIN},
        {"title": "प्रक्रिया पुनः सुरु गर्नुहोस्", "payload": BUTTON_RESTART_PROCESS},
        {"title": "कथामा पुनः सुरु गर्नुहोस्", "payload": BUTTON_RESTART_STORY},
        {"title": "यसै रूपमा दर्ता गर्नुहोस्", "payload": BUTTON_SUBMIT_DETAILS},
        {"title": "बाहिर निस्कनुहोस्", "payload": BUTTON_EXIT}
    ]
}

BUTTONS_CHECK_STATUS = {
    'en': [
        {"title": "Check Status", "payload": "/check_status"},
        {"title": "Skip", "payload": BUTTON_SKIP},
    ],
    'ne': [
        {"title": "स्थिति जाँच गर्नुहोस्", "payload": "/check_status"},
        {"title": "छोड्नुहोस्", "payload": BUTTON_SKIP},
    ]
}


VALIDATION_SKIP = {"utterance":{
    "en" : "Did you want to skip this field? I matched '{matched_word}'",
    "ne" : "के तपाईं यो क्षेत्र छोड्न चाहनुहुन्छ? मैले '{matched_word}' मिलान गरेको छु।"
    },
    "buttons":{
        "en": [
            {"title": "Yes, skip it", "payload": "/affirm_skip"},
            {"title": "No, let me enter a value", "payload": "/deny_skip"}
        ],
        "ne": [
            {"title": "हो", "payload": "/affirm_skip"},
            {"title": "होइन", "payload": "/deny_skip"}
        ]
    }
}