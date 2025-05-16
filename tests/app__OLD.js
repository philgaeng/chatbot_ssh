/**
 * Nepal Chatbot Accessible Interface
 * Modular structure based on refactoring plan
 */

// Module namespaces
let SpeechModule = {};
let AccessibilityModule = {};
let UIModule = {};
let APIModule = {};
let RecordingModule = {};
let FileUploadModule = {};
let GrievanceModule = {};

// Global state
let state = {
    currentStep: '1',  // Start with first step as string
    grievanceId: null
};
let recordedBlobs = {};
let appInitialized = false;

// --- Submission Overlay Logic ---
// 1. Show overlay on submit
// 2. Prevent multiple submissions
// 3. Show Cancel button after 5s
// 4. AbortController for fetch
// 5. Hide overlay and re-enable UI on completion/cancel

// Add these variables at the top level
let submissionAbortController = null;
let cancelBtnTimeout = null;

// Add at the start of the file, after any imports
let overlayMutationObserver = null;

// Add at the top of the file
let isSubmitting = false;
let isTransitioning = false;

// Add this near the top of the file where other state variables are defined
let isSpeechIndicatorEnabled = true;

// Replace the APP_STEPS array with a dictionary
const APP_STEPS = {
    grievance: {
        name: 'Record your Grievance',
        windows: ['grievanceDetails'],
        requiresRecording: true
    },
    personalInfo: {
        name: 'Record your Details',
        windows: ['fullName', 'phone', 'municipality', 'village', 'address'],
        requiresRecording: true
    },
    confirmation: {
        name: 'Voice Grievance Submitted',
        windows: ['confirmation'],
        requiresRecording: false
    },
    review: {
        name: 'Review your Submission',
        windows: ['reviewGrievance', 'reviewDetails'],
        requiresRecording: false
    },
    attachments: {
        name: 'Attachments',
        windows: ['attachments'],
        requiresRecording: false
    }
};

// Define the submission step as a constant
const SUBMISSION_STEP_WINDOW = ['personalInfo', 'address'];

// Add a helper function to get step order
function getStepOrder() {
    return ['grievance', 'personalInfo', 'review', 'attachments'];
}

// At the top of the file, after the windowToRecordingTypeMap
const windowToRecordingTypeMap = {
    grievance: {
        'grievanceDetails': 'grievance_details',
    },
    personalInfo: {
        'fullName': 'user_full_name',
        'phone': 'user_contact_phone',
        'municipality': 'user_municipality',
        'village': 'user_village',
        'address': 'user_address'
    }
};
const stepWindowList = Object.entries(windowToRecordingTypeMap).map(([k, v]) => [k, Object.keys(v)]);

// Optionally, generate the reverse mapping automatically:
const recordingTypeToWindowMap = Object.fromEntries(
    Object.entries(windowToRecordingTypeMap).map(([k, v]) => [v, k])
);

// Function: window -> recording type
function getRecordingTypeForWindow(stepName, windowName) {
    if (!windowToRecordingTypeMap[stepName]) {
        return null;
    }
    return windowToRecordingTypeMap[stepName][windowName] || null;
}

// Function: recording type -> window
function getWindowForRecordingType(recordingType) {
    if (!recordingTypeToWindowMap[recordingType]) {
        return null;
    }
    return recordingTypeToWindowMap[recordingType] || null;
}

console.log('app.js loaded');

document.addEventListener('DOMContentLoaded', function() {
    if (UIModule.Overlay && typeof UIModule.Overlay.checkForDuplicateOverlays === 'function') {
        UIModule.Overlay.checkForDuplicateOverlays();
    }
});


/**
 * Speech Module - Handles text-to-speech functionality
 */
SpeechModule = {
    voice: null,
    voices: [],
    speaking: false,
    autoRead: true, // default to true
    currentRate: 1,
    
    init: function() {
        this.loadPreferences();
        // If no preference, default to true
        if (localStorage.getItem('autoRead') === null) {
            this.autoRead = true;
        }
        
        // Set up speech synthesis
        if ('speechSynthesis' in window) {
            this.setupVoices();
            
            // Handle speech rate dropdown
            document.getElementById('speedBtn').addEventListener('click', this.toggleSpeedDropdown.bind(this));
            
            // Set up speech rate options
            const speedOptions = document.querySelectorAll('.speed-option');
            speedOptions.forEach(option => {
                option.addEventListener('click', (e) => {
                    const rate = parseFloat(e.target.dataset.rate);
                    this.setRate(rate);
                    this.toggleSpeedDropdown();
                });
            });
            
            // Set up the read page button
            document.getElementById('readPageBtn').addEventListener('click', this.toggleAutoRead.bind(this));
            
            // Close the dropdown when clicking outside
            document.addEventListener('click', (e) => {
                const dropdown = document.getElementById('speedDropdown');
                const speedBtn = document.getElementById('speedBtn');
                if (dropdown && !dropdown.hidden && e.target !== speedBtn && !speedBtn.contains(e.target) && 
                    e.target !== dropdown && !dropdown.contains(e.target)) {
                    this.toggleSpeedDropdown(null, true);
                }
            });
            
            // Update button text with saved rate
            document.querySelector('#speedBtn .icon').textContent = this.currentRate + 'x';
        } else {
            console.error('Speech synthesis not supported');
            document.getElementById('readPageBtn').disabled = true;
            document.getElementById('speedBtn').disabled = true;
        }
    },
    
    setupVoices: function() {
        // Setup voices when they're loaded
        window.speechSynthesis.onvoiceschanged = () => {
            this.voices = window.speechSynthesis.getVoices();
            
            // Find a suitable voice (prefer English)
            this.voice = this.voices.find(voice => voice.lang.startsWith('en')) || this.voices[0];
            console.log('Selected voice:', this.voice);
        };
        
        // Check if voices are already loaded
        this.voices = window.speechSynthesis.getVoices();
        if (this.voices.length > 0) {
            this.voice = this.voices.find(voice => voice.lang.startsWith('en')) || this.voices[0];
            console.log('Voices already loaded, selected:', this.voice);
        }
    },
    
    speak: function(text) {
        if (!('speechSynthesis' in window)) {
            console.error('Speech synthesis not supported');
            return;
        }
        
        // Stop any current speech
            window.speechSynthesis.cancel();
            
        if (!text) return;
        
        // Create and configure utterance
            const utterance = new SpeechSynthesisUtterance(text);
        utterance.voice = this.voice;
        utterance.rate = this.currentRate;
        utterance.pitch = 1;
        utterance.volume = 1;
        
        this.speaking = true;
        this.updateSpeakingUI(true);
        
        // When speech ends
        utterance.onend = () => {
            this.speaking = false;
            this.updateSpeakingUI(false);
        };
        
        utterance.onerror = (event) => {
            console.error('Speech synthesis error:', event);
            this.speaking = false;
            this.updateSpeakingUI(false);
        };
        
        // Speak the text
            window.speechSynthesis.speak(utterance);
    },
    
    updateSpeakingUI: function(isSpeaking) {
        const readBtn = document.getElementById('readPageBtn');
        if (isSpeaking) {
            readBtn.classList.add('active');
            readBtn.classList.remove('inactive');
        } else {
            if (this.autoRead) {
                readBtn.classList.add('active');
                readBtn.classList.remove('inactive');
            } else {
                readBtn.classList.remove('active');
                readBtn.classList.add('inactive');
            }
        }
    },
    
    toggleAutoRead: function() {
        this.autoRead = !this.autoRead;
        const readBtn = document.getElementById('readPageBtn');
        if (this.autoRead) {
            readBtn.classList.add('active');
            readBtn.classList.remove('inactive');
            // Read current content if auto-read is turned on
            const currentStep = document.querySelector('.step:not([hidden])');
            if (currentStep) {
                this.speak(currentStep.textContent);
            }
        } else {
            readBtn.classList.remove('active');
            readBtn.classList.add('inactive');
            window.speechSynthesis.cancel();
        }
        // Save preference
        this.savePreferences();
        // Announce change for screen readers
        UIModule.announceToScreenReader(`Auto read ${this.autoRead ? 'enabled' : 'disabled'}`);
    },
    
    toggleSpeedDropdown: function(event, forceClose = false) {
        const dropdown = document.getElementById('speedDropdown');
        const speedBtn = document.getElementById('speedBtn');
        
        if (dropdown.hidden && !forceClose) {
            // Position dropdown above the speed button in the footer
            const buttonRect = speedBtn.getBoundingClientRect();
            dropdown.style.bottom = (window.innerHeight - buttonRect.top + 5) + 'px';
            dropdown.style.right = (window.innerWidth - buttonRect.right) + 'px';
            
            dropdown.hidden = false;
        } else {
            dropdown.hidden = true;
        }
        
        if (event) {
            event.stopPropagation();
        }
    },
    
    setRate: function(rate) {
        this.currentRate = rate;
        
        // Update button text
        document.querySelector('#speedBtn .icon').textContent = rate + 'x';
        
        // Update selected option in dropdown
        const options = document.querySelectorAll('.speed-option');
        options.forEach(option => {
            if (parseFloat(option.dataset.rate) === rate) {
                option.classList.add('selected');
            } else {
                option.classList.remove('selected');
            }
        });
        
        // Save preference
        this.savePreferences();
        
        // Announce change for screen readers
        UIModule.announceToScreenReader(`Speech rate set to ${rate}`);
    },
    
    savePreferences: function() {
        try {
            localStorage.setItem('speechRate', this.currentRate);
            localStorage.setItem('autoRead', this.autoRead ? 'true' : 'false');
        } catch (e) {
            console.error('Failed to save preferences:', e);
        }
    },
    
    loadPreferences: function() {
        try {
            const savedRate = localStorage.getItem('speechRate');
            if (savedRate) {
                this.currentRate = parseFloat(savedRate);
            }
            
            const savedAutoRead = localStorage.getItem('autoRead');
            if (savedAutoRead) {
                this.autoRead = savedAutoRead === 'true';
            }
        } catch (e) {
            console.error('Failed to load preferences:', e);
        }
    }
};

/**
 * Accessibility Module - Handles accessibility features
 */
AccessibilityModule = {
    highContrast: false,
    fontSize: null,
    fontSizeOptions: null,
    
    init: function() {
        this.fontSizeOptions = APP_CONFIG.accessibility.fontSize;
        this.fontSize = this.fontSizeOptions.default;
        
        this.loadPreferences();
        this.setupAccessibilityControls();
        this.applySettings();
    },
    
        toggleContrast: function() {
        this.highContrast = !this.highContrast;
        document.body.classList.toggle('high-contrast', this.highContrast);
        this.savePreferences();
        
        // Update button state
        const contrastBtn = document.getElementById('contrastToggleBtn');
        if (contrastBtn) {
            contrastBtn.classList.toggle('active', this.highContrast);
            
            // Update tooltip text
            const tooltip = contrastBtn.querySelector('.tooltip');
            if (tooltip) {
                tooltip.textContent = this.highContrast ? 'Disable High Contrast' : 'Enable High Contrast';
            }
        }
    },
    
    increaseFontSize: function() {
        if (this.fontSize < this.fontSizeOptions.max) {
            this.fontSize += this.fontSizeOptions.step;
            this.applyFontSize();
            this.savePreferences();
        }
    },
    
    decreaseFontSize: function() {
        if (this.fontSize > this.fontSizeOptions.default) {
            this.fontSize -= this.fontSizeOptions.step;
            this.applyFontSize();
            this.savePreferences();
        }
    },
    
    applyFontSize: function() {
        document.body.style.fontSize = `${this.fontSize}px`;
        
        // Update font size button state
        const fontBtn = document.getElementById('fontSizeBtn');
        if (fontBtn) {
            // Add active class if font size is larger than default
            fontBtn.classList.toggle('active', this.fontSize > this.fontSizeOptions.default);
        }
    },
    
    setupAccessibilityControls: function() {
        const fontBtn = document.getElementById('fontSizeBtn');
        const contrastBtn = document.getElementById('contrastToggleBtn');
        
        if (fontBtn) {
            fontBtn.addEventListener('click', () => {
                this.increaseFontSize();
                if (this.fontSize >= this.fontSizeOptions.max) {
                    // Reset to default if we've reached the maximum
                    this.fontSize = this.fontSizeOptions.default;
                    this.applyFontSize();
                    this.savePreferences();
                    
                    // Update tooltip
                    const tooltip = fontBtn.querySelector('.tooltip');
                    if (tooltip) {
                        tooltip.textContent = 'Reset Font Size';
                        setTimeout(() => {
                            tooltip.textContent = 'Increase Font Size';
                        }, 2000);
                    }
                    
                    // Announce for screen readers
                    SpeechModule.speak("Font size reset to default");
                } else {
                    // Announce for screen readers
                    SpeechModule.speak("Font size increased");
                }
            });
        }
        
        if (contrastBtn) {
            contrastBtn.addEventListener('click', () => {
                this.toggleContrast();
                const message = this.highContrast ? 
                    "High contrast mode enabled" : 
                    "High contrast mode disabled";
                SpeechModule.speak(message);
            });
            
            // Initialize high contrast button state
            contrastBtn.classList.toggle('active', this.highContrast);
            
            // Set initial tooltip text
            const contrastTooltip = contrastBtn.querySelector('.tooltip');
            if (contrastTooltip) {
                contrastTooltip.textContent = this.highContrast ? 'Disable High Contrast' : 'Enable High Contrast';
            }
        }
    },
    
    applySettings: function() {
        this.applyFontSize();
        document.body.classList.toggle('high-contrast', this.highContrast);
    },
    
    savePreferences: function() {
        try {
            localStorage.setItem('accessibilitySettings', JSON.stringify({
                highContrast: this.highContrast,
                fontSize: this.fontSize
            }));
        } catch (error) {
            console.error("Could not save accessibility preferences", error);
        }
    },
    
    loadPreferences: function() {
        try {
            const savedSettings = localStorage.getItem('accessibilitySettings');
            if (savedSettings) {
                const settings = JSON.parse(savedSettings);
                this.highContrast = settings.highContrast || false;
                this.fontSize = settings.fontSize || this.fontSizeOptions.default;
            }
        } catch (error) {
            console.error("Could not load accessibility preferences", error);
            this.highContrast = false;
            this.fontSize = this.fontSizeOptions.default;
        }
    }
};

/**
 * UI Module - Handles UI state and navigation
 */
UIModule = {
    steps: APP_STEPS,
    stepOrder: getStepOrder(),
    currentStepIndex: 0,
    currentWindowIndex: 0,
    hasTranscriptionErrors: false,

    // Add the helper function
    getCurrentWindow: function() {
        const currentStepKey = this.stepOrder[this.currentStepIndex];
        const currentStep = this.steps[currentStepKey];
        return {
            step: currentStepKey,
            window: currentStep.windows[this.currentWindowIndex]
        };
    },
    
    init: function() {
        this.setupHelpDialog();
        UIModule.Navigation.showCurrentWindow();

        // Add event listener for review data loading
        document.addEventListener('DOMContentLoaded', () => {
            const grievanceId = new URLSearchParams(window.location.search).get('id');
            if (grievanceId) {
                GrievanceModule.loadReviewData(grievanceId);
            }
        });
    },
    showMessage: function(message, isError = false) {
        if (isError) {
            console.error(message);
        } else {
            console.log(message);
        }
        const messageElement = document.getElementById('statusMessage');
        if (messageElement) {
            messageElement.textContent = message;
            messageElement.className = isError ? 'error-message' : 'status-message';
        }
    },


    setupHelpDialog: function() {
        // No-op for now, or add help dialog setup here if needed
    },

    
    Navigation:{
        showCurrentWindow: function() {
            try {
                const { step, window } = UIModule.getCurrentWindow();
                const currentStepKey = UIModule.stepOrder[UIModule.currentStepIndex];
                const currentStep = UIModule.steps[currentStepKey];
                const currentWindow = currentStep ? currentStep.windows[UIModule.currentWindowIndex] : undefined;
                
                if (step === 'confirmation') {
                    UIModule.showConfirmationScreen(state.grievanceId);
                    return;
                }
                if (step === 'attachments') {
                    UIModule.showAttachmentsStep();
                    return;
                }
                // Default logic for other steps
                document.querySelectorAll('.step').forEach(stepEl => {
                    stepEl.hidden = true;
                    stepEl.style.display = 'none';
                });
                
                const el = document.getElementById(`${currentStepKey}-${currentWindow}`);
                if (el) {
                    el.hidden = false;
                    el.style.display = 'block';
                    const content = el.querySelector('.content');
                    if (content && SpeechModule.autoRead) {
                        SpeechModule.speak(content.textContent);
                    }
                }
            } catch(error) {
                console.error('[ERROR] Navigation error:', error, 'currentStepKey:', currentStepKey, 'currentWindow:', currentWindow);
            }
        },

        goToNextWindow: function() {
            if (isTransitioning || RecordingModule.isRecording) return;
            isTransitioning = true;

            const currentStepKey = UIModule.stepOrder[UIModule.currentStepIndex];
            console.log('[NAV] goToNextWindow - currentStepKey:', currentStepKey, 'currentWindowIndex:', UIModule.currentWindowIndex);
            
            if (!currentStepKey) {
                UIModule.showMessage('Navigation error: invalid step index.', true);
                isTransitioning = false;
                return;
            }
            
            const currentStep = UIModule.steps[currentStepKey];
            if (!currentStep) {
                UIModule.showMessage('Navigation error: invalid step configuration.', true);
                isTransitioning = false;
                return;
            }
            
            const currentWindow = currentStep.windows[UIModule.currentWindowIndex];
            if (!currentWindow) {
                UIModule.showMessage('Navigation error: invalid window index.', true);
                isTransitioning = false;
                return;
            }
            console.log('[NAV] goToNextWindow - currentStep:', UIModule.currentStepIndex, currentStepKey, currentStep, 'currentWindow:', UIModule.currentWindowIndex, currentWindow);

            // Check if we can proceed based on recording state
            if (currentStep.requiresRecording && RecordingModule.isRecording) {
                UIModule.showMessage('Cannot proceed while recording is in progress.', true);
                isTransitioning = false;
                return;
            }
            
            // Check if we have a recording for the current window if required
            const recordingType = getRecordingTypeForWindow(currentStepKey, currentWindow);
            if (currentStep.requiresRecording && recordingType && !RecordingModule.hasRecording(recordingType)) {
                UIModule.showMessage('Please record before continuing.', true);
                isTransitioning = false;
                return;
            }
            
            // Proceed with navigation
            if (UIModule.currentWindowIndex < currentStep.windows.length - 1) {
                // If there are more windows in this step, move to next window
                UIModule.currentWindowIndex++;
                state.currentStep = currentStepKey; // Keep state in sync
                this.showCurrentWindow();
            } else {
                // If we're at the last window of this step, move to next step
                this.goToNextStep();
            }
            isTransitioning = false;
        },

        goToPrevWindow: function() {
            if (this.currentWindowIndex > 0) {
                this.currentWindowIndex--;
                this.showCurrentWindow();
            } else if (this.currentStepIndex > 0) {
                this.goToPrevStep();
            }
        },

        goToNextStep: function() {
            const currentStepKey = UIModule.stepOrder[UIModule.currentStepIndex];
            const nextStepIndex = UIModule.currentStepIndex + 1; 
            const nextStepKey = UIModule.stepOrder[nextStepIndex];

            if (nextStepIndex >= UIModule.stepOrder.length) {
                UIModule.showMessage('Already at last step.', true);
                return;
            }
            // transition from confirmation to attachments if there are transcription errors
            if (currentStepKey === 'confirmation' && UIModule.hasTranscriptionErrors) {
                UIModule.currentStepIndex = UIModule.stepOrder.indexOf('attachments');
                state.currentStep = 'attachments';
                UIModule.currentWindowIndex = 0;
                this.showCurrentWindow();
                return;
            }

            // Special handling for transition from personalInfo to confirmation
            if (currentStepKey === 'personalInfo' && nextStepKey === 'review') {
                console.log('[NAV] goToNextStep - starting submission');
                GrievanceModule.submitGrievance().then(result => {
                    UIModule.hasTranscriptionErrors = result.hasTranscriptionErrors || false;
                    // Always go to confirmation after submission
                    UIModule.currentStepIndex = UIModule.stepOrder.indexOf('confirmation');
                    state.currentStep = 'confirmation';
                    UIModule.currentWindowIndex = 0;
                    console.log('[NAV] goToNextStep - going to confirmation');
                    this.showCurrentWindow();
                }).catch(error => {
                    UIModule.showMessage('Failed to submit grievance.', true);
                    isTransitioning = false;
                });
                return; // Early return as we're handling the transition asynchronously
            } else {
                UIModule.currentStepIndex = nextStepIndex;
                state.currentStep = nextStepKey;
            }
            UIModule.currentWindowIndex = 0;
            console.log('[NAV] goToNextStep - navigation done showing window for step:', nextStepKey);
            this.showCurrentWindow();
        },

        goToPrevStep: function() {
            if (this.currentStepIndex > 0) {
                this.currentStepIndex--;
                const currentStepKey = this.stepOrder[this.currentStepIndex];
            const currentStep = this.steps[currentStepKey];
                this.currentWindowIndex = currentStep.windows.length - 1;
                this.showCurrentWindow();
            }
        },
    },
    
    showLoading: function(message) {
        // Log the message but don't show overlay notifications
        console.log('Loading:', message);
        
        // Instead of showing a notification, update a status element on the page
        // This is safer than modal popups
        const statusElement = document.getElementById('statusMessage');
        if (statusElement) {
            statusElement.textContent = message || 'Loading...';
            statusElement.className = 'status-message';
            statusElement.hidden = false;
        }
    },
    
    hideLoading: function() {
        // Hide the status element
        const statusElement = document.getElementById('statusMessage');
        if (statusElement) {
            statusElement.hidden = true;
        }
    },
    
    hideAllSteps: function() {
        document.querySelectorAll('.step').forEach(step => {
            step.hidden = true;
            step.style.display = 'none';
        });
    },
    
    showConfirmationScreen: function(grievanceId) {
        console.log("Showing confirmation screen for grievance ID:", grievanceId);

        // Hide the submission overlay
        UIModule.Overlay.hideSubmissionOverlay();

        // Hide all steps
        UIModule.hideAllSteps();

        // Show the confirmation screen
        const confirmationElement = document.getElementById('confirmation-confirmation');
        if (!confirmationElement) {
            console.error("Confirmation element not found!");
            return;
        }

        // Update the grievance ID
        const idElement = document.getElementById('grievanceId');
        if (idElement) {
            const span = idElement.querySelector('span');
            if (span) {
                span.textContent = grievanceId;
            }
        }

        // Update the success message
        const resultMessage = document.getElementById('resultMessage');
        if (resultMessage) {
            resultMessage.textContent = "Your voice grievance has been submitted successfully.";
        }

        // Ensure attachment instructions are visible
        const attachmentInstructions = document.getElementById('attachmentInstructions');
        if (attachmentInstructions) {
            attachmentInstructions.hidden = false;
        }

        // Show the confirmation screen
        confirmationElement.hidden = false;
        confirmationElement.style.display = 'block';
        window.scrollTo(0, 0);
        console.log("Confirmation screen should now be the only visible step");
    },
    
    resetApp: function() {
        this.currentStepIndex = 0;
        this.currentWindowIndex = 0;
        this.hasTranscriptionErrors = false;
        UIModule.Navigation.showCurrentWindow();
    },
    
    Overlay :{
        setupOverlayObserver: function() {
            const overlay = document.getElementById('submissionOverlay');
            if (!overlay) {
                console.error('[ERROR] Could not set up overlay observer: overlay not found');
                return;
            }
            overlayMutationObserver = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    if (mutation.type === 'attributes' && mutation.attributeName === 'hidden') {
                        console.log('[DEBUG] Overlay visibility changed:', {
                            isHidden: overlay.hidden,
                            timestamp: new Date().toISOString(),
                            stack: new Error().stack
                        });
                    }
                });
            });
            overlayMutationObserver.observe(overlay, {
                attributes: true,
                attributeFilter: ['hidden']
            });
        },
        showSubmissionOverlay: function() {
            console.log('[TRACE] showSubmissionOverlay called');
            const overlay = document.getElementById('submissionOverlay');
            if (!overlay) {
                console.error('[ERROR] Submission overlay element not found');
                return;
            }
            const message = overlay.querySelector('.submission-message');
            if (message) {
                message.textContent = 'Submitting your grievance…';
                message.style.color = '#045c94';
            }
            const cancelBtn = overlay.querySelector('#cancelSubmissionBtn');
            if (cancelBtn) {
                cancelBtn.style.display = 'none';
                if (cancelBtnTimeout) clearTimeout(cancelBtnTimeout);
                cancelBtnTimeout = setTimeout(() => {
                    cancelBtn.style.display = 'inline-block';
                }, 5000);
            }
            overlay.hidden = false;
            const submitBtn = document.getElementById('submitGrievanceBtn');
            if (submitBtn) {
                submitBtn.disabled = true;
            }
        },
        hideSubmissionOverlay: function() {
            console.log('[TRACE] hideSubmissionOverlay called');
            const overlay = document.getElementById('submissionOverlay');
            if (overlay) {
                overlay.hidden = true;
                if (cancelBtnTimeout) clearTimeout(cancelBtnTimeout);
                const submitBtn = document.getElementById('submitGrievanceBtn');
                if (submitBtn) {
                    submitBtn.disabled = false;
                }
            }
            console.log('[TRACE] hideSubmissionOverlay done');
        },
        checkForDuplicateOverlays: function() {
            const overlays = document.querySelectorAll('#submissionOverlay');
            if (overlays.length > 1) {
                console.error('[ERROR] Multiple submission overlays found:', overlays.length);
                overlays.forEach((overlay, index) => {
                    console.error(`[ERROR] Overlay ${index + 1}:`, overlay);
                });
            }
        },
        showAttachmentsStep: function() {
            this.hideAllSteps();
            const attachmentsElement = document.getElementById('attachments-attachments');
            if (attachmentsElement) {
                attachmentsElement.hidden = false;
                attachmentsElement.style.display = 'block';
            }
            // Optionally reset file upload UI
            FileUploadModule.clearFiles();
            window.scrollTo(0, 0);
            console.log("Attachments step is now visible");
        }
    },
   
    updateButtonStates: function(options = {}) {
        const {
            isRecording = false,
            hasRecording = false,
            isSubmitting = false
        } = options;
    
        // Get current step/window info
        const { step, window } = UIModule.getCurrentWindow ? UIModule.getCurrentWindow() : { step: null, window: null };
        if (!step || !window) return;
        const currentStep = UIModule.steps[step];
        if (!currentStep) return;
        const recordingType = getRecordingTypeForWindow(step, window);
    
        // Update record button
        const recordBtn = document.getElementById(`recordBtn-${step}-${window}`);
        if (recordBtn) {
            if (isSubmitting) {
                recordBtn.disabled = true;
            } else if (isRecording) {
                recordBtn.textContent = 'Stop Recording';
                recordBtn.classList.add('recording');
                recordBtn.classList.remove('waiting');
                recordBtn.disabled = false;
            } else {
                recordBtn.textContent = 'Record';
                recordBtn.classList.remove('recording', 'waiting');
                recordBtn.disabled = false;
            }
        }
    
        // Update navigation buttons
        const currentStepElement = document.getElementById(`${step}-${window}`);
        if (!currentStepElement) return;
        const navButtons = currentStepElement.querySelectorAll('.nav-btn');
        navButtons.forEach(button => {
            const action = button.getAttribute('data-action');
            if (isRecording || isSubmitting) {
                button.disabled = true;
                return;
            }
            switch (action) {
                case 'prev':
                    button.disabled = (step === 'grievance' && window === 'grievanceDetails');
                    button.style.display = '';
                    break;
                case 'next':
                    if (step === 'personalInfo' && window === 'address'){
                        button.style.display = 'none';
                        button.disabled = true;
                    } else {
                        button.disabled = !hasRecording;
                        button.style.display = '';
                    }
                    break;
                case 'continue':
                    button.disabled = !hasRecording;
                    button.style.display = '';
                    break;
                case 'retry':
                    button.disabled = isRecording;
                    button.style.display = '';
                    break;
                case 'submit':
                    if (step === 'personalInfo' && window === 'address') {
                        button.style.display = '';
                        button.disabled = isSubmitting || !(
                            RecordingModule.hasRecording('grievance_details') &&
                            RecordingModule.hasRecording('user_full_name') &&
                            RecordingModule.hasRecording('user_contact_phone') &&
                            RecordingModule.hasRecording('user_municipality') &&
                            RecordingModule.hasRecording('user_village') &&
                            RecordingModule.hasRecording('user_address')
                        );
                    } else {
                        button.style.display = 'none';
                        button.disabled = true;
                    }
                    break;
            }
            if (button.disabled) {
                button.classList.add('disabled');
            } else {
                button.classList.remove('disabled');
            }
        });
    
        // Show/hide recording indicators
        document.querySelectorAll('.recording-indicator').forEach(indicator => {
            indicator.hidden = !isRecording;
        });
    
        // Show/hide playback containers based on recording state
        document.querySelectorAll('.playback').forEach(el => el.hidden = true);
        if (hasRecording && recordedBlobs && recordedBlobs[recordingType]) {
            const playback = document.getElementById(`playback-${step}-${window}`);
            if (playback) playback.hidden = false;
        }
        const playback = document.getElementById(`playback-${step}-${window}`);
        if (playback) {
            const playbackRow = playback.querySelector('.playback-row');
            const audio = playback.querySelector('audio');
            if (recordedBlobs && recordedBlobs[recordingType]) {
                if (playbackRow) playbackRow.style.display = 'flex';
                if (audio) {
                    audio.style.display = '';
                    if (!audio.src) {
                        const audioURL = URL.createObjectURL(recordedBlobs[recordingType]);
                        audio.src = audioURL;
                    }
                }
            } else {
                if (playbackRow) playbackRow.style.display = 'none';
                if (audio) {
                    audio.style.display = 'none';
                    audio.src = '';
                }
            }
        }
    }
},
 
//     updateButtonStates: function(options = {}) {
//         const {
//             isRecording = false,
//             currentStep = state.currentStep,
//             hasRecording = false,
//             isSubmitting = false
//         } = options;
        
//         // Get current step info
//         const currentStepElement = document.querySelector('.step:not([hidden])');
//         if (!currentStepElement) return;
        
//         const stepId = currentStepElement.id;
//         const currentStepNumber = stepId.replace('step', '');
//         const currentWindow = UIModule.steps[UIModule.currentStepIndex].windows[UIModule.currentWindowIndex];
//         const recordingType = getRecordingTypeForWindow(currentWindow);
        
//         // Update record buttons
//         const recordButtons = document.querySelectorAll('[id^="recordBtn"]');
//         recordButtons.forEach(button => {
//             // Disable record buttons during submission
//             if (isSubmitting) {
//                 button.disabled = true;
//                 return;
//             }
            
//             if (isRecording) {
//                 button.textContent = 'Stop Recording';
//                 button.classList.add('recording');
//                 button.classList.remove('waiting');
//                 button.disabled = false;
//             } else {
//                 button.textContent = 'Record';
//                 button.classList.remove('recording', 'waiting');
//                 button.disabled = false;
//             }
//         });
        
//         // Update navigation buttons
//         const navButtons = currentStepElement.querySelectorAll('.nav-btn');
//         navButtons.forEach(button => {
//             const action = button.getAttribute('data-action');
            
//             // During recording or submission, all navigation is disabled
//             if (isRecording || isSubmitting) {
//                 button.disabled = true;
//                 return;
//             }
            
//             switch (action) {
//                 case 'prev':
//                     button.disabled = (currentStepNumber === '1');
//                     button.style.display = '';
//                     break;
                    
//                 case 'next':
//                 case 'continue':
//                     if (currentStepNumber === '3c') {
//                         button.style.display = 'none';
//                     } else {
//                         button.disabled = !hasRecording;
//                         button.style.display = '';
//                     }
//                     break;
                    
//                 case 'retry':
//                     button.disabled = isRecording;
//                     button.style.display = '';
//                     break;
                    
//                 case 'submit':
//                     if (currentStepNumber === '3c') {
//                         button.style.display = '';
//                         // Only enable submit if we have all required recordings
//                         button.disabled = isSubmitting || !(
//                             RecordingModule.hasRecording('grievance_details') &&
//                             RecordingModule.hasRecording('user_full_name') &&
//                             RecordingModule.hasRecording('user_contact_phone') &&
//                             RecordingModule.hasRecording('user_municipality') &&
//                             RecordingModule.hasRecording('user_village') &&
//                             RecordingModule.hasRecording('user_address')
//                         );
//                     } else {
//                         button.style.display = 'none';
//                         button.disabled = true;
//                     }
//                     break;
//             }
            
//             // Add visual indication of disabled state
//             if (button.disabled) {
//                 button.classList.add('disabled');
//             } else {
//                 button.classList.remove('disabled');
//             }
//         });
        
//         // Show/hide recording indicators
//         document.querySelectorAll('.recording-indicator').forEach(indicator => {
//             indicator.hidden = !isRecording;
//         });
        
//         // Show/hide playback containers based on recording state
//         // Hide all playback containers
//         document.querySelectorAll('.playback').forEach(el => el.hidden = true);
//         // Show only the current step's playback if a recording exists
//         if (hasRecording && recordedBlobs && recordedBlobs[recordingType]) {
//             const playback = document.getElementById(`playback${currentStepNumber}`);
//             if (playback) playback.hidden = false;
//         }

//         // ... after showing/hiding playback containers ...
//         // Hide or show the audio element based on recording
//         const playback = document.getElementById(`playback${currentStepNumber}`);
//         if (playback) {
//             const playbackRow = playback.querySelector('.playback-row');
//             const audio = playback.querySelector('audio');
//             if (recordedBlobs && recordedBlobs[recordingType]) {
//                 if (playbackRow) playbackRow.style.display = 'flex';
//                 if (audio) {
//                     audio.style.display = '';
//                     if (!audio.src) {
//                         const audioURL = URL.createObjectURL(recordedBlobs[recordingType]);
//                         audio.src = audioURL;
//                     }
//                 }
//             } else {
//                 if (playbackRow) playbackRow.style.display = 'none';
//                 if (audio) {
//                     audio.style.display = 'none';
//                     audio.src = '';
//                 }
//             }
//         }
//     }
// };

/**
 * API Module - Handles all API interactions
 */
APIModule = {
    baseUrl: '',
    endpoints: {},
    
    init: function() {
        this.baseUrl = APP_CONFIG.api.baseUrl || '';
        this.endpoints = APP_CONFIG.api.endpoints || {};
    },
    
    /**
     * Makes a fetch request to the specified endpoint
     * @param {string} endpoint - The API endpoint path
     * @param {Object} options - Fetch options
     * @returns {Promise} - Fetch promise
     */
    request: async function(endpoint, options = {}) {
        const url = this.baseUrl + endpoint;
        
        // Don't set Content-Type for FormData - browser will set it with proper boundary
        if (!(options.body instanceof FormData) && !options.headers) {
            options.headers = {
                'Content-Type': 'application/json'
            };
        }
        
        console.log(`API request to ${url}`, options);
        
        try {
            const response = await fetch(url, options);
            
            if (!response.ok) {
                throw new Error(`API error: ${response.status} ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    },
    
    /**
     * Creates a new grievance
     * @param {Object} formData - FormData object with grievance details
     * @returns {Promise} - Promise with grievance creation result
     */
    createGrievance: async function(formData) {
        return this.request(this.endpoints.submitGrievance, {
            method: 'POST',
            body: formData,
        });
    },
    
    /**
     * Uploads a file for a grievance
     * @param {string} grievanceId - The grievance ID
     * @param {Object} formData - FormData object with file data
     * @returns {Promise} - Promise with file upload result
     */
    uploadFile: async function(grievanceId, formData) {
        console.log(`Uploading files for grievance ID: ${grievanceId}`);
        
        // Make sure grievance_id is in the formData
        if (!formData.has('grievance_id')) {
            formData.append('grievance_id', grievanceId);
        }
        
        // Use accessible-file-upload endpoint for better handling of multiple files
        const endpoint = this.endpoints.accessibleFileUpload;
        const url = this.baseUrl + endpoint;
        
        console.log(`Sending files to endpoint: ${url}`);
        
        try {
            // Log some debugging info about what's in the formData
            console.log("FormData contents (keys only):");
            for (const key of formData.keys()) {
                if (key === 'files[]') {
                    const files = formData.getAll('files[]');
                    console.log(`- ${key}: ${files.length} files`);
                    files.forEach((file, i) => {
                        console.log(`  - File ${i+1}: ${file.name} (${file.size} bytes)`);
                    });
                } else {
                    console.log(`- ${key}: ${formData.get(key)}`);
                }
            }
            
            // Make the request
            const response = await fetch(url, {
                method: 'POST',
                body: formData,
            });
            
            if (!response.ok) {
                console.error(`API error: ${response.status} ${response.statusText}`);
                
                // Try to get more detailed error info
                let errorDetails;
                try {
                    errorDetails = await response.json();
                    console.error("Error details:", errorDetails);
            } catch (e) {
                    // If response is not JSON, get text instead
                    try {
                        errorDetails = await response.text();
                        console.error("Error response:", errorDetails);
                    } catch (e2) {
                        console.error("Could not parse error response");
                    }
                }
                
                throw new Error(`API error: ${response.status} ${response.statusText}`);
            }
            
            const result = await response.json();
            console.log("File upload result:", result);
            return result;
        } catch (error) {
            console.error('File upload request failed:', error);
            throw error;
        }
    },
    
    /**
     * Checks the status of a grievance
     * @param {string} grievanceId - The grievance ID
     * @returns {Promise} - Promise with grievance status
     */
    checkGrievanceStatus: async function(grievanceId) {
        const endpoint = `${this.endpoints.checkStatus}?grievance_id=${grievanceId}`;
        
        return this.request(endpoint, {
            method: 'GET',
        });
    }
},

/**
 * File Upload Module - Handles file selection and uploads
 */
FileUploadModule = {
    selectedFiles: [],
    uploadedFiles: [],
    maxFileSize: 0,
    allowedFileTypes: [],
    
    init: function() {
        this.maxFileSize = APP_CONFIG.upload.maxFileSize || 10 * 1024 * 1024; // 10MB default
        this.allowedFileTypes = APP_CONFIG.upload.allowedTypes || [];
        
        this.setupFileInput();
        this.setupFileDrop();
        this.setupAttachmentButtons();
    },
    
    setupFileInput: function() {
        const fileInput = document.getElementById('fileInput');
        const fileList = document.getElementById('fileList');
        
        if (fileInput && fileList) {
            fileInput.addEventListener('change', (event) => {
                this.handleFileSelection(event.target.files);
            });
        }
    },
    
    setupAttachmentButtons: function() {
        // Setup attach files button
        const attachFilesBtn = document.getElementById('attachFilesBtn');
        if (attachFilesBtn) {
            attachFilesBtn.addEventListener('click', () => {
                const fileInput = document.getElementById('fileInput');
                if (fileInput) {
                    fileInput.click();
                }
            });
        }
        
        // Setup submit files button
        const submitFilesBtn = document.getElementById('submitFilesBtn');
        if (submitFilesBtn) {
            submitFilesBtn.addEventListener('click', () => {
                this.submitSelectedFiles();
            });
        }
        
        // Setup attach more files button
        const attachMoreBtn = document.getElementById('attachMoreBtn');
        if (attachMoreBtn) {
            attachMoreBtn.addEventListener('click', () => {
                // Clear existing selected files first
                this.selectedFiles = [];
                this.updateFileList();
                
                // Then show attach button and trigger file input
                const fileInput = document.getElementById('fileInput');
                if (fileInput) {
                    fileInput.click();
                }
            });
        }
    },
    
    setupFileDrop: function() {
        const dropZone = document.getElementById('dropZone');
        
        if (dropZone) {
            // Prevent default drag behaviors
            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                dropZone.addEventListener(eventName, preventDefaults, false);
            });
            
            function preventDefaults(e) {
                e.preventDefault();
                e.stopPropagation();
            }
            
            // Highlight drop zone when item is dragged over it
            ['dragenter', 'dragover'].forEach(eventName => {
                dropZone.addEventListener(eventName, () => {
                    dropZone.classList.add('highlight');
                }, false);
            });
            
            ['dragleave', 'drop'].forEach(eventName => {
                dropZone.addEventListener(eventName, () => {
                    dropZone.classList.remove('highlight');
                }, false);
            });
            
            // Handle dropped files
            dropZone.addEventListener('drop', (e) => {
                const dt = e.dataTransfer;
                const files = dt.files;
                this.handleFileSelection(files);
            }, false);
        }
    },
    
    handleFileSelection: function(fileList) {
        if (!fileList || fileList.length === 0) return;
        
        // Convert FileList to Array for easier manipulation
        const files = Array.from(fileList);
        
        // Validate files
        const validFiles = files.filter(file => this.validateFile(file));
        
        // Add valid files to selected files array
        this.selectedFiles = [...this.selectedFiles, ...validFiles];
        
        // Update UI
        this.updateFileList();
        
        // Show the file list
        const fileListElement = document.getElementById('fileList');
        if (fileListElement) {
            fileListElement.hidden = false;
        }
        
        // Announce for screen readers
        SpeechModule.speak(`${validFiles.length} files selected. Review the files and click Submit Files when ready.`);
    },
    
    validateFile: function(file) {
        // Check file size
        if (file.size > this.maxFileSize) {
            UIModule.showMessage(`File ${file.name} is too large. Maximum size is ${this.maxFileSize / (1024 * 1024)}MB.`, true);
            return false;
        }
        
        // Check file type if restrictions exist
        if (this.allowedFileTypes.length > 0) {
            const fileType = file.type.toLowerCase();
            const fileName = file.name.toLowerCase();
            const isAllowed = this.allowedFileTypes.some(type => {
                return fileType.includes(type) || fileName.endsWith(`.${type}`);
            });
            
            if (!isAllowed) {
                UIModule.showMessage(`File ${file.name} is not allowed. Allowed types: ${this.allowedFileTypes.join(', ')}`, true);
                return false;
            }
        }
        
        return true;
    },
    
    updateFileList: function() {
        const fileListElement = document.getElementById('fileList');
        if (!fileListElement) return;
        
        const listElement = fileListElement.querySelector('ul') || document.createElement('ul');
        
        // Clear existing list
        listElement.innerHTML = '';
        
        // Add files to list
        this.selectedFiles.forEach((file, index) => {
            const listItem = document.createElement('li');
            
            // Format file size
            const fileSize = file.size < 1024 * 1024
                ? `${Math.round(file.size / 1024)} KB`
                : `${Math.round(file.size / (1024 * 1024) * 10) / 10} MB`;
            
            listItem.textContent = `${file.name} (${fileSize})`;
            
            // Add remove button
            const removeButton = document.createElement('button');
            removeButton.textContent = 'Remove';
            removeButton.setAttribute('type', 'button');
            removeButton.setAttribute('aria-label', `Remove file ${file.name}`);
            removeButton.classList.add('remove-file-btn');
            
            removeButton.addEventListener('click', () => {
                this.removeFile(index);
            });
            
            listItem.appendChild(removeButton);
            listElement.appendChild(listItem);
        });
        
        // Add the list to the container if it's not already there
        if (!fileListElement.contains(listElement)) {
            fileListElement.appendChild(listElement);
        }
        
        // Show or hide the file list section based on whether there are files
        fileListElement.hidden = this.selectedFiles.length === 0;
    },
    
    removeFile: function(index) {
        if (index >= 0 && index < this.selectedFiles.length) {
            const fileName = this.selectedFiles[index].name;
            this.selectedFiles.splice(index, 1);
            this.updateFileList();
            SpeechModule.speak(`File ${fileName} removed.`);
        }
    },
    
    submitSelectedFiles: async function() {
        if (!state.grievanceId) {
            UIModule.showMessage('No grievance ID found. Cannot upload files.', true);
            return;
        }
        
        if (this.selectedFiles.length === 0) {
            UIModule.showMessage('No files selected for upload.', true);
                return;
            }
            
        try {
            UIModule.showLoading('Uploading files...');
            
            const uploadResult = await this.uploadFiles(state.grievanceId);
            
            if (uploadResult.success) {
                // Add to uploaded files list
                this.uploadedFiles = [...this.uploadedFiles, ...uploadResult.results.map(result => ({
                    fileName: result.fileName,
                    fileSize: result.fileSize || 'Unknown size'
                }))];
                
                // Show success message
                const successMessage = document.getElementById('uploadSuccessMessage');
                if (successMessage) {
                    successMessage.textContent = `${this.selectedFiles.length} ${this.selectedFiles.length === 1 ? 'file' : 'files'} uploaded successfully!`;
                }
                
                // Update uploaded files list
                this.updateUploadedFilesList();
                
                // Show the uploaded files section
                const uploadedFilesSection = document.getElementById('uploadedFilesSection');
                if (uploadedFilesSection) {
                    uploadedFilesSection.hidden = false;
                }
                
                // Clear selected files for next upload if needed
                this.selectedFiles = [];
                this.updateFileList();
                
                // Hide file list section
                const fileListElement = document.getElementById('fileList');
                if (fileListElement) {
                    fileListElement.hidden = true;
                }
                
                // Announce success
                SpeechModule.speak(`${uploadResult.results.length} files uploaded successfully. You can attach more files if needed.`);
            } else {
                UIModule.showMessage('Some files failed to upload. Please try again.', true);
                SpeechModule.speak('Some files failed to upload. Please try again.');
            }
        } catch (error) {
            console.error('Error uploading files:', error);
            UIModule.showMessage('Error uploading files. Please try again.', true);
            SpeechModule.speak('Error uploading files. Please try again.');
        } finally {
            UIModule.hideLoading();
        }
    },
    
    updateUploadedFilesList: function() {
        const uploadedFilesList = document.getElementById('uploadedFilesList');
        if (!uploadedFilesList) return;
        
        const listElement = uploadedFilesList.querySelector('ul') || document.createElement('ul');
        
        // Clear existing list
        listElement.innerHTML = '';
        
        // Add files to list
        this.uploadedFiles.forEach((file) => {
            const listItem = document.createElement('li');
            listItem.textContent = `${file.fileName} (${file.fileSize})`;
            listElement.appendChild(listItem);
        });
        
        // Add the list to the container if it's not already there
        if (!uploadedFilesList.contains(listElement)) {
            uploadedFilesList.appendChild(listElement);
        }
    },
    
    uploadFiles: async function(grievanceId) {
        if (!grievanceId || this.selectedFiles.length === 0) {
            return { success: true, message: 'No files to upload' };
        }
        
        const results = [];
        
        try {
            // Create a single FormData object for all files
            const formData = new FormData();
            
            // Add grievance_id to FormData
            formData.append('grievance_id', grievanceId);
            
            // Add interface language if available
            const htmlLang = document.documentElement.lang || 'ne';
            formData.append('interface_language', htmlLang);
            
            // Add all files under the 'files[]' key as expected by the server
            for (const file of this.selectedFiles) {
                formData.append('files[]', file);
                console.log(`Adding file to FormData: ${file.name}, size: ${file.size} bytes`);
            }
            
            // Upload all files in a single request
            console.log(`Uploading ${this.selectedFiles.length} files for grievance ID: ${grievanceId}`);
            const result = await APIModule.uploadFile(grievanceId, formData);
            
            // Process results
            if (result && (result.status === 'success' || result.success)) {
                // Handle successful upload
                for (const file of this.selectedFiles) {
                    results.push({
                        fileName: file.name,
                        fileSize: file.size < 1024 * 1024
                            ? `${Math.round(file.size / 1024)} KB`
                            : `${Math.round(file.size / (1024 * 1024) * 10) / 10} MB`,
                        success: true
                    });
                }
            } else {
                // Handle error
                throw new Error(result.error || result.message || "Failed to upload files");
            }
        } catch (error) {
            console.error(`Error uploading files:`, error);
            // Mark all files as failed
            for (const file of this.selectedFiles) {
                results.push({
                    fileName: file.name,
                    success: false,
                    error: error.message
                });
            }
        }
        
        // Check if all uploads were successful
        const allSuccessful = results.every(result => result.success);
        
        return {
            success: allSuccessful,
            results: results,
            message: allSuccessful
                ? 'All files uploaded successfully'
                : 'Some files failed to upload'
        };
    },
    
    clearFiles: function() {
        this.selectedFiles = [];
        this.uploadedFiles = [];
        this.updateFileList();
        
        const uploadedFilesSection = document.getElementById('uploadedFilesSection');
        if (uploadedFilesSection) {
            uploadedFilesSection.hidden = true;
        }
    }
};

/**
 * Recording Module - Handles audio recording functionality
 */
RecordingModule = {
    recorder: null,
    stream: null,
    isRecording: false,
    chunks: [],
    recordingType: null,
    permissionGranted: false,
    
    init: function() {
        this.requestMicrophonePermission();
        console.log('Recording module initialized');
    },
    
    /**
     * Request microphone permission early to avoid disrupting the flow later
     */
    requestMicrophonePermission: function() {
        // Show a subtle notification that we're requesting microphone access
        const micPermissionNote = document.createElement('div');
        micPermissionNote.className = 'mic-permission-note';
        micPermissionNote.textContent = 'Requesting microphone access...';
        micPermissionNote.style.position = 'fixed';
        micPermissionNote.style.bottom = '10px';
        micPermissionNote.style.right = '10px';
        micPermissionNote.style.padding = '8px 12px';
        micPermissionNote.style.backgroundColor = 'rgba(0,0,0,0.7)';
        micPermissionNote.style.color = 'white';
        micPermissionNote.style.borderRadius = '4px';
        micPermissionNote.style.fontSize = '14px';
        micPermissionNote.style.zIndex = '9999';
        document.body.appendChild(micPermissionNote);
        
        // Request microphone permission early
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(stream => {
                console.log('Microphone permission granted during initialization');
                this.permissionGranted = true;
                
                // Stop tracks immediately, we just needed the permission
                stream.getTracks().forEach(track => track.stop());
                
                // Remove the notification
                if (micPermissionNote.parentNode) {
                    micPermissionNote.parentNode.removeChild(micPermissionNote);
                }
                
                // Replace with success notification that fades out
                const successNote = document.createElement('div');
                successNote.className = 'mic-permission-success';
                successNote.textContent = 'Microphone access granted';
                successNote.style.position = 'fixed';
                successNote.style.bottom = '10px';
                successNote.style.right = '10px';
                successNote.style.padding = '8px 12px';
                successNote.style.backgroundColor = 'rgba(43,138,62,0.9)';
                successNote.style.color = 'white';
                successNote.style.borderRadius = '4px';
                successNote.style.fontSize = '14px';
                successNote.style.zIndex = '9999';
                successNote.style.transition = 'opacity 1s ease-out';
                document.body.appendChild(successNote);
                
                // Fade out and remove after 3 seconds
                setTimeout(() => {
                    successNote.style.opacity = '0';
                    setTimeout(() => {
                        if (successNote.parentNode) {
                            successNote.parentNode.removeChild(successNote);
            }
        }, 1000);
                }, 3000);
            })
            .catch(error => {
                console.warn('Failed to get microphone permission during initialization:', error);
                
                // Remove the notification
                if (micPermissionNote.parentNode) {
                    micPermissionNote.parentNode.removeChild(micPermissionNote);
                }
                
                // We'll try again when the user clicks record
            });
    },
    
    setupRecordingControls: function() {
        // Get all record buttons
        const recordButtons = document.querySelectorAll('.record-btn');
        recordButtons.forEach(button => {
            button.addEventListener('click', () => {
                const { step, window } = UIModule.getCurrentWindow();
                const recordingType = getRecordingTypeForWindow(step, window);
                if (recordingType) {
                this.startRecording(recordingType);
            }
        });
        });
    },

    
    /**
     * Request microphone access and start recording
     * @param {string} recordingType - Type of recording (e.g., 'grievance', 'name')
     */
    startRecording: async function(recordingType) {
        if (this.isRecording) {
            console.log('Already recording');
            return;
        }
        
        this.recordingType = recordingType;
        console.log(`Starting recording for: ${recordingType}`);
        
        // Get current window using the helper
        const { step, window } = UIModule.getCurrentWindow();
        
        // Find the record button for this type
        const recordBtn = document.getElementById(`recordBtn-${step}-${window}`);
        const statusEl = document.getElementById(`status-${step}-${window}`);
        const playbackContainer = document.getElementById(`playback-${step}-${window}`);
        
        // Hide audio player during recording
        if (playbackContainer) {
            playbackContainer.hidden = true;
        }
        
        if (recordBtn) {
            // Update button text to indicate waiting for permission
            recordBtn.textContent = this.permissionGranted ? "Preparing recording..." : "Waiting for microphone...";
            recordBtn.classList.add("waiting");
            recordBtn.disabled = true;
        }
        
        if (statusEl) {
            statusEl.hidden = false;
            // Clear any existing content
            statusEl.innerHTML = this.permissionGranted ? 
                '<div class="recording-status">Preparing recorder...</div>' : 
                '<div class="recording-status">Waiting for microphone access...</div>';
        }
        
        try {
            // Request microphone access
            this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.permissionGranted = true;
            
            // Create MediaRecorder
            const options = { mimeType: 'audio/webm' };
            try {
                this.recorder = new MediaRecorder(this.stream, options);
            } catch (e) {
                console.warn(`MediaRecorder not available with specified options: ${e.message}`);
                this.recorder = new MediaRecorder(this.stream);
            }
            
            this.chunks = [];
            
            // Setup recorder event handlers
            this.recorder.ondataavailable = (event) => {
                if (event.data && event.data.size > 0) {
                    this.chunks.push(event.data);
                    console.log(`Recording chunk received: ${event.data.size} bytes`);
                }
            };
            
            this.recorder.onstop = () => {
                const blob = new Blob(this.chunks, { type: 'audio/webm' });
                console.log(`Recording stopped, blob size: ${blob.size} bytes`);
                this.saveRecording(blob);
                
                // Release microphone
                this.stream.getTracks().forEach(track => track.stop());
                this.stream = null;
            };
            
            // Start recording with timeslices to get data during recording
            this.recorder.start(1000); // Get data every second
            this.isRecording = true;
            
            // Start timer for recording duration
            this.startTimer(recordingType);
            
            // Update UI to show recording state
            this.updateRecordingUI(true);
            
            console.log(`Recording started for ${recordingType}`);
            SpeechModule.speak('Recording started');
        } catch (error) {
            console.error('Error starting recording:', error);
            this.permissionGranted = false;
            
            // Reset button state
            if (recordBtn) {
                recordBtn.textContent = "Record";
                recordBtn.classList.remove("waiting");
                recordBtn.disabled = false;
            }
            
            // Show error in status area
            if (statusEl) {
                statusEl.innerHTML = '<div class="recording-error">Microphone access denied. Please check permissions and try again.</div>';
            }
            
            SpeechModule.speak('Could not access microphone. Please check permissions and try again.');
        }
    },
    
    startTimer: function(recordingType) {
        // Get current window using the helper
        const { step, window } = UIModule.getCurrentWindow();
        const statusElement = document.getElementById(`status-${step}-${window}`);
        
        if (!statusElement) {
            console.warn(`Status element not found for window: ${step} - ${window}`);
            return;
        }
        
        // Show the status element
        statusElement.hidden = false;
        
        // Create recording indicator with timer
        statusElement.innerHTML = `
            <div class="recording-indicator">
                <div class="recording-pulse"></div>
                <div class="recording-label">Recording:</div>
                <div class="recording-timer">0:00</div>
            </div>
        `;
        
        // Get the timer element
        const timerElement = statusElement.querySelector('.recording-timer');
        
        // Reset timer
        let seconds = 0;
        
        // Clear any existing timer
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
        }
        
        // Start timer
        this.timerInterval = setInterval(() => {
            seconds++;
            const minutes = Math.floor(seconds / 60);
            const remainingSeconds = seconds % 60;
            const timeText = `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
            
            if (timerElement) {
                timerElement.textContent = timeText;
            }
            
            console.log(`Recording time: ${timeText}`);
        }, 1000);
    },
    
    /**
     * Stop the current recording
     */
    stopRecording: function() {
        if (!this.isRecording || !this.recorder) {
            console.log('Not recording');
            return;
        }
        console.log('Stopping recording');
        let finalTime = '0:00';
        
        // Get current window using the helper
        const { step, window } = UIModule.getCurrentWindow();
        const statusElement = document.getElementById(`status-${step}-${window}`);
        
        if (statusElement) {
            const timerElement = statusElement.querySelector('.recording-timer');
            if (timerElement) {
                finalTime = timerElement.textContent;
                console.log(`Final recording time: ${finalTime}`);
            }
            statusElement.innerHTML = `
                <div class="recording-complete">
                    <div class="recording-complete-icon">✓</div>
                    <div class="recording-complete-label"> Recorded:</div>
                    <div class="recording-complete-time">${finalTime}</div>
                </div>
            `;
        }
        
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
        
        try {
            this.recorder.stop();
        } catch (e) {
            console.error('Error stopping recorder:', e);
        }
        
        this.isRecording = false;
        
        // Show playback container
        const playbackContainer = document.getElementById(`playback-${step}-${window}`);
        if (playbackContainer) {
            playbackContainer.hidden = false;
        }
        
        // Update UI after recording stops
        this.updateRecordingUI(false);
        
        console.log(`Stopped recording for step ${step} - window ${window}, waiting for user action.`);
        SpeechModule.speak('Recording stopped. Please review and continue.');
    },
    
    saveRecording: function(blob) {
        if (!recordedBlobs) {
            recordedBlobs = {};
        }
        
        recordedBlobs[this.recordingType] = blob;
        
        // Create audio element for preview
        this.createAudioPreview(blob, this.recordingType);
        
        console.log(`Recording saved as ${this.recordingType}`);
        
        // Let updateRecordingUI handle all button states
        this.updateRecordingUI(false);
    },
    
    /**
     * Create an audio element to preview the recording
     * @param {Blob} blob - The audio blob
     * @param {string} recordingType - Type of recording
     */
    createAudioPreview: function(blob, recordingType) {
        // Find the step/window for this recordingType
        let step = null, windowName = null;
        for (const s in windowToRecordingTypeMap) {
            for (const w in windowToRecordingTypeMap[s]) {
                if (windowToRecordingTypeMap[s][w] === recordingType) {
                    step = s;
                    windowName = w;
                    break;
                }
            }
            if (step && windowName) break;
        }
        if (!step || !windowName) {
            console.warn(`No step/window found for recordingType: ${recordingType}`);
            return;
        }
        const previewContainerId = `playback-${step}-${windowName}`;
        const container = document.getElementById(previewContainerId);
        
        if (container) {
            // Get audio element
            let audio = container.querySelector('audio');
            if (!audio) {
                audio = document.createElement('audio');
                audio.controls = true;
                audio.className = 'recording-player';
                container.prepend(audio);
            }
            
            // Remove recording-in-progress class if present
            audio.classList.remove('recording-in-progress');
            
            // Remove data-recording attribute
            audio.removeAttribute('data-recording');
            
            // Set the audio source
            const audioURL = URL.createObjectURL(blob);
            audio.src = audioURL;
            
            // Add play/pause event listeners
            audio.addEventListener('play', () => {
                if (SpeechModule.stopSpeaking) {
                    SpeechModule.stopSpeaking();
                }
            });
            
            // Add aria-label
            audio.setAttribute('aria-label', `${recordingType} recording preview`);
            
            // Show the container
            container.hidden = false;
        } else {
            console.warn(`Preview container not found: ${previewContainerId}`);
        }
    },
    
    /**
     * Update UI elements based on recording state
     * @param {boolean} isRecording - Whether recording is in progress
     */
    updateRecordingUI: function(isRecording) {
        UIModule.updateButtonStates({
            isRecording: isRecording,
            hasRecording: this.hasRecording(this.recordingType),
            isSubmitting: isSubmitting
        });
    },
    
    /**
     * Check if there are any recordings
     * @returns {boolean} - Whether any recordings exist
     */
    hasRecordings: function() {
        return recordedBlobs && Object.keys(recordedBlobs).length > 0;
    },
    
    /**
     * Clear all recordings
     */
    clearRecordings: function() {
        recordedBlobs = {};
        
        // Clear all preview containers
        const previewContainers = document.querySelectorAll('[id^="playback"]');
        previewContainers.forEach(container => {
            const audio = container.querySelector('audio');
            if (audio) {
                audio.src = '';
            }
            container.hidden = true;
        });
        
        // Reset all status displays
        const statusElements = document.querySelectorAll('[id^="status"]');
        statusElements.forEach(element => {
            const span = element.querySelector('span');
            if (span) {
                span.textContent = '0:00';
            }
            element.hidden = true;
        });
    },
    
    
    /**
     * Checks if a recording exists for the given type
     */
    hasRecording: function(type) {
        return recordedBlobs && !!recordedBlobs[type];
    }
};

/**
 * Grievance Module - Handles grievance submission flow
 */
GrievanceModule = {
    categories: [],
    
    init: function() {
        console.log("Initializing Grievance Module");
        this.loadCategories();
        
        console.log("Grievance Module initialized with steps:", );
    },
    
    loadCategories: function() {
        // Load categories from config or API
        this.categories = APP_CONFIG.grievanceCategories || [];
        this.populateCategoryDropdown();
    },
    
    populateCategoryDropdown: function() {
        const categorySelect = document.getElementById('grievanceCategory');
        if (!categorySelect) return;
        
        // Clear existing options
        categorySelect.innerHTML = '';
        
        // Add default option
        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = 'Select a category';
        categorySelect.appendChild(defaultOption);
        
        // Add categories
        this.categories.forEach(category => {
            const option = document.createElement('option');
            option.value = category.id || category.value || category;
            option.textContent = category.label || category;
            categorySelect.appendChild(option);
        });
    },
    
    
    validateCurrentStep: function() {
        const { step, window } = UIModule.getCurrentWindow();
        const recordingType = getRecordingTypeForWindow(step, window);
        // Check if recording exists for the current window
        if (recordingType && !RecordingModule.hasRecording(recordingType)) {
            console.warn(`Missing ${recordingType} recording, but proceeding anyway`);
            return true; // Allow to proceed anyway
        }
        return true; // Always return true to allow proceeding
    },
    
    
    getFieldLabel: function(fieldName) {
        // Map field names to user-friendly labels
        const labelMap = {
            'name': 'Name',
            'phone': 'Phone Number',
            'email': 'Email',
            'grievanceCategory': 'Grievance Category',
            'location': 'Location',
            'details': 'Additional Details'
        };
        
        return labelMap[fieldName] || fieldName;
    },
    
    getRecordingLabel: function(recordingType) {
        // Map recording types to user-friendly labels
        const labelMap = {
            'grievance': 'Grievance',
            'name': 'Name',
            'contact': 'Contact Information',
            'location': 'Location'
        };
        
        return labelMap[recordingType] || recordingType;
    },
    
    
    submitGrievance: async function() {
        try {
            // Prevent submission if recording is in progress or we're still navigating
            if (RecordingModule.isRecording) {
                console.log("Cannot submit: recording in progress or navigation not complete");
                UIModule.showMessage('Please wait for navigation to complete before submitting.', true);
                return;
            }
            isTransitioning = true;

            // Check if we're on the final step
            const { step, window } = UIModule.getCurrentWindow();
            if (!(step === 'personalInfo' && window === 'address')) {
                console.log("Cannot submit from step/window:", step, window);
                UIModule.showMessage('Please complete all steps before submitting.', true);
                return;
            }

            console.log("Starting grievance submission process");
            UIModule.Overlay.showSubmissionOverlay();
            
            // Create form data from JS state
            const formData = new FormData();
            // If you have any text fields, add them here, e.g.:
            // formData.append('user_full_name', yourNameVariable);
            // Add interface language
            const htmlLang = document.documentElement.lang || 'ne';
            formData.append('interface_language', htmlLang);
            
            // Add voice recordings
            let recordingsCount = 0;
            for (const type in recordedBlobs) {
                const blob = recordedBlobs[type];
                const fileName = `${type}.webm`;
                formData.append(type, blob, fileName);
                recordingsCount++;
            }
            
            console.log(`Adding ${recordingsCount} recordings to form data`);
            
            if (recordingsCount === 0) {
                throw new Error("No voice recordings found!");
            }
            
            // Submit grievance recordings
            console.log("Sending API request to create grievance");
            const response = await APIModule.createGrievance(formData);
            console.log("API response:", response);
            
            if (!response.success && response.status !== 'success') {
                throw new Error(response.message || response.error || 'Failed to submit grievance');
            }
            
            // Store the grievance ID returned from the server
            state.grievanceId = response.grievance_id || response.id;
            console.log("Received grievance ID from server:", state.grievanceId);
            
            // First hide any visible steps to avoid UI state conflicts
            console.log("Hiding all current steps before showing confirmation");
            UIModule.hideAllSteps();
            
            // Hide submission overlay before showing confirmation screen
            UIModule.Overlay.hideSubmissionOverlay();
            
            // Show confirmation screen using the UIModule function
            console.log("Now showing confirmation screen");
            UIModule.showConfirmationScreen(state.grievanceId);
            
            // Prepare file upload UI
            const fileListElement = document.getElementById('fileList');
            if (fileListElement) {
                fileListElement.hidden = true;
            }
            
            // Now announce the success with callback to hide the indicator when done
            SpeechModule.speak('Your grievance has been submitted successfully. Your grievance ID is ' + 
                state.grievanceId.split('').join(' ') + '. You can now attach photos or documents.', function() {
                    if (speechIndicator && isSpeechIndicatorEnabled) {
                        speechIndicator.classList.remove('active');
                    }
                })
                
            return {hasTranscriptionErrors: false,
                grievanceId: state.grievanceId
            };
                
        } catch (error) {
            console.error('Error submitting grievance:', error);
            UIModule.showMessage('There was an error submitting your grievance. Please try again.', true);
            SpeechModule.speak('There was an error submitting your grievance. Please try again.');
            UIModule.Overlay.hideSubmissionOverlay();
        } finally {
                isTransitioning = false;
        }
    },
    
    
    showStatusMessage: function(message, isError = false) {
        // Log the message but don't show overlay notifications
        console.log(isError ? 'Error:' : 'Message:', message);
        
        // Instead of showing a notification, update a status element on the page
        // This is safer than modal popups
        const statusElement = document.getElementById('statusMessage');
        if (statusElement) {
            statusElement.textContent = message;
            statusElement.className = isError ? 'status-error' : 'status-message';
            statusElement.hidden = false;
            
            // Auto-hide after a few seconds
            setTimeout(() => {
                statusElement.hidden = true;
            }, 3000);
        }
    },

    showExitConfirmation: function() {
        // Implement as needed
    },

    loadReviewData: async function(grievanceId) {
        try {
            // Show loading state
            UIModule.showLoading('Loading grievance data...');
            
            // Fetch the review data
            const response = await APIModule.request(`/api/grievance/${grievanceId}/review`, {
                method: 'GET'
            });
            
            if (!response.success) {
                throw new Error(response.message || 'Failed to load grievance data');
            }
            
            // Store the data for later use
            this.reviewData = response.data;
            
            // Populate the review UI
            this.populateReviewUI(response.data);
            
            // Show success message
            UIModule.showMessage('Grievance data loaded successfully');
            
    } catch (error) {
            console.error('Error loading grievance data:', error);
            UIModule.showMessage('Failed to load grievance data. Please try again.', true);
        } finally {
            UIModule.hideLoading();
        }
    },

    populateReviewUI: function(data) {
        // Populate grievance details
        const grievanceDetails = document.getElementById('grievanceDetailsReview');
        if (grievanceDetails) {
            grievanceDetails.textContent = data.grievance_details || '';
        }

        // Populate categories
        const categoriesContainer = document.getElementById('grievanceCategoriesReview');
        if (categoriesContainer) {
            categoriesContainer.innerHTML = '';
            (data.categories || []).forEach(category => {
                const categoryEl = document.createElement('div');
                categoryEl.className = 'category-item';
                categoryEl.textContent = category;
                categoriesContainer.appendChild(categoryEl);
            });
        }

        // Populate user details
        const userDetails = {
            'userNameReview': data.user_full_name,
            'userPhoneReview': data.user_contact_phone,
            'userMunicipalityReview': data.user_municipality,
            'userVillageReview': data.user_village,
            'userAddressReview': data.user_address
        };

        Object.entries(userDetails).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = value || '';
            }
        });
    },

    // ... rest of GrievanceModule ...
};

ModifyModule = {
    init: function() {
        this.setupModifyUI();
        this.setupEventListeners();
    },

    setupModifyUI: function() {
        // Create modification interface
        const modifyContainer = document.createElement('div');
        modifyContainer.id = 'modifyContainer';
        modifyContainer.className = 'modify-container';
        modifyContainer.hidden = true;
        
        // Add transcript display
        const transcriptArea = document.createElement('div');
        transcriptArea.id = 'transcriptArea';
        transcriptArea.className = 'transcript-area';
        transcriptArea.contentEditable = true;
        
        // Add controls
        const controls = document.createElement('div');
        controls.className = 'modify-controls';
        controls.innerHTML = `
            <button class="save-btn">Save Changes</button>
            <button class="cancel-btn">Cancel</button>
        `;
        
        modifyContainer.appendChild(transcriptArea);
        modifyContainer.appendChild(controls);
        document.body.appendChild(modifyContainer);
    },

    setupEventListeners: function() {
        // Handle save/cancel buttons
        document.querySelector('.save-btn').addEventListener('click', () => this.saveChanges());
        document.querySelector('.cancel-btn').addEventListener('click', () => this.hideModifyInterface());
    },

    modifyRecording: async function(recordingType) {
        try {
            // Show loading state
            UIModule.showLoading('Loading transcript...');
            
            // Get transcript from API
            const transcript = await this.getTranscript(recordingType);
            
            // Show modification interface
            this.showModifyInterface(transcript);
            
            // Store current recording type
            this.currentRecordingType = recordingType;
            
        } catch (error) {
            console.error('Error loading transcript:', error);
            UIModule.showMessage('Failed to load transcript. Please try again.', true);
        } finally {
            UIModule.hideLoading();
        }
    },

    getTranscript: async function(recordingType) {
        // API call to get transcript
        const response = await APIModule.request('/api/transcript', {
            method: 'GET',
            params: { recordingType }
        });
        return response.transcript;
    },

    saveChanges: async function() {
        try {
            const transcript = document.getElementById('transcriptArea').textContent;
            
            // Save to API
            await APIModule.request('/api/transcript', {
                method: 'POST',
                body: {
                    recordingType: this.currentRecordingType,
                    transcript
                }
            });
            
            // Hide interface
            this.hideModifyInterface();
            
            // Show success message
            UIModule.showMessage('Changes saved successfully');
            
        } catch (error) {
            console.error('Error saving changes:', error);
            UIModule.showMessage('Failed to save changes. Please try again.', true);
        }
    },

    showModifyInterface: function(transcript) {
        const container = document.getElementById('modifyContainer');
        const transcriptArea = document.getElementById('transcriptArea');
        
        // Set transcript content
        transcriptArea.textContent = transcript;
        
        // Show container
        container.hidden = false;
        
        // Focus transcript area
        transcriptArea.focus();
    },

    hideModifyInterface: function() {
        const container = document.getElementById('modifyContainer');
        container.hidden = true;
        
        // Clear current recording type
        this.currentRecordingType = null;
    }
};

/**
 * Event Module - Centralizes all event listeners
 */
EventModule = {
    init: function() {
        console.log('EventModule.init called');
        this.setupModifyButtons();
        this.setupNavigationButtons();
        this.setupRecordButtons();
        this.setupFileUploadButtons();
        this.setupAccessibilityButtons();
        this.setupDialogButtons();
        this.setupActionButtons(); // Add this line
    },

    setupModifyButtons: function() {
        // Handle modify recording buttons
        document.querySelectorAll('.modify-btn[data-recording-type]').forEach(btn => {
            btn.addEventListener('click', () => {
                const type = btn.dataset.recordingType;
                ModifyModule.modifyRecording(type);
            });
        });

        // Handle categories dropdown
        document.querySelectorAll('.modify-btn[data-action="show-categories"]').forEach(btn => {
            btn.addEventListener('click', () => {
                UIModule.showCategoriesDropdown();
            });
        });
    },

    setupNavigationButtons: function() {
        // Handle navigation buttons
        document.querySelectorAll('.nav-btn[data-action]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const action = btn.dataset.action;
                if (RecordingModule.isRecording) return;

                switch(action) {
                    case 'next':
                    case 'continue':
                    case 'submit':
                        UIModule.Navigation.goToNextWindow();
                        break;
                    case 'prev':
                        UIModule.Navigation.goToPrevWindow();
                        break;
                    case 'retry':
                const { step, window } = UIModule.getCurrentWindow();
                const recordingType = getRecordingTypeForWindow(step, window);
                if (recordingType) {
                            RecordingModule.startRecording(recordingType);
                        }
                        break;
                }
            });
        });
    },

    handleSubmit: async function(e) {
        e.preventDefault(); // Prevent form submission
        
        console.log('[TRACE] Submit button clicked');
        console.log('[DEBUG] Current step:', state.currentStep);
        console.log('[DEBUG] Submit button state:', {
                visible: e.target.offsetParent !== null,
                enabled: !e.target.disabled,
                text: e.target.textContent
        });

        // Prevent submission if recording is in progress
        if (RecordingModule.isRecording) {
            console.warn('[WARN] Cannot submit while recording is in progress');
            UIModule.showMessage('Please finish or stop your recording before submitting.', true);
            return;
        }

        // Only allow submission at the correct step/window using SUBMISSION_STEP_WINDOW
        const { step, window } = UIModule.getCurrentWindow();
        if (!(step === SUBMISSION_STEP_WINDOW[0] && window === SUBMISSION_STEP_WINDOW[1])) {
            console.warn('[WARN] Cannot submit from step:', step, window);
            UIModule.showMessage('Please complete all steps before submitting.', true);
            return;
        }

        // Prevent multiple submissions
        if (isSubmitting) {
            console.warn('[WARN] Submission already in progress, ignoring click');
            return;
        }

        try {
            isSubmitting = true;
            e.target.disabled = true;
            // Show the submission overlay
            UIModule.Overlay.showSubmissionOverlay();
            // Call submitGrievance
            await GrievanceModule.submitGrievance();
        } catch (error) {
            console.error('[ERROR] Submission failed:', error);
            // Re-enable the button if submission fails
            e.target.disabled = false;
            isSubmitting = false;
            UIModule.Overlay.hideSubmissionOverlay();
        }
    },

    setupRecordButtons: function() {
        // Handle record buttons
        document.querySelectorAll('.record-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                if (RecordingModule.isRecording) {
                    RecordingModule.stopRecording();
                } else {
                    const { step, window } = UIModule.getCurrentWindow();
                    const recordingType = getRecordingTypeForWindow(step, window);
                    if (recordingType) {
                        RecordingModule.startRecording(recordingType);
                    }
                }
            });
        });
    },

    setupFileUploadButtons: function() {
        // Handle file upload buttons
        const attachFilesBtn = document.getElementById('attachFilesBtn');
        if (attachFilesBtn) {
            attachFilesBtn.addEventListener('click', () => {
                const fileInput = document.getElementById('fileInput');
                if (fileInput) fileInput.click();
            });
        }

        const submitFilesBtn = document.getElementById('submitFilesBtn');
        if (submitFilesBtn) {
            submitFilesBtn.addEventListener('click', () => {
                FileUploadModule.submitSelectedFiles();
            });
        }

        const attachMoreBtn = document.getElementById('attachMoreBtn');
        if (attachMoreBtn) {
            attachMoreBtn.addEventListener('click', () => {
                FileUploadModule.clearFiles();
                const fileInput = document.getElementById('fileInput');
                if (fileInput) fileInput.click();
            });
        }
    },

    setupAccessibilityButtons: function() {
        // Handle accessibility buttons
        const contrastBtn = document.getElementById('contrastToggleBtn');
        if (contrastBtn) {
            contrastBtn.addEventListener('click', () => {
                AccessibilityModule.toggleContrast();
            });
        }

        const fontSizeBtn = document.getElementById('fontSizeBtn');
        if (fontSizeBtn) {
            fontSizeBtn.addEventListener('click', () => {
                AccessibilityModule.increaseFontSize();
            });
        }

        const readPageBtn = document.getElementById('readPageBtn');
        if (readPageBtn) {
            readPageBtn.addEventListener('click', () => {
                SpeechModule.toggleAutoRead();
            });
        }

        const speedBtn = document.getElementById('speedBtn');
        if (speedBtn) {
            speedBtn.addEventListener('click', () => {
                SpeechModule.toggleSpeedDropdown();
            });
        }
    },

    setupDialogButtons: function() {
        // Handle help dialog
        const helpBtn = document.getElementById('helpBtn');
        if (helpBtn) {
            helpBtn.addEventListener('click', () => {
                const helpDialog = document.getElementById('helpDialog');
                if (helpDialog) {
                    helpDialog.showModal();
                    const closeBtn = helpDialog.querySelector('button');
                    if (closeBtn) {
                        closeBtn.addEventListener('click', () => {
                            helpDialog.close();
                        });
                    }
                }
            });
        }

        // Handle screen reader dialog
        const enableScreenReaderBtn = document.getElementById('enableScreenReaderBtn');
        const disableScreenReaderBtn = document.getElementById('disableScreenReaderBtn');
        if (enableScreenReaderBtn && disableScreenReaderBtn) {
            enableScreenReaderBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                speechReady = true;
                SpeechModule.autoRead = true;
                localStorage.setItem('autoRead', 'true');
                document.getElementById('screenReaderDialog').close();
            });

            disableScreenReaderBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                speechReady = false;
                SpeechModule.autoRead = false;
                localStorage.setItem('autoRead', 'false');
                document.getElementById('screenReaderDialog').close();
            });
        }
    },

    setupActionButtons: function() {
        // Handle new button
        const newBtn = document.getElementById('newBtn');
        if (newBtn) {
            newBtn.addEventListener('click', () => {
                UIModule.resetApp();
            });
        }

        // Handle exit button
        const exitBtn = document.getElementById('exitBtn');
        if (exitBtn) {
            exitBtn.addEventListener('click', () => {
                if (confirm('Are you sure you want to exit? Any unsaved changes will be lost.')) {
                    window.close();
                }
            });
        }

        // Handle confirm review button
        const confirmReviewBtn = document.getElementById('confirmReviewBtn');
        if (confirmReviewBtn) {
            confirmReviewBtn.addEventListener('click', async () => {
                const grievanceId = document.getElementById('grievanceId').querySelector('span').textContent;
                if (grievanceId && window._reviewData) {
                    const result = await updateReviewData(grievanceId, window._reviewData);
                    if (result && result.message) {
                        alert('Changes saved successfully!');
                    } else {
                        alert('Failed to save changes.');
                    }
                }
            });
        }
    }
};

// Cancel button logic
window.addEventListener('DOMContentLoaded', function() {
  const cancelBtn = document.getElementById('cancelSubmissionBtn');
  if (cancelBtn) {
    cancelBtn.addEventListener('click', function() {
      if (submissionAbortController) submissionAbortController.abort();
      UIModule.Overlay.hideSubmissionOverlay();
      const submitBtn = document.getElementById('submitGrievanceBtn');
      if (submitBtn) submitBtn.disabled = false;
      alert('Submission cancelled. Please try again.');
    });
    }
});

// Add these functions to manage the speech indicator
function disableSpeechIndicator() {
    isSpeechIndicatorEnabled = false;
    const indicator = document.getElementById('speechIndicator');
    if (indicator) {
        indicator.remove();
    }
}

function enableSpeechIndicator() {
    isSpeechIndicatorEnabled = true;
}



// --- Review Step Data Fetch/Update Logic ---
async function fetchReviewData(grievanceId) {
    try {
        const response = await fetch(`/grievance-review/${grievanceId}`);
        if (!response.ok) throw new Error('Failed to fetch review data');
        return await response.json();
    } catch (e) {
        console.error('Error fetching review data:', e);
        return null;
    }
}

async function updateReviewData(grievanceId, data) {
    try {
        const response = await fetch(`/grievance-review/${grievanceId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return await response.json();
    } catch (e) {
        console.error('Error updating review data:', e);
        return null;
    }
}

// Populate review UI fields
function populateReviewUI(data) {
    if (!data) return;
    // Step 1
    document.getElementById('grievanceDetailsReview').textContent = data.grievance_details || '';
    document.getElementById('grievanceSummaryReview').textContent = data.grievance_summary || '';
    // Categories as list with delete buttons
    const catContainer = document.getElementById('grievanceCategoriesReview');
    catContainer.innerHTML = '';
    (data.grievance_categories || []).forEach((cat, idx) => {
        const div = document.createElement('div');
        div.className = 'category-item';
        div.textContent = cat;
        const delBtn = document.createElement('button');
        delBtn.textContent = 'Delete';
        delBtn.className = 'delete-category-btn';
        delBtn.onclick = () => {
            data.grievance_categories.splice(idx, 1);
            populateReviewUI(data);
        };
        div.appendChild(delBtn);
        catContainer.appendChild(div);
    });
    // Add button for new category
    const addBtn = document.createElement('button');
    addBtn.textContent = 'Add Category';
    addBtn.className = 'add-category-btn';
    addBtn.onclick = () => {
        // Show dropdown (implement as needed)
        // For now, just prompt
        const newCat = prompt('Enter new category:');
        if (newCat) {
            data.grievance_categories.push(newCat);
            populateReviewUI(data);
        }
    };
    catContainer.appendChild(addBtn);
    // Step 2
    document.getElementById('userNameReview').textContent = data.user_full_name || '';
    document.getElementById('userPhoneReview').textContent = data.user_contact_phone || '';
    // Step 3
    document.getElementById('userMunicipalityReview').textContent = data.user_municipality || '';
    document.getElementById('userVillageReview').textContent = data.user_village || '';
    document.getElementById('userAddressReview').textContent = data.user_address || '';
}

// On entering confirmation/review, fetch and populate
function setupReviewStepData() {
    const confirmation = document.getElementById('confirmation');
    if (!confirmation) return;
    const observer = new MutationObserver(() => {
        if (!confirmation.hidden) {
            const grievanceId = document.getElementById('grievanceId').querySelector('span').textContent;
            if (grievanceId) {
                fetchReviewData(grievanceId).then(data => {
                    window._reviewData = data; // store for later update
                    populateReviewUI(data);
                });
            }
        }
    });
    observer.observe(confirmation, { attributes: true, attributeFilter: ['hidden'] });
}
setupReviewStepData();

// On confirmation, send all updates
function setupReviewConfirmation() {
    const confirmation = document.getElementById('confirmation');
    if (!confirmation) return;
    // Add a confirm button if not present
    let confirmBtn = document.getElementById('confirmReviewBtn');
    if (!confirmBtn) {
        confirmBtn = document.createElement('button');
        confirmBtn.id = 'confirmReviewBtn';
        confirmBtn.textContent = 'Confirm and Save Changes';
        confirmBtn.className = 'primary-btn';
        confirmation.querySelector('.content').appendChild(confirmBtn);
    }
    confirmBtn.onclick = async () => {
        const grievanceId = document.getElementById('grievanceId').querySelector('span').textContent;
        if (grievanceId && window._reviewData) {
            const result = await updateReviewData(grievanceId, window._reviewData);
            if (result && result.message) {
                alert('Changes saved successfully!');
            } else {
                alert('Failed to save changes.');
            }
        }
    };
}
setupReviewConfirmation();

window.addEventListener('DOMContentLoaded', function() {
    // Initialize all modules
    SpeechModule.init();
    AccessibilityModule.init();
    UIModule.init();
    APIModule.init();
    FileUploadModule.init();
    RecordingModule.init();
    GrievanceModule.init();
    ModifyModule.init();
    EventModule.init(); // <-- THIS IS CRUCIAL
});
