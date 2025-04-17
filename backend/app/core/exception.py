# backend/core/exception.py

class AssistantBaseException(Exception):
    """Base exception for the voice assistant application."""
    def __init__(self, message: str, original_exception: Exception | None = None):
        super().__init__(message)
        self.original_exception = original_exception
        self.message = message # Store message for easier access

    def __str__(self):
        if self.original_exception:
            return f"{self.message} (Original: {type(self.original_exception).__name__}: {str(self.original_exception)})"
        return self.message

# --- Configuration & Request Errors ---
class ConfigurationError(AssistantBaseException):
    """Raised for missing or invalid configuration."""
    pass

class InvalidRequestError(AssistantBaseException):
    """Raised for invalid input data from the API request."""
    pass

# --- External Service Errors ---
class TranscriptionError(AssistantBaseException):
    """Raised when Google Speech-to-Text fails."""
    pass

class TranslationError(AssistantBaseException):
    """Raised when Google Translation API fails."""
    pass

class NluError(AssistantBaseException):
    """Raised when the Gemini interaction or parsing fails."""
    pass

class SynthesisError(AssistantBaseException):
    """Raised when Google Text-to-Speech fails."""
    pass

class NavigationError(AssistantBaseException):
    """Raised for errors related to Google Maps or navigation logic."""
    pass

class CommunicationError(AssistantBaseException):
    """Raised for errors related to SMS/Call services (e.g., Twilio)."""
    pass

class SafetyError(AssistantBaseException):
    """Raised for errors in safety-related operations."""
    pass

# --- Internal Logic Errors ---
class StateError(AssistantBaseException):
    """Raised when an operation is attempted in an invalid state (e.g., no order context)."""
    pass