import logging
from typing import Dict, Optional
from google.cloud import translate_v2 as translate # v2 is simpler for basic use
# from google.cloud import translate # v3beta is more complex but offers more features
from google.api_core.exceptions import GoogleAPIError
import asyncio
import functools

from ..config import Settings, settings as global_settings
from ..exception import TranslationError, ConfigurationError, InvalidRequestError

logger = logging.getLogger(__name__)

# Mock implementation for structure - Replace with your actual GoogleTranslateClient
class GoogleTranslateClient:
    """Client for Google Cloud Translation API (v2)."""

    def __init__(self, settings: Settings):
        self.settings = settings
        try:
            # ADC preferred
            self.client = translate.Client()
            # Test connection (optional)
            # self.client.get_languages()
            logger.info("Google Translation v2 Client initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Google Translate client: {e}", exc_info=True)
            raise ConfigurationError(f"Google Translate client initialization failed: {e}", original_exception=e)

    async def translate_text(
        self,
        text: str | list[str],
        target_language: str, # ISO 639-1 code (e.g., "en", "ms")
        source_language: Optional[str] = None # ISO 639-1 code or None for auto-detect
    ) -> Dict | list[Dict]:
        """
        Translates text using Google Translate API.

        Args:
            text: The text string or list of strings to translate.
            target_language: The ISO 639-1 code of the language to translate to.
            source_language: Optional ISO 639-1 code of the source language.

        Returns:
            A dictionary (or list of dictionaries) containing:
            - 'translatedText': The translated text.
            - 'detectedSourceLanguage': The detected source language code (if source_language was None).
            - 'input': The original input text.

        Raises:
            TranslationError: If the API call fails.
            InvalidRequestError: If input parameters are invalid.
        """
        if not text:
            logger.warning("Translate called with empty text.")
            # Return structure consistent with API response for empty input
            if isinstance(text, list):
                 return [{'translatedText': '', 'input': t, 'detectedSourceLanguage': source_language} for t in text]
            else:
                 return {'translatedText': '', 'input': text, 'detectedSourceLanguage': source_language}

        if not target_language:
             raise InvalidRequestError("target_language is required for translation.")

        try:
             # The v2 client library methods are synchronous, so run them in an executor
             # to avoid blocking the FastAPI event loop.
             loop = asyncio.get_running_loop()
             logger.info(f"Requesting translation to '{target_language}' (Source: '{source_language or 'auto'}'). Running in executor.")

             translate_with_args = functools.partial(
                 self.client.translate,
                 target_language=target_language,
                 source_language=source_language or '',
                 format_='text'
             )

             # Run the partial function, passing the 'text' argument positionally
             result = await loop.run_in_executor(
                 None,
                 translate_with_args,  # Run the partial function
                 text  # Pass the main positional argument
             )
             logger.info(f"Translation successful. Detected source: '{result.get('detectedSourceLanguage', 'N/A') if isinstance(result, dict) else [r.get('detectedSourceLanguage', 'N/A') for r in result]}'")
             # The client returns dict or list of dicts matching the desired structure
             return result

        except GoogleAPIError as e:
             logger.error(f"Google Translate API error: {e}", exc_info=True)
             raise TranslationError(f"Translate API request failed: {e}", original_exception=e)
        except Exception as e:
             logger.error(f"Unexpected error during translation: {e}", exc_info=True)
             raise TranslationError(f"An unexpected error occurred during translation: {e}", original_exception=e)