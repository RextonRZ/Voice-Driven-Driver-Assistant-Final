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

        default_lang = self.settings.DEFAULT_LANGUAGE_CODE
        supported_langs = self.settings.SUPPORTED_LANGUAGES or []  # Handle empty list

        # Create the list of alternatives (all supported except the default one)
        # Compare using lowercase to avoid case sensitivity issues, but use original case for API
        normalized_default_lang = default_lang.lower()
        alternative_langs_for_api = [
            lang for lang in supported_langs if lang.lower() != normalized_default_lang
        ]
        # --------------------------------------------------------------------

        logger.debug(f"STT Config - Model: {self.settings.STT_MODEL}, "
                     f"Punctuation: {self.settings.STT_ENABLE_AUTOMATIC_PUNCTUATION}, "
                     f"Encoding: {input_encoding.name}, Rate: {sample_rate_hertz}, "
                     f"Primary Lang: {default_lang}, "
                     f"Alternative Langs ({len(alternative_langs_for_api)}): {alternative_langs_for_api[:5]}..., "  # Log first few alternatives
                     f"Hint provided: {language_code_hint or 'None'}")

        config = speech.RecognitionConfig(
            encoding=input_encoding,
            sample_rate_hertz=sample_rate_hertz,
            language_code=default_lang,  # Use the fixed default language
            alternative_language_codes=alternative_langs_for_api,  # Use other supported languages as alternatives
            enable_automatic_punctuation=self.settings.STT_ENABLE_AUTOMATIC_PUNCTUATION,
            use_enhanced=True if self.settings.STT_MODEL else False,
            model=self.settings.STT_MODEL if self.settings.STT_MODEL else None,
            # adaptation=... # Add if needed
        )

        recognition_audio = speech.RecognitionAudio(content=audio_data)
        request = speech.RecognizeRequest(config=config, audio=recognition_audio)

        try:
            # Log the config being sent (optional, can be verbose)
            # try:
            #     config_dict = type(config).to_dict(config)
            #     logger.debug(f"Sending RecognitionConfig to Google STT API: {json.dumps(config_dict, indent=2)}")
            # except Exception:
            #      logger.debug(f"Sending RecognitionConfig to Google STT API (raw): {config}")

            logger.info("Sending request to Google STT API...")
            response = await self.client.recognize(request=request)
            # Log the raw response object - helpful for debugging empty transcripts/detection issues
            logger.debug(f"Raw Google STT API response object: {response}")
            logger.info("Received response from Google STT API.")

            # --- Process results (Mostly same as 'not working' version, but applied to correct config) ---
            transcript = ""
            # Store the detected language code exactly as returned by the API (original case)
            detected_language_bcp47 = None
            highest_confidence = -1.0  # Keep track of confidence

            if response.results:
                best_result = response.results[0]
                # Get language code directly from the result object if available
                if best_result.language_code:
                    detected_language_bcp47 = best_result.language_code
                    logger.debug(f"STT result language code directly from result: '{detected_language_bcp47}'")
                else:
                    # Sometimes language code might be on the alternative, check later
                    logger.debug("Language code not found directly on the STT result object.")

                # Process alternatives for transcript and confidence
                if best_result.alternatives:
                    # Often only one alternative is returned by default, but iterate just in case
                    for i, alternative in enumerate(best_result.alternatives):
                        logger.debug(
                            f"Alternative {i}: Confidence={alternative.confidence:.4f}, Transcript='{alternative.transcript[:50]}...'")
                        if alternative.confidence > highest_confidence:
                            transcript = alternative.transcript
                            highest_confidence = alternative.confidence
                            # If language wasn't on the main result, check the best alternative
                            if not detected_language_bcp47 and hasattr(alternative,
                                                                       'language_code') and alternative.language_code:
                                detected_language_bcp47 = alternative.language_code
                                logger.debug(
                                    f"Detected language '{detected_language_bcp47}' obtained from best alternative.")

                    logger.debug(f"Selected transcript: '{transcript[:50]}...' (Confidence: {highest_confidence:.4f})")
                else:
                    logger.warning("STT result contained no alternatives to extract transcript from.")

            else:
                logger.warning("STT API response contained no results.")

            # --- Log warnings based on detection outcome ---
            if not transcript and detected_language_bcp47:
                logger.warning(f"STT returned detected language '{detected_language_bcp47}' but an empty transcript.")
            elif not transcript and not detected_language_bcp47:
                logger.warning("STT returned empty transcript and no detected language.")
            elif transcript and not detected_language_bcp47:
                logger.warning(
                    f"STT returned transcript but failed to detect language. Transcript: '{transcript[:50]}...'")

            # Optional: Check if detected language is within the *expected* supported list (using lowercase comparison)
            if detected_language_bcp47:
                normalized_detected = detected_language_bcp47.lower()
                normalized_supported = [lang.lower() for lang in supported_langs]
                normalized_default = default_lang.lower()
                if normalized_detected not in normalized_supported and normalized_detected != normalized_default:
                    logger.warning(
                        f"Detected language '{detected_language_bcp47}' is not in the configured SUPPORTED_LANGUAGES list nor is it the DEFAULT_LANGUAGE_CODE. Proceeding anyway.")

            # Return the transcript and the detected language code (original case)
            return transcript.strip(), detected_language_bcp47

        except InvalidArgument as e:
            logger.error(
                f"Invalid argument for STT API. Processed audio or config likely invalid? Rate={sample_rate_hertz}Hz, Encoding={input_encoding.name}. Error: {e}",
                exc_info=True)
            # You could add more details from 'e' if needed
            raise InvalidRequestError(f"Invalid configuration or data for STT request: {e}", original_exception=e)
        except GoogleAPIError as e:
            logger.error(f"Google STT API error: {e}", exc_info=True)
            raise TranscriptionError(f"STT API request failed: {e}", original_exception=e)
        except Exception as e:
            logger.error(f"Unexpected error during STT transcription: {e}", exc_info=True)
            raise TranscriptionError(f"An unexpected error occurred during transcription: {e}", original_exception=e)