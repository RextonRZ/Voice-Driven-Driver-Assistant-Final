# backend/api/dependencies.py
from functools import lru_cache
import logging
import httpx  # Import httpx
import ssl
import certifi # **** ADD CERTIFI IMPORT ****

from ..core.clients.twillio_client import TwilioClient
from ..core.config import Settings, settings as global_settings

# --- Clients ---
from ..core.clients.google_stt import GoogleSttClient
from ..core.clients.google_tts import GoogleTtsClient
from ..core.clients.gemini import GeminiClient
from ..core.clients.google_translate import GoogleTranslateClient
from ..core.clients.google_maps import GoogleMapsClient
from ..core.clients.openai_client import OpenAiClient

# --- Services ---
from ..services.transcription_service import TranscriptionService
from ..services.nlu_service import NluService
from ..services.synthesis_service import SynthesisService
from ..services.translation_service import TranslationService
from ..services.navigation_service import NavigationService
from ..services.safety_service import SafetyService
from ..services.conversation_service import ConversationService
from ..core.exception import ConfigurationError  # Import exception

logger = logging.getLogger(__name__)

from fastapi import Depends


# --- Settings ---
@lru_cache()
def get_settings() -> Settings:
    """Provides the globally imported Settings instance."""
    logger.debug("Providing Settings instance (from global import, cached).")
    return global_settings


# --- Initialize Clients Globally (Once) ---
# This code runs when the module is imported, in the main thread.
try:
    _settings_instance = get_settings()  # Get settings once
    logger.info("Initializing global client instances...")

    _stt_client_instance = GoogleSttClient(settings=_settings_instance)
    logger.info("Global GoogleSttClient initialized.")

    _tts_client_instance = GoogleTtsClient(settings=_settings_instance)
    logger.info("Global GoogleTtsClient initialized.")

    _gemini_client_instance = GeminiClient(settings=_settings_instance)
    logger.info("Global GeminiClient initialized.")

    _translate_client_instance = GoogleTranslateClient(settings=_settings_instance)
    logger.info("Global GoogleTranslateClient initialized.")

    _maps_client_instance = GoogleMapsClient(settings=_settings_instance)
    logger.info("Global GoogleMapsClient initialized.")

    _twilio_client_instance = TwilioClient(settings=_settings_instance)
    logger.info("Global TwilioClient initialized (or disabled).")

    _openai_client_instance = None
    try:
        # Initialization logic is inside the OpenAiClient class now
        _openai_client_instance = OpenAiClient(settings=_settings_instance)
        if _openai_client_instance.enabled:
            logger.info("Global OpenAiClient initialized.")
        else:
            logger.warning("Global OpenAiClient initialized but is DISABLED (check API key).")
    except ConfigurationError as e:
        logger.error(f"Failed to initialize OpenAI client during startup: {e}")
        _openai_client_instance = None  # Ensure it's None on failure
    except Exception as e:
        logger.error(f"Unexpected error initializing OpenAI client: {e}", exc_info=True)
        _openai_client_instance = None

    logger.info("All global client instances initialized successfully.")

except ConfigurationError as e:
    # Log critical error if client init fails here, app might not work
    logger.critical(f"FATAL: Failed to initialize global client instances in dependencies.py: {e}", exc_info=True)
    # Set instances to None or re-raise to potentially stop app? For now, set to None.
    _stt_client_instance = None
    _tts_client_instance = None
    _gemini_client_instance = None
    _translate_client_instance = None
    _maps_client_instance = None
    _twilio_client_instance = None
    _openai_client_instance = None
    # raise e
except Exception as e:
    logger.critical(f"FATAL: Unexpected error initializing global client instances in dependencies.py: {e}", exc_info=True)
    _stt_client_instance = None
    _tts_client_instance = None
    _gemini_client_instance = None
    _translate_client_instance = None
    _maps_client_instance = None
    _twilio_client_instance = None
    _openai_client_instance = None
    # raise ConfigurationError(f"Unexpected error during global client setup: {e}", original_exception=e)


# --- Client Getter Functions (Now return global instances) ---
def get_google_stt_client() -> GoogleSttClient:
    """Provides the globally initialized GoogleSttClient instance."""
    if _stt_client_instance is None:
        raise ConfigurationError("Google STT Client was not initialized successfully.")
    logger.debug("Providing global GoogleSttClient instance.")
    return _stt_client_instance

def get_google_tts_client() -> GoogleTtsClient:
    """Provides the globally initialized GoogleTtsClient instance."""
    if _tts_client_instance is None:
        raise ConfigurationError("Google TTS Client was not initialized successfully.")
    logger.debug("Providing global GoogleTtsClient instance.")
    return _tts_client_instance

def get_gemini_client() -> GeminiClient:
    """Provides the globally initialized GeminiClient instance."""
    if _gemini_client_instance is None:
        raise ConfigurationError("Gemini Client was not initialized successfully.")
    logger.debug("Providing global GeminiClient instance.")
    return _gemini_client_instance

def get_google_translate_client() -> GoogleTranslateClient:
    """Provides the globally initialized GoogleTranslateClient instance."""
    if _translate_client_instance is None:
        raise ConfigurationError("Google Translate Client was not initialized successfully.")
    logger.debug("Providing global GoogleTranslateClient instance.")
    return _translate_client_instance

def get_google_maps_client() -> GoogleMapsClient:
    """Provides the globally initialized GoogleMapsClient instance."""
    if _maps_client_instance is None:
        raise ConfigurationError("Google Maps Client was not initialized successfully.")
    logger.debug("Providing global GoogleMapsClient instance.")
    return _maps_client_instance

def get_twilio_client() -> TwilioClient:
    """Provides the globally initialized TwilioClient instance."""
    if _twilio_client_instance is None:
        raise ConfigurationError("Twilio Client object was not initialized successfully.")
    logger.debug("Providing global TwilioClient instance.")
    return _twilio_client_instance

def get_openai_client() -> OpenAiClient:
    """Provides the globally initialized OpenAiClient instance."""
    if _openai_client_instance is None:
        raise ConfigurationError("OpenAI Client was not initialized successfully.")
    # Check if enabled *at time of request* as well? Or rely on init check?
    # Rely on init check for now, client methods raise error if not enabled.
    # if not _openai_client_instance.enabled:
    #     raise ConfigurationError("OpenAI Client is configured but disabled (e.g., missing API key).")
    logger.debug("Providing global OpenAiClient instance.")
    return _openai_client_instance

# --- Service Getters (Depend on global client getters and settings) ---
# No changes needed below this line compared to the previous correct version
def get_translation_service(
    translate_client: GoogleTranslateClient = Depends(get_google_translate_client),
    settings: Settings = Depends(get_settings)
) -> TranslationService:
    logger.debug("Providing TranslationService instance.")
    return TranslationService(translate_client=translate_client, settings=settings)

def get_nlu_service(
    gemini_client: GeminiClient = Depends(get_gemini_client),
    settings: Settings = Depends(get_settings)
) -> NluService:
    logger.debug("Providing NluService instance.")
    return NluService(gemini_client=gemini_client, settings=settings)

def get_synthesis_service(
    tts_client: GoogleTtsClient = Depends(get_google_tts_client),
    settings: Settings = Depends(get_settings)
) -> SynthesisService:
    logger.debug("Providing SynthesisService instance.")
    return SynthesisService(tts_client=tts_client, settings=settings)

def get_navigation_service(
    maps_client: GoogleMapsClient = Depends(get_google_maps_client),
    settings: Settings = Depends(get_settings)
) -> NavigationService:
    logger.debug("Providing NavigationService instance.")
    return NavigationService(
        maps_client=maps_client,
        settings=settings
    )

def get_safety_service(
    settings: Settings = Depends(get_settings),
    twilio_client: TwilioClient = Depends(get_twilio_client)
) -> SafetyService:
    logger.debug("Providing SafetyService instance.")
    return SafetyService(settings=settings, twilio_client=twilio_client)

def get_transcription_service(
    stt_client: GoogleSttClient = Depends(get_google_stt_client),
    openai_client: OpenAiClient = Depends(get_openai_client),
    translation_service: TranslationService = Depends(get_translation_service), # **** ADD DEPENDENCY ****
    settings: Settings = Depends(get_settings)
) -> TranscriptionService:
    logger.debug("Providing TranscriptionService instance with Google STT, OpenAI, and Translation clients.")
    return TranscriptionService(
        stt_client=stt_client,
        openai_client=openai_client,
        translation_service=translation_service, # **** PASS SERVICE ****
        settings=settings
    )

def get_conversation_service(
    transcription_service: TranscriptionService = Depends(get_transcription_service),
    translation_service: TranslationService = Depends(get_translation_service),
    nlu_service: NluService = Depends(get_nlu_service),
    synthesis_service: SynthesisService = Depends(get_synthesis_service),
    navigation_service: NavigationService = Depends(get_navigation_service),
    safety_service: SafetyService = Depends(get_safety_service),
    settings: Settings = Depends(get_settings)
) -> ConversationService:
    logger.debug("Providing ConversationService instance.")
    return ConversationService(
        transcription_service=transcription_service,
        translation_service=translation_service,
        nlu_service=nlu_service,
        synthesis_service=synthesis_service,
        navigation_service=navigation_service,
        safety_service=safety_service,
        settings=settings
    )