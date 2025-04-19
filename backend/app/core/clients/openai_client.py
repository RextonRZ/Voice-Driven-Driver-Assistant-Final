import logging
import io
from typing import Optional
import asyncio

try:
    from openai import AsyncOpenAI, APIError, OpenAIError
except ImportError:
    AsyncOpenAI = None
    APIError = None
    OpenAIError = None
    logging.critical("OpenAI library not found. Please install it (`pip install openai`). OpenAI features will be disabled.")


from ..config import Settings
from ..exception import TranscriptionError, ConfigurationError, InvalidRequestError

logger = logging.getLogger(__name__)

# Recommended model for transcription
DEFAULT_WHISPER_MODEL = "whisper-1"

class OpenAiClient:
    """Client for interacting with OpenAI APIs (specifically Whisper for now)."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = None
        self.enabled = False

        if AsyncOpenAI is None:
            logger.error("OpenAI client cannot be initialized because the 'openai' library is missing.")
            return # Remain disabled

        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY is not configured. OpenAI client will be disabled.")
            return # Remain disabled

        try:
            self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            self.enabled = True
            logger.info(f"OpenAI AsyncClient initialized successfully (for Whisper model: {DEFAULT_WHISPER_MODEL}).")
            # Potential test call (optional, adds startup time/cost):
            # asyncio.run(self.client.models.list())
        except OpenAIError as e:
            logger.error(f"Failed to initialize OpenAI client: {e}", exc_info=True)
            raise ConfigurationError(f"OpenAI client configuration failed: {e}", original_exception=e)
        except Exception as e:
             logger.error(f"Unexpected error initializing OpenAI client: {e}", exc_info=True)
             # Fallback to disabled state
             self.enabled = False


    def _get_iso_639_1_code(self, bcp47_code: Optional[str]) -> Optional[str]:
        """Extracts ISO 639-1 code for Whisper language hint."""
        if not bcp47_code:
            return None
        try:
            return bcp47_code.split('-')[0].lower()
        except Exception:
            logger.warning(f"Could not parse ISO 639-1 code from BCP-47 hint: {bcp47_code}")
            return None

    async def transcribe(
        self,
        audio_data: bytes,
        filename: str, # Must include extension (e.g., "audio.wav")
        language_code_hint: Optional[str] = None # Optional BCP-47 hint
    ) -> Optional[str]:
        """
        Transcribes audio data using OpenAI Whisper API.

        Args:
            audio_data: Raw audio bytes.
            filename: A filename including a valid audio extension (e.g., audio.wav, audio.mp3).
                      Required by the OpenAI API.
            language_code_hint: Optional BCP-47 language hint (will be converted to ISO 639-1).

        Returns:
            The transcribed text (str) or None if transcription fails or returns empty.

        Raises:
            TranscriptionError: If the API call fails.
            InvalidRequestError: If input parameters are invalid.
            ConfigurationError: If the client is not enabled/configured.
        """
        if not self.enabled or self.client is None:
            raise ConfigurationError("OpenAI client is not enabled or configured.")
        if not audio_data:
            logger.warning("OpenAI transcribe called with empty audio data.")
            return None
        if not filename or '.' not in filename:
            raise InvalidRequestError("A valid filename with an extension is required for OpenAI transcription.")

        try:
            # Prepare file tuple for API: (filename, file_bytes, content_type - optional)
            audio_file_tuple = (filename, audio_data)

            # Convert BCP-47 hint to ISO 639-1 for Whisper if provided
            iso_language_hint = self._get_iso_639_1_code(language_code_hint)

            logger.info(f"Sending request to OpenAI Whisper API ({DEFAULT_WHISPER_MODEL}). File: {filename}, Lang hint: {iso_language_hint or 'None'}")

            response = await self.client.audio.transcriptions.create(
                model=DEFAULT_WHISPER_MODEL,
                file=audio_file_tuple,
                language=iso_language_hint, # Pass ISO code or None
                # response_format="text" # Simpler, but "json" (default) might be safer if API changes
            )

            # Default response format is JSON with a 'text' field
            transcript = response.text if hasattr(response, 'text') else None

            if transcript:
                logger.info(f"OpenAI Whisper transcription successful. Transcript: '{transcript[:50]}...'")
                return transcript.strip()
            else:
                logger.warning("OpenAI Whisper API returned no transcript text.")
                return None

        except APIError as e:
            # Handle API errors (e.g., authentication, rate limits)
            logger.error(f"OpenAI API error during transcription: {e}", exc_info=True)
            raise TranscriptionError(f"OpenAI API request failed: {e.status_code} - {e.message}", original_exception=e)
        except OpenAIError as e:
            # Handle other library errors
            logger.error(f"OpenAI library error during transcription: {e}", exc_info=True)
            raise TranscriptionError(f"OpenAI client library error: {e}", original_exception=e)
        except Exception as e:
            logger.error(f"Unexpected error during OpenAI transcription: {e}", exc_info=True)
            raise TranscriptionError(f"An unexpected error occurred during OpenAI transcription: {e}", original_exception=e)