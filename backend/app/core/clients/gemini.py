# backend/core/clients/gemini.py
import logging
import google.generativeai as genai
import json
from typing import List, Optional, Dict
import asyncio
import functools

from ..config import Settings
from ..exception import NluError, ConfigurationError
from ...models.internal import ChatMessage # Use internal ChatMessage

logger = logging.getLogger(__name__)

DEFAULT_SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

class GeminiClient:
    """Client for interacting with the Google Gemini API."""

    def __init__(self, settings: Settings):
        self.settings = settings
        if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
            logger.error("GEMINI_API_KEY is not configured.")
            raise ConfigurationError("GEMINI_API_KEY must be set in the environment or .env file.")
        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.model = genai.GenerativeModel(
                settings.GEMINI_MODEL_NAME,
                safety_settings=DEFAULT_SAFETY_SETTINGS  # Apply safety settings on model init
            )
            logger.info(f"Gemini client initialized with model: {settings.GEMINI_MODEL_NAME}")
        except Exception as e:
            logger.error(f"Failed to configure Gemini client: {e}", exc_info=True)
            raise ConfigurationError(f"Gemini client configuration failed: {e}", original_exception=e)

    def _format_history_for_gemini(self, history: List[ChatMessage]) -> List[Dict[str, str]]:
        """Converts internal ChatMessage list to Gemini's expected format."""
        gemini_history = []
        for msg in history:
            # Gemini expects 'user' and 'model' roles
            role = "model" if msg.role == "assistant" else msg.role
            gemini_history.append({"role": role, "parts": [msg.content]})
        return gemini_history

    async def generate_simple_response(self, prompt: str) -> str:
        """
        Generates a simple text response from Gemini, suitable for tasks like refinement.
        """
        if not prompt:
            logger.warning("generate_simple_response called with empty prompt.")
            return ""

        try:
            logger.debug(f"Sending simple generation request to Gemini. Prompt: '{prompt[:100]}...'")

            # Basic generation config - tune temperature if needed
            generation_config = genai.types.GenerationConfig(
                temperature=0.2,  # Lower temperature for more predictable refinement
                max_output_tokens=1024,  # Set a reasonable limit
            )

            # API calls are often synchronous, run in executor
            loop = asyncio.get_running_loop()
            send_message_with_args = functools.partial(
                self.model.generate_content,
                generation_config=generation_config,
                # Safety settings are applied at model level now
                # safety_settings=DEFAULT_SAFETY_SETTINGS, # Pass if not set globally
            )

            response = await loop.run_in_executor(
                None,
                send_message_with_args,
                prompt  # Pass positional content
            )

            # Check for blocked content or errors (important!)
            if not response.candidates:
                block_reason = getattr(getattr(response, 'prompt_feedback', None), 'block_reason', 'Unknown')
                safety_ratings_str = str(getattr(getattr(response, 'prompt_feedback', None), 'safety_ratings', 'N/A'))
                logger.warning(
                    f"Gemini simple response blocked or empty. Reason: {block_reason}. Safety Ratings: {safety_ratings_str}")
                # Check finish reason if available on the candidate
                finish_reason = "UNKNOWN"
                if hasattr(response, 'candidates') and response.candidates and hasattr(response.candidates[0],
                                                                                       'finish_reason'):
                    finish_reason = response.candidates[0].finish_reason.name
                # Do not raise an error here, return empty string so fallback can happen
                logger.warning(
                    f"Gemini simple response failed. Finish Reason: {finish_reason}. Returning empty string.")
                return ""  # Indicate failure gracefully

            # Access the text safely
            try:
                response_text = response.text
            except ValueError as e:
                # Handle cases where response.text might raise ValueError (e.g., finish_reason != STOP)
                logger.warning(
                    f"Could not extract text from Gemini simple response: {e}. Parts: {response.candidates[0].content.parts if response.candidates else 'N/A'}")
                return ""  # Return empty string on failure

            logger.debug(f"Gemini simple response received: '{response_text[:200]}...'")
            return response_text.strip()

        except (genai.types.BlockedPromptException, genai.types.StopCandidateException) as safety_error:
            logger.error(f"Gemini safety block or stop exception during simple generation: {safety_error}",
                         exc_info=False)  # Don't need full trace?
            return ""  # Indicate failure gracefully
        except Exception as e:
            logger.error(f"Error interacting with Gemini API for simple generation: {e}", exc_info=True)
            # For simple generation, maybe don't raise NluError, just return empty and let caller fallback?
            return ""

    async def generate_structured_nlu_response(
        self,
        user_query: str,
        history: List[ChatMessage],
        system_prompt: str, # The prompt instructing JSON output
        context: Optional[Dict] = None # Add context if needed
    ) -> str:
        """
        Generates a response from Gemini, expecting a specific structured output (JSON string).
        (Ensure system_prompt guides towards ONLY JSON output)
        """
        if not user_query:
             logger.warning("Gemini client received empty user query for NLU.")
             # Return a default JSON indicating failure
             return json.dumps({
                 "intent": "unknown",
                 "entities": {},
                 "confidence": 0.0,
                 "response": "I didn't receive any input. Could you please repeat?"
             }, ensure_ascii=False) # Use ensure_ascii=False for potential unicode

        gemini_history = self._format_history_for_gemini(history)
        full_user_prompt = f"Context: {json.dumps(context, ensure_ascii=False)}\n\nUser Query: {user_query}" if context else user_query

        # Construct the prompt/chat history
        # Strategy: Provide the JSON instruction prompt once at the beginning.
        prompt_parts = []
        # Check if history is needed or if system prompt should replace it for initial turn? Test.
        # For now, keep history + prepend system prompt to the LATEST user query.
        if not gemini_history: # If first turn, maybe combine sys prompt + user query?
            prompt_parts.append(f"{system_prompt}\n\n{full_user_prompt}")
        else:
            # If history exists, maintain it and add the latest query + system prompt.
            # Note: Newer Gemini might prefer system prompt separate. This mimics older APIs.
            # Put sys_prompt before user query
            prompt_parts.append(f"{system_prompt}\n\n{full_user_prompt}")


        try:
            logger.debug(f"Sending NLU request to Gemini. History length: {len(gemini_history)}. Prompt start: '{prompt_parts[0][:150]}...'")
            # Use start_chat if maintaining conversation state is desired by Gemini
            # If each call is independent state, generate_content might suffice. Chat seems better.
            chat = self.model.start_chat(history=gemini_history)

            # Configure generation - JSON focus
            generation_config = genai.types.GenerationConfig(
                temperature=0.3, # Lower temp for factual JSON structure
                max_output_tokens=1024, # Adjust if needed
                # response_mime_type="application/json" # EXPERIMENTAL: Use if supported by your model version
            )

            loop = asyncio.get_running_loop()
            send_message_with_args = functools.partial(
                chat.send_message, # Use chat instance
                generation_config=generation_config,
                # safety_settings=DEFAULT_SAFETY_SETTINGS, # Applied at model level
                # stream=False # Ensure streaming is off for single JSON blob
            )

            response = await loop.run_in_executor(
                None,
                send_message_with_args,
                prompt_parts # Send the prepared prompts/queries
            )

            # Check for blocked content or errors (Crucial for NLU)
            if not response.candidates:
                 block_reason = getattr(getattr(response, 'prompt_feedback', None), 'block_reason', 'Unknown')
                 safety_ratings_str = str(getattr(getattr(response, 'prompt_feedback', None), 'safety_ratings', 'N/A'))
                 logger.error(f"Gemini NLU response blocked or empty. Reason: {block_reason}. Safety Ratings: {safety_ratings_str}")
                 finish_reason = "UNKNOWN"
                 if hasattr(response, 'candidates') and response.candidates and hasattr(response.candidates[0], 'finish_reason'):
                     finish_reason = response.candidates[0].finish_reason.name
                 raise NluError(f"Gemini NLU response was empty or blocked. Finish Reason: {finish_reason}. Block Reason: {block_reason}")

            # Extract text, expecting JSON
            try:
                 response_text = response.text
            except ValueError as e:
                 # This is a critical failure for NLU
                 logger.error(f"Could not extract text from Gemini NLU response: {e}. Candidate: {response.candidates[0] if response.candidates else 'N/A'}")
                 raise NluError(f"Failed to extract text from Gemini NLU response: {e}", original_exception=e)


            logger.debug(f"Gemini raw NLU response: {response_text[:500]}...")
            # Return raw string - parsing happens in NluService
            return response_text.strip()

        except (genai.types.BlockedPromptException, genai.types.StopCandidateException) as safety_error:
             logger.error(f"Gemini safety block or stop exception during NLU generation: {safety_error}", exc_info=True)
             raise NluError(f"Gemini content policy violation or stop condition: {safety_error}", original_exception=safety_error)
        except Exception as e:
            logger.error(f"Error interacting with Gemini API for NLU: {e}", exc_info=True)
            raise NluError(f"Gemini API interaction failed: {e}", original_exception=e)