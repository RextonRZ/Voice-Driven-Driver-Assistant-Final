# backend/core/config.py
import os
from typing import List, Optional, Dict, Tuple
from pydantic_settings import BaseSettings, SettingsConfigDict
import logging

# Configure logging early
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """Application configuration settings."""
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    LOG_LEVEL: str = "INFO"

    # --- API Keys & Credentials ---
    # GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None # Recommended: Set this env var externally for ADC
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY") # Required for NLU
    GOOGLE_MAPS_API_KEY: str = os.getenv("GOOGLE_MAPS_API_KEY") # Required for Navigation
    # TWILIO_ACCOUNT_SID: Optional[str] = None # Required if using Twilio for SMS/Calls
    # TWILIO_AUTH_TOKEN: Optional[str] = None # Required if using Twilio
    # TWILIO_PHONE_NUMBER: Optional[str] = None # Required if using Twilio

    # --- Translation & NLU ---
    NLU_PROCESSING_LANGUAGE: str = "en" # Target language for Gemini processing
    DEFAULT_LANGUAGE_CODE: str = "en-US" # Fallback BCP-47 language
    SUPPORTED_LANGUAGES: List[str] = [ # BCP-47 codes for STT language detection hint
        "en-SG", "en-PH", "ms-MY", "id-ID",
        "fil-PH", "th-TH", "vi-VN", "km-KH", "my-MM", "cmn-Hans-CN", "cmn-CN", "ta-IN"
    ]

    # --- Assistant Behavior ---
    HISTORY_MAX_MESSAGES: int = 10 # Max user/assistant turn pairs in history
    GEMINI_MODEL_NAME: str = "gemini-2.0-flash" # Updated model
    NLU_INTENT_PROMPT: str = """
Analyze the user's query considering the conversation history and provided context.
Identify the primary intent from the list: {intents}.
Extract relevant entities for the intent. Examples:
- get_route: {{ "destination": "..." }}
- send_message: {{ "recipient_hint": "...", "message_content": "..." }}
- check_flood: {{ "location_hint": "..." }} (e.g., "around current location", "on my route")
- ask_gate_info: {{}} (intent is enough if order context is present)
- reroute_check: {{}} (intent is enough)
- general_chat: {{}}
If the intent is unclear or purely conversational, classify as 'general_chat' and provide a natural language response.
If the intent is recognized but lacks necessary entities (e.g., get_route without destination), ask for clarification.

Output ONLY a JSON object with the following structure:
{{
  "intent": "...", // One of the listed intents
  "entities": {{...}}, // Extracted entities as key-value pairs
  "confidence": 0.0_to_1.0, // Your confidence in the intent classification
  "response": "..." // Your natural language response/clarification question/chat reply. Required.
}}
"""

    # --- STT Settings ---
    STT_MODEL: Optional[str] = "latest_long"
    STT_ENABLE_AUTOMATIC_PUNCTUATION: bool = True

    # --- TTS Settings ---
    DEFAULT_TTS_SPEAKING_RATE: float = 1.0
    TTS_AUDIO_ENCODING: str = "MP3" # Or LINEAR16 if preferred
    DEFAULT_TTS_VOICE_NAME: Optional[str] = "en-US-Standard-C" # Fallback voice
    TTS_LANGUAGE_VOICE_MAP: Dict[str, str] = {  # BCP-47 lowercased : Voice Name
        "en-us": "en-US-Standard-C",
        "en-sg": "en-US-Standard-B",  # <<< MAKE SURE THIS IS CORRECT and SAVED
        "en-ph": "en-PH-Standard-A",
        "ms-my": "ms-MY-Standard-A",
        "id-id": "id-ID-Standard-A",
        "fil-ph": "fil-PH-Standard-A",
        "th-th": "th-TH-Standard-A",
        "vi-vn": "vi-VN-Standard-D",
        "km-kh": "km-KH-Standard-A",
        "my-mm": "my-MM-Standard-A",
        "cmn-cn": "cmn-CN-Standard-A",
        "cmn-hans-cn": "cmn-Hans-CN-Standard-A",
        "ta-in": "ta-IN-Standard-A"
    }

    # --- Navigation Settings ---
    MAPS_DEFAULT_REGION: str = "MY"  # Bias results towards a region (e.g., SG, MY, PH)
    MAPS_DEFAULT_TRAVEL_MODE: str = "DRIVING"  # Routes API uses enum name
    MAPS_ROUTES_FIELD_MASK: str = "routes.legs.steps.localized_values,routes.legs.steps.polyline,routes.warnings,routes.localized_values,routes.route_token,routes.legs.polyline,routes.polyline.encodedPolyline,routes.distanceMeters,routes.duration,routes.travelAdvisory"  # Default fields for RouteInfo
    FLOOD_CHECK_ENABLED: bool = False

    # --- Safety Settings ---
    CRASH_DETECTION_NOTIFICATION_ENABLED: bool = True # Feature flag
    # Define emergency contact lookup method (e.g., API endpoint, placeholder)
    EMERGENCY_CONTACT_SOURCE: str = "placeholder" # e.g., "api://internal.profile.service/contacts/{driver_id}"

    # --- Drowsiness Detection Settings ---
    DROWSINESS_DETECTION_ENABLED: bool = True
    YAWN_MODEL_PATH: str = "C:\\Users\\hongy\\PycharmProjects\\Voice-Driven-Driver-Assistant-Final\\backend\\app\\ml_models\\detect_yawn_best.pt"
    EYE_MODEL_PATH: str = "C:\\Users\\hongy\\PycharmProjects\\Voice-Driven-Driver-Assistant-Final\\backend\\app\\ml_models\\detect_eye_best.pt"
    # Thresholds (adjust based on testing and batch duration)
    DROWSINESS_YAWN_THRESHOLD_SEC: float = 5.0  # Shorter than original? Depends on batch analysis.
    DROWSINESS_MICROSLEEP_THRESHOLD_SEC: float = 2.0  # Shorter than original?
    DROWSINESS_FRAME_INTERVAL_SEC: float = 0.2  # Estimated time between frames IN A BATCH sent by frontend
    DROWSINESS_YOLO_CONF_THRESHOLD: float = 0.5  # Confidence threshold for YOLO detections
    DROWSINESS_MEDIAPIPE_MIN_DET_CONF: float = 0.5
    DROWSINESS_MEDIAPIPE_MIN_TRACK_CONF: float = 0.5

try:
    settings = Settings()
    # Log some settings on startup for verification
    logger.info(f"Settings loaded. NLU Lang: {settings.NLU_PROCESSING_LANGUAGE}, Gemini Model: {settings.GEMINI_MODEL_NAME}")
    logger.info(f"Maps API Key Loaded: {'Yes' if settings.GOOGLE_MAPS_API_KEY != 'YOUR_GOOGLE_MAPS_API_KEY' else 'No/Default'}")
    if settings.DROWSINESS_DETECTION_ENABLED:
        if not os.path.exists(settings.YAWN_MODEL_PATH):
            logger.warning(
                f"Yawn detection model not found at: {settings.YAWN_MODEL_PATH}. Drowsiness detection may fail.")
            # Consider raising ConfigurationError if models are essential
        if not os.path.exists(settings.EYE_MODEL_PATH):
            logger.warning(
                f"Eye detection model not found at: {settings.EYE_MODEL_PATH}. Drowsiness detection may fail.")
except Exception as e:
    logger.critical(f"FATAL: Could not load settings. Error: {e}", exc_info=True)
    # You might want to exit the application here if settings are critical
    # import sys
    # sys.exit(1)
    # Fallback to default settings object for type hinting, but it will likely fail later
    settings = Settings()