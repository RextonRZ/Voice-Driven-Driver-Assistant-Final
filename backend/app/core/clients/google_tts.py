import logging
from typing import Optional
from google.cloud import texttospeech
from google.api_core.exceptions import GoogleAPIError
import asyncio

from ..config import Settings, settings as global_settings
from ..exception import SynthesisError, ConfigurationError, InvalidRequestError

logger = logging.getLogger(__name__)

# Mock implementation for structure - Replace with your actual GoogleTtsClient
class GoogleTtsClient:
    """Client for Google Cloud Text-to-Speech API."""

    def __init__(self, settings: Settings):
        self.settings = settings
        try:
            # ADC preferred
            self.client = texttospeech.TextToSpeechAsyncClient()
            logger.info("Google Text-to-Speech AsyncClient initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Google TTS client: {e}", exc_info=True)
            raise ConfigurationError(f"Google TTS client initialization failed: {e}", original_exception=e)

    async def synthesize(
        self,
        text: str,
        language_code: str, # BCP-47 code (e.g., "en-US")
        voice_name: Optional[str] = None, # Specific voice name (e.g., "en-US-Standard-C")
        speaking_rate: Optional[float] = None,
        audio_encoding: Optional[str] = None # e.g., "MP3", "LINEAR16"
    ) -> bytes:
        """
        Synthesizes speech from text.

        Args:
            text: The text to synthesize.
            language_code: The BCP-47 language code.
            voice_name: Optional specific voice name. If None, API chooses default.
            speaking_rate: Optional speaking rate (default defined in settings).
            audio_encoding: Optional audio encoding (default defined in settings).

        Returns:
            The synthesized audio as bytes.

        Raises:
            SynthesisError: If the API call fails.
            InvalidRequestError: If input is invalid.
        """
        if not text:
            logger.warning("Synthesize called with empty text.")
            return b""
        if not language_code:
            raise InvalidRequestError("language_code is required for synthesis.")

        synthesis_input = texttospeech.SynthesisInput(text=text)

        effective_voice_name = voice_name or self.settings.DEFAULT_TTS_VOICE_NAME # Use default from settings if specific one not provided
        voice_params = texttospeech.VoiceSelectionParams(
            language_code=language_code
            # Name is optional; if not provided, API picks a default *for that language*
        )
        if effective_voice_name:
             voice_params.name = effective_voice_name


        effective_encoding_str = audio_encoding or self.settings.TTS_AUDIO_ENCODING
        try:
             audio_config_encoding = texttospeech.AudioEncoding[effective_encoding_str.upper()]
        except KeyError:
             logger.error(f"Invalid TTS_AUDIO_ENCODING '{effective_encoding_str}'. Falling back to MP3.")
             audio_config_encoding = texttospeech.AudioEncoding.MP3


        effective_speaking_rate = speaking_rate or self.settings.DEFAULT_TTS_SPEAKING_RATE
        audio_config = texttospeech.AudioConfig(
            audio_encoding=audio_config_encoding,
            speaking_rate=effective_speaking_rate,
            # Add pitch, volume etc. if needed
        )

        request = texttospeech.SynthesizeSpeechRequest(
            input=synthesis_input,
            voice=voice_params,
            audio_config=audio_config,
        )

        logger.info(f"Sending request to Google TTS API. Lang: '{language_code}', Voice: '{effective_voice_name or 'API Default'}', Encoding: {audio_config_encoding.name}, Rate: {effective_speaking_rate:.2f}")

        try:
            response = await self.client.synthesize_speech(request=request)
            logger.info(f"Received response from Google TTS API ({len(response.audio_content)} bytes).")
            return response.audio_content
        except GoogleAPIError as e:
            logger.error(f"Google TTS API error: {e}", exc_info=True)
            raise SynthesisError(f"TTS API request failed: {e}", original_exception=e)
        except Exception as e:
            logger.error(f"Unexpected error during TTS synthesis: {e}", exc_info=True)
            raise SynthesisError(f"An unexpected error occurred during synthesis: {e}", original_exception=e)
