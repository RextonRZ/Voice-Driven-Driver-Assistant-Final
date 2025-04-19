from fastapi import APIRouter

from .navigation import router as navigation_router

# Create the main API router and include all route modules
api_router = APIRouter()

# Include all endpoint routers with appropriate prefixes
api_router.include_router(navigation_router, prefix="/navigation", tags=["navigation"])