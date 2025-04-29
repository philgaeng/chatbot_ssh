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

// Add this near the top of the file where other state variables are defined
let isSpeechIndicatorEnabled = true;

function setupOverlayObserver() {
    const overlay = document.getElementById('submissionOverlay');
    if (!overlay) {
        console.error('[ERROR] Could not set up overlay observer: overlay not found');
        return;
    }

    // Create an observer instance
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

    // Start observing the overlay for attribute changes
    overlayMutationObserver.observe(overlay, {
        attributes: true,
        attributeFilter: ['hidden']
    });
}

// Utility to show/hide overlay
function showSubmissionOverlay() {
    console.log('[TRACE] showSubmissionOverlay called');
    const overlay = document.getElementById('submissionOverlay');
    if (!overlay) {
        console.error('[ERROR] Submission overlay element not found');
        return;
    }
    
    // Reset overlay content
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
    
    // Show overlay
    overlay.hidden = false;
    
    // Disable the submit button
    const submitBtn = document.getElementById('submitGrievanceBtn');
    if (submitBtn) {
        submitBtn.disabled = true;
    }
}

// Add a function to check for duplicate overlays
function checkForDuplicateOverlays() {
    const overlays = document.querySelectorAll('#submissionOverlay');
    if (overlays.length > 1) {
        console.error('[ERROR] Multiple submission overlays found:', overlays.length);
        overlays.forEach((overlay, index) => {
            console.error(`[ERROR] Overlay ${index + 1}:`, overlay);
        });
    }
}

// Call the check when the page loads
document.addEventListener('DOMContentLoaded', checkForDuplicateOverlays);

function hideSubmissionOverlay() {
    console.log('[TRACE] hideSubmissionOverlay called');
    const overlay = document.getElementById('submissionOverlay');
    if (overlay) {
        overlay.hidden = true;
        if (cancelBtnTimeout) clearTimeout(cancelBtnTimeout);
        // Re-enable the submit button
        const submitBtn = document.getElementById('submitGrievanceBtn');
        if (submitBtn) {
            submitBtn.disabled = false;
        }
    }
}

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
    steps: ['1', '2a', '2b', '3a', '3b', '3c', 'confirmation'],
    currentStepIndex: 0,
    
    init: function() {
        this.setupHelpDialog();
        this.setupNavigation();
        this.showCurrentStep();
    },
    
    setupHelpDialog: function() {
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
    },
    
    setupNavigation: function() {
        // Single setup for all navigation buttons
        document.addEventListener('click', (e) => {
            const button = e.target.closest('.nav-btn');
            if (!button) return;
            
            const action = button.getAttribute('data-action');
            if (!action) return;
            
            // Prevent actions during recording
            if (RecordingModule.isRecording) return;
            
            switch(action) {
                case 'next':
                case 'continue':
                    this.goToNextStep();
                    break;
                case 'prev':
                    this.goToPreviousStep();
                    break;
                case 'retry':
                    // Handled by RecordingModule
                    break;
                case 'submit':
                    if (!isSubmitting) {
                        GrievanceModule.submitGrievance();
                    }
                    break;
            }
        });

        // Setup other navigation-related buttons
        const newBtn = document.getElementById('newBtn');
        if (newBtn) {
            newBtn.addEventListener('click', () => this.resetApp());
        }

        const exitBtn = document.getElementById('exitBtn');
        if (exitBtn) {
            exitBtn.addEventListener('click', () => this.showExitConfirmation());
        }
    },
    
    showCurrentStep: function() {
        // Hide all steps
        this.hideAllSteps();
        
        // Show current step
        const step = this.steps[this.currentStepIndex];
        state.currentStep = step;
        const stepElement = document.getElementById(`step${step}`);
        
        if (stepElement) {
            stepElement.hidden = false;
            
            // Get step content for screen reader
            const content = stepElement.querySelector('.content');
            if (content && SpeechModule.autoRead) {
                SpeechModule.speak(content.textContent);
            }
            
            // Update button states for the new step
            const recordingType = RecordingModule.getRecordingTypeForStep(step);
            this.updateButtonStates({
                isRecording: RecordingModule.isRecording,
                hasRecording: RecordingModule.hasRecording(recordingType),
                isSubmitting: isSubmitting
            });
        }
    },
    
    hideAllSteps: function() {
        this.steps.forEach(step => {
            const element = document.getElementById(`step${step}`);
            if (element) {
                element.hidden = true;
            }
        });
    },
    
    goToNextStep: function(skip = false) {
        console.log('Going to next step from:', state.currentStep);
        
        let nextStep;
        
        // Special handling for step 3c - never proceed beyond it
        if (state.currentStep === '3c') {
            console.log('On step 3c - no next step available');
            return;
        }
        
        // Determine next step
        if (state.currentStep === '3b') {
            nextStep = '3c';
        } else if (state.currentStep === '1') {
            nextStep = '2a';
        } else if (state.currentStep === '2a') {
            nextStep = '2b';
        } else if (state.currentStep === '2b') {
            nextStep = '3a';
        } else if (state.currentStep === '3a') {
            nextStep = '3b';
        } else {
            console.error('Unable to determine next step from:', state.currentStep);
            return;
        }
        
        console.log('Next step determined as:', nextStep);
        
        // Check for recording if not skipping
        if (!skip) {
            const hasRecordings = RecordingModule.hasRecording(RecordingModule.getRecordingTypeForStep(state.currentStep));
            if (!hasRecordings) {
                console.warn(`No recording found for step ${state.currentStep}, not proceeding`);
                this.showError('Please record your response before continuing, or use Skip.');
                return;
            }
        }
        
        // Update state and show next step
        const previousStep = state.currentStep;
        state.currentStep = nextStep;
        UIModule.currentStepIndex = UIModule.steps.indexOf(nextStep);
        
        // Hide previous step before showing next
        const prevStepElement = document.getElementById(`step${previousStep}`);
        if (prevStepElement) {
            prevStepElement.hidden = true;
        }
        
        // Show next step
        const nextStepElement = document.getElementById(`step${nextStep}`);
        if (nextStepElement) {
            nextStepElement.hidden = false;
            
            // Get step content for screen reader
            const content = nextStepElement.querySelector('.content');
            if (content && SpeechModule.autoRead) {
                SpeechModule.speak(content.textContent);
            }
        }
        
        // Update button states for the new step
        const recordingType = RecordingModule.getRecordingTypeForStep(nextStep);
        this.updateButtonStates({
            isRecording: RecordingModule.isRecording,
            hasRecording: RecordingModule.hasRecording(recordingType),
            isSubmitting: isSubmitting
        });
    },
    
    goToPreviousStep: function() {
        if (this.currentStepIndex > 0) {
            this.currentStepIndex--;
            this.showCurrentStep();
        }
    },
    
    goToStep: function(stepIndex) {
        if (stepIndex >= 0 && stepIndex < this.steps.length) {
            this.currentStepIndex = stepIndex;
            this.showCurrentStep();
        }
        
        // Auto-read step content if enabled
        if (SpeechModule.autoRead) {
            setTimeout(() => {
                const currentStep = document.querySelector('.step:not([hidden])');
                if (currentStep) {
                    SpeechModule.speak(currentStep.textContent);
                }
            }, 300);
        }
    },
    
    navigateToStep: function(stepName) {
        const stepIndex = this.steps.indexOf(stepName);
        if (stepIndex !== -1) {
            this.goToStep(stepIndex);
        } else {
            console.error(`Step ${stepName} not found`);
        }
    },
    
    resetApp: function() {
        console.log("Resetting application state");
        
        // Reset to initial state
        this.currentStepIndex = 0;
        state.currentStep = this.steps[0];
        state.grievanceId = null;
        
        // Hide confirmation step
        const confirmationStep = document.getElementById('confirmation');
        if (confirmationStep) {
            confirmationStep.hidden = true;
        }
        
        // Reset the form
        const form = document.getElementById('grievanceForm');
        if (form) {
            form.reset();
        }
        
        // Clear recordings
        RecordingModule.clearRecordings();
        
        // Clear files
        FileUploadModule.clearFiles();
        
        // Reset UI elements related to file uploads
        const fileList = document.getElementById('fileList');
        if (fileList) {
            fileList.hidden = true;
            const ul = fileList.querySelector('ul');
            if (ul) ul.innerHTML = '';
        }
        
        const uploadedFilesSection = document.getElementById('uploadedFilesSection');
        if (uploadedFilesSection) {
            uploadedFilesSection.hidden = true;
        }
        
        const uploadedFilesList = document.getElementById('uploadedFilesList');
        if (uploadedFilesList) {
            const ul = uploadedFilesList.querySelector('ul');
            if (ul) ul.innerHTML = '';
        }
        
        // Show first step
        UIModule.showCurrentStep();
    },
    
    showError: function(message) {
        // Log the message but don't show overlay notifications
        console.log('Error:', message);
        
        // Instead of showing a notification, update a status element on the page
        // This is safer than modal popups
        const statusElement = document.getElementById('statusMessage');
        if (statusElement) {
            statusElement.textContent = message;
            statusElement.className = 'status-error';
            statusElement.hidden = false;
            
            // Auto-hide after a few seconds
            setTimeout(() => {
                statusElement.hidden = true;
            }, 3000);
        }
    },
    
    showSuccess: function(message, grievanceId) {
        const confirmationElement = document.getElementById('confirmation');
        const messageElement = document.getElementById('resultMessage');
        const idElement = document.getElementById('grievanceId').querySelector('span');
        
        if (confirmationElement && messageElement && idElement) {
            messageElement.textContent = message;
            idElement.textContent = grievanceId;
            confirmationElement.hidden = false;
            
            SpeechModule.speak(message + ". Your grievance ID is " + 
                grievanceId.split('').join(' '));
        }
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
    
    showConfirmationScreen: function(grievanceId) {
        console.log("Showing confirmation screen for grievance ID:", grievanceId);
        
        // First hide the submission overlay
        hideSubmissionOverlay();
        
        // Then completely hide ALL steps including step3c
        document.querySelectorAll('.step').forEach(step => {
            step.hidden = true;
            step.style.display = 'none';
        });
        
        // Get the confirmation screen element
        const confirmationElement = document.getElementById('confirmation');
        
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
            resultMessage.textContent = "Your voice grievance has been submitted successfully. You can now attach photos or documents.";
        }
        
        // Ensure attachment instructions are visible
        const attachmentInstructions = document.getElementById('attachmentInstructions');
        if (attachmentInstructions) {
            attachmentInstructions.hidden = false;
        }
        
        // Make the confirmation screen visible
        confirmationElement.hidden = false;
        confirmationElement.style.display = 'block';
        
        // Force a repaint to ensure visibility
        confirmationElement.offsetHeight;
        
        // Update the current step state
        this.currentStepIndex = this.steps.indexOf('confirmation');
        state.currentStep = 'confirmation';
        
        // Scroll to the top to ensure visibility
        window.scrollTo(0, 0);
        
        console.log("Confirmation screen should now be the only visible step");
    },
    
    showExitConfirmation: function() {
        console.log("User chose to exit");
        window.location.href = '/';
    },
    
    closeExitDialog: function() {
        console.log("Exit dialog would be closed");
    },
    
    executeExit: function() {
        // First try using window.close()
        window.close();
        
        // As a fallback if window.close() doesn't work
        // (which can happen due to browser security restrictions)
        setTimeout(() => {
            const message = document.createElement('div');
            message.setAttribute('role', 'alert');
            message.style.position = 'fixed';
            message.style.top = '0';
            message.style.left = '0';
            message.style.width = '100%';
            message.style.height = '100%';
            message.style.backgroundColor = '#fff';
            message.style.display = 'flex';
            message.style.flexDirection = 'column';
            message.style.justifyContent = 'center';
            message.style.alignItems = 'center';
            message.style.zIndex = '9999';
            message.innerHTML = `
                <h1>Thank You for Your Submission</h1>
                <p>Your grievance ID is: <strong>${state.grievanceId || 'N/A'}</strong></p>
                <p>It is now safe to close this window.</p>
                <button id="close-tab-btn" style="margin-top:20px; padding:10px 20px; background-color:#4CAF50; color:white; border:none; border-radius:4px; cursor:pointer;">
                    Close Tab
                </button>
            `;
            document.body.innerHTML = '';
            document.body.appendChild(message);
            
            // Add event listener to the close tab button
            const closeTabBtn = document.getElementById('close-tab-btn');
            if (closeTabBtn) {
                closeTabBtn.addEventListener('click', () => {
                    window.close();
                });
                
                // Focus on the button for keyboard users
                closeTabBtn.focus();
            }
            
            // Announce completion for screen readers
            SpeechModule.speak("Thank you for your submission. Your grievance ID is " + 
                (state.grievanceId ? state.grievanceId.split('').join(' ') : 'not available') + 
                ". It is now safe to close this window.");
        }, 300);
    },
    
    showLoadingOverlay: function(message) {
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
    
    hideLoadingOverlay: function() {
        // Hide the status element
        const statusElement = document.getElementById('statusMessage');
        if (statusElement) {
            statusElement.hidden = true;
        }
    },
    
    updateButtonStates: function(options = {}) {
        const {
            isRecording = false,
            currentStep = state.currentStep,
            hasRecording = false,
            isSubmitting = false
        } = options;
        
        // Get current step info
        const currentStepElement = document.querySelector('.step:not([hidden])');
        if (!currentStepElement) return;
        
        const stepId = currentStepElement.id;
        const currentStepNumber = stepId.replace('step', '');
        const recordingType = RecordingModule.getRecordingTypeForStep(currentStepNumber);
        
        // Update record buttons
        const recordButtons = document.querySelectorAll('[id^="recordBtn"]');
        recordButtons.forEach(button => {
            // Disable record buttons during submission
            if (isSubmitting) {
                button.disabled = true;
                return;
            }
            
            if (isRecording) {
                button.textContent = 'Stop Recording';
                button.classList.add('recording');
                button.classList.remove('waiting');
                button.disabled = false;
            } else {
                button.textContent = 'Record';
                button.classList.remove('recording', 'waiting');
                button.disabled = false;
            }
        });
        
        // Update navigation buttons
        const navButtons = currentStepElement.querySelectorAll('.nav-btn');
        navButtons.forEach(button => {
            const action = button.getAttribute('data-action');
            
            // During recording or submission, all navigation is disabled
            if (isRecording || isSubmitting) {
                button.disabled = true;
                return;
            }
            
            switch (action) {
                case 'prev':
                    button.disabled = (currentStepNumber === '1');
                    button.style.display = '';
                    break;
                    
                case 'next':
                case 'continue':
                    if (currentStepNumber === '3c') {
                        button.style.display = 'none';
                    } else {
                        button.disabled = !hasRecording;
                        button.style.display = '';
                    }
                    break;
                    
                case 'retry':
                    button.disabled = isRecording;
                    button.style.display = '';
                    break;
                    
                case 'submit':
                    if (currentStepNumber === '3c') {
                        button.style.display = '';
                        // Only enable submit if we have all required recordings
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
            
            // Add visual indication of disabled state
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
    }
};

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
};

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
            UIModule.showError(`File ${file.name} is too large. Maximum size is ${this.maxFileSize / (1024 * 1024)}MB.`);
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
                UIModule.showError(`File ${file.name} is not allowed. Allowed types: ${this.allowedFileTypes.join(', ')}`);
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
            UIModule.showError('No grievance ID found. Cannot upload files.');
            return;
        }
        
        if (this.selectedFiles.length === 0) {
            UIModule.showError('No files selected for upload.');
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
                UIModule.showError('Some files failed to upload. Please try again.');
                SpeechModule.speak('Some files failed to upload. Please try again.');
            }
        } catch (error) {
            console.error('Error uploading files:', error);
            UIModule.showError('Error uploading files. Please try again.');
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
        this.setupRecordingControls();
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
        // Use event delegation for recording buttons
        document.addEventListener('click', (e) => {
            const button = e.target.closest('[id^="recordBtn"]');
            if (!button) return;
            
            const recordingType = this.getRecordingTypeFromId(button.id);
            if (this.isRecording) {
                this.stopRecording();
            } else {
                this.startRecording(recordingType);
            }
        });
        
        // Use event delegation for retry buttons
        document.addEventListener('click', (e) => {
            const button = e.target.closest('.retry-btn');
            if (!button) return;
            
            const stepElement = button.closest('.step');
            if (stepElement) {
                const stepId = stepElement.id;
                const recordingType = this.getRecordingTypeFromStepId(stepId);
                this.startRecording(recordingType);
            }
        });
    },
    
    getRecordingTypeFromId: function(buttonId) {
        // Map button IDs to recording types
        const typeMap = {
            'recordBtn1': 'grievance_details',
            'recordBtn2a': 'user_full_name',
            'recordBtn2b': 'user_contact_phone',
            'recordBtn3a': 'user_municipality',
            'recordBtn3b': 'user_village',
            'recordBtn3c': 'user_address'
        };
        
        return typeMap[buttonId] || 'unknown';
    },
    
    getRecordingTypeFromStepId: function(stepId) {
        // Map step IDs to recording types
        const typeMap = {
            'step1': 'grievance_details',
            'step2a': 'user_full_name',
            'step2b': 'user_contact_phone',
            'step3a': 'user_municipality',
            'step3b': 'user_village',
            'step3c': 'user_address'
        };
        
        return typeMap[stepId] || 'unknown';
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
        
        // Special handling for step3c visibility
        if (recordingType === 'user_address') {
            const step3c = document.getElementById('step3c');
            if (step3c && step3c.hidden) {
                console.log("Making step3c visible for recording");
                
                // Hide all other steps
                document.querySelectorAll('.step').forEach(step => {
                    if (step.id !== 'step3c') {
                        step.hidden = true;
                    }
                });
                
                // Show step3c
                step3c.hidden = false;
                step3c.style.display = 'block';
                
                // Update state
                state.currentStep = '3c';
                UIModule.currentStepIndex = UIModule.steps.indexOf('3c');
            }
        }
        
        // Find the record button for this type
        const stepId = this.getStepIdFromRecordingType(recordingType);
        const recordBtn = document.getElementById(`recordBtn${stepId}`);
        const statusEl = document.getElementById(`status${stepId}`);
        const playbackContainer = document.getElementById(`playback${stepId}`);
        
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
        // Find the correct status element based on recording type
        let stepId = this.getStepIdFromRecordingType(recordingType);
        const statusElement = document.getElementById(`status${stepId}`);
        
        if (!statusElement) {
            console.warn(`Status element not found for recording type: ${recordingType}`);
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
    
    getStepIdFromRecordingType: function(recordingType) {
        // Map recording types back to step IDs
        const stepMap = {
            'grievance_details': '1',
            'user_full_name': '2a',
            'user_contact_phone': '2b',
            'user_municipality': '3a',
            'user_village': '3b',
            'user_address': '3c'
        };
        
        return stepMap[recordingType] || '1';
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
        const stepId = this.getStepIdFromRecordingType(this.recordingType);
        const statusElement = document.getElementById(`status${stepId}`);
        if (statusElement) {
            const timerElement = statusElement.querySelector('.recording-timer');
            if (timerElement) {
                finalTime = timerElement.textContent;
                console.log(`Final recording time: ${finalTime}`);
            }
            statusElement.innerHTML = `
                <div class="recording-complete">
                    <div class="recording-complete-icon">✓</div>
                    <div class="recording-complete-label">Recorded:</div>
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
        const playbackContainer = document.getElementById(`playback${stepId}`);
        if (playbackContainer) {
            playbackContainer.hidden = false;
        }
        
        // Update UI after recording stops
        this.updateRecordingUI(false);
        
        console.log(`Stopped recording for step ${stepId}, waiting for user action.`);
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
        const stepId = this.getStepIdFromRecordingType(recordingType);
        const previewContainerId = `playback${stepId}`;
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
     * Returns the recording type key for a given step name (e.g., '1', '2a', ...)
     */
    getRecordingTypeForStep: function(step) {
        const map = {
            '1': 'grievance_details',
            '2a': 'user_full_name',
            '2b': 'user_contact_phone',
            '3a': 'user_municipality',
            '3b': 'user_village',
            '3c': 'user_address'
        };
        return map[step] || null;
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
    steps: ['1', '2a', '2b', '3a', '3b', '3c', 'confirmation'],
    
    init: function() {
        console.log("Initializing Grievance Module");
        this.loadCategories();
        this.setupStepNavigation();
        this.setupSubmitHandler();
        
        // Add direct handler for step3b continue button
        this.setupDirectStepHandlers();
        
        console.log("Grievance Module initialized with steps:", this.steps);
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
    
    setupStepNavigation: function() {
        // Remove duplicate event listeners for .next-btn and .prev-step
        // Navigation is now handled by UIModule.setupNavigation
    },
    
    setupSubmitHandler: function() {
        // Remove form submission handler since we handle submission through button clicks
        console.log('Form submission now handled through button click handlers only');
    },
    
    validateCurrentStep: function() {
        const currentStep = state.currentStep;
        console.log('Validating step:', currentStep);
        
        // Map step IDs to recording types
        const stepToRecordingType = {
            '1': 'grievance_details',
            '2a': 'user_full_name',
            '2b': 'user_contact_phone',
            '3a': 'user_municipality',
            '3b': 'user_village',
            '3c': 'user_address'
        };
        
        // Get the recording type for the current step
        const recordingType = stepToRecordingType[currentStep];
        
        // Check if recording exists for the current step
        if (recordingType && !RecordingModule.hasRecording(recordingType)) {
            console.warn(`Missing ${recordingType} recording, but proceeding anyway`);
            return true; // Allow to proceed anyway
        }
        
        return true; // Always return true to allow proceeding
    },
    
    populateReviewScreen: function() {
        const reviewContainer = document.getElementById('reviewDetails');
        if (!reviewContainer) return;
        
        // Get form data
        const formData = new FormData(document.getElementById('grievanceForm'));
        
        // Clear existing content
        reviewContainer.innerHTML = '';
        
        // Create review items
        for (const [key, value] of formData.entries()) {
            // Skip files and empty values
            if (value instanceof File || !value.trim()) continue;
            
            const item = document.createElement('div');
            item.classList.add('review-item');
            
            const label = document.createElement('strong');
            label.textContent = this.getFieldLabel(key) + ': ';
            
            const valueSpan = document.createElement('span');
            valueSpan.textContent = value;
            
            item.appendChild(label);
            item.appendChild(valueSpan);
            reviewContainer.appendChild(item);
        }
        
        // Add recordings info
        if (recordedBlobs && Object.keys(recordedBlobs).length > 0) {
            const recordingsTitle = document.createElement('h3');
            recordingsTitle.textContent = 'Voice Recordings';
            reviewContainer.appendChild(recordingsTitle);
            
            const recordingsList = document.createElement('ul');
            
            for (const type in recordedBlobs) {
                const item = document.createElement('li');
                item.textContent = `${this.getRecordingLabel(type)} recording`;
                recordingsList.appendChild(item);
            }
            
            reviewContainer.appendChild(recordingsList);
        }
        
        // Add files info
        if (FileUploadModule.selectedFiles.length > 0) {
            const filesTitle = document.createElement('h3');
            filesTitle.textContent = 'Attached Files';
            reviewContainer.appendChild(filesTitle);
            
            const filesList = document.createElement('ul');
            
            FileUploadModule.selectedFiles.forEach(file => {
                const item = document.createElement('li');
                item.textContent = file.name;
                filesList.appendChild(item);
            });
            
            reviewContainer.appendChild(filesList);
        }
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
    
    goToNextStep: function(skip = false) {
        console.log('Going to next step from:', state.currentStep);
        
        let nextStep;
        
        // Special handling for step 3c - never proceed beyond it
        if (state.currentStep === '3c') {
            console.log('On step 3c - no next step available');
            return;
        }
        
        // Determine next step
        if (state.currentStep === '3b') {
            nextStep = '3c';
        } else if (state.currentStep === '1') {
            nextStep = '2a';
        } else if (state.currentStep === '2a') {
            nextStep = '2b';
        } else if (state.currentStep === '2b') {
            nextStep = '3a';
        } else if (state.currentStep === '3a') {
            nextStep = '3b';
        } else {
            console.error('Unable to determine next step from:', state.currentStep);
            return;
        }
        
        console.log('Next step determined as:', nextStep);
        
        // Check for recording if not skipping
        if (!skip) {
            const hasRecordings = RecordingModule.hasRecording(RecordingModule.getRecordingTypeForStep(state.currentStep));
            if (!hasRecordings) {
                console.warn(`No recording found for step ${state.currentStep}, not proceeding`);
                this.showError('Please record your response before continuing, or use Skip.');
                return;
            }
        }
        
        // Update state and show next step
        const previousStep = state.currentStep;
        state.currentStep = nextStep;
        UIModule.currentStepIndex = UIModule.steps.indexOf(nextStep);
        
        // Hide previous step before showing next
        const prevStepElement = document.getElementById(`step${previousStep}`);
        if (prevStepElement) {
            prevStepElement.hidden = true;
        }
        
        // Show next step
        const nextStepElement = document.getElementById(`step${nextStep}`);
        if (nextStepElement) {
            nextStepElement.hidden = false;
            
            // Get step content for screen reader
            const content = nextStepElement.querySelector('.content');
            if (content && SpeechModule.autoRead) {
                SpeechModule.speak(content.textContent);
            }
        }
        
        // Update button states for the new step
        const recordingType = RecordingModule.getRecordingTypeForStep(nextStep);
        this.updateButtonStates({
            isRecording: RecordingModule.isRecording,
            hasRecording: RecordingModule.hasRecording(recordingType),
            isSubmitting: isSubmitting
        });
    },
    
    goToPreviousStep: function() {
        const currentIndex = this.steps.indexOf(state.currentStep);
        if (currentIndex > 0) {
            const prevStep = this.steps[currentIndex - 1];
            UIModule.navigateToStep(prevStep);
        }
    },
    
    submitGrievance: async function() {
        try {
            // Prevent submission if recording is in progress or we're still navigating
            if (RecordingModule.isRecording || this.isNavigatingTo3c || this.isTransitioning) {
                console.log("Cannot submit: recording in progress or navigation not complete");
                UIModule.showError('Please wait for navigation to complete before submitting.');
                return;
            }

            // Check if we're on the final step
            if (state.currentStep !== '3c') {
                console.log("Cannot submit from step:", state.currentStep);
                UIModule.showError('Please complete all steps before submitting.');
                return;
            }

            console.log("Starting grievance submission process");
            showSubmissionOverlay();
            
            // Create form data from the form
            const form = document.getElementById('grievanceForm');
            if (!form) {
                throw new Error("Grievance form not found!");
            }
            
            const formData = new FormData(form);
            
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
            hideSubmissionOverlay();
            
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
                });
                
        } catch (error) {
            console.error('Error submitting grievance:', error);
            UIModule.showError('There was an error submitting your grievance. Please try again.');
            SpeechModule.speak('There was an error submitting your grievance. Please try again.');
            hideSubmissionOverlay();
        }
    },
    
    setupDirectStepHandlers: function() {
        // Remove redundant handler for step3b's continue button
        // Navigation is now handled by UIModule.goToNextStep
    },
    
    showMessage: function(message, isError = false) {
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
    }
};

// Initialize the app on window load
window.addEventListener('load', function() {
    // Avoid double initialization
    if (appInitialized) return;
    
    try {
        // Initialize all modules
        SpeechModule.init();
        AccessibilityModule.init();
        UIModule.init();
        APIModule.init();
        FileUploadModule.init();
        RecordingModule.init();
        GrievanceModule.init();
        
        // Mark as initialized
        appInitialized = true;
        console.log('App initialized');
        // After showing the first step, read it if autoRead is true
        setTimeout(() => {
            if (SpeechModule.autoRead) {
                const firstStep = document.querySelector('.step:not([hidden]) .content');
                if (firstStep) {
                    SpeechModule.speak(firstStep.textContent);
                }
            }
        }, 300);
    } catch (error) {
        console.error("Error initializing app:", error);
    }
});

// For backward compatibility with existing code
window.nepalChatbot = window.nepalChatbot || {};
// ... existing code ... 

// --- Screen Reader Enable Dialog Logic ---
let speechReady = false;
window.addEventListener('DOMContentLoaded', function() {
    const dialog = document.getElementById('screenReaderDialog');
    if (dialog && typeof dialog.showModal === 'function') {
        dialog.showModal();
        // Trap focus in dialog for accessibility
        dialog.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                e.preventDefault();
            }
        });
        document.getElementById('enableScreenReaderBtn').addEventListener('click', function(event) {
            // Only set speech state and close dialog
            event.preventDefault();
            event.stopPropagation();
            speechReady = true;
            SpeechModule.autoRead = true;
            localStorage.setItem('autoRead', 'true');
            dialog.close();
            // Immediately read the current step
            setTimeout(() => {
                const firstStep = document.querySelector('.step:not([hidden]) .content');
                if (firstStep) {
                    SpeechModule.speak(firstStep.textContent);
                }
            }, 200);
        });
        document.getElementById('disableScreenReaderBtn').addEventListener('click', function(event) {
            // Only set speech state and close dialog
            event.preventDefault();
            event.stopPropagation();
            speechReady = false;
            SpeechModule.autoRead = false;
            localStorage.setItem('autoRead', 'false');
            dialog.close();
        });
    } else {
        // Fallback: allow speech
        speechReady = true;
    }
});

// Patch SpeechModule.speak to only allow after user enables
const originalSpeak = SpeechModule.speak;
SpeechModule.speak = function(text, retryCount = 0) {
    if (!speechReady) {
        console.warn('Speech synthesis blocked until user enables Screen Reader.');
        return;
    }
    return originalSpeak.call(this, text, retryCount);
};

// Cancel button logic
window.addEventListener('DOMContentLoaded', function() {
  const cancelBtn = document.getElementById('cancelSubmissionBtn');
  if (cancelBtn) {
    cancelBtn.addEventListener('click', function() {
      if (submissionAbortController) submissionAbortController.abort();
      hideSubmissionOverlay();
      const submitBtn = document.getElementById('submitGrievanceBtn');
      if (submitBtn) submitBtn.disabled = false;
      alert('Submission cancelled. Please try again.');
    });
  }
});

// Modify the submit button click handler
document.getElementById('submitGrievanceBtn').addEventListener('click', async function(e) {
    e.preventDefault(); // Prevent form submission
    
    console.log('[TRACE] Submit button clicked');
    console.log('[DEBUG] Current step:', state.currentStep);
    console.log('[DEBUG] Submit button state:', {
        visible: this.offsetParent !== null,
        enabled: !this.disabled,
        text: this.textContent
    });

    // Prevent submission if recording is in progress
    if (RecordingModule.isRecording) {
        console.warn('[WARN] Cannot submit while recording is in progress');
        UIModule.showError('Please finish or stop your recording before submitting.');
        return;
    }

    // Prevent submission if not on the final step
    if (state.currentStep !== '3c') {
        console.warn('[WARN] Cannot submit from step:', state.currentStep);
        UIModule.showError('Please complete all steps before submitting.');
        return;
    }

    // Prevent multiple submissions
    if (isSubmitting) {
        console.warn('[WARN] Submission already in progress, ignoring click');
        return;
    }

    try {
        isSubmitting = true;
        this.disabled = true;
        
        // Show the submission overlay
        showSubmissionOverlay();
        
        // Call submitGrievance
        await GrievanceModule.submitGrievance();
    } catch (error) {
        console.error('[ERROR] Submission failed:', error);
        // Re-enable the button if submission fails
        this.disabled = false;
        isSubmitting = false;
        hideSubmissionOverlay();
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