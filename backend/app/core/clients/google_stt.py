import logging
from typing import Tuple, Optional
from google.cloud import speech
from google.api_core.exceptions import GoogleAPIError
import asyncio

from ..config import Settings, settings as global_settings
from ..exception import TranscriptionError, InvalidRequestError, ConfigurationError

logger = logging.getLogger(__name__)

# Mock implementation for structure - Replace with your actual GoogleSttClient
class GoogleSttClient:
    """Client for Google Cloud Speech-to-Text API."""

    def __init__(self, settings: Settings):
        self.settings = settings
        try:
            self.client = speech.SpeechAsyncClient()
            logger.info("Google Speech-to-Text AsyncClient initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Google STT client: {e}", exc_info=True)
            raise ConfigurationError(f"Google STT client initialization failed: {e}", original_exception=e)

    async def transcribe(
        self,
        audio_data: bytes,
        sample_rate_hertz: int,
        input_encoding: speech.RecognitionConfig.AudioEncoding,
        language_code_hint: Optional[str] = None # Optional BCP-47 hint
    ) -> Tuple[str, Optional[str]]:
        """
        Transcribes audio data using Google STT with auto language detection.

        Args:
            audio_data: Raw audio bytes (ensure LINEAR16 or compatible).
            sample_rate_hertz: Sample rate of the audio.
            input_encoding: Encoding of the audio (e.g., LINEAR16).
            language_code_hint: Optional preferred language code (BCP-47).

        Returns:
            A tuple containing:
                - The transcribed text (str).
                - The detected language code (BCP-47 str) or None if detection failed.

        Raises:
            TranscriptionError: If the API call fails.
            InvalidRequestError: If input parameters are invalid.
        """
        if not audio_data:
            logger.warning("Transcribe called with empty audio data.")
            return "", None
        if not sample_rate_hertz or sample_rate_hertz <= 0:
             raise InvalidRequestError("Valid sample_rate_hertz is required for transcription.")

        recognition_audio = speech.RecognitionAudio(content=audio_data)

        # Configure for auto-detection, potentially biased by hint or supported list
        possible_languages = list(set([lang.lower() for lang in self.settings.SUPPORTED_LANGUAGES]))
        if language_code_hint and language_code_hint.lower() in possible_languages:
             # Prioritize the hint if it's supported
             possible_languages.insert(0, language_code_hint.lower())
        # Ensure default is included if not already there
        if self.settings.DEFAULT_LANGUAGE_CODE.lower() not in possible_languages:
            possible_languages.append(self.settings.DEFAULT_LANGUAGE_CODE.lower())

        logger.debug(f"STT Config - Model: {self.settings.STT_MODEL}, "
                     f"Punctuation: {self.settings.STT_ENABLE_AUTOMATIC_PUNCTUATION}, "
                     f"Encoding: {input_encoding.name}, Rate: {sample_rate_hertz}, "
                     f"Possible Languages: {possible_languages[:5]}...") # Log first few

        config = speech.RecognitionConfig(
            encoding=input_encoding,
            sample_rate_hertz=sample_rate_hertz,
            language_code=possible_languages[0], # Primary language set for basic config
            alternative_language_codes=possible_languages[1:], # Others for auto-detection
            enable_automatic_punctuation=self.settings.STT_ENABLE_AUTOMATIC_PUNCTUATION,
            use_enhanced=True if self.settings.STT_MODEL else False, # Use enhanced if model specified
            model=self.settings.STT_MODEL if self.settings.STT_MODEL else None,
            # Speech adaptation can be added here if configured in settings
            # adaptation=speech.SpeechAdaptation(...)
        )

        request = speech.RecognizeRequest(config=config, audio=recognition_audio)

        try:
            logger.info("Sending request to Google STT API...")
            response = await self.client.recognize(request=request)
            logger.info("Received response from Google STT API.")

            # Process results
            transcript = ""
            detected_language = None
            highest_confidence = -1.0

            if response.results:
                # Find the best result (usually the first one if alternatives aren't requested heavily)
                # Check language code of the most confident alternative
                best_result = response.results[0]
                if best_result.language_code:
                     detected_language = best_result.language_code
                     logger.debug(f"STT result language code: {detected_language}")

                # Concatenate transcripts from alternatives within the best result
                for alternative in best_result.alternatives:
                     # Using the alternative with highest confidence, though often only one is returned without explicit settings
                     if alternative.confidence > highest_confidence:
                         transcript = alternative.transcript
                         highest_confidence = alternative.confidence
                         logger.debug(f"Transcript selected (confidence: {highest_confidence:.2f}): '{transcript[:50]}...'")
                         if not detected_language and hasattr(alternative, 'language_code'):
                            detected_language = alternative.language_code

            if not transcript and detected_language:
                logger.warning(f"STT returned detected language '{detected_language}' but an empty transcript.")
            elif not transcript and not detected_language:
                 logger.warning("STT returned empty transcript and no detected language.")
            elif not detected_language:
                 logger.warning(f"STT returned transcript but no detected language: '{transcript[:50]}...'")


            # Fallback or correction logic for language code if needed
            if detected_language and detected_language.lower() not in [l.lower() for l in self.settings.SUPPORTED_LANGUAGES]:
                logger.warning(f"STT detected language '{detected_language}' which is not in the explicitly supported list. Proceeding anyway.")
            elif not detected_language:
                logger.warning(f"STT failed to detect language. Falling back to default: {self.settings.DEFAULT_LANGUAGE_CODE}")
                # Decide if you want to return the default or None
                # detected_language = self.settings.DEFAULT_LANGUAGE_CODE # Option 1: Assume default
                detected_language = None # Option 2: Indicate failure

            return transcript.strip(), detected_language

        except GoogleAPIError as e:
            logger.error(f"Google STT API error: {e}", exc_info=True)
            raise TranscriptionError(f"STT API request failed: {e}", original_exception=e)
        except Exception as e:
            logger.error(f"Unexpected error during STT transcription: {e}", exc_info=True)
            # Catch potential asyncio issues or client errors not covered by GoogleAPIError
            raise TranscriptionError(f"An unexpected error occurred during transcription: {e}", original_exception=e)