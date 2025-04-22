// Accessible Interface JavaScript
document.addEventListener('DOMContentLoaded', () => {
    console.log('Accessible interface: DOM loaded');
    const config = window.APP_CONFIG;
    
    // Simple speech function that works (copied directly from test-speech.html)
    function simpleSpeech(text, rate = 1.0, callback) {
        try {
            // TEMPORARILY DISABLED TTS
            console.log('TTS disabled - would have spoken:', text);
            
            // Just call the callback immediately
            if (callback) {
                setTimeout(callback, 100);
            }
            return true;
            
            /* ORIGINAL CODE COMMENTED OUT
            if (!window.speechSynthesis) {
                throw new Error('Speech synthesis not supported');
            }
            
            // Cancel any ongoing speech
            window.speechSynthesis.cancel();
            
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.rate = typeof rate === 'string' ? parseFloat(rate) : rate;
            
            utterance.onstart = function() {
                console.log('Speech started');
            };
            
            utterance.onend = function() {
                console.log('Speech ended');
                if (callback) callback();
            };
            
            utterance.onerror = function(event) {
                console.error('Speech error:', event.error || 'Unknown error');
                showFallbackText(text);
                if (callback) callback(event.error || 'Unknown error');
            };
            
            window.speechSynthesis.speak(utterance);
            console.log('Speech request sent');
            
            return true;
            */
        } catch (error) {
            console.error('Speech exception:', error.message);
            // showFallbackText(text); // Also disable this
            if (callback) callback(error.message);
            return false;
        }
    }
    
    // Visual fallback display (copied from test-speech.html)
    function showFallbackText(text) {
        // TEMPORARILY DISABLED
        console.log('Fallback text display disabled - would have shown:', text);
        return;
        
        /* ORIGINAL CODE COMMENTED OUT
        console.log('Showing fallback text:', text);
        
        // Create dialog
        const dialog = document.createElement('div');
        dialog.style.position = 'fixed';
        dialog.style.top = '30%';
        dialog.style.left = '50%';
        dialog.style.transform = 'translate(-50%, -50%)';
        dialog.style.backgroundColor = 'rgba(0, 0, 0, 0.8)';
        dialog.style.color = 'white';
        dialog.style.padding = '20px';
        dialog.style.borderRadius = '10px';
        dialog.style.zIndex = '9999';
        dialog.style.minWidth = '300px';
        dialog.style.maxWidth = '80%';
        dialog.style.textAlign = 'center';
        
        const heading = document.createElement('h3');
        heading.textContent = 'Text to Speech';
        heading.style.margin = '0 0 10px 0';
        
        const content = document.createElement('p');
        content.textContent = text;
        
        const closeBtn = document.createElement('button');
        closeBtn.textContent = 'Close';
        closeBtn.style.marginTop = '15px';
        
        dialog.appendChild(heading);
        dialog.appendChild(content);
        dialog.appendChild(closeBtn);
        
        document.body.appendChild(dialog);
        console.log('Fallback dialog shown');
        
        closeBtn.onclick = function() {
            document.body.removeChild(dialog);
            console.log('Fallback dialog closed');
        };
        
        // Auto-dismiss after 8 seconds
        setTimeout(function() {
            if (document.body.contains(dialog)) {
                document.body.removeChild(dialog);
                console.log('Fallback dialog auto-dismissed');
            }
        }, 8000);
        */
    }
    
    // Get utilities from shared script (but we'll use our own speech function)
    const { $ } = window.nepalChatbot || { $: (id) => document.getElementById(id) };
    const accessibility = window.nepalChatbot?.accessibility || {
        toggleContrast: function() {
            document.body.classList.toggle('high-contrast');
        },
        setFontSize: function(size) {
            document.documentElement.style.fontSize = size + 'px';
        },
        savePreference: function(key, value) {
            localStorage.setItem(key, value);
        },
        loadPreference: function(key, defaultValue) {
            const value = localStorage.getItem(key);
            return value !== null ? value : defaultValue;
        }
    };
    
    const state = {
        currentStep: 'step1',
        recording: false,
        recorder: null,
        audioBlobs: {},
        fontSize: config.accessibility.fontSize.default,
        lastAnnouncement: Date.now(),
        // Define the sequence of steps
        stepSequence: ['step1', 'step2a', 'step2b', 'step3a', 'step3b', 'step3c', 'result'],
        // Store the grievance ID once created
        grievanceId: null,
        // Store selected files for upload
        selectedFiles: []
    };

    console.log('Accessible interface: Initializing steps');
    
    // Initialize all step containers and elements
    // We're using a more structured approach for expanded steps
    const stepContainers = {
        step1: document.getElementById('step1'),
        step2a: document.getElementById('step2a'),
        step2b: document.getElementById('step2b'),
        step3a: document.getElementById('step3a'),
        step3b: document.getElementById('step3b'),
        step3c: document.getElementById('step3c'),
        result: document.getElementById('result')
    };
    
    // Create a structured object for each step's elements
    const stepElements = {};
    
    // Setup all steps (1, 2a, 2b, 3a, 3b, 3c)
    const stepIds = ['1', '2a', '2b', '3a', '3b', '3c'];
    
    stepIds.forEach(id => {
        const stepKey = 'step' + id;
        const container = document.getElementById(stepKey);
        if (!container) {
            console.error(`Step container ${stepKey} not found in the DOM`);
            return;
        }
        
        console.log(`Initializing elements for step ${stepKey}`);
        
        const recordBtnId = `recordBtn${id}`;
        const statusId = `status${id}`;
        const playbackId = `playback${id}`;
        
        const recordBtn = document.getElementById(recordBtnId);
        const status = document.getElementById(statusId);
        const playback = document.getElementById(playbackId);
        
        if (!recordBtn) console.warn(`Record button ${recordBtnId} not found for ${stepKey}`);
        if (!status) console.warn(`Status element ${statusId} not found for ${stepKey}`);
        if (!playback) console.warn(`Playback element ${playbackId} not found for ${stepKey}`);
        
        stepElements[stepKey] = {
            container: container,
            recordBtn: recordBtn,
            status: status,
            timer: status ? status.querySelector('span') : null,
            playback: playback,
            audio: playback ? playback.querySelector('audio') : null,
            retryBtn: playback ? playback.querySelector('.retry-btn') : null,
            nextBtn: playback ? playback.querySelector('.next-btn') : null
        };
        
        // Log the initialized elements
        console.log(`Step ${id} initialized:`, {
            container: !!stepElements[stepKey].container,
            recordBtn: !!stepElements[stepKey].recordBtn,
            status: !!stepElements[stepKey].status,
            timer: !!stepElements[stepKey].timer,
            playback: !!stepElements[stepKey].playback,
            audio: !!stepElements[stepKey].audio,
            retryBtn: !!stepElements[stepKey].retryBtn,
            nextBtn: !!stepElements[stepKey].nextBtn
        });
    });

    // Initialize
    function init() {
        console.log('Accessible interface: Initializing');
        
        // Check for media devices
        if (!navigator.mediaDevices) {
            console.error('Media devices API not available');
            showError(config.errors.browserSupport);
            return;
        }
        
        console.log('Media devices supported');
        
        initRecording();
        initAccessibility();
        initHelp();
        initReadButtons();
        initFocusAnnouncements();
        initFileUpload();

        // Show first step and hide all others
        Object.keys(stepContainers).forEach(stepId => {
            stepContainers[stepId].hidden = (stepId !== 'step1');
        });
        
        // Add direct submit button handler for step3c
        const step3cSubmitBtn = document.querySelector('#playback3c .next-btn');
        if (step3cSubmitBtn) {
            console.log('Adding direct handler to step3c submit button');
            step3cSubmitBtn.addEventListener('click', function() {
                console.log('Step3c submit button clicked directly');
                submitGrievance();
            });
        } else {
            console.error('Could not find step3c submit button');
        }
        
        console.log('TTS disabled - welcome message not announced');
        /* Original welcome message - disabled
        const welcomeMessage = 
            'Welcome to the Accessible Grievance Reporting system. ' +
            'This interface will guide you through reporting a grievance step by step. ' +
            'Use the Read Page button at the bottom to hear all instructions, or press the ' +
            'speaker icons next to each step for specific guidance. ' +
            'You can also press the Help button for more options. ' +
            'To begin, press the Record Grievance button in Step 1.';
        
        simpleSpeech(welcomeMessage, document.getElementById('rate').value);
        */
        
        // Pre-check for microphone permission to avoid issues later
        checkMicrophonePermission();
    }
    
    // Check microphone permission proactively to avoid issues when recording
    function checkMicrophonePermission() {
        if (navigator.permissions && navigator.permissions.query) {
            navigator.permissions.query({ name: 'microphone' })
                .then(permissionStatus => {
                    console.log('Microphone permission status:', permissionStatus.state);
                    
                    if (permissionStatus.state === 'denied') {
                        simpleSpeech("Microphone access is denied. Please enable microphone access in your browser settings to use the recording feature.");
                    }
                    
                    permissionStatus.onchange = function() {
                        console.log('Microphone permission status changed to:', this.state);
                    };
                })
                .catch(error => {
                    console.error('Error checking microphone permission:', error);
                });
        } else {
            console.log('Permissions API not supported, will check mic when recording starts');
        }
    }

    // Add focus announcements
    function initFocusAnnouncements() {
        // TEMPORARILY DISABLED FOCUS SOUNDS
        console.log('Focus announcements disabled');
        return;
        
        /* ORIGINAL CODE COMMENTED OUT
        // Add audio feedback for focus
        const focusSound = new Audio();
        focusSound.src = 'data:audio/wav;base64,UklGRjIAAABXQVZFZm10IBIAAAABAAEAQB8AAEAfAAABAAgAAABMYXZjNTguMTMuMTAwAGRhdGEAAAAA';
        
        // Add focus announcement for all buttons
        const buttons = document.querySelectorAll('button');
        buttons.forEach(button => {
            button.addEventListener('focus', () => {
                // Play subtle focus sound
                focusSound.play().catch(e => console.log('Could not play focus sound', e));
                
                // Don't announce too frequently (debounce)
                if (Date.now() - state.lastAnnouncement > 1500) {
                    state.lastAnnouncement = Date.now();
                    
                    // Get the button's accessible name from aria-label or text content
                    const buttonName = button.getAttribute('aria-label') || button.textContent;
                    
                    // Don't announce read buttons to avoid conflict with their own action
                    if (!button.classList.contains('read-btn')) {
                        const announcement = `${buttonName}. Press Enter to activate.`;
                        simpleSpeech(announcement, document.getElementById('rate').value);
                    }
                }
            });
            
            // Add keyboard activation for better accessibility
            button.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    button.click();
                }
            });
        });
        */
    }

    // Recording functionality
    function initRecording() {
        console.log('Initializing recording buttons');
        
        // Setup recording for each step
        Object.keys(stepElements).forEach(stepKey => {
            const step = stepElements[stepKey];
            
            if (!step.recordBtn) {
                console.error(`Record button for ${stepKey} not found`);
                return;
            }
            
            // Use direct event handlers
            step.recordBtn.addEventListener('click', function() {
                console.log(`Record button for ${stepKey} clicked, recording state:`, state.recording);
                if (state.recording) {
                    stopRecording(stepKey);
                } else {
                    startRecording(stepKey);
                }
            });
            
            // Make sure buttons are visible and enabled
            step.recordBtn.hidden = false;
            step.recordBtn.disabled = false;
            
            if (step.retryBtn) {
                step.retryBtn.addEventListener('click', function() {
                    resetRecording(stepKey);
                });
            }
            
            if (step.nextBtn) {
                step.nextBtn.addEventListener('click', function() {
                    // Move to the next step in the sequence
                    const currentIndex = state.stepSequence.indexOf(stepKey);
                    if (currentIndex >= 0 && currentIndex < state.stepSequence.length - 1) {
                        const nextStepId = state.stepSequence[currentIndex + 1];
                        showStep(nextStepId);
                    } else if (stepKey === 'step3c') {
                        submitGrievance();
                    }
                });
            }
        });
        
        // Setup the "New Grievance" button
        const newBtn = document.getElementById('newBtn');
        if (newBtn) {
            newBtn.addEventListener('click', function() {
                resetAllAndStartOver();
            });
        }
    }

    async function startRecording(stepKey) {
        console.log(`Starting recording for ${stepKey}`);
        const step = stepElements[stepKey];
        
        // Prevent multiple recording attempts
        if (state.recording) {
            console.log('Already recording, stopping current recording first');
            stopRecording(stepKey);
            return;
        }
        
        try {
            console.log('Requesting microphone access...');
            const stream = await navigator.mediaDevices.getUserMedia({ 
                audio: true,
                video: false // Explicitly specify no video to avoid unnecessary permission requests
            });
            
            console.log('Microphone access granted, creating MediaRecorder');
            state.recording = true;
            
            // Set up MediaRecorder with appropriate options
            const options = {
                mimeType: 'audio/webm',
                audioBitsPerSecond: 128000
            };
            
            try {
                state.recorder = new MediaRecorder(stream, options);
            } catch (e) {
                console.log('MediaRecorder with options failed, using default', e);
            state.recorder = new MediaRecorder(stream);
            }
            
            const chunks = [];

            state.recorder.ondataavailable = e => {
                console.log('Data available from recorder', e.data.size);
                if (e.data.size > 0) {
                    chunks.push(e.data);
                }
            };
            
            state.recorder.onstop = () => {
                console.log('Recorder stopped, processing', chunks.length, 'chunks');
                if (chunks.length > 0) {
                const blob = new Blob(chunks, { type: 'audio/webm' });
                    state.audioBlobs[stepKey] = blob;
                    
                    // Create audio URL and update UI
                    const audioURL = URL.createObjectURL(blob);
                    if (step.audio) {
                        step.audio.src = audioURL;
                        step.playback.hidden = false;
                    } else {
                        console.error(`Audio element not found for ${stepKey}`);
                    }
                    
                    if (step.status) {
                        step.status.hidden = true;
                    }
                    
                    if (step.recordBtn) {
                        step.recordBtn.hidden = false;
                        const originalLabel = step.recordBtn.getAttribute('aria-label') || 'Record';
                        step.recordBtn.textContent = originalLabel.replace('Stop', '').trim();
                    }
                    
                    // Stop tracks
                stream.getTracks().forEach(track => track.stop());
                    console.log(`Recording for ${stepKey} completed and ready for playback`);
                    
                    // Announce recording complete
                    simpleSpeech("Recording complete. You can now play it back, retry, or continue.", 
                        document.getElementById('rate').value);
                } else {
                    console.error('No data recorded');
                    simpleSpeech("No audio was recorded. Please try again.", 
                        document.getElementById('rate').value);
                    resetRecording(stepKey);
                }
            };
            
            state.recorder.onerror = (event) => {
                console.error('MediaRecorder error:', event);
                simpleSpeech("There was an error while recording. Please try again.", 
                    document.getElementById('rate').value);
                resetRecording(stepKey);
            };

            // Start the recorder with timeslice to ensure we get data chunks
            state.recorder.start(1000);
            console.log('MediaRecorder started');
            
            // Update UI
            if (step.recordBtn) {
                step.recordBtn.textContent = 'Stop Recording';
            }
            
            if (step.status) {
                step.status.hidden = false;
            }
            
            startTimer(stepKey);
            
            // Announce recording started
            simpleSpeech("Recording started. Speak clearly and press the same button when finished.", 
                document.getElementById('rate').value);

        } catch (err) {
            console.error('Recording error:', err);
            state.recording = false;
            
            if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
                showError(config.errors.micPermission);
                simpleSpeech("Microphone access was denied. Please allow microphone access to record your grievance.", 
                    document.getElementById('rate').value);
            } else if (err.name === 'NotFoundError') {
                showError("No microphone found. Please connect a microphone and try again.");
                simpleSpeech("No microphone found. Please connect a microphone and try again.", 
                    document.getElementById('rate').value);
            } else {
                showError(config.errors.recording);
                simpleSpeech("There was an error starting the recording. Please try again.", 
                    document.getElementById('rate').value);
            }
        }
    }

    function stopRecording(stepKey) {
        console.log(`Stopping recording for ${stepKey}`);
        const step = stepElements[stepKey];
        
        if (state.recorder && state.recording) {
            try {
            state.recorder.stop();
                console.log('MediaRecorder stopped');
            } catch (e) {
                console.error('Error stopping MediaRecorder:', e);
                
                // Handle the error - force reset the state
                state.recording = false;
                
                // Ensure stream tracks are stopped if we have access to them
                if (state.recorder && state.recorder.stream) {
                    state.recorder.stream.getTracks().forEach(track => track.stop());
                }
                
                // Reset UI
                if (step) {
                    if (step.status) step.status.hidden = true;
                    if (step.recordBtn) {
                        const originalLabel = step.recordBtn.getAttribute('aria-label') || 'Record';
                        step.recordBtn.textContent = originalLabel.replace('Stop', '').trim();
                    }
                }
                
                stopTimer();
                return;
            }
            
            state.recording = false;
            
            // Reset the recording button text
            if (step && step.recordBtn) {
                const originalLabel = step.recordBtn.getAttribute('aria-label') || 'Record';
                step.recordBtn.textContent = originalLabel.replace('Stop', '').trim();
            }
            
            stopTimer();
        } else {
            console.warn(`Attempted to stop recording for ${stepKey} but no active recorder found`);
            
            // Reset UI elements in case of inconsistent state
            if (step) {
                if (step.status) step.status.hidden = true;
                if (step.recordBtn) {
                    const originalLabel = step.recordBtn.getAttribute('aria-label') || 'Record';
                    step.recordBtn.textContent = originalLabel.replace('Stop', '').trim();
                }
            }
            
            state.recording = false;
            stopTimer();
        }
    }

    function resetRecording(stepKey) {
        console.log(`Resetting recording for ${stepKey}`);
        const step = stepElements[stepKey];
        
        if (step) {
            step.playback.hidden = true;
            step.recordBtn.hidden = false;
            step.recordBtn.disabled = false;
            step.status.hidden = true;
            state.audioBlobs[stepKey] = null;
            
            // Announce reset
            simpleSpeech("Recording reset. You can now record again.", 
                document.getElementById('rate').value);
        }
    }

    // Reset everything and start over
    function resetAllAndStartOver() {
        console.log('Resetting all and starting over');
        
        // Clear all recordings
        Object.keys(state.audioBlobs).forEach(key => {
            state.audioBlobs[key] = null;
        });
        
        // Reset UI for all steps
        Object.keys(stepElements).forEach(stepKey => {
            const step = stepElements[stepKey];
            if (step) {
                step.playback.hidden = true;
                if (step.recordBtn) {
                    step.recordBtn.hidden = false;
                    step.recordBtn.disabled = false;
                    const originalLabel = step.recordBtn.getAttribute('aria-label') || 'Record';
                    step.recordBtn.textContent = originalLabel.replace('Stop', '').trim();
                }
                step.status.hidden = true;
                if (step.audio) {
                    step.audio.src = '';
                }
            }
        });
        
        // Show first step, hide others
        showStep('step1');
        
        // Announce new session
        simpleSpeech("Starting a new grievance report. Please record your grievance.", 
            document.getElementById('rate').value);
    }

    // Timer functionality
    let timer;
    function startTimer(stepKey) {
        // Clear any existing timer first
        stopTimer();
        
        const step = stepElements[stepKey];
        if (!step || !step.timer) {
            console.warn(`Timer element not found for ${stepKey}`);
            return;
        }
        
        let seconds = 0;
        timer = setInterval(() => {
            seconds++;
            const mins = Math.floor(seconds / 60);
            const secs = seconds % 60;
            
            if (step.timer) {
                step.timer.textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
                if (seconds >= config.recording.maxDuration) {
                    console.log(`Maximum recording duration reached for ${stepKey}`);
                    stopRecording(stepKey);
                }
            } else {
                console.warn(`Timer element disappeared for ${stepKey}`);
                stopTimer();
            }
        }, 1000);
    }

    function stopTimer() {
        if (timer) {
        clearInterval(timer);
            timer = null;
        }
    }

    // Accessibility functionality
    function initAccessibility() {
        console.log('Initializing accessibility features');
        
        const readBtn = document.getElementById('readBtn');
        console.log('Read button element:', readBtn);
        
        if (readBtn) {
            readBtn.onclick = function() {
                console.log('Read Page button clicked');
                readCurrentStep();
            };
        } else {
            console.error('Read Page button not found in the DOM!');
        }
        
        document.getElementById('rate').oninput = e => {
            const rate = e.target.value;
            document.getElementById('rateValue').textContent = rate + 'x';
            accessibility.savePreference('speechRate', rate);
        };
        
        document.getElementById('fontBtn').onclick = toggleFontSize;
        document.getElementById('contrastBtn').onclick = toggleContrast;

        // Load saved preferences
        const savedRate = accessibility.loadPreference('speechRate', '1.0');
        if (savedRate) {
            document.getElementById('rate').value = savedRate;
            document.getElementById('rateValue').textContent = savedRate + 'x';
        }
    }

    // Initialize read section buttons
    function initReadButtons() {
        console.log('Initializing read buttons - TTS disabled');
        const readButtons = document.querySelectorAll('.read-btn');
        console.log(`Found ${readButtons.length} read section buttons`);
        
        readButtons.forEach(button => {
            button.addEventListener('click', function() {
                console.log('Read button clicked - TTS disabled');
                const targetId = this.getAttribute('data-target');
                const targetElement = document.getElementById(targetId);
                if (targetElement) {
                    const heading = targetElement.querySelector('h2');
                    const content = targetElement.querySelector('.content p');
                    
                    if (heading && content) {
                        const speechText = heading.textContent + '. ' + content.textContent;
                        console.log('Would have read:', speechText);
                        
                        // Add visual indicator briefly
                    this.classList.add('reading');
                        setTimeout(() => {
                        this.classList.remove('reading');
                        }, 500);
                    }
                }
            });
        });
    }

    function readCurrentStep() {
        // TEMPORARILY DISABLED
        console.log('readCurrentStep called - TTS disabled');
        
        // Find the visible step
        let visibleStepId = null;
        Object.keys(stepContainers).forEach(stepId => {
            if (!stepContainers[stepId].hidden) {
                visibleStepId = stepId;
            }
        });
        
        console.log('Current visible step:', visibleStepId);
        
        if (!visibleStepId) {
            return;
        }
        
        const step = document.getElementById(visibleStepId);
        if (step) {
            const heading = step.querySelector('h2');
            const content = step.querySelector('.content p');
            
            if (heading && content) {
                const speechText = heading.textContent + '. ' + content.textContent;
                console.log('Would have read current step content:', speechText);
            }
        }
    }

    // Help functionality
    function initHelp() {
        console.log('Initializing help dialog - TTS disabled');
        const dialog = document.getElementById('helpDialog');
        document.getElementById('helpBtn').onclick = () => {
            dialog.showModal();
            // Log instead of reading help content
            const helpText = "Help and Instructions. " + 
                         document.querySelector('#helpDialog ol').textContent + " " +
                         document.querySelector('#helpDialog ul').textContent;
            console.log('Would have read help content:', helpText);
        };
        dialog.querySelector('button').onclick = () => dialog.close();
    }

    // Navigation
    function showStep(stepId) {
        console.log('Showing step:', stepId);
        console.log('Current step in state:', state.currentStep);
        console.log('Audio blob for step1 exists:', !!state.audioBlobs['step1']);
        console.log('Audio blobs keys:', Object.keys(state.audioBlobs));
        
        // Special handling when moving from step1 to step2a - create grievance ID
        if (state.currentStep === 'step1' && stepId === 'step2a') {
            // Only create grievance if we've recorded something
            if (state.audioBlobs['step1']) {
                console.log('Moving from step1 to step2a, creating grievance ID');
                
                // Create the grievance ID and then continue with navigation
                createGrievance().then(id => {
                    console.log('Created grievance ID:', id);
                    
                    // Update any UI that might need the ID
                    updateUIWithGrievanceId(id);
                    
                    // Continue with navigation
                    completeStepNavigation(stepId);
                }).catch(err => {
                    console.error('Failed to create grievance ID:', err);
                    // Continue anyway with navigation
                    completeStepNavigation(stepId);
                });
                
                // Return early as we'll complete navigation in the Promise handlers
                return;
            } else {
                console.warn('No recording for step1, skipping grievance creation');
                // Continue with normal navigation
            }
        }
        
        // For all other transitions, proceed normally
        completeStepNavigation(stepId);
    }
    
    // Helper function to update UI elements with grievance ID
    function updateUIWithGrievanceId(id) {
        console.log('Updating UI with grievance ID:', id);
        // Store the ID in the span element on the result page
        const idSpan = document.querySelector('#grievanceId span');
        if (idSpan) {
            idSpan.textContent = id;
        }
    }
    
    // Complete the step navigation process
    function completeStepNavigation(stepId) {
        // Hide all steps
        Object.keys(stepContainers).forEach(id => {
            stepContainers[id].hidden = true;
        });
        
        // Show the requested step
        if (stepContainers[stepId]) {
            stepContainers[stepId].hidden = false;
            
            // Update the current step in the state
            state.currentStep = stepId;
            
            const stepIndex = state.stepSequence.indexOf(stepId);
            if (stepIndex >= 0) {
                console.log(`Step ${stepId} is at position ${stepIndex+1} in the sequence`);
            }
            
            // Log step change instead of announcing
            const stepTitle = document.querySelector(`#${stepId} h2`)?.textContent;
            const stepContent = document.querySelector(`#${stepId} .content p`)?.textContent;
            if (stepTitle && stepContent) {
                console.log(`Would have announced: Moving to ${stepTitle}. ${stepContent}`);
            }
        } else {
            console.error(`Step container ${stepId} not found`);
        }
    }

    // Create a grievance ID from the server when step 1 is completed
    async function createGrievance() {
        try {
            console.log('Creating new grievance on server');
            console.log('API base URL:', config.api.baseUrl);
            
            // Debug output for configuration
            console.log('Current config:', {
                baseUrl: config.api.baseUrl,
                endpoints: config.api.endpoints
            });
            
            // Always generate a local ID first in case the server request fails
            const localId = generateLocalId();
            
            // Use the endpoint from config if available
            const endpoint = config.api.endpoints.createGrievance || '/create-grievance';
            console.log('Using endpoint:', endpoint);
            console.log('Full URL:', config.api.baseUrl + endpoint);
            
            try {
                // Make sure we're using the full server URL
                const serverUrl = config.api.baseUrl;
                const response = await fetch(`${serverUrl}${endpoint}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        source: 'accessibility',
                        timestamp: new Date().toISOString()
                    })
                });

                if (!response.ok) {
                    console.error('Failed to create grievance:', response.status, response.statusText);
                    // If the server returns an error, use the local ID
                    console.log('Using local grievance ID due to server error:', localId);
                    state.grievanceId = localId;
                    return localId;
                }

                // Try to parse the response
                try {
                    const data = await response.json();
                    console.log('Grievance created, response:', data);
                    
                    if (data.id || data.grievance_id) {
                        // Store the ID in state for later use
                        state.grievanceId = data.id || data.grievance_id;
                        console.log('Grievance ID stored in state:', state.grievanceId);
                        return state.grievanceId;
                    } else {
                        console.error('No grievance ID returned from server');
                        // Use the local ID
                        state.grievanceId = localId;
                        console.log('Using local grievance ID due to missing ID in response:', localId);
                        return localId;
                    }
                } catch (parseError) {
                    console.error('Error parsing response from server:', parseError);
                    // Use the local ID if we couldn't parse the response
                    state.grievanceId = localId;
                    console.log('Using local grievance ID due to parse error:', localId);
                    return localId;
                }
            } catch (networkError) {
                console.error('Network error creating grievance:', networkError);
                // Use the local ID in case of network errors
                state.grievanceId = localId;
                console.log('Using local grievance ID due to network error:', localId);
                return localId;
            }
        } catch (err) {
            console.error('Unexpected error creating grievance:', err);
            // Generate a fallback ID
            const fallbackId = 'ERR-' + Date.now();
            state.grievanceId = fallbackId;
            console.log('Using fallback grievance ID due to unexpected error:', fallbackId);
            return fallbackId;
        }
    }
    
    // Generate a local ID for grievances when server is unavailable
    function generateLocalId() {
        const timestamp = Date.now();
        const random = Math.floor(Math.random() * 1000);
        return `GR-${timestamp}-${random}`;
    }

    // File upload functionality
    function initFileUpload() {
        console.log('Initializing file upload functionality');
        
        const attachBtn = document.getElementById('attachFilesBtn');
        const fileInput = document.getElementById('fileInput');
        const fileList = document.getElementById('fileList');
        const fileListUl = fileList ? fileList.querySelector('ul') : null;
        
        if (!attachBtn || !fileInput || !fileList || !fileListUl) {
            console.error('File upload elements not found in the DOM');
            return;
        }
        
        // Show file input when attach button is clicked
        attachBtn.addEventListener('click', function() {
            console.log('Attach files button clicked');
            fileInput.click();
        });
        
        // Handle file selection
        fileInput.addEventListener('change', function() {
            console.log('Files selected:', this.files.length);
            if (this.files.length > 0) {
                // Clear previous file list
                fileListUl.innerHTML = '';
                state.selectedFiles = Array.from(this.files);
                
                // Display selected files
                state.selectedFiles.forEach((file, index) => {
                    const fileSizeKB = Math.round(file.size / 1024);
                    const fileItem = document.createElement('li');
                    
                    const fileNameSpan = document.createElement('span');
                    fileNameSpan.className = 'file-name';
                    fileNameSpan.textContent = file.name;
                    
                    const fileSizeSpan = document.createElement('span');
                    fileSizeSpan.className = 'file-size';
                    fileSizeSpan.textContent = `${fileSizeKB} KB`;
                    
                    const removeBtn = document.createElement('button');
                    removeBtn.className = 'remove-file';
                    removeBtn.textContent = '×';
                    removeBtn.setAttribute('aria-label', `Remove file ${file.name}`);
                    removeBtn.addEventListener('click', function() {
                        removeFile(index);
                    });
                    
                    fileItem.appendChild(fileNameSpan);
                    fileItem.appendChild(fileSizeSpan);
                    fileItem.appendChild(removeBtn);
                    fileListUl.appendChild(fileItem);
                });
                
                // Show the file list
                fileList.hidden = false;
                
                // Announce files selected
                simpleSpeech(`${this.files.length} files selected.`, document.getElementById('rate').value);
            } else {
                // Hide the file list if no files are selected
                fileList.hidden = true;
                state.selectedFiles = [];
            }
        });
    }

    // Remove a file from the selected files
    function removeFile(index) {
        console.log('Removing file at index:', index);
        if (index >= 0 && index < state.selectedFiles.length) {
            const fileName = state.selectedFiles[index].name;
            
            // Remove from state
            state.selectedFiles.splice(index, 1);
            
            // Update the UI
            const fileListUl = document.querySelector('#fileList ul');
            if (fileListUl) {
                fileListUl.innerHTML = ''; // Clear the list
                
                // Rebuild the list with updated files
                state.selectedFiles.forEach((file, idx) => {
                    const fileSizeKB = Math.round(file.size / 1024);
                    const fileItem = document.createElement('li');
                    
                    const fileNameSpan = document.createElement('span');
                    fileNameSpan.className = 'file-name';
                    fileNameSpan.textContent = file.name;
                    
                    const fileSizeSpan = document.createElement('span');
                    fileSizeSpan.className = 'file-size';
                    fileSizeSpan.textContent = `${fileSizeKB} KB`;
                    
                    const removeBtn = document.createElement('button');
                    removeBtn.className = 'remove-file';
                    removeBtn.textContent = '×';
                    removeBtn.setAttribute('aria-label', `Remove file ${file.name}`);
                    removeBtn.addEventListener('click', function() {
                        removeFile(idx);
                    });
                    
                    fileItem.appendChild(fileNameSpan);
                    fileItem.appendChild(fileSizeSpan);
                    fileItem.appendChild(removeBtn);
                    fileListUl.appendChild(fileItem);
                });
                
                // Hide the file list if no files are left
                if (state.selectedFiles.length === 0) {
                    document.getElementById('fileList').hidden = true;
                }
            }
            
            // Announce file removal
            simpleSpeech(`Removed file ${fileName}.`, document.getElementById('rate').value);
        }
    }

    // Form submission
    async function submitGrievance() {
        console.log('Submitting grievance');
        try {
            // Handle voice recordings submission
            const formData = new FormData();
            
            // Use existing grievance ID if available
            if (state.grievanceId) {
                console.log('Using existing grievance ID:', state.grievanceId);
                formData.append('grievance_id', state.grievanceId);
            } else {
                // Create a new ID if we don't have one yet
                console.log('No grievance ID found, creating one');
                const newId = await createGrievance();
                console.log('Created new grievance ID for submission:', newId);
                formData.append('grievance_id', newId);
            }
            
            // Log how many audio blobs we have
            console.log('Audio blobs to submit:', Object.keys(state.audioBlobs).length);
            
            // Add all audio recordings with database field names
            Object.entries(state.audioBlobs).forEach(([key, blob]) => {
                if (blob) {
                    // Use database field names for each recording to match backend
                    const fieldNameMap = {
                        'step1': 'grievance_details',
                        'step2a': 'user_full_name',
                        'step2b': 'user_contact_phone',
                        'step3a': 'user_municipality',
                        'step3b': 'user_village',
                        'step3c': 'user_address'
                    };
                    
                    const fileName = fieldNameMap[key] || key;
                    
                    console.log(`Adding blob for ${key} as ${fileName}.webm (size: ${blob.size} bytes)`);
                    formData.append(`${fileName}.webm`, blob);
                }
            });

            const submissionUrl = config.api.baseUrl + config.api.endpoints.submitGrievance;
            console.log('Submitting voice recordings to:', submissionUrl);
            
            try {
                const response = await fetch(submissionUrl, {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    console.error('Voice submission failed with status:', response.status, response.statusText);
                    const errorText = await response.text();
                    console.error('Error response:', errorText);
                    throw new Error(config.errors.submission + ' (Status: ' + response.status + ')');
                }
                
                console.log('Voice submission successful, parsing response');
                const data = await response.json();
                console.log('Voice submission response data:', data);
                
                // Use the grievance ID returned from the server or the one we already have
                const grievanceId = data.grievance_id || data.id || state.grievanceId;
                console.log('Using grievance ID for subsequent uploads:', grievanceId);
                
                // After successful voice submission, upload any attached files
                if (state.selectedFiles && state.selectedFiles.length > 0) {
                    await uploadFiles(grievanceId);
                } else {
                    console.log('No files selected for upload');
                }
                
                // Set current step to result before showing the result screen
                state.currentStep = 'result';
                
                // Hide all step containers
                Object.keys(stepContainers).forEach(id => {
                    stepContainers[id].hidden = (id !== 'result');
                });
                
                // Display the grievance ID
                if (grievanceId) {
                    const idElement = document.getElementById('grievanceId');
                    if (idElement) {
                        const spanElement = idElement.querySelector('span');
                        if (spanElement) {
                            spanElement.textContent = grievanceId;
                            idElement.hidden = false;
                        } else {
                            idElement.textContent = 'Your grievance ID is: ' + grievanceId;
                            idElement.hidden = false;
                        }
                    }
                }
                
                const resultMessage = document.getElementById('resultMessage');
                if (resultMessage) {
                    resultMessage.textContent = 'Your voice recordings have been received.';
                    if (state.selectedFiles && state.selectedFiles.length > 0) {
                        resultMessage.textContent += ' Your files have also been uploaded.';
                    }
                }
                
            } catch (fetchError) {
                console.error('Fetch error during submission:', fetchError);
                throw fetchError;
            }
            
        } catch (err) {
            console.error('Submission error:', err);
            showError(err.message || config.errors.submission);
        }
    }

    // Upload files after voice recording submission
    async function uploadFiles(grievanceId) {
        if (!state.selectedFiles || state.selectedFiles.length === 0) {
            console.log('No files to upload');
            return;
        }
        
        console.log(`Uploading ${state.selectedFiles.length} files for grievance ID ${grievanceId}`);
        
        try {
            const formData = new FormData();
            formData.append('grievance_id', grievanceId);
            
            // Add all files to the FormData
            state.selectedFiles.forEach((file, index) => {
                console.log(`Adding file to upload: ${file.name} (${file.size} bytes)`);
                formData.append('files[]', file);
            });
            
            // Use the accessibleFileUpload endpoint from config
            const uploadUrl = config.api.baseUrl + config.api.endpoints.accessibleFileUpload;
            console.log('Uploading files to:', uploadUrl);
            
            const response = await fetch(uploadUrl, {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                console.error('File upload failed with status:', response.status, response.statusText);
                const errorText = await response.text();
                console.error('Error response:', errorText);
                throw new Error('File upload failed (Status: ' + response.status + ')');
            }
            
            const data = await response.json();
            console.log('File upload successful:', data);
            
            return data;
        } catch (error) {
            console.error('Error uploading files:', error);
            // Don't throw the error - we still want to show the success screen for the voice recording
        }
    }

    // Utility functions
    function showError(message) {
        console.error('Showing error:', message);
        
        // Hide all other steps
        Object.keys(stepContainers).forEach(id => {
            stepContainers[id].hidden = true;
        });
        
        // Show result container with error
        document.getElementById('result').hidden = false;
        document.getElementById('resultMessage').textContent = message;
        document.getElementById('resultMessage').style.color = 'var(--error-color)';
        console.log(`Would have announced error: ${message}`);
    }

    function toggleFontSize() {
        state.fontSize = state.fontSize === config.accessibility.fontSize.max ? 
            config.accessibility.fontSize.default : 
            Math.min(state.fontSize + config.accessibility.fontSize.step, config.accessibility.fontSize.max);
        accessibility.setFontSize(state.fontSize);
        
        // Log instead of announcing font size change
        const fontSizeMessage = state.fontSize === config.accessibility.fontSize.default ? 
            "Font size reset to default." : "Font size increased.";
        console.log(`Would have announced: ${fontSizeMessage}`);
    }

    function toggleContrast() {
        accessibility.toggleContrast();
        
        // Log instead of announcing contrast change
        const contrastMode = document.body.classList.contains('high-contrast');
        const contrastMessage = contrastMode ? 
            "High contrast mode enabled." : "Normal contrast mode enabled.";
        console.log(`Would have announced: ${contrastMessage}`);
    }

    // Start the application
    console.log('Accessible interface: Starting application');
    init();
}); 