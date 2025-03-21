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
BUTTON_SLOT_SKIPPED = "/slot_skipped"
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
        {"title": "Nepali / नेपाली", "payload": "/nepali"},
        {"title": "English / अंग्रेजी", "payload": "/english"}
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

BUTTONS_SLOT_SKIPPED = {
    'en': [
        {"title": "Skip", "payload": BUTTON_SLOT_SKIPPED}
    ],
    'ne': [
        {"title": "छोड्नुहोस्", "payload": BUTTON_SLOT_SKIPPED}
    ]
}

BUTTONS_CONTACT_CONSENT = {
    'en': [
        {"title": "Yes", "payload": BUTTON_AFFIRM},
        {"title": "Anonymous with phone", "payload": BUTTON_ANONYMOUS_WITH_PHONE},
        {"title": "No contact info", "payload": BUTTON_SLOT_SKIPPED}
    ],
    'ne': [
        {"title": "हो", "payload": BUTTON_AFFIRM},
        {"title": "फोनसहित गुमनाम", "payload": BUTTON_ANONYMOUS_WITH_PHONE},
        {"title": "सम्पर्क जानकारी छैन", "payload": BUTTON_SLOT_SKIPPED}
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
        {"title": "Cancel filing", "payload": BUTTON_EXIT_WITHOUT_FILING}
    ],
    'ne': [
        {"title": "यसै रूपमा दर्ता गर्नुहोस्", "payload": BUTTON_SUBMIT_DETAILS},
        {"title": "थप विवरण थप्नुहोस्", "payload": BUTTON_ADD_MORE_DETAILS},
        {"title": "दर्ता रद्द गर्नुहोस्", "payload": BUTTON_EXIT_WITHOUT_FILING}
    ]
}

BUTTONS_EMAIL_CONFIRMATION = {
    'en': [
        {"title": "Confirm Email", "payload": BUTTON_SLOT_CONFIRMED},
        {"title": "Try Different Email", "payload": BUTTON_SLOT_EDITED},
        {"title": "Skip Email", "payload": BUTTON_SLOT_SKIPPED}
    ],
    'ne': [
        {"title": "इमेल पुष्टि गर्नुहोस्", "payload": BUTTON_SLOT_CONFIRMED},
        {"title": "अर्को इमेल प्रयास गर्नुहोस्", "payload": BUTTON_SLOT_EDITED},
        {"title": "इमेल छोड्नुहोस्", "payload": BUTTON_SLOT_SKIPPED}
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

UTTERANCE_MAPPING = {
    'location_form': {
        'action_ask_location_form_user_location_consent': {
            'utterances': {
                1: {
                    'en': "Do you want to provide the location details for your grievance. This is optional, your grievance can be filed without it.",
                    'ne': "के तपाईं आफ्नो गुनासोको लागि स्थान विवरण प्रदान गर्न चाहनुहुन्छ? यो वैकल्पिक हो, तपाईंको गुनासो यस बिना पनि दर्ता गर्न सक्नुहुन्छ।"
                }
            },
            'buttons': {
                1: BUTTONS_AFFIRM_DENY
            }
        },
        'action_ask_location_form_user_municipality_temp': {
            'utterances': {
                1: {
                    'en': "Please enter a valid municipality name in {district}, {province} (at least 3 characters) or Skip to skip",
                    'ne': "कृपया {district}, {province} मा वैध नगरपालिका नाम प्रविष्ट गर्नुहोस् (कम्तिमा 3 अक्षर) वा छोड्न स्किप गर्नुहोस्"
                }
            },
            'buttons': {
                1: BUTTONS_SKIP
            }
        },
        'action_ask_location_form_user_municipality_confirmed': {
            'utterances': {
                1: {
                    'en': "Is {validated_municipality} your correct municipality?",
                    'ne': "के {validated_municipality} तपाईंको सही नगरपालिका हो?"
                }
            },
            'buttons': {
                1: BUTTONS_AFFIRM_DENY
            }
        },
        'action_ask_location_form_user_village': {
            'utterances': {
                1: {
                    'en': "Please provide your village name or Skip to skip",
                    'ne': "कृपया आफ्नो गाउँको नाम प्रदान गर्नुहोस् वा छोड्न स्किप गर्नुहोस्"
                }
            },
            'buttons': {
                1: BUTTONS_SKIP
            }
        },
        'action_ask_location_form_user_address_temp': {
            'utterances': {
                1: {
                    'en': "Please provide your address or Skip to skip",
                    'ne': "कृपया आफ्नो ठेगाना प्रदान गर्नुहोस् वा छोड्न स्किप गर्नुहोस्"
                }
            },
            'buttons': {
                1: BUTTONS_SKIP
            }
        },
        'action_ask_location_form_user_address_confirmed': {
            'utterances': {
                1: {
                    'en': "Thank you for providing your location details:\n- Municipality: {municipality}\n- Village: {village}\n- Address: {address}\nIs this correct?",
                    'ne': "तपाईंको स्थान विवरण प्रदान गर्नुभएकोमा धन्यवाद:\n- नगरपालिका: {municipality}\n- गाउँ: {village}\n- ठेगाना: {address}\nके यो सही हो?"
                }
            },
            'buttons': {
                1: BUTTONS_AFFIRM_DENY
            }
        },
        'action_ask_location_form_user_province': {
            'utterances': {
                1: {
                    'en': "Please provide your province name or Skip",
                    'ne': "कृपया आफ्नो प्रदेशको नाम प्रदान गर्नुहोस् वा छोड्न स्किप गर्नुहोस्"
                }
            },
            'buttons': {
                1: BUTTONS_SKIP
            }
        },
        'action_ask_location_form_user_district': {
            'utterances': {
                1: {
                    'en': "Please provide your district name or Skip",
                    'ne': "कृपया आफ्नो जिल्लाको नाम प्रदान गर्नुहोस् वा छोड्न स्किप गर्नुहोस्"
                }
            },
            'buttons': {
                1: BUTTONS_SKIP
            }
        },
        'validate_user_province': {
            'utterances': {
                1: {
                    'en': "Please provide a valid province name, this is required to file your grievance",
                    'ne': "कृपया एक वैध प्रदेशको नाम प्रदान गर्नुहोस्, यो आपको ग्रेवियंसको फाइल गर्नको लागि आवश्यक छ"
                },
                2: {
                    'en': "We cannot match your entry {slot_value} to a valid province. Please try again",
                    'ne': "आपको प्रविष्टि {slot_value} एक वैध प्रदेशको मिल्न सकिन्छ। कृपया पुनरावर्तन गर्नुहोस्"
                },
                3: {
                    'en': "We have matched your entry {slot_value} to {result}.",
                    'ne': "हामीले तपाईंको प्रविष्टि {slot_value} लाई {result} सँग मिलान गरेका छौं।"
                }
            }
        },
        'validate_user_district': {
            'utterances': {
                1: {
                    'en': "Please provide a valid district name, this is required to file your grievance",
                    'ne': "कृपया एक वैध जिल्लाको नाम प्रदान गर्नुहोस्, यो आपको ग्रेवियंसको फाइल गर्नको लागि आवश्यक छ"
                },
                2: {
                    'en': "We cannot match your entry {slot_value} to a valid district. Please try again",
                    'ne': "आपको प्रविष्टि {slot_value} एक वैध जिल्लाको मिल्न सकिन्छ। कृपया पुनरावर्तन गर्नुहोस्"
                },
                3: {
                    'en': "We have matched your entry {slot_value} to {result}.",
                    'ne': "हामीले तपाईंको प्रविष्टि {slot_value} लाई {result} सँग मिलान गरेका छौं।"
                }
            }
        },
        'validate_user_village': {
            'utterances': {
                1: {
                    'en': "Please provide a valid village name (at least 3 characters) or type 'skip' to skip",
                    'ne': "कृपया एक वैध गाउँको नाम प्रदान गर्नुहोस् (कम्तिमा 3 अक्षर) वा छोड्न 'skip' टाइप गर्नुहोस्"
                }
            }
        },
        'validate_user_address_temp': {
            'utterances': {
                1: {
                    'en': "Please provide a valid address (at least 3 characters)",
                    'ne': "कृपया एक वैध ठेगाना प्रदान गर्नुहोस् (कम्तिमा 3 अक्षर)"
                }
            }
        }
    },
    'contact_form': {
        'action_ask_contact_form_user_contact_consent': {
            'utterances': {
                1: {
                    'en': "Would you like to provide your contact information? Here are your options:\n\n1️⃣ **Yes**: Share your contact details for follow-up and updates about your grievance.\n2️⃣ **Anonymous with phone number**: Stay anonymous but provide a phone number to receive your grievance ID.\n3️⃣ **No contact information**: File your grievance without providing contact details. Note that we won't be able to follow up or share your grievance ID.",
                    'ne': "के तपाईं आफ्नो सम्पर्क जानकारी प्रदान गर्न चाहनुहुन्छ? तपाईंका विकल्पहरू यहाँ छन्:\n\n1️⃣ **हो**: तपाईंको गुनासोको अनुवर्ती र अपडेटको लागि आफ्नो सम्पर्क विवरण साझेदारी गर्नुहोस्।\n2️⃣ **फोन नम्बरसहित गुमनाम**: गुमनाम रहनुहोस् तर तपाईंको गुनासो आईडी प्राप्त गर्न फोन नम्बर प्रदान गर्नुहोस्।\n3️⃣ **सम्पर्क जानकारी छैन**: सम्पर्क विवरण प्रदान नगरी आफ्नो गुनासो दर्ता गर्नुहोस्। ध्यान दिनुहोस् कि हामी अनुवर्ती गर्न वा तपाईंको गुनासो आईडी साझेदारी गर्न सक्षम हुने छैनौं।"
                }
            },
            'buttons': {
                1: BUTTONS_CONTACT_CONSENT
            }
        },
        'validate_user_full_name': {
            'utterances': {
                1: {
                    'en': "Please enter a valid full name (at least 3 characters)",
                    'ne': "कृपया मान्य पूरा नाम प्रविष्ट गर्नुहोस् (कम्तिमा 3 अक्षर)"
                }
            }
        },
        'validate_user_contact_phone': {
            'utterances': {
                1: {
                    'en': "Please enter a valid phone number (10 digits starting with 9)",
                    'ne': "कृपया मान्य फोन नम्बर प्रविष्ट गर्नुहोस् (9 बाट सुरु हुन्छ र 10 अंकको हुनुपर्छ)"
                }
            }
        },
        'validate_user_contact_email_temp': {
            'utterances': {
                1: {
                    'en': "⚠️ I couldn't find a valid email address in your message.\nA valid email should be in the format: **username@domain.com**.",
                    'ne': "⚠️ तपाईंको संदेशमा मान्य इमेल ठेगाना फेला पार्न सकिन्छ।\nएक वैध इमेल ठेगाना फॉर्मेट: **username@domain.com** हुनुपर्छ।"
                }
            }
        },
        'action_ask_contact_form_user_full_name': {
            'utterances': {
                1: {
                    'en': "Please enter your full name. You can skip this if you prefer to remain anonymous.",
                    'ne': "कृपया आफ्नो पूरा नाम प्रविष्ट गर्नुहोस्। यदि तपाईं गुमनाम रहन चाहनुहुन्छ भने यसलाई छोड्न सक्नुहुन्छ।"
                }
            },
            'buttons': {
                1: BUTTONS_SLOT_SKIPPED
            }
        },
        'action_ask_contact_form_user_contact_phone': {
            'utterances': {
                1: {
                    'en': "Please enter your contact phone number. Nepali phone number starts with 9 and should be 10 digits long. \nYou can skip this if you prefer to remain anonymous.",
                    'ne': "कृपया आफ्नो सम्पर्क फोन नम्बर प्रविष्ट गर्नुहोस्। नेपाली फोन नम्बर 9 बाट सुरु हुन्छ र 10 अंकको हुनुपर्छ।\nयदि तपाईं गुमनाम रहन चाहनुहुन्छ भने यसलाई छोड्न सक्नुहुन्छ।"
                }
            },
            'buttons': {
                1: BUTTONS_SLOT_SKIPPED
            }
        },
        'action_ask_contact_form_phone_validation_required': {
            'utterances': {
                1: {
                    'en': "Your grievance is filed without a validated number. Providing a valid number will help in the follow-up of the grievance and we recommend it. However, you can file the grievance as is.",
                    'ne': "तपाईंको गुनासो प्रमाणित नम्बर बिना दर्ता गरिएको छ। वैध नम्बर प्रदान गर्दै गुनासोको अनुवर्तीमा मद्दत पुग्छ र हामी यसलाई सिफारिस गर्दछौं। तथापि, तपाईं गुनासो यसै रूपमा दर्ता गर्न सक्नुहुन्छ।"
                }
            },
            'buttons': {
                1: BUTTONS_PHONE_VALIDATION
            }
        },
        'action_ask_contact_form_user_contact_email_temp': {
            'utterances': {
                1: {
                    'en': "Please enter your contact email. You can skip this if you prefer to remain anonymous.",
                    'ne': "कृपया आफ्नो सम्पर्क इमेल प्रविष्ट गर्नुहोस्। यदि तपाईं गुमनाम रहन चाहनुहुन्छ भने यसलाई छोड्न सक्नुहुन्छ।"
                }
            },
            'buttons': {
                1: BUTTONS_SLOT_SKIPPED
            }
        },
        'action_ask_contact_form_user_contact_email_confirmed': {
            'utterances': {
                1: {
                    'en': "⚠️ The email domain '{domain_name}' is not recognized as a common Nepali email provider.\nPlease confirm if this is correct or try again with a different email.",
                    'ne': "⚠️ इमेल डोमेन '{domain_name}' सामान्य नेपाली इमेल प्रदायकको रूपमा पहिचान गरिएको छैन।\nकृपया यो सही हो कि होइन पुष्टि गर्नुहोस् वा अर्को इमेलसँग पुनः प्रयास गर्नुहोस्।"
                }
            },
            'buttons': {
                1: BUTTONS_EMAIL_CONFIRMATION
            }
        },
        'action_modify_contact_info': {
            'utterances': {
                1: {
                    'en': "Which contact information would you like to modify?",
                    'ne': "तपाईं कुन सम्पर्क जानकारी परिवर्तन गर्न चाहनुहुन्छ?"
                }
            },
            'buttons': {
                1: BUTTONS_CONTACT_MODIFICATION
            }
        },
        'action_modify_email': {
            'utterances': {
                1: {
                    'en': "Please enter your new email address.",
                    'ne': "कृपया आफ्नो नयाँ इमेल ठेगाना प्रविष्ट गर्नुहोस्।"
                }
            }
        },
        'action_cancel_modification_contact': {
            'utterances': {
                1: {
                    'en': "✅ Modification cancelled. Your contact information remains unchanged.",
                    'ne': "✅ परिवर्तन रद्द गरिएको छ। तपाईंको सम्पर्क जानकारी परिवर्तन नभएको छ।"
                }
            }
        }
    },
    'otp_form': {
        'action_ask_otp_verification_form_otp_input': {
            'utterances': {
                1: {
                    'en': "-------- OTP verification ongoing --------\nPlease enter the 6-digit One Time Password (OTP) sent to your phone {phone_number} to verify your number.",
                    'ne': "-------- OTP प्रमाणीकरण जारी छ --------\nकृपया आफ्नो नम्बर प्रमाणित गर्न {phone_number} मा पठाइएको 6-अंकको वन टाइम पासवर्ड (OTP) प्रविष्ट गर्नुहोस्।"
                },
                2: {
                    'en': "❌ Maximum resend attempts reached. Please try again later or skip verification.",
                    'ne': "❌ अधिकतम पुनःपठाउने प्रयास पूरा भयो। कृपया पछि पुनः प्रयास गर्नुहोस् वा प्रमाणीकरण छोड्नुहोस्।"
                },
                3: {
                    'en': "❌ Invalid code. Please try again or type 'resend' to get a new code.",
                    'ne': "❌ अमान्य कोड। कृपया पुनः प्रयास गर्नुहोस् वा नयाँ कोड प्राप्त गर्न 'resend' टाइप गर्नुहोस्।"
                },
                4: {
                    'en': "Continuing without phone verification. Your grievance details will not be sent via SMS.",
                    'ne': "फोन प्रमाणीकरण बिना अगाडि बढ्दै। तपाईंको गुनासो विवरण SMS मार्फत पठाइने छैन।"
                }
            },
            'buttons': {
                1: BUTTONS_OTP_VERIFICATION
            }
        }
    },
    'grievance_form': {
        'action_start_grievance_process': {
            'utterances': {
                1: {
                    'en': "Great! Let's start by understanding your grievance...",
                    'ne': "राम्रो! चल्नुस् तपाईंको गुनासो बुझेर सुरु गरौं..."
                }
            }
        },
        'action_ask_grievance_details_form_grievance_temp': {
            'utterances': {
                1: {
                    'en': "Great! Let's start by understanding your grievance...",
                    'ne': "राम्रो! चल्नुस् तपाईंको गुनासो बुझेर सुरु गरौं..."
                },
                2: {
                    'en': "Please enter more details...",
                    'ne': "कृपया थप विवरण प्रविष्ट गर्नुहोस्..."
                },
                3: {
                    'en': "Calling OpenAI for classification... This may take a few seconds...",
                    'ne': "OpenAI क्लासिफिकेशनको लागि कल गर्दै... यसमा केही सेकेन्ड लाग्न सक्छ..."
                },
                4: {
                    'en': "Thank you for your entry. Do you want to add more details to your grievance, such as:\n"
                    "- Location information\n"
                    "- Persons involved\n"
                    "- Quantification of damages (e.g., number of bags of rice lost)\n"
                    "- Monetary value of damages",
                    'ne': "तपाईंको प्रविष्टिको लागि धन्यवाद। के तपाईं आफ्नो गुनासोको बारेमा थप विवरण गर्न चाहनुहुन्छ, जुन यस प्रकारको हुन्छ:\n"
                    "- स्थान जानकारी\n"
                    "- भागहरूको सम्बन्धमा\n"
                    "- हानिको मात्रात्मकको सम्बन्धमा (उदाहरणका लागि, गुनासोको बर्गहरूको संख्या)\n"
                    "- हानिको मुनाफा मूल्य"
                }
            },
            'buttons': {
                1: BUTTONS_GRIEVANCE_SUBMISSION
            }
        },
        'action_call_openai_for_classification': {
            'utterances': {
                1: {
                    'en': "There was an issue processing your grievance. Please try again.",
                    'ne': "तपाईंको गुनासोको प्रकार पत्ता लगाउन त्रुटि भयो। कृपया पुनः प्रयास गर्नुहोस्।"
                }
            },
            'buttons': {
                1: {'en': [
                    {"title": "Try again", "payload": "/start_grievance_process"},
                    {"title": "Exit", "payload": "/exit_without_filing"}
                ]
                ,
                'ne': [
                    {"title": "पुनःप्रयास गर्नुहोस्", "payload": "/start_grievance_process"},
                    {"title": "बाहिर निस्कनुहोस्", "payload": "/exit_without_filing"}
                ]
                }
            }
        },
        'action_submit_grievance': {
            'utterances': {
                1: {
                    'en': "Your grievance has been filed successfully.",
                    'ne': "तपाईंको गुनासो सफलतापूर्वक दर्ता गरिएको छ।"
                },
                2: {
                    'en': "✅ A recap of your grievance has been sent to your email.",
                    'ne': "✅ तपाईंको गुनासोको सारांश तपाईंको इमेलमा पठाइएको छ।"
                },
                3: {
                    'en': "I apologize, but there was an error submitting your grievance. Please try again or contact support.",
                    'ne': "मलाई माफ गर्नुहोस्, तर तपाईंको गुनासो दर्ता गर्दै गर्दा त्रुटि भयो। कृपया पुनः प्रयास गर्नुहोस् वा सहयोग सम्पर्क गर्नुहोस्।"
                }
            }
        },
        'action_submit_grievance_as_is': {
            'utterances': {
                1: {
                    'en': "Your grievance has been filed successfully.",
                    'ne': "तपाईंको गुनासो सफलतापूर्वक दर्ता गरिएको छ।"
                },
                2: {
                    'en': "✅ A recap of your grievance has been sent to your email.",
                    'ne': "✅ तपाईंको गुनासोको सारांश तपाईंको इमेलमा पठाइएको छ।"
                },
                3: {
                    'en': "I apologize, but there was an error submitting your grievance. Please try again or contact support.",
                    'ne': "मलाई माफ गर्नुहोस्, तर तपाईंको गुनासो दर्ता गर्दै गर्दा त्रुटि भयो। कृपया पुनः प्रयास गर्नुहोस् वा सहयोग सम्पर्क गर्नुहोस्।"
                }
            }
        },
        'action_ask_grievance_summary_form_grievance_list_cat_confirmed': {
            'utterances': {
                1: {
                    'en': "No categories have been identified yet.",
                    'ne': "कृपया आफ्नो गुनासोको लागि निम्न श्रेणीहरू समीक्षा गर्नुहोस्:"
                },
                2: {
                    'en': "Here are the suggested categories for your grievance:\n{category_text}\nDoes this seem correct?",
                    'ne': "तपाईंको गुनासोको लागि सुझाव गरिएका श्रेणीहरू यहाँ छन्:\n{category_text}\nके यो सही लाग्दैन?"
                }
            },
            'buttons': {
                1: {'en' :[
                    {"title": "Add category", "payload": "/add_category"},
                    {"title": "Continue without categories", "payload": "/slot_confirmed"}
                ],
                'ne': [
                    {"title": "श्रेणी थप्नुहोस्", "payload": "/add_category"},
                    {"title": "श्रेणी छोड्नुहोस्", "payload": "/slot_confirmed"}
                ]
            },
                2: {
                    'en': [
                        {"title": "Yes", "payload": "/slot_confirmed"},
                        {"title": "Add category", "payload": "/slot_added"},
                        {"title": "Delete category", "payload": "/slot_deleted"},
                        {"title": "Exit", "payload": "/skip"}
                    ],
                    'ne': [
                        {"title": "हो", "payload": "/slot_confirmed"},
                        {"title": "श्रेणी थप्नुहोस्", "payload": "/slot_added"},
                        {"title": "श्रेणी हटाउनुहोस्", "payload": "/slot_deleted"},
                        {"title": "बाहिर निस्कनुहोस्", "payload": "/skip"}
                    ]
                }
            }
        },
        'action_ask_grievance_summary_form_grievance_cat_modify': {
            'utterances': {
                1: {
                    'en': "No categories selected. Skipping this step.",
                    'ne': "कुनै श्रेणी चयन गरिएको छैन। यस चरण छोड्नुहोस्।"
                },
                2: {
                    'en': "Which category would you like to delete?",
                    'ne': "तपाईं कुन श्रेणी हटाउन चाहनुहुन्छ?"
                },
                3: {
                    'en': "Select the category you want to add from the list below:",
                    'ne': "निम्न सूचीमा तपाईं थप्न चाहनुहुन्छ श्रेणी चयन गर्नुहोस्:"
                }
            }
        },
        'action_ask_grievance_summary_form_grievance_summary_confirmed': {
            'utterances': {
                1: {
                    'en': "Here is the current summary: '{current_summary}'.\n Is this correct?",
                    'ne': "तपाईंको गुनासोको निम्न सारांश यहाँ छ:\n{current_summary}\nके यो सही लाग्दैन?"
                },
                2: {
                    'en': "There is no summary yet. Please type a new summary for your grievance or skip",
                    'ne': "कुनै सारांश छैन। कृपया तपाईंको गुनासोको लागि नयाँ सारांश प्रविष्ट गर्नुहोस् वा छोड्नुहोस्"
                }
            },
            'buttons': {
                1: {'en':[
                    {"title": "Validate summary", "payload": "/slot_confirmed"},
                    {"title": "Edit summary", "payload": "/slot_edited"},
                    {"title": "Skip", "payload": "/skip"}
                ],
                'ne': [
                    {"title": "सारांश सुनिश्चित गर्नुहोस्", "payload": "/slot_confirmed"},
                    {"title": "सारांश संपादन गर्नुहोस्", "payload": "/slot_edited"},
                    {"title": "छोड्नुहोस्", "payload": "/skip"}
                ]
                }
            }
        },
        'action_ask_grievance_summary_form_grievance_summary_temp': {
            'utterances': {
                1: {
                    'en': "Please enter the new summary and confirm again.",
                    'ne': "कृपया नयाँ सारांश प्रविष्ट गर्नुहोस् र फेरी सुनिश्चित गर्नुहोस्।"
                }
            }
        },
        'action_ask_details_form_grievance_temp': {
            'utterances': {
                1: {
                    'en': "Great! Let's start by understanding your grievance...",
                    'ne': "राम्रो! चल्नुस् तपाईंको गुनासोको बारेमा सुरु गरौं..."
                },
                2: {
                    'en': "Please provide more details about your grievance.",
                    'ne': "कृपया आफ्नो गुनासोको बारेमा थप विवरण प्रदान गर्नुहोस्।"
                },
                3: {
                    'en': "Calling OpenAI for classification... This may take a few seconds",
                    'ne': "OpenAI क्लासिफिकेशनको लागि कल गर्दै... यसमा केही सेकेन्ड लाग्न सक्छ"
                },
                4: {'en': "Thank you for your entry. Do you want to add more details to your grievance, such as:\n"
                    "- Location information\n"
                    "- Persons involved\n"
                    "- Quantification of damages (e.g., number of bags of rice lost)\n"
                    "- Monetary value of damages",
                    'ne': "तपाईंको प्रविष्टिको लागि धन्यवाद। के तपाईं आफ्नो गुनासोको बारेमा थप विवरण गर्न चाहनुहुन्छ, जुन यस प्रकारको हुन्छ:\n"
                    "- स्थान जानकारी\n"
                    "- भागहरूको सम्बन्धमा\n"
                    "- हानिको मात्रात्मकको सम्बन्धमा (उदाहरणका लागि, गुनासोको बर्गहरूको संख्या)\n"
                    "- हानिको मुनाफा मूल्य"}
            },
            'buttons': BUTTONS_GRIEVANCE_SUBMISSION
        },
        'create_confirmation_message': {
            'utterances': {
                'base_message': {
                    'en': "Your grievance has been filed successfully.\n**Grievance ID:** {grievance_id}",
                    'ne': "तपाईंको गुनासो सफलतापूर्वक दर्ता गरिएको छ।\n**गुनासो ID:** {grievance_id}"
                },
                'grievance_summary': {
                    'en': "**Summary: {grievance_summary}**",
                    'ne': "**सारांश: {grievance_summary}**"
                },
                'grievance_category': {
                    'en': "**Category: {grievance_category}**",
                    'ne': "**श्रेणी: {grievance_category}**"
                },
                'grievance_details': {
                    'en': "**Details: {grievance_details}**",
                    'ne': "**विवरण: {grievance_details}**"
                },
                'grievance_email': {
                    'en': "\nA confirmation email will be sent to {grievance_email}",
                    'ne': "\nतपाईंको इमेलमा सुनिश्चित गर्ने ईमेल भेटिन्छ।"
                },
                'grievance_phone': {
                    'en': "**Phone: {grievance_phone}**",
                    'ne': "**फोन: {grievance_phone}**"
                },
                'grievance_outro': {
                    'en': "Our team will review it shortly and contact you if more information is needed.",
                    'ne': "हाम्रो टीमले त्यो गुनासोको लागि कल गर्दैछु र तपाईंलाई यदि अधिक जानकारी आवश्यक हुन्छ भने सम्पर्क गर्नेछ।"
                },
                'grievance_timeline': {
                    'en': "The standard timeline for a grievance is 15 days.",
                    'ne': "गुनासोको मानक समयावधि 15 दिन हुन्छ।"
                },
                'grievance_status': {
                    'en': "**Status:**",
                    'ne': "**स्थिति:**"
                }
            }
        }
    },
    'generic_actions': {
        'action_introduce': {
            'utterances': {
                1: {
                    'en': "Hello! Welcome to the Grievance Management Chatbot.\nI am here to help you file a grievance or check its status. What would you like to do?",
                    'ne': "नमस्कार! गुनासो व्यवस्थापन च्याटबटमा स्वागत छ।\nम तपाईंलाई गुनासो दर्ता गर्न वा यसको स्थिति जाँच गर्न मद्दत गर्न यहाँ छु। तपाईं के गर्न चाहनुहुन्छ?"
                },
                2: {
                    'en': "Hello! Welcome to the Grievance Management Chatbot.\nYou are reaching out to the office of {district} in {province}.\nI am here to help you file a grievance or check its status. What would you like to do?",
                    'ne': "नमस्कार! गुनासो व्यवस्थापन च्याटबटमा स्वागत छ।\nतपाईं {province} मा {district} को कार्यालयमा सम्पर्क गर्दै हुनुहुन्छ।\nम तपाईंलाई गुनासो दर्ता गर्न वा यसको स्थिति जाँच गर्न मद्दत गर्न यहाँ छु। तपाईं के गर्न चाहनुहुन्छ?"
                }
            },
            'buttons': {
                1: {
                    'en': [
                        {"title": "File a grievance", "payload": "/start_grievance_process"},
                        {"title": "Check my status", "payload": "/check_status"},
                        {"title": "Exit", "payload": "/goodbye"}
                    ],
                    'ne': [
                        {"title": "गुनासो दर्ता गर्नुहोस्", "payload": "/start_grievance_process"},
                        {"title": "स्थिति जाँच गर्नुहोस्", "payload": "/check_status"},
                        {"title": "बाहिर निस्कनुहोस्", "payload": "/goodbye"}
                    ]
                }
            }
        },
        'action_menu': {
            'utterances': {
                1: {
                    'en': "Hello! Welcome to the Grievance Management Chatbot.\nI am here to help you file a grievance or check its status. What would you like to do?",
                    'ne': "नमस्कार! गुनासो व्यवस्थापन च्याटबटमा स्वागत छ।\nम तपाईंलाई गुनासो दर्ता गर्न वा यसको स्थिति जाँच गर्न मद्दत गर्न यहाँ छु। तपाईं के गर्न चाहनुहुन्छ?"
                },
                2: {
                    'en': "Hello! Welcome to the Grievance Management Chatbot.\nYou are reaching out to the office of {district} in {province}.\nI am here to help you file a grievance or check its status. What would you like to do?",
                    'ne': "नमस्कार! गुनासो व्यवस्थापन च्याटबटमा स्वागत छ।\nतपाईं {province} मा {district} को कार्यालयमा सम्पर्क गर्दै हुनुहुन्छ।\nम तपाईंलाई गुनासो दर्ता गर्न वा यसको स्थिति जाँच गर्न मद्दत गर्न यहाँ छु। तपाईं के गर्न चाहनुहुन्छ?"
                }
            },
            'buttons': {
                1: {
                    'en': [
                        {"title": "File a grievance", "payload": "/start_grievance_process"},
                        {"title": "Check my status", "payload": "/check_status"},
                        {"title": "Exit", "payload": "/goodbye"}
                    ],
                    'ne': [
                        {"title": "गुनासो दर्ता गर्नुहोस्", "payload": "/start_grievance_process"},
                        {"title": "स्थिति जाँच गर्नुहोस्", "payload": "/check_status"},
                        {"title": "बाहिर निस्कनुहोस्", "payload": "/goodbye"}
                    ]
                }
            }
        },
        'action_session_start': {
            'utterances': {
                1: {
                    'en':
                     "नमस्कार! गुनासो व्यवस्थापन च्याटबटमा स्वागत छ।\nतपाईं कुन भाषा प्रयोग गर्न चाहनुहुन्छ?\nHello! Welcome to the Grievance Management Chatbot.\nWhat language do you want to use?"
                }
            },
            'buttons': {
                1: BUTTONS_LANGUAGE_OPTIONS
                
            }
        },
        'action_set_current_process': {
            'utterances': {
                1: {
                    'en': "You are currently in the process of {current_story}.",
                    'ne': "तपाईं हाल {current_story} को प्रक्रियामा हुनुहुन्छ।"
                }
            }
        },
        'action_go_back': {
            'utterances': {
                1: {
                    'en': "Going back to the previous step.",
                    'ne': "अघिल्लो चरणमा फर्कदै।"
                }
            }
        },
        'action_restart_story': {
            'utterances': {
                1: {
                    'en': "Would you like to restart the current process or story?",
                    'ne': "के तपाईं वर्तमान प्रक्रिया वा कथामा पुनः सुरु गर्न चाहनुहुन्छ?"
                }
            },
            'buttons': {
                1: BUTTONS_RESTART_OPTIONS
            }
        },
        'action_show_current_story': {
            'utterances': {
                1: {
                    'en': "You are currently in the {current_story} process.",
                    'ne': "तपाईं हाल {current_story} प्रक्रियामा हुनुहुन्छ।"
                },
                2: {
                    'en': "I don't know which process you're currently in.",
                    'ne': "मलाई थाहा छैन तपाईं हाल कुन प्रक्रियामा हुनुहुन्छ।"
                }
            }
        },
        'action_handle_mood_great': {
            'utterances': {
                1: {
                    'en': "I'm glad you're feeling good! Let's continue with your grievance.",
                    'ne': "मलाई खुशी लाग्यो कि तपाईं राम्रो महसुस गर्दै हुनुहुन्छ! चल्नुस् तपाईंको गुनासो जारी राखौं।"
                },
                2: {
                    'en': "That's great! What would you like to do next?",
                    'ne': "त्यो राम्रो हो! तपाईं अब के गर्न चाहनुहुन्छ?"
                }
            }
        },
        'action_respond_to_challenge': {
            'utterances': {
                1: {
                    'en': "I understand this might be challenging. I'm here to help you through it.",
                    'ne': "म बुझ्दछु कि यो चुनौतीपूर्ण हुन सक्छ। म तपाईंलाई यसमा मद्दत गर्न यहाँ छु।"
                }
            }
        },
        'action_custom_fallback': {
            'utterances': {
                1: {
                    'en': "I didn't understand that. What would you like to do next?",
                    'ne': "मैले त्यो बुझिन। तपाईं अब के गर्न चाहनुहुन्छ?"
                }
            },
            'buttons': {
                1: BUTTONS_FALLBACK
            }
        },
        'action_handle_skip': {
            'utterances': {
                1: {
                    'en': "Would you like to file your grievance as is?",
                    'ne': "के तपाईं आफ्नो गुनासो यसै रूपमा दर्ता गर्न चाहनुहुन्छ?"
                },
                2: {
                    'en': "Are you sure you want to skip this step?",
                    'ne': "के तपाईं यो चरण छोड्न निश्चित हुनुहुन्छ?"
                }
            },
            'buttons': {
                1: BUTTONS_AFFIRM_DENY
            }
        },
        'action_mood_unhappy': {
            'utterances': {
                1: {
                    'en': "I'm sorry to hear that you're not satisfied. How can I help you address that?",
                    'ne': "मलाई खुशी लाग्यो कि तपाईं अनचाहित छ। म तपाईंलाई के मद्दत गर्न सक्छु?"
                }
            },
            'buttons': {
                1: BUTTONS_FALLBACK
            }
        },
        'action_exit_without_filing': {
            'utterances': {
                1: {
                    'en': "Thank you for your time. If you change your mind, feel free to start the grievance process again.",
                    'ne': "तपाईंको समय धन्यवाद। यदि तपाईं अपनो मन बदल्न चाहनुहुन्छ भने, कृपया गुनासो प्रक्रिया पुनः सुरु गर्नुहोस्।"
                }
            },
        },
        'action_goodbye': {
            'utterances': {
                1: {
                    'en': "Goodbye! If you need further assistance, feel free to ask.",
                    'ne': "बाहिर निस्कनुहोस्", "payload": "/goodbye"}
                }
            }
        
    },
    'menu_form': {
        'action_ask_menu_form_main_story': {
            'utterances': {
                1: {
                    'en': "Hello! Welcome to the Grievance Management Chatbot.\nI am here to help you file a grievance or check its status. What would you like to do?",
                    'ne': "नमस्कार! गुनासो व्यवस्थापन च्याटबटमा स्वागत छ।\nम तपाईंलाई गुनासो दर्ता गर्न वा यसको स्थिति जाँच गर्न मद्दत गर्न यहाँ छु। तपाईं के गर्न चाहनुहुन्छ?"
                },
                2: {
                    'en': "Hello! Welcome to the Grievance Management Chatbot.\nYou are reaching out to the office of {district} in {province}.\nI am here to help you file a grievance or check its status. What would you like to do?",
                    'ne': "नमस्कार! गुनासो व्यवस्थापन च्याटबटमा स्वागत छ।\nतपाईं {province} मा {district} को कार्यालयमा सम्पर्क गर्दै हुनुहुन्छ।\nम तपाईंलाई गुनासो दर्ता गर्न वा यसको स्थिति जाँच गर्न मद्दत गर्न यहाँ छु। तपाईं के गर्न चाहनुहुन्छ?"
                }
            },
            'buttons': {
                1: {
                    'en': [
                        {"title": "File a grievance", "payload": "/start_grievance_process"},
                        {"title": "Check my status", "payload": "/check_status"},
                        {"title": "Exit", "payload": "/goodbye"}
                    ],
                    'ne': [
                        {"title": "गुनासो दर्ता गर्नुहोस्", "payload": "/start_grievance_process"},
                        {"title": "स्थिति जाँच गर्नुहोस्", "payload": "/check_status"},
                        {"title": "बाहिर निस्कनुहोस्", "payload": "/goodbye"}
                    ]
                }
            }
        },
        'action_ask_menu_form_language_code': {
            'utterances': {
                1: {
                    'en':
                     "नमस्कार! गुनासो व्यवस्थापन च्याटबटमा स्वागत छ।\nतपाईं कुन भाषा प्रयोग गर्न चाहनुहुन्छ?\nHello! Welcome to the Grievance Management Chatbot.\nWhat language do you want to use?"
                }
            },
            'buttons': {
                1: BUTTONS_LANGUAGE_OPTIONS
            }
        }
    },
    'base_form': {
        "handle_slot_extraction": {
            "utterances":{
                1 : {
                    "en" : "Did you want to skip this field? I matched '{matched_word}'",
                     "ne" : "के तपाईं यो क्षेत्र छोड्न चाहनुहुन्छ? मलाई '{matched_word}' मिलेको छ।"
                }
            },
            "buttons":{
                1:{
                    "en": [
                                {"title": "Yes, skip it", "payload": "/affirm_skip"},
                                {"title": "No, let me enter a value", "payload": "/deny_skip"}
                            ],
                    "ne": [
                                {"title": "Yes, skip it", "payload": "/affirm_skip"},
                                {"title": "No, let me enter a value", "payload": "/deny_skip"}
                            ]
                }
            }
        }
    }
}

def get_utterance(form_name: str, action_name: str, utter_index: int, language: str = 'en') -> str:
    """
    Get the appropriate utterance based on form, action, index, and language.
    
    Args:
        form_name (str): Name of the form
        action_name (str): Name of the action
        utter_index (int): Index of the utterance (1-based)
        language (str): Language code ('en' or 'ne')
        
    Returns:
        str: The appropriate utterance name
    """
    try:
        ic(form_name, action_name, utter_index, language)
        return UTTERANCE_MAPPING[form_name][action_name]['utterances'][utter_index][language]
    except (KeyError, IndexError) as e:
        print(f"Error getting utterance: {str(e)}")
        return None

def get_all_utterances(form_name: str, action_name: str, language: str = 'en') -> list:
    """
    Get all utterances for a specific form, action, and language.
    
    Args:
        form_name (str): Name of the form
        action_name (str): Name of the action
        language (str): Language code ('en' or 'ne')
        
    Returns:
        list: List of utterance names
    """
    try:
        return [utterance[language] for utterance in UTTERANCE_MAPPING[form_name][action_name]['utterances'].values()]
    except KeyError as e:
        print(f"Error getting utterances: {str(e)}")
        return []

def get_utterance_count(form_name: str, action_name: str) -> int:
    """
    Get the number of utterances for a specific form and action.
    
    Args:
        form_name (str): Name of the form
        action_name (str): Name of the action
        
    Returns:
        int: Number of utterances
    """
    try:
        return len(UTTERANCE_MAPPING[form_name][action_name]['utterances'])
    except KeyError as e:
        print(f"Error getting utterance count: {str(e)}")
        return 0

def get_buttons(form_name: str, action_name: str, button_index: int, language: str = 'en') -> list:
    """
    Get the buttons for a specific form, action, index, and language.
    
    Args:
        form_name (str): Name of the form
        action_name (str): Name of the action
        button_index (int): Index of the button set (1-based)
        language (str): Language code ('en' or 'ne')
        
    Returns:
        list: List of button dictionaries with title and payload
    """
    try:
        ic(form_name, action_name, button_index, language)
        return UTTERANCE_MAPPING[form_name][action_name]['buttons'][button_index][language]
    except KeyError as e:
        print(f"Error getting buttons: {str(e)}")
        return []