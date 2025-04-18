import logging
import sys # For stdout logging handler
from fastapi import FastAPI, Request, status, Depends
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware # Import CORS middleware

# --- Routers ---
from . import assistant, safety, navigation # Import new routers

# --- Core ---
from ..core.config import settings # Import settings if needed directly
from ..core.exception import (
    AssistantBaseException,
    InvalidRequestError,
    StateError,
    TranscriptionError,
    NluError,
    SynthesisError,
    TranslationError,
    NavigationError,
    CommunicationError,
    ConfigurationError,
    SafetyError
)

from .dependencies import get_settings

root_logger = logging.getLogger()
# Avoid adding handlers multiple times if using reload
if not root_logger.handlers:
     root_logger.setLevel(logging.DEBUG if settings.LOG_LEVEL.upper() == "DEBUG" else logging.INFO) # Set level from settings
     handler = logging.StreamHandler(sys.stdout) # Output to standard out
     formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s [%(filename)s:%(lineno)d]') # More detailed formatter
     handler.setFormatter(formatter)
     root_logger.addHandler(handler)
else:
      # Update level if already configured (useful for reload)
      root_logger.setLevel(logging.DEBUG if settings.LOG_LEVEL.upper() == "DEBUG" else logging.INFO)

# Now get the logger for this specific module AFTER configuring the root
logger = logging.getLogger(__name__)
# --------------------------------------

# --- Test Log Message ---
logger.debug("DEBUG level logging configured in main.py")
logger.info("INFO level logging configured in main.py")


# --- FastAPI App Initialization ---
app = FastAPI(
    title="Voice-Driven Driver Assistant Backend",
    description="API for processing voice commands, handling navigation tasks, safety features, and providing responses.",
    version="0.2.0", # Bump version
    # Add OpenAPI tags metadata for better docs UI
    openapi_tags=[
        {"name": "Assistant Interaction", "description": "Core voice command processing."},
        {"name": "Safety Features", "description": "Endpoints related to crash detection, etc."},
        {"name": "Navigation Features", "description": "Endpoints for rerouting checks, etc."},
        {"name": "Health Check", "description": "Basic application health status."},
    ]
)

# --- CORS Middleware ---
# Allow requests from your frontend development server and production domain
# Adjust origins as needed for your environment
origins = [
    "http://localhost",      # Allow localhost (common for dev)
    "http://localhost:3000", # Allow common React dev port
    "http://localhost:8080", # Allow common Vue dev port
    # "https://your-frontend-domain.com", # Add your production frontend domain
    # Add any other origins needed
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True, # Allow cookies if needed
    allow_methods=["*"],    # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],    # Allow all headers
)


# --- Include API Routers ---
app.include_router(assistant.router)
app.include_router(safety.router)
app.include_router(navigation.router)


# --- Global Exception Handlers (Mostly unchanged, add specific checks if needed) ---

@app.exception_handler(AssistantBaseException)
async def assistant_exception_handler(request: Request, exc: AssistantBaseException):
    """Handles known custom exceptions originating from services or core components."""
    logger.error(f"Assistant Exception caught by handler: {type(exc).__name__} - {exc}", exc_info=isinstance(exc, (ConfigurationError, SafetyError))) # Log traceback for critical ones
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    # Map specific exceptions if not handled adequately by the endpoint handlers
    if isinstance(exc, InvalidRequestError):
        status_code = status.HTTP_400_BAD_REQUEST
    elif isinstance(exc, StateError):
         status_code = status.HTTP_409_CONFLICT
    elif isinstance(exc, (TranscriptionError, NluError, SynthesisError, TranslationError, NavigationError, CommunicationError)):
         status_code = status.HTTP_502_BAD_GATEWAY
    elif isinstance(exc, ConfigurationError):
         status_code = status.HTTP_500_INTERNAL_SERVER_ERROR # Keep as 500

    return JSONResponse(
        status_code=status_code,
        content={"detail": f"An error occurred: {exc.message}"},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handles Pydantic validation errors for incoming requests."""
    logger.warning(f"Request validation failed: {exc.errors()}")
    # Provide more detailed error feedback to the client
    error_details = []
    for error in exc.errors():
        field = " -> ".join(map(str, error["loc"])) # Join path components
        message = error["msg"]
        error_details.append({"field": field, "message": message})

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Request validation failed.", "errors": error_details},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handles any other unexpected exceptions."""
    logger.critical(f"Unhandled Exception caught by generic handler: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected internal server error occurred."},
    )


# --- Startup Event ---
@app.on_event("startup")
async def startup_event():
    logger.info("Application starting up...")
    # Enhanced startup checks - try initializing all key clients/services
    try:
        # Import the specific getter for settings
        from .dependencies import get_settings
        # Import the CLIENT CLASSES directly for startup checks
        from ..core.clients.google_stt import GoogleSttClient
        from ..core.clients.google_tts import GoogleTtsClient
        from ..core.clients.gemini import GeminiClient
        from ..core.clients.google_translate import GoogleTranslateClient
        from ..core.clients.google_maps import GoogleMapsClient
        from ..core.clients.twillio_client import TwilioClient

        logger.info("Performing startup initialization checks...")

        # --- STEP 1: Get the Settings instance (using the cached getter) ---
        settings_instance = get_settings()
        logger.info("Settings loaded.")

        # --- STEP 2: Directly INSTANTIATE clients using the settings_instance ---
        # This bypasses the @lru_cache issue for manual calls during startup
        GoogleSttClient(settings=settings_instance)
        logger.info("STT client initialized.")
        GoogleTtsClient(settings=settings_instance)
        logger.info("TTS client initialized.")
        GoogleTranslateClient(settings=settings_instance)
        logger.info("Translate client initialized.")
        GeminiClient(settings=settings_instance)
        logger.info("Gemini client initialized.")
        GoogleMapsClient(settings=settings_instance)
        logger.info("Maps client initialized.")
        TwilioClient(settings=settings_instance)  # Corrected typo
        logger.info("Twilio client initialized (or disabled).")
        logger.info("All clients initialized successfully.")

    except ConfigurationError as e:
         logger.critical(f"STARTUP FAILED: Configuration error - {e}", exc_info=True)
         # Consider stopping the server if config fails:
         # import sys
         # sys.exit(1)
    except Exception as e:
        logger.critical(f"STARTUP FAILED: Could not initialize core components. Error: {e}", exc_info=True)
        # import sys
        # sys.exit(1)

    logger.info("Application startup complete.")


# --- Root Endpoint ---
@app.get("/", tags=["Health Check"])
async def read_root():
    """Simple health check endpoint."""
    logger.debug("Root health check endpoint accessed.")
    return {"status": "ok", "message": "Welcome to the Voice-Driven Driver Assistant Backend!"}