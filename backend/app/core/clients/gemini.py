# backend/core/clients/gemini.py
import logging
import google.generativeai as genai
import json
from typing import List, Optional, Dict
import asyncio

from ..config import Settings
from ..exception import NluError, ConfigurationError
from ...models.internal import ChatMessage # Use internal ChatMessage

logger = logging.getLogger(__name__)

class GeminiClient:
    """Client for interacting with the Google Gemini API."""

    def __init__(self, settings: Settings):
        self.settings = settings
        if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
            logger.error("GEMINI_API_KEY is not configured.")
            raise ConfigurationError("GEMINI_API_KEY must be set in the environment or .env file.")
        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.model = genai.GenerativeModel(settings.GEMINI_MODEL_NAME)
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

    async def generate_structured_nlu_response(
        self,
        user_query: str,
        history: List[ChatMessage],
        system_prompt: str, # The prompt instructing JSON output
        context: Optional[Dict] = None # Add context if needed
    ) -> str:
        """
        Generates a response from Gemini, expecting a specific structured output (e.g., JSON).

        Args:
            user_query: The latest user query.
            history: The list of previous ChatMessages.
            system_prompt: The detailed instruction prompt for Gemini.
            context: Optional dictionary with contextual information.

        Returns:
            The raw text response from Gemini (expected to be JSON string).

        Raises:
            NluError: If the API call fails or returns an unexpected response.
        """
        if not user_query:
             logger.warning("Gemini client received empty user query.")
             # Return a default JSON indicating failure or let the NLU service handle it
             return json.dumps({
                 "intent": "unknown",
                 "entities": {},
                 "confidence": 0.0,
                 "response": "I didn't receive any input. Could you please repeat?"
             })

        gemini_history = self._format_history_for_gemini(history)

        # Construct the full prompt including context if available
        full_user_prompt = f"Context: {json.dumps(context)}\n\nUser Query: {user_query}" if context else user_query

        try:
            logger.debug(f"Sending request to Gemini. History length: {len(gemini_history)}. Query: '{user_query[:100]}...'")
            # Use start_chat for conversation context
            chat = self.model.start_chat(history=gemini_history)

            # Configure generation - enforce JSON output if possible with the model version
            # Note: Official JSON mode might require specific model versions or prompt structures
            generation_config = genai.types.GenerationConfig(
                # candidate_count=1, # Usually default
                # stop_sequences=['\n'], # Be careful with stop sequences
                # max_output_tokens=1024,
                temperature=0.7, # Adjust creativity vs factualness
                # response_mime_type="application/json" # Use if model supports it directly
            )

            # Prepend the system prompt (instructions) before the user query
            # Gemini's newer APIs might handle system prompts differently, check documentation
            # For now, include it as part of the first user message or context if chat history is empty
            # Or prepend it clearly to the current query if history exists.
            prompt_to_send = f"{system_prompt}\n\n{full_user_prompt}"
            # If history exists, maybe just send the user query and rely on the history + initial prompt? Test this.
            # if gemini_history:
            #     prompt_to_send = full_user_prompt


            # Gemini API calls are often synchronous in the SDK, run in executor
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                 None,
                 chat.send_message,
                 prompt_to_send,
                 generation_config=generation_config,
                 # stream=False # Ensure we get the full response
            )

            # Check for blocked content or errors
            if not response.candidates or not hasattr(response.candidates[0], 'content') or not response.candidates[0].content.parts:
                 # Handle safety blocks or empty responses
                 block_reason = response.prompt_feedback.block_reason if hasattr(response.prompt_feedback, 'block_reason') else 'Unknown'
                 safety_ratings = response.prompt_feedback.safety_ratings if hasattr(response.prompt_feedback, 'safety_ratings') else 'N/A'
                 logger.warning(f"Gemini response blocked or empty. Reason: {block_reason}. Safety Ratings: {safety_ratings}")

                 # Attempt to get finish_reason if available in candidate
                 finish_reason = "UNKNOWN"
                 if response.candidates and hasattr(response.candidates[0], 'finish_reason'):
                    finish_reason = response.candidates[0].finish_reason.name

                 raise NluError(f"Gemini response was empty or blocked. Finish Reason: {finish_reason}. Block Reason: {block_reason}")


            assistant_response_text = response.text # Accessing .text concatenates parts

            logger.debug(f"Gemini raw response: {assistant_response_text[:200]}...") # Log beginning of response
            return assistant_response_text.strip()

        except (genai.types.BlockedPromptException, genai.types.StopCandidateException) as safety_error:
             logger.error(f"Gemini safety block or stop exception: {safety_error}", exc_info=True)
             raise NluError(f"Gemini content policy violation or stop condition: {safety_error}", original_exception=safety_error)
        except Exception as e:
            logger.error(f"Error interacting with Gemini API: {e}", exc_info=True)
            # Catch potential network errors, API key issues, etc.
            raise NluError(f"Gemini API interaction failed: {e}", original_exception=e)