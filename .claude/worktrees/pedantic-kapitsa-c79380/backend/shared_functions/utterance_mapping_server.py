"""
Server-side utterance mapping for multi-language support.
This is separate from the Rasa actions utterance mapping.
"""

def get_utterance(module, function, message_id, language='en'):
    """
    Get a user-friendly server-side message in the specified language.
    Fallback to English if translation not available.
    
    Args:
        module: The module requesting the utterance
        function: The function requesting the utterance
        message_id: The specific message ID
        language: The language code (default: 'en')
        
    Returns:
        A user-friendly message in the requested language
    """
    # Default English messages
    default_messages = {
        'file_server': {
            'upload_files': {
                1: "No grievance ID provided",
                2: "Cannot upload files for pending grievance",
                3: "No files provided",
                4: "No files selected",
                5: "Invalid file type",
                6: "An error occurred while uploading files"
            },
            'get_files': {
                1: "Error retrieving files"
            },
            'download_file': {
                1: "File not found"
            }
        }
    }
    
    # Return the requested message or a generic error if not found
    try:
        return default_messages.get(module, {}).get(function, {}).get(message_id, "An error occurred")
    except Exception:
        return "An error occurred" 

