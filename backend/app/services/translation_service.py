import logging
from typing import Optional, Tuple

from ..core.clients.google_translate import GoogleTranslateClient
from ..core.exception import TranslationError
from ..core.config import Settings
from ..core.exception import TranslationError as ServiceTranslationError # Alias if needed

logger = logging.getLogger(__name__)

ISO_TO_BCP47_MAP = {
    "en": "en-US",
    "ms": "ms-MY",
    "id": "id-ID",
    "fil": "fil-PH",
    "th": "th-TH",
    "vi": "vi-VN",
    "km": "km-KH",
    "my": "my-MM",
    "zh-cn": "cmn-Hans-CN", # Translate often detects zh-CN or zh-TW
    "zh-tw": "cmn-Hant-TW", # Use Hant for traditional
    "zh": "cmn-Hans-CN",    # Default Chinese to simplified
    "ta": "ta-IN",
    # Add others...
}

class TranslationService:
    """Handles text translation logic."""

    def __init__(self, translate_client: GoogleTranslateClient, settings: Settings):
        self.client = translate_client
        self.settings = settings
        self.target_language = settings.NLU_PROCESSING_LANGUAGE # e.g., 'en'
        logger.debug(f"TranslationService initialized. NLU Target Lang: {self.target_language}")

    def _extract_language_code(self, bcp47_code: str) -> str:
        """Extracts the base ISO 639-1 code from a BCP-47 code (e.g., 'en-US' -> 'en')."""
        if not bcp47_code: return ""
        return bcp47_code.split('-')[0].lower()

    async def translate_to_nlu_language(self, text: str, source_bcp47_code: Optional[str]) -> Tuple[str, str]:
        """
        Translates text from the source language to the NLU processing language.

        Returns: (translated_text, source_iso_code_used)
        """
        if not text:
            return "", self._extract_language_code(source_bcp47_code or self.settings.DEFAULT_LANGUAGE_CODE)

        source_iso_code = self._extract_language_code(source_bcp47_code or self.settings.DEFAULT_LANGUAGE_CODE)

        if source_iso_code == self.target_language:
            logger.debug(f"Input text already in NLU target language '{self.target_language}'. No translation needed.")
            return text, source_iso_code

        logger.debug(f"Translating text from '{source_iso_code}' to NLU target '{self.target_language}'.")
        try:
            result = await self.client.translate_text(
                text=text,
                target_language=self.target_language,
                source_language=source_iso_code # Provide source hint
            )
            translated_text = result.get('translatedText', '')
            detected_source = result.get('detectedSourceLanguage', source_iso_code) # Use hint as fallback

            if not translated_text and text:
                 logger.warning(f"Translation to '{self.target_language}' resulted in empty text. Returning original.")
                 return text, detected_source

            logger.info(f"Input text translated to '{self.target_language}' (Detected Source: {detected_source}).")
            return translated_text, detected_source

        except (TranslationError, Exception) as e:
            logger.error(f"Failed to translate text to NLU language: {e}", exc_info=True)
            # Fallback: return original text if translation fails
            logger.warning("Translation failed. Proceeding with original text for NLU.")
            return text, source_iso_code

    async def translate_from_nlu_language(self, text: str, target_bcp47_code: str) -> str:
        """
        Translates text from the NLU processing language back to the target language.
        """
        if not text:
            return ""

        target_iso_code = self._extract_language_code(target_bcp47_code)

        if target_iso_code == self.target_language:
            logger.debug(f"Target language '{target_bcp47_code}' matches NLU language. No translation needed.")
            return text

        logger.debug(f"Translating NLU response from '{self.target_language}' back to '{target_iso_code}'.")
        try:
            result = await self.client.translate_text(
                text=text,
                target_language=target_iso_code,
                source_language=self.target_language # Source is known
            )
            translated_text = result.get('translatedText', '')

            if not translated_text and text:
                logger.warning(f"Translation back to '{target_iso_code}' resulted in empty text. Returning original NLU text.")
                return text

            logger.info(f"NLU response translated back to '{target_iso_code}'.")
            return translated_text

        except (TranslationError, Exception) as e:
            logger.error(f"Failed to translate NLU response back to target language: {e}", exc_info=True)
            # Fallback: return the untranslated NLU response
            logger.warning("Translation failed. Returning original NLU response text.")
            return text

    async def detect_language_of_text(self, text: str) -> Optional[str]:
        """
        Detects the language of a text string and returns its likely BCP-47 code.
        Returns None if detection fails or is undetermined.
        """
        if not text:
            return None
        try:
            detection_result = await self.client.detect_language(text)
            # Result is a dict: {'language': 'fi', 'confidence': 0.65, 'input': '...'}
            detected_iso = detection_result.get('language')
            confidence = detection_result.get('confidence', 0.0)

            if detected_iso and detected_iso != 'und' and confidence > 0.5:  # Add confidence threshold
                # Map ISO code back to a BCP-47 code (using our helper map)
                bcp47_code = ISO_TO_BCP47_MAP.get(detected_iso, None)
                if not bcp47_code:
                    # Fallback if specific BCP-47 isn't mapped: just use the ISO code?
                    # Or maybe construct a basic one? Let's return None for now if unmapped.
                    logger.warning(
                        f"Detected language ISO code '{detected_iso}' has no defined BCP-47 mapping in ISO_TO_BCP47_MAP. Cannot determine BCP-47.")
                    return None
                    # Alternative: return f"{detected_iso}-{detected_iso.upper()}" # e.g., fi-FI (guessing region)

                logger.info(
                    f"Detected language of fallback transcript as: {detected_iso} -> {bcp47_code} (Confidence: {confidence:.2f})")
                return bcp47_code
            else:
                logger.warning(
                    f"Language detection for fallback transcript returned undetermined or low confidence. ISO: {detected_iso}, Conf: {confidence:.2f}")
                return None
        except (TranslationError, Exception) as e:
            logger.error(f"Language detection failed: {e}", exc_info=True)
            return None  # Return None on error