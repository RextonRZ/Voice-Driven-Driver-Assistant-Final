import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import requests
import os

router = APIRouter()

# Development mode - set to False in production
DEV_MODE = True  # or read from environment: os.getenv("DEV_MODE", "false").lower() == "true"

# Initialize the logger
Logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

@router.get("/directions")
def get_directions(
        origin: str = Query(..., description="Origin coordinates (latitude,longitude)"),
        destination: str = Query(..., description="Destination coordinates (latitude,longitude)"),
):
    """
    Fetch directions from Google Maps Directions API.
    """
    try:
        api_key = os.environ.get("GOOGLE_MAPS_API_KEY")

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
def get_coordinates(
    placeName: str = Query(..., description="Name of the place to search for"),
):
    """
    Fetch the coordinates of a place using Google Places API.
    """
    try:
        api_key = os.environ.get("GOOGLE_MAPS_API_KEY")

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