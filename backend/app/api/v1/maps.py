import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from ...services.maps_service import MapsService
from ...dependencies.auth import get_current_user
from ...models.user import User
from typing import Optional
import requests
import os

router = APIRouter()

# Development mode - set to False in production
DEV_MODE = True  # or read from environment: os.getenv("DEV_MODE", "false").lower() == "true"

# Initialize the logger
Logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


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


@router.get("/directions")
def get_directions(
        origin: str = Query(..., description="Origin coordinates (latitude,longitude)"),
        destination: str = Query(..., description="Destination coordinates (latitude,longitude)"),
        current_user: User = Depends(get_current_user) if not DEV_MODE else None
):
    """
    Fetch directions from Google Maps Directions API.
    """
    try:
        api_key = MapsService.get_api_key()

        url = "https://maps.googleapis.com/maps/api/directions/json"
        params = {
            "origin": origin,
            "destination": destination,
            "key": api_key,
            "departure_time": "now",
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        if data["status"] != "OK":
            raise HTTPException(status_code=400, detail=f"Error fetching directions: {data['error_message']}")

        return data
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error fetching directions: {str(e)}")


@router.get("/place-coordinates")
def get_directions(
        placeName: str = Query(..., description="Name of the place to search for"),
        current_user: User = Depends(get_current_user) if not DEV_MODE else None
):
    """
    Fetch the coordinates of a place using Google Places API.
    """
    try:
        api_key = MapsService.get_api_key()

        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            "query": placeName,
            "key": api_key,
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        if data["status"] != "OK" or not data["results"]:
            raise HTTPException(status_code=404, detail=f"Place not found: {placeName}")

        location = data["results"][0]["geometry"]["location"]
        return {"status": "OK", "coordinates": {"latitude": location["lat"], "longitude": location["lng"]}}
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error fetching place coordinates: {str(e)}")