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
                    'ne': """तपाईले बेनामी रूपमा फोन नम्बर प्रयोग गरेर  वा फोन नम्बर प्रयोग नगरी आफ्नो गुनासो दर्ता गर्न सक्नुहुन्छ।
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
    'action_ask_commons': {
        'action_ask_story_main': {
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
                        {"title": "File a grievance", "payload": "/new_grievance"},
                        {"title": "Report sexual exploitation, sexual abuse, and sexual harassment", "payload": "/seah_intake"},
                        {"title": "Check my status", "payload": "/check_status"},
                        {"title": "Exit", "payload": "/goodbye"}
                    ],
                    'ne': [
                        {"title": "गुनासो दर्ता गर्नुहोस्", "payload": "/new_grievance"},
                        {"title": "असुरक्षित व्यवहार, असुरक्षित व्यवहार, वा असुरक्षित व्यवहार रिपोर्ट गर्नुहोस्", "payload": "/seah_intake"},
                        {"title": "स्थिति जाँच गर्नुहोस्", "payload": "/check_status"},
                        {"title": "बाहिर निस्कनुहोस्", "payload": "/goodbye"}
                    ]
                }
            }
        },
        'action_ask_language_code': {
            'utterances': {
                1: {
                    'en':"तपाईं कुन भाषा प्रयोग गर्न चाहनुहुन्छ?\nWhat language do you want to use?",
                    'ne':"तपाईं कुन भाषा प्रयोग गर्न चाहनुहुन्छ?\nWhat language do you want to use?",
                }
            },
            'buttons': {
                1: BUTTONS_LANGUAGE_OPTIONS
            }
        },
        'action_ask_story_route': {
            'utterances': {
                1: {
                    'en': "You can retrieve your grievance by using your grievance ID or the phone number provided during the filing process.",
                    'ne': "तपाईं आफ्नो गुनासो गुनासो परिचय नम्बर  वा फोन नम्बर प्रयोग गरेर पुनः प्राप्त गर्न सक्नुहुन्छ। यो गुनासो दर्ता गर्न दुई तरिका छ।",
                }
            },
            'buttons': {
                1: {
                    'en': [
                        {"title": "Phone Number", "payload": "/route_status_check_phone"},
                        {"title": "Grievance ID", "payload": "/route_status_check_grievance_id"},
                        {"title": "Skip", "payload": BUTTON_SKIP}
                    ],
                    'ne': [
                        {"title": "फोन नम्बर", "payload": "/route_status_check_phone"},
                        {"title": "गुनासो ID", "payload": "/route_status_check_grievance_id"},
                        {"title": "छोड्नुहोस्", "payload": BUTTON_SKIP}
                    ]
                }
            }
        },
        "action_ask_story_step": {
            'utterances': {
                1: {
                    'en': "Here are the details of the grievance:",
                    'ne': "यहाँ गुनासोको विवरणहरु छन्:",
                },
                2: {
                    'en': "We couldn't find any grievance details.",
                    'ne': "हामीले कुनै पनि गुनासो विवरण फेला पार्न सकेनौं।",
                }
            },
            'buttons': {
                1: {
                    'en':[
                    {"title": "Request follow up", "payload": "/status_check_request_follow_up"},
                    {"title": "Modify grievance", "payload": "/status_check_modify_grievance"},
                    {"title": "Skip", "payload": BUTTON_SKIP}
                    ],
                    'ne': [
                        {"title": "अनुसंधान अनुसंधान गर्नुहोस्", "payload": "/status_check_request_follow_up"},
                        {"title": "गुनासो सम्पादन गर्नुहोस्", "payload": "/status_check_modify_grievance"},
                        {"title": "छोड्नुहोस्", "payload": BUTTON_SKIP}]
                },
                2: {
                    'en': [
                        {"title": "Request follow up", "payload": "/status_check_request_follow_up"}
                    ],
                    'ne': [
                        {"title": "अनुसंधान अनुसंधान गर्नुहोस्", "payload": "/status_check_request_follow_up"}
                    ]
                }
            }
        },
        'action_ask_complainant_phone': {
                'utterances': {
                    1: {
                        'en': "Please enter your contact phone number. Nepali phone number starts with 9 and should be 10 digits long. \nYou can skip this if you prefer to remain anonymous.",
                        'ne': "कृपया आफ्नो सम्पर्क फोन नम्बर प्रविष्ट गर्नुहोस्। नेपाली फोन नम्बर 9 बाट सुरु हुन्छ र 10 अंकको हुनुपर्छ।\nयदि तपाईं गुमनाम रहन चाहनुहुन्छ भने यसलाई छोड्न सक्नुहुन्छ।"
                    },
                     2: {
                    'en': "The number you provided is not valid. Please provide a valid number - it should start by 9 and be 10 digits long",
                    'ne': "कृपया तपाईंको आधिकारिक फोन नम्बर प्रदान गर्नुहोस् - फोन नम्बर ९ अंक बाट सुरु हुनुपर्छ र १० अंकको हुनुपर्छ"
                },
                },
                'profile_utterances': {
                    'seah-victim': {
                        1: {
                            'en': "Please enter your contact phone number so a confidential SEAH handler can follow up if needed. Nepali phone number starts with 9 and should be 10 digits long. You can skip this if you prefer not to share it.",
                            'ne': "कृपया आवश्यक परे गोप्य SEAH फलो-अपका लागि आफ्नो सम्पर्क फोन नम्बर दिनुहोस्। नेपाली नम्बर 9 बाट सुरु भई 10 अंकको हुनुपर्छ। दिन नचाहेमा छोड्न सक्नुहुन्छ।"
                        },
                        2: {
                            'en': "The phone number is not valid. Please enter a valid Nepali number starting with 9 and 10 digits long.",
                            'ne': "फोन नम्बर मान्य छैन। कृपया 9 बाट सुरु हुने 10 अंकको वैध नेपाली नम्बर दिनुहोस्।"
                        }
                    },
                    'seah-other': {
                        1: {
                            'en': "Please enter your phone number as the reporting person. Nepali phone number starts with 9 and should be 10 digits long. You can skip this if you prefer not to share it.",
                            'ne': "रिपोर्ट गर्ने व्यक्तिको रूपमा आफ्नो फोन नम्बर दिनुहोस्। नेपाली नम्बर 9 बाट सुरु भई 10 अंकको हुनुपर्छ। दिन नचाहेमा छोड्न सक्नुहुन्छ।"
                        },
                        2: {
                            'en': "The reporting person's phone number is not valid. Please provide a valid Nepali number starting with 9 and 10 digits long.",
                            'ne': "रिपोर्ट गर्ने व्यक्तिको फोन नम्बर मान्य छैन। कृपया 9 बाट सुरु हुने 10 अंकको वैध नेपाली नम्बर दिनुहोस्।"
                        }
                    },
                    'seah-focal': {
                        'reporter': {
                            1: {
                                'en': "As a SEAH focal point, please enter your phone number. Nepali phone number starts with 9 and should be 10 digits long. This is required.",
                                'ne': "SEAH फोकल पर्सनको रूपमा रिपोर्टर सम्पर्कका लागि आफ्नो फोन नम्बर दिनुहोस्। नेपाली नम्बर 9 बाट सुरु भई 10 अंकको हुनुपर्छ। नचाहेमा छोड्न सक्नुहुन्छ।"
                            },
                            2: {
                                'en': "The focal reporter phone number is not valid. Please provide a valid Nepali number starting with 9 and 10 digits long.",
                                'ne': "फोकल रिपोर्टरको फोन नम्बर मान्य छैन। कृपया 9 बाट सुरु हुने 10 अंकको वैध नेपाली नम्बर दिनुहोस्।"
                            }
                        },
                        'complainant': {
                            1: {
                                'en': "Please enter the affected person's phone number for follow-up if consented. Nepali phone number starts with 9 and should be 10 digits long. You can skip if it is unavailable.",
                                'ne': "सहमति भएमा फलो-अपका लागि प्रभावित व्यक्तिको फोन नम्बर दिनुहोस्। नेपाली नम्बर 9 बाट सुरु भई 10 अंकको हुनुपर्छ। उपलब्ध नभए छोड्न सक्नुहुन्छ।"
                            },
                            2: {
                                'en': "The affected person's phone number is not valid. Please provide a valid Nepali number starting with 9 and 10 digits long.",
                                'ne': "प्रभावित व्यक्तिको फोन नम्बर मान्य छैन। कृपया 9 बाट सुरु हुने 10 अंकको वैध नेपाली नम्बर दिनुहोस्।"
                            }
                        }
                    }
                },
                'buttons': {
                1: BUTTONS_SKIP
            }
        },
        'action_ask_complainant_location_consent': {
            'utterances': {
                1: {
                    'en': "Do you want to provide the location details for your grievance. This is optional, your grievance can be filed without it.",
                    'ne': "के तपाईं आफ्नो गुनासोको लागि स्थान विवरण प्रदान गर्न चाहनुहुन्छ? यो वैकल्पिक हो, तपाईंको गुनासो यस बिना पनि दर्ता गर्न सक्नुहुन्छ।"
                }
            },
            'profile_utterances': {
                'seah-other': {
                    1: {
                        'en': "Would you like to provide location details for the incident you are reporting? This is optional.",
                        'ne': "तपाईंले रिपोर्ट गरिरहेको घटनाको स्थान विवरण दिन चाहनुहुन्छ? यो वैकल्पिक हो।"
                    }
                },
                'seah-focal': {
                    'reporter': {
                        1: {
                            'en': "Would you like to share your location as the reporting focal person? This is optional.",
                            'ne': "रिपोर्ट गर्ने फोकल पर्सनको रूपमा आफ्नो स्थान दिन चाहनुहुन्छ? यो वैकल्पिक हो।"
                        }
                    },
                    'complainant': {
                        1: {
                            'en': "Would you like to provide the affected person's grievance location details? This is optional.",
                            'ne': "प्रभावित व्यक्तिको गुनासो सम्बन्धी स्थान विवरण दिन चाहनुहुन्छ? यो वैकल्पिक हो।"
                        }
                    }
                }
            },
            'buttons': {
                1: BUTTONS_AFFIRM_DENY
            }
        },
        'action_ask_complainant_municipality_temp': {
            'utterances': {
                1: {
                    'en': "To provide the Municipality where the incident happened, please enter a valid municipality name. You may Skip if you do not want to share or you do not know the location.",
                    'ne': "कृपया {municipality} मा घटना भएको नगरपालिकाको आधाकारिक नाम प्रविष्ट गर्नुहोस्  (कम्तिमा ३ अक्षर) ।  यदि तपाईं साझा गर्न चाहनुहुन्न वा तपाईंलाई स्थान थाहा छैन भने तपाईं स्किप गर्न सक्नुहुन्छ।",
                }
            },
            'buttons': {
                1: BUTTONS_SKIP
            }
        },
        'action_ask_complainant_municipality_confirmed': {
            'utterances': {
                1: {
                    'en': "Is {validated_municipality} your correct municipality?",
                    'ne': "के {validated_municipality} तपाईंको सही नगरपालिका हो?"
                }
            },
            'profile_utterances': {
                'seah-focal': {
                    'complainant': {
                        1: {
                            'en': "Is {validated_municipality} his/her correct municipality?",
                            'ne': "के {validated_municipality} उहाँ/उनीको सही नगरपालिका हो?"
                        }
                    }
                }
            },
            'buttons': {
                1: BUTTONS_AFFIRM_DENY
            }
        },
        'action_ask_complainant_village_temp': {
            'utterances': {
                1: {
                    'en': "Please provide your village name or Skip to skip",
                    'ne': "कृपया आफ्नो गाउँको नाम प्रदान गर्नुहोस् वा छोड्न स्किप गर्नुहोस्"
                }
            },
            'profile_utterances': {
                'seah-focal': {
                    'complainant': {
                        1: {
                            'en': "Please provide his/her village name or Skip to skip",
                            'ne': "कृपया उहाँ/उनीको गाउँको नाम प्रदान गर्नुहोस् वा छोड्न स्किप गर्नुहोस्"
                        }
                    }
                }
            },
            'buttons': {
                1: BUTTONS_SKIP
            }
        },
        'action_ask_complainant_village_confirmed': {
            'utterances': {
                1: {
                    'en': "Is {validated_village} in ward number {validated_ward} your correct village?",
                    'ne': "तपाईले उपलब्ध गराएको गाउँ  {validated_village},  वडा  {validated_ward} को विवरण  सही हो?",
                }
            },
            'profile_utterances': {
                'seah-focal': {
                    'complainant': {
                        1: {
                            'en': "Is {validated_village} in ward number {validated_ward} his/her correct village?",
                            'ne': "के वड नं. {validated_ward} मा रहेको {validated_village} उहाँ/उनीको सही गाउँ हो?"
                        }
                    }
                }
            },
            'buttons': {
                1: BUTTONS_AFFIRM_DENY
            }
        },
        'action_ask_complainant_ward': {
            'utterances': {
                1: {
                    'en': "Please provide your ward number (number between 1 and 20) or Skip to skip",
                    'ne': "कृपया आफ्नो वडा नम्बर प्रदान गर्नुहोस् (१ बाट २० बीचको संख्या) वा छोड्नको लागि  स्किप गर्नुहोस्",
                }
            },
            'profile_utterances': {
                'seah-focal': {
                    'complainant': {
                        1: {
                            'en': "Please provide his/her ward number (number between 1 and 20) or Skip to skip",
                            'ne': "कृपया उहाँ/उनीको वड नम्बर प्रदान गर्नुहोस् (१ देखि २० बीचको) वा छोड्न स्किप गर्नुहोस्"
                        }
                    }
                }
            },
            'buttons': {    
                1: BUTTONS_SKIP
            }
        },
        'action_ask_complainant_address_temp': {
            'utterances': {
                1: {
                    'en': "Please provide your address or Skip to skip",
                    'ne': "कृपया आफ्नो ठेगाना प्रदान गर्नुहोस् वा छोड्न स्किप गर्नुहोस्"
                }
            },
            'profile_utterances': {
                'seah-focal': {
                    'complainant': {
                        1: {
                            'en': "Please provide his/her address or Skip to skip",
                            'ne': "कृपया उहाँ/उनीको ठेगाना प्रदान गर्नुहोस् वा छोड्न स्किप गर्नुहोस्"
                        }
                    }
                }
            },
            'buttons': {
                1: BUTTONS_SKIP
            }
        },
        'action_ask_complainant_address_confirmed': {
            'utterances': {
                1: {
                    'en': "Thank you for providing your location details:\n- Municipality: {municipality}\n- Village: {village}\n- Address: {address}\nIs this correct?",
                    'ne': "तपाईंको स्थान विवरण प्रदान गर्नुभएकोमा धन्यवाद:\n- नगरपालिका: {municipality}\n- गाउँ: {village}\n- ठेगाना: {address}\nके यो सही हो?"
                }
            },
            'profile_utterances': {
                'seah-focal': {
                    'complainant': {
                        1: {
                            'en': "Thank you for providing his/her location details:\n- Municipality: {municipality}\n- Village: {village}\n- Address: {address}\nIs this correct?",
                            'ne': "उहाँ/उनीको स्थान विवरण प्रदान गर्नुभएकोमा धन्यवाद:\n- नगरपालिका: {municipality}\n- गाउँ: {village}\n- ठेगाना: {address}\nके यो सही हो?"
                        }
                    }
                }
            },
            'buttons': {
                1: BUTTONS_AFFIRM_DENY
            }
        },
        'action_ask_complainant_province': {
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
        'action_ask_complainant_district': {
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
        'action_ask_complainant_consent': {
            'utterances': {
                1: {
                    'en': "Would you like to provide your contact information? You can file anonymously but we won't be able to contact you for follow-up or updates.",
                    'ne': "के तपाईं आफ्नो सम्पर्क जानकारी प्रदान गर्न चाहनुहुन्छ? तपाईं गुमनाम रहन सक्नुहुन्छ तर हामी तपाईंलाई अनुवर्ती वा अपडेटको लागि सम्पर्क गर्न सक्नुहुनेछैनौं।"
                }
            },
            'profile_utterances': {
                'seah-victim': {
                    1: {
                        'en': "Would you like to share your contact information for confidential SEAH follow-up? You can continue without sharing it.",
                        'ne': "गोप्य SEAH फलो-अपका लागि आफ्नो सम्पर्क जानकारी दिन चाहनुहुन्छ? नदिई पनि अगाडि बढ्न सक्नुहुन्छ।"
                    }
                },
                'seah-other': {
                    1: {
                        'en': "Would you like to share your contact information as the reporting person? This helps us reach you for follow-up updates.",
                        'ne': "रिपोर्ट गर्ने व्यक्तिको रूपमा आफ्नो सम्पर्क जानकारी दिन चाहनुहुन्छ? यसले फलो-अप अपडेटका लागि तपाईंलाई सम्पर्क गर्न मद्दत गर्छ।"
                    }
                },
                'seah-focal': {
                    'reporter': {
                        1: {
                            'en': "As a SEAH focal point, would you like to share your contact details for reporter follow-up?",
                            'ne': "SEAH फोकल पर्सनको रूपमा रिपोर्टर फलो-अपका लागि आफ्नो सम्पर्क विवरण दिन चाहनुहुन्छ?"
                        }
                    },
                    'complainant': {
                        1: {
                            'en': "Would you like to share the affected person's contact details for confidential follow-up, if consented?",
                            'ne': "सहमति भएमा गोप्य फलो-अपका लागि प्रभावित व्यक्तिको सम्पर्क विवरण दिन चाहनुहुन्छ?"
                        }
                    }
                }
            },
            'buttons': {
                1: BUTTONS_AFFIRM_DENY
            }
        },
        'action_ask_complainant_full_name': {
            'utterances': {
                1: {
                    'en': "Please enter the name you want us to address you by. We recommend you to enter your full name with first name, middle name and last name for better identification. You can skip this if you prefer to remain anonymous.",
                    'ne': "कृपया हामीले तपाईलाई सम्बोधन गर्न चाहेको नाम प्रविष्ट गर्नुहोस्। तपाईको सहि पहिचानको लागि आफ्नो पुरा नाम थर  (पहिलो नाम, बिचको  नाम र थर) प्रविष्ट गर्नुहोस्। यदि तपाई बेनामी  रहन चाहनुहुन्छ भने यसलाई स्किप गर्न सक्नुहुन्छ।",
                },
                2: {
                    'en': "Please enter your full name. We recommend you to enter your full name with first name, middle name and last name for better identification. You can skip this if you prefer to remain anonymous.",
                    'ne': "तपाईको सहि पहिचानको लागि आफ्नो पुरा नाम थर  (पहिलो नाम, मध्य नाम र अन्तिम नाम) प्रविष्ट गर्नुहोस्। यदि तपाईं बेनामी  रहन चाहनुहुन्छ भने यसलाई स्किप गर्न सक्नुहुन्छ।",
                }
            },
            'profile_utterances': {
                'seah-other': {
                    1: {
                        'en': "Please enter your full name as the reporting person. You can skip this if you prefer not to share it.",
                        'ne': "रिपोर्ट गर्ने व्यक्तिको रूपमा आफ्नो पूरा नाम दिनुहोस्। दिन नचाहेमा छोड्न सक्नुहुन्छ।"
                    },
                    2: {
                        'en': "Please enter your full name as the reporting person. You can skip this if you prefer not to share it.",
                        'ne': "रिपोर्ट गर्ने व्यक्तिको रूपमा आफ्नो पूरा नाम दिनुहोस्। दिन नचाहेमा छोड्न सक्नुहुन्छ।"
                    }
                },
                'seah-focal': {
                    'reporter': {
                        1: {
                            'en': "As a SEAH focal point, please enter your full name as the reporting person.",
                            'ne': "SEAH फोकल पर्सनको रूपमा रिपोर्टरको हैसियतले आफ्नो पूरा नाम दिनुहोस्। आवश्यक परे छोड्न सक्नुहुन्छ।"
                        },
                        2: {
                            'en': "As a SEAH focal point, please enter your full name as the reporting person.",
                            'ne': "SEAH फोकल पर्सनको रूपमा रिपोर्टरको हैसियतले आफ्नो पूरा नाम दिनुहोस्। आवश्यक परे छोड्न सक्नुहुन्छ।"
                        }
                    },
                    'complainant': {
                        1: {
                            'en': "Please enter the affected person's full name. You can skip this if they prefer anonymity.",
                            'ne': "प्रभावित व्यक्तिको पूरा नाम दिनुहोस्। उनीहरूले गुमनाम रहन चाहेमा छोड्न सक्नुहुन्छ।"
                        },
                        2: {
                            'en': "Please enter the affected person's full name. You can skip this if they prefer anonymity.",
                            'ne': "प्रभावित व्यक्तिको पूरा नाम दिनुहोस्। उनीहरूले गुमनाम रहन चाहेमा छोड्न सक्नुहुन्छ।"
                        }
                    }
                }
            },
            'buttons': {
                1: BUTTONS_SKIP
            }
        },
        'action_ask_complainant_email_temp': {
            'utterances': {
                1: {
                    'en': "Please enter your email address so we can contact you for any needed follow-up. Skip if you do not want to share it.",
                    'ne': "कृपया आफ्नो इमेल ठेगाना प्रविष्ट गर्नुहोस्, जसबाट आवश्यक फलो-अपको लागि हामी तपाईलाई सम्पर्क गर्न सकौं। यदि तपाई साझा गर्न चाहनुहुन्न भने यसलाई स्किप गर्न सक्नुहुन्छ।",
                }
            },
            'profile_utterances': {
                'seah-other': {
                    1: {
                        'en': "Please enter your contact email as the reporting person. You can skip this if you prefer not to share it.",
                        'ne': "रिपोर्ट गर्ने व्यक्तिको रूपमा आफ्नो सम्पर्क इमेल दिनुहोस्। दिन नचाहेमा छोड्न सक्नुहुन्छ।"
                    }
                },
                'seah-focal': {
                    'reporter': {
                        1: {
                            'en': "Reporter email is optional in this focal stage. You can type skip and continue; affected person email is collected later when applicable.",
                            'ne': "यो फोकल रिपोर्टर चरणमा इमेल वैकल्पिक हो। skip टाइप गरेर अगाडि बढ्न सक्नुहुन्छ; आवश्यक परे प्रभावित व्यक्तिको इमेल पछि लिइन्छ।"
                        }
                    },
                    'complainant': {
                        1: {
                            'en': "Please enter the affected person's contact email. You can skip this if they prefer not to share it.",
                            'ne': "प्रभावित व्यक्तिको सम्पर्क इमेल दिनुहोस्। उनीहरूले दिन नचाहेमा छोड्न सक्नुहुन्छ।"
                        }
                    }
                }
            },
            'buttons': {
                1: BUTTONS_SKIP
            }
        },
        'action_ask_complainant_email_confirmed': {
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
    },
    "form_contact": {
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
        'validate_complainant_village_temp': {
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
        'validate_complainant_address_confirmed': {
            'utterances': {
                1: {
                    'en': "Please enter your correct village and address",
                    'ne': "कृपया आफ्नो सही गाउँ र ठेगाना प्रविष्ट गर्नुहोस्।",
                }
            }
        },
        'validate_complainant_email_temp': {
            'utterances': {
                1: {
                    # Reuse the generic email prompt text for invalid email format
                    'en': "The email you provided is not valid. Please enter a valid email address, or type 'skip' if you prefer to remain anonymous.",
                    'ne': "तपाईले प्रदान गर्नुभएको इमेल सही छैन। कृपया सही इमेल ठेगाना प्रविष्ट गर्नुहोस्, वा बेनामी रहन चाहनुहुन्छ भने 'skip' टाइप गर्नुहोस्।",
                }
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
                    'ne': "राम्रो!  तपाईको गुनासो बुझेर सुरु गरौं...",
                }
            }
        },
         'action_ask_grievance_new_detail': {
            'utterances': {
                1: {
                    'en': "Great! Let's start by understanding your grievance...",
                    'ne': "राम्रो! चल्नुस् तपाईंको गुनासो बुझेर सुरु गरौं..."
                },
                2: {
                    'en': "Lets restart, please enter your grievance details...",
                    'ne': "प्रक्रिया पुनः सुरु गर्नुहोस्, कृपया आफ्नो गुनासो विवरणहरु प्रविष्ट गर्नुहोस्... ",
                },
                3: {
                    'en': "Please enter more details...",
                    'ne': "कृपया थप विवरण प्रविष्ट गर्नुहोस्..."
                },
                4: {
                    'en': """Thank you for your entry: "{grievance_description}\n. 
                    Do you want to add more details to your grievance, such as:\n
                    - Location information\n
                    - Persons involved\n
                    - Quantification of damages (e.g., number of bags of rice lost)\n"
                    - Monetary value of damages""",
                    'ne': """तपाईंको प्रविष्टिको लागि धन्यवाद। "{grievance_description}                                             
.     के तपाई आफ्नो गुनासोमा थप विवरणहरू थप्न चाहनुहुन्छ, जस्तै: 
                    - स्थान जानकारी
                    -  संलग्न व्यक्तिहरू सम्बन्धमा
                    -  क्षतिको परिमाण निर्धारण (जस्तै, हराएको चामलको बोराको संख्या)"
                    - क्षतिको मौद्रिक मूल्य""",
                }
            },
            'buttons': {
                4: BUTTONS_GRIEVANCE_SUBMISSION
            }
        }
    },
    'action_submit_grievance': {
        'action_submit_grievance': {
            'utterances': {
                1: {
                    'en': "Your grievance has been filed successfully.",
                    'ne': "तपाईंको गुनासो सफलतापूर्वक दर्ता गरिएको छ।"
                },
                2: {
                    'en': "✅ A recap of your grievance has been sent to your phone : {complainant_phone}.",
                    'ne': "✅ तपाईको गुनासोको सारांश तपाईको फोनमा पठाइएको छ। {complainant_phone}",
                },
                3: {
                    'en': "✅ A recap of your grievance has been sent to your email : {complainant_email}.",
                    'ne': "✅ तपाईको गुनासोको सारांश तपाईंको इमेलमा पठाइएको छ। {complainant_email}",
                },
                4: {
                    'en': "I apologize, but there was an error submitting your grievance. Please try again or contact support.",
                    'ne': "मलाई माफ गर्नुहोस्, तर तपाईंको गुनासो दर्ता गर्दै गर्दा त्रुटि भयो। कृपया पुनः प्रयास गर्नुहोस् वा सहयोग सम्पर्क गर्नुहोस्।"
                },
            },
        },
        'action_grievance_outro': {
            'utterances': {
                1: {
                    'en': "Your grievance has been filed, we recommend that you contact the One Stop Crisis Management Centre of Morang where special support will be provided to you.",
                    'ne': "तपाईको गुनासो दर्ता गरिएको छ, हामी तपाईलाई मोरङको एकल बिन्दु विपत व्यवस्थापन केन्द्रमा सम्पर्क गर्न अनुरोध गर्दछौं जहाँबाट तपाईलाई विशेष सहयोग प्रदान गरिनेछ।",
                },
                2: {
                    'en': "You have not attached any files. You can still attach them now by clicking on the attachment button below.",
                    'ne': "तपाईले कुनै पनि फाइल संलग्न गर्नुभएको छैन। तलको संलग्न बटन प्रयोग  गरेर तपाई अझै पनि फाइल संलग्न गर्न सक्नुहुन्छ। ",
                },
                3: {
                    'en': "You can still attach more files to your grievance  by clicking on the attachment button below.",
                    'ne': "तलको संलग्न बटन प्रयोग गरेर तपाईले आफ्नो गुनासोका थप फाइलहरू संलग्न गर्न सक्नुहुन्छ।",
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
                    'ne': "✅ तपाईको गुनासोको सारांश तपाईको इमेलमा पठाइएको छ। {complainant_email}",
                },
                3: {
                    'en': "✅ A recap of your grievance has been sent to your phone : {complainant_phone}.",
                    'ne': "✅ तपाईको गुनासोको सारांश तपाईको फोनमा पठाइएको छ। {complainant_phone}",
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
    'action_seah_outro': {
        'action_seah_outro': {
            'utterances': {
                1: {
                    'en': "Thank you for reporting this incident. This confidential SEAH report has been submitted. Your reference number is available in this chat.",
                    'ne': "रिपोर्ट गर्नुभएकोमा धन्यवाद। तपाईको गोप्य SEAH रिपोर्ट पेश गरिएको छ। तपाईको सन्दर्भ नम्बर यस च्याटमा उपलब्ध छ।",
                },
                2: {
                    'en': "Thank you for reporting this incident. This confidential SEAH report has been submitted. Here are support services that may help victim-survivors: [list to be provided].",
                    'ne': "रिपोर्ट गर्नुभएकोमा धन्यवाद। तपाईको गोप्य SEAH रिपोर्ट पेश गरिएको छ। मद्दतका लागि सहायता सेवाहरू यहाँ छन्: [list to be provided]।",
                },
                3: {
                    'en': "Thank you. We may contact you using the phone number you provided, if needed for follow-up.",
                    'ne': "धन्यवाद। फलो-अपको लागि आवश्यक परेमा, हामी तपाईले प्रदान गर्नुभएको फोन नम्बरमा  तपाईलाई सम्पर्क गर्न सक्छौं।",
                },
                4: {
                    'en': "Thank you. Your report is confidential. If you did not share contact details, please reach a SEAH support point (below) if you need help.",
                    'ne': "धन्यवाद। तपाईको रिपोर्ट गोप्य छ।  तपाईले सम्पर्क विवरणहरू साझा गर्नुभएको छैन भने र तपाईलाई मद्दत चाहिएमा  कृपया तलको  SEAH सहायता बिन्दुमा (तल) सम्पर्क गर्नुहोस्।",
                },
                5: {
                    'en': "Thank you. Your report is confidential. We may use the contact details you provided as agreed.",
                    'ne': "धन्यवाद। तपाईले सहमति अनुसार प्रदान गर्नुभएको सम्पर्क विवरणहरू हामी  प्रयोग गर्न सक्छौं। ",
                },
            },
            'buttons': {
                1: BUTTONS_SEAH_OUTRO,
            },
        },
    },
    'form_grievance_complainant_review': {
        'validate_form_grievance_complainant_review': {
            'utterances': {
                1: {
                    'en': "No category selected. skipping this step.",
                    'ne': "कुनै समूह चयन गरिएको छैन। यस चरण छोड्नुहोस्।",
                }
            }
        },
        'action_ask_form_grievance_complainant_review_grievance_classification_consent': {
            'utterances': {
                1: {
                    'en': "We have generated categories and summary for your grievance. They will help our officer to treat your grievance faster. Do you want to review if they are correct and possibly answer one more question?",
                    'ne': "हामीले तपाईको गुनासोको लागि समुहहरू र सारांश उत्पन्न गरिएको छ। यसले  हाम्रा अधिकारीलाई तपाईंको गुनासो छिटो सम्बोधन गर्न मद्दत गर्नेछन्। के तपाई यो सही छ कि छैन भनेर समीक्षा गर्न चाहनुहुन्छ र अर्को एक प्रश्न जाँच गर्न चाहनुहुन्छ? ",
                }
            },
            'buttons': {
                1: BUTTONS_AFFIRM_DENY
            }
        },
        'action_ask_form_grievance_complainant_review_grievance_categories_status': {
            'utterances': {
                1: {
                    'en': """
                    Here are the categories suggested by our classification:\n{category_text}\nDoes this seem correct?""",
                    'ne': """हाम्रो वर्गीकरणद्वारा सुझाव गरिएका समूहहरु यहाँ छन्: 
      {category_text}
के यो सही देखिन्छ?""",
                },
                2: {
                    'en': "We have not identified any categories for your grievance.",
                    'ne': "हामीले तपाईंको गुनासोको लागि कुनै पनि समूह पहिचान गरेका छैनौं। ",
                },
                3: {
                    'en': "Here is the list of modified categories:\n{category_text}\nDoes this seem correct?",
                    'ne': """यहाँ संशोधित श्रेणीहरू छन्:
{category_text}
के यो सही देखिन्छ?""",
                },
                4: {
                    'en': "You have removed all the categories, is it correct",
                    'ne': "तपाईले सबै समूहहरू हटाउनुभएको छ, के यो सही छ?",
                }
            },
            'buttons': {
                1: {
                    'en': [
                        {"title": "Yes", "payload": "/slot_confirmed"},
                        {"title": "Add category", "payload": "/slot_added"},
                        {"title": "Delete category", "payload": "/slot_deleted"},
                        BUTTON_SKIP_EN
                    ],
                    'ne': [
                        {"title": "हो", "payload": "/slot_confirmed"},
                        {"title": "श्रेणी थप्नुहोस्", "payload": "/slot_added"},
                        {"title": "श्रेणी हटाउनुहोस्", "payload": "/slot_deleted"},
                        BUTTON_SKIP_NE
                    ]
                },
                2: {'en' :[
                    {"title": "Add category", "payload": "/slot_added"},
                    {"title": "Continue without categories", "payload": "/slot_confirmed"},
                    BUTTON_SKIP_EN
                    ],
                    'ne': [
                        {"title": "श्रेणी थप्नुहोस्", "payload": "/slot_added"},
                        {"title": "श्रेणी छोड्नुहोस्", "payload": "/slot_confirmed"},
                        BUTTON_SKIP_NE
                    ]
                }
            }
        },
        'action_ask_form_grievance_complainant_review_grievance_cat_modify': {
            'utterances': {
                1: {
                    'en': "No categories selected. Skipping this step.",
                    'ne': "कुनै श्रेणी चयन गरिएको छैन। यस चरण छोड्नुहोस्।"
                },
                2: {
                    'en': "Which category would you like to delete? Skip if you don't want to delete any category.",
                    'ne': "तपाई कुन समुह हटाउन चाहनुहुन्छ?  यदि तपाईं कुनै पनि समुह हटाउन चाहनुहुन्न भने स्किप गर्नुहोस्।",
                },
                3: {
                    'en': "Select the category you want to add from the list below, Skip if you don't want to add any category.",
                    'ne': "तलको सूचीबाट तपाईले थप्न चाहनुभएको समुह चयन गर्नुहोस्, यदि तपाई कुनै पनि समुह थप्न चाहनुहुन्न भने स्किप गर्नुहोस्।",
                }
            }
        },
        'action_ask_form_grievance_complainant_review_grievance_summary_status': {
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
                    BUTTON_SKIP_EN
                    ],
                    'ne': [
                        {"title": "सारांश सुनिश्चित गर्नुहोस्", "payload": "/slot_confirmed"},
                        {"title": "सारांश संपादन गर्नुहोस्", "payload": "/slot_edited"},
                        BUTTON_SKIP_NE
                    ]
                },
                2: {'en':[
                    {"title": "Edit summary", "payload": "/slot_edited"},
                    BUTTON_SKIP_EN
                    ],
                    'ne': [
                        {"title": "सारांश संपादन गर्नुहोस्", "payload": "/slot_edited"},
                        BUTTON_SKIP_NE
                    ]
                }
            }
        },
        'action_ask_form_grievance_complainant_review_grievance_summary_temp': {
            'utterances': {
                1: {
                    'en': "Please enter the new summary and confirm again.",
                    'ne': "कृपया नयाँ सारांश प्रविष्ट गर्नुहोस् र फेरी सुनिश्चित गर्नुहोस्।"
                }
            }
        },
        'action_retrieve_classification_results': {
            'utterances': {
                1: {
                    'en': "Categorization of your grievance is available.",
                    'ne': "तपाईको गुनासोको लागि समुहहरु उपलब्ध गरिएको छ। ",
                },
                2: {
                    'en': "Categorization of your grievance is not available. Our officer will review your grievance and contact you soon.",
                    'ne': "तपाईको गुनासोको समूह उपलब्ध छैन।  हाम्रा अधिकारीले तपाईको गुनासोको समीक्षा गर्नेछन् र चाँडै तपाईलाई सम्पर्क गर्नेछन्। ",
                }
            }
        },
        'action_ask_form_grievance_complainant_review_sensitive_issues_follow_up': SENSITIVE_ISSUES_UTTERANCES_AND_BUTTONS,  
       
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
        'action_main_menu': {
            'utterances': {
                1: {
                    'en': "Hello! Welcome to the Grievance Management Chatbot.\nI am here to help you file a grievance or check its status. What would you like to do?",
                    'ne': "नमस्कार! गुनासो व्यवस्थापन च्याटबटमा स्वागत छ।\nम तपाईंलाई गुनासो दर्ता गर्न वा यसको स्थिति जाँच गर्न मद्दत गर्न यहाँ छु। तपाईं के गर्न चाहनुहुन्छ?"
                },
                2: {
                    'en': "Hello! Welcome to the Grievance Management Chatbot.\nYou are reaching out to the office of {district} in {province}.\nI am here to help you file a grievance or check its status. What would you like to do?",
                    'ne': "नमस्कार! गुनासो व्यवस्थापन च्याटबटमा स्वागत छ।\nतपाईं {province} मा {district} को कार्यालयमा सम्पर्क गर्दै हुनुहुन्छ।\nम तपाईंलाई गुनासो दर्ता गर्न वा यसको स्थिति जाँच गर्न मद्दत गर्न यहाँ छु। तपाईं के गर्न चाहनुहुन्छ?"
                },
                3: {
                    'en': "Hello! Welcome to the Grievance Management Chatbot.\nYou are reaching out from {package_label}, {district} District.\nI am here to help you file a grievance or check its status. What would you like to do?",
                    'ne': """नमस्कार! गुनासो व्यवस्थापन च्याटबटमा स्वागत छ।
तपाईं {package_label}, {district} जिल्लाबाट सम्पर्क गर्दै हुनुहुन्छ।
म तपाईलाई गुनासो दर्ता गर्न वा यसको स्थिति जाँच गर्न मद्दत गर्न तयार छु। तपाईं के गर्न चाहनुहुन्छ? """,
                }
            },
            'buttons': {
                1: {
                    'en': [
                        {"title": "File a grievance", "payload": "/new_grievance"},
                        {"title": "Report sexual exploitation, sexual abuse, and sexual harassment", "payload": "/seah_intake"},
                        {"title": "Check my status", "payload": "/start_status_check"},
                        {"title": "Exit", "payload": "/goodbye"}
                    ],
                    'ne': [
                        {"title": "गुनासो दर्ता गर्नुहोस्", "payload": "/new_grievance"},
                        {"title": "SEAH/SEIA उजुरी दर्ता गर्नुहोस्", "payload": "/seah_intake"},
                        {"title": "स्थिति जाँच गर्नुहोस्", "payload": "/start_status_check"},
                        {"title": "बाहिर निस्कनुहोस्", "payload": "/goodbye"}
                    ]
                }
            }
        },
        'action_outro': {
            'utterances': {
                1: {
                    'en': "Thank you for using the Grievance Management Chatbot. Have a great day!",
                    'ne': "गुनासो व्यवस्थापन च्याटबट प्रयोग गर्नुभएकोमा धन्यवाद। तपाईंको दिन शुभ रहोस्!",
                }
            }
        },
        'action_set_current_process': {
            'utterances': {
                1: {
                    'en': "You are currently in the process of {story_current}.",
                    'ne': "तपाई हाल निम्न प्रक्रियामा हुनुहुन्छ {story_current} ",
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
        'action_show_story_current': {
            'utterances': {
                1: {
                    'en': "You are currently in the {story_current} process.",
                    'ne': "तपाई हाल {story_current} प्रक्रियामा हुनुहुन्छ।",
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
                    'ne': "बाहिर निस्कनुहोस्! यदि तपाईंलाई अधिक मद्दत चाहिनुहुन्छ भने, कृपया प्रश्न गर्नुहोस्।"
                }
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
                    'ne': "फाइलहरू संलग्न गर्न, कृपया संलग्नक बटनमा क्लिक गर्नुहोस्।",
                }
            }
        }
    },
    'form_otp': {
        'action_ask_otp_consent': {
            'utterances': {
                # 1: Modify-grievance / new-grievance flow – OTP optional
                1: {
                    'en': "Do you want to verify your phone number so we can safely contact you? If you don't confirm the number, we will keep it for reference but will not contact you.",
                    'ne': "के तपाईं आफ्नो फोन नम्बर सत्यापन गर्न चाहनुहुन्छ? यदि तपाईं सत्यापन गर्न चाहनुहुन्न भने, हामी नम्बर सन्दर्भको लागि राख्छौं तर तपाईंलाई सम्पर्क गर्ने छैनौं।",
                },
                # 2: Status-check flow – OTP mandatory to access grievance
                2: {
                    'en': "You must verify your phone number to access your grievance and make changes. Without verification, you can only request a follow-up.",
                    'ne': "तपाईको गुनासो पहुँच र परिवर्तन गर्न तपाईंले आफ्नो फोन नम्बर प्रमाणित गर्नुपर्छ।  फोन नम्बर  प्रमाणीकरण बिना, तपाईंले केवल फलो-अप अनुरोध मात्र गर्न सक्नुहुन्छ। ",
                }
            },
            'buttons': {
                1: BUTTONS_OTP_CONSENT,
                2: BUTTONS_OTP_CONSENT
            },

        },
        'base_validate_phone': {
            'utterances': {
                1: {
                    'en': "The phone number you provided is not valid. Please enter a valid 10-digit Nepali mobile number starting with 9, or type 'skip' to continue without it.",
                    'ne': "तपाईले प्रदान गर्नुभएको फोन नम्बर मान्य छैन। कृपया ९ बाट सुरु हुने १० अङ्कको मान्य नेपाली मोबाइल नम्बर प्रविष्ट गर्नुहोस्, वा  बिना नम्बर अघि बढ्न 'skip' टाइप गर्नुहोस्। ",
                }
            }
        },
        'validate_otp_input': {
            'utterances': {
                1: {
                    'en': "OTP verified successfully",
                    'ne': "OTP सफलतापूर्वक प्रमाणित भयो।",
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
                1: BUTTONS_OTP_VERIFICATION
            }
        }
    },
    'form_seah_1': {
        'action_ask_form_seah_1_sensitive_issues_follow_up': {
            'utterances': {
                1: {
                    'en': "Would you like to file this report anonymously or with contact details?",
                    'ne': "तपाई यो गुनासो बेनामी रूपमा दर्ता गर्न चाहनुहुन्छ वा सम्पर्क विवरणहरू सहित? ",
                },
                2: {
                    'en': "Please choose anonymous grievance or grievance with contact details.",
                    'ne': "कृपया बेनामी गुनासो वा सम्पर्क विवरण सहितको गुनासो छनौट गर्नुहोस्।",
                }
            },
            'buttons': {
                1: BUTTONS_SEAH_IDENTITY_MODE
            }
        },
        'action_ask_form_seah_1_seah_victim_survivor_role': {
            'utterances': {1: {'en': "Are you:", 'ne': "तपाई कुन भूमिकामा हुनुहुन्छ?"}},
            'buttons': {1: BUTTONS_SEAH_VICTIM_SURVIVOR_ROLE}
        },
        'action_ask_form_seah_1_seah_witness_victim_consent_to_file': {
            'utterances': {
                1: {
                    'en': "Did the victim-survivor agree that you file this complaint?",
                    'ne': "के पीडित व्यक्तिले तपाईलाई यो उजुरी दर्ता गर्न सहमति दिनुभएको छ?",
                }
            },
            'buttons': {1: BUTTONS_SEAH_YES_NO}
        },
        'action_ask_form_seah_1_seah_witness_immediate_danger': {
            'utterances': {
                1: {
                    'en': "Is there an immediate danger to the life of the victim-survivor?",
                    'ne': "के पीडित व्यक्तिको जीवनमा तत्काल खतरा छ?",
                }
            },
            'buttons': {1: BUTTONS_SEAH_YES_NO}
        },
    },
    'form_seah_2': {
        'action_ask_form_seah_2_sensitive_issues_new_detail': {
            'utterances': {
                1: {
                    'en': "Please provide a brief summary of the incident.",
                    'ne': "कृपया घटनाको संक्षिप्त विवरण प्रदान गर्नुहोस्। ",
                },
                2: {
                    'en': """Thank you for your entry: "{grievance_description}".
Do you want to add more details before submission?""",
                    'ne': """तपाईको प्रविष्टिको लागि धन्यवाद: "{grievance_description}"।
के तपाई पेस गर्नु अघि थप विवरण थप्न चाहनुहुन्छ?"""
                },
                3: {
                    'en': "Please add more details.",
                    'ne': "कृपया थप विवरणहरू थप्नुहोस्।",
                }
            },
            'buttons': {
                1: BUTTONS_SKIP,
                2: BUTTONS_GRIEVANCE_SUBMISSION
            }
        },
        'action_ask_form_seah_2_seah_project_identification': {
            'utterances': {1: {'en': "Is the alleged perpetrator employed by an ADB project?", 'ne': "के आरोपित व्यक्ति एडीबी आयोजनामा ​​कार्यरत छन्? "}},
            'buttons': {1: BUTTONS_SEAH_YES_NO}
        },
        'action_ask_form_seah_2_seah_contact_consent_channel': {
            'utterances': {1: {'en': "Do you consent to be contacted for follow-up? Choose one channel.", 'ne': "के तपाई फलो-अपको लागि सम्पर्क गर्न सहमत हुनुहुन्छ? एउटा च्यानल छान्नुहोस्। "}},
            'buttons': {1: BUTTONS_SEAH_CONTACT_CONSENT_CHANNEL}
        },
    },
    'form_seah_focal_point': {
        'action_ask_form_seah_focal_point_1_seah_focal_learned_when': {
            'utterances': {1: {'en': "When did you learn about this incident?", 'ne': "तपाईले यो घटनाको बारेमा कहिले थाहा पाउनुभयो? "}},
            'buttons': {1: BUTTONS_SEAH_FOCAL_LEARNED_WHEN}
        },
        'action_ask_form_seah_focal_point_1_seah_focal_reporter_consent_to_report': {
            'utterances': {1: {'en': "Did the complainant consent to you reporting this here?", 'ne': "के उजुरीकर्ताले तपाईलाई यहाँ यो रिपोर्ट गर्न सहमति दिनुभयो?"}},
            'buttons': {1: BUTTONS_SEAH_YES_NO}
        },
        'action_ask_form_seah_focal_point_1_sensitive_issues_follow_up': {
            'utterances': {1: {'en': "Did the complainant agree to be identified or anonymous?", 'ne': "के उजुरीकर्ता पहिचान सहित वा बेनाम रहन सहमत हुनुहुन्छ?"}},
            'buttons': {1: BUTTONS_SEAH_IDENTITY_MODE}
        },
        'action_ask_form_seah_focal_point_2_seah_project_identification': {
            'utterances': {1: {'en': "Is the alleged perpetrator employed by an ADB project?", 'ne': "के आरोपित व्यक्ति एडीबी आयोजनामा ​​कार्यरत छन्? "}},
            'buttons': {1: BUTTONS_SEAH_YES_NO}
        },
        'action_ask_form_seah_focal_point_2_seah_focal_survivor_risks': {
            'utterances': {1: {'en': "What additional risks to health, safety, or wellbeing are present? Choose an option below, or type your own response.", 'ne': "स्वास्थ्य, सुरक्षा, वा कल्याणको लागि कस्ता थप जोखिमहरू छन्? तलको एउटा विकल्प छान्नुहोस्, वा आफ्नो प्रतिक्रिया टाइप गर्नुहोस्। "}},
            'buttons': {1: BUTTONS_SEAH_FOCAL_SURVIVOR_RISKS}
        },
        'action_ask_form_seah_focal_point_2_seah_focal_mitigation_measures': {
            'utterances': {1: {'en': "In what way have you mitigated these risks? Choose an option below, or type your own response.", 'ne': "तपाईंले यी जोखिमहरूलाई कसरी कम गर्नुभएको छ? तलको एउटा विकल्प छान्नुहोस्, वा आफ्नो प्रतिक्रिया टाइप गर्नुहोस्।"}},
            'buttons': {1: BUTTONS_SEAH_FOCAL_MITIGATION_MEASURES}
        },
        'action_ask_form_seah_focal_point_2_seah_focal_other_at_risk_parties': {
            'utterances': {1: {'en': "Aside from the survivor, who else is at risk? Choose an option below, or type your own response.", 'ne': "पीडित बाहेक, अरू को जोखिममा छन्? तलको विकल्प छान्नुहोस्, वा आफ्नो प्रतिक्रिया टाइप गर्नुहोस्।"}},
            'buttons': {1: BUTTONS_SEAH_FOCAL_OTHER_AT_RISK_PARTIES}
        },
        'action_ask_form_seah_focal_point_2_seah_focal_project_risk': {
            'utterances': {1: {'en': "Is there a risk to the ADB project? Choose an option below, or type your own response.", 'ne': "के एडीबी आयोजनामा ​​कुनै जोखिम छ?  तलको विकल्प छान्नुहोस्, वा आफ्नो प्रतिक्रिया टाइप गर्नुहोस्।"}},
            'buttons': {1: BUTTONS_SEAH_FOCAL_PROJECT_RISK}
        },
        'action_ask_form_seah_focal_point_2_seah_focal_reputational_risk': {
            'utterances': {1: {'en': "Is there reputational risk for ADB?", 'ne': "के एडीबी को प्रतिष्ठामा कुनै जोखिम छ?"}},
            'buttons': {1: BUTTONS_SEAH_YES_NO},
        },
        'action_ask_form_seah_focal_point_2_sensitive_issues_new_detail': {
            'utterances': {
                1: {
                    'en': "Please provide a brief summary of the incident.",
                    'ne': "कृपया घटनाको संक्षिप्त विवरण प्रदान गर्नुहोस्। ",
                },
                2: {
                    'en': """Thank you for your entry: "{grievance_description}".
Do you want to add more details before submission?""",
                    'ne': """तपाईको प्रविष्टिको लागि धन्यवाद: "{grievance_description}"।
के तपाई पेश गर्नु अघि थप विवरणहरू थप्न चाहनुहुन्छ?"""
                },
                3: {
                    'en': "Please add more details.",
                    'ne': "कृपया थप विवरणहरू थप्नुहोस्।",
                }
            },
            'buttons': {
                1: BUTTONS_SKIP,
                2: BUTTONS_GRIEVANCE_SUBMISSION
            }
        },
        'action_ask_form_seah_focal_point_2_seah_contact_consent_channel': {
            'utterances': {1: {'en': "Do you consent to be contacted for follow-up? Choose one channel.", 'ne': "के तपाई फलो-अपको लागि सम्पर्क गर्न सहमत हुनुहुन्छ?  एक च्यानल छान्नुहोस्।"}},
            'buttons': {1: BUTTONS_SEAH_CONTACT_CONSENT_CHANNEL}
        },
        'action_ask_form_seah_focal_point_2_seah_focal_referred_to_support': {
            'utterances': {1: {'en': "Did you refer the complainant to proper support?", 'ne': "के तपाईले उजुरीकर्तालाई उचित सहयोगको लागि सिफारिस गर्नुभयो? "}},
            'buttons': {1: BUTTONS_SEAH_YES_NO}
        },
        'action_outro_sensitive_issues': {
            'utterances': {
                1: {
                    'en': "Thank you for reporting this incident. This confidential SEAH report has been submitted.",
                    'ne': "यो घटना रिपोर्ट गर्नुभएकोमा धन्यवाद। तपाईको गोप्य SEAH रिपोर्ट पेश गरिएको छ। ",
                },
                2: {
                    'en': "Thank you. This does not appear to be an ADB project. We will still handle your report confidentially and share referral/support contacts.",
                    'ne': "धन्यवाद। यो एडीबीको आयोजना जस्तो देखिँदैन। हामी तपाईको रिपोर्टलाई गोप्य रूपमा व्यवस्थापन गर्नेछौं र सिफारिस/सहयोग सम्पर्कहरू उपलब्ध गराउनेछौं।",
                }
            },
            'buttons': {
                1: BUTTONS_CLEAN_WINDOW_OPTIONS
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
                                {"title": "हो", "payload": "/affirm_skip"},
                                {"title": "होइन", "payload": "/deny_skip"}
                            ]
                }
            }
        }
    },
    'form_status_check': {
        'base_validate_phone': {
            'utterances': {
                1: {
                    'en': "The phone number you provided is not valid. Please enter a valid 10-digit Nepali mobile number starting with 9, or type 'skip' to continue without it.",
                    'ne': "तपाईले प्रदान गर्नुभएको फोन नम्बर मान्य छैन। कृपया ९ बाट सुरु हुने १० अङ्कको मान्य नेपाली मोबाइल नम्बर प्रविष्ट गर्नुहोस्, वा  बिना नम्बर अघि बढ्न 'skip' टाइप गर्नुहोस्। ",
                }
            }
        },
        "action_skip_status_check": {
            'utterances': {
                1: {
                    'en': "Our bot cannot provide you with the status of your grievance. Please contact directly the officer in charge at {officer_in_charge_phone} or visit the office in person. {office_name_and_address}",
                    'ne': "हाम्रो बटले तपाईको गुनासोको स्थिति प्रदान गर्न सक्दैन। कृपया अधिकारीको फोन नम्बर {officer_in_charge_phone} मा सम्पर्क गर्नुहोस् वा व्यक्तिगत रूपमा कार्यालयमा उपस्थित भई भेट गर्नुहोस। {office_name_and_address} ",
                }
            }
        },
        "validate_form_status_check": {
            'utterances': {
                1: {
                    'en': "We have matched your full name with the grievance ID {grievance_id}",
                    'ne': "हामीले तपाईंको पूरा नाम गुनासो परिचय {grievance_id} सँग मिलाएका छौं। ",
                },
                2: {
                    'en': "We have found several grievances of closed grievances, we selected the latest one {grievance_id}",
                    'ne': "हामीले बन्द गरिएका गुनासोहरूमध्ये धेरै गुनासोहरू फेला पारेका छौं, हामीले पछिल्लो एउटा गुनासो  छनौट गरेका छौं {grievance_id}।",
                },
                3: {
                    'en': "We have found one grievance with the status {status} and one or several already closed, we selected the latest one {grievance_id}",
                    'ne': "हामीले एउटा गुनासोको अवस्था {status}  सहित  फेला पारेका छौं र एउटा वा धेरै पहिले नै बन्द भइसकेका छन्, हामीले पछिल्लो एउटा  छनौट गरेका छौं  {grievance_id}।    ",
                },
                4: {
                    'en': "We have found several grievances, we selected the latest one {grievance_id}",
                    'ne': "हामीले धेरै गुनासोहरू फेला पारेका छौं, हामीले पछिल्लो एउटा गुनासो  छनौट गरेका छौं {grievance_id}। ",
                }
            }
        },
        "action_ask_status_check_method": {
            'utterances': {
                1: {
                    'en': "You can retrieve your grievance by using your grievance ID or the phone number provided during the filing process.",
                    'ne': "तपाईंले आफ्नो गुनासो परिचय वा  फोन नम्बर प्रयोग गरेर आफ्नो गुनासो पुन: प्राप्त गर्न सक्नुहुन्छ। ",
                }
            },
            'buttons': {
                1: {
                    'en': [
                        {"title": "Phone Number", "payload": "/route_status_check_phone"},
                        {"title": "Grievance ID", "payload": "/route_status_check_grievance_id"},
                        {"title": "Skip", "payload": BUTTON_SKIP},
                    ],
                    'ne': [
                        {"title": "फोन नम्बर", "payload": "/route_status_check_phone"},
                        {"title": "गुनासो ID", "payload": "/route_status_check_grievance_id"},
                        {"title": "छोड्नुहोस्", "payload": BUTTON_SKIP},
                    ],
                }
            },
        },
        'action_ask_status_check_list_grievance_id': {
            'utterances': {
                1: {
                    'en': "Please provide your grievance ID? Alternatively, you can exit by skipping or search by phone number instead.",
                    'ne': "कृपया तपाईको गुनासो परिचय प्रदान गर्नुहोस्? वा वैकल्पिक रूपमा, तपाई स्किप गरेर बाहिर निस्कन सक्नुहुन्छ वा फोन नम्बरद्वारा खोजी गर्न सक्नुहुन्छ। ",
                },
                2: {
                    'en': "We cannot find any grievance associated with this grievance ID. You can try providing another ID or choose to search by phone number or skip to exit",
                    'ne': " हामीले यो गुनासो परिचय  सँग सम्बन्धित कुनै पनि गुनासो फेला पार्न सकेनौं।  तपाईं अर्को परिचय  प्रदान गर्ने प्रयास गर्न सक्नुहुन्छ वा फोन नम्बरद्वारा खोजी गर्न सक्नुहुन्छ वा स्किप  गरेर बाहिर निस्क्न सक्नुहुन्छ। ",
                }
            },
            'buttons': {
                1: {
                    'en': [
                        {"title": "Skip", "payload": BUTTON_SKIP},
                        {"title": "Search by phone number", "payload": "/route_status_check_phone"}
                    ],
                    'ne': [
                        {"title": "छोड्नुहोस्", "payload": BUTTON_SKIP},
                        {"title": "फोन नम्बर सेव्नुहोस्", "payload": "/route_status_check_phone"}
                    ]
                }
            }
        },
        'action_ask_form_status_check_1_complainant_phone': {
            'utterances': {
                1: {
                    'en': "Please provide the phone number associated with your grievance - it should start by 9 and be 10 digits long",
                    'ne': "कृपया तपाईंको गुनासोसँग सम्बन्धित फोन नम्बर प्रदान गर्नुहोस् - यो ९ बाट सुरु हुनुपर्छ र १० अंकको हुनुपर्छ। ",
                },
                2: {
                    'en': "The number you provided is not valid. Please provide a valid number - it should start by 9 and be 10 digits long",
                    'ne': "पाईंले प्रदान गर्नुभएको नम्बर मान्य छैन। कृपया एउटा मान्य नम्बर प्रदान गर्नुहोस् - यो ९ बाट सुरु हुनुपर्छ र १० अङ्कको हुनुपर्छ। ",
                },
                3: {
                    'en': "We cannot find any grievance associated with this phone number. You can try providing another number or skip to exit",
                    'ne': "हामीले यो फोन नम्बरसँग सम्बन्धित कुनै पनि गुनासो फेला पार्न सकेनौं। तपाईं अर्को नम्बर प्रदान गर्ने प्रयास गर्न सक्नुहुन्छ वा स्किप गरेर बाहिर निस्कन सक्नुहुन्छ",
                }
            },
            'buttons': {
                1: BUTTONS_SKIP
            }
        },
        'action_ask_status_check_complainant_full_name': {
            'utterances': {
                1: {
                    'en': "We have found multiple grievances associated with this phone number. Please provide your full name - you will have better chance of matching if you provide your full name with first name, middle name and last name?",
                    'ne': "हामीले यस फोन नम्बरसँग सम्बन्धित धेरै गुनासोहरू फेला पारेका छौं।  कृपया आफ्नो पूरा नाम थर प्रदान गर्नुहोस् - यदि तपाईले आफ्नो पूरा नामको साथ पहिलो नाम, बिचको नाम र थर प्रदान गर्नुभयो भने मिल्ने सम्भावना बढी हुन्छ। ",
                },
                2: {
                    'en': "We didn't find any grievance associated with your full name. Please provide your complete full name again?",
                    'ne': "हामीले तपाईको पूरा नामसँग सम्बन्धित कुनै गुनासो फेला पारेनौं। कृपया पुनः आफ्नो पूरा नाम थर प्रदान गर्नुहोस्। ",
                }
            },
            'buttons': {
                1: BUTTONS_SKIP
            }
        },
        'action_ask_status_check_complainant_full_name_validation_required': {
            'utterances': {
                1: {
                    'en': "Please provide your full name - you will have better chance of matching if you provide your full name with first name, middle name and last name?",
                    'ne': "कृपया आफ्नो पूरा नाम थर प्रदान गर्नुहोस् - यदि तपाईले आफ्नो पूरा नामको साथ पहिलो नाम, बिचको नाम र थर प्रदान गर्नुभयो भने मिल्ने सम्भावना बढी हुन्छ। ",
                }
            }
        },
        'action_ask_form_status_check_skip_valid_province_and_district': {
            'utterances': {
                1: {
                    'en': "We will ask you questions about your location, so we can provide you the contact information of the officer in charge of your grievance.",
                    'ne': "हामी तपाईंको स्थानको बारेमा प्रश्नहरू सोध्नेछौं, ताकि हामी तपाईंको गुनासो हेर्ने अधिकारीको सम्पर्क जानकारी प्रदान गर्न सकौं। ",
                },
                2: {
                    'en': "Are you in {province}, {district}?",
                    'ne': "के तपाई {province}, {district} मा हुनुहुन्छ?",
                },
                3: {
                    'en': "Are you in {province}?",
                    'ne': "के तपाई {province} मा हुनुहुन्छ?",
                },
                4: {
                    'en': "Are you in {district}?",
                    'ne': "के तपाई {district} मा हुनुहुन्छ?",
                }
            },
            'buttons': {
                1: BUTTONS_AFFIRM_DENY
            }
        },
        'action_ask_form_status_check_skip_complainant_province': {
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
        'action_ask_form_status_check_skip_complainant_district': {
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
        'action_ask_form_status_check_skip_complainant_municipality_temp': {
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
        'action_ask_form_status_check_skip_complainant_municipality_confirmed': {
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
        'action_ask_status_check_grievance_id_selected': {
            'utterances': {
                1: {
                    'en': "Please enter the last 6 characters of the grievance ID without the dash like this: JH7707",
                    'ne': "कृपया गुनासो परिचय को अन्तिम ६ अक्षरहरू ड्यास बिना यसरी प्रविष्ट गर्नुहोस्: JH7707 ",
                },
                2: {
                    'en': "You have not provided enough characters. Please enter the last 6 characters of the grievance ID without the dash like this: JH7707",
                    'ne': "तपाईले पर्याप्त वर्णहरू प्रदान गर्नुभएको छैन। कृपया गुनासो परिचय को अन्तिम ६ अक्षरहरू ड्यास बिना यसरी प्रविष्ट गर्नुहोस्: JH7707",
                },
                3: {
                    'en': "We have not found any grievance with that ID. Please try again or choose to search by phone number instead or skip to exit.",
                    'ne': "हामीले त्यो परिचय मा कुनै गुनासो फेला पारेका छैनौं।  कृपया फेरि प्रयास गर्नुहोस् वा फोन नम्बरद्वारा खोजी गर्नुहोस् वा स्किप  गरेर बाहिर निस्क्न सक्नुहुन्छ।",
                },
                4: {
                    'en': "Select any of the grievances if you want to check or amend the details",
                    'ne': "यदि तपाई विवरणहरू जाँच गर्न वा संशोधन गर्न चाहनुहुन्छ भने कुनै पनि गुनासो चयन गर्नुहोस्। ",
                },
                5: {
                    'en': "We have not found any grievance, do you want to try again?",
                    'ne': "हामीले कुनै पनि गुनासो फेला पारेका छैनौं, के तपाईं फेरि प्रयास गर्न चाहनुहुन्छ?",
                }
            },
            'buttons': {
                
                1: {
                    'en': [
                        {"title": "Search by Phone Number", "payload": "/route_status_check_phone"},
                        {"title": "Skip", "payload": BUTTON_SKIP}
                    ],
                    'ne': [
                        {"title": "फोन नम्बर सेव्नुहोस्", "payload": "/route_status_check_phone"},
                        {"title": "छोड्नुहोस्", "payload": BUTTON_SKIP}
                    ]
                },
                2: BUTTONS_SKIP,
            }
        }
        ,
        'action_status_check_request_follow_up': {
            'utterances': {
                1: {
                    'en': "We have received your request for follow up.",
                    'ne': "हामीले तपाईको फलोअप अनुरोध प्राप्त गरेका छौं।",
                },
                2: {
                    'en': "Our officer will follow up on your grievance (ID: {grievance_id}) and contact you shortly on this number: {complainant_phone}.",
                    'ne': "हाम्रो अधिकारीले तपाईंको गुनासो  (ID: {grievance_id}) को बारेमा फलोअप गर्नेछन् र चाँडै नै तपाईको नम्बरमा सम्पर्क गर्नेछन्:  {complainant_phone} ।",
                },
                3: {
                    'en': "We do not have a phone number for this grievance, so we cannot send you a follow-up by SMS. You can add or update your contact details and try again.",
                    'ne': "हामीसँग यो गुनासोको लागि  फोन नम्बर छैन, त्यसैले हामी तपाईंलाई SMS मार्फत फलो-अप पठाउन सक्दैनौं।  तपाईले आफ्नो सम्पर्क विवरणहरू थप्न वा अद्यावधिक गर्न सक्नुहुन्छ र फेरि प्रयास गर्न सक्नुहुन्छ।",
                },
                4: {
                    'en': "The phone number we have has not been verified yet. Please verify your number first so we can contact you for follow-up.",
                    'ne': "हामीसँग भएको फोन नम्बर अझै प्रमाणित भएको छैन। कृपया पहिले आफ्नो नम्बर प्रमाणित गर्नुहोस् ताकि हामी तपाईलाई फलो-अपको लागि सम्पर्क गर्न सकौं। ",
                }
            },
            'buttons': {
                2: {
                    'en': [
                        {"title": "Add missing info", "payload": "/modify_grievance_add_missing_info"},
                        {"title": "Modify grievance", "payload": "/status_check_modify_grievance"},
                        {"title": "Cancel", "payload": "/modify_grievance_cancel"}
                    ],
                    'ne': [
                        {"title": "नभएको जानकारी भर्नुहोस्", "payload": "/modify_grievance_add_missing_info"},
                        {"title": "गुनासो सम्पादन गर्नुहोस्", "payload": "/status_check_modify_grievance"},
                        {"title": "रद्द गर्नुहोस्", "payload": "/modify_grievance_cancel"}
                    ]
                }
            }
        },
        'action_status_check_modify_grievance': {
            'utterances': {
                1: {
                    'en': "You can add documents, add more to your grievance text, or fill in contact or location details you skipped. What would you like to do?",
                    'ne': "तपाईले कागजातहरू थप्न सक्नुहुन्छ, आफ्नो गुनासो लेख  थप्न सक्नुहुन्छ, वा तपाईले छुटाउनुभएको सम्पर्क वा स्थान विवरणहरू भर्न सक्नुहुन्छ। तपाई के गर्न चाहनुहुन्छ?",
                }
            },
            'buttons': {
                1: {
                    'en': [
                        {"title": "Add pictures and documents", "payload": "/modify_grievance_add_pictures"},
                        {"title": "Add more info to my grievance", "payload": "/modify_grievance_add_more_info"},
                        {"title": "Add missing info", "payload": "/modify_grievance_add_missing_info"},
                        {"title": "Exit", "payload": "/exit"}
                    ],
                    'ne': [
                        {"title": "चित्र र कागजात थप्नुहोस्", "payload": "/modify_grievance_add_pictures"},
                        {"title": "मेरो गुनासोमा थप जानकारी थप्नुहोस्", "payload": "/modify_grievance_add_more_info"},
                        {"title": "नभएको जानकारी भर्नुहोस्", "payload": "/modify_grievance_add_missing_info"},
                        {"title": "अन्त्य गर्नुहोस्", "payload": "/exit"}
                    ]
                }
            }
        },
        'action_skip_status_check_outro': {
            'utterances': {
                1: {
                    'en': "To get more information about your grievance, please contact our nearest office:",
                    'ne': "तपाईको गुनासोको बारेमा थप जानकारी प्राप्त गर्न, कृपया हाम्रो नजिकको कार्यालयमा सम्पर्क गर्नुहोस्: ",
                },
                2: {
                    'en': "Name: {office_name}",
                    'ne': "नाम: {office_name}"
                },
                3: {
                    'en': "Address: {office_address}",
                    'ne': "ठेगाना: {office_address}"
                },
                4: {
                    'en': "Phone Number: {office_phone}",
                    'ne': "फोन नम्बर: {office_phone}"
                },
                5: {
                    'en': "PIC Name: {office_pic_name}",
                    'ne': "पिआईसी नाम: {office_pic_name}",
                },
                6: {
                    'en': "Thank you for contacting us. We will get back to you soon.",
                    'ne': "हामीलाई सम्पर्क गर्नुभएकोमा धन्यवाद। हामी चाँडै नै तपाईलाई सम्पर्क गर्नेछौं। ",
                },
                7: {
                    'en': "You have not provided any location information. We cannot provide you the contact information of the officer in charge of your grievance. You can restart the conversation or end the conversation and walk into the nearest KL-road office.",
                    'ne': "तपाईले कुनै पनि स्थान जानकारी प्रदान गर्नुभएको छैन। हामी तपाईको गुनासो हेर्ने अधिकारीको सम्पर्क जानकारी प्रदान गर्न सक्दैनौं। तपाई कुराकानी पुनः सुरु गर्न सक्नुहुन्छ वा  कुराकानी अन्त्य गरेर नजिकैको सडक कार्यालयमा जान सक्नुहुन्छ।  ",
                }
            },
            'buttons': {
                1: {
                    'en': [
                        BUTTONS_MAIN_MENU['en'][0],
                        BUTTONS_GOODBYE['en'][0]
                    ],
                    'ne': [
                        BUTTONS_MAIN_MENU['ne'][0],
                        BUTTONS_GOODBYE['ne'][0]
                    ]
                }
            }
        }
    },
    'form_modify_contact': {
        'action_ask_form_modify_contact_complainant_phone': {
            'utterances': {
                1: {
                    'en': "Please provide your phone number for this grievance. You can skip to move to the next field or click I'm done when finished.",
                    'ne': "कृपया यस गुनासोको लागि आफ्नो फोन नम्बर प्रदान गर्नुहोस्। तपाई अर्को फिल्डमा  जान छोड्न सक्नुहुन्छ वा समाप्त भएपछि म समाप्त गर्छु क्लिक गर्न सक्नुहुन्छ। ",
                }
            },
            'buttons': {
                1: {
                    'en': [
                        {"title": "Skip", "payload": "/skip"},
                        {"title": "I'm done", "payload": "/modify_missing_done"}
                    ],
                    'ne': [
                        {"title": "छोड्नुहोस्", "payload": "/skip"},
                        {"title": "म समाप्त गर्छु", "payload": "/modify_missing_done"}
                    ]
                }
            }
        },
        'utterance_all_contact_complete': {
            'utterances': {
                1: {
                    'en': "All contact and location info is already complete.",
                    'ne': "सबै सम्पर्क र स्थान जानकारी पहिले नै पूर्ण भइसकेको छ। ",
                }
            }
        },
        'action_ask_modify_missing_field': {
            'utterances': {
                1: {
                    'en': "Please provide {field_label}. You can skip to move to the next field or click I'm done when finished.",
                    'ne': "कृपया {field_label} प्रदान गर्नुहोस्। तपाई अर्को क्षेत्रमा जान छोड्न सक्नुहुन्छ वा समाप्त भएपछि म समाप्त गर्छु क्लिक गर्न सक्नुहुन्छ।",
                }
            },
            'buttons': {
                1: {
                    'en': [
                        {"title": "Skip", "payload": "/skip"},
                        {"title": "I'm done", "payload": "/modify_missing_done"}
                    ],
                    'ne': [
                        {"title": "छोड्नुहोस्", "payload": "/skip"},
                        {"title": "म समाप्त गर्छु", "payload": "/modify_missing_done"}
                    ]
                }
            }
        }
    },
    'form_modify_grievance': {
        'action_ask_modify_follow_up_answer': {
            'utterances': {
                1: {
                    'en': "Please answer the following question about your grievance: {question}",
                    'ne': "कृपया तपाईको गुनासोको बारेमा निम्न प्रश्नको उत्तर दिनुहोस्: {question}",
                }
            },
            'buttons': {
                1: {
                    'en': [{"title": "Skip", "payload": "/skip"}],
                    'ne': [{"title": "छोड्नुहोस्", "payload": "/skip"}]
                }
            }
        },
        'action_ask_modify_grievance_new_detail': {
            'utterances': {
                1: {
                    'en': "Add more details to your grievance. You can type your additional information below, or use the buttons to save or cancel.",
                    'ne': "तपाईको गुनासोमा थप विवरण थप्नुहोस्। तपाई तल अतिरिक्त जानकारी टाइप गर्न सक्नुहुन्छ वा बटन प्रयोग गरेर सेभ गर्न वा रद्द गर्न सक्नुहुन्छ।",
                },
                2: {
                    'en': "Your text has been added. Add more details below or save and continue.",
                    'ne': "तपाईको पाठ थपिएको छ। तल थप विवरण थप्नुहोस् वा सेभ गर्नुहोस् र जारी राख्नुहोस्।",
                }
            },
            'buttons': {
                1: {
                    'en': [
                        {"title": "Save and continue", "payload": "/submit_details"},
                        {"title": "Cancel", "payload": "/modify_grievance_cancel"}
                    ],
                    'ne': [
                        {"title": "बचत गर्नुहोस् र जारी राख्नुहोस्", "payload": "/submit_details"},
                        {"title": "रद्द गर्नुहोस्", "payload": "/modify_grievance_cancel"}
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
                        {"title": "Use Phone Number", "payload": "/route_status_check_phone"},
                        {"title": "Use Grievance ID", "payload": "/route_status_check_grievance_id"}
                    ],
                    'ne': [
                        {"title": "फोन नम्बर प्रयोग गर्नुहोस्", "payload": "/route_status_check_phone"},
                        {"title": "गुनासो ID प्रयोग गर्नुहोस्", "payload": "/route_status_check_grievance_id"}
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
    # Spec 12: REST webchat file upload (post-upload and Go back messages)
    "rest_webchat_file_upload": {
        "post_upload": {
            "utterances": {
                1: {
                    "en": "Files uploaded. You can add more files or go back to the chat.",
                    'ne': "फाइलहरू अपलोड गरियो। तपाई थप फाइलहरू थप्न सक्नुहुन्छ वा च्याटमा फर्कन सक्नुहुन्छ।",
                },
                2: {
                    "en": "Your files are uploaded. Here's where we left off.",
                    'ne': "तपाईको फाइलहरू सेभ भयो। यहाँ हामी रोक्यौ।",
                },
                3: {
                    "en": "One or more files could not be saved. You can try adding files again or go back to the chat.",
                    'ne': "एक वा बढी फाइलहरू सेभ गर्न सकिएन। तपाई फाइलहरू फेरि थप्न प्रयास गर्न सक्नुहुन्छ वा च्याटमा फर्कन सक्नुहुन्छ।",
                }
            },
            "buttons": {
                1: {
                    "en": [
                        {"title": "Add more files", "payload": "__add_more_files__"},
                        {"title": "Go back to chat", "payload": "__go_back_to_chat__"}
                    ],
                    "ne": [
                        {"title": "थप फाइलहरू थप्नुहोस्", "payload": "__add_more_files__"},
                        {"title": "च्याटमा फर्कनुहोस्", "payload": "__go_back_to_chat__"}
                    ]
                }
            }
        }
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
        button_sets = UTTERANCE_MAPPING[form_name][action_name]['buttons']

        # API contract is 1-based; some mappings may still use 0-based keys.
        if isinstance(button_sets, list):
            zero_based = button_index - 1
            if 0 <= zero_based < len(button_sets):
                return button_sets[zero_based].get(language, [])
            if 0 <= button_index < len(button_sets):
                return button_sets[button_index].get(language, [])
            raise IndexError(button_index)

        if isinstance(button_sets, dict):
            if button_index in button_sets:
                return button_sets[button_index].get(language, [])
            if str(button_index) in button_sets:
                return button_sets[str(button_index)].get(language, [])

            zero_based = button_index - 1
            if zero_based in button_sets:
                return button_sets[zero_based].get(language, [])
            if str(zero_based) in button_sets:
                return button_sets[str(zero_based)].get(language, [])

            raise KeyError(button_index)

        raise TypeError(type(button_sets))
    except (KeyError, IndexError, TypeError) as e:
        print(f"Error getting buttons: {str(e)}")
        return []