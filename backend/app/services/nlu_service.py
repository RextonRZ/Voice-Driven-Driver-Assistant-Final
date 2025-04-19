# backend/services/nlu_service.py
import logging
import json
import time  # Add this import
from typing import List, Dict, Any, Optional

from ..core.clients.gemini import GeminiClient
from ..core.config import Settings
from ..core.exception import NluError
from ..models.internal import ChatMessage, ChatHistory, NluIntent, NluResult

logger = logging.getLogger(__name__)

class NluService:
    """Handles interaction with the NLU (Gemini) model for intent recognition and entity extraction."""

    def __init__(self, gemini_client: GeminiClient, settings: Settings):
        self.gemini_client = gemini_client
        self.settings = settings
        # Prepare the intent list string for the prompt only once
        self._intent_list_str = ", ".join([intent.value for intent in NluIntent])

    def _prepare_history_for_model(self, history: ChatHistory) -> List[ChatMessage]:
        """Prepares chat history, potentially trimming it."""
        if len(history.messages) > self.settings.HISTORY_MAX_MESSAGES:
            # Keep only the last N pairs (N * 2 messages)
            start_index = max(0, len(history.messages) - self.settings.HISTORY_MAX_MESSAGES * 2)
            trimmed_messages = history.messages[start_index:]
            logger.debug(f"History trimmed from {len(history.messages)} to {len(trimmed_messages)} messages.")
            return trimmed_messages
        return history.messages

    def _parse_gemini_response(self, response_text: str) -> NluResult:
        """Attempts to parse the JSON string from Gemini into an NluResult model."""
        try:
            # Gemini might sometimes wrap the JSON in ```json ... ``` or add preamble/postamble text.
            # Basic cleaning: find the first '{' and last '}'
            json_start = response_text.find('{')
            json_end = response_text.rfind('}')
            if json_start != -1 and json_end != -1 and json_end > json_start:
                json_str = response_text[json_start : json_end + 1]
            else:
                json_str = response_text # Assume it might be valid JSON as is

            data = json.loads(json_str)

            # Validate required fields and intent enum
            intent_str = data.get("intent")
            try:
                intent = NluIntent(intent_str)
            except ValueError:
                logger.warning(f"Gemini returned unknown intent '{intent_str}'. Mapping to UNKNOWN.")
                intent = NluIntent.UNKNOWN

            entities = data.get("entities", {})
            confidence = data.get("confidence")
            response = data.get("response") # The natural language reply from Gemini

            if not response:
                 logger.warning("NLU JSON response from Gemini is missing the 'response' field.")
                 # Provide a generic fallback if Gemini didn't generate one
                 response = "Sorry, I encountered an issue understanding that." if intent == NluIntent.UNKNOWN else "Okay."


            # Basic type check for confidence
            if confidence is not None and not isinstance(confidence, (float, int)):
                 logger.warning(f"Gemini returned non-numeric confidence '{confidence}'. Setting to None.")
                 confidence = None
            elif confidence is not None:
                 confidence = float(confidence) # Ensure float

            return NluResult(
                intent=intent,
                entities=entities,
                confidence=confidence,
                fallback_response=response # Store Gemini's text response here
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON response from Gemini: {e}. Raw response: '{response_text[:500]}...'")
            # Return a default error NluResult
            return NluResult(
                intent=NluIntent.UNKNOWN,
                entities={},
                confidence=0.0,
                fallback_response="Sorry, I had trouble processing the response. Can you try rephrasing?"
            )
        except Exception as e:
            logger.error(f"Unexpected error parsing Gemini response: {e}. Raw response: '{response_text[:500]}...'", exc_info=True)
            return NluResult(
                intent=NluIntent.UNKNOWN,
                entities={},
                confidence=0.0,
                fallback_response="Sorry, an unexpected error occurred while understanding the response."
            )

    async def get_nlu_result(
        self,
        user_query: str,
        history: ChatHistory,
        context: Optional[Dict] = None
    ) -> NluResult:
        """
        Gets a structured NLU result (intent, entities) from Gemini.

        Args:
            user_query: The user's transcribed text query (in NLU processing language).
            history: The current ChatHistory object.
            context: Optional context dictionary (location, order status, etc.).

        Returns:
            An NluResult object.

        Raises:
            NluError: If the underlying Gemini API call fails critically.
        """
        logger.info("Getting structured NLU result from Gemini.")
        start_time = time.time()  # Start timing

        if not user_query:
            logger.warning("NLU service received empty user query.")
            # Return a specific NluResult for empty input
            return NluResult(
                intent=NluIntent.UNKNOWN,
                entities={},
                confidence=0.0,
                fallback_response="Sorry, I didn't catch that. Could you please repeat?"
            )

        prepared_history = self._prepare_history_for_model(history)

        # Format the system prompt with the current list of intents
        system_prompt = self.settings.NLU_INTENT_PROMPT.format(intents=self._intent_list_str)

        try:
            # Call Gemini client, expecting a JSON string back
            raw_response = await self.gemini_client.generate_structured_nlu_response(
                user_query=user_query,
                history=prepared_history,
                system_prompt=system_prompt,
                context=context
            )

            # Parse the raw response string
            nlu_result = self._parse_gemini_response(raw_response)
            logger.info(f"Parsed NLU Result - Intent: {nlu_result.intent.value}, Confidence: {nlu_result.confidence:.2f}, Entities: {nlu_result.entities}")
            return nlu_result

        except NluError as e:
            # Catch errors from the Gemini client call itself
            logger.error(f"NLU interaction with Gemini failed: {e}", exc_info=True)
            # Depending on the error, maybe return a fallback NluResult instead of raising?
            # For now, re-raise to let the ConversationService handle the failure flow.
            raise e # Re-raise NluError from the client
        except Exception as e:
            logger.error(f"Unexpected error in NLU service during Gemini interaction: {e}", exc_info=True)
            raise NluError(f"An unexpected error occurred during NLU processing: {e}", original_exception=e)
        finally:
            end_time = time.time()  # End timing
            logger.info(f"NLU processing time: {end_time - start_time:.2f} seconds")