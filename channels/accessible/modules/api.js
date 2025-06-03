/**
 * API Module - Handles all API interactions
 */
export default function createAPIModule() {
    return {
        baseUrl: '',
        endpoints: {},
        
        init: function() {
            // Set default values if APP_CONFIG is not available
            this.baseUrl = (typeof APP_CONFIG !== 'undefined' && APP_CONFIG.api?.baseUrl) ? APP_CONFIG.api.baseUrl : '';
            this.endpoints = (typeof APP_CONFIG !== 'undefined' && APP_CONFIG.api?.endpoints) ? APP_CONFIG.api.endpoints : {};
            
            // Add configurable submitGrievance endpoint
            if (!this.endpoints.submitGrievance) {
                this.endpoints.submitGrievance = '/accessible-api/submit-grievance';
            }
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
         * Submits the main grievance (user info + recordings)
         * @param {Object} userInfo - User info fields
         * @param {Object} recordings - Map of recordingType -> Blob
         * @param {FormData} [additionalFormData] - Optional FormData with additional fields like grievance_id, user_id, language_code
         * @returns {Promise}
         */
        submitGrievance: async function(userInfo, recordings, additionalFormData) {
            const formData = new FormData();
            
            // Add user info fields
            Object.entries(userInfo).forEach(([key, value]) => {
                formData.append(key, value);
            });
            
            // Add additional form data if provided (grievance_id, user_id, language_code, etc.)
            if (additionalFormData && additionalFormData instanceof FormData) {
                for (const [key, value] of additionalFormData.entries()) {
                    formData.append(key, value);
                }
            }
            
            // Add all recordings as separate files
            Object.entries(recordings).forEach(([type, blob]) => {
                formData.append(type, blob, `${type}.webm`);
                // Add duration if available and valid
                if (blob.duration && isFinite(blob.duration) && blob.duration > 0) {
                    formData.append(`duration`, Math.round(blob.duration));
                }
            });
            
            // Debug: Log what we're sending
            console.log('Submitting grievance with FormData contents:');
            for (const [key, value] of formData.entries()) {
                if (value instanceof File || value instanceof Blob) {
                    console.log(`- ${key}: ${value.constructor.name} (${value.size} bytes)`);
                } else {
                    console.log(`- ${key}: ${value}`);
                }
            }
            
            // POST to /submit-grievance
            return this.request(this.endpoints.submitGrievance, {
                method: 'POST',
                body: formData
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
        },
        
        /**
         * Generates grievance_id and user_id using centralized logic
         * @param {string} province - Province code (e.g., 'KO', 'Koshi')
         * @param {string} district - District code (e.g., 'JH', 'Jhapa')
         * @returns {Promise} - Promise with generated IDs
         */
        generateIds: async function(province, district) {
            return this.request(this.endpoints.generateIds, {
                method: 'POST',
                body: JSON.stringify({
                    province: province,
                    district: district
                })
            });
        }
    };
} 