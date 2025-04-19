# backend/models/response.py
from pydantic import BaseModel, Field
from typing import Optional, Any, List, Dict

from .internal import RouteInfo, RouteWarning # Import for type hinting

class AssistantResponse(BaseModel):
    """Response model containing the assistant's reply for /interact."""
    session_id: str = Field(..., description="The session identifier for context")
    request_transcription: str = Field(..., description="The text transcribed from the user's input audio")
    response_text: str = Field(..., description="The generated text response from the assistant")
    response_audio: str = Field(..., description="The synthesized audio response (base64 encoded string)")
    detected_input_language: Optional[str] = Field(None, description="BCP-47 language code detected from the user's input audio")
    # Optional field to send structured data back to the frontend if needed
    action_result: Optional[Any] = Field(None, description="Structured result of the action performed (e.g., RouteInfo).")

    class Config:
        arbitrary_types_allowed = True

# --- NEW: Response model for speech detection endpoint ---
class DetectSpeechResponse(BaseModel):
    """Response model for the /assistant/detect-speech endpoint."""
    speech_detected: bool = Field(..., description="True if speech was detected in the provided audio chunk, False otherwise.")

class SafetyResponse(BaseModel):
    """Generic response model for safety endpoints."""
    status: str = Field(..., description="Status of the operation (e.g., 'acknowledged', 'failed').")
    message: str = Field(..., description="Details about the operation outcome.")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details if applicable.")

class NavigationResponse(BaseModel):
    """Generic response model for navigation endpoints."""
    status: str = Field(..., description="Status of the operation (e.g., 'route_found', 'no_reroute_needed', 'error').")
    message: Optional[str] = Field(None, description="A summary message.")
    route_info: Optional[RouteInfo] = Field(None, description="Detailed route information if applicable.")
    warnings: List[RouteWarning] = Field(default_factory=list, description="Relevant warnings.")