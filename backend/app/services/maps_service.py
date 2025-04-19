import logging
import urllib.parse
from typing import Optional, Dict
import aiohttp

logger = logging.getLogger(__name__)

class MapsService:
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def get_place_coordinates(self, place_name: str) -> Optional[Dict[str, float]]:
        """Fetches coordinates for a given place name using the Google Maps API."""
        try:
            encoded_place_name = urllib.parse.quote(place_name)
            url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_place_name}&key={self.api_key}"
            logger.info(f"Fetching coordinates for place: {place_name}. Request URL: {url}")

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 404:
                        logger.error(f"Place not found: {place_name}")
                        return None
                    if response.status != 200:
                        logger.error(f"Failed to fetch coordinates. Status: {response.status}")
                        return None

                    data = await response.json()
                    if data.get("status") != "OK":
                        logger.error(f"Google Maps API error: {data.get('status')}")
                        return None

                    location = data["results"][0]["geometry"]["location"]
                    return {"latitude": location["lat"], "longitude": location["lng"]}

        except Exception as e:
            logger.exception(f"Error fetching place coordinates for {place_name}: {e}")
            return None