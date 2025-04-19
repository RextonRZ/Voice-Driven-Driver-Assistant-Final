# backend/api/assistant.py
import logging
import json
import base64 # Import base64 for decoding
import binascii # Import binascii for error handling
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Request,
    Form,
    File,
    UploadFile, Body
)
from typing import Optional, Tuple

# Models
from ..models.request import ProcessAudioRequest, OrderContext, DetectSpeechRequest # Added
from ..models.response import AssistantResponse, DetectSpeechResponse # Added DetectSpeechResponse
# Services & Dependencies
from ..services.conversation_service import ConversationService
from ..services.transcription_service import TranscriptionService # Added TranscriptionService import
from ..api.dependencies import get_conversation_service, get_transcription_service
# Exceptions
from ..core.exception import (
    AssistantBaseException, TranscriptionError, NluError, SynthesisError,
    TranslationError, NavigationError, CommunicationError, SafetyError, StateError,
    InvalidRequestError, ConfigurationError
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/assistant",
    tags=["Assistant Interaction"],
)

def _parse_location(loc_str: Optional[str]) -> Optional[Tuple[float, float]]:
    """Helper to parse location string 'lat,lon' or JSON '{"lat":x, "lon":y}'."""
    if not loc_str:
        return None
    try:
        if '{' in loc_str: # Try JSON parsing
            data = json.loads(loc_str)
            lat = float(data['lat'])
            lon = float(data['lon'])
        else: # Try comma-separated parsing
            parts = loc_str.split(',')
            if len(parts) != 2:
                raise ValueError("Location string must have two parts separated by comma.")
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
        return lat, lon
    except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
        logger.warning(f"Failed to parse location string '{loc_str}': {e}")
        return None # Or raise InvalidRequestError? Let service layer handle None for now.

def _parse_order_context(context_str: Optional[str]) -> Optional[OrderContext]:
    """Helper to parse order context JSON string."""
    if not context_str:
        return None
    try:
        data = json.loads(context_str)
        # Basic validation - check if it's a dict
        if not isinstance(data, dict):
            raise ValueError("Order context must be a JSON object.")
        # Use Pydantic model for validation and structure
        return OrderContext(**data)
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning(f"Failed to parse order context string '{context_str}': {e}")
        return None

@router.post(
    "/interact",
    response_model=AssistantResponse,
    summary="Process voice input and get assistant response",
    description="Receives audio, session ID, and optional context (location, order). "
                "Performs STT, NLU (intent recognition), action dispatch, TTS, and returns results.",
)
async def interact(
    # Use Form fields to receive multipart data
    session_id: str = Form(...),
    audio_data: UploadFile = File(...),
    language_code_hint: Optional[str] = Form(None, description="Optional BCP-47 language hint (e.g., 'ms-MY')"),
    current_location: Optional[str] = Form(None, description="Optional current location as 'lat,lon' string or JSON '{\"lat\":lat, \"lon\":lon}'"),
    order_context: Optional[str] = Form(None, description="Optional current order details as JSON string"),
    # Dependency injection
    conversation_service: ConversationService = Depends(get_conversation_service)
) -> AssistantResponse:
    """
    Main interaction endpoint handling voice commands.
    """
    logger.info(f"Received interaction request for session: {session_id}")

    try:
        # 1. Read and validate audio data
        audio_bytes = await audio_data.read()
        if not audio_bytes:
             logger.warning(f"Received empty audio file for session {session_id}.")
             raise InvalidRequestError("Received empty audio file.")
        logger.debug(f"Audio received: {len(audio_bytes)} bytes, filename: {audio_data.filename}, content_type: {audio_data.content_type}")

        # 2. Parse context data
        parsed_location = _parse_location(current_location)
        parsed_order_context = _parse_order_context(order_context)

        # 3. Construct request model for the service layer
        request_model = ProcessAudioRequest(
            session_id=session_id,
            audio_data=audio_bytes,
            language_code_hint=language_code_hint,
            current_location=parsed_location,
            order_context=parsed_order_context
        )

        # 4. Call the Conversation Service to handle the core logic
        response = await conversation_service.process_interaction(request_model)

        logger.info(f"Successfully processed interaction for session: {session_id}")
        return response

    # --- Specific Exception Handling for API Layer ---
    # Map service exceptions to appropriate HTTP status codes
    except InvalidRequestError as e:
        logger.warning(f"Invalid request for session {session_id}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (TranscriptionError, NluError, SynthesisError, TranslationError, NavigationError, CommunicationError) as e:
         # These indicate issues communicating with external services or core processing failures
         logger.error(f"Service error processing interaction for session {session_id}: {type(e).__name__} - {e}")
         # Use 502 Bad Gateway as we're acting as a gateway to other services
         raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Processing failed: {e.message}")
    except StateError as e:
         # Indicates the request cannot be fulfilled in the current context (e.g., asking for route without destination)
         logger.warning(f"State error for session {session_id}: {e}")
         # Use 409 Conflict or 400 Bad Request depending on semantics
         raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Action cannot be performed: {e.message}")
    except ConfigurationError as e:
         # Configuration issues should ideally be caught at startup, but handle defensively
         logger.critical(f"Configuration error encountered during request for session {session_id}: {e}", exc_info=True)
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal configuration error.")
    except AssistantBaseException as e:
         # Catch-all for other custom exceptions if any were missed
         logger.error(f"Unhandled Assistant Exception for session {session_id}: {e}", exc_info=True)
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An internal error occurred: {e.message}")
    except Exception as e:
        # Generic catch-all for truly unexpected errors
        logger.exception(f"Unexpected error during interaction for session {session_id}: {e}") # Use logger.exception to include traceback
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected internal server error occurred."
        )

# --- NEW: Speech Detection Endpoint ---
@router.post(
    "/detect-speech",
    response_model=DetectSpeechResponse,
    summary="Detect speech in a short audio chunk",
    description="Receives a short audio chunk (base64 encoded) and uses STT to detect "
                "if any human speech is present. Used by the frontend to determine when to stop recording.",
)
async def detect_speech(
    # Receive data from request body as JSON
    request_data: DetectSpeechRequest = Body(...),
    # Inject only the needed service
    transcription_service: TranscriptionService = Depends(get_transcription_service)
) -> DetectSpeechResponse:
    """
    Endpoint to check for voice activity in small audio segments.
    """
    session_id = request_data.session_id or "unknown"
    logger.debug(f"Received speech detection request for session: {session_id}")

    if not request_data.audio_data:
        logger.warning(f"Received empty audio data for speech detection (session: {session_id}).")
        # No audio means no speech detected
        return DetectSpeechResponse(speech_detected=False)

    try:
        # Decode the base64 audio data string
        try:
            audio_bytes = base64.b64decode(request_data.audio_data)
            logger.debug(f"Decoded base64 audio for detection: {len(audio_bytes)} bytes")
        except (binascii.Error, ValueError) as decode_err:
            logger.error(f"Invalid base64 audio data received for detection (session: {session_id}): {decode_err}")
            raise InvalidRequestError(f"Invalid base64 encoding for audio data: {decode_err}")

        # Call transcription service - we only care if transcript is non-empty
        # No language hint needed, let STT try its best to detect anything
        transcript, _ = await transcription_service.process_audio(
            audio_data=audio_bytes,
            language_code_hint=None # Explicitly None for broad detection
        )

        speech_was_detected = bool(transcript) # True if transcript is not empty, False otherwise
        logger.debug(f"Speech detection result for session {session_id}: {speech_was_detected}. Transcript: '{transcript[:50]}...'")

        return DetectSpeechResponse(speech_detected=speech_was_detected)

    except InvalidRequestError as e:
        # Errors during decoding or audio processing
        logger.warning(f"Invalid request for speech detection (session: {session_id}): {e}")
        # Decide how to handle: maybe return speech_detected=False or raise error?
        # Raising 400 seems appropriate for bad input.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid audio data: {e.message}")
    except TranscriptionError as e:
        # Errors from the STT API itself
        logger.error(f"STT error during speech detection (session: {session_id}): {e}")
        # If STT fails, we can't reliably detect silence. Treat as if speech *might* be present? Or error out?
        # Erroring out (502) seems safer than incorrectly telling FE to stop.
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Speech detection failed due to STT error: {e.message}")
    except Exception as e:
        # Generic catch-all
        logger.exception(f"Unexpected error during speech detection (session: {session_id}): {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unexpected error during speech detection.")