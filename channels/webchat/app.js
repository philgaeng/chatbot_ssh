// Import configurations
import { WEBSOCKET_CONFIG, SESSION_CONFIG, UI_CONFIG, FILE_UPLOAD_CONFIG } from './config.js';

// Make FILE_UPLOAD_CONFIG globally available for the file upload function
window.FILE_UPLOAD_CONFIG = FILE_UPLOAD_CONFIG;

// DOM Elements
let chatWidget;
let chatLauncher;
let closeButton;
let messageForm;
let messageInput;
let messages;
let fileInput;
let attachmentButton;

// Session and State Variables
let socket;
let sessionConfirmed = false;
let sessionStarted = false;
let messageRetryCount = 0;
const MAX_RETRIES = 3;
const RETRY_DELAY = 500; // 500ms

// Global state
window.grievanceId = null;
window.currentRetryTimer = null;
window.hasReceivedResponse = false;
window.introductionSent = false;
window.introductionWindowTimer = null;
window.sessionInitialized = false;
window.lastBotMessageText = '';
window.lastBotQuickReplies = null;

// File type constants
const FILE_TYPES = {
    IMAGE: {
        extensions: ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'heic', 'heif'],
        maxSize: 5 * 1024 * 1024 // 5MB
    },
    VIDEO: {
        extensions: ['mp4', 'mov', 'avi', 'mkv', 'wmv', 'flv', 'webm', 'm4v'],
        maxSize: 50 * 1024 * 1024 // 50MB
    },
    AUDIO: {
        extensions: ['mp3', 'wav', 'ogg', 'm4a', 'aac', 'wma', 'flac', 'webm'],
        maxSize: 10 * 1024 * 1024 // 10MB
    },
    DOCUMENT: {
        extensions: ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'rtf', 'csv', 'odt', 'ods', 'odp'],
        maxSize: 2 * 1024 * 1024 // 2MB
    },
    ARCHIVE: {
        extensions: ['zip', 'rar', '7z', 'tar', 'gz'],
        maxSize: 20 * 1024 * 1024 // 20MB
    }
};

// Function to get URL parameters
function getUrlParams() {
    const params = new URLSearchParams(window.location.search);
    return {
        province: params.get('province'),
        district: params.get('district')
    };
}

// Create a temporary session ID
const tempSessionId = 'temp_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

// Make getSessionId available globally
window.getSessionId = function() {
    if (socket && socket.connected) {
        return socket.id;
    }
    const storage = localStorage;
    const storageKey = SESSION_CONFIG.STORAGE_KEY;
    return storage.getItem(storageKey) || tempSessionId;
};

// Initialize WebSocket connection
function initializeWebSocket() {
    socket = io(WEBSOCKET_CONFIG.URL, {
        path: WEBSOCKET_CONFIG.OPTIONS.path,
        transports: WEBSOCKET_CONFIG.OPTIONS.transports,
        reconnection: true,
        reconnectionAttempts: 10,
        reconnectionDelay: 2000,
        pingTimeout: 120000,
    });

    // Make socket available globally
    window.socket = socket;

    setupSocketEventHandlers();
}

// Set up WebSocket event handlers
function setupSocketEventHandlers() {
    socket.on('connect', () => {
        console.log('Socket connected with ID:', socket.id);
        const storage = localStorage;
        const storageKey = SESSION_CONFIG.STORAGE_KEY;
        storage.setItem(storageKey, socket.id);
        
        // Reset session state
        sessionConfirmed = false;
        sessionStarted = false;
        messageRetryCount = 0;
        
        // Request a session
        socket.emit('session_request', { session_id: socket.id });
        console.log('Sent session_request with ID:', socket.id);
    });

    socket.on('session_confirm', () => {
        sessionConfirmed = true;
        console.log('Session confirmed with ID:', socket.id);
        
        setTimeout(() => {
            sessionStarted = true;
            console.log('Session fully initialized, sending initial message...');
            if (!window.sessionInitialized) {
                sendIntroduceMessage();
            }
        }, 1000);
    });

    socket.on('bot_uttered', handleBotResponse);

    // Error handling
    socket.on('error', (error) => {
        console.error('Socket error:', error);
    });

    socket.on('connect_error', (error) => {
        console.error('Connection error:', error);
        appendMessage('Connection error. Please try again later.', 'received');
    });

    socket.on('connect_timeout', () => {
        console.error('Connection timeout');
        appendMessage('Connection timed out. Please try again later.', 'received');
    });

    socket.on('reconnect_attempt', (attemptNumber) => {
        console.log('Reconnection attempt:', attemptNumber);
    });

    socket.on('reconnect', (attemptNumber) => {
        console.log('Reconnected after', attemptNumber, 'attempts');
    });

    socket.on('reconnect_error', (error) => {
        console.error('Reconnection error:', error);
    });

    socket.on('reconnect_failed', () => {
        console.error('Reconnection failed');
        appendMessage('Unable to reconnect. Please refresh the page.', 'received');
    });

    socket.on('user_uttered', (message) => {
        console.log('📩 User message sent:', message);
    });
    socket.on('file_status_update', (data) => {
        console.log('File status update:', data);
    });
}

// Handle bot responses
function handleBotResponse(response) {
    console.log('Bot uttered:', response);
    
    window.lastBotQuickReplies = null;
    
    // Clear timers
    if (window.currentRetryTimer) {
        clearTimeout(window.currentRetryTimer);
        window.currentRetryTimer = null;
    }
    
    if (window.introductionWindowTimer) {
        clearTimeout(window.introductionWindowTimer);
        window.introductionWindowTimer = null;
    }
    
    messageRetryCount = 0;
    window.hasReceivedResponse = true;
    
    // Extract and set grievance ID if present
    const grievanceId = extractGrievanceId(response);
    if (grievanceId) {
        console.log('Setting grievance ID:', grievanceId);
        window.grievanceId = grievanceId;
    }
    
    // Handle task status updates
    if (response.task_status) {
        handleTaskStatus(response.task_status);
        return;
    }
    
    // Handle the response text
    if (response.text && !response.custom?.hidden) {
        appendMessage(response.text, 'received');
        window.lastBotMessageText = response.text;
    }

    // Handle quick replies
    if (response.quick_replies) {
        appendQuickReplies(response.quick_replies);
        window.lastBotQuickReplies = response.quick_replies;
    }
    
    if (response.attachment) {
        console.log('Attachment received:', response.attachment);
    }
}

// Handle task status updates
function handleTaskStatus(taskStatus) {
    const { task_id, status, progress, result, error } = taskStatus;
    
    // Create or update task status message
    let statusElement = document.getElementById(`task-status-${task_id}`);
    if (!statusElement) {
        statusElement = document.createElement('div');
        statusElement.id = `task-status-${task_id}`;
        statusElement.className = 'task-status';
        document.querySelector('.chat-messages').appendChild(statusElement);
    }
    
    // Update status message
    let statusMessage = '';
    switch (status) {
        case 'PENDING':
            statusMessage = 'Processing...';
            break;
        case 'STARTED':
            statusMessage = progress ? `Processing: ${progress}%` : 'Processing...';
            break;
        case 'SUCCESS':
            statusMessage = 'Completed successfully';
            if (result) {
                // Handle successful result
                if (result.grievance_id) {
                    window.grievanceId = result.grievance_id;
                }
                if (result.message) {
                    appendMessage(result.message, 'received');
                }
            }
            break;
        case 'FAILURE':
            statusMessage = `Failed: ${error || 'Unknown error'}`;
            break;
        default:
            statusMessage = `Status: ${status}`;
    }
    
    statusElement.textContent = statusMessage;
    
    // Remove status message after success/failure
    if (status === 'SUCCESS' || status === 'FAILURE') {
        setTimeout(() => {
            statusElement.remove();
        }, 5000);
    }
}

// Extract grievance ID from bot response
function extractGrievanceId(response) {
    if (response.json_message?.grievance_id) {
        return response.json_message.grievance_id;
    }
    if (response.metadata?.grievance_id) {
        return response.metadata.grievance_id;
    }
    if (response.grievance_id) {
        return response.grievance_id;
    }
    if (response.text) {
        const grievanceMatch = response.text.match(/Your grievance ID is (GR-[A-Z0-9-]+)/);
        if (grievanceMatch) {
            console.log('Grievance ID found in text:', grievanceMatch[1]);
            return grievanceMatch[1];
        }
    }
    return null;
}

// Safe message sending function
window.safeSendMessage = function(message, additionalData = {}) {
    if (!socket.connected) {
        console.error('Socket not connected, cannot send message');
        return false;
    }
    
    const payload = {
        message: message,
        session_id: socket.id
    };
    
    if (Object.keys(additionalData).length > 0) {
        if (additionalData.file_references) {
            payload.file_references = additionalData.file_references;
            payload.metadata = { 
                file_references: additionalData.file_references 
            };
        } else {
            payload.metadata = additionalData;
        }
    }
    
    console.log('Sending message:', payload);
    socket.emit('user_uttered', payload);
    return true;
};

// Send introduction message
function sendIntroduceMessage() {
    if (!sessionStarted) {
        console.log('Waiting for session to be fully initialized...');
        return;
    }
    
    if (window.introductionSent) {
        console.log('Introduction already sent, skipping...');
        return;
    }
    
    const { province, district } = getUrlParams();
    const initialMessage = province && district 
        ? `/introduce{"province": "${province}", "district": "${district}"}`
        : '/introduce';
    
    console.log('Preparing to send initial message:', initialMessage);
    
    if (window.safeSendMessage(initialMessage)) {
        console.log('Initial message sent successfully');
        window.introductionSent = true;
        
        if (!window.hasReceivedResponse) {
            window.introductionWindowTimer = setTimeout(() => {
                console.log('Introduction window closed - no more retries allowed');
                if (window.currentRetryTimer) {
                    clearTimeout(window.currentRetryTimer);
                    window.currentRetryTimer = null;
                }
                if (messageRetryCount >= MAX_RETRIES) {
                    appendMessage('Sorry, there seems to be a connection issue. Please try again.', 'received');
                }
            }, 3000);
            
            const retryTimer = setTimeout(() => {
                if (messageRetryCount < MAX_RETRIES && !window.hasReceivedResponse) {
                    messageRetryCount++;
                    console.log(`No response received, retrying (${messageRetryCount}/${MAX_RETRIES})...`);
                    window.introductionSent = false;
                    sendIntroduceMessage();
                }
            }, RETRY_DELAY);
            
            window.currentRetryTimer = retryTimer;
        }
    }
}

// Initialize the chat application
function initializeChat() {
    // Get DOM elements
    chatWidget = document.getElementById('chat-widget');
    chatLauncher = document.getElementById('chat-launcher');
    closeButton = document.querySelector('.close-button');
    messageForm = document.getElementById('form');
    messageInput = document.getElementById('message-input');
    fileInput = document.getElementById('file-input');
    attachmentButton = document.getElementById('attachment-button');
    messages = document.getElementById('messages');

    // Initialize chat widget visibility
    chatWidget.style.display = 'none';
    chatLauncher.style.display = 'flex';

    // Initialize WebSocket
    initializeWebSocket();

    // Set up event listeners
    setupEventListeners();
}

// Set up UI event listeners
function setupEventListeners() {
    chatLauncher.addEventListener('click', () => {
        chatWidget.style.display = 'flex';
        chatLauncher.style.display = 'none';
        messageInput.focus();
    });

    closeButton.addEventListener('click', () => {
        chatWidget.style.display = 'none';
        chatLauncher.style.display = 'flex';
    });

    // File attachment handling
    attachmentButton.addEventListener('click', () => {
        fileInput.click();
    });

    // Form submission
    messageForm.addEventListener('submit', handleMessageSubmit);

    // File input change
    fileInput.addEventListener('change', handleFileSelection);

    // Add auto-resize functionality to message input
    messageInput.addEventListener('input', function() {
        // Reset height to auto to get the correct scrollHeight
        this.style.height = 'auto';
        // Set new height based on scrollHeight, but cap it at max-height via CSS
        this.style.height = Math.min(this.scrollHeight, parseInt(getComputedStyle(this).maxHeight)) + 'px';
    });
}

// Handle message submission
function handleMessageSubmit(e) {
    e.preventDefault();
    const message = messageInput.value.trim();
    
    if (message) {
        appendMessage(message, 'sent');
        window.safeSendMessage(message);
        messageInput.value = '';
        messageInput.style.height = '44px';
    }
    
    // Handle file upload if files are selected
    if (selectedFiles.length > 0) {
        handleFileUpload(selectedFiles);
        selectedFiles = [];
        displayFilePreview();
    }
}

// Append message to chat
function appendMessage(msg, type) {
    const timestamp = new Date();
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', `message_${type}`);
    messageDiv.textContent = msg;
    
    const timestampDiv = document.createElement('div');
    timestampDiv.classList.add('timestamp');
    timestampDiv.textContent = formatTimestamp(timestamp);
    
    const container = document.createElement('div');
    container.appendChild(messageDiv);
    container.appendChild(timestampDiv);
    
    messages.appendChild(container);
    messages.scrollTop = messages.scrollHeight;
}

// Append quick replies
function appendQuickReplies(quickReplies) {
    const quickRepliesDiv = document.createElement('div');
    quickRepliesDiv.classList.add('quick-replies');
    
    quickReplies.forEach(reply => {
        const button = document.createElement('button');
        button.classList.add('quick-reply-button');
        button.textContent = reply.title;
        button.onclick = () => {
            appendMessage(reply.title, 'sent');
            window.safeSendMessage(reply.payload);
            messages.removeChild(quickRepliesDiv);
        };
        quickRepliesDiv.appendChild(button);
    });
    
    messages.appendChild(quickRepliesDiv);
    messages.scrollTop = messages.scrollHeight;
}

// Format timestamp
function formatTimestamp(date) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// Handle file selection
function handleFileSelection(e) {
    const files = Array.from(e.target.files);
    if (files.length > 0) {
        handleSelectedFiles(files);
    }
}

// Handle selected files
function handleSelectedFiles(files) {
    selectedFiles = [];
    
    files.forEach(file => {
        const maxFileSize = FILE_UPLOAD_CONFIG.MAX_SIZE_MB * 1024 * 1024;
        if (file.size > maxFileSize) {
            compressFile(file).then(compressedFile => {
                selectedFiles.push(compressedFile);
                displayFilePreview();
            });
        } else {
            selectedFiles.push(file);
        }
    });
    
    displayFilePreview();
}

// Display file preview
function displayFilePreview() {
    const existingPreview = document.querySelector('.file-preview');
    if (existingPreview) {
        existingPreview.remove();
    }
    
    if (selectedFiles.length === 0) return;
    
    const previewContainer = document.createElement('div');
    previewContainer.classList.add('file-preview');
    
    selectedFiles.forEach((file, index) => {
        const fileItem = document.createElement('div');
        fileItem.classList.add('file-item');
        
        const fileName = document.createElement('span');
        fileName.classList.add('file-item-name');
        fileName.textContent = file.name;
        
        const removeButton = document.createElement('button');
        removeButton.classList.add('file-item-remove');
        removeButton.textContent = '×';
        removeButton.onclick = () => {
            selectedFiles.splice(index, 1);
            displayFilePreview();
        };
        
        fileItem.appendChild(fileName);
        fileItem.appendChild(removeButton);
        previewContainer.appendChild(fileItem);
    });
    
    messageForm.parentNode.insertBefore(previewContainer, messageForm);
}

// Compress file if needed
function compressFile(file) {
    return new Promise((resolve) => {
        if (file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.readAsDataURL(file);
            reader.onload = function(e) {
                const img = new Image();
                img.src = e.target.result;
                img.onload = function() {
                    const canvas = document.createElement('canvas');
                    const ctx = canvas.getContext('2d');
                    
                    let width = img.width;
                    let height = img.height;
                    const maxSize = 1200;
                    
                    if (width > height && width > maxSize) {
                        height = (height * maxSize) / width;
                        width = maxSize;
                    } else if (height > maxSize) {
                        width = (width * maxSize) / height;
                        height = maxSize;
                    }
                    
                    canvas.width = width;
                    canvas.height = height;
                    ctx.drawImage(img, 0, 0, width, height);
                    
                    canvas.toBlob(
                        blob => {
                            const compressedFile = new File([blob], file.name, {
                                type: file.type,
                                lastModified: file.lastModified
                            });
                            resolve(compressedFile);
                        },
                        file.type,
                        0.7
                    );
                };
            };
        } else {
            resolve(file);
        }
    });
}

// Global variables
let selectedFiles = [];

// Handle file upload
async function handleFileUpload(files) {
    console.log('Starting file upload process...', files);
    if (!window.grievanceId) {
        appendMessage('Please start a grievance submission first.', 'received');
        return;
    }

    const formData = new FormData();
    formData.append('grievance_id', window.grievanceId);
    formData.append('client_type', 'rasa');
    formData.append('session_id', socket.id);
    
    // Check for audio files
    const audioFiles = Array.from(files).filter(file => {
        const ext = file.name.split('.').pop().toLowerCase();
        return FILE_TYPES.AUDIO.extensions.includes(ext);
    });
    
    if (audioFiles.length > 0) {
        console.log('Audio files detected:', audioFiles);
        appendMessage('Voice recordings detected. These will be processed and transcribed.', 'received');
    }
    
    // Check file sizes
    const oversizedFiles = Array.from(files).filter(file => {
        const ext = file.name.split('.').pop().toLowerCase();
        for (const type of Object.values(FILE_TYPES)) {
            if (type.extensions.includes(ext)) {
                return file.size > type.maxSize;
            }
        }
        return file.size > 10 * 1024 * 1024; // Default 10MB limit
    });
    
    if (oversizedFiles.length > 0) {
        console.log('Oversized files detected:', oversizedFiles);
        appendMessage(`Some files are too large and will be skipped: ${oversizedFiles.map(f => f.name).join(', ')}`, 'received');
    }
    
    // Add valid files to form data
    const validFiles = Array.from(files).filter(file => !oversizedFiles.includes(file));
    console.log('Valid files to upload:', validFiles);
    
    for (const file of validFiles) {
        formData.append('files[]', file);
    }

    try {
        console.log('Sending file upload request...');
        const response = await fetch('/upload-files', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        console.log('File upload response:', data);
        
        if (response.ok) {
            // Show initial status
            let statusMessage = 'Files uploaded successfully. Processing...';
            if (audioFiles.length > 0) {
                statusMessage = 'Voice recordings uploaded. Processing and transcribing...';
            }
            appendMessage(statusMessage, 'received');
            
            // // Start polling for file status
            // if (data.files && data.files.length > 0) {
            //     console.log('Starting file status polling for:', data.files);
            //     pollFileStatus(data.files);
            // } else {
            //     console.warn('No file IDs received in response');
            // }
            
            // // Handle oversized files warning
            // if (data.oversized_files) {
            //     appendMessage(`Some files were too large and could not be processed: ${data.oversized_files.join(', ')}`, 'received');
            // }
        } else {
            console.error('Upload failed:', data.error);
            appendMessage(`Error uploading files: ${data.error}`, 'received');
        }
    } catch (error) {
        console.error('Error uploading files:', error);
        appendMessage('Error uploading files. Please try again.', 'received');
    }
}

// Poll file status
async function pollFileStatus(fileIds) {
    const maxAttempts = 30; // 5 minutes total (10s * 30)
    let attempts = 0;
    
    const poll = async () => {
        try {
            console.log(`Polling file status (attempt ${attempts + 1}/${maxAttempts}):`, fileIds);
            const statuses = await Promise.all(
                fileIds.map(fileId => 
                    fetch(`/file-status/${fileId}`)
                        .then(async res => {
                            if (!res.ok) {
                                // Try to parse JSON error, or fallback to a default
                                try {
                                    const data = await res.json();
                                    return data;
                                } catch {
                                    return { status: "NOT_FOUND", message: "File not found" };
                                }
                            }
                            return res.json();
                        })
                )
            );
            console.log('File status response:', statuses);
            
            // Update status for each file
            statuses.forEach((data, index) => {
                if (data.status) {
                    updateFileStatus(fileIds[index], data);
                }
            });
            
            // Check if all files are processed
            const allProcessed = statuses.every(data => 
                data.status === 'SUCCESS' || data.status === 'FAILURE'
            );
            
            if (!allProcessed && attempts < maxAttempts) {
                attempts++;
                setTimeout(poll, 10000); // Poll every 10 seconds
            } else if (!allProcessed) {
                console.log('Max polling attempts reached');
                appendMessage('File processing is taking longer than expected. You can continue with your submission.', 'received');
            }
        } catch (error) {
            console.error('Error polling file status:', error);
        }
    };
    
    // Start polling
    poll();
}

// Update file status in UI
function updateFileStatus(fileId, data) {
    const { status, progress, result, error } = data;
    
    // Get messages container
    const chatMessages = document.getElementById('messages');
    if (!chatMessages) {
        console.error('Messages container not found');
        return;
    }
    
    // Create or update file status message
    let statusElement = document.getElementById(`file-status-${fileId}`);
    if (!statusElement) {
        statusElement = document.createElement('div');
        statusElement.id = `file-status-${fileId}`;
        statusElement.className = 'file-status';
        chatMessages.appendChild(statusElement);
    }
    
    // Update status message
    let statusMessage = '';
    switch (status) {
        case 'PENDING':
            statusMessage = 'Processing files...';
            break;
        case 'STARTED':
            if (result && result.file_type === 'audio') {
                statusMessage = progress ? `Transcribing audio: ${progress}%` : 'Transcribing audio...';
            } else {
                statusMessage = progress ? `Processing files: ${progress}%` : 'Processing files...';
            }
            break;
        case 'SUCCESS':
            if (result && result.file_type === 'audio') {
                statusMessage = 'Voice recording processed and transcribed successfully';
            } else {
                statusMessage = 'Files processed successfully';
            }
            if (result) {
                // Handle successful result
                if (result.grievance_id) {
                    window.grievanceId = result.grievance_id;
                }
                if (result.message) {
                    appendMessage(result.message, 'received');
                }
            }
            break;
        case 'FAILURE':
            let errorMsg = error || 'Unknown error';
            if (result && result.file_type === 'audio') {
                statusMessage = `Failed to process voice recording: ${errorMsg}`;
            } else {
                statusMessage = `Failed to process files: ${errorMsg}`;
            }
            // Always show failure message to user
            appendMessage(statusMessage, 'received');
            console.error('Task failed:', errorMsg);
            break;
        default:
            statusMessage = `Status: ${status}`;
    }
    
    statusElement.textContent = statusMessage;
    statusElement.setAttribute('data-status', status);
    
    // Remove status element after a delay
    if (status === 'SUCCESS' || status === 'FAILURE') {
        setTimeout(() => {
            if (statusElement && statusElement.parentNode) {
                statusElement.remove();
            }
        }, 5000);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initializeChat); 
document.addEventListener('DOMContentLoaded', initializeChat); 