# backend/api/assistant.py
import logging
import json
import time
import base64
import os
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
from fastapi.responses import FileResponse
from typing import Optional, Tuple
from google.api_core.exceptions import InvalidArgument  # Ensure this import is added

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

# Define a directory to save generated audio files
AUDIO_OUTPUT_DIR = "generated_audio"
os.makedirs(AUDIO_OUTPUT_DIR, exist_ok=True)

def _parse_location(loc_str: Optional[str]) -> Optional[Tuple[float, float]]:
    """Helper to parse location string 'lat,lon' or JSON '{"lat":x, "lon":y}'."""
    if not loc_str:
        return None
    try:
        if '{' in loc_str: # Try JSON parsing
            data = json.loads(loc_str)
            # Ensure keys are present and values are numeric
            lat = float(data['lat']) if 'lat' in data and isinstance(data['lat'], (int, float)) else None
            lon = float(data['lon']) if 'lon' in data and isinstance(data['lon'], (int, float)) else None
            if lat is None or lon is None:
                 raise ValueError("Invalid lat or lon in JSON location string.")
            return lat, lon
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
)
async def interact(
    session_id: str = Form(...),
    audio_data: UploadFile = File(...),
    language_code_hint: Optional[str] = Form(None),
    current_location: Optional[str] = Form(None),
    order_context: Optional[str] = Form(None),
    conversation_service: ConversationService = Depends(get_conversation_service)
) -> AssistantResponse:
    logger.info(f"Received interaction request for session: {session_id}")
    start_time = time.time()  # Start timing

    try:
        # Read audio bytes - UploadFile needs await .read()
        audio_bytes = await audio_data.read()
        if not audio_bytes:
            logger.error("Received empty audio file for /interact.")
            raise InvalidRequestError("Received empty audio file.")
        logger.debug(f"Received {len(audio_bytes)} bytes for /interact audio_data.")

        # Parse optional form fields
        parsed_location = _parse_location(current_location)
        if parsed_location is None and current_location:
            # Log this as a warning if parsing failed but data was provided
            logger.warning(f"Failed to parse current location string provided: '{current_location}'")

        parsed_order_context = _parse_order_context(order_context)
        if parsed_order_context is None and order_context:
            # Log this as a warning if parsing failed but data was provided
            logger.warning(f"Failed to parse order context string provided: '{order_context}'")


        # Create the internal request model
        request_model = ProcessAudioRequest(
            session_id=session_id,
            audio_data=audio_bytes, # Pass raw bytes
            language_code_hint=language_code_hint,
            current_location=parsed_location,
            order_context=parsed_order_context
        )

        logger.debug(f"Calling ConversationService.process_interaction for session: {session_id}")

        # Process the interaction using the service
        response = await conversation_service.process_interaction(request_model)

        # Check if response_audio (base64 string) is present and save it
        response_audio_path = None
        if response.response_audio:
            try:
                audio_filename = f"{session_id}_{int(time.time())}_response.wav" # Added _response
                audio_file_path_full = os.path.join(AUDIO_OUTPUT_DIR, audio_filename)

                # Decode and save the audio
                audio_data_bytes = base64.b64decode(response.response_audio)
                with open(audio_file_path_full, "wb") as audio_file:
                    audio_file.write(audio_data_bytes)

                logger.info(f"Generated audio saved at: {audio_file_path_full}")

                # Set the public path for the frontend
                response_audio_path = f"/assistant/audio/{audio_filename}"
                response.audio_file_path = response_audio_path

            except binascii.Error:
                 logger.error("Failed to decode base64 audio data from conversation service response.")
                 # Don't raise error, just don't set audio_file_path
                 response.audio_file_path = None # Ensure it's None on error
            except Exception as e:
                logger.error(f"Error saving generated audio: {e}")
                response.audio_file_path = None # Ensure it's None on error


        logger.info(f"Interaction processed successfully for session: {session_id}")
        return response # Return the response model

    except InvalidArgument as e:  # Handle InvalidArgument from Google APIs within services
        logger.error(f"Google API Invalid argument error during transcription or NLU: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Service processing error: Invalid argument provided to external API. {str(e)}"
        )
    except InvalidRequestError as e: # Handle custom validation errors
        logger.error(f"Invalid request received: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )
    except AssistantBaseException as e: # Handle known service-layer errors
        logger.error(f"Assistant service error: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, # Or appropriate status code per exception type
            detail=e.message
        )
    except Exception as e: # Catch any other unexpected errors
        logger.exception(f"Unexpected error during interaction for session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during interaction: {str(e)}"
        )
    finally:
        end_time = time.time()  # End timing
        logger.info(f"Total processing time for session {session_id}: {end_time - start_time:.2f} seconds")

# Add an endpoint to serve the audio files
@router.get("/audio/{filename}")
async def get_audio_file(filename: str):
    """Serve the generated audio files."""
    file_path = os.path.join(AUDIO_OUTPUT_DIR, filename)
    # Basic security check: prevent directory traversal
    if not os.path.abspath(file_path).startswith(os.path.abspath(AUDIO_OUTPUT_DIR)):
         logger.warning(f"Attempted directory traversal detected: {filename}")
         raise HTTPException(status_code=400, detail="Invalid filename")

    if not os.path.exists(file_path):
        logger.warning(f"Requested audio file not found: {filename}")
        raise HTTPException(status_code=404, detail="Audio file not found")

    # Determine media type dynamically if possible, or use a common one
    # For .wav, audio/wav is standard. For .mp3, audio/mpeg, etc.
    # For simplicity, hardcode wav or use a library like `mimetypes`
    file_extension = os.path.splitext(filename)[1].lower()
    media_type = "application/octet-stream" # Default unknown type
    if file_extension == ".wav":
        media_type = "audio/wav"
    elif file_extension == ".mp3":
        media_type = "audio/mpeg"
    elif file_extension == ".ogg":
        media_type = "audio/ogg"
    elif file_extension == ".aac":
         media_type = "audio/aac"
    elif file_extension == ".m4a":
         media_type = "audio/mp4" # m4a is often mp4 audio

    logger.debug(f"Serving audio file {filename} with media type {media_type}")
    return FileResponse(file_path, media_type=media_type)

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
            logger.info(f"[VAD] Decoded base64 audio for detection: {len(audio_bytes)} bytes")
            logger.debug(f"Decoded base64 audio for detection: {len(audio_bytes)} bytes")
        except (binascii.Error, ValueError) as decode_err:
            logger.error(f"Invalid base64 audio data received for detection (session: {session_id}): {decode_err}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid base64 encoding for audio data: {decode_err}")

        if not audio_bytes:
             logger.debug(f"Decoded audio data is empty after base64 decode (session: {session_id}).")
             return DetectSpeechResponse(speech_detected=False)

        # Call transcription service - we only care if transcript is non-empty
        # We can pass the raw bytes directly to process_audio
        # No language hint needed, let STT try its best to detect anything
        logger.info(f"[VAD] Calling STT service to check for speech (session: {session_id})")
        transcript, _ = await transcription_service.process_audio(
            audio_data=audio_bytes,
            language_code_hint=None, # Explicitly None for broad detection
             # Optionally pass format/encoding info if known, but transcription service should ideally detect
             # audio_format=..., audio_encoding=...
        )

        # Determine if speech was detected based on whether a non-empty transcript was returned
        # Some STT services might return a non-empty transcript even for noise.
        # A more advanced VAD might involve checking confidence scores or specific events.
        # For this implementation, non-empty transcript = speech detected.
        speech_was_detected = bool(transcript and transcript.strip()) # Check for non-empty, non-whitespace string
        logger.debug(f"Speech detection result for session {session_id}: {speech_was_detected}. Transcript: '{transcript.strip()[:50]}...'")

        # Enhanced logging with truncated transcript
        if speech_was_detected:
            logger.info(f"[VAD] SPEECH DETECTED for session {session_id}. Transcript snippet: '{transcript.strip()[:30]}...'")
        else:
            logger.info(f"[VAD] NO SPEECH DETECTED for session {session_id}. Empty or silent audio.")

        return DetectSpeechResponse(speech_detected=speech_was_detected)

    except InvalidRequestError as e:
        # Errors during decoding or audio processing (e.g., unsupported format by STT)
        logger.warning(f"Invalid request data for speech detection (session: {session_id}): {e.message}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid audio data: {e.message}")
    except TranscriptionError as e:
        # Errors from the STT API itself
        logger.error(f"STT error during speech detection (session: {session_id}): {e.message}")
        # If STT fails, we can't reliably detect silence. Treat as if speech *might* be present? Or error out?
        # Erroring out (502 Bad Gateway) seems safer than incorrectly telling FE to stop,
        # but the frontend is designed to assume speech on backend errors for robustness.
        # So, we raise the error here, and the frontend's catch block handles it by returning true.
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Speech detection failed due to STT error: {e.message}")
    except Exception as e:
        # Generic catch-all
        logger.exception(f"Unexpected error during speech detection (session: {session_id}): {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unexpected error during speech detection.")
