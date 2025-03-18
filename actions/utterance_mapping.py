"""
Utterance mapping dictionary for multilingual support (English and Nepali).
Structure:
{
    'form_name': {
        'action_name': {
            'utterances': {
                'en': ['utter_1', 'utter_2', ...],
                'ne': ['utter_1', 'utter_2', ...]
            }
        }
    }
}
"""

UTTERANCE_MAPPING = {
    'location_form': {
        'action_ask_location_form_user_location_consent': {
            'utterances': {
                'en': [
                    "Do you want to provide the location details for your grievance. This is optional, your grievance can be filed without it."
                ],
                'ne': [
                    "के तपाईं आफ्नो गुनासोको लागि स्थान विवरण प्रदान गर्न चाहनुहुन्छ? यो वैकल्पिक हो, तपाईंको गुनासो यस बिना पनि दर्ता गर्न सक्नुहुन्छ।"
                ]
            }
        },
        'action_ask_location_form_user_municipality_temp': {
            'utterances': {
                'en': [
                    "Please enter a valid municipality name in {district}, {province} (at least 3 characters) or Skip to skip"
                ],
                'ne': [
                    "कृपया {district}, {province} मा वैध नगरपालिका नाम प्रविष्ट गर्नुहोस् (कम्तिमा 3 अक्षर) वा छोड्न स्किप गर्नुहोस्"
                ]
            }
        },
        'action_ask_location_form_user_municipality_confirmed': {
            'utterances': {
                'en': [
                    "Is {validated_municipality} your correct municipality?"
                ],
                'ne': [
                    "के {validated_municipality} तपाईंको सही नगरपालिका हो?"
                ]
            }
        },
        'action_ask_location_form_user_village': {
            'utterances': {
                'en': [
                    "Please provide your village name or Skip to skip"
                ],
                'ne': [
                    "कृपया आफ्नो गाउँको नाम प्रदान गर्नुहोस् वा छोड्न स्किप गर्नुहोस्"
                ]
            }
        },
        'action_ask_location_form_user_address_temp': {
            'utterances': {
                'en': [
                    "Please provide your address or Skip to skip"
                ],
                'ne': [
                    "कृपया आफ्नो ठेगाना प्रदान गर्नुहोस् वा छोड्न स्किप गर्नुहोस्"
                ]
            }
        },
        'action_ask_location_form_user_address_confirmed': {
            'utterances': {
                'en': [
                    "Thank you for providing your location details:\n- Municipality: {municipality}\n- Village: {village}\n- Address: {address}\nIs this correct?"
                ],
                'ne': [
                    "तपाईंको स्थान विवरण प्रदान गर्नुभएकोमा धन्यवाद:\n- नगरपालिका: {municipality}\n- गाउँ: {village}\n- ठेगाना: {address}\nके यो सही हो?"
                ]
            }
        }
    },
    'contact_form': {
        'action_ask_contact_form_user_contact_consent': {
            'utterances': {
                'en': [
                    "Would you like to provide your contact information? Here are your options:\n\n1️⃣ **Yes**: Share your contact details for follow-up and updates about your grievance.\n2️⃣ **Anonymous with phone number**: Stay anonymous but provide a phone number to receive your grievance ID.\n3️⃣ **No contact information**: File your grievance without providing contact details. Note that we won't be able to follow up or share your grievance ID."
                ],
                'ne': [
                    "के तपाईं आफ्नो सम्पर्क जानकारी प्रदान गर्न चाहनुहुन्छ? तपाईंका विकल्पहरू यहाँ छन्:\n\n1️⃣ **हो**: तपाईंको गुनासोको अनुवर्ती र अपडेटको लागि आफ्नो सम्पर्क विवरण साझेदारी गर्नुहोस्।\n2️⃣ **फोन नम्बरसहित गुमनाम**: गुमनाम रहनुहोस् तर तपाईंको गुनासो आईडी प्राप्त गर्न फोन नम्बर प्रदान गर्नुहोस्।\n3️⃣ **सम्पर्क जानकारी छैन**: सम्पर्क विवरण प्रदान नगरी आफ्नो गुनासो दर्ता गर्नुहोस्। ध्यान दिनुहोस् कि हामी अनुवर्ती गर्न वा तपाईंको गुनासो आईडी साझेदारी गर्न सक्षम हुने छैनौं।"
                ]
            }
        },
        'action_ask_contact_form_user_full_name': {
            'utterances': {
                'en': [
                    "Please enter your full name. You can skip this if you prefer to remain anonymous."
                ],
                'ne': [
                    "कृपया आफ्नो पूरा नाम प्रविष्ट गर्नुहोस्। यदि तपाईं गुमनाम रहन चाहनुहुन्छ भने यसलाई छोड्न सक्नुहुन्छ।"
                ]
            }
        },
        'action_ask_contact_form_user_contact_phone': {
            'utterances': {
                'en': [
                    "Please enter your contact phone number. Nepali phone number starts with 9 and should be 10 digits long. \nYou can skip this if you prefer to remain anonymous."
                ],
                'ne': [
                    "कृपया आफ्नो सम्पर्क फोन नम्बर प्रविष्ट गर्नुहोस्। नेपाली फोन नम्बर 9 बाट सुरु हुन्छ र 10 अंकको हुनुपर्छ।\nयदि तपाईं गुमनाम रहन चाहनुहुन्छ भने यसलाई छोड्न सक्नुहुन्छ।"
                ]
            }
        },
        'action_ask_contact_form_phone_validation_required': {
            'utterances': {
                'en': [
                    "Your grievance is filed without a validated number. Providing a valid number will help in the follow-up of the grievance and we recommend it. However, you can file the grievance as is."
                ],
                'ne': [
                    "तपाईंको गुनासो प्रमाणित नम्बर बिना दर्ता गरिएको छ। वैध नम्बर प्रदान गर्दै गुनासोको अनुवर्तीमा मद्दत पुग्छ र हामी यसलाई सिफारिस गर्दछौं। तथापि, तपाईं गुनासो यसै रूपमा दर्ता गर्न सक्नुहुन्छ।"
                ]
            }
        }
    },
    'otp_form': {
        'action_ask_otp_verification_form_otp_input': {
            'utterances': {
                'en': [
                    "-------- OTP verification ongoing --------\nPlease enter the 6-digit One Time Password (OTP) sent to your phone {phone_number} to verify your number.",
                    "❌ Maximum resend attempts reached. Please try again later or skip verification.",
                    "❌ Invalid code. Please try again or type 'resend' to get a new code.",
                    "Continuing without phone verification. Your grievance details will not be sent via SMS."
                ],
                'ne': [
                    "-------- OTP प्रमाणीकरण जारी छ --------\nकृपया आफ्नो नम्बर प्रमाणित गर्न {phone_number} मा पठाइएको 6-अंकको वन टाइम पासवर्ड (OTP) प्रविष्ट गर्नुहोस्।",
                    "❌ अधिकतम पुनःपठाउने प्रयास पूरा भयो। कृपया पछि पुनः प्रयास गर्नुहोस् वा प्रमाणीकरण छोड्नुहोस्।",
                    "❌ अमान्य कोड। कृपया पुनः प्रयास गर्नुहोस् वा नयाँ कोड प्राप्त गर्न 'resend' टाइप गर्नुहोस्।",
                    "फोन प्रमाणीकरण बिना अगाडि बढ्दै। तपाईंको गुनासो विवरण SMS मार्फत पठाइने छैन।"
                ]
            }
        }
    },
    'grievance_form': {
        'action_start_grievance_process': {
            'utterances': {
                'en': [
                    "Great! Let's start by understanding your grievance...",
                    "Please enter more details...",
                    "Calling OpenAI for classification... This may take a few seconds..."
                ],
                'ne': [
                    "राम्रो! चल्नुस् तपाईंको गुनासो बुझेर सुरु गरौं...",
                    "कृपया थप विवरण प्रविष्ट गर्नुहोस्...",
                    "OpenAI क्लासिफिकेशनको लागि कल गर्दै... यसमा केही सेकेन्ड लाग्न सक्छ..."
                ]
            }
        },
        'action_submit_grievance': {
            'utterances': {
                'en': [
                    "Your grievance has been filed successfully.",
                    "✅ A recap of your grievance has been sent to your email.",
                    "I apologize, but there was an error submitting your grievance. Please try again or contact support."
                ],
                'ne': [
                    "तपाईंको गुनासो सफलतापूर्वक दर्ता गरिएको छ।",
                    "✅ तपाईंको गुनासोको सारांश तपाईंको इमेलमा पठाइएको छ।",
                    "मलाई माफ गर्नुहोस्, तर तपाईंको गुनासो दर्ता गर्दै गर्दा त्रुटि भयो। कृपया पुनः प्रयास गर्नुहोस् वा सहयोग सम्पर्क गर्नुहोस्।"
                ]
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
        utter_index = utter_index - 1  # Convert to 0-based index
        return UTTERANCE_MAPPING[form_name][action_name]['utterances'][language][utter_index]
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
        return UTTERANCE_MAPPING[form_name][action_name]['utterances'][language]
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
        return len(UTTERANCE_MAPPING[form_name][action_name]['utterances']['en'])
    except KeyError as e:
        print(f"Error getting utterance count: {str(e)}")
        return 0