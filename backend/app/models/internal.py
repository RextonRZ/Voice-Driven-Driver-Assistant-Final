# backend/models/internal.py
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
from datetime import datetime, timedelta

class NluIntent(str, Enum):
    """Enumeration of possible user intents recognized by NLU."""
    GET_ROUTE = "get_route"
    SEND_MESSAGE = "send_message"
    CHECK_FLOOD = "check_flood"
    ASK_GATE_INFO = "ask_gate_info"
    REROUTE_CHECK = "reroute_check" # Explicit request for reroute
    GENERAL_CHAT = "general_chat"
    ORDER_ACCEPTED_NOTIFICATION = "order_accepted_notification" # Internal trigger?
    SLEEPINESS_DETECTED = "sleepiness_detected" # Internal trigger?
    CRASH_DETECTED = "crash_detected" # Internal trigger?
    UNKNOWN = "unknown"

class NluResult(BaseModel):
    """Structured result from the NLU service."""
    intent: NluIntent = Field(..., description="The recognized intent.")
    entities: Dict[str, Any] = Field(default_factory=dict, description="Extracted entities, e.g., {'destination': '...', 'message_content': '...'}")
    confidence: Optional[float] = Field(None, description="Confidence score of the intent recognition (0.0 to 1.0).")
    fallback_response: Optional[str] = Field(None, description="A generated chat response if intent is unclear or conversational.")

# --- Conversation History ---

class ChatMessage(BaseModel):
    """Represents a single message in the conversation history."""
    role: str = Field(..., description="The role of the speaker ('user' or 'assistant')")
    # Store original user input and final assistant output for history context
    content: str = Field(..., description="The text content of the message")

class ChatHistory(BaseModel):
    """Represents the conversation history for a session."""
    session_id: str = Field(..., description="Unique identifier for the conversation session")
    messages: List[ChatMessage] = Field(default_factory=list, description="List of messages in chronological order")

# --- Navigation Related ---

class RouteWarning(BaseModel):
    """Represents a warning associated with a route (e.g., toll info, restrictions)."""
    # Routes API warnings are often strings or structured differently
    severity: Optional[str] = Field(None, description="Severity level (e.g., INFO, WARNING)") # Example field
    message: str = Field(..., description="Details about the warning/advisory.")

class RouteLocalizedValues(BaseModel):
    """Localized text values for distance and duration."""
    distance: Optional[str] = None
    duration: Optional[str] = None
    static_duration: Optional[str] = None # Duration without traffic

class RouteInfo(BaseModel):
    """Structured information about a calculated route using Routes API."""
    duration: Optional[timedelta] = Field(None, description="Estimated travel time including traffic (as timedelta).")
    distance_meters: Optional[int] = Field(None, description="Total distance in meters.")
    polyline_encoded: Optional[str] = Field(None, description="Encoded polyline for the entire route.")
    # Add legs if step-by-step is needed later
    # legs: List[RouteLeg] = Field(default_factory=list)
    warnings: List[RouteWarning] = Field(default_factory=list, description="List of warnings/advisories for the route.")
    localized_values: Optional[RouteLocalizedValues] = Field(None, description="Localized text for duration/distance.")
    # Fields derived in the service layer for easier use:
    duration_text: Optional[str] = Field(None, description="User-friendly duration text (e.g., '25 mins').")
    distance_text: Optional[str] = Field(None, description="User-friendly distance text (e.g., '15.3 km').")
    start_address: Optional[str] = Field(None, description="Resolved start address (from geocoding).") # Populate separately
    end_address: Optional[str] = Field(None, description="Resolved end address (from geocoding).")   # Populate separately

    class Config:
        arbitrary_types_allowed = True  # Allow Duration protobuf

# --- Order Context (Simplified) ---
class OrderContext(BaseModel):
    """Minimal context about the current order, passed in requests."""
    order_id: Optional[str] = None
    passenger_destination_address: Optional[str] = None
    passenger_destination_place_id: Optional[str] = None # Add place_id if available
    passenger_pickup_address: Optional[str] = None
    passenger_pickup_place_id: Optional[str] = None # Add place_id if available
    passenger_phone_number: Optional[str] = None

# --- Safety Related ---
class SleepinessReport(BaseModel):
    """Information related to sleepiness detection."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    confidence: float = Field(..., description="Confidence level of sleepiness detection.")
    evidence_type: str = Field(..., description="e.g., 'image_analysis', 'behavioral'")

class CrashReport(BaseModel):
    """Information related to crash detection."""
    session_id: str
    driver_id: Optional[str] = None # Important for fetching emergency contacts
    location: Tuple[float, float] = Field(..., description="Lat/Lon of the incident.")
    timestamp: datetime = Field(default_factory=datetime.utcnow)