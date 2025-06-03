/**
 * Accessibility Module - Handles accessibility features
 */
export default function createAccessibilityModule(SpeechModule) {
    return {
        highContrast: false,
        fontSize: null,
        fontSizeOptions: null,
        
        init: function() {
            // Set default font size options if APP_CONFIG is not available
            this.fontSizeOptions = (typeof APP_CONFIG !== 'undefined' && APP_CONFIG.accessibility?.fontSize) 
                ? APP_CONFIG.accessibility.fontSize 
                : {
                    default: 16,
                    max: 24,
                    step: 2
                };
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
                        if (SpeechModule && SpeechModule.speak) {
                            SpeechModule.speak("Font size reset to default");
                        }
                    } else {
                        // Announce for screen readers
                        if (SpeechModule && SpeechModule.speak) {
                            SpeechModule.speak("Font size increased");
                        }
                    }
                });
            }
            
            if (contrastBtn) {
                contrastBtn.addEventListener('click', () => {
                    this.toggleContrast();
                    const message = this.highContrast ? 
                        "High contrast mode enabled" : 
                        "High contrast mode disabled";
                    if (SpeechModule && SpeechModule.speak) {
                        SpeechModule.speak(message);
                    }
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
} 