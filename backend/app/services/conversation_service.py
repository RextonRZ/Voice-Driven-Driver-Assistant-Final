# backend/services/conversation_service.py
import logging
from datetime import datetime
from typing import Dict, Tuple, Optional, Any
import asyncio

from ..models.internal import ChatHistory, ChatMessage, NluIntent, NluResult, RouteInfo, OrderContext
from ..models.request import ProcessAudioRequest
from ..models.response import AssistantResponse
from ..services.transcription_service import TranscriptionService
from ..services.nlu_service import NluService
from ..services.synthesis_service import SynthesisService
from ..services.translation_service import TranslationService
from ..services.navigation_service import NavigationService
from ..services.safety_service import SafetyService # Import SafetyService
# Potentially add a CommunicationService later for sending messages
# from services.communication_service import CommunicationService
from ..core.config import Settings
from ..core.exception import (
    AssistantBaseException, InvalidRequestError, TranscriptionError,
    NluError, TranslationError, SynthesisError, NavigationError, StateError,
    CommunicationError, SafetyError
)

logger = logging.getLogger(__name__)

# Simple in-memory storage for chat histories.
# Replace with Redis or DB for persistence/scaling.
_chat_histories: Dict[str, ChatHistory] = {}

class ConversationService:
    """Orchestrates the voice assistant conversation flow including intent dispatching."""

    def __init__(
        self,
        transcription_service: TranscriptionService,
        translation_service: TranslationService,
        nlu_service: NluService,
        synthesis_service: SynthesisService,
        navigation_service: NavigationService,
        safety_service: SafetyService, # Add SafetyService
        # communication_service: CommunicationService, # Add later
        settings: Settings
    ):
        self.transcription_service = transcription_service
        self.translation_service = translation_service
        self.nlu_service = nlu_service
        self.synthesis_service = synthesis_service
        self.navigation_service = navigation_service
        self.safety_service = safety_service # Store SafetyService
        # self.communication_service = communication_service
        self.settings = settings
        self.chat_histories = _chat_histories
        self.nlu_target_language = self.settings.NLU_PROCESSING_LANGUAGE
        logger.debug("ConversationService initialized with all dependent services.")

    def _get_or_create_history(self, session_id: str) -> ChatHistory:
        """Retrieves or initializes chat history for a session."""
        history = self.chat_histories.get(session_id)
        if not history:
            logger.info(f"Creating new chat history for session_id: {session_id}")
            history = ChatHistory(session_id=session_id)
            self.chat_histories[session_id] = history
        return history

    def _update_history(self, session_id: str, user_message: str, assistant_message: str):
        """Adds user and assistant messages to the history, trimming if needed."""
        history = self.chat_histories.get(session_id)
        if not history:
            logger.warning(f"Attempted to update history for non-existent session_id: {session_id}. Creating new history.")
            history = self._get_or_create_history(session_id)

        # Add messages
        history.messages.append(ChatMessage(role="user", content=user_message))
        history.messages.append(ChatMessage(role="assistant", content=assistant_message))

        # Trim history (keep last N pairs)
        max_len = self.settings.HISTORY_MAX_MESSAGES * 2
        if len(history.messages) > max_len:
             excess = len(history.messages) - max_len
             history.messages = history.messages[excess:]
             logger.debug(f"History for session {session_id} trimmed to {len(history.messages)} messages.")

    async def _handle_intent(
        self,
        nlu_result: NluResult,
        request: ProcessAudioRequest,
        history: ChatHistory
        ) -> Tuple[str, Optional[Any]]:
        """
        Dispatches the request to the appropriate service based on NLU intent.

        Args:
            nlu_result: The result from NluService.
            request: The original ProcessAudioRequest containing context.
            history: The current chat history.

        Returns:
            A tuple containing:
                - The natural language response text (in NLU processing language).
                - Optional structured action result data (e.g., RouteInfo).
        """
        intent = nlu_result.intent
        entities = nlu_result.entities
        response_text_nlu = nlu_result.fallback_response or "Okay." # Default response from NLU
        action_result: Optional[Any] = None
        current_location = request.current_location
        order_context = request.order_context

        logger.info(f"Handling intent: {intent.value}. Entities: {entities}. Location: {current_location}. Order: {order_context}")

        try:
            if intent == NluIntent.GET_ROUTE:
                destination = entities.get("destination")
                if not destination:
                    # NLU should ideally handle this via clarification, but double-check
                    response_text_nlu = "Where would you like me to get directions to?"
                elif not current_location:
                    response_text_nlu = "I need your current location to get directions. Can you enable location services?"
                else:
                    logger.info(f"Calling NavigationService.get_route_and_eta for destination: {destination}")
                    route_info = await self.navigation_service.get_route_and_eta(...)
                    action_result = route_info # Send route details back to frontend
                    # Format a nice response
                    response_text_nlu = f"Okay, heading to {route_info.end_address or destination}. "
                    response_text_nlu += f"It should take about {route_info.duration_text} ({route_info.distance_text})."
                    if route_info.summary:
                        response_text_nlu += f" The route is mainly via {route_info.summary}."
                    if route_info.warnings:
                        warnings_text = " Also, be aware: " + ", ".join([w.message for w in route_info.warnings])
                        response_text_nlu += warnings_text
                        logger.warning(f"Route warnings for {destination}: {warnings_text}")

            elif intent == NluIntent.REROUTE_CHECK:
                 if not current_location:
                     response_text_nlu = "I need your current location to check for a reroute."
                 elif not order_context or not order_context.passenger_destination_address:
                      response_text_nlu = "I need an active order with a destination to check for a reroute."
                 else:
                      destination = order_context.passenger_destination_address
                      logger.info(f"Calling NavigationService.check_for_reroute to {destination}")
                      # We might need the current route details for better comparison
                      # For now, just check from current location
                      new_route = await self.navigation_service.check_for_reroute(
                          current_location=current_location,
                          destination=destination
                          # current_route_info= ??? # How to get this? Needs state management
                      )
                      if new_route:
                          action_result = new_route
                          response_text_nlu = f"Found a potentially faster route to {new_route.end_address or destination}. "
                          response_text_nlu += f"It should take about {new_route.duration_text}. "
                          # Should we automatically update the route on the frontend? Or just inform?
                          response_text_nlu += "Check your map for the updated route."
                      else:
                          response_text_nlu = "Looks like you're on the best route currently."

            elif intent == NluIntent.SEND_MESSAGE:
                 # Simple placeholder - requires CommunicationService and contact resolution
                 recipient_hint = entities.get("recipient_hint", "the passenger") # Default to passenger
                 message_content = entities.get("message_content")
                 if not message_content:
                      response_text_nlu = "What message would you like me to send?"
                 else:
                      logger.info(f"Placeholder: Sending message '{message_content}' to '{recipient_hint}'.")
                      # success = await self.communication_service.send_message(recipient_hint, message_content, order_context)
                      # response_text_nlu = "Okay, message sent." if success else "Sorry, I couldn't send the message."
                      response_text_nlu = "Okay, message sent." # Placeholder success


            elif intent == NluIntent.ASK_GATE_INFO:

                if not order_context:
                    response_text_nlu = "I need an active order to ask about the gate."
                elif not order_context.passenger_phone_number:
                    response_text_nlu = "I need the passenger's contact number from the order details to ask about the gate."
                elif not order_context.passenger_pickup_address and not order_context.passenger_pickup_place_id:
                    response_text_nlu = "I need the pickup address or Place ID from the order details to check the location type."
                else:
                    # Check if the location is complex using the NavigationService helper
                    is_complex = await self.navigation_service.is_pickup_location_complex(order_context)
                    if is_complex:
                        # Location is likely complex, proceed with asking
                        passenger_number = order_context.passenger_phone_number
                        pickup_location_name = order_context.passenger_pickup_address or f"Place ID {order_context.passenger_pickup_place_id}"
                        message = f"Hi, this is your Grab driver reaching {pickup_location_name}. As it seems like a large place, could you please let me know which specific gate, entrance, or lobby I should meet you at? Thanks!"
                        logger.info(
                            f"Placeholder: Sending 'ask gate' message for complex location to {passenger_number}.")
                        # success = await self.communication_service.send_sms(passenger_number, message) # Uncomment when communication service exists
                        # response_text_nlu = "Okay, the pickup location seems complex. I've sent a message to the passenger asking for the specific gate or entrance." if success else "Sorry, I couldn't send the message to the passenger."
                        response_text_nlu = "Okay, the pickup location seems complex. I've sent a message to the passenger asking for the specific gate or entrance."  # Placeholder success
                    else:
                        # Location doesn't seem complex, maybe skip or just confirm arrival
                        logger.info("Pickup location doesn't seem complex. Skipping specific 'ask gate' message.")
                        response_text_nlu = "Okay, I'm heading to the pickup location. It doesn't seem like a place with multiple gates, but I'll let you know when I arrive."

            elif intent == NluIntent.CHECK_FLOOD:
                 location_hint = entities.get("location_hint", "current route")
                 logger.info(f"Calling NavigationService.check_flood_zones for hint: {location_hint}")
                 target_location = current_location
                 target_route = None
                 # More sophisticated logic needed to interpret "on my route" vs "around here"
                 # If "on my route", need current route state. Assume current location for now.
                 if "route" in location_hint and order_context and order_context.passenger_destination_address:
                     # Try to get current route if possible (needs state)
                     # target_route = await self.navigation_service.get_route_and_eta(...)
                     pass # Requires state

                 warnings = await self.navigation_service.check_flood_zones(
                     route_info=target_route,
                     location=target_location
                 )
                 if warnings:
                     response_text_nlu = "Found potential flood warnings: " + "; ".join([w.message for w in warnings])
                 else:
                     response_text_nlu = f"I didn't find any specific flood warnings for {location_hint} right now."

            elif intent == NluIntent.GENERAL_CHAT:
                 # Use the fallback response already generated by NLU
                 response_text_nlu = nlu_result.fallback_response or "Okay."

            elif intent == NluIntent.UNKNOWN:
                 # Use the fallback response, likely a clarification or apology
                 response_text_nlu = nlu_result.fallback_response or "Sorry, I'm not sure how to help with that."

            # Add other intents (ORDER_ACCEPTED_NOTIFICATION etc. if triggered via voice)

        # --- Catch specific errors from dispatched services ---
        except InvalidRequestError as e:
             logger.warning(f"Intent handling failed due to invalid request/missing info: {e}")
             response_text_nlu = f"I can't do that right now. {e.message}"
        except StateError as e:
            logger.warning(f"Intent handling failed due to invalid state: {e}")
            response_text_nlu = f"Sorry, I can't do that in the current state. {e.message}"
        except NavigationError as e:
            logger.error(f"Navigation failed during intent handling: {e}")
            response_text_nlu = f"Sorry, I had trouble with the navigation request: {e.message}"
        except CommunicationError as e:
             logger.error(f"Communication failed during intent handling: {e}")
             response_text_nlu = f"Sorry, I couldn't complete the communication task: {e.message}"
        except SafetyError as e: # Should safety issues be handled via voice? Unlikely.
             logger.error(f"Safety service error during intent handling (unexpected): {e}")
             response_text_nlu = "Sorry, there was a problem with a safety-related action."
        except AssistantBaseException as e:
             # Catch other known custom exceptions
             logger.error(f"Assistant service error during intent handling: {e}", exc_info=True)
             response_text_nlu = f"Sorry, an error occurred: {e.message}"
        except Exception as e:
            # Catch unexpected errors during intent logic
            logger.exception(f"Unexpected error handling intent {intent.value}: {e}")
            response_text_nlu = "Sorry, an unexpected error occurred while processing your request."

        return response_text_nlu, action_result


    async def process_interaction(self, request: ProcessAudioRequest) -> AssistantResponse:
        """
        Handles the full voice interaction flow: STT -> Translate -> NLU -> Dispatch -> Translate Back -> TTS.
        """
        session_id = request.session_id
        logger.info(f"Processing interaction for session_id: {session_id}")

        # --- 1. Speech-to-Text ---
        user_transcription_original = ""
        detected_language_bcp47 = None
        try:
            user_transcription_original, detected_language_bcp47 = await self.transcription_service.process_audio(
                audio_data=request.audio_data,
                language_code_hint=request.language_code_hint
            )
            # Handle empty transcription early
            if not user_transcription_original:
                 logger.warning(f"Transcription resulted in empty text for session {session_id}.")
                 no_input_text = "Sorry, I didn't catch that. Could you please repeat?"
                 # Synthesize in detected language (or default)
                 tts_lang_for_error = detected_language_bcp47 or self.settings.DEFAULT_LANGUAGE_CODE
                 no_input_audio = await self.synthesis_service.text_to_speech(
                     text=no_input_text, language_code=tts_lang_for_error, return_base64=True
                 )
                 return AssistantResponse(
                     session_id=session_id, request_transcription="",
                     response_text=no_input_text, response_audio=no_input_audio,
                     detected_input_language=detected_language_bcp47
                 )
        except (TranscriptionError, InvalidRequestError) as e:
            logger.error(f"STT failed for session {session_id}: {e}")
            # Raise specific exceptions to be caught by API layer for appropriate HTTP status
            raise e
        except Exception as e:
             logger.error(f"Unexpected error during STT stage for session {session_id}: {e}", exc_info=True)
             raise TranscriptionError(f"Unexpected STT error: {e}", original_exception=e) # Wrap

        # --- Determine Effective Language ---
        effective_language_bcp47 = detected_language_bcp47 or self.settings.DEFAULT_LANGUAGE_CODE
        logger.info(f"Input Lang: {detected_language_bcp47}, Effective Lang: {effective_language_bcp47}, Original Text: '{user_transcription_original[:50]}...'")

        # --- 2. Translate User Input (if needed) ---
        user_input_for_nlu = user_transcription_original
        try:
            # Translation service handles checking if translation is necessary
            user_input_for_nlu, source_iso_code_used = await self.translation_service.translate_to_nlu_language(
                text=user_transcription_original,
                source_bcp47_code=effective_language_bcp47
            )
            logger.info(f"Text for NLU ({self.nlu_target_language}): '{user_input_for_nlu[:50]}...'")
        except TranslationError as e: # Catch specific error from service
            logger.error(f"Input translation failed for session {session_id}: {e}. Using original text.")
            # Continue with original text, NLU might handle it poorly
        except Exception as e:
             logger.error(f"Unexpected error during input translation for session {session_id}: {e}", exc_info=True)
             # Continue with original text

        # --- 3. NLU Processing (Intent & Entity Recognition) ---
        history = self._get_or_create_history(session_id)
        nlu_result: Optional[NluResult] = None
        try:
            # Prepare context for NLU
            nlu_context = {
                "current_location": request.current_location,
                "order_context": request.order_context.dict() if request.order_context else None,
                "timestamp": datetime.utcnow().isoformat()
            }
            nlu_result = await self.nlu_service.get_nlu_result(
                user_query=user_input_for_nlu,
                history=history,
                context=nlu_context
            )
        except NluError as e:
            logger.error(f"NLU processing failed for session {session_id}: {e}")
            raise e # Let API layer handle
        except Exception as e:
             logger.error(f"Unexpected error during NLU stage for session {session_id}: {e}", exc_info=True)
             raise NluError(f"Unexpected NLU error: {e}", original_exception=e) # Wrap


        # --- 4. Handle Intent / Dispatch ---
        response_text_nlu = "Sorry, something went wrong." # Default if NLU result missing
        action_result = None
        if nlu_result:
            try:
                response_text_nlu, action_result = await self._handle_intent(
                    nlu_result=nlu_result,
                    request=request,
                    history=history
                )
                logger.info(f"Intent handling completed. Response (NLU Lang): '{response_text_nlu[:50]}...'. Action Result: {type(action_result)}")
            except Exception as e:
                # Catch errors within the intent handling logic itself
                logger.exception(f"Core logic error handling intent {nlu_result.intent.value} for session {session_id}: {e}")
                response_text_nlu = "Sorry, I encountered an internal error trying to process your request."
                action_result = None # Clear any partial result
        else:
             logger.error(f"NLU result was None for session {session_id}, cannot handle intent.")
             # Use default error message


        # --- 5. Translate Response Back (if needed) ---
        final_response_text = response_text_nlu
        try:
            # Translation service handles checking if translation is necessary
            final_response_text = await self.translation_service.translate_from_nlu_language(
                text=response_text_nlu,
                target_bcp47_code=effective_language_bcp47
            )
            logger.info(f"Final response text ({effective_language_bcp47}): '{final_response_text[:50]}...'")
        except TranslationError as e:
            logger.error(f"Output translation failed for session {session_id}: {e}. Sending NLU language response.")
            # Use the untranslated NLU response text
        except Exception as e:
             logger.error(f"Unexpected error during output translation for session {session_id}: {e}", exc_info=True)
             # Use the untranslated NLU response text


        # --- 6. Text-to-Speech ---
        assistant_audio_response = ""
        try:
            assistant_audio_response = await self.synthesis_service.text_to_speech(
                text=final_response_text,
                language_code=effective_language_bcp47,
                return_base64=True
            )
            logger.debug(f"Synthesis complete for session {session_id}. Audio length (base64): {len(assistant_audio_response)}")
        except SynthesisError as e:
            logger.error(f"Synthesis failed for session {session_id}: {e}")
            raise e # Let API layer handle
        except Exception as e:
             logger.error(f"Unexpected error during TTS stage for session {session_id}: {e}", exc_info=True)
             raise SynthesisError(f"Unexpected TTS error: {e}", original_exception=e) # Wrap

        # --- 7. Update History ---
        # Store original user input and final (potentially translated) assistant response
        self._update_history(
            session_id=session_id,
            user_message=user_transcription_original,
            assistant_message=final_response_text
        )

        # --- 8. Format and Return Response ---
        logger.info(f"Successfully processed interaction for session_id: {session_id}")
        return AssistantResponse(
            session_id=session_id,
            request_transcription=user_transcription_original,
            response_text=final_response_text,
            response_audio=assistant_audio_response,
            detected_input_language=detected_language_bcp47,
            action_result=action_result # Include structured result if generated
        )