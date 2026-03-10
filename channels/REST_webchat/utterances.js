/**
 * REST webchat utterances (Spec 09 §6).
 * Centralizes all frontend-only copy. Uses en/ne structure like utterance_mapping_rasa.py.
 * Chat is Nepali-only; English is for testing.
 */
const DEFAULT_LANG = "ne";

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
  file_upload: {
    post_upload: {
      en: "Files uploaded. You can add more files or go back to the chat.",
      ne: "फाइलहरू अपलोड गरियो। तपाईं थप फाइलहरू थप्न सक्नुहुन्छ वा च्याटमा फर्कन सक्नुहुन्छ।",
    },
    transition: {
      en: "Your files are uploaded. Here's where we left off.",
      ne: "तपाईंको फाइलहरू सेव भयो। यहाँ हामी रोक्यौ।",
    },
    failure: {
      en: "One or more files could not be saved. You can try adding files again or go back to the chat.",
      ne: "एक वा बढी फाइलहरू सेव गर्न सकिएन। तपाईं फाइलहरू फेरि थप्न प्रयास गर्न सक्नुहुन्छ वा च्याटमा फर्कन सक्नुहुन्छ।",
    },
    no_grievance: {
      en: 'To attach files, first start a grievance: click "Register a grievance" (गुनासो दर्ता गर्नुहोस्) above and complete the steps. Once your grievance is created, you can attach files here.',
      ne: "फाइलहरू संलग्न गर्न, पहिले गुनासो सुरु गर्नुहोस्: माथि \"गुनासो दर्ता गर्नुहोस्\" क्लिक गर्नुहोस् र चरणहरू पूरा गर्नुहोस्। गुनासो सिर्जना भएपछि तपाईं यहाँ फाइलहरू संलग्न गर्न सक्नुहुन्छ।",
    },
    voice_detected: {
      en: "Voice recordings detected. These will be processed and transcribed.",
      ne: "आवाज रेकर्डिङहरू पत्ता लाग्यो। यी प्रशोधन र ट्रान्सक्रिप्सन गरिनेछ।",
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
      en: "File is saved in the database.",
      ne: "फाइल डाटाबेसमा सेव भयो।",
    },
    voice_success: {
      en: "Voice recording processed and transcribed successfully",
      ne: "आवाज रेकर्डिङ सफलतापूर्वक प्रशोधन र ट्रान्सक्रिप्शन गरियो",
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
    },
    uploaded_processing: {
      en: "Files uploaded successfully. Processing...",
      ne: "फाइलहरू सफलतापूर्वक अपलोड भयो। प्रशोधन गर्दैछ...",
    },
    voice_uploaded_processing: {
      en: "Voice recordings uploaded. Processing and transcribing...",
      ne: "आवाज रेकर्डिङहरू अपलोड भयो। प्रशोधन र ट्रान्सक्रिप्शन गर्दैछ...",
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
export function get(keyPath, lang = DEFAULT_LANG) {
  const keys = keyPath.split(".");
  let v = U;
  for (const k of keys) v = v?.[k];
  if (v && typeof v === "object" && (v.en || v.ne)) {
    return v[lang] ?? v.en ?? v.ne ?? "";
  }
  return typeof v === "string" ? v : "";
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
