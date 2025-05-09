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
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY", None)
    # TWILIO_ACCOUNT_SID: Optional[str] = None # Required if using Twilio for SMS/Calls
    # TWILIO_AUTH_TOKEN: Optional[str] = None # Required if using Twilio
    # TWILIO_PHONE_NUMBER: Optional[str] = None # Required if using Twilio

    # --- Translation & NLU ---
    NLU_PROCESSING_LANGUAGE: str = "en" # Target language for Gemini processing
    DEFAULT_LANGUAGE_CODE: str = "en-US" # Fallback BCP-47 language
    SUPPORTED_LANGUAGES: List[str] = [ # BCP-47 codes for STT language detection hint
        "en-SG", "en-PH", "ms-MY", "id-ID",
        "fil-PH", "th-TH", "vi-VN", "km-KH", "cmn-Hans-CN", "cmn-CN", "ta-IN"
    ]

    # --- Assistant Behavior ---
    HISTORY_MAX_MESSAGES: int = 10 # Max user/assistant turn pairs in history
    GEMINI_MODEL_NAME: str = "gemini-2.0-flash" # Updated model

    # --- NEW: Refinement Prompt ---
    ENABLE_TRANSCRIPTION_REFINEMENT: bool = True  # Feature flag for the refinement step
    NLU_REFINEMENT_PROMPT: str = """
Task: You are an intelligent assistant aiding a driver who speaks {language_name} ({language_code}). Your task is to refine the provided raw voice transcription. The transcription might contain speech recognition errors, colloquialisms, or be incomplete. Your goal is to interpret the driver's *likely intended request* based on common driving/assistant scenarios and output a clear, complete, and actionable version of that request or statement.
Instructions:
1.  **Correct Errors:** Fix obvious speech recognition errors, typos, and misheard words. Pay close attention to locations, names, numbers, and keywords relevant to driving actions (e.g., "navigate", "directions", "send", "message", "call", "check", "flood", "gate", "passenger", "ETA").
2.  **Infer Intent & Complete Requests:** If the transcription is fragmented or missing key information (like a verb or object), infer the most probable *driver request*.
    *   Example 1: If input is just "KLCC Tower", infer "Navigate to KLCC Tower" or "Get directions to KLCC Tower".
    *   Example 2: If input is "message passenger running bit late", infer "Send message to the passenger saying I am running a bit late."
    *   Example 3: If input is "check flood Bedok area", infer "Check for flood warnings in the Bedok area."
    *   Example 4: If input is very short like "Gate?" (in a pickup context), infer "Ask passenger for specific gate information".
    *   Use common sense based on a driver's typical needs during a trip (navigation, communication, status checks).
3.  **Improve Clarity & Flow:** Rephrase slightly for grammatical correctness and natural sentence structure in {language_name}. Eliminate hesitation sounds or filler words if clearly not part of the intended request.
4.  **Maintain Core Meaning:** While inferring missing parts, *do not fundamentally change the topic or goal* of the likely request. If the input is truly ambiguous or nonsensical, make minimal corrections. Avoid adding completely new information or requests not implied by the input.
5.  **Language:** The output MUST be in the original language: {language_code}.
6.  **Output:** Respond ONLY with the single, refined text string. Do not add greetings, explanations, or labels.

Original Transcription ({language_code}):
"{original_text}"

Refined Text ({language_code}):
"""

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

    # --- Noise Reduction Settings (NEW) ---
    NOISE_REDUCTION_METHOD: str = "tunable_nr"  # Options: 'tunable_nr', 'wiener' (if implemented), 'none'
    # Parameters for 'tunable_nr' method (from noise_reduction.py defaults/example)
    NR_PROP_DECREASE: float = 0.9  # NR strength (0.0-1.0). Controls how much noise is subtracted.
    NR_TIME_SMOOTH_MS: float = 150.0  # Temporal smoothing (ms). Higher = less aggressive gating.
    NR_PASSES: int = 1

    # --- TTS Settings ---
    DEFAULT_TTS_SPEAKING_RATE: float = 1.0
    TTS_AUDIO_ENCODING: str = "MP3" # Or LINEAR16 if preferred
    DEFAULT_TTS_VOICE_NAME: Optional[str] = "en-US-Standard-C" # Fallback voice
    TTS_LANGUAGE_VOICE_MAP: Dict[str, str] = {  # BCP-47 lowercased : Voice Name
        "en-us": "en-US-Standard-C",
        "en-sg": "en-US-Standard-B",
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
    MAPS_DEFAULT_TRAVEL_MODE: str = "DRIVE"  # Routes API uses enum name
    MAPS_ROUTES_FIELD_MASK: str = "routes.legs.steps.localized_values,routes.legs.steps.polyline,routes.warnings,routes.localized_values,routes.route_token,routes.legs.polyline,routes.polyline.encodedPolyline,routes.distanceMeters,routes.duration,routes.travelAdvisory"  # Default fields for RouteInfo
    FLOOD_CHECK_ENABLED: bool = True

    # --- Flood Check Specific Settings ---
    FLOOD_DATA_BASE_URL: str = "https://publicinfobanjir.water.gov.my"
    # Mapping from state names (as likely returned by Google Geocoding for Malaysia)
    # to the codes used on publicinfobanjir.water.gov.my
    # NOTE: Verify these codes match the website's dropdown/query params exactly!
    MALAYSIA_STATE_CODES: Dict[str, str] = {
        "johor": "JHR",
        "kedah": "KDH",
        "kelantan": "KEL",
        "melaka": "MLK",
        "negeri sembilan": "NSN",
        "pahang": "PHG",
        "perak": "PRK",
        "perlis": "PLS",
        "pulau pinang": "PNG",  # Penang
        "sabah": "SBH",
        "sarawak": "SWK",
        "selangor": "SEL",
        "terengganu": "TRG",
        "wilayah persekutuan kuala lumpur": "WLY",  # KL Federal Territory
        "wilayah persekutuan labuan": "WLY",  # Labuan (assuming same code as KL? Verify)
        "wilayah persekutuan putrajaya": "WLY",  # Putrajaya (assuming same code as KL? Verify)
        "federal territory of kuala lumpur": "WLY",
        "kuala lumpur": "WLY",
        "penang": "PNG",
    }

    # --- Safety Settings ---
    CRASH_DETECTION_NOTIFICATION_ENABLED: bool = True # Feature flag
    # Define emergency contact lookup method (e.g., API endpoint, placeholder)
    EMERGENCY_CONTACT_SOURCE: str = "placeholder" # e.g., "api://internal.profile.service/contacts/{driver_id}"

    # --- Drowsiness Detection Settings ---
    DROWSINESS_DETECTION_ENABLED: bool = True
    YAWN_MODEL_PATH: str = "/Users/vannessliu/VisualStudioCode/Voice-Driven-Driver-Assistant-Final/backend/app/ml_models/detect_eye_best.pt"
    EYE_MODEL_PATH: str = "/Users/vannessliu/VisualStudioCode/Voice-Driven-Driver-Assistant-Final/backend/app/ml_models/detect_yawn_best.pt"
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