# backend/api/assistant.py
import logging
import json
import time
import base64
import os
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Request,
    Form,
    File,
    UploadFile
)
from fastapi.responses import FileResponse
from typing import Optional, Tuple
from google.api_core.exceptions import InvalidArgument  # Ensure this import is added

# Models
from ..models.request import ProcessAudioRequest, OrderContext
from ..models.response import AssistantResponse
# Services & Dependencies
from ..services.conversation_service import ConversationService
from ..api.dependencies import get_conversation_service
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
        audio_bytes = await audio_data.read()
        if not audio_bytes:
            logger.error("Received empty audio file.")
            raise InvalidRequestError("Received empty audio file.")

        parsed_location = _parse_location(current_location)
        if parsed_location is None and current_location:
            logger.warning(f"Failed to parse current location: {current_location}")

        parsed_order_context = _parse_order_context(order_context)
        if parsed_order_context is None and order_context:
            logger.warning(f"Failed to parse order context: {order_context}")

        request_model = ProcessAudioRequest(
            session_id=session_id,
            audio_data=audio_bytes,
            language_code_hint=language_code_hint,
            current_location=parsed_location,
            order_context=parsed_order_context
        )

        logger.debug(f"Request model created: {request_model}")

        response = await conversation_service.process_interaction(request_model)
        
        # Convert base64 audio to WAV file
        if response.response_audio:
            audio_filename = f"{session_id}_{int(time.time())}.wav"
            audio_file_path = os.path.join(AUDIO_OUTPUT_DIR, audio_filename)
            
            # Decode and save the audio
            with open(audio_file_path, "wb") as audio_file:
                audio_file.write(base64.b64decode(response.response_audio))
            
            logger.info(f"Generated audio saved at: {audio_file_path}")
            
            # Add the public path to the response
            response.audio_file_path = f"/assistant/audio/{audio_filename}"
        
        logger.info(f"Interaction processed successfully for session: {session_id}")
        return response

    except InvalidArgument as e:  # Handle InvalidArgument exception
        logger.error(f"Invalid argument error during transcription: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid argument error during transcription: {str(e)}"
        )
    except InvalidRequestError as e:
        logger.error(f"Invalid request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except AssistantBaseException as e:
        logger.error(f"Assistant error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Unexpected error during interaction: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during transcription: {str(e)}"
        )
    finally:
        end_time = time.time()  # End timing
        logger.info(f"Total processing time for session {session_id}: {end_time - start_time:.2f} seconds")

# Add an endpoint to serve the audio files
@router.get("/audio/{filename}")
async def get_audio_file(filename: str):
    """Serve the generated audio files."""
    file_path = os.path.join(AUDIO_OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(file_path, media_type="audio/wav")