/**
 * Speech Module - Handles text-to-speech functionality
 */
export default function createSpeechModule() {
    return {
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
            this.announceToScreenReader(`Auto read ${this.autoRead ? 'enabled' : 'disabled'}`);
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
            this.announceToScreenReader(`Speech rate set to ${rate}`);
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
        },
        
        announceToScreenReader: function(message) {
            // Create a temporary element for screen reader announcements
            const announcement = document.createElement('div');
            announcement.setAttribute('aria-live', 'polite');
            announcement.setAttribute('aria-atomic', 'true');
            announcement.style.position = 'absolute';
            announcement.style.left = '-9999px';
            announcement.style.width = '1px';
            announcement.style.height = '1px';
            announcement.style.overflow = 'hidden';
            
            document.body.appendChild(announcement);
            announcement.textContent = message;
            
            // Remove after announcement
            setTimeout(() => {
                document.body.removeChild(announcement);
            }, 1000);
        }
    };
} 