# Nepal Chatbot - Modular Architecture

## Overview

This directory contains modularized components extracted from the main `app.js` file to improve code organization, maintainability, and collaboration.

## Current Structure

```
channels/accessible/
├── app.js                    # Main application file (reduced from 3,422 to ~2,850 lines)
├── modules/
│   ├── socket.js             # WebSocket connection management
│   ├── reviewData.js         # Review data management module
│   ├── speech.js             # Text-to-speech functionality
│   ├── accessibility.js     # Accessibility features (contrast, font size)
│   └── README.md            # This file
```

## Extracted Modules

### ✅ **ReviewDataModule** (`reviewData.js`)
- **Purpose**: Manages data collection from websocket events
- **Dependencies**: `socket`, `UIModule`, `RecordingModule`, `GrievanceModule`
- **Features**: Real-time event handling, 3-second timer logic, field mapping, progressive navigation

### ✅ **SpeechModule** (`speech.js`)
- **Purpose**: Handles text-to-speech functionality
- **Dependencies**: None (self-contained)
- **Features**: Voice synthesis, auto-read toggle, speech rate control, screen reader announcements

### ✅ **AccessibilityModule** (`accessibility.js`)
- **Purpose**: Handles accessibility features
- **Dependencies**: `SpeechModule`
- **Features**: High contrast mode, font size adjustment, preference persistence

### ✅ **SocketModule** (`socket.js`)
- **Purpose**: WebSocket connection management
- **Dependencies**: None (self-contained)
- **Features**: Socket.IO connection, room management, event logging

## Module Design Pattern

Each module follows this factory pattern:

```javascript
export default function createModuleName(dependencies) {
    return {
        // Module properties
        moduleProperty: {},
        
        // Module methods
        init: function() {
            // Initialization logic
        },
        
        // Public API methods
        publicMethod: function() {
            // Implementation
        }
    };
}
```

## Benefits Achieved

### 1. **Separation of Concerns**
- Each module handles a specific functionality
- Clear boundaries between different features
- Easier to understand and debug individual components

### 2. **Dependency Injection**
- Modules receive their dependencies as parameters
- Testable and flexible design
- No global state dependencies

### 3. **Maintainability**
- Smaller, focused files are easier to work with
- Changes to one module don't affect others
- Clear module interfaces

### 4. **Collaboration**
- Multiple developers can work on different modules
- Reduced merge conflicts
- Better code review process

### 5. **File Size Reduction**
- **app.js**: Reduced from 3,422 lines to ~2,850 lines (16% reduction)
- Individual modules are easier to navigate and understand

## Integration in app.js

Modules are imported and initialized in `app.js`:

```javascript
import createReviewDataModule from './modules/reviewData.js';
import createSpeechModule from './modules/speech.js';
import createAccessibilityModule from './modules/accessibility.js';

// During initialization
SpeechModule = createSpeechModule();
AccessibilityModule = createAccessibilityModule(SpeechModule);
ReviewDataModule = createReviewDataModule(socket, UIModule, RecordingModule, GrievanceModule);

// Initialize all modules
SpeechModule.init();
AccessibilityModule.init();
ReviewDataModule.init();
```

## Future Modules to Extract

1. **UIModule** - User interface management  
2. **RecordingModule** - Audio recording functionality
3. **GrievanceModule** - Grievance submission logic
4. **FileUploadModule** - File upload handling
5. **APIModule** - API communication layer
6. **EventModule** - Event handling and listeners

## Migration Guidelines

When extracting a new module:

1. Create a new file in `modules/` directory
2. Use the factory pattern with dependency injection
3. Update `app.js` to import and initialize the module
4. Remove the old code from `app.js`
5. Test the module independently
6. Update this README with the new module

## Testing Strategy

Each module should be testable in isolation:

```javascript
// Example test setup
const mockSocket = { on: jest.fn() };
const mockUIModule = { getCurrentWindow: jest.fn() };
const reviewModule = createReviewDataModule(mockSocket, mockUIModule);
```

## Performance Impact

- **Positive**: Smaller individual files load faster
- **Positive**: Better browser caching of individual modules
- **Positive**: Easier to identify performance bottlenecks
- **Neutral**: ES6 module imports have minimal overhead 