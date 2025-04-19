# backend/services/navigation_service.py
import os
import logging
import requests
from typing import Optional, Tuple, List, Any, Dict
from bs4 import BeautifulSoup # Import BeautifulSoup
import httpx # Keep for type hint in __init__
import requests # **** ADD requests IMPORT ****
import asyncio # **** ADD asyncio IMPORT ****
import functools # **** ADD functools IMPORT ****


# Use the refactored client
from ..core.clients.google_maps import GoogleMapsClient, COMPLEX_PLACE_TYPES
from ..core.config import Settings
from ..core.exception import NavigationError, InvalidRequestError, StateError
# Use the updated models
from ..models.internal import RouteInfo, RouteWarning, OrderContext

logger = logging.getLogger(__name__)

FLOOD_ALERT_LEVELS = {"alert", "warning", "danger"}

class NavigationService:
    """Handles navigation-related tasks like routing, ETA, and checks using Routes API."""

    def __init__(self, maps_client: GoogleMapsClient, http_client: httpx.AsyncClient, settings: Settings):
        self.maps_client = maps_client
        self.http_client = http_client # Store the http client
        self.settings = settings
        logger.debug("NavigationService initialized (using Routes API via client and httpx).")

    async def get_route_and_eta(
        self,
        origin: Tuple[float, float] | str,
        destination: Tuple[float, float] | str,
        context: Optional[Dict] = None
        ) -> RouteInfo:
        """Gets route and ETA information using Routes API."""
        if not origin:
             raise InvalidRequestError("Origin (current location) is required for routing.")
        if not destination:
             raise InvalidRequestError("Destination is required for routing.")

        logger.info(f"Getting route from '{origin}' to '{destination}' using Routes API.")
        try:
            # Call the new method in the client
            route_info = await self.maps_client.compute_route(
                origin=origin,
                destination=destination,
                departure_time=None # Use current time for traffic
            )

            if not route_info:
                logger.warning(f"No route found by Routes API from '{origin}' to '{destination}'.")
                raise NavigationError(f"Could not find a route to {destination}.")

            # Populate start/end addresses using geocoding if needed (client helper)
            # Addresses are important for user feedback
            route_info = await self.maps_client._populate_addresses(route_info, origin, destination)

            logger.info(f"Route found: {route_info.duration_text}, {route_info.distance_text}")
            return route_info

        except NavigationError as e:
            logger.error(f"Navigation error getting route: {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error in get_route_and_eta: {e}", exc_info=True)
            raise NavigationError(f"An unexpected error occurred during routing: {e}", original_exception=e)
    
    def fetch_directions(self, origin: str, destination: str) -> dict:
        """
        Fetch directions from Google Maps Directions API.
        """
        try:
            api_key = os.getenv("GOOGLE_MAPS_API_KEY")  # Assume API key is in settings
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
                raise NavigationError(f"Error fetching directions: {data.get('error_message', 'Unknown error')}")

            return data
        except requests.RequestException as e:
            raise NavigationError(f"Error fetching directions: {str(e)}")
        
    async def fetch_coordinates(self, place_name: str) -> dict:
        """
        Fetch the coordinates of a place using Google Places API.
        """
        try:
            api_key = os.getenv("GOOGLE_MAPS_API_KEY")  # Assume API key is in settings
            url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
            params = {
                "query": place_name,
                "key": api_key,
            }
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data["status"] != "OK" or not data["results"]:
                raise NavigationError(f"Place not found: {place_name}")

            location = data["results"][0]["geometry"]["location"]
            return {"latitude": location["lat"], "longitude": location["lng"]}
        except requests.RequestException as e:
            raise NavigationError(f"Error fetching place coordinates: {str(e)}")
        
    async def check_for_reroute(
        self,
        current_location: Tuple[float, float],
        destination: Tuple[float, float] | str,
        current_route_info: Optional[RouteInfo] = None
        ) -> Optional[RouteInfo]:
        """Checks for a better route using Routes API via the client."""
        try:
             new_route = await self.maps_client.check_for_reroute(
                 current_location=current_location,
                 destination=destination,
                 current_route_info=current_route_info
             )
             if new_route:
                  # Populate addresses for the new route before returning
                  new_route = await self.maps_client._populate_addresses(new_route, current_location, destination)
             return new_route
        except NavigationError as e:
            logger.error(f"Error during reroute check service call: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during reroute check service call: {e}", exc_info=True)
            return None

    async def check_flood_zones(
        self,
        route_info: Optional[RouteInfo] = None, # Keep route_info for potential future use
        location: Optional[Tuple[float, float]] = None
        ) -> List[RouteWarning]:
        """
        Checks for flood warnings based on driver's current state using scraped river level data.
        """
        warnings = []
        if not self.settings.FLOOD_CHECK_ENABLED:
            logger.debug("Flood check is disabled in settings.")
            return []
        if not location:
            logger.warning("Flood check requires current location (lat, lon).")
            return [] # Cannot perform check without location

        logger.info(f"Performing flood zone check for location {location} using publicinfobanjir data...")

        # 1. Get State from Location using Reverse Geocoding
        state_name = None
        try:
            geo_result = await self.maps_client.reverse_geocode_location(location)
            if geo_result and geo_result.get("address_components"):
                for component in geo_result["address_components"]:
                    types = component.get("types", [])
                    # State level component in Google Geocoding API
                    if "administrative_area_level_1" in types:
                        state_name = component.get("long_name")
                        logger.info(f"Determined state from location {location} as: {state_name}")
                        break
            if not state_name:
                 logger.warning(f"Could not determine state name from reverse geocoding result for {location}.")
                 return [] # Cannot proceed without state

        except NavigationError as e:
            logger.error(f"Reverse geocoding failed during flood check for location {location}: {e}")
            return [] # Cannot proceed
        except Exception as e:
            logger.error(f"Unexpected error during reverse geocoding for flood check: {e}", exc_info=True)
            return [] # Cannot proceed

        # 2. Map State Name to State Code
        state_code = self._get_state_code(state_name)
        if not state_code:
            logger.error(f"Cannot perform flood check: Failed to map state name '{state_name}' to a known code.")
            return []

        # 3. Fetch and Parse River Level Data for the State
        try:
            station_levels = await self._fetch_parse_river_levels(state_code)
        except Exception as e:
             logger.error(f"Failed to fetch or parse flood data for state {state_code}: {e}", exc_info=True)
             # Optionally return a warning indicating data couldn't be fetched
             warnings.append(RouteWarning(type="FLOOD_DATA_ERROR", message=f"Could not retrieve latest flood data for {state_name}."))
             return warnings

        # 4. Check for Alert Levels in the Parsed Data
        alert_stations = []
        for station in station_levels:
            status = station.get("status", "Unknown").lower()
            if status in FLOOD_ALERT_LEVELS:
                station_name = station.get('station_name', 'Unknown Station')
                district = station.get('district', 'Unknown District')
                level = station.get('water_level_m', 'N/A')
                last_updated = station.get('last_updated', 'N/A')
                alert_stations.append(f"{station_name} ({district}) at {status.capitalize()} level ({level}m as of {last_updated})")

        # 5. Create Warnings
        if alert_stations:
            num_alerts = len(alert_stations)
            # Create a single, more general warning for the state
            warning_message = f"Potential flood alerts: {num_alerts} station(s) in {state_name} reporting elevated levels (Alert/Warning/Danger)."
            # Optionally list the first few stations
            if num_alerts <= 3:
                 warning_message += " Details: " + "; ".join(alert_stations)
            else:
                 warning_message += f" Example: {alert_stations[0]}"

            logger.warning(f"Flood Alert: {warning_message}")
            warnings.append(RouteWarning(type="FLOOD_ALERT", message=warning_message))
        else:
            logger.info(f"No flood alerts (Alert/Warning/Danger) found for state: {state_name} ({state_code}) based on latest check.")

        # Include placeholder warnings if any (can be removed if only using scraped data)
        # ... (existing placeholder logic based on destination address can be kept or removed) ...
        # if "bedok" in destination_address.lower() or "geylang" in destination_address.lower():
        #     if not any("bedok" in w.message.lower() or "geylang" in w.message.lower() for w in warnings):
        #          warnings.append(RouteWarning(type="FLOOD_PLACEHOLDER", message=f"Placeholder: Potential flood risk noted in {destination_address}.", location=location))


        return warnings
    async def is_pickup_location_complex(self, order_context: OrderContext) -> bool:
        """
        Checks if the pickup location is likely complex (mall, airport, etc.)
        using Places API Details (preferred) or Geocoding results.

        Args:
            order_context: The order context containing pickup Place ID or address.

        Returns:
            True if the location is likely complex, False otherwise.
        """
        place_id = order_context.passenger_pickup_place_id
        address = order_context.passenger_pickup_address
        location_identifier = address or f"Place ID {place_id}" if place_id else "Unknown Location"

        if not place_id and not address:
            logger.warning(
                f"Cannot check location complexity for order {order_context.order_id}: No Place ID or address provided.")
            return False  # Assume not complex if no info

        details = None
        place_types_found = None

        # 1. Try Place Details using Place ID (most reliable)
        if place_id:
            logger.info(f"Checking complexity for '{location_identifier}' using Place ID: {place_id}")
            try:
                # Request 'types' field specifically
                details = await self.maps_client.get_place_details(place_id, fields=['types'])
                if details and details.get("types"):
                    place_types_found = set(details["types"])
                    logger.debug(f"Types found via Place Details: {place_types_found}")
            except NavigationError as e:
                logger.warning(
                    f"Failed to get Place Details for ID {place_id} during complexity check: {e}. Will try geocoding address if available.")
            except Exception as e:
                logger.error(f"Unexpected error getting Place Details for {place_id} during complexity check",
                             exc_info=True)

        # 2. If Place Details failed or no Place ID, try Geocoding the address
        if not place_types_found and address:
            logger.info(f"Checking complexity for '{location_identifier}' by geocoding address.")
            try:
                geo_result = await self.maps_client.geocode_address(address)
                if geo_result and geo_result.get("types"):
                    # Use types from geocoding result (might be less specific)
                    place_types_found = set(geo_result["types"])
                    logger.debug(f"Types found via Geocoding: {place_types_found}")
            except NavigationError as e:
                logger.warning(f"Failed to geocode address '{address}' for complexity check: {e}")
            except Exception as e:
                logger.error(f"Unexpected error geocoding address '{address}' for complexity check", exc_info=True)

        # 3. Check if found types intersect with our complex types list
        if place_types_found:
            complex_matches = place_types_found.intersection(COMPLEX_PLACE_TYPES)
            if complex_matches:
                logger.info(
                    f"Pickup location '{location_identifier}' identified as COMPLEX based on types: {complex_matches}")
                return True
            else:
                logger.info(
                    f"Pickup location '{location_identifier}' types ({place_types_found}) do not indicate complexity.")
                return False
        else:
            # Default to not complex if type check fails or yields no results
            logger.info(
                f"Could not determine complexity for '{location_identifier}' based on available info. Assuming NOT complex.")
            return False

    def _get_state_code(self, state_name_from_geo: str) -> Optional[str]:
        """Maps a state name (from geocoding) to the website's state code."""
        if not state_name_from_geo:
            return None
        # Normalize the input name (lowercase)
        normalized_state = state_name_from_geo.lower()
        # Look up in the settings map
        code = self.settings.MALAYSIA_STATE_CODES.get(normalized_state)
        if code:
            logger.debug(f"Mapped state name '{normalized_state}' to code '{code}'.")
        else:
            logger.warning(f"Could not map state name '{normalized_state}' to a known state code.")
        return code

    # --- NEW: Helper to scrape and parse flood data ---
    async def _fetch_parse_river_levels(self, state_code: str) -> List[Dict[str, str]]:
        """Fetches and parses river level data using synchronous requests library."""
        stations_data = []
        target_url = f"{self.settings.FLOOD_DATA_BASE_URL}/aras-air/data-paras-air/aras-air-data/"
        params = {
            'state': state_code,
            'district': 'ALL',
            'station': 'ALL',
            'lang': 'en'
        }
        logger.info(f"Fetching river level data from {target_url} for state {state_code} using 'requests' library...")

        try:
            # --- Use synchronous requests in an executor ---
            loop = asyncio.get_running_loop()
            requests_get_with_args = functools.partial(
                requests.get,
                params=params,
                timeout=15.0,
                verify=False # Disable verification directly in requests
            )
            # Log the dangerous setting
            logger.warning("!!! Disabling SSL verification for 'requests' call to flood site (Hackathon Fix) !!!")

            # Run the synchronous call in the default executor
            response = await loop.run_in_executor(
                None,
                requests_get_with_args, # The partial function
                target_url # The positional URL argument
            )
            # --------------------------------------------

            response.raise_for_status() # Raise HTTP errors
            html_content = response.text
            logger.debug(f"Successfully fetched HTML content ({len(html_content)} bytes) via 'requests'.")

            # --- Parsing logic remains the same ---
            soup = BeautifulSoup(html_content, 'lxml')
            table = soup.find('table')
            if not table:
                logger.warning(f"Could not find the data table on the flood page for state {state_code}.")
                return []
            tbody = table.find('tbody')
            if not tbody:
                 logger.warning(f"Could not find the tbody within the data table for state {state_code}.")
                 return []
            # ... (rest of parsing logic as before) ...
            header_map = { # Map column index to a meaningful key
                2: "station_name", 3: "district", 6: "last_updated", 7: "water_level_m",
                8: "status_normal", 9: "status_alert", 10: "status_warning", 11: "status_danger",
            }
            status_keys = { 8: "Normal", 9: "Alert", 10: "Warning", 11: "Danger" }
            rows = tbody.find_all('tr')
            logger.debug(f"Found {len(rows)} rows in the table body.")
            for row in rows:
                cells = row.find_all('td')
                if len(cells) < 12: continue
                station_info = {}
                current_status = "Unknown"
                for idx, cell in enumerate(cells):
                    key = header_map.get(idx)
                    if key: station_info[key] = cell.text.strip()
                    if idx in status_keys:
                        cell_text = cell.text.strip()
                        if cell_text: current_status = status_keys[idx]
                station_info['status'] = current_status
                if station_info.get("station_name"):
                    stations_data.append(station_info)
                    if current_status.lower() in FLOOD_ALERT_LEVELS:
                        logger.debug(f"Parsed station data with alert: {station_info}")
            logger.info(f"Parsed {len(stations_data)} stations for state {state_code}.")
            return stations_data
            # --- End Parsing Logic ---

        except requests.exceptions.SSLError as e:
             # Catch requests-specific SSL error
             logger.error(f"Requests SSL error fetching flood data for {state_code}: {e}", exc_info=True)
             # Check if it's still the same underlying issue
             if "UNSAFE_LEGACY_RENEGOTIATION_DISABLED" in str(e):
                 logger.error(">>> Still encountering UNSAFE_LEGACY_RENEGOTIATION even with requests and verify=False <<<")
             return []
        except requests.exceptions.RequestException as e:
            # Catch other requests errors (timeout, connection error, etc.)
            logger.error(f"Requests exception fetching flood data for state {state_code}: {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Error parsing flood data HTML for state {state_code}: {e}", exc_info=True)
            return []