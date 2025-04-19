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
        # This logic remains the same: stores the ORIGINAL user message and FINAL assistant response
        history = self.chat_histories.get(session_id)
        if not history:
            logger.warning(f"Attempted to update history for non-existent session_id: {session_id}. Creating new history.")
            history = self._get_or_create_history(session_id)

        history.messages.append(ChatMessage(role="user", content=user_message))
        history.messages.append(ChatMessage(role="assistant", content=assistant_message))

        max_pairs = self.settings.HISTORY_MAX_MESSAGES
        max_messages = max_pairs * 2
        if len(history.messages) > max_messages:
             excess = len(history.messages) - max_messages
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
                logger.info("Processing ASK_GATE_INFO intent.")
                # 1. Validate Context
                if not order_context:
                    response_text_nlu = "I need an active order to ask about the gate."
                    logger.warning("ASK_GATE_INFO failed: No order context provided.")
                elif not order_context.passenger_phone_number:
                    # Check phone number even for simulation, as it's needed eventually
                    response_text_nlu = "I need the passenger's contact number from the order details to ask about the gate."
                    logger.warning("ASK_GATE_INFO failed: Missing passenger phone number in order context.")
                elif not order_context.passenger_pickup_address and not order_context.passenger_pickup_place_id:
                    response_text_nlu = "I need the pickup address or Place ID from the order details to determine if the location is complex."
                    logger.warning("ASK_GATE_INFO failed: Missing pickup address and Place ID in order context.")
                else:
                    # 2. Check Location Complexity using NavigationService helper
                    logger.info(f"Checking pickup location complexity for order {order_context.order_id}.")
                    try:
                        is_complex = await self.navigation_service.is_pickup_location_complex(order_context)
                        # 3. Handle based on complexity
                        if is_complex:
                            # Location is likely complex, proceed with asking
                            passenger_number = order_context.passenger_phone_number  # Already checked it exists
                            # Construct location name for the message
                            pickup_location_name = order_context.passenger_pickup_address or f"the pickup location (Place ID: {order_context.passenger_pickup_place_id})"
                            # Construct the message to be sent (can be refined)
                            message = f"Hi, this is your Grab driver reaching {pickup_location_name}. As it seems like a large place, could you please let me know which specific gate, entrance, or lobby I should meet you at? Thanks!"
                            logger.info(
                                f"Pickup location deemed complex. Preparing to send 'ask gate' message to {passenger_number}. Message: '{message}'")
                            # --- Placeholder: Send message via Communication Service ---
                            # if self.communication_service:
                            #     try:
                            #         logger.debug(f"Calling CommunicationService.send_sms for ASK_GATE_INFO.")
                            #         success = await self.communication_service.send_sms(passenger_number, message)
                            #         if success:
                            #             logger.info("Successfully sent 'ask gate' SMS via CommunicationService.")
                            #             response_text_nlu = "Okay, the pickup location seems complex. I've sent a message to the passenger asking for the specific gate or entrance."
                            #         else:
                            #             logger.error("CommunicationService.send_sms returned False for ASK_GATE_INFO.")
                            #             response_text_nlu = "Sorry, I couldn't send the message to the passenger asking about the gate."
                            #     except CommunicationError as comm_err:
                            #         logger.error(f"CommunicationError sending 'ask gate' SMS: {comm_err}", exc_info=True)
                            #         response_text_nlu = f"Sorry, I encountered an error trying to message the passenger: {comm_err.message}"
                            # else:
                            #     logger.warning("CommunicationService not available/configured. Skipping actual SMS send for ASK_GATE_INFO.")
                            #     # Provide placeholder success response if no communication service
                            #     response_text_nlu = "Okay, the pickup location seems complex. I've sent a message to the passenger asking for the specific gate or entrance. (Simulation)"
                            # --- Using only placeholder logging for now ---
                            logger.info(f"Placeholder: Simulating sending SMS to {passenger_number}: '{message}'")
                            response_text_nlu = "Okay, the pickup location seems complex. I've sent a message to the passenger asking for the specific gate or entrance."
                            # --- End Placeholder ---
                        else:
                            # Location doesn't seem complex, skip specific 'ask gate' message
                            logger.info(
                                "Pickup location doesn't seem complex based on checks. Skipping specific 'ask gate' message.")
                            # Provide a suitable response confirming the driver's request but indicating no message was sent for this reason.
                            response_text_nlu = "Okay, I checked the pickup location. It doesn't seem like a place with multiple gates, so I haven't messaged the passenger about it. I'm heading there now."
                            # Alternative simpler response:
                            # response_text_nlu = "Okay, I'm heading to the pickup location."
                    except NavigationError as nav_err:
                        logger.error(f"NavigationError during complexity check for ASK_GATE_INFO: {nav_err}",
                                     exc_info=True)
                        response_text_nlu = "Sorry, I had trouble checking the details of the pickup location."
                    except Exception as complex_err:
                        logger.error(f"Unexpected error during complexity check for ASK_GATE_INFO: {complex_err}",
                                     exc_info=True)
                        response_text_nlu = "Sorry, an unexpected error occurred while checking the pickup location."


            elif intent == NluIntent.CHECK_FLOOD:
                # Ensure current_location is available
                if not current_location:
                    response_text_nlu = "I need your current location to check for flood warnings."
                else:
                    logger.info(f"Calling NavigationService.check_flood_zones for current location: {current_location}")
                    # Call the updated service method, primarily using location
                    warnings = await self.navigation_service.check_flood_zones(
                        location=current_location
                        # route_info could be passed if needed for future enhancements, but location is key now
                    )
                    if warnings:
                        # Combine warning messages
                        warning_msgs = [w.message for w in warnings]
                        response_text_nlu = "Attention: " + "; ".join(warning_msgs)
                        # Log the combined message
                        logger.warning(f"Flood warnings found for location {current_location}: {response_text_nlu}")
                    else:
                        response_text_nlu = f"Good news, I didn't find any active flood alerts reported for your current area right now."

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
        Handles the full interaction flow: STT -> Refine -> Translate -> NLU -> Dispatch -> Translate Back -> TTS.
        """
        session_id = request.session_id
        start_time = datetime.now()
        logger.info(f"Processing interaction for session_id: {session_id}")

        # --- 1. Speech-to-Text ---
        user_transcription_original = ""
        detected_language_bcp47 = None
        try:
            stt_start = datetime.now()
            user_transcription_original, detected_language_bcp47 = await self.transcription_service.process_audio(
                audio_data=request.audio_data,
                language_code_hint=request.language_code_hint
            )
            stt_duration = (datetime.now() - stt_start).total_seconds()
            logger.info(f"STT complete ({stt_duration:.2f}s). Detected Lang: {detected_language_bcp47}. Original Text: '{user_transcription_original[:70]}...'")

            # Handle empty transcription right after STT
            if not user_transcription_original:
                 logger.warning(f"Transcription resulted in empty text for session {session_id}.")
                 # Synthesize a generic "didn't catch that" in detected/default language
                 no_input_text = "Sorry, I didn't catch that. Could you please repeat?"
                 tts_lang_for_error = detected_language_bcp47 or self.settings.DEFAULT_LANGUAGE_CODE
                 tts_start = datetime.now()
                 no_input_audio = await self.synthesis_service.text_to_speech(
                     text=no_input_text, language_code=tts_lang_for_error, return_base64=True
                 )
                 tts_duration = (datetime.now() - tts_start).total_seconds()
                 logger.info(f"Synthesized empty input response ({tts_duration:.2f}s)")
                 return AssistantResponse(
                     session_id=session_id, request_transcription="",
                     response_text=no_input_text, response_audio=no_input_audio,
                     detected_input_language=detected_language_bcp47
                 )

        except (TranscriptionError, InvalidRequestError) as e:
            logger.error(f"STT or preprocessing failed for session {session_id}: {e}")
            raise e # Raise to API layer for appropriate HTTP status
        except Exception as e:
             logger.error(f"Unexpected error during STT stage for session {session_id}: {e}", exc_info=True)
             raise TranscriptionError(f"Unexpected STT error: {e}", original_exception=e)


        # --- Determine Effective Language ---
        effective_language_bcp47 = detected_language_bcp47 or self.settings.DEFAULT_LANGUAGE_CODE
        logger.info(f"Effective language for processing: {effective_language_bcp47}")

        # --- 2. Refine Transcription (NEW STEP) ---
        text_for_translation = user_transcription_original # Default to original if refinement fails/disabled
        if self.settings.ENABLE_TRANSCRIPTION_REFINEMENT:
             refine_start = datetime.now()
             try:
                 # Call the NLU service's refinement method
                 refined_transcription = await self.nlu_service.refine_transcription(
                     original_text=user_transcription_original,
                     language_bcp47=effective_language_bcp47
                 )
                 refine_duration = (datetime.now() - refine_start).total_seconds()
                 if refined_transcription != user_transcription_original:
                      logger.info(f"Transcription refined ({refine_duration:.2f}s). Using refined text for translation.")
                      text_for_translation = refined_transcription
                      # Log original vs refined for comparison
                      logger.debug(f"Refinement Diff | Orig: '{user_transcription_original}' | Refined: '{refined_transcription}'")
                 else:
                      logger.info(f"Refinement ({refine_duration:.2f}s) did not change the text or failed gracefully. Using original.")

             except Exception as e:
                 # Catch unexpected errors during refinement call itself
                 refine_duration = (datetime.now() - refine_start).total_seconds()
                 logger.error(f"Unexpected error during transcription refinement call ({refine_duration:.2f}s): {e}", exc_info=True)
                 logger.warning("Proceeding with original transcription due to refinement error.")
                 # text_for_translation remains user_transcription_original


        # --- 3. Translate User Input (Potentially Refined) to NLU Language ---
        user_input_for_nlu = text_for_translation # Use refined (or original) text
        translated_source_iso = effective_language_bcp47.split('-')[0] # Default to effective lang
        try:
            translate_in_start = datetime.now()
            # Translation service handles checking if translation is actually needed
            user_input_for_nlu, detected_iso_after_translate = await self.translation_service.translate_to_nlu_language(
                text=text_for_translation, # Pass the text chosen in step 2
                source_bcp47_code=effective_language_bcp47
            )
            translate_in_duration = (datetime.now() - translate_in_start).total_seconds()
            logger.info(f"Input translation to '{self.nlu_target_language}' complete ({translate_in_duration:.2f}s). Text for NLU: '{user_input_for_nlu[:70]}...'")
            # Update the source language based on translation result if available
            translated_source_iso = detected_iso_after_translate

        except TranslationError as e:
            translate_in_duration = (datetime.now() - translate_in_start).total_seconds()
            logger.error(f"Input translation failed ({translate_in_duration:.2f}s) for session {session_id}: {e}. Proceeding with un-translated text.")
            # user_input_for_nlu remains the (potentially refined) text_for_translation
        except Exception as e:
             translate_in_duration = (datetime.now() - translate_in_start).total_seconds()
             logger.error(f"Unexpected error during input translation ({translate_in_duration:.2f}s) for session {session_id}: {e}", exc_info=True)
             # Proceed with un-translated text


        # --- 4. NLU Processing (Intent & Entity Recognition on Translated Text) ---
        history = self._get_or_create_history(session_id)
        nlu_result: Optional[NluResult] = None
        try:
            nlu_start = datetime.now()
            nlu_context = {
                "current_location": request.current_location,
                "order_context": request.order_context.dict(exclude_unset=True) if request.order_context else None, # Use Pydantic's dict method
                "timestamp": start_time.isoformat(),
                "original_language": effective_language_bcp47,
            }
            nlu_result = await self.nlu_service.get_nlu_result(
                user_query=user_input_for_nlu, # Use the (potentially translated) text
                history=history,
                context=nlu_context
            )
            nlu_duration = (datetime.now() - nlu_start).total_seconds()
            logger.info(f"NLU processing complete ({nlu_duration:.2f}s). Intent: {nlu_result.intent.value if nlu_result else 'N/A'}")

        except NluError as e:
            nlu_duration = (datetime.now() - nlu_start).total_seconds()
            logger.error(f"NLU processing failed ({nlu_duration:.2f}s) for session {session_id}: {e}")
            raise e # Let API layer handle
        except Exception as e:
             nlu_duration = (datetime.now() - nlu_start).total_seconds()
             logger.error(f"Unexpected error during NLU stage ({nlu_duration:.2f}s) for session {session_id}: {e}", exc_info=True)
             raise NluError(f"Unexpected NLU error: {e}", original_exception=e)


        # --- 5. Handle Intent / Dispatch ---
        response_text_nlu = "Sorry, I wasn't able to understand or process that request." # Default error response in NLU lang
        action_result = None
        if nlu_result:
            dispatch_start = datetime.now()
            try:
                # Pass NLU result and original request context
                response_text_nlu, action_result = await self._handle_intent(
                    nlu_result=nlu_result,
                    request=request, # Contains original context like location, order
                    history=history
                )
                dispatch_duration = (datetime.now() - dispatch_start).total_seconds()
                logger.info(f"Intent handling ({nlu_result.intent.value}) complete ({dispatch_duration:.2f}s). Response (NLU Lang): '{response_text_nlu[:70]}...'. Action Result: {type(action_result).__name__}")
            except Exception as e:
                # Catch errors within the intent handling logic itself
                dispatch_duration = (datetime.now() - dispatch_start).total_seconds()
                logger.exception(f"Core logic error handling intent {nlu_result.intent.value} ({dispatch_duration:.2f}s) for session {session_id}: {e}")
                response_text_nlu = "Sorry, I encountered an internal error trying to process your request." # Use generic error in NLU lang
                action_result = None # Clear any partial result
        else:
             # This case should ideally not happen if NLU service handles errors gracefully
             logger.error(f"NLU result was None for session {session_id}, cannot handle intent.")
             # Use default error message response_text_nlu


        # --- 6. Translate Response Back to User's Language (if needed) ---
        final_response_text = response_text_nlu # Default to NLU language response
        try:
            translate_out_start = datetime.now()
            # Translation service checks if translation is needed
            final_response_text = await self.translation_service.translate_from_nlu_language(
                text=response_text_nlu, # The response generated by _handle_intent
                target_bcp47_code=effective_language_bcp47 # Target the user's original effective language
            )
            translate_out_duration = (datetime.now() - translate_out_start).total_seconds()
            if final_response_text != response_text_nlu:
                logger.info(f"Output translation to '{effective_language_bcp47}' complete ({translate_out_duration:.2f}s).")
            else:
                 logger.info(f"Output translation ({translate_out_duration:.2f}s): No translation needed or translation failed; using NLU language response.")
            logger.debug(f"Final response text ({effective_language_bcp47}): '{final_response_text[:70]}...'")
        except TranslationError as e:
            translate_out_duration = (datetime.now() - translate_out_start).total_seconds()
            logger.error(f"Output translation failed ({translate_out_duration:.2f}s) for session {session_id}: {e}. Sending NLU language response.")
            # final_response_text remains response_text_nlu
        except Exception as e:
             translate_out_duration = (datetime.now() - translate_out_start).total_seconds()
             logger.error(f"Unexpected error during output translation ({translate_out_duration:.2f}s) for session {session_id}: {e}", exc_info=True)
             # final_response_text remains response_text_nlu


        # --- 7. Text-to-Speech ---
        assistant_audio_response = ""
        try:
            tts_start = datetime.now()
            assistant_audio_response = await self.synthesis_service.text_to_speech(
                text=final_response_text, # Use the (potentially translated back) final text
                language_code=effective_language_bcp47, # Use user's effective language for TTS
                return_base64=True
            )
            tts_duration = (datetime.now() - tts_start).total_seconds()
            logger.info(f"Synthesis complete ({tts_duration:.2f}s) for session {session_id}. Audio length (base64 approx): {len(assistant_audio_response)}")
        except SynthesisError as e:
            tts_duration = (datetime.now() - tts_start).total_seconds()
            logger.error(f"Synthesis failed ({tts_duration:.2f}s) for session {session_id}: {e}")
            raise e # Let API layer handle
        except Exception as e:
             tts_duration = (datetime.now() - tts_start).total_seconds()
             logger.error(f"Unexpected error during TTS stage ({tts_duration:.2f}s) for session {session_id}: {e}", exc_info=True)
             raise SynthesisError(f"Unexpected TTS error: {e}", original_exception=e) # Wrap


        # --- 8. Update History ---
        # Store the ORIGINAL user input and the FINAL assistant text response
        self._update_history(
            session_id=session_id,
            user_message=user_transcription_original, # Store the raw STT output
            assistant_message=final_response_text # Store the final text sent to TTS
        )

        # --- 9. Format and Return Response ---
        total_duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Successfully processed interaction for session_id: {session_id}. Total time: {total_duration:.2f}s")
        return AssistantResponse(
            session_id=session_id,
            request_transcription=user_transcription_original, # Return the original transcription
            response_text=final_response_text,
            response_audio=assistant_audio_response,
            detected_input_language=detected_language_bcp47, # Return language detected by STT
            action_result=action_result # Include structured result if generated by _handle_intent
        )