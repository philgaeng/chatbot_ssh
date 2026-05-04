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
BUTTON_MAIN_MENU = "/nav_main_menu"
BUTTON_TRY_AGAIN = "/restart_story{\"restart_type\": \"story\"}"
BUTTON_EXIT = "/exit"

BUTTON_GOODBYE = "/nav_goodbye"
BUTTON_SELECTION_DONE = "/selection_done"

BUTTON_SKIP_EN = {"title": "Skip", "payload": BUTTON_SKIP}
BUTTON_SKIP_NE = {"title": "छोड्नुहोस्", "payload": BUTTON_SKIP}

BUTTONS_GOODBYE = {
    'en': [
        {"title": "Goodbye", "payload": BUTTON_GOODBYE}
    ],
    'ne': [
        {"title": "बाहिर निस्कनुहोस्", "payload": BUTTON_GOODBYE}
    ]
}

BUTTONS_MAIN_MENU = {
    'en': [
        {"title": "Main Menu", "payload": BUTTON_MAIN_MENU}
    ],
    'ne': [
        {"title": "मुख्य मेनुमा फर्कनुहोस्", "payload": BUTTON_MAIN_MENU}
    ]
}


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

BUTTONS_OTP_CONSENT = {
    'en': [
        {"title": "Validate with OTP", "payload": BUTTON_AFFIRM},
        {"title": "Skip OTP", "payload": BUTTON_DENY}
    ],
    'ne': [
        {"title": "OTP सत्यापन गर्नुहोस्", "payload": BUTTON_AFFIRM},
        {"title": "OTP छोड्नुहोस्", "payload": BUTTON_DENY}
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
        BUTTON_SKIP_EN
    ],
    'ne': [
        BUTTON_SKIP_NE
    ]
}

BUTTONS_CLEAN_WINDOW_OPTIONS = {
    'en': [
        {"title": "Close Browser", "payload": "/nav_close_browser_tab"},
        {"title": "Close Session", "payload": "/nav_clear"}
    ],
    'ne': [
        {"title": "ब्राउजर बन्द गर्नुहोस्", "payload": "/nav_close_browser_tab"},
        {"title": "सत्र बन्द गर्नुहोस्", "payload": "/nav_clear"}
    ]
}

# SEAH outro + submit-failure UX uses explicit close controls.
BUTTONS_SEAH_OUTRO = {
    "en": [
        *BUTTONS_CLEAN_WINDOW_OPTIONS["en"],
    ],
    "ne": [
        *BUTTONS_CLEAN_WINDOW_OPTIONS["ne"],
    ],
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
        {"title": "Change Phone", "payload": BUTTON_MODIFY_PHONE},
        {"title": "Skip", "payload": BUTTON_SKIP}
    ],
    'ne': [
        {"title": "पुनः पठाउनुहोस्", "payload": BUTTON_RESEND},
        {"title": "फोन परिवर्तन गर्नुहोस्", "payload": BUTTON_MODIFY_PHONE},
        {"title": "छोड्नुहोस्", "payload": BUTTON_SKIP}
    ]
}

BUTTONS_GRIEVANCE_SUBMISSION = {
    'en': [
        {"title": "File as is", "payload": BUTTON_SUBMIT_DETAILS},
        {"title": "Add more details", "payload": BUTTON_ADD_MORE_DETAILS},
        {"title": "Rewrite the summary", "payload": BUTTON_RESTART}
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

BUTTONS_SEAH_IDENTITY_MODE = {
    "en": [
        {"title": "Anonymous grievance", "payload": "/anonymous"},
        {"title": "Grievance with contact details", "payload": "/identified"},
    ],
    "ne": [
        {"title": "गुमनाम उजुरी", "payload": "/anonymous"},
        {"title": "सम्पर्क विवरण सहित उजुरी", "payload": "/identified"},
    ],
}

BUTTONS_SEAH_VICTIM_SURVIVOR_ROLE = {
    "en": [
        {"title": "SEAH focal-point", "payload": "/focal_point"},
        {"title": "Victim-Survivor", "payload": "/victim_survivor"},
        {"title": "Witness / Relative of the victim", "payload": "/not_victim_survivor"},
    ],
    "ne": [
        {"title": "SEAH फोकल-पोइन्ट", "payload": "/focal_point"},
        {"title": "पीडित/उत्तरजीवी", "payload": "/victim_survivor"},
        {"title": "साक्षी / पीडितको आफन्त", "payload": "/not_victim_survivor"},
    ],
}

BUTTONS_SEAH_PROJECT_IDENTIFICATION = {
    "en": [
        {"title": "Cannot specify", "payload": "/cannot_specify"},
        {"title": "Not an ADB project", "payload": "/not_adb_project"},
        {"title": "Skip", "payload": BUTTON_SKIP},
    ],
    "ne": [
        {"title": "उल्लेख गर्न सक्दिन", "payload": "/cannot_specify"},
        {"title": "यो ADB आयोजना होइन", "payload": "/not_adb_project"},
        {"title": "छोड्नुहोस्", "payload": BUTTON_SKIP},
    ],
}

BUTTONS_SEAH_CONTACT_CONSENT_CHANNEL = {
    "en": [
        {"title": "Phone only", "payload": "/phone"},
        {"title": "Email only", "payload": "/email"},
        {"title": "Both phone and email", "payload": "/both"},
        {"title": "No follow-up contact", "payload": "/none"},
    ],
    "ne": [
        {"title": "फोन मात्र", "payload": "/phone"},
        {"title": "इमेल मात्र", "payload": "/email"},
        {"title": "फोन र इमेल दुवै", "payload": "/both"},
        {"title": "फलो-अप सम्पर्क नगर्नुहोस्", "payload": "/none"},
    ],
}

BUTTONS_SEAH_YES_NO = {
    "en": [
        {"title": "Yes", "payload": "/yes"},
        {"title": "No", "payload": "/no"},
    ],
    "ne": [
        {"title": "हो", "payload": "/yes"},
        {"title": "होइन", "payload": "/no"},
    ],
}

BUTTONS_SEAH_FOCAL_LEARNED_WHEN = {
    "en": [
        {"title": "Within last 24h", "payload": "/learned_within_24h"},
        {"title": "24-72h ago", "payload": "/learned_24_to_72h"},
        {"title": "3-7 days ago", "payload": "/learned_3_to_7d"},
        {"title": "More than 7 days", "payload": "/learned_over_7d"},
    ],
    "ne": [
        {"title": "पछिल्लो २४ घण्टा", "payload": "/learned_within_24h"},
        {"title": "२४-७२ घण्टा अघि", "payload": "/learned_24_to_72h"},
        {"title": "३-७ दिन अघि", "payload": "/learned_3_to_7d"},
        {"title": "७ दिनभन्दा बढी अघि", "payload": "/learned_over_7d"},
    ],
}

BUTTONS_SEAH_FOCAL_SURVIVOR_RISKS = {
    "en": [
        {"title": "Retaliation, intimidation, or threat to job security", "payload": "/retaliation_threat"},
        {"title": "Personal safety", "payload": "/personal_safety"},
        {"title": "Trauma", "payload": "/trauma"},
        {"title": "Skip", "payload": BUTTON_SKIP},
    ],
    "ne": [
        {"title": "प्रतिशोध, धम्की वा रोजगारी सुरक्षामा खतरा", "payload": "/retaliation_threat"},
        {"title": "व्यक्तिगत सुरक्षा", "payload": "/personal_safety"},
        {"title": "आघात", "payload": "/trauma"},
        {"title": "छोड्नुहोस्", "payload": BUTTON_SKIP},
    ],
}

BUTTONS_SEAH_FOCAL_OTHER_AT_RISK_PARTIES = {
    "en": [
        {"title": "Witnesses", "payload": "/witnesses"},
        {"title": "Other family members", "payload": "/other_family_members"},
        {"title": "Other project workers", "payload": "/other_project_workers"},
        {"title": "Other members of the community", "payload": "/other_community_members"},
        {"title": "Skip", "payload": BUTTON_SKIP},
    ],
    "ne": [
        {"title": "प्रत्यक्षदर्शीहरू", "payload": "/witnesses"},
        {"title": "अन्य परिवारका सदस्यहरू", "payload": "/other_family_members"},
        {"title": "अन्य परियोजना कामदारहरू", "payload": "/other_project_workers"},
        {"title": "समुदायका अन्य सदस्यहरू", "payload": "/other_community_members"},
        {"title": "छोड्नुहोस्", "payload": BUTTON_SKIP},
    ],
}

BUTTONS_SEAH_FOCAL_PROJECT_RISK = {
    "en": [
        {"title": "Project delay", "payload": "/project_delay"},
        {"title": "Skip", "payload": BUTTON_SKIP},
    ],
    "ne": [
        {"title": "परियोजना ढिलाइ", "payload": "/project_delay"},
        {"title": "छोड्नुहोस्", "payload": BUTTON_SKIP},
    ],
}

BUTTONS_SEAH_FOCAL_MITIGATION_MEASURES = {
    "en": [
        {"title": "Referral to support services", "payload": "/referral_support_services"},
        {"title": "Provided information on police and/or legal services", "payload": "/police_legal_information"},
    ],
    "ne": [
        {"title": "सहायता सेवामा सन्दर्भ गरिएको", "payload": "/referral_support_services"},
        {"title": "प्रहरी वा कानुनी सेवाबारे जानकारी दिइयो", "payload": "/police_legal_information"},
    ],
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