/**
 * Nepal Chatbot Accessible Interface
 * Modular structure based on refactoring plan
 */

// Debug: Check if script starts loading
console.log('🔍 Starting to load app.js...');

import socket from './modules/socket.js';
import createReviewDataModule from './modules/reviewData.js';
import createSpeechModule from './modules/speech.js';
import createAccessibilityModule from './modules/accessibility.js';
import createAPIModule from './modules/api.js';
import createModifyModule from './modules/modify.js';

// Module namespaces
let SpeechModule = {};
let AccessibilityModule = {};
let UIModule = {};
let APIModule = {};
let FileUploadModule = {};
let RecordingModule = {};
let GrievanceModule = {};
let ModifyModule = {};
let EventModule = {};
let ReviewDataModule = {};

// Language Module
let LanguageModule = {
    currentLanguage: 'en',
    languageSelect: null,

    init: function() {
        this.languageSelect = document.getElementById('languageSelect');
        
        // Initialize language from localStorage if available
        if (localStorage.getItem('language_code')) {
            this.currentLanguage = localStorage.getItem('language_code');
            this.languageSelect.value = this.currentLanguage;
        }

        // Update language when selection changes
        this.languageSelect.addEventListener('change', (event) => {
            this.currentLanguage = event.target.value;
            localStorage.setItem('language_code', this.currentLanguage);
            // You can add additional language change handling here
            // For example, triggering a page reload or updating content
        });
    },

    getCurrentLanguage: function() {
        return this.currentLanguage;
    }
};

// Global state and configuration
let state = {
    currentStep: 'grievance',
    language: 'ne', // Default to Nepali
    grievanceId: null,
    userId: null
};

let speechReady = false;
let speechQueue = [];
let recordedBlobs = {};
let isSpeechIndicatorEnabled = true;
let overlayMutationObserver = null;
let cancelBtnTimeout = null;
let isTransitioning = false;

const SUBMISSION_STEP_WINDOW = ['personalInfo', 'address'];

// Define the APP_STEPS structure for application flow
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
    attachments: {
        name: 'Attachments',
        windows: ['attachments'],
        requiresRecording: false
    },
    review: {
        name: 'Review your Submission',
        windows: ['reviewAll'],
        requiresRecording: false
    }
};

// Helper function to get step order for navigation
function getStepOrder() {
    return ['grievance', 'personalInfo', 'attachments', 'review'];
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


UIModule = {
    steps: APP_STEPS,
    stepOrder: getStepOrder(),
    currentStepIndex: 0,
    currentWindowIndex: 0,

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
            let currentStepKey, currentWindow;
            try {
                const { step, window } = UIModule.getCurrentWindow();
                currentStepKey = step;
                currentWindow = window;
                
                // Debug logging
                console.log(`[NAV] showCurrentWindow: step='${currentStepKey}', window='${currentWindow}', stepIndex=${UIModule.currentStepIndex}, windowIndex=${UIModule.currentWindowIndex}`);
                
                // Default logic for other steps
                document.querySelectorAll('.step').forEach(stepEl => {
                    stepEl.hidden = true;
                    stepEl.style.display = 'none';
                });
                
                const elementId = `${currentStepKey}-${currentWindow}`;
                const el = document.getElementById(elementId);
                console.log(`[NAV] Looking for element: ${elementId}, found: ${!!el}`);
                
                if (el) {
                    console.log(`[NAV] Before changes - hidden: ${el.hidden}, display: ${el.style.display}`);
                    el.hidden = false;
                    el.style.display = 'block';
                    console.log(`[NAV] After changes - hidden: ${el.hidden}, display: ${el.style.display}`);
                    
                    // Additional debugging - check if element is actually visible
                    const rect = el.getBoundingClientRect();
                    console.log(`[NAV] Element dimensions:`, rect);
                    console.log(`[NAV] Element computed styles:`, {
                        display: globalThis.getComputedStyle(el).display,
                        visibility: globalThis.getComputedStyle(el).visibility,
                        opacity: globalThis.getComputedStyle(el).opacity
                    });
                    
                    // If this is the review element with zero dimensions, do detailed debugging
                    if (currentStepKey === 'review' && rect.width === 0 && rect.height === 0) {
                        console.log(`[NAV] DEBUGGING ZERO DIMENSIONS for element:`, elementId);
                        const computedStyle = globalThis.getComputedStyle(el);
                        console.log(`[NAV] Full computed style check:`, {
                            width: computedStyle.width,
                            height: computedStyle.height,
                            minWidth: computedStyle.minWidth,
                            minHeight: computedStyle.minHeight,
                            maxWidth: computedStyle.maxWidth,
                            maxHeight: computedStyle.maxHeight,
                            padding: computedStyle.padding,
                            margin: computedStyle.margin,
                            border: computedStyle.border,
                            boxSizing: computedStyle.boxSizing,
                            overflow: computedStyle.overflow,
                            position: computedStyle.position,
                            float: computedStyle.float,
                            fontSize: computedStyle.fontSize,
                            lineHeight: computedStyle.lineHeight
                        });
                        
                        // Check if the content inside has dimensions
                        const contentElements = el.querySelectorAll('*');
                        console.log(`[NAV] Found ${contentElements.length} child elements`);
                        contentElements.forEach((child, index) => {
                            const childRect = child.getBoundingClientRect();
                            if (childRect.width > 0 || childRect.height > 0) {
                                console.log(`[NAV] Child ${index} (${child.tagName}.${child.className}) has dimensions:`, childRect);
                            }
                        });
                        
                        // Check if there's actual text content
                        console.log(`[NAV] Element innerHTML length:`, el.innerHTML.length);
                        console.log(`[NAV] Element textContent length:`, el.textContent.length);
                        console.log(`[NAV] Element textContent preview:`, el.textContent.substring(0, 200));
                    }
                    
                    // If we're on the attachments step, update the grievanceId span
                    if (currentStepKey === 'attachments') {
                        const idElement = document.getElementById('grievanceId');
                        if (idElement) {
                            const span = idElement.querySelector('span');
                            if (span) {
                                span.textContent = state.grievanceId || '';
                            }
                        }
                    }
                    
                    // If we're on the review step, trigger review data population
                    if (currentStepKey === 'review') {
                        console.log('[NAV] On review step - triggering data population');
                        
                        // Try multiple ways to access the ReviewDataModule
                        let reviewModule = null;
                        if (window.debugReviewData) {
                            reviewModule = window.debugReviewData;
                            console.log('[NAV] Using debugReviewData');
                        } else if (window.ReviewDataModule) {
                            reviewModule = window.ReviewDataModule;
                            console.log('[NAV] Using global ReviewDataModule');
                        } else if (ReviewDataModule && typeof ReviewDataModule.updateReviewUI === 'function') {
                            reviewModule = ReviewDataModule;
                            console.log('[NAV] Using local ReviewDataModule');
                        }
                        
                        if (reviewModule && typeof reviewModule.updateReviewUI === 'function') {
                            console.log('[NAV] Review data available:', reviewModule.reviewData);
                            console.log('[NAV] Calling updateReviewUI...');
                            reviewModule.updateReviewUI();
                        } else {
                            console.warn('[NAV] ReviewDataModule not available or missing updateReviewUI function');
                            console.log('[NAV] Available on window:', Object.keys(window).filter(k => k.includes('Review')));
                        }
                    }
                    
                    const content = el.querySelector('.content');
                    if (content && SpeechModule.autoRead) {
                        SpeechModule.speak(content.textContent);
                    }
                    
                    // Update button states for the current step
                    UIModule.updateButtonStates({
                        isRecording: RecordingModule.isRecording,
                        hasRecording: RecordingModule.hasAnyRecording(),
                        isSubmitting: GrievanceModule.isSubmitting
                    });
                    
                    console.log(`[NAV] Successfully showed window: ${elementId}`);
                } else {
                    console.error(`[NAV] Element not found: ${elementId}`);
                }
            } catch(error) {
                console.error('[ERROR] Navigation error:', error, 'currentStepKey:', currentStepKey, 'currentWindow:', currentWindow);
            }
        },

        goToNextWindow: function() {
            const { step, window } = UIModule.getCurrentWindow();
            const currentStepKey = UIModule.stepOrder[UIModule.currentStepIndex];
            const currentStep = UIModule.steps[currentStepKey];
            // If there are more windows in this step, move to next window
            if (UIModule.currentWindowIndex < currentStep.windows.length - 1) {
                UIModule.currentWindowIndex++;
                this.showCurrentWindow();
            } else {
                // If we're at the last window of this step, move to next step
                this.goToNextStep();
            }
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

            // Navigation logic only - submission is handled by GrievanceModule.handleSubmission
                UIModule.currentStepIndex = nextStepIndex;
                state.currentStep = nextStepKey;
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
    
    resetApp: function() {
        this.currentStepIndex = 0;
        this.currentWindowIndex = 0;
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
                message.style.color = 'var(--primary-color)';
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
            isSubmitting = GrievanceModule.isSubmitting // Use centralized state
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
                    } else if (step === 'review') {
                        // Review step doesn't require recordings - always enable Next
                        button.disabled = false;
                        button.style.display = '';
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
                        
                        // Use centralized validation from GrievanceModule
                        const validation = GrievanceModule.canSubmit();
                        button.disabled = !validation.canSubmit;
                        
                        // Add tooltip or aria-label with validation reason
                        if (!validation.canSubmit) {
                            button.setAttribute('title', validation.reason);
                            button.setAttribute('aria-label', `Submit (disabled: ${validation.reason})`);
                        } else {
                            button.removeAttribute('title');
                            button.setAttribute('aria-label', 'Submit grievance');
                        }
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
 


/**
 * File Upload Module - Handles file selection and uploads
 */
FileUploadModule = {
    selectedFiles: [],
    uploadedFiles: [],
    maxFileSize: 0,
    allowedFileTypes: [],
    uploadedFileNames: [],
    isInitialized: false, // Add initialization flag
    
    init: function() {
        // Prevent double initialization
        if (this.isInitialized) {
            console.log('FileUploadModule already initialized, skipping...');
            return;
        }
        
        this.maxFileSize = APP_CONFIG.upload.maxFileSize || 10 * 1024 * 1024; // 10MB default
        this.allowedFileTypes = APP_CONFIG.upload.allowedTypes || [];
        
        this.setupFileInput();
        this.setupFileDrop();
        this.setupAttachmentButtons();
        
        // Register event-specific status update handler for file uploads
        socket.on('status_update:file_upload', this.handleStatusUpdateFileUpload.bind(this));
        
        this.isInitialized = true;
        console.log('✅ FileUploadModule initialized successfully');
    },
    
    setupFileInput: function() {
        const fileInput = document.getElementById('fileInput');
        const fileList = document.getElementById('fileList');
        
        if (fileInput && fileList) {
            // Remove ALL event listeners by replacing the element with a clone
            const newFileInput = fileInput.cloneNode(true);
            fileInput.parentNode.replaceChild(newFileInput, fileInput);
            
            // Add event listener to the new clean element
            newFileInput.addEventListener('change', (event) => {
                this.handleFileSelection(event.target.files);
            });
        }
    },
    
    setupAttachmentButtons: function() {
        // Clean and setup attach files button
        const attachFilesBtn = document.getElementById('attachFilesBtn');
        if (attachFilesBtn) {
            // Remove all event listeners by replacing with clone
            const newAttachFilesBtn = attachFilesBtn.cloneNode(true);
            attachFilesBtn.parentNode.replaceChild(newAttachFilesBtn, attachFilesBtn);
            
            newAttachFilesBtn.addEventListener('click', () => {
                const fileInput = document.getElementById('fileInput');
                if (fileInput) {
                    fileInput.click();
                }
            });
        }
        
        // Clean and setup submit files button
        const submitFilesBtn = document.getElementById('submitFilesBtn');
        if (submitFilesBtn) {
            // Remove all event listeners by replacing with clone
            const newSubmitFilesBtn = submitFilesBtn.cloneNode(true);
            submitFilesBtn.parentNode.replaceChild(newSubmitFilesBtn, submitFilesBtn);
            
            newSubmitFilesBtn.addEventListener('click', () => {
                this.submitSelectedFiles();
            });
        }
        
        // Clean and setup attach more files button
        const attachMoreBtn = document.getElementById('attachMoreBtn');
        if (attachMoreBtn) {
            // Remove all event listeners by replacing with clone
            const newAttachMoreBtn = attachMoreBtn.cloneNode(true);
            attachMoreBtn.parentNode.replaceChild(newAttachMoreBtn, attachMoreBtn);
            
            newAttachMoreBtn.addEventListener('click', () => {
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
            
            // Add all files under the 'files[]' key as expected by the server
            for (const file of this.selectedFiles) {
                formData.append('files[]', file);
                console.log(`Adding file to FormData: ${file.name}, size: ${file.size} bytes`);
            }
            
            // Upload all files in a single request
            console.log(`Uploading ${this.selectedFiles.length} files for grievance ID: ${grievanceId}`);
            const result = await APIModule.uploadFile(grievanceId, formData);
            
            // Process results
            if (result && (result.status === 'success' || result.status === 'processing')) {
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
                
                // Show appropriate message based on status
                if (result.status === 'processing') {
                    UIModule.showMessage('Files are being processed. You will be notified when processing is complete.', false);
                    if (result.warning) {
                        UIModule.showMessage(result.warning, false);
                    }
                } else {
                    UIModule.showMessage('Files uploaded successfully.', false);
                }
                
                return { success: true, results };
            } else {
                // Handle error
                throw new Error(result.error || result.message || "Failed to upload files");
            }
        } catch (error) {
            console.error('Error uploading files:', error);
            throw error;
        }
    },
    
    clearFiles: function() {
        this.selectedFiles = [];
        this.uploadedFiles = [];
        this.updateFileList();
        
        const uploadedFilesSection = document.getElementById('uploadedFilesSection');
        if (uploadedFilesSection) {
            uploadedFilesSection.hidden = true;
        }
    },
    
    handleStatusUpdateFileUpload: function(data) {
        console.log('Received status_update:file_upload:', data);
        // Check if this is a completed file upload
        if (data.status === 'completed' && data.message && data.message.results) {
            // Extract file names from the results array
            const newFiles = data.message.results
                .filter(result => result.status === 'success' && result.operation === 'file_upload' && result.value && result.value.file_name)
                .map(result => result.value.file_name);
            // Append new file names to the global list
            this.uploadedFileNames = [...this.uploadedFileNames, ...newFiles];
            // Update the upload success message
            const successMessageElement = document.getElementById('uploadSuccessMessage');
            if (successMessageElement) {
                if (this.uploadedFileNames.length > 0) {
                    successMessageElement.textContent = `Files uploaded successfully: ${this.uploadedFileNames.join(', ')}`;
                } else {
                    successMessageElement.textContent = 'Files uploaded successfully!';
                }
            }
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
        micPermissionNote.style.backgroundColor = 'var(--dark-bg)';
        micPermissionNote.style.color = 'var(--text-color)';
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
                successNote.style.backgroundColor = 'var(--success-color)';
                successNote.style.color = 'var(--text-color)';
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
            
            // Add metadata loaded event listener to get duration
            audio.addEventListener('loadedmetadata', () => {
                // Store duration in the recordedBlobs object
                if (!recordedBlobs[recordingType].duration) {
                    recordedBlobs[recordingType].duration = Math.round(audio.duration);
                }
            });
            
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
            isSubmitting: GrievanceModule.isSubmitting // Use centralized state
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
     * Check if there are any recordings (alias for hasRecordings)
     * @returns {boolean} - Whether any recordings exist
     */
    hasAnyRecording: function() {
        return this.hasRecordings();
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
 * Grievance Module - Handles grievance-related business logic and state
 */
GrievanceModule = {
    categories: [],
    isSubmitting: false, // Centralized submission state
    
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
    
    /**
     * Centralized state management with event notifications
     */
    setSubmissionState: function(isSubmitting) {
        const oldState = this.isSubmitting;
        this.isSubmitting = isSubmitting;
        
        // Dispatch state change event for other modules to listen
        if (oldState !== isSubmitting) {
            window.dispatchEvent(new CustomEvent('submissionStateChanged', { 
                detail: { 
                    isSubmitting,
                    previousState: oldState,
                    timestamp: Date.now()
                } 
            }));
            console.log(`[STATE] Submission state changed: ${oldState} → ${isSubmitting}`);
        }
    },

    /**
     * Centralized validation logic - single source of truth
     */
    canSubmit: function() {
        // Check if already submitting
        if (this.isSubmitting) {
            console.warn('[VALIDATION] Cannot submit: already submitting');
            return { canSubmit: false, reason: 'Already submitting' };
        }

        // Check if recording is in progress
        if (RecordingModule.isRecording) {
            console.warn('[VALIDATION] Cannot submit: recording in progress');
            return { canSubmit: false, reason: 'Recording in progress' };
        }

        // Check current step/window
        const { step, window } = UIModule.getCurrentWindow();
        if (!(step === 'personalInfo' && window === 'address')) {
            console.warn('[VALIDATION] Cannot submit: not at final step', { step, window });
            return { canSubmit: false, reason: 'Not at final step' };
        }

        // Check if session is properly initialized
        if (!state.grievanceId || !state.userId) {
            console.warn('[VALIDATION] Cannot submit: session not initialized');
            return { canSubmit: false, reason: 'Session not properly initialized' };
        }

        // Check if all required recordings exist
        const requiredRecordings = [
            'grievance_details',
            'user_full_name', 
            'user_contact_phone',
            'user_municipality',
            'user_village',
            'user_address'
        ];

        const missingRecordings = requiredRecordings.filter(type => 
            !RecordingModule.hasRecording(type)
        );

        if (missingRecordings.length > 0) {
            console.warn('[VALIDATION] Missing recordings:', missingRecordings);
            return { 
                canSubmit: false, 
                reason: `Missing recordings: ${missingRecordings.join(', ')}`,
                missingRecordings 
            };
        }

        console.log('[VALIDATION] All checks passed - can submit');
        return { canSubmit: true, reason: 'All validations passed' };
    },

    /**
     * Centralized submission handler - replaces EventModule.handleSubmit
     */
    handleSubmission: async function(e) {
        if (e) {
            e.preventDefault(); // Prevent form submission
        }
        
        console.log('[TRACE] Submit button clicked - handled by GrievanceModule');
        console.log('[DEBUG] Current step:', state.currentStep);
        console.log('[DEBUG] Submit button state:', {
            visible: e?.target?.offsetParent !== null,
            enabled: !e?.target?.disabled,
            text: e?.target?.textContent
        });

        // Use centralized validation - single validation call
        const validation = this.canSubmit();
        if (!validation.canSubmit) {
            console.warn(`[WARN] Submission blocked: ${validation.reason}`);
            UIModule.showMessage(`Cannot submit: ${validation.reason}`, true);
            SpeechModule.speak(`Cannot submit: ${validation.reason}`);
            return { success: false, reason: validation.reason, type: 'validation' };
        }

        // Set submission state using centralized method
        this.setSubmissionState(true);
        if (e?.target) {
            e.target.disabled = true;
        }
        
        try {
            // Call the actual submission logic with validation result to avoid duplicate checks
            const result = await this.submitGrievance(validation);
            
            if (result.success) {
                // Handle successful submission
                console.log('[SUCCESS] Submission completed successfully');
                UIModule.showMessage(result.message, false);
                
                // Announce success with grievance ID
                const successMessage = result.message + ' Your grievance ID is ' + 
                    state.grievanceId.split('').join(' ') + '. You can now attach photos or documents.';
                SpeechModule.speak(successMessage);
                
                // Reset submission state after successful completion
                this.setSubmissionState(false);
                
                return { success: true, result: result.result };
            } else {
                // Handle submission failure with type-specific handling
                console.warn(`[WARN] Submission failed [${result.type}]: ${result.error}`);
                this.handleSubmissionError(result);
                
                // Re-enable the button for retry
                if (e?.target) {
                    e.target.disabled = false;
                }
                
                return { success: false, error: result.error, type: result.type };
            }
            
        } catch (error) {
            // This should rarely happen now since submitGrievance returns status objects
            console.error('[ERROR] Unexpected error in submission:', error);
            
            // Re-enable the button if submission fails
            if (e?.target) {
                e.target.disabled = false;
            }
            
            // Reset state on unexpected error
            this.setSubmissionState(false);
            
            // Show user-friendly error using UIModule consistently
            const errorMessage = error.message || 'An unexpected error occurred. Please try again.';
            UIModule.showMessage(errorMessage, true);
            SpeechModule.speak(errorMessage);
            
            return { success: false, error: errorMessage, type: 'unexpected' };
        }
        // Note: State reset is handled appropriately in each path
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
    
    
    submitGrievance: async function(validationResult = null) {
        // Use passed validation result or perform validation if not provided (for backward compatibility)
        const validation = validationResult || this.canSubmit();
        if (!validation.canSubmit) {
            console.warn(`[VALIDATION] Submit blocked: ${validation.reason}`);
            return { 
                success: false, 
                error: validation.reason,
                type: 'validation'
            };
        }
        
            const { step, window } = UIModule.getCurrentWindow();
            if (!(step === 'personalInfo' && window === 'address')) {
            return { 
                success: false, 
                error: 'Please complete all steps before submitting.',
                type: 'validation'
            };
        }
        
        // Check if IDs are available
        if (!state.grievanceId || !state.userId) {
            return { 
                success: false, 
                error: 'Session not properly initialized. Please refresh the page.',
                type: 'session'
            };
            }
        
        try {
            // Add interface language and IDs to formData
            const formData = new FormData();
            formData.append('language_code', LanguageModule.getCurrentLanguage());
            formData.append('grievance_id', state.grievanceId);
            formData.append('user_id', state.userId);
            
            // Submit all recordings with the pre-generated IDs
            const result = await APIModule.submitGrievance({}, recordedBlobs, formData);
            if (result.status === 'success') {
                // IDs are already set and room already joined, just proceed to attachments
                UIModule.currentStepIndex = UIModule.stepOrder.indexOf('attachments');
                UIModule.currentWindowIndex = 0;
                UIModule.Navigation.showCurrentWindow();
                
                // Log all task status/progress to console
                console.log('Task orchestration result:', result.tasks || result.files);
                
                // Don't reset submission state here - let the calling function handle success flow
                return { 
                    success: true, 
                    result,
                    message: 'Your grievance has been submitted successfully.'
                };
            } else {
                const errorMessage = result.error || result.message || 'Failed to submit grievance';
                return { 
                    success: false, 
                    error: errorMessage,
                    type: 'api'
                };
            }
        } catch (error) {
            console.error('Error submitting grievance:', error);
            return { 
                success: false, 
                error: error.message || 'There was an error submitting your grievance. Please try again.',
                type: 'network'
            };
        } finally {
            // Always re-enable submit buttons, but don't reset state here
            // State reset is handled by the calling function based on success/failure
            document.querySelectorAll('[data-action="submit"]').forEach(btn => {
                btn.disabled = false;
            });
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
                return {
                    success: false,
                    error: response.message || 'Failed to load grievance data',
                    type: 'api'
                };
            }
            
            // Store the data for later use
            this.reviewData = response.data;
            
            // Populate the review UI
            this.populateReviewUI(response.data);
            
            // Show success message
            UIModule.showMessage('Grievance data loaded successfully');
            
            return {
                success: true,
                data: response.data,
                message: 'Grievance data loaded successfully'
            };
            
    } catch (error) {
            console.error('Error loading grievance data:', error);
            const errorType = this.getErrorType(error, 'network');
            
            return {
                success: false,
                error: error.message || 'Failed to load grievance data. Please try again.',
                type: errorType
            };
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



    /**
     * Helper method to check if submission is currently allowed
     */
    isSubmissionAllowed: function() {
        return this.canSubmit().canSubmit;
    },

    /**
     * Helper method to get validation status with details
     */
    getValidationStatus: function() {
        return this.canSubmit();
    },

    /**
     * Helper method to get current submission state
     */
    getSubmissionState: function() {
        return {
            isSubmitting: this.isSubmitting,
            canSubmit: this.isSubmissionAllowed(),
            validationDetails: this.getValidationStatus()
        };
    },

    /**
     * Handle submission errors with type-specific messaging and actions
     */
    handleSubmissionError: function(result) {
        const { error, type } = result;
        
        // Log with error type for debugging
        console.error(`[${type.toUpperCase()}] Submission error:`, error);
        
        // Type-specific error handling
        switch (type) {
            case 'validation':
                // Validation errors - usually user action required
                UIModule.showMessage(`Validation Error: ${error}`, true);
                SpeechModule.speak(`Please fix the following: ${error}`);
                break;
                
            case 'session':
                // Session errors - may require page refresh
                UIModule.showMessage(`Session Error: ${error}`, true);
                SpeechModule.speak(`Session error: ${error}. You may need to refresh the page.`);
                break;
                
            case 'api':
                // API errors - server-side issues
                UIModule.showMessage(`Server Error: ${error}`, true);
                SpeechModule.speak(`Server error: ${error}. Please try again.`);
                break;
                
            case 'network':
                // Network errors - connectivity issues
                UIModule.showMessage(`Network Error: ${error}`, true);
                SpeechModule.speak(`Network error: ${error}. Please check your connection and try again.`);
                break;
                
            default:
                // Generic error handling
                UIModule.showMessage(error, true);
                SpeechModule.speak(error);
        }
        
        // Reset submission state for all error types
        this.setSubmissionState(false);
    },

    /**
     * Helper method to determine error type from error object or result
     */
    getErrorType: function(error, defaultType = 'unknown') {
        if (typeof error === 'object' && error.type) {
            return error.type;
        }
        
        // Categorize based on error message patterns
        if (error && typeof error === 'string') {
            const errorMessage = error.toLowerCase();
            
            if (errorMessage.includes('network') || errorMessage.includes('connection') || errorMessage.includes('fetch')) {
                return 'network';
            }
            if (errorMessage.includes('validation') || errorMessage.includes('required') || errorMessage.includes('missing')) {
                return 'validation';
            }
            if (errorMessage.includes('session') || errorMessage.includes('unauthorized') || errorMessage.includes('expired')) {
                return 'session';
            }
            if (errorMessage.includes('server') || errorMessage.includes('api') || errorMessage.includes('500') || errorMessage.includes('400')) {
                return 'api';
            }
        }
        
        return defaultType;
    },
};

EventModule = {
    init: function() {
        console.log('EventModule.init called');
        this.setupModifyButtons();
        this.setupNavigationButtons();
        this.setupRecordButtons();
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
    },

    setupNavigationButtons: function() {
        // Handle navigation buttons
        document.querySelectorAll('.nav-btn[data-action]').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const action = btn.dataset.action;
                
                // Prevent any action if recording is in progress
                if (RecordingModule.isRecording) {
                    console.warn('[EventModule] Action blocked: recording in progress');
                    return;
                }

                try {
                switch(action) {
                    case 'next':
                    case 'continue':
                        UIModule.Navigation.goToNextWindow();
                        break;
                    case 'prev':
                        UIModule.Navigation.goToPrevWindow();
                        break;
                        case 'submit':
                            console.log('[EventModule] Delegating submit to GrievanceModule');
                            const result = await GrievanceModule.handleSubmission(e);
                            if (result && !result.success) {
                                console.warn('[EventModule] Submission failed:', result.reason || result.error);
                            } else if (result && result.success) {
                                console.log('[EventModule] Submission successful');
                            }
                        break;
                    case 'retry':
                const { step, window } = UIModule.getCurrentWindow();
                const recordingType = getRecordingTypeForWindow(step, window);
                if (recordingType) {
                            RecordingModule.startRecording(recordingType);
                            } else {
                                console.warn('[EventModule] No recording type found for retry action');
                        }
                        break;
                        default:
                            console.warn('[EventModule] Unknown navigation action:', action);
                    }
                } catch (error) {
                    console.error('[EventModule] Error handling navigation action:', action, error);
                    
                    // Show user-friendly error message
                    const errorMessage = error.message || `Failed to ${action}. Please try again.`;
                    UIModule.showMessage(errorMessage, true);
                    SpeechModule.speak(errorMessage);
                    
                    // Re-enable button if it was disabled
                    if (e.target && e.target.disabled) {
            e.target.disabled = false;
        }
                }
            });
        });
    },

    setupRecordButtons: function() {
        // Handle record buttons
        console.log('setupRecordButtons called');
        const recordButtons = document.querySelectorAll('.record-btn');
        console.log(`Found ${recordButtons.length} record buttons`);
        
        recordButtons.forEach((btn, index) => {
            console.log(`Setting up listener for button ${index + 1}:`, btn.id);
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
        console.log('setupRecordButtons completed');
    },

    setupAccessibilityButtons: function() {
        // Note: contrastToggleBtn is handled by AccessibilityModule directly
        // const contrastBtn = document.getElementById('contrastToggleBtn');
        // if (contrastBtn) {
        //     contrastBtn.addEventListener('click', () => {
        //         AccessibilityModule.toggleContrast();
        //     });
        // }

        const fontSizeBtn = document.getElementById('fontSizeBtn');
        if (fontSizeBtn) {
            fontSizeBtn.addEventListener('click', () => {
                AccessibilityModule.increaseFontSize();
            });
        }

        // const readPageBtn = document.getElementById('readPageBtn');
        // if (readPageBtn) {
        //     readPageBtn.addEventListener('click', () => {
        //         SpeechModule.toggleAutoRead();
        //     });
        // }

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


// Attach modules to window for global access (needed for inline event handlers)
window.SpeechModule = SpeechModule;
window.AccessibilityModule = AccessibilityModule;
window.UIModule = UIModule;
window.APIModule = APIModule;
window.FileUploadModule = FileUploadModule;
window.RecordingModule = RecordingModule;
window.GrievanceModule = GrievanceModule;
window.ModifyModule = ModifyModule;
window.EventModule = EventModule;
window.LanguageModule = LanguageModule;
// Note: ReviewDataModule is assigned after initialization

// Test if script loads completely and we reach the DOMContentLoaded setup
console.log('🔍 End of app.js reached - about to set up DOMContentLoaded listener');

// Function to initialize all modules
function initializeModules() {
    console.log('🔍 Starting module initialization...');
    
    // Initialize all modules with error handling
    try {
        console.log('Initializing SpeechModule...');
        // Create SpeechModule instance
        SpeechModule = createSpeechModule();
    SpeechModule.init();
        console.log('✅ SpeechModule initialized');
    } catch (error) {
        console.error('❌ SpeechModule failed:', error);
    }
    
    try {
        console.log('Initializing AccessibilityModule...');
        // Create AccessibilityModule instance with SpeechModule dependency
        AccessibilityModule = createAccessibilityModule(SpeechModule);
    AccessibilityModule.init();
        console.log('✅ AccessibilityModule initialized');
    } catch (error) {
        console.error('❌ AccessibilityModule failed:', error);
    }
    
    try {
        console.log('Initializing UIModule...');
    UIModule.init();
        console.log('✅ UIModule initialized');
    } catch (error) {
        console.error('❌ UIModule failed:', error);
    }
    
    try {
        console.log('Initializing APIModule...');
        // Create APIModule instance
        APIModule = createAPIModule();
    APIModule.init();
        console.log('✅ APIModule initialized');
    } catch (error) {
        console.error('❌ APIModule failed:', error);
    }
    
    try {
        console.log('Initializing FileUploadModule...');
    FileUploadModule.init();
        console.log('✅ FileUploadModule initialized');
    } catch (error) {
        console.error('❌ FileUploadModule failed:', error);
    }
    
    try {
        console.log('Initializing RecordingModule...');
    RecordingModule.init();
        console.log('✅ RecordingModule initialized');
    } catch (error) {
        console.error('❌ RecordingModule failed:', error);
    }
    
    try {
        console.log('Initializing GrievanceModule...');
    GrievanceModule.init();
        console.log('✅ GrievanceModule initialized');
    } catch (error) {
        console.error('❌ GrievanceModule failed:', error);
    }
    
    try {
        console.log('Initializing ModifyModule...');
        // Create ModifyModule instance with dependencies
        ModifyModule = createModifyModule(APIModule, UIModule);
    ModifyModule.init();
        console.log('✅ ModifyModule initialized');
    } catch (error) {
        console.error('❌ ModifyModule failed:', error);
    }
    
    try {
        console.log('Initializing LanguageModule...');
        LanguageModule.init();
        console.log('✅ LanguageModule initialized');
    } catch (error) {
        console.error('❌ LanguageModule failed:', error);
    }
    
    try {
        console.log('Initializing ReviewDataModule...');
        // Create ReviewDataModule instance with dependencies
        ReviewDataModule = createReviewDataModule(socket, UIModule, RecordingModule, GrievanceModule);
        ReviewDataModule.init();
        
        // Make sure it's available on window for onclick handlers
        window.ReviewDataModule = ReviewDataModule;
        
        console.log('✅ ReviewDataModule initialized');
    } catch (error) {
        console.error('❌ ReviewDataModule failed:', error);
    }

    // Initialize EventModule with proper DOM readiness detection
    initializeEventModule();
    
    // Set up global state change listeners
    setupStateChangeListeners();
}

/**
 * Initialize EventModule with proper DOM readiness detection
 */
function initializeEventModule() {
    // Check if required DOM elements exist before initializing EventModule
    const checkDOMReadiness = () => {
        const requiredElements = [
            '.nav-btn[data-action]',
            '.record-btn',
            '#contrastToggleBtn',
            '#fontSizeBtn',
            '#readPageBtn',
            '#speedBtn'
        ];
        
        const allElementsReady = requiredElements.every(selector => {
            const elements = document.querySelectorAll(selector);
            return elements.length > 0;
        });
        
        if (allElementsReady) {
            try {
                console.log('Initializing EventModule...');
                EventModule.init();
                console.log('✅ EventModule initialized after DOM ready check');
                return true;
            } catch (error) {
                console.error('❌ EventModule failed:', error);
                return false;
            }
        }
        return false;
    };
    
    // Try immediate initialization
    if (checkDOMReadiness()) {
        return;
    }
    
    // If not ready, use MutationObserver to wait for DOM changes
    console.log('🔍 DOM not ready for EventModule, waiting for elements...');
    const observer = new MutationObserver((mutations) => {
        if (checkDOMReadiness()) {
            observer.disconnect();
        }
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
    
    // Fallback timeout after 5 seconds
    setTimeout(() => {
        if (!checkDOMReadiness()) {
            console.warn('⚠️ EventModule initialization timeout - forcing init');
            try {
                EventModule.init();
                console.log('✅ EventModule initialized via timeout fallback');
            } catch (error) {
                console.error('❌ EventModule timeout fallback failed:', error);
            }
        }
        observer.disconnect();
    }, 5000);
}

/**
 * Set up global state change listeners
 */
function setupStateChangeListeners() {
    // Listen for submission state changes
    window.addEventListener('submissionStateChanged', (event) => {
        const { isSubmitting, previousState } = event.detail;
        console.log(`[StateListener] Submission state: ${previousState} → ${isSubmitting}`);
        
        // Update UI components that depend on submission state
        try {
            UIModule.updateButtonStates({
                isRecording: RecordingModule.isRecording,
                hasRecording: RecordingModule.hasAnyRecording(),
                isSubmitting: isSubmitting
            });
        } catch (error) {
            console.error('[StateListener] Error updating button states:', error);
        }
        
        // Update any other UI elements that depend on submission state
        document.querySelectorAll('[data-action="submit"]').forEach(btn => {
            if (isSubmitting) {
                btn.disabled = true;
                btn.classList.add('submitting');
            } else {
                btn.classList.remove('submitting');
                // Don't auto-enable - let validation determine if it should be enabled
    }
});
    });
    
    console.log('✅ State change listeners initialized');
}

// Function to generate IDs and join socket room
function initializeGrievanceSession() {
    try {
        console.log('🔍 Generating grievanceId and userId...');
        
        // Get province and district from URL parameters if available
        const urlParams = new URLSearchParams(window.location.search);
        const province = urlParams.get('province') || 'KO';  // Default to 'KO'
        const district = urlParams.get('district') || 'JH';   // Default to 'JH'
        
        console.log(`Using province: ${province}, district: ${district} for ID generation`);
        
        // Call the API to generate IDs using the APIModule
        APIModule.generateIds(province, district)
        .then(data => {
            console.log('🔍 Generated IDs:', data);
            if (data.status === 'success') {
                state.grievanceId = data.grievance_id;
                state.userId = data.user_id;
                
                console.log('Generated grievanceId:', state.grievanceId);
                console.log('Generated userId:', state.userId);
                
                // Join the room for this grievance
                socket.emit('join_room', { room: state.grievanceId });
                console.log('Joined room:', state.grievanceId);
            } else {
                console.error('❌ Failed to generate IDs:', data.message);
                // Fallback to client-side generation if API fails
                const timestamp = Date.now();
                const randomId = Math.random().toString(36).substr(2, 9);
                state.grievanceId = `GRV_${timestamp}_${randomId}`;
                state.userId = `USR_${timestamp}_${randomId}`;
                
                console.log('Fallback grievanceId:', state.grievanceId);
                console.log('Fallback userId:', state.userId);
                
                socket.emit('join_room', { room: state.grievanceId });
                console.log('Joined room:', state.grievanceId);
            }
        })
        .catch(error => {
            console.error('❌ API call failed, using fallback:', error);
            // Fallback to client-side generation if API call fails
            const timestamp = Date.now();
            const randomId = Math.random().toString(36).substr(2, 9);
            state.grievanceId = `GRV_${timestamp}_${randomId}`;
            state.userId = `USR_${timestamp}_${randomId}`;
            
            console.log('Fallback grievanceId:', state.grievanceId);
            console.log('Fallback userId:', state.userId);
            
            socket.emit('join_room', { room: state.grievanceId });
            console.log('Joined room:', state.grievanceId);
        });
        
    } catch (error) {
        console.error('❌ Failed to initialize grievance session:', error);
    }
}

// Check if DOM is already ready or wait for it
if (document.readyState === 'loading') {
    console.log('🔍 DOM is still loading, waiting for DOMContentLoaded...');
    document.addEventListener('DOMContentLoaded', () => {
        initializeModules();
        // Generate IDs after modules are initialized
        setTimeout(initializeGrievanceSession, 200);
});
} else {
    console.log('🔍 DOM is already ready, initializing immediately...');
    initializeModules();
    // Generate IDs after modules are initialized
    setTimeout(initializeGrievanceSession, 200);
}

socket.on('processing_complete', (data) => {
    console.log('Processing complete:', data);
    UIModule.showMessage(`Processing complete: ${data.message}`, false);
    
    // Update UI state using centralized state management
    UIModule.updateButtonStates({
        isRecording: RecordingModule.isRecording,
        hasRecording: RecordingModule.hasAnyRecording(),
        isSubmitting: GrievanceModule.isSubmitting // Use centralized state
    });
});