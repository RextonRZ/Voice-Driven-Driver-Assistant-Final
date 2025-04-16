from fastapi import APIRouter

from .user import router as user_router
from .auth import router as auth_router
from .maps import router as maps_router

# Create the main API router and include all route modules
api_router = APIRouter()

# Include all endpoint routers with appropriate prefixes
api_router.include_router(user_router, prefix="/users", tags=["users"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(maps_router, prefix="/maps", tags=["maps"])
