# backend/models/request.py
from typing import Optional, Tuple, Dict, Any
from pydantic import BaseModel, Field, Json
from fastapi import Form, UploadFile, File
from datetime import datetime
from typing import List

from ..models.internal import OrderContext # Import for type hinting

class ProcessAudioRequest(BaseModel):
    """Internal representation of the data from the /interact endpoint form."""
    session_id: str
    audio_data: bytes # Raw audio bytes after reading UploadFile
    language_code_hint: Optional[str] = None # Optional hint from form
    current_location: Optional[Tuple[float, float]] = None # Parsed from form
    order_context: Optional[OrderContext] = None # Parsed from form

    class Config:
        arbitrary_types_allowed = True


class InteractFormData:
    def __init__(
        self,
        session_id: str = Form(...),
        audio_data: UploadFile = File(...),
        language_code: Optional[str] = Form(None, alias="language_code_hint"),
        current_location: Optional[str] = Form(None), # Receive as JSON string "lat,lon" or {"lat": x, "lon": y}
        order_context: Optional[str] = Form(None) # Receive as JSON string
    ):
        self.session_id = session_id
        self.audio_data = audio_data
        self.language_code_hint = language_code
        self.current_location_str = current_location
        self.order_context_str = order_context


# --- Safety Endpoint Request ---
class CrashDetectionRequest(BaseModel):
    """Request body for the /safety/crash-detected endpoint."""
    session_id: str
    driver_id: Optional[str] = Field(None, description="Identifier for the driver, if available.")
    location: Tuple[float, float] = Field(..., description="Lat/Lon where crash was detected.")
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Timestamp of detection.")
    # Include any relevant sensor data if needed
    sensor_details: Optional[Dict[str, Any]] = None

# --- Navigation Endpoint Request (Example) ---
class RerouteCheckRequest(BaseModel):
    """Request body for the /navigation/reroute-check endpoint."""
    session_id: str
    current_location: Tuple[float, float]
    destination_address: str # Or Lat/Lon tuple
    # Include current route details if needed for comparison (e.g., current polyline, original ETA)
    current_route_polyline: Optional[str] = None
    current_eta_seconds: Optional[int] = None

class AnalyzeSleepinessRequest(BaseModel):
    """Request body for the /safety/analyze-sleepiness endpoint."""
    session_id: str
    driver_id: Optional[str] = None
    # Expecting a list of base64 encoded image frames
    image_frames_base64: List[str] = Field(..., description="List of base64 encoded image frames from a short interval.")
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)
    # Optional: Frontend can pass the estimated duration this batch represents
    batch_duration_sec: Optional[float] = None