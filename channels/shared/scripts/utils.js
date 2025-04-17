/**
 * Shared utilities for Nepal Chatbot channels
 */

// Get element by ID shorthand
const $ = id => document.getElementById(id);

// Accessibility utilities
const accessibility = {
    // Toggle high contrast mode
    toggleContrast: function() {
        document.body.classList.toggle('high-contrast');
        return document.body.classList.contains('high-contrast');
    },
    
    // Set font size
    setFontSize: function(size) {
        document.documentElement.style.fontSize = size + 'px';
    },
    
    // Save preference to localStorage
    savePreference: function(key, value) {
        localStorage.setItem(key, value);
    },
    
    // Load preference from localStorage
    loadPreference: function(key, defaultValue) {
        const value = localStorage.getItem(key);
        return value !== null ? value : defaultValue;
    }
};

// API utilities
const api = {
    // Base fetch with error handling
    fetch: async function(url, options = {}) {
        try {
            const response = await fetch(url, options);
            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    },
    
    // Upload files
    uploadFiles: async function(url, files) {
        const formData = new FormData();
        Object.entries(files).forEach(([key, file]) => {
            formData.append(key, file);
        });
        
        return this.fetch(url, {
            method: 'POST',
            body: formData
        });
    }
};

// Export utilities
window.nepalChatbot = {
    $,
    accessibility,
    api
}; 