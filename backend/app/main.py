from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .api.v1 import api_router

# Create FastAPI app
app = FastAPI(title=settings.APP_NAME)  # Updated to use APP_NAME instead of PROJECT_NAME

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development; restrict this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(
    api_router, 
    prefix=settings.API_V1_STR
)

@app.get("/")
async def root():
    """Root endpoint to verify the API is running."""
    return {"message": f"Welcome to {settings.APP_NAME} API"}
