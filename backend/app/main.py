import os
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from google.oauth2 import service_account
import logging
import sys
from pathlib import Path

# Configure logging for better debug information
logging.basicConfig(
    level=logging.DEBUG,  # Change to DEBUG to see more details
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Voice-Driven Driver Assistant",
    description="Backend for the Voice-Driven Driver Assistant application.",
    version="1.0.0",
)

# Add CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace "*" with specific frontend URLs in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load Google Cloud configuration
def setup_gcloud():
    try:
        # Try several possible locations for the credentials file
        possible_paths = [
            # Relative to the project root
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "gcloudconfig.json"),
            # Relative to the current file
            os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "gcloudconfig.json"),
            # Absolute path (as backup)
            r"C:\Users\ooiru\Voice-Driven-Driver-Assistant-Final\frontend\gcloudconfig.json",
            # Look in the current directory
            os.path.join(os.getcwd(), "gcloudconfig.json")
        ]
        
        # Try each path until we find an existing file
        gcloud_config_path = None
        for path in possible_paths:
            logger.info(f"Checking for credentials at: {path}")
            if os.path.exists(path):
                gcloud_config_path = path
                logger.info(f"Found credentials file at: {path}")
                break
        
        if not gcloud_config_path:
            logger.error("Google Cloud credentials file not found in any expected location!")
            # Create a fallback credentials file with environment variables if available
            if "GOOGLE_CREDENTIALS" in os.environ:
                logger.info("Using GOOGLE_CREDENTIALS environment variable")
                temp_path = os.path.join(os.getcwd(), "temp_credentials.json")
                with open(temp_path, "w") as f:
                    f.write(os.environ["GOOGLE_CREDENTIALS"])
                gcloud_config_path = temp_path
            else:
                raise FileNotFoundError("Google Cloud credentials file not found")

        # Load and verify credentials
        with open(gcloud_config_path, "r") as f:
            gcloud_config = json.load(f)

        # Set environment variables for Google Cloud
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = gcloud_config_path
        os.environ["GCLOUD_PROJECT"] = gcloud_config["project_id"]

        # Verify credentials
        credentials = service_account.Credentials.from_service_account_info(gcloud_config)
        logger.info(f"Google Cloud project set to: {gcloud_config['project_id']}")
        logger.info(f"Using service account: {gcloud_config.get('client_email', 'Unknown')}")
        return True
    except Exception as e:
        logger.exception(f"Failed to load Google Cloud configuration: {e}")
        return False

# Call setup_gcloud during startup
gcloud_setup_success = setup_gcloud()
if not gcloud_setup_success:
    logger.warning("Google Cloud setup failed! Some features may not work correctly.")

# Include routers
from app.api.assistant import router as assistant_router
app.include_router(assistant_router)

# Root endpoint for health check
@app.get("/")
async def root():
    gcloud_status = "configured" if gcloud_setup_success else "failed"
    return {
        "message": "Backend is running!",
        "google_cloud_status": gcloud_status,
        "environment": {
            "cwd": os.getcwd(),
            "credentials_set": "GOOGLE_APPLICATION_CREDENTIALS" in os.environ
        }
    }
