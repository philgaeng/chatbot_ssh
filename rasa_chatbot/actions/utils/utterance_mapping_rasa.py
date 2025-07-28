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
from .mapping_buttons import *

#special case for sensitive issues follow up so that the messaging is consistent accross all forms that may use it
SENSITIVE_ISSUES_UTTERANCES_AND_BUTTONS = {
            'utterances': {
                1: {
                    'en': """We recommend that you contact the One Stop Crisis Management Centre of Morang where special support will be provided to you. 
                    """,
                    'ne': """गेंडर गुनासो बारेमा बताइएको छ। कृपया थप विवरण प्रविष्ट गर्नुहोस्।
                    """
                },
                2: {
                    'en': """Address : Koshi Regional Hospital, Biratnagar
                    Morang
                    Phone : 021-530103""",
                    'ne': """कोशी रिजियनल हस्तान्याउन हस्तान्याउन, बिरतनगर
                    फोन : 021-530103""",
                },
                3: {
                    'en': """ You can get more information on : https://nwchelpline.gov.np""",
                    'ne': """तपाईं अधिक जानकारी प्राप्त गर्न सक्नुहुन्छ : https://nwchelpline.gov.np""",
                },
                4: {
                    'en': """You can decide to file your grievance anonymously with one phone number or not.
                    """,
                    'ne': """तपाईं एक फोन नम्बर सहित गुनासो दर्ता गर्न चाहनुहुन्छ वा छोड्न सक्नुहुन्छ।
                    """
                },
                5: {
                    'en': "If you desire, you can provide us with more details that we will forward to the OCMC.",
                    'ne': "यदि तपाईं चाहनुहुन्छ भने, तपाईंको अतिरिक्त विवरण हामीलाई फोरवर्ड गर्न सक्नुहुन्छ जुन हामी एक फोन नम्बर सहित गुनासो दर्ता गर्न चाहनुहुन्छ।",
                }
            },
            'buttons': {
                1:  {
                    'en': [
                        {"title": "File anonymously", "payload": BUTTON_EXIT},
                        {"title": "File anonymously with one phone number", "payload": BUTTON_ANONYMOUS_WITH_PHONE},
                        {"title": "Provide more details", "payload": BUTTON_ADD_MORE_DETAILS},
                    ],
                    'ne': [
                        {"title": "गुनासो दर्ता गर्न चाहनुहुन्छ", "payload": BUTTON_EXIT},
                        {"title": "एक फोन नम्बर सहित गुनासो दर्ता गर्न चाहनुहुन्छ", "payload": BUTTON_ANONYMOUS_WITH_PHONE},
                        {"title": "अधिक विवरण प्रदान गर्न चाहनुहुन्छ", "payload": BUTTON_ADD_MORE_DETAILS},   
                    ],
                }
            }
        }

UTTERANCE_MAPPING = {
    'form_contact': {
        'action_ask_form_contact_complainant_location_consent': {
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
        'action_ask_form_contact_complainant_municipality_temp': {
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
        'action_ask_form_contact_complainant_municipality_confirmed': {
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
        'action_ask_form_contact_complainant_village': {
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
        'action_ask_form_contact_complainant_address_temp': {
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
        'action_ask_form_contact_complainant_address_confirmed': {
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
        'action_ask_form_contact_complainant_province': {
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
        'action_ask_form_contact_complainant_district': {
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
        'validate_complainant_province': {
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
        'validate_complainant_district': {
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
        'validate_complainant_village': {
            'utterances': {
                1: {
                    'en': "Please provide a valid village name (at least 3 characters) or type 'skip' to skip",
                    'ne': "कृपया एक वैध गाउँको नाम प्रदान गर्नुहोस् (कम्तिमा 3 अक्षर) वा छोड्न 'skip' टाइप गर्नुहोस्"
                }
            }
        },
        'validate_complainant_address_temp': {
            'utterances': {
                1: {
                    'en': "Please provide a valid address (at least 3 characters)",
                    'ne': "कृपया एक वैध ठेगाना प्रदान गर्नुहोस् (कम्तिमा 3 अक्षर)"
                }
            }
        },
        'validate_complainant_confirmed': {
            'utterances': {
                1: {
                    'en': "Please enter your correct village and address",
                    'ne': "कृपया आफ्नो सही गाउँ र ठेगाना प्रविष्ट गर्नुहोस्"
                }
            }
        },
        'action_ask_form_contact_complainant_location_consent': {
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
        'action_ask_form_contact_complainant_municipality_temp': {
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
        'action_ask_form_contact_complainant_municipality_confirmed': {
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
        'action_ask_form_contact_complainant_village': {
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
        'action_ask_form_contact_complainant_address_temp': {
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
        'action_ask_form_contact_complainant_address_confirmed': {
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
        'action_ask_form_contact_complainant_province': {
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
        'action_ask_form_contact_complainant_district': {
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
        'validate_complainant_province': {
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
        'validate_complainant_district': {
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
        'validate_complainant_village': {
            'utterances': {
                1: {
                    'en': "Please provide a valid village name (at least 3 characters) or type 'skip' to skip",
                    'ne': "कृपया एक वैध गाउँको नाम प्रदान गर्नुहोस् (कम्तिमा 3 अक्षर) वा छोड्न 'skip' टाइप गर्नुहोस्"
                }
            }
        },
        'validate_complainant_address_temp': {
            'utterances': {
                1: {
                    'en': "Please provide a valid address (at least 3 characters)",
                    'ne': "कृपया एक वैध ठेगाना प्रदान गर्नुहोस् (कम्तिमा 3 अक्षर)"
                }
            }
        },
        'validate_complainant_phone': {
            'utterances': {
                1: {
                    'en': "Please enter a correct phone number.",
                    'ne': "कृपया आफ्नो सम्पर्क फोन नम्बर प्रविष्ट गर्नुहोस्। नेपाली फोन नम्बर 9 बाट सुरु हुन्छ र 10 अंकको हुनुपर्छ।"
                }
            },
            'buttons': {
                1: BUTTONS_SLOT_SKIPPED
            }
        },
        'action_ask_form_contact_complainant_consent': {
            'utterances': {
                1: {
                    'en': "Would you like to provide your contact information? You can file anonymously but we won't be able to contact you for follow-up or updates.",
                    'ne': "के तपाईं आफ्नो सम्पर्क जानकारी प्रदान गर्न चाहनुहुन्छ? तपाईं गुमनाम रहन सक्नुहुन्छ तर हामी तपाईंलाई अनुवर्ती वा अपडेटको लागि सम्पर्क गर्न सक्नुहुनेछैनौं।"
                }
            },
            'buttons': {
                1: BUTTONS_AFFIRM_DENY
            }
        },
        'action_ask_form_contact_complainant_full_name': {
            'utterances': {
                1: {
                    'en': "Please enter the name you want us to address you by. You can skip this if you prefer to remain anonymous.",
                    'ne': "कृपया हामीलाई तपाईंको नाम प्रविष्ट गर्नुहोस्। यदि तपाईं गुमनाम रहन चाहनुहुन्छ भने यसलाई छोड्न सक्नुहुन्छ।"
                },
                2: {
                    'en': "Please enter your full name. You can skip this if you prefer to remain anonymous.",
                    'ne': "कृपया आफ्नो पूरा नाम प्रविष्ट गर्नुहोस्। यदि तपाईं गुमनाम रहन चाहनुहुन्छ भने यसलाई छोड्न सक्नुहुन्छ।"
                }
            },
            'buttons': {
                1: BUTTONS_SLOT_SKIPPED
            }
        },
        'action_ask_form_contact_complainant_phone': {
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
        'action_ask_form_contact_phone_validation_required': {
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
        'action_ask_form_contact_complainant_email_temp': {
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
        'action_ask_form_contact_complainant_email_confirmed': {
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
    'form_grievance': {
        'action_start_grievance_process': {
            'utterances': {
                1: {
                    'en': "Great!  Let's start by understanding your grievance...",
                    'ne': "राम्रो!  चल्नुस् तपाईंको गुनासो बुझेर सुरु गरौं..."
                }
            }
        },
        'action_ask_form_grievance_summary_sensitive_issues_follow_up': SENSITIVE_ISSUES_UTTERANCES_AND_BUTTONS,  
        'action_ask_grievance_new_detail': {
            'utterances': {
                1: {
                    'en': "Great! Let's start by understanding your grievance...",
                    'ne': "राम्रो! चल्नुस् तपाईंको गुनासो बुझेर सुरु गरौं..."
                },
                2: {
                    'en': "Lets restart, please enter your grievance details...",
                    'ne': "प्रक्रिया पुनः सुरु गर्नुहोस्, कृपया आफ्नो गुनासो विवरण प्रविष्ट गर्नुहोस्..."
                },
                3: {
                    'en': "Please enter more details...",
                    'ne': "कृपया थप विवरण प्रविष्ट गर्नुहोस्..."
                },
                4: {
                    'en': 'Thank you for your entry: "{grievance_description}"',
                    'ne': 'तपाईंको प्रविष्टिको लागि धन्यवाद। "{grievance_description}"'
                },
                5: {
                    'en': "Do you want to add more details to your grievance, such as:\n"
                    "- Location information\n"
                    "- Persons involved\n"
                    "- Quantification of damages (e.g., number of bags of rice lost)\n"
                    "- Monetary value of damages",
                    'ne': "के तपाईं आफ्नो गुनासोको बारेमा थप विवरण गर्न चाहनुहुन्छ, जुन यस प्रकारको हुन्छ:\n"
                    "- स्थान जानकारी\n"
                    "- भागहरूको सम्बन्धमा\n"
                    "- हानिको मात्रात्मकको सम्बन्धमा (उदाहरणका लागि, गुनासोको बर्गहरूको संख्या)\n"
                    "- हानिको मुनाफा मूल्य"
                }
            },
            'buttons': {
                4: BUTTONS_GRIEVANCE_SUBMISSION
            }
        },
        'action_submit_grievance': {
            'utterances': {
                1: {
                    'en': "Your grievance has been filed successfully.",
                    'ne': "तपाईंको गुनासो सफलतापूर्वक दर्ता गरिएको छ।"
                },
                2: {
                    'en': "✅ A recap of your grievance has been sent to your phone : {complainant_phone}.",
                    'ne': "✅ तपाईंको गुनासोको सारांश तपाईंको फोनमा पठाइएको छ। {complainant_phone}"
                },
                3: {
                    'en': "✅ A recap of your grievance has been sent to your email : {complainant_email}.",
                    'ne': "✅ तपाईंको गुनासोको सारांश तपाईंको इमेलमा पठाइएको छ। {complainant_email}"
                },
                4: {
                    'en': "I apologize, but there was an error submitting your grievance. Please try again or contact support.",
                    'ne': "मलाई माफ गर्नुहोस्, तर तपाईंको गुनासो दर्ता गर्दै गर्दा त्रुटि भयो। कृपया पुनः प्रयास गर्नुहोस् वा सहयोग सम्पर्क गर्नुहोस्।"
                },
                5: {
                    'en': "Your grievance has been filed, we recommend that you contact the One Stop Crisis Management Centre of Morang where special support will be provided to you.",
                    'ne': "तपाईंको गुनासो दर्ता गरिएको छ। हामीलाई एक फोन नम्बर सहित गुनासो दर्ता गर्न सक्नुहुन्छ जुन हामी एक फोन नम्बर सहित गुनासो दर्ता गर्न सक्नुहुन्छ।"
                },
                6: {
                    'en': "You have not attached any files. You can still attach them now by clicking on the attachment button below.",
                    'ne': "तपाईंले कुनै फाइल अपलोड गरिएन। तपाईं अभी भी फाइलहरू अपलोड गर्न फाइल बटन पर्खन गर्न सक्नुहुन्छ।"
                },
                7: {
                    'en': "You can still attach more files to your grievance  by clicking on the attachment button below.",
                    'ne': "तपाईं अभी भी तपाईंको गुनासोको लागि अधिक फाइलहरू अपलोड गर्न फाइल बटन पर्खन गर्न सक्नुहुन्छ।"
                }
            },
            'buttons': {
                1: BUTTONS_CLEAN_WINDOW_OPTIONS
            }
        },
        'action_submit_grievance_as_is': {
            'utterances': {
                1: {
                    'en': "Your grievance has been filed successfully.",
                    'ne': "तपाईंको गुनासो सफलतापूर्वक दर्ता गरिएको छ।"
                },
                2: {
                    'en': "✅ A recap of your grievance has been sent to your email : {complainant_email}.",
                    'ne': "✅ तपाईंको गुनासोको सारांश तपाईंको इमेलमा पठाइएको छ। {complainant_email}"
                },
                3: {
                    'en': "✅ A recap of your grievance has been sent to your phone : {complainant_phone}.",
                    'ne': "✅ तपाईंको गुनासोको सारांश तपाईंको फोनमा पठाइएको छ। {complainant_phone}"
                },
                4: {
                    'en': "I apologize, but there was an error submitting your grievance. Please try again or contact support.",
                    'ne': "मलाई माफ गर्नुहोस्, तर तपाईंको गुनासो दर्ता गर्दै गर्दा त्रुटि भयो। कृपया पुनः प्रयास गर्नुहोस् वा सहयोग सम्पर्क गर्नुहोस्।"
                }
            }
        },
        'action_inform_files_uploaded': {
            'en': {
                1: "✅ Your files have been successfully attached to your grievance:\n{description}",
                2: "You can continue with your grievance process or attach more files if needed."
            },
            'ne': {
                1: "✅ तपाईंको फाइलहरू सफलतापूर्वक तपाईंको गुनासोमा संलग्न गरिएको छ:\n{description}",
                2: "तपाईं आफ्नो गुनासो प्रक्रिया जारी राख्न सक्नुहुन्छ वा थप फाइलहरू संलग्न गर्न सक्नुहुन्छ।"
            }
        },
        'action_inform_files_oversized': {
            'en': {
                1: "⚠️ Some files exceeded the maximum size limit of {max_size_formatted}:\n{oversized_files_list}",
                2: "Please compress these files or upload smaller files."
            },
            'ne': {
                1: "⚠️ केही फाइलहरू अधिकतम साइज सीमा {max_size_formatted} भन्दा बढी छन्:\n{oversized_files_list}",
                2: "कृपया यी फाइलहरूलाई कम्प्रेस गर्नुहोस् वा सानो फाइलहरू अपलोड गर्नुहोस्।"
            }
        }
    },
    'form_grievance_summary': {
        'action_ask_form_grievance_summary_grievance_categories_status': {
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
                        {"title": "Skip", "payload": "/skip"}
                    ],
                    'ne': [
                        {"title": "हो", "payload": "/slot_confirmed"},
                        {"title": "श्रेणी थप्नुहोस्", "payload": "/slot_added"},
                        {"title": "श्रेणी हटाउनुहोस्", "payload": "/slot_deleted"},
                        {"title": "छोड्नुहोस्", "payload": "/skip"}
                    ]
                }
            }
        },
        'action_ask_form_grievance_summary_grievance_cat_modify': {
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
        'action_ask_form_grievance_summary_grievance_summary_status': {
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
        'action_ask_form_grievance_summary_grievance_summary_temp': {
            'utterances': {
                1: {
                    'en': "Please enter the new summary and confirm again.",
                    'ne': "कृपया नयाँ सारांश प्रविष्ट गर्नुहोस् र फेरी सुनिश्चित गर्नुहोस्।"
                }
            }
        }
    },
    'generic_actions': {
        'action_introduce': {
            'utterances': {
                1: {
                    'en':
                     "नमस्कार! गुनासो व्यवस्थापन च्याटबटमा स्वागत छ।\nतपाईं कुन भाषा प्रयोग गर्न चाहनुहुन्छ?\nHello! Welcome to the Grievance Management Chatbot.\nWhat language do you want to use?",
                     'ne':
                     "नमस्कार! गुनासो व्यवस्थापन च्याटबटमा स्वागत छ।\nतपाईं कुन भाषा प्रयोग गर्न चाहनुहुन्छ?\nHello! Welcome to the Grievance Management Chatbot.\nWhat language do you want to use?"
                }
            },
            'buttons': {
                1: BUTTONS_LANGUAGE_OPTIONS
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
                        {"title": "Check my status", "payload": "/start_check_status"},
                        {"title": "Exit", "payload": "/goodbye"}
                    ],
                    'ne': [
                        {"title": "गुनासो दर्ता गर्नुहोस्", "payload": "/start_grievance_process"},
                        {"title": "स्थिति जाँच गर्नुहोस्", "payload": "/start_check_status"},
                        {"title": "बाहिर निस्कनुहोस्", "payload": "/goodbye"}
                    ]
                }
            }
        },
        'action_outro': {
            'utterances': {
                1: {
                    'en': "Thank you for using the Grievance Management Chatbot. Have a great day!",
                    'ne': "गुनासो व्यवस्थापन च्याटबटमा धन्यवाद। एक अच्छा दिन राखौं!"
                }
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
            },
        'action_attach_file': {
            'utterances': {
                1: {
                    'en': "No files were attached. Please select files using the attachment button first.",
                    'ne': "कुनै फाइलहरू संलग्न गरिएको छैन। कृपया पहिले एट्याचमेन्ट बटन प्रयोग गरेर फाइलहरू छान्नुहोस्।"
                },
                2: {
                    'en': "Thank you. Your file '{file_name}' has been successfully attached to your grievance.",
                    'ne': "धन्यवाद। तपाईंको फाइल '{file_name}' सफलतापूर्वक तपाईंको गुनासोमा संलग्न गरिएको छ।"
                },
                3: {
                    'en': "Please file a grievance first before attaching files.",
                    'ne': "कृपया फाइलहरू संलग्न गर्नु अघि गुनासो दर्ता गर्नुहोस्।"
                },
                4: {
                    'en': "Thank you. Your {count} files ({files}) have been successfully attached to your grievance.",
                    'ne': "धन्यवाद। तपाईंका {count} फाइलहरू ({files}) सफलतापूर्वक तपाईंको गुनासोमा संलग्न गरिएको छन्।"
                },
                5: {
                    'en': "You can now attach files to your grievance using the attachment button.",
                    'ne': "अब तपाईं एट्याचमेन्ट बटन प्रयोग गरेर आफ्नो गुनासोमा फाइलहरू संलग्न गर्न सक्नुहुन्छ।"
                }
            }
        },
        'action_clean_window_options': {
            'utterances': {
                1: {
                    'en': "Your grievance is completed. You can close the browser tab or session.",
                    'ne': "तपाईंको गुनासो पूरा हुन गरियो। तपाईं ब्राउजर टैब वा सत्र बन्द गर्न सक्नुहुन्छ।"
                }
            },
            'buttons': {
                1: BUTTONS_CLEAN_WINDOW_OPTIONS
            }
        },
        'action_question_attach_files': {
            'utterances': {
                1: {
                    'en': "In order to attach files, please click the attachment button.",
                    'ne': "फाइलहरू संलग्न गर्न चाहनुहुन्छ भने, कृपया एट्याचमेन्ट बटन प्रयोग गर्नुहोस्।"
                }
            }
        }
    },
    'form_menu': {
        'action_ask_form_menu_main_story': {
            'utterances': {
                1: {
                    'en': "I am here to help you file a grievance or check its status. What would you like to do?",
                    'ne': "म तपाईंलाई गुनासो दर्ता गर्न वा यसको स्थिति जाँच गर्न मद्दत गर्न यहाँ छु। तपाईं के गर्न चाहनुहुन्छ?"
                },
                2: {
                    'en': "You are reaching out to the office of {district} in {province}.\nI am here to help you file a grievance or check its status. What would you like to do?",
                    'ne': "तपाईं {province} मा {district} को कार्यालयमा सम्पर्क गर्दै हुनुहुन्छ।\nम तपाईंलाई गुनासो दर्ता गर्न वा यसको स्थिति जाँच गर्न मद्दत गर्न यहाँ छु। तपाईं के गर्न चाहनुहुन्छ?"
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
        'action_ask_form_menu_language_code': {
            'utterances': {
                1: {
                    'en':"तपाईं कुन भाषा प्रयोग गर्न चाहनुहुन्छ?\nWhat language do you want to use?",
                    'ne':"तपाईं कुन भाषा प्रयोग गर्न चाहनुहुन्छ?\nWhat language do you want to use?",
                }
            },
            'buttons': {
                1: BUTTONS_LANGUAGE_OPTIONS
            }
        }
    },
    'form_otp': {
        'action_ask_otp_consent': {
            'utterances': {
                1: {
                    'en': "Do you want to verify your phone number so we can safely contact you? If you don't confirm the number, we will keep it for reference but will not contact you.",
                    'ne': "के तपाईं आफ्नो फोन नम्बरको प्रमाणित गर्न चाहनुहुन्छ? यदि तपाईं नम्बर सुनिश्चित गर्न नभएको हुन्, त्यसैले तपाईंको नम्बर सुनिश्चित गर्न हुन्छ र हामीलाई सुनिश्चित गर्न हुन्छ कि तपाईंलाई सम्पर्क गर्न हुन्छ।",
                }
            },
            'buttons': {
                1: BUTTONS_AFFIRM_DENY
            }
        },
        'validate_otp_input': {
            'utterances': {
                1: {
                    'en': "OTP verified successfully",
                    'ne': "OTP सुनिश्चित गर्न गरिएको छ।"
                }
            }
        },
        "action_ask_otp_input": {
            'utterances': {
                1: {
                    'en': "Your verification code is {otp_number}. \n Please enter this code to verify your phone number.",
                    'ne': "तपाईंको प्रमाणित कोड {otp_number} हो। \n कृपया यो कोड प्रमाणित गर्न तपाईंको फोन नम्बरमा प्रविष्ट गर्नुहोस्।"
                },
                2: {
                    'en': "-------- OTP verification ongoing --------\nPlease enter the 6-digit One Time Password (OTP) sent to your phone {phone_number} to verify your number.",
                    'ne': "-------- OTP सुनिश्चित गर्न गरिएको छ --------\nकृपया तपाईंको फोन नम्बर {phone_number}मा पठाईएको 6-अंकीय एक बारमा प्रविष्ट गर्नुहोस्।"
                },
                3: {
                    'en': "This is your {resend_count} attempt. You have {max_attempts} attempts left.",
                    'ne': "यो तपाईंको {resend_count} प्रयास हो। तपाईंलाई अब {max_attempts} प्रयास बाँचेको छ।"
                },
                4: {
                    'en': "Sorry, we couldn't send the verification code.",
                    'ne': "मलाई खुशी लाग्यो कि तपाईं अपनो मन बदल्न चाहनुहुन्छ। म तपाईंलाई के मद्दत गर्न सक्छु?"
                },
                5: {
                    'en': "❌ Maximum resend attempts reached. Please try again later or skip verification.",
                    'ne': "❌ अधिकतम प्रयास पुनः प्रयास गर्न गरिएको छ। कृपया फेरि प्रयास गर्नुहोस् वा प्रमाणित गर्न छोड्नुहोस्।"
                },
                6: {
                    'en': "❌ Invalid code. Please try again or type 'resend' to get a new code.",
                    'ne': "❌ अवैध कोड। कृपया पुनः प्रयास गर्नुहोस् वा 'resend' प्रमाणित गर्न गर्नुहोस्।"
                },
                7: {
                    'en': "Continuing without phone verification. Your grievance details will not be sent via SMS.",
                    'ne': "प्रमाणित गर्न छोड्नुहोस्। तपाईंको गुनासो व्यवस्थापन च्याटबटमा स्वागत छ।\nम तपाईंलाई गुनासो दर्ता गर्न वा यसको स्थिति जाँच गर्न मद्दत गर्न यहाँ छु। तपाईं के गर्न चाहनुहुन्छ?"
                }
            },
            'buttons': {
                1: {
                    'en': [
                        {"title": "Resend", "payload": "/resend"},
                        {"title": "Skip", "payload": "/skip"}
                    ],
                    'ne': [
                        {"title": "पुनः प्रमाणित गर्नुहोस्", "payload": "/resend"},
                        {"title": "छोड्नुहोस्", "payload": "/skip"}
                    ]
                }
            }
        }
    },
    'form_sensitive_issues': {
        'action_ask_sensitive_issues_new_detail': {
            'utterances': {
                1: {
                    'en': "What are the details you want to add, you may add details about the location, date and time, etc.",
                    'ne': "तपाईं के विवरण थप्न चाहनुहुन्छ, तपाईं स्थान, मिति र समय विवरण थप्न सक्नुहुन्छ।"
                }
            }
        },
        'action_ask_sensitive_issues_nickname': {
            'utterances': {
                1: {
                    'en': "Do you want to provide us a nickname that we will use to contact you anonymously - you can skip if you want?",
                    'ne': "के तपाईं हामीलाई एक नाम दिन चाहनुहुन्छ जुन हामी तपाईंलाई अनामिक रूपमा सम्पर्क गर्न प्रयोग गर्न सक्नुहुन्छ?"
                }
            },
            'buttons': {
                1: BUTTONS_SKIP
            }
        },
        'action_ask_form_sensitive_issues_complainant_phone': {
            'utterances': {
                1: {
                    'en': "Do you want to provide us your phone number so we can contact you - or skip?",
                    'ne': "के तपाईं हामीलाई आफ्नो फोन नम्बर दिन चाहनुहुन्छ जुन हामी तपाईंलाई सम्पर्क गर्न प्रयोग गर्न सक्नुहुन्छ?"
                }
            },
            'buttons': {
                1: BUTTONS_SKIP
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
    },
    'check_status': {
        'action_choose_retrieval_method': {
            'utterances': {
                1: {
                    'en': "How would you like to retrieve your grievance?",
                    'ne': "तपाईं आफ्नो गुनासो कसरी पुनः प्राप्त गर्न चाहनुहुन्छ?"
                }
            },
            'buttons': {
                1: {
                    'en': [
                        {"title": "Use Phone Number", "payload": "/retrieve_with_phone"},
                        {"title": "Use Grievance ID", "payload": "/retrieve_grievance_with_id"}
                    ],
                    'ne': [
                        {"title": "फोन नम्बर प्रयोग गर्नुहोस्", "payload": "/retrieve_with_phone"},
                        {"title": "गुनासो ID प्रयोग गर्नुहोस्", "payload": "/retrieve_grievance_with_id"}
                    ]
                }
            }
        },
        'action_display_grievance': {
            'utterances': {
                1: {
                    'en': "Sorry, I couldn't find any grievance with that ID.",
                    'ne': "माफ गर्नुहोस्, म त्यो ID सँग कुनै गुनासो भेट्टाउन सकिन।"
                },
                2: {
                    'en': "No grievances found for this phone number.",
                    'ne': "यो फोन नम्बरको लागि कुनै गुनासो भेट्टाउन सकिएन।"
                },
                3: {
                    'en': "Sorry, I need either a grievance ID or phone number to retrieve details.",
                    'ne': "माफ गर्नुहोस्, मलाई विवरण पुनः प्राप्त गर्न गुनासो ID वा फोन नम्बर चाहिन्छ।"
                },
                4: {
                    'en': "Found {count} grievances:",
                    'ne': "{count} वटा गुनासो भेट्टाउन सकिएन:"
                },
                5: {
                    'en': "Which grievance would you like to check?",
                    'ne': "तपाईं कुन गुनासो जाँच गर्न चाहनुहुन्छ?"
                },
                6: {
                    'en': "Would you like to check the detailed status?",
                    'ne': "के तपाईं विस्तृत स्थिति जाँच गर्न चाहनुहुन्छ?"
                }
            },
            'buttons': {
                1: {
                    'en': [
                        {"title": "Check Status", "payload": "/check_status"}
                    ],
                    'ne': [
                        {"title": "स्थिति जाँच गर्नुहोस्", "payload": "/check_status"}
                    ]
                }
            }
        },
        'action_helpers': {
            'utterances': {
                'grievance_id': {
                    'en': "🔍 **Grievance ID:** {grievance_id}",
                    'ne': "🔍 **गुनासो ID:** {grievance_id}"
                },
                'grievance_categories': {
                    'en': "📋 **Category:** {grievance_categories}",
                    'ne': "📋 **श्रेणी:** {grievance_categories}"
                },
                'grievance_summary': {
                    'en': "📝 **Summary:** {grievance_summary}",
                    'ne': "📝 **सारांश:** {grievance_summary}"
                },
                'grievance_date': {
                    'en': "📅 **Date:** {grievance_date}",
                    'ne': "📅 **मिति:** {grievance_date}"
                },
                'grievance_creation_date': {
                    'en': "📅 **Created:** {grievance_creation_date}",
                    'ne': "📅 **सिर्जना गरिएको:** {grievance_creation_date}"
                },
                'grievance_status': {
                    'en': "📊 **Status:** {grievance_status}",
                    'ne': "📊 **स्थिति:** {grievance_status}"
                },
                'grievance_status_update_date': {
                    'en': "🔄 **Last Updated:** {grievance_status_update_date}",
                    'ne': "🔄 **अन्तिम अपडेट:** {grievance_status_update_date}"
                },
                'next_step': {
                    'en': "➡️ **Next Step:** {next_step}",
                    'ne': "➡️ **अर्को चरण:** {next_step}"
                },
                'expected_resolution_date': {
                    'en': "🎯 **Expected Resolution:** {expected_resolution_date}",
                    'ne': "🎯 **अपेक्षित समाधान:** {expected_resolution_date}"
                },
                'complainant_full_name': {
                    'en': "👤 **Name:** {complainant_full_name}",
                    'ne': "👤 **नाम:** {complainant_full_name}"
                },
                'complainant_phone': {
                    'en': "📞 **Phone:** {complainant_phone}",
                    'ne': "📞 **फोन:** {complainant_phone}"
                },
                'complainant_address': {
                    'en': "📍 **Address:** {complainant_address}",
                    'ne': "📍 **ठेगाना:** {complainant_address}"
                },
                'grievance_claimed_amount': {
                    'en': "💰 **Claimed Amount:** {grievance_claimed_amount}",
                    'ne': "💰 **दावी रकम:** {grievance_claimed_amount}"
                },
                'grievance_location': {
                    'en': "📍 **Location:** {grievance_location}",
                    'ne': "📍 **स्थान:** {grievance_location}"
                }
            }
        },
        'action_check_status': {
            'utterances': {
                1: {
                    'en': "Sorry, I couldn't determine which grievance to check.",
                    'ne': "माफ गर्नुहोस्, म कुन गुनासो जाँच गर्ने निर्धारण गर्न सकिन।"
                },
                2: {
                    'en': "Sorry, I couldn't retrieve the status history at this moment.",
                    'ne': "माफ गर्नुहोस्, म यो समयमा स्थिति इतिहास पुनः प्राप्त गर्न सकिन।"
                },
                3: {
                    'en': "Would you like to see the full status history?",
                    'ne': "के तपाईं पूर्ण स्थिति इतिहास हेर्न चाहनुहुन्छ?"
                }
            },
            'buttons': {
                1: {
                    'en': [
                        {"title": "View History", "payload": "/show_status_history"},
                        {"title": "Check Another Grievance", "payload": "/retrieve_another_grievance"}
                    ],
                    'ne': [
                        {"title": "इतिहास हेर्नुहोस्", "payload": "/show_status_history"},
                        {"title": "अर्को गुनासो जाँच गर्नुहोस्", "payload": "/retrieve_another_grievance"}
                    ]
                }
            }
        },
        'action_show_status_history': {
            'utterances': {
                1: {
                    'en': "Sorry, I couldn't determine which grievance to show history for.",
                    'ne': "माफ गर्नुहोस्, म कुन गुनासोको लागि इतिहास देखाउने निर्धारण गर्न सकिन।"
                },
                2: {
                    'en': "No status history found for this grievance.",
                    'ne': "यो गुनासोको लागि कुनै स्थिति इतिहास भेट्टाउन सकिएन।"
                },
                3: {
                    'en': "What would you like to do next?",
                    'ne': "तपाईं अब के गर्न चाहनुहुन्छ?"
                }
            },
            'buttons': {
                1: {
                    'en': [
                        {"title": "Check Current Status", "payload": "/check_status"},
                        {"title": "Check Another Grievance", "payload": "/retrieve_another_grievance"},
                        {"title": "End Conversation", "payload": "/goodbye"}
                    ],
                    'ne': [
                        {"title": "वर्तमान स्थिति जाँच गर्नुहोस्", "payload": "/check_status"},
                        {"title": "अर्को गुनासो जाँच गर्नुहोस्", "payload": "/retrieve_another_grievance"},
                        {"title": "कुराकानी समाप्त गर्नुहोस्", "payload": "/goodbye"}
                    ]
                }
            }
        },
        'validate_grievance_id_form': {
            'utterances': {
                1: {
                    'en': "We have found your grievance with ID: {grievance_id}",
                    'ne': "हामीलाई तपाईंको गुनासो भेट्टाउने ID: {grievance_id} भेटिन्छ।"
                },
                2: {
                    'en': "Sorry, we couldn't find a grievance with that ID in our system. Please check the ID and try again.",
                    'ne': "माफ गर्नुहोस्, हामीले यो ID सँग कुनै गुनासो फेला पार्न सकेनौं। कृपया ID जाँच गर्नुहोस् र फेरि प्रयास गर्नुहोस्।"
                },
                3: {
                    'en': "Please enter a valid grievance ID. The ID cannot be empty.",
                    'ne': "कृपया वैध गुनासो ID प्रविष्ट गर्नुहोस्। ID खाली हुन सक्दैन।"
                },
                4: {
                    'en': "The grievance ID must start with 'GR' followed by numbers and letters. Please check the format and try again.",
                    'ne': "गुनासो ID 'GR' सँग सुरु हुनुपर्छ र त्यसपछि नम्बर र अक्षरहरू आउनुपर्छ। कृपया ढाँचा जाँच गर्नुहोस् र फेरि प्रयास गर्नुहोस्।"
                }
            }
        },
        'action_ask_grievance_id_form_grievance_id': {
            'utterances': {
                1: {
                    'en': "Please enter a valid grievance ID starting with 'GR'.",
                    'ne': "कृपया 'GR' शुरु गर्ने एक वैध गुनासो ID प्रविष्ट गर्नुहोस्।"
                }
            }   
        }
    },
    'file_server': {
        'upload_files': {
            'utterances': {
                1: {
                    'en': "No grievance_id provided",
                    'ne': "गुनासो ID प्रदान गरिएन"
                },
                2: {
                    'en': "Please complete your grievance details before attaching files",
                    'ne': "कृपया गुनासो विवरण पूरा गर्न पहिले फाइलहरू अपलोड गर्नुहोस्"
                },
                3: {
                    'en': "No files provided",
                    'ne': "कुनै फाइल प्रदान गरिएन"
                },
                4: {
                    'en': "No files selected",
                    'ne': "कुनै फाइल चयन गरिएन"
                },
                5: {
                    'en': "This type of file is not allowed. Please upload a different file.",
                    'ne': "यो प्रकारको फाइल अनुमति भेटिन्छ नैन। कृपया अर्को फाइल अपलोड गर्नुहोस्।"
                },
                6: {
                    'en': "There was a problem uploading your files. Please try again.",
                    'ne': "फाइलहरू अपलोड गर्दा समस्या भयो। कृपया पुन: प्रयास गर्नुहोस्।"
                }
            }
        },
        'get_files': {
            'utterances': {
                1: {
                    'en': "Internal server error",
                    'ne': "आंतरिक सर्वर त्रुटि"
                }
                
            }
        },
        'download_files': {
            'utterances': {
                1: {
                    'en': "File not found",
                    'ne': "फाइल भेटिन्छ नैन"
                },
                2: {
                    'en': "Internal server error",
                    'ne': "आंतरिक सर्वर त्रुटि"
                }
            }
        }
    },
    "action_inform_files_uploaded": {
        "en": {
            1: "✅ Your files have been successfully attached to your grievance:\n{description}",
            2: "There was a problem uploading your files. Please try again."
        },
        "ne": {
            1: "✅ तपाईंको फाइलहरू सफलतापूर्वक तपाईंको गुनासोमा संलग्न गरिएको छ:\n{description}",
            2: "फाइलहरू अपलोड गर्दा समस्या भयो। कृपया पुन: प्रयास गर्नुहोस्।"
        }
    },
    "action_inform_files_oversized": {
        "en": [
            "⚠️ Some files are too large to upload. The maximum file size allowed is {max_size_formatted}. Please reduce the size of your files and try again."  # Simple size limit message
        ],
        "ne": [
            "⚠️ केही फाइलहरू अपलोड गर्न धेरै ठूला छन्। अधिकतम फाइल साइज {max_size_formatted} हो। कृपया फाइलको साइज घटाएर पुन: प्रयास गर्नुहोस्।"  # Simple size limit message
        ]
    },
}

def get_utterance_base(form_name: str, action_name: str, utter_index: int, language: str = 'en') -> str:
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
        return UTTERANCE_MAPPING[form_name][action_name]['utterances'][utter_index][language]
    except Exception as e:
        raise ValueError(f"Error getting utterance: {str(e)}, form_name: {form_name}, action_name: {action_name}, utter_index: {utter_index}, language: {language}")

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

def get_buttons_base(form_name: str, action_name: str, button_index: int, language: str = 'en') -> list:
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
        return UTTERANCE_MAPPING[form_name][action_name]['buttons'][button_index][language]
    except KeyError as e:
        print(f"Error getting buttons: {str(e)}")
        return []