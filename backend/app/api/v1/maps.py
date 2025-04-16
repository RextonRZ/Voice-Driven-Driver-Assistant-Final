from fastapi import APIRouter, Depends, HTTPException, Query
from ...services.maps_service import MapsService
from ...dependencies.auth import get_current_user
from ...models.user import User
from typing import Optional
import os

router = APIRouter()

# Development mode - set to False in production
DEV_MODE = True  # or read from environment: os.getenv("DEV_MODE", "false").lower() == "true"

@router.get("/google-maps-key")
def get_google_maps_key(
    platform: Optional[str] = Query(None, description="Parameter kept for compatibility"),
    current_user: User = Depends(get_current_user) if not DEV_MODE else None
):
    """
    Endpoint to get the Google Maps API key.
    In production, only authenticated users can access this endpoint.
    In development mode, authentication is bypassed.
    """
    try:
        MapsService.validate_api_key()
        return {"api_key": MapsService.get_api_key()}
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
