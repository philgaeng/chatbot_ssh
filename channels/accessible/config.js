// Accessible Interface Configuration

// API Configuration
const API_CONFIG = {
    // Base URL for the API
    BASE_URL: window.location.hostname === 'localhost' ? 
        'http://localhost:5001' : 
        'https://' + window.location.hostname + '/accessible-api',
    
    // Endpoints
    ENDPOINTS: {
        SUBMIT_GRIEVANCE: '/submit-voice-grievance',
        TRANSCRIBE: '/transcribe-audio',
        FILE_UPLOAD: '/upload-files',
        CREATE_GRIEVANCE: '/create-grievance'
    },
    
    // Request headers
    HEADERS: {
        'Content-Type': 'application/json'
    }
};

// Voice Recording Configuration
const RECORDING_CONFIG = {
    // Maximum recording duration in seconds
    MAX_DURATION: 180,
    
    // Audio settings for recording
    AUDIO_SETTINGS: {
        sampleRate: 44100,
        mimeType: 'audio/webm',
        audioBitsPerSecond: 128000
    },
    
    // Timer settings
    TIMER_INTERVAL: 1000, // 1 second
    
    // File upload settings
    MAX_FILE_SIZE_MB: 10
};

// Accessibility Configuration
const ACCESSIBILITY_CONFIG = {
    // Text-to-speech settings
    TTS: {
        RATE: 1.0,  // Speech rate (0.1 to 10)
        PITCH: 1.0, // Speech pitch (0 to 2)
        VOLUME: 1.0, // Speech volume (0 to 1)
        VOICE_URI: '', // Default voice (empty for system default)
        LANGUAGE: 'en-US' // Default language
    },
    
    // Font size settings
    FONT_SIZE: {
        DEFAULT: 16, // Default font size in pixels
        MIN: 14,     // Minimum font size
        MAX: 28,     // Maximum font size
        STEP: 2      // Step for increasing/decreasing
    },
    
    // Contrast settings
    HIGH_CONTRAST: {
        BACKGROUND: '#000000',
        TEXT: '#FFFFFF',
        BUTTONS: '#FFFF00',
        LINKS: '#00FFFF'
    }
};

// UI Configuration
const UI_CONFIG = {
    // Step transitions
    TRANSITION_DELAY: 300, // milliseconds
    
    // Button states
    BUTTON_STATES: {
        RECORD: 'Press to Record',
        RECORDING: 'Recording... Press to Stop',
        PROCESSING: 'Processing...'
    },
    
    // Alert message timeout
    ALERT_TIMEOUT: 5000 // milliseconds
};

// Error messages
const ERROR_MESSAGES = {
    RECORDING_NOT_SUPPORTED: 'Voice recording is not supported in your browser. Please try using a modern browser like Chrome, Firefox, or Edge.',
    MICROPHONE_PERMISSION_DENIED: 'Microphone access was denied. This app needs microphone access to record your grievance.',
    RECORDING_ERROR: 'There was an error while recording. Please try again.',
    UPLOAD_ERROR: 'There was an error uploading your recording. Please try again.',
    SUBMISSION_ERROR: 'There was an error submitting your grievance. Please try again or contact support.',
    NETWORK_ERROR: 'Network error. Please check your internet connection and try again.',
    TRANSCRIPTION_ERROR: 'Could not transcribe your recording. Please try again and speak clearly.'
};

// Export all configurations
window.APP_CONFIG = {
    api: {
        baseUrl: window.location.hostname === 'localhost' ? 
            'http://localhost:5001' : 
            'https://' + window.location.hostname + '/accessible-api',
        endpoints: {
            submitGrievance: '/submit-voice-grievance',
            fileUpload: '/upload-files',
            createGrievance: '/create-grievance'
        }
    },
    recording: {
        maxDuration: 180,
        audioSettings: {
            mimeType: 'audio/webm'
        }
    },
    accessibility: {
        fontSize: {
            default: 16,
            min: 14,
            max: 28,
            step: 2
        }
    },
    errors: {
        browserSupport: 'Voice recording is not supported in your browser.',
        micPermission: 'Microphone access was denied.',
        recording: 'Recording error. Please try again.',
        submission: 'Submission error. Please try again.'
    }
}; 