# backend/api/assistant.py
import logging
import json
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
from typing import Optional, Tuple

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