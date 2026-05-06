/**
 * Modify Module - Handles recording modification and transcript editing
 */
export default function createModifyModule(APIModule, UIModule) {
    return {
        currentRecordingType: null,
        
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
                if (UIModule && UIModule.showLoading) {
                    UIModule.showLoading('Loading transcript...');
                }
                
                // Get transcript from API
                const transcript = await this.getTranscript(recordingType);
                
                // Show modification interface
                this.showModifyInterface(transcript);
                
                // Store current recording type
                this.currentRecordingType = recordingType;
                
            } catch (error) {
                console.error('Error loading transcript:', error);
                if (UIModule && UIModule.showMessage) {
                    UIModule.showMessage('Failed to load transcript. Please try again.', true);
                }
            } finally {
                if (UIModule && UIModule.hideLoading) {
                    UIModule.hideLoading();
                }
            }
        },

        getTranscript: async function(recordingType) {
            // API call to get transcript
            if (!APIModule || !APIModule.request) {
                throw new Error('APIModule not available');
            }
            
            const response = await APIModule.request('/api/transcript', {
                method: 'GET',
                params: { recordingType }
            });
            return response.transcript;
        },

        saveChanges: async function() {
            try {
                const transcriptArea = document.getElementById('transcriptArea');
                if (!transcriptArea) {
                    throw new Error('Transcript area not found');
                }
                
                const transcript = transcriptArea.textContent;
                
                // Save to API
                if (!APIModule || !APIModule.request) {
                    throw new Error('APIModule not available');
                }
                
                await APIModule.request('/api/transcript', {
                    method: 'POST',
                    body: JSON.stringify({
                        recordingType: this.currentRecordingType,
                        transcript
                    })
                });
                
                // Hide interface
                this.hideModifyInterface();
                
                // Show success message
                if (UIModule && UIModule.showMessage) {
                    UIModule.showMessage('Changes saved successfully');
                }
                
            } catch (error) {
                console.error('Error saving changes:', error);
                if (UIModule && UIModule.showMessage) {
                    UIModule.showMessage('Failed to save changes. Please try again.', true);
                }
            }
        },

        showModifyInterface: function(transcript) {
            const container = document.getElementById('modifyContainer');
            const transcriptArea = document.getElementById('transcriptArea');
            
            if (!container || !transcriptArea) {
                console.error('Modify interface elements not found');
                return;
            }
            
            // Set transcript content
            transcriptArea.textContent = transcript;
            
            // Show container
            container.hidden = false;
            
            // Focus transcript area
            transcriptArea.focus();
        },

        hideModifyInterface: function() {
            const container = document.getElementById('modifyContainer');
            if (container) {
                container.hidden = true;
            }
            
            // Clear current recording type
            this.currentRecordingType = null;
        }
    };
} 