# backend/services/nlu_service.py
import logging
import json
from typing import List, Dict, Any, Optional
# Need pycountry for language names from codes
try:
    import pycountry
except ImportError:
    pycountry = None
    logging.warning("pycountry not installed (`pip install pycountry`). Language name lookup will be basic.")

from ..core.clients.gemini import GeminiClient
from ..core.config import Settings
from ..core.exception import NluError
from ..models.internal import ChatMessage, ChatHistory, NluIntent, NluResult

logger = logging.getLogger(__name__)

# Cache for language names
_language_name_cache = {}

def _get_language_name(bcp47_code: str) -> str:
    """Gets the English name of a language from its BCP-47 code."""
    if not bcp47_code:
        return "Unknown Language"
    if bcp47_code in _language_name_cache:
        return _language_name_cache[bcp47_code]

    lang_code = bcp47_code.split('-')[0].lower()
    name = f"Unknown Language ({lang_code})" # Default fallback

    if pycountry:
        try:
            lang_obj = pycountry.languages.get(alpha_2=lang_code)
            if lang_obj:
                name = lang_obj.name
            else:
                 # Try alpha_3 if alpha_2 fails? Less common for BCP-47 mapping
                 lang_obj = pycountry.languages.get(alpha_3=lang_code)
                 if lang_obj: name = lang_obj.name

        except Exception as e:
            logger.warning(f"pycountry lookup failed for code '{lang_code}': {e}")
            # Use the fallback name already defined
    else:
        # Basic fallback map if pycountry is not installed
        basic_map = {"en": "English", "ms": "Malay", "id": "Indonesian", "fil": "Filipino", "th": "Thai", "vi": "Vietnamese", "km": "Khmer", "my": "Burmese", "zh": "Chinese", "ta":"Tamil"} # Common Southeast Asian langs
        name = basic_map.get(lang_code, f"Language code {lang_code}")

    _language_name_cache[bcp47_code] = name
    return name

class NluService:
    """Handles interaction with the NLU (Gemini) model for intent recognition and entity extraction."""

    def __init__(self, gemini_client: GeminiClient, settings: Settings):
        self.gemini_client = gemini_client
        self.settings = settings
        # Prepare the intent list string for the prompt only once
        self._intent_list_str = ", ".join([intent.value for intent in NluIntent])
        logger.debug("NluService initialized.")

    async def refine_transcription(self, original_text: str, language_bcp47: str) -> str:
        """
        Uses Gemini to refine a raw transcription for clarity and potential errors.

        Args:
            original_text: The raw text from STT.
            language_bcp47: The detected language code (e.g., 'ms-MY').

        Returns:
            The refined text, or the original text if refinement fails or is disabled.
        """
        if not self.settings.ENABLE_TRANSCRIPTION_REFINEMENT:
            logger.debug("Transcription refinement is disabled by settings.")
            return original_text
        if not original_text:
            logger.debug("Skipping refinement for empty original text.")
            return original_text
        if not language_bcp47:
             logger.warning("Cannot refine transcription without a language code. Returning original text.")
             return original_text

        language_name = _get_language_name(language_bcp47)
        prompt = self.settings.NLU_REFINEMENT_PROMPT.format(
            language_name=language_name,
            language_code=language_bcp47,
            original_text=original_text
        )

        logger.info(f"Attempting to refine transcription (lang: {language_bcp47}). Original: '{original_text[:100]}...'")
        try:
            # Use the simpler text generation method
            refined_text = await self.gemini_client.generate_simple_response(prompt)

            if refined_text:
                # Basic check: don't return overly short/empty refinements if original was longer
                if len(refined_text) < len(original_text) * 0.5 and len(original_text) > 20:
                     logger.warning(f"Refinement produced significantly shorter text. Returning original. (Orig: {len(original_text)}, Refined: {len(refined_text)})")
                     return original_text
                logger.info(f"Transcription refined. Refined: '{refined_text[:100]}...'")
                return refined_text
            else:
                logger.warning("Gemini refinement returned empty response. Using original text.")
                return original_text

        except Exception as e:
            # Catch any unexpected error during refinement call itself
            logger.error(f"Error during Gemini refinement call: {e}", exc_info=True)
            logger.warning("Transcription refinement failed. Using original text.")
            return original_text # Fallback to original text


    def _prepare_history_for_model(self, history: ChatHistory) -> List[ChatMessage]:
        """Prepares chat history, potentially trimming it."""
        # Use existing logic
        max_pairs = self.settings.HISTORY_MAX_MESSAGES
        max_messages = max_pairs * 2
        if len(history.messages) > max_messages:
            start_index = len(history.messages) - max_messages
            trimmed_messages = history.messages[start_index:]
            logger.debug(f"History trimmed from {len(history.messages)} to {len(trimmed_messages)} messages.")
            return trimmed_messages
        return history.messages


    def _parse_gemini_nlu_json_response(self, response_text: str) -> NluResult:
        """Attempts to parse the JSON string from Gemini NLU response into an NluResult model."""
        # Original parsing logic seems robust, keep it
        try:
            # Clean potential markdown code fences ```json ... ```
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            # Find the first '{' and last '}' to handle potential preamble/postamble text
            json_start = response_text.find('{')
            json_end = response_text.rfind('}')
            if json_start != -1 and json_end != -1 and json_end >= json_start:
                json_str = response_text[json_start : json_end + 1]
            else:
                json_str = response_text # Hope for the best if braces are missing

            data = json.loads(json_str)

            # Validate intent
            intent_str = data.get("intent")
            try:
                intent = NluIntent(intent_str)
            except ValueError:
                logger.warning(f"Gemini returned unknown intent '{intent_str}'. Mapping to UNKNOWN.")
                intent = NluIntent.UNKNOWN

            # Extract other fields, providing defaults or handling errors
            entities = data.get("entities", {})
            if not isinstance(entities, dict):
                 logger.warning(f"NLU response 'entities' field is not a dict: {entities}. Using empty dict.")
                 entities = {}

            confidence = data.get("confidence")
            try:
                 confidence = float(confidence) if confidence is not None else None
                 if confidence is not None and not (0.0 <= confidence <= 1.0):
                     logger.warning(f"NLU confidence '{confidence}' out of range [0, 1]. Clamping or setting None.")
                     confidence = max(0.0, min(1.0, confidence)) # Clamp or set None? Let's clamp.
            except (ValueError, TypeError):
                 logger.warning(f"NLU response 'confidence' field is not a valid number: {confidence}. Setting to None.")
                 confidence = None


            response = data.get("response") # The natural language reply generated by Gemini for NLU
            if not response or not isinstance(response, str):
                 logger.warning("NLU JSON response from Gemini is missing or has invalid 'response' field.")
                 # Provide a generic fallback if Gemini didn't generate one
                 response = "Okay." if intent != NluIntent.UNKNOWN else "Sorry, I'm not sure how to respond."


            return NluResult(
                intent=intent,
                entities=entities,
                confidence=confidence,
                fallback_response=response # Store Gemini's generated NLU response here
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode NLU JSON response from Gemini: {e}. Raw response: '{response_text[:500]}...'")
            return NluResult(
                intent=NluIntent.UNKNOWN,
                entities={},
                confidence=0.0,
                fallback_response="Sorry, I couldn't process the information structure correctly."
            )
        except Exception as e:
            logger.error(f"Unexpected error parsing Gemini NLU JSON response: {e}. Raw response: '{response_text[:500]}...'", exc_info=True)
            return NluResult(
                intent=NluIntent.UNKNOWN,
                entities={},
                confidence=0.0,
                fallback_response="Sorry, an unexpected error occurred while understanding the structure of the response."
            )

    async def get_nlu_result(
        self,
        user_query: str, # Should be the *translated* query for NLU
        history: ChatHistory,
        context: Optional[Dict] = None
    ) -> NluResult:
        """
        Gets a structured NLU result (intent, entities) from Gemini using the translated query.
        """
        logger.info("Getting structured NLU result from Gemini (post-translation).")

        if not user_query:
            logger.warning("NLU service received empty translated user query.")
            # Return a specific NluResult for empty input
            return NluResult(
                intent=NluIntent.UNKNOWN,
                entities={},
                confidence=0.0,
                fallback_response="Sorry, I didn't get any translated input to understand."
            )

        prepared_history = self._prepare_history_for_model(history)

        # Use the intent extraction prompt
        system_prompt = self.settings.NLU_INTENT_PROMPT.format(intents=self._intent_list_str)

        try:
            # Call Gemini client, expecting a JSON string back
            raw_nlu_response = await self.gemini_client.generate_structured_nlu_response(
                user_query=user_query, # Send the translated query
                history=prepared_history, # History (should ideally match language of NLU)
                system_prompt=system_prompt,
                context=context
            )

            # Parse the raw JSON response string
            nlu_result = self._parse_gemini_nlu_json_response(raw_nlu_response)
            logger.info(f"Parsed NLU Result - Intent: {nlu_result.intent.value}, Confidence: {nlu_result.confidence}, Entities: {nlu_result.entities}")
            return nlu_result

        except NluError as e:
            # Catch errors from the Gemini client call itself
            logger.error(f"NLU interaction with Gemini failed: {e}", exc_info=True)
            # Raise to let ConversationService handle the failure flow
            raise e
        except Exception as e:
            logger.error(f"Unexpected error in NLU service during Gemini NLU interaction: {e}", exc_info=True)
            raise NluError(f"An unexpected error occurred during NLU processing: {e}", original_exception=e)