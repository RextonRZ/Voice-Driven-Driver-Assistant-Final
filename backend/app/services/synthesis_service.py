import logging
import base64
from typing import Optional

from ..core.clients.google_tts import GoogleTtsClient
from ..core.config import Settings
from ..core.exception import SynthesisError, InvalidRequestError

logger = logging.getLogger(__name__)

class SynthesisService:
    """Handles the text-to-speech synthesis logic."""

    def __init__(self, tts_client: GoogleTtsClient, settings: Settings):
        self.tts_client = tts_client
        self.settings = settings
        # Pre-normalize the map keys for efficiency
        self._normalized_voice_map = {k.lower(): v for k, v in self.settings.TTS_LANGUAGE_VOICE_MAP.items()}
        logger.debug("SynthesisService initialized.")


    def _select_voice_for_language(self, language_code: str) -> str | None:
        """Selects a specific voice name based on the language code."""
        normalized_lang_code = language_code.lower()
        mapped_voice = self._normalized_voice_map.get(normalized_lang_code)

        if mapped_voice:
            # logger.debug(f"Using specific voice '{mapped_voice}' for language '{language_code}'.")
            return mapped_voice
        else:
            # logger.debug(f"No specific voice map found for '{language_code}'. Using default: {self.settings.DEFAULT_TTS_VOICE_NAME}")
            return self.settings.DEFAULT_TTS_VOICE_NAME # Can be None

    async def text_to_speech(
        self,
        text: str,
        language_code: Optional[str], # BCP-47 code
        return_base64: bool = True
    ) -> bytes | str:
        """Synthesizes speech from text using language-specific voices."""
        logger.info("Starting text-to-speech synthesis.")

        if not text:
             logger.warning("Synthesis service received empty text.")
             return b"" if not return_base64 else ""

        effective_language_code = language_code or self.settings.DEFAULT_LANGUAGE_CODE
        if not effective_language_code:
             logger.error("No effective language code determined for TTS.")
             raise SynthesisError("Cannot synthesize speech without a language code.")

        voice_name = self._select_voice_for_language(effective_language_code)
        logger.debug(f"Requesting synthesis for lang '{effective_language_code}', voice '{voice_name or 'API Default'}'.")

        try:
            audio_bytes = await self.tts_client.synthesize(
                text=text,
                language_code=effective_language_code,
                voice_name=voice_name,
                speaking_rate=self.settings.DEFAULT_TTS_SPEAKING_RATE,
                audio_encoding=self.settings.TTS_AUDIO_ENCODING
            )

            if not audio_bytes:
                logger.warning("TTS client returned empty audio bytes.")
                return b"" if not return_base64 else ""

            logger.info(f"Text successfully synthesized ({len(audio_bytes)} bytes) for language: {effective_language_code}")

            if return_base64:
                return base64.b64encode(audio_bytes).decode('utf-8')
            else:
                return audio_bytes

        except SynthesisError as e:
            logger.error(f"Synthesis failed in service layer for language {effective_language_code}: {e}")
            raise e # Re-raise SynthesisError from client
        except Exception as e:
            logger.error(f"Unexpected error in synthesis service for language {effective_language_code}: {e}", exc_info=True)
            raise SynthesisError(f"An unexpected error occurred during synthesis: {e}", original_exception=e)