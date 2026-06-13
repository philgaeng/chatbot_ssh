/**
 * REST webchat utterances (Spec 09 §6).
 * Centralizes all frontend-only copy. Uses en/ne structure like utterance_mapping_rasa.py.
 * Chat is Nepali-only; English is for testing.
 */
const DEFAULT_LANG = "en";
const VALID_LANGS = new Set(["en", "ne"]);
let currentLang = DEFAULT_LANG;

export const U = {
  errors: {
    connection: {
      en: "Sorry, there seems to be a connection issue. Please try again.",
      ne: "सम्पर्कमा समस्या भयो। कृपया पुन: प्रयास गर्नुहोस्।",
    },
    connection_timeout: {
      en: "Connection timed out. Please try again later.",
      ne: "सम्पर्क समय सकियो। कृपया पछि प्रयास गर्नुहोस्।",
    },
    reconnect: {
      en: "Unable to reconnect. Please refresh the page.",
      ne: "पुन: जोड्न सकिएन। कृपया पृष्ठ नवीकरण गर्नुहोस्।",
    },
  },
  filed_banner: {
    label: {
      en: "Grievance filed —",
      ne: "गुनासो दर्ता भयो —",
    },
  },
  post_submit: {
    file_another: {
      en: "File another grievance",
      ne: "अर्को गुनासो दर्ता गर्नुहोस्",
    },
  },
  file_upload: {
    invitation: {
      en: "You can attach pictures or other documents related to your grievance. These will be reviewed by our officer. You may also attach a photo of a handwritten complaint.",
      ne: "तपाईं आफ्नो गुनासोसँग सम्बन्धित तस्बिर वा अन्य कागजात संलग्न गर्न सक्नुहुन्छ। यी हाम्रा अधिकारीले हेर्नेछन्। हस्तलिखित उजुरीको फोटो पनि संलग्न गर्न सक्नुहुन्छ।",
    },
    post_upload: {
      en: "Your file is saved. You can add more files or go back to the chat.",
      ne: "तपाईंको फाइल सेव भयो। तपाईं थप फाइलहरू थप्न वा च्याटमा फर्कन सक्नुहुन्छ।",
    },
    /** Shown after upload when orchestrator is already at end of flow (`done`). */
    post_upload_at_flow_end: {
      en: "Your file is saved. You can add more files, go back to the chat, file another grievance, or end your session below.",
      ne: "तपाईंको फाइल सेव भयो। तपाईं थप फाइलहरू थप्न, च्याटमा फर्कन, अर्को गुनासो दर्ता गर्न, वा तल सत्र समाप्त गर्न सक्नुहुन्छ।",
    },
    transition: {
      en: "Your file is saved. Here's where we left off.",
      ne: "तपाईंको फाइल सेव भयो। यहाँ हामी रोक्यौ।",
    },
    failure: {
      en: "One or more files could not be saved. You can try adding files again or go back to the chat.",
      ne: "एक वा बढी फाइलहरू सेव गर्न सकिएन। तपाईं फाइलहरू फेरि थप्न प्रयास गर्न सक्नुहुन्छ वा च्याटमा फर्कन सक्नुहुन्छ।",
    },
    failure_at_flow_end: {
      en: "We could not save one or more files. You can try again, go back to the chat, or use the buttons below.",
      ne: "एक वा बढी फाइलहरू सेव गर्न सकिएन। तपाईं फेरि प्रयास गर्न, च्याटमा फर्कन, वा तलका बटनहरू प्रयोग गर्न सक्नुहुन्छ।",
    },
    no_grievance: {
      en: 'To attach files, start a grievance first: choose "File a grievance" (गुनासो दर्ता गर्नुहोस्) in the chat above and complete the steps. After your grievance is created, you can attach photos or documents here.',
      ne: "फाइल संलग्न गर्न पहिले गुनासो सुरु गर्नुहोस्: माथिको च्याटमा \"गुनासो दर्ता गर्नुहोस्\" छान्नुहोस् र चरणहरू पूरा गर्नुहोस्। गुनासो सिर्जना भएपछि तपाईं यहाँ तस्बिर वा कागजात संलग्न गर्न सक्नुहुन्छ।",
    },
    voice_detected: {
      en: "Voice recording detected. Uploading…",
      ne: "आवाज रेकर्ड पत्ता लाग्यो। अपलोड गर्दैछ…",
    },
    oversized_prefix: {
      en: "Some files are too large and will be skipped:",
      ne: "केही फाइलहरू धेरै ठूला छन् र छोडिनेछ:",
    },
    oversized_api_prefix: {
      en: "Some files were too large and could not be processed:",
      ne: "केही फाइलहरू धेरै ठूला थिए र प्रशोधन गर्न सकिएन:",
    },
    processing_long: {
      en: "File processing is taking longer than expected. You can continue with your submission.",
      ne: "फाइल प्रशोधन अपेक्षित भन्दा बढी समय लिँदैछ। तपाईं आफ्नो जम्मा गर्ने काम जारी राख्न सक्नुहुन्छ।",
    },
    processing: {
      en: "Processing files...",
      ne: "फाइलहरू प्रशोधन गर्दैछ...",
    },
    transcribing: {
      en: "Transcribing audio...",
      ne: "ऑडियो ट्रान्सक्रिप्शन गर्दैछ...",
    },
    transcribing_progress: {
      en: "Transcribing audio: {progress}%",
      ne: "ऑडियो ट्रान्सक्रिप्शन: {progress}%",
    },
    processing_progress: {
      en: "Processing files: {progress}%",
      ne: "फाइलहरू प्रशोधन: {progress}%",
    },
    file_saved: {
      en: "Voice record is saved in the database.",
      ne: "आवाज रेकर्ड डाटाबेसमा सेव भयो।",
    },
    voice_success: {
      en: "Voice record saved for officer review.",
      ne: "आवाज रेकर्ड अधिकारी समीक्षाको लागि सेव भयो।",
    },
    voice_failure_prefix: {
      en: "Failed to process voice recording:",
      ne: "आवाज रेकर्डिङ प्रशोधन गर्न असफल:",
    },
    files_failure_prefix: {
      en: "Failed to process files:",
      ne: "फाइलहरू प्रशोधन गर्न असफल:",
    },
    files_success: {
      en: "Files processed successfully",
      ne: "फाइलहरू सफलतापूर्वक प्रशोधन गरियो",
    },
    status_prefix: {
      en: "Status:",
      ne: "स्थिति:",
    },
    buttons: {
      add_more: {
        en: "Add more files",
        ne: "थप फाइलहरू थप्नुहोस्",
      },
      go_back: {
        en: "Go back to chat",
        ne: "च्याटमा फर्कनुहोस्",
      },
      add_voice_record: {
        en: "Add a file",
        ne: "फाइल थप्नुहोस्",
      },
      next_step: {
        en: "Next step",
        ne: "अर्को चरण",
      },
      close_browser: {
        en: "Close Browser",
        ne: "ब्राउजर बन्द गर्नुहोस्",
      },
      clear_session: {
        en: "Clear Session",
        ne: "सत्र खाली गर्नुहोस्",
      },
      close_session: {
        en: "Close Session",
        ne: "सत्र बन्द गर्नुहोस्",
      },
    },
    uploaded_processing: {
      en: "Voice record uploaded. Processing…",
      ne: "आवाज रेकर्ड अपलोड भयो। प्रशोधन गर्दैछ…",
    },
    voice_uploaded_processing: {
      en: "Voice record uploaded. Processing…",
      ne: "आवाज रेकर्ड अपलोड भयो। प्रशोधन गर्दैछ…",
    },
    continue_below: {
      en: "You can continue below.",
      ne: "तपाईं तल जारी राख्न सक्नुहुन्छ।",
    },
  },
  task_status: {
    classification_done: {
      en: "We've finished analyzing your grievance and saved the results.",
      ne: "हामीले तपाईंको गुनासो विश्लेषण गर्यौं र नतिजाहरू सेव गर्यौं।",
    },
    classification_done_fallback: {
      en: "We've finished analyzing your grievance. The results have been saved and will be used for follow‑up.",
      ne: "हामीले तपाईंको गुनासो विश्लेषण गर्यौं। नतिजाहरू सेव गरिएको छ र अनुसरणको लागि प्रयोग गरिनेछ।",
    },
    task_success: {
      en: "Task completed successfully",
      ne: "कार्य सफलतापूर्वक पूरा भयो",
    },
    task_failed: {
      en: "Task failed",
      ne: "कार्य असफल भयो",
    },
    task_in_progress: {
      en: "Task is processing...",
      ne: "कार्य प्रशोधन गर्दैछ...",
    },
  },
  map: {
    confirm_sent: {
      en: "Map location sent.",
      ne: "नक्साको स्थान पठाइयो।",
    },
  },
  status_banner: {
    recording: {
      en: "Recording {elapsed} / {max} — tap mic to stop",
      ne: "रेकर्डिङ {elapsed} / {max} — रोक्न माइक थिच्नुहोस्",
    },
    max_length: {
      en: "Maximum length ({max}) reached. Uploading…",
      ne: "अधिकतम लम्बाइ ({max}) पुग्यो। अपलोड गर्दैछ…",
    },
    mic_denied: {
      en: "Microphone access is required to record.",
      ne: "रेकर्ड गर्न माइक्रोफोन अनुमति चाहिन्छ।",
    },
    voice_detected: {
      en: "Voice recording detected. Uploading…",
      ne: "आवाज रेकर्ड पत्ता लाग्यो। अपलोड गर्दैछ…",
    },
    files_detected: {
      en: "Files selected. Uploading…",
      ne: "फाइलहरू छानियो। अपलोड गर्दैछ…",
    },
    voice_uploaded_processing: {
      en: "Voice record uploaded. Processing…",
      ne: "आवाज रेकर्ड अपलोड भयो। प्रशोधन गर्दैछ…",
    },
    voice_processing: {
      en: "Processing voice record…",
      ne: "आवाज रेकर्ड प्रशोधन गर्दैछ…",
    },
    voice_saved: {
      en: "Voice record saved for officer review.",
      ne: "आवाज रेकर्ड अधिकारी समीक्षाको लागि सेव भयो।",
    },
    voice_failure: {
      en: "Could not save voice record: {error}",
      ne: "आवाज रेकर्ड सेव गर्न सकिएन: {error}",
    },
    files_processing: {
      en: "Processing files…",
      ne: "फाइलहरू प्रशोधन गर्दैछ…",
    },
    files_processing_progress: {
      en: "Processing files: {progress}%",
      ne: "फाइलहरू प्रशोधन: {progress}%",
    },
    files_saved: {
      en: "Files saved for officer review.",
      ne: "फाइलहरू अधिकारी समीक्षाको लागि सेव भयो।",
    },
    files_failure: {
      en: "Could not save files: {error}",
      ne: "फाइलहरू सेव गर्न सकिएन: {error}",
    },
    oversized: {
      en: "Some files are too large and were skipped: {names}",
      ne: "केही फाइलहरू धेरै ठूला थिए र छोडियो: {names}",
    },
    processing_long: {
      en: "Processing is taking longer than expected…",
      ne: "प्रशोधन अपेक्षित भन्दा बढी समय लिँदैछ…",
    },
    map_saving: {
      en: "Saving map location…",
      ne: "नक्साको स्थान सेव गर्दैछ…",
    },
    map_saved: {
      en: "Location saved ({lat}, {lng}).",
      ne: "स्थान सेव भयो ({lat}, {lng})।",
    },
    map_failed: {
      en: "Could not save map location. Please try again.",
      ne: "नक्साको स्थान सेव गर्न सकिएन। कृपया फेरि प्रयास गर्नुहोस्।",
    },
    phone_location_getting: {
      en: "Getting your phone location…",
      ne: "फोनको स्थान पत्ता लगाउँदैछ…",
    },
    phone_location_denied: {
      en: "Location access was denied. Try the map or enter your area manually.",
      ne: "स्थान अनुमति अस्वीकार भयो। नक्सा प्रयोग गर्नुहोस् वा स्थान आफैं टाइप गर्नुहोस्।",
    },
    phone_location_unavailable: {
      en: "Could not detect your location. Try the map or enter your area manually.",
      ne: "स्थान पत्ता लागेन। नक्सा प्रयोग गर्नुहोस् वा स्थान आफैं टाइप गर्नुहोस्।",
    },
    phone_location_timeout: {
      en: "Location took too long. Try again, use the map, or enter manually.",
      ne: "स्थान पत्ता लगाउन धेरै समय लाग्यो। फेरि प्रयास गर्नुहोस्, नक्सा प्रयोग गर्नुहोस्, वा आफैं टाइप गर्नुहोस्।",
    },
    phone_location_unsupported: {
      en: "This browser cannot use phone location. Try the map or enter manually.",
      ne: "यो ब्राउजरले फोनको स्थान प्रयोग गर्न सक्दैन। नक्सा प्रयोग गर्नुहोस् वा आफैं टाइप गर्नुहोस्।",
    },
    phone_location_failed: {
      en: "Could not use phone location. Try the map or enter manually.",
      ne: "फोनको स्थान प्रयोग गर्न सकिएन। नक्सा प्रयोग गर्नुहोस् वा आफैं टाइप गर्नुहोस्।",
    },
  },
  location_buttons: {
    use_phone: {
      en: "Use my phone location",
      ne: "मेरो फोनको स्थान प्रयोग गर्नुहोस्",
    },
    use_map: {
      en: "Use the map",
      ne: "नक्सा प्रयोग गर्नुहोस्",
    },
    manual: {
      en: "Enter location manually",
      ne: "स्थान आफैं टाइप गर्नुहोस्",
    },
  },
  voice_note: {
    tap_to_record: {
      en: "Record voice note (tap again to stop)",
      ne: "आवाज नोट रेकर्ड गर्नुहोस् (रोक्न फेरि थिच्नुहोस्)",
    },
    inactive_step: {
      en: "Voice recording is available when describing your grievance.",
      ne: "गुनासो विवरण बताउँदा मात्र आवाज रेकर्ड उपलब्ध छ।",
    },
    recording: {
      en: "Recording… tap again to stop (max 45 seconds).",
      ne: "रेकर्डिङ… रोक्न फेरि थिच्नुहोस् (अधिकतम ४५ सेकेन्ड)।",
    },
    max_length: {
      en: "Maximum recording length reached. Uploading your voice note…",
      ne: "अधिकतम रेकर्डिङ लम्बाइ पुग्यो। आवाज नोट अपलोड गर्दैछ…",
    },
    denied: {
      en: "Microphone access was denied. You can type your grievance instead.",
      ne: "माइक्रोफोन अनुमति अस्वीकार भयो। तपाईं टाइप गरेर गुनासो दर्ता गर्न सक्नुहुन्छ।",
    },
    uploaded: {
      en: "Voice note uploaded. You can add more or tap **File as is** when ready.",
      ne: "आवाज नोट अपलोड भयो। थप थप्न वा तयार भएपछि **यसै रूपमा दर्ता** थिच्नुहोस्।",
    },
    uploaded_advancing: {
      en: "Voice note saved. Continuing to the next step…",
      ne: "आवाज नोट सुरक्षित भयो। अर्को चरणमा जाँदैछ…",
    },
    need_grievance: {
      en: "Start a grievance first before recording a voice note.",
      ne: "आवाज नोट रेकर्ड गर्न पहिले गुनासो सुरु गर्नुहोस्।",
    },
  },
  photo_exif: {
    consent: {
      en: "May we read photo location and time from your images (EXIF)? This helps officers verify where/when photos were taken. We never show raw EXIF data in the chat.",
      ne: "के हामी तपाईंका तस्बिरबाट स्थान र समय (EXIF) पढ्न सक्छौं? यसले अधिकारीलाई तस्बिर कहाँ/कहिले लिइएको थियो भनेर जाँच गर्न मद्दत गर्छ। कच्चा EXIF डेटा च्याटमा देखाइँदैन।",
    },
    allow: { en: "Allow", ne: "अनुमति दिनुहोस्" },
    deny: { en: "Not now", ne: "अहिले होइन" },
  },
  attach_button: {
    start_first: {
      en: "Start a grievance first",
      ne: "पहिले गुनासो सुरु गर्नुहोस्",
    },
    saving: {
      en: "Saving your grievance… files will be available shortly",
      ne: "तपाईंको गुनासो सेव गर्दैछ… फाइलहरू चाँडै उपलब्ध हुनेछ",
    },
    ready: {
      en: "Files can be uploaded now",
      ne: "फाइलहरू अहिले अपलोड गर्न सकिन्छ",
    },
  },
};

/** Resolve nested key path like "file_upload.post_upload" or "errors.connection" */
export function get(keyPath, lang = currentLang) {
  const keys = keyPath.split(".");
  let v = U;
  for (const k of keys) v = v?.[k];
  if (v && typeof v === "object" && (v.en || v.ne)) {
    return v[lang] ?? v.en ?? v.ne ?? "";
  }
  return typeof v === "string" ? v : "";
}

export function setLanguage(lang) {
  if (!VALID_LANGS.has(lang)) return;
  currentLang = lang;
}

export function getLanguage() {
  return currentLang;
}

/** Format string with {placeholders} */
export function format(template, vars = {}) {
  let s = template;
  for (const [k, v] of Object.entries(vars)) {
    s = s.replace(new RegExp(`\\{${k}\\}`, "g"), String(v ?? ""));
  }
  return s;
}

export const ADD_MORE_PAYLOAD = "__add_more_files__";
export const GO_BACK_PAYLOAD = "__go_back_to_chat__";
export const VOICE_ADD_PAYLOAD = "__add_voice_record__";
export const VOICE_NEXT_STEP_PAYLOAD = "__voice_next_step__";
export const FILE_ANOTHER_PAYLOAD = "__file_another_grievance__";
