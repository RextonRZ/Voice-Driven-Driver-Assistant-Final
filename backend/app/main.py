import os
import json
import logging
import sys
import httpx # <--- Import httpx
from contextlib import asynccontextmanager # <--- Import asynccontextmanager
from fastapi import FastAPI, Request, status, Depends
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from google.oauth2 import service_account
from pathlib import Path
from dotenv import load_dotenv 

load_dotenv()

# --- Configure Logging ---
logging.basicConfig(
    level=logging.DEBUG,  # Change to DEBUG to see more details
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# --- Lifespan for managing resources like HTTP client ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code to run on startup
    logger.info("Application starting up - initializing resources...")
    # Create a single httpx client for the application lifecycle
    # Reuse the verify=False setting from your requests call in NavigationService
    # WARNING: Disabling SSL verification is insecure. Use only if absolutely necessary
    #          and you understand the risks (e.g., internal network, trusted endpoint).
    logger.warning("Creating shared httpx.AsyncClient with verify=False due to NavigationService requirement.")
    http_client = httpx.AsyncClient(verify=False, timeout=15.0)
    app.state.http_client = http_client # Store client in app state
    logger.info("Shared httpx.AsyncClient created and stored in app.state.")

    yield # Application runs here

    # Code to run on shutdown
    logger.info("Application shutting down - closing resources...")
    await app.state.http_client.aclose()
    logger.info("Shared httpx.AsyncClient closed.")
    logger.info("Shutdown complete.")

# --- Initialize FastAPI App ---
# Pass the lifespan context manager to the FastAPI constructor
app = FastAPI(
    title="Voice-Driven Driver Assistant Backend",
    description="API for processing voice commands, handling navigation tasks, safety features, and providing responses.",
    version="1.0.0",
    openapi_tags=[
        {"name": "Assistant Interaction", "description": "Core voice command processing."},
        {"name": "Safety Features", "description": "Endpoints related to crash detection, etc."},
        {"name": "Navigation Features", "description": "Endpoints for rerouting checks, etc."},
        {"name": "Health Check", "description": "Basic application health status."},
    ],
    lifespan=lifespan # <--- ADD LIFESPAN HERE
)

# --- CORS Middleware ---
origins = [
    "http://localhost",      # Allow localhost (common for dev)
    "http://localhost:3000", # Allow common React dev port
    "http://localhost:8080", # Allow common Vue dev port
    # Add production frontend domains here
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Load Google Cloud Configuration ---
def setup_gcloud():
    try:
        possible_paths = [
            # Adjust paths if necessary based on your actual structure
            os.path.join(os.path.dirname(__file__), "gcloudconfig.json"), # Check relative to main.py
            os.path.join(os.path.dirname(__file__), "..", "gcloudconfig.json"), # Check one level up
            os.path.join(os.getcwd(), "gcloudconfig.json"), # Check current working dir
            "/Users/vannessliu/VisualStudioCode/Voice-Driven-Driver-Assistant-Final/backend/gcloudconfig.json", # Hardcoded path (less ideal)
        ]

        gcloud_config_path = None
        for path in possible_paths:
            abs_path = os.path.abspath(path) # Use absolute path for clarity
            logger.info(f"Checking for credentials at: {abs_path}")
            if os.path.exists(abs_path):
                gcloud_config_path = abs_path
                logger.info(f"Found credentials file at: {gcloud_config_path}")
                break

        if not gcloud_config_path:
            logger.warning("Google Cloud credentials file not found in standard locations.")
            if "GOOGLE_CREDENTIALS" in os.environ:
                logger.info("Attempting to use GOOGLE_CREDENTIALS environment variable")
                # Be cautious writing env vars to disk if sensitive
                temp_path = os.path.join(os.getcwd(), "temp_credentials.json")
                try:
                    with open(temp_path, "w") as f:
                        f.write(os.environ["GOOGLE_CREDENTIALS"])
                    gcloud_config_path = temp_path
                    logger.info(f"Created temporary credentials file: {temp_path}")
                except Exception as write_err:
                    logger.error(f"Failed to write GOOGLE_CREDENTIALS to temp file: {write_err}")
                    raise FileNotFoundError("Google Cloud credentials file not found and failed to use environment variable.") from write_err
            else:
                raise FileNotFoundError("Google Cloud credentials file not found and GOOGLE_CREDENTIALS env var not set.")

        with open(gcloud_config_path, "r") as f:
            gcloud_config = json.load(f)

        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = gcloud_config_path
        # It's generally better to get project_id from the credentials file if needed elsewhere,
        # but setting GCLOUD_PROJECT env var is also common.
        if "project_id" in gcloud_config:
             os.environ["GCLOUD_PROJECT"] = gcloud_config["project_id"]
             logger.info(f"Google Cloud project set to: {gcloud_config['project_id']}")
        else:
             logger.warning("project_id not found in credentials file. GCLOUD_PROJECT environment variable not set.")


        # Validate credentials by trying to load them (optional but good check)
        credentials = service_account.Credentials.from_service_account_file(gcloud_config_path)
        logger.info(f"Successfully loaded Google Cloud credentials for service account: {credentials.service_account_email}")

        # Clean up temp file if it was created
        if 'temp_path' in locals() and os.path.exists(temp_path):
             try:
                 os.remove(temp_path)
                 logger.info(f"Removed temporary credentials file: {temp_path}")
             except OSError as rm_err:
                 logger.warning(f"Could not remove temporary credentials file {temp_path}: {rm_err}")

        return True
    except FileNotFoundError as fnf_err:
         logger.error(f"Google Cloud setup failed: {fnf_err}")
         return False
    except Exception as e:
        logger.exception(f"Failed to load Google Cloud configuration: {e}") # Use exception for full traceback
        # Clean up temp file in case of other errors
        if 'temp_path' in locals() and os.path.exists(temp_path):
             try:
                 os.remove(temp_path)
             except OSError as rm_err:
                  logger.warning(f"Could not remove temporary credentials file {temp_path} during error handling: {rm_err}")
        return False

gcloud_setup_success = setup_gcloud()
if not gcloud_setup_success:
    # Decide if the app should exit or just continue with limited functionality
    logger.critical("Google Cloud setup failed! Application might not function correctly.")
    # sys.exit(1) # Uncomment to force exit if GCloud is essential

# --- Include API Routers ---
# Ensure these imports happen *after* potential environment variable setup if they rely on it
try:
    from app.api.assistant import router as assistant_router
    from app.api.safety import router as safety_router
    from app.api.navigation import router as navigation_router

    app.include_router(assistant_router)
    app.include_router(safety_router)
    app.include_router(navigation_router)
    logger.info("API routers included successfully.")
except ImportError as import_err:
     logger.critical(f"Failed to import API routers: {import_err}. Check module paths and dependencies.", exc_info=True)
     # sys.exit(1) # Optional: Exit if routers are essential


# --- Global Exception Handlers ---
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # Avoid logging handled HTTPExceptions as critical errors if possible
    # This basic handler logs *all* uncaught exceptions.
    logger.critical(f"Unhandled Exception during request to {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected internal server error occurred."},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Log validation errors as warnings, not errors/critical
    logger.warning(f"Request validation failed for {request.url}: {exc.errors()}")
    # Provide more structured error info to the client
    error_details = []
    for error in exc.errors():
        field = " -> ".join(map(str, error.get("loc", ["unknown"]))) # Ensure loc exists
        message = error.get("msg", "Unknown validation error")
        error_type = error.get("type", "validation_error")
        error_details.append({"field": field, "message": message, "type": error_type})

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Request validation failed. Please check the input data.",
            "errors": error_details
            },
    )

# --- Startup Event (Deprecated in favor of lifespan) ---
# @app.on_event("startup") # <-- Keep commented out or remove if using lifespan
# async def startup_event():
#     logger.info("Application starting up...")
#     # Perform any additional startup checks here if needed (outside lifespan)
#     logger.info("Startup checks completed successfully.")


# --- Root Endpoint ---
@app.get("/", tags=["Health Check"], summary="Check application status")
async def root(request: Request):
    """Provides basic health status including Google Cloud and HTTP client state."""
    gcloud_status = "Configured successfully" if gcloud_setup_success else "Configuration failed"
    http_client_status = "Initialized" if hasattr(request.app.state, 'http_client') and request.app.state.http_client else "Not Initialized"
    return {
        "message": "Voice-Driven Driver Assistant Backend is running!",
        "status": "OK",
        "google_cloud_status": gcloud_status,
        "shared_http_client_status": http_client_status, # Reflect lifespan state
        "environment": {
            "cwd": os.getcwd(),
            "google_credentials_env_set": "GOOGLE_APPLICATION_CREDENTIALS" in os.environ,
            "google_project_env_set": "GCLOUD_PROJECT" in os.environ
        }
    }

# --- Run with Uvicorn (Example) ---
# This part is usually run from the command line like: uvicorn main:app --reload
# if __name__ == "__main__":
#     import uvicorn
#     port = int(os.environ.get("PORT", 8000)) # Use PORT env var or default to 8000
#     logger.info(f"Starting Uvicorn server on port {port}...")
#     # Set reload=True for development, False for production
#     uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True, log_level="info")