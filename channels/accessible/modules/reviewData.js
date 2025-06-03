/**
 * Review Data Module - Manages data collection from websocket events
 */
export default function createReviewDataModule(socket, UIModule, RecordingModule, GrievanceModule) {
    return {
        reviewData: {},
        taskCompletionStatus: {},
        firstSuccessTime: null,
        summaryTimer: null,
        updateTimer: null,
        isCollectingData: false,
        
        // Field mapping: websocket field name -> review element ID
        fieldMapping: {
            'grievance_details': 'grievanceDetailsReview',
            'grievance_summary': 'grievanceSummaryReview', 
            'grievance_categories': 'grievanceCategoriesReview',
            'user_full_name': 'userNameReview',
            'user_contact_phone': 'userPhoneReview',
            'user_municipality': 'userMunicipalityReview',
            'user_village': 'userVillageReview',
            'user_address': 'userAddressReview'
        },
        
        init: function() {
            // Listen for task completion events
            socket.on('status_update:llm_processor', this.handleTaskCompletion.bind(this));
            console.log('✅ ReviewDataModule initialized');
        },
        
        handleTaskCompletion: function(data) {
            console.log('[ReviewData] Received task completion:', data);
            
            if (data.status === 'completed' && data.message && data.message.result) {
                const result = data.message.result;
                
                // Start timer logic on first success
                if (!this.isCollectingData) {
                    this.startDataCollection();
                }
                
                // Store the result data
                this.storeTaskResult(result);
                
                // Update UI immediately for responsiveness
                this.updateReviewUI(result);
                
                // Check if we can enable navigation
                this.checkNavigationStatus();
            }
        },
        
        startDataCollection: function() {
            console.log('[ReviewData] Starting data collection with 3-second timer');
            this.isCollectingData = true;
            this.firstSuccessTime = Date.now();
            
            // Set 3-second timer for summary
            this.summaryTimer = setTimeout(() => {
                this.sendSummaryUpdate();
                this.startPeriodicUpdates();
            }, 3000);
        },
        
        storeTaskResult: function(result) {
            if (result.value && typeof result.value === 'object') {
                // Store each field from the result value
                Object.entries(result.value).forEach(([key, value]) => {
                    if (key !== 'field_name' && this.fieldMapping[key]) {
                        this.reviewData[key] = value;
                        this.taskCompletionStatus[key] = 'completed';
                        console.log(`[ReviewData] Stored ${key}: ${value}`);
                    }
                });
                
                // Handle categories specially (they come as an array)
                if (result.value.grievance_categories) {
                    this.reviewData.grievance_categories = result.value.grievance_categories;
                    this.taskCompletionStatus.grievance_categories = 'completed';
                }
            }
        },
        
        updateReviewUI: function(result) {
            if (!result.value) return;
            
            Object.entries(result.value).forEach(([fieldName, fieldValue]) => {
                const elementId = this.fieldMapping[fieldName];
                if (elementId) {
                    const element = document.getElementById(elementId);
                    if (element) {
                        if (fieldName === 'grievance_categories' && Array.isArray(fieldValue)) {
                            // Handle categories as a list
                            element.innerHTML = fieldValue.map(cat => `<span class="category-tag">${cat}</span>`).join(' ');
                        } else {
                            element.textContent = fieldValue || '';
                        }
                        console.log(`[ReviewData] Updated UI element ${elementId} with: ${fieldValue}`);
                    }
                }
            });
        },
        
        checkNavigationStatus: function() {
            // Check if we have at least one contact_info or classification task completed
            const hasContactInfo = ['user_full_name', 'user_contact_phone', 'user_municipality', 'user_village', 'user_address']
                .some(field => this.taskCompletionStatus[field] === 'completed');
                
            const hasClassification = ['grievance_summary', 'grievance_categories']
                .some(field => this.taskCompletionStatus[field] === 'completed');
            
            if (hasContactInfo || hasClassification) {
                this.enableReviewNavigation();
            }
        },
        
        enableReviewNavigation: function() {
            const { step, window } = UIModule.getCurrentWindow();
            if (step === 'attachments') {
                const nextBtn = document.querySelector('#attachments-attachments .nav-btn[data-action="next"]');
                if (nextBtn) {
                    nextBtn.disabled = false;
                    nextBtn.style.display = '';
                    console.log('[ReviewData] Enabled navigation to review step');
                    
                    // Update button states
                    UIModule.updateButtonStates({
                        isRecording: RecordingModule.isRecording,
                        hasRecording: RecordingModule.hasAnyRecording(),
                        isSubmitting: GrievanceModule.isSubmitting
                    });
                }
            }
        },
        
        sendSummaryUpdate: function() {
            console.log('[ReviewData] Sending summary update after 3 seconds');
            console.log('[ReviewData] Collected data:', this.reviewData);
            console.log('[ReviewData] Task status:', this.taskCompletionStatus);
            
            // Emit custom event for other modules
            window.dispatchEvent(new CustomEvent('reviewDataReady', { 
                detail: { 
                    data: this.reviewData,
                    completionStatus: this.taskCompletionStatus,
                    timestamp: Date.now()
                } 
            }));
        },
        
        startPeriodicUpdates: function() {
            console.log('[ReviewData] Starting periodic 1-second updates for new arrivals');
            this.updateTimer = setInterval(() => {
                // Check if we have new data since last update
                // For now, just log - could add more sophisticated change detection
                console.log('[ReviewData] Periodic update check');
            }, 1000);
        },
        
        stopDataCollection: function() {
            if (this.summaryTimer) {
                clearTimeout(this.summaryTimer);
                this.summaryTimer = null;
            }
            if (this.updateTimer) {
                clearInterval(this.updateTimer);
                this.updateTimer = null;
            }
            this.isCollectingData = false;
            console.log('[ReviewData] Stopped data collection');
        },
        
        // Public method to get current review data
        getReviewData: function() {
            return {
                data: this.reviewData,
                completionStatus: this.taskCompletionStatus
            };
        },
        
        // Public method to reset data (for new grievance)
        reset: function() {
            this.reviewData = {};
            this.taskCompletionStatus = {};
            this.stopDataCollection();
            console.log('[ReviewData] Reset review data');
        }
    };
} 