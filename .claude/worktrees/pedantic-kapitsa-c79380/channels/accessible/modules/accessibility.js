/**
 * Accessibility Module - Handles accessibility features
 */
export default function createAccessibilityModule(SpeechModule) {
    return {
        highContrast: false,
        fontSize: null,
        fontSizeOptions: null,
        
        init: function() {
            console.log('[Accessibility] Starting initialization...');
            
            // Set default font size options if APP_CONFIG is not available
            this.fontSizeOptions = (typeof APP_CONFIG !== 'undefined' && APP_CONFIG.accessibility?.fontSize) 
                ? APP_CONFIG.accessibility.fontSize 
                : {
                    default: 16,
                    min: 14,
                    max: 28,      // Increased from 24
                    step: 2
                };
            this.fontSize = this.fontSizeOptions.default;
            
            this.loadPreferences();
            console.log('[Accessibility] Loaded preferences:', { highContrast: this.highContrast, fontSize: this.fontSize });
            
            this.setupAccessibilityControls();
            this.applySettings();
            
            console.log('[Accessibility] Initialization complete');
        },
        
        toggleContrast: function() {
            this.highContrast = !this.highContrast;
            console.log('[Accessibility] High contrast toggled:', this.highContrast);
            
            document.body.classList.toggle('high-contrast', this.highContrast);
            console.log('[Accessibility] Body classes after toggle:', document.body.classList.toString());
            
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
                
                console.log('[Accessibility] Button state updated, active:', contrastBtn.classList.contains('active'));
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
            // Use CSS custom property instead of direct body style
            // This allows better cascade and inheritance
            document.documentElement.style.setProperty('--base-font-size', `${this.fontSize}px`);
            
            // Also set body font-size as fallback
            document.body.style.fontSize = `${this.fontSize}px`;
            
            // Update font size button state
            const fontBtn = document.getElementById('fontSizeBtn');
            if (fontBtn) {
                // Add active class if font size is larger than default
                fontBtn.classList.toggle('active', this.fontSize > this.fontSizeOptions.default);
                
                // Update tooltip to show current size
                const tooltip = fontBtn.querySelector('.tooltip');
                if (tooltip) {
                    tooltip.textContent = `Font Size: ${this.fontSize}px`;
                }
            }
            
            console.log(`[Accessibility] Applied font size: ${this.fontSize}px`);
        },
        
        setupAccessibilityControls: function() {
            console.log('[Accessibility] Setting up controls...');
            
            const fontBtn = document.getElementById('fontSizeBtn');
            const contrastBtn = document.getElementById('contrastToggleBtn');
            
            console.log('[Accessibility] Found elements:', { 
                fontBtn: !!fontBtn, 
                contrastBtn: !!contrastBtn 
            });
            
            if (fontBtn) {
                fontBtn.addEventListener('click', () => {
                    // Cycle through font sizes: default -> larger sizes -> back to default
                    if (this.fontSize >= this.fontSizeOptions.max) {
                        // Reset to default if we've reached the maximum
                        this.fontSize = this.fontSizeOptions.default;
                    } else {
                        // Increase font size
                        this.fontSize += this.fontSizeOptions.step;
                    }
                    
                    this.applyFontSize();
                    this.savePreferences();
                    
                    // Update tooltip and announce
                    const tooltip = fontBtn.querySelector('.tooltip');
                    if (tooltip) {
                        if (this.fontSize === this.fontSizeOptions.default) {
                            tooltip.textContent = 'Font Size: Default';
                        } else {
                            tooltip.textContent = `Font Size: ${this.fontSize}px`;
                        }
                    }
                    
                    // Announce for screen readers
                    if (SpeechModule && SpeechModule.speak) {
                        if (this.fontSize === this.fontSizeOptions.default) {
                            SpeechModule.speak("Font size reset to default");
                        } else {
                            SpeechModule.speak(`Font size set to ${this.fontSize} pixels`);
                        }
                    }
                });
            }
            
            if (contrastBtn) {
                console.log('[Accessibility] Setting up contrast button event handler...');
                
                contrastBtn.addEventListener('click', () => {
                    console.log('[Accessibility] Contrast button clicked!');
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
                console.log('[Accessibility] Initial contrast button state set, active:', this.highContrast);
                
                // Set initial tooltip text
                const contrastTooltip = contrastBtn.querySelector('.tooltip');
                if (contrastTooltip) {
                    contrastTooltip.textContent = this.highContrast ? 'Disable High Contrast' : 'Enable High Contrast';
                }
            } else {
                console.warn('[Accessibility] Contrast button not found!');
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