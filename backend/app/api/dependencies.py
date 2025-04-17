# backend/api/dependencies.py
from functools import lru_cache
import logging

from ..core.clients.twillio_client import TwilioClient
# --- Config ---
# Import the *instance* directly
from ..core.config import Settings, settings as global_settings

# --- Clients ---
from ..core.clients.google_stt import GoogleSttClient
from ..core.clients.google_tts import GoogleTtsClient
from ..core.clients.gemini import GeminiClient
from ..core.clients.google_translate import GoogleTranslateClient
from ..core.clients.google_maps import GoogleMapsClient

# --- Services ---
from ..services.transcription_service import TranscriptionService
from ..services.nlu_service import NluService
from ..services.synthesis_service import SynthesisService
from ..services.translation_service import TranslationService
from ..services.navigation_service import NavigationService
from ..services.safety_service import SafetyService
from ..services.conversation_service import ConversationService
# from services.communication_service import CommunicationService # Add later

logger = logging.getLogger(__name__)

from fastapi import Depends

# --- Settings ---
@lru_cache()
def get_settings() -> Settings:
    """Provides the globally imported Settings instance."""
    logger.debug("Providing Settings instance (from global import).")
    # REMOVE THE RECURSIVE CALL: _settings = get_settings()
    return global_settings # Return the imported instance

# --- Clients ---
@lru_cache()
def get_google_stt_client(settings: Settings = Depends(get_settings)) -> GoogleSttClient:
    """Provides GoogleSttClient instance, using the injected settings."""
    logger.debug("Providing GoogleSttClient instance.")
    # REMOVE THE RECURSIVE CALL: _settings = get_settings()
    # USE the 'settings' argument passed into the function
    return GoogleSttClient(settings=settings)

@lru_cache()
def get_google_tts_client(settings: Settings = Depends(get_settings)) -> GoogleTtsClient:
    """Provides GoogleTtsClient instance, using the injected settings."""
    logger.debug("Providing GoogleTtsClient instance.")
    # REMOVE THE RECURSIVE CALL: _settings = get_settings()
    return GoogleTtsClient(settings=settings)

@lru_cache()
def get_gemini_client(settings: Settings = Depends(get_settings)) -> GeminiClient:
    """Provides GeminiClient instance, using the injected settings."""
    logger.debug("Providing GeminiClient instance.")
    # REMOVE THE RECURSIVE CALL: _settings = get_settings()
    return GeminiClient(settings=settings)

@lru_cache()
def get_google_translate_client(settings: Settings = Depends(get_settings)) -> GoogleTranslateClient:
    """Provides GoogleTranslateClient instance, using the injected settings."""
    logger.debug("Providing GoogleTranslateClient instance.")
    # REMOVE THE RECURSIVE CALL: _settings = get_settings()
    return GoogleTranslateClient(settings=settings)

@lru_cache()
def get_google_maps_client(settings: Settings = Depends(get_settings)) -> GoogleMapsClient:
    """Provides GoogleMapsClient instance, using the injected settings."""
    logger.debug("Providing GoogleMapsClient instance.")
    # REMOVE THE RECURSIVE CALL: _settings = get_settings()
    return GoogleMapsClient(settings=settings)

@lru_cache()
def get_twilio_client(settings: Settings = Depends(get_settings)) -> TwilioClient:
    """Provides TwilioClient instance, using the injected settings."""
    logger.debug("Providing TwilioClient instance.")
    # REMOVE THE RECURSIVE CALL: _settings = get_settings()
    # Note: TwilioClient handles its own enablement based on config
    return TwilioClient(settings=settings)

# --- Services ---

@lru_cache()
def get_transcription_service(
    stt_client: GoogleSttClient = Depends(get_google_stt_client),
    settings: Settings = Depends(get_settings)
) -> TranscriptionService:
    """Provides TranscriptionService instance, using injected dependencies."""
    logger.debug("Providing TranscriptionService instance.")
    # USE the injected 'stt_client' and 'settings' arguments
    return TranscriptionService(stt_client=stt_client, settings=settings)

@lru_cache()
def get_translation_service(
    translate_client: GoogleTranslateClient = Depends(get_google_translate_client),
    settings: Settings = Depends(get_settings)
) -> TranslationService:
    """Provides TranslationService instance, using injected dependencies."""
    logger.debug("Providing TranslationService instance.")
    return TranslationService(translate_client=translate_client, settings=settings)

@lru_cache()
def get_nlu_service(
    gemini_client: GeminiClient = Depends(get_gemini_client),
    settings: Settings = Depends(get_settings)
) -> NluService:
    """Provides NluService instance, using injected dependencies."""
    logger.debug("Providing NluService instance.")
    return NluService(gemini_client=gemini_client, settings=settings)

@lru_cache()
def get_synthesis_service(
    tts_client: GoogleTtsClient = Depends(get_google_tts_client),
    settings: Settings = Depends(get_settings)
) -> SynthesisService:
    """Provides SynthesisService instance, using injected dependencies."""
    logger.debug("Providing SynthesisService instance.")
    return SynthesisService(tts_client=tts_client, settings=settings)

@lru_cache()
def get_navigation_service(
    maps_client: GoogleMapsClient = Depends(get_google_maps_client),
    settings: Settings = Depends(get_settings)
) -> NavigationService:
    """Provides NavigationService instance, using injected dependencies."""
    logger.debug("Providing NavigationService instance.")
    return NavigationService(maps_client=maps_client, settings=settings)

@lru_cache()
def get_safety_service( # Keep Depends here for FastAPI requests
    settings: Settings = Depends(get_settings),
    twilio_client: TwilioClient = Depends(get_twilio_client)
) -> SafetyService:
    """Provides SafetyService instance, using injected dependencies."""
    logger.debug("Providing SafetyService instance.")
    return SafetyService(settings=settings, twilio_client=twilio_client)

# @lru_cache()
# def get_communication_service(...) -> CommunicationService: ...

@lru_cache()
def get_conversation_service(
    transcription_service: TranscriptionService = Depends(get_transcription_service),
    translation_service: TranslationService = Depends(get_translation_service),
    nlu_service: NluService = Depends(get_nlu_service),
    synthesis_service: SynthesisService = Depends(get_synthesis_service),
    navigation_service: NavigationService = Depends(get_navigation_service),
    safety_service: SafetyService = Depends(get_safety_service),
    # communication_service: CommunicationService = Depends(get_communication_service), # Add later
    settings: Settings = Depends(get_settings)
) -> ConversationService:
    """Provides ConversationService instance, using injected dependencies."""
    logger.debug("Providing ConversationService instance.")
    # USE the injected service and settings arguments
    return ConversationService(
        transcription_service=transcription_service,
        translation_service=translation_service,
        nlu_service=nlu_service,
        synthesis_service=synthesis_service,
        navigation_service=navigation_service,
        safety_service=safety_service,
        # communication_service=communication_service,
        settings=settings
    )