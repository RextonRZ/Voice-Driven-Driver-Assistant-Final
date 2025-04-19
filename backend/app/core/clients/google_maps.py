# backend/core/clients/google_maps.py
import logging
import googlemaps # Keep for Places/Geocoding
from google.maps import routing_v2 # Use the new Routes API library
from google.type import latlng_pb2 # Import the LatLng structure
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict, Any
import asyncio
import os
from google.api_core.exceptions import GoogleAPIError, InvalidArgument
import functools

from ..config import Settings
from ..exception import NavigationError, ConfigurationError, InvalidRequestError
from ...models.internal import RouteInfo, RouteWarning, RouteLocalizedValues

logger = logging.getLogger(__name__)

# Define complex place types for gate check logic
COMPLEX_PLACE_TYPES = {
    "airport", "amusement_park", "bus_station", "hospital", "library",
    "light_rail_station", "shopping_mall", "stadium", "subway_station",
    "tourist_attraction", "train_station", "transit_station", "university",
    "zoo", "department_store", "parking" , "convention_center", "port"
}

class GoogleMapsClient:
    """
    Client using Google Maps Routes API for routing and
    legacy Geocoding/Places API for other lookups.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.api_key = os.getenv("GOOGLE_MAPS_API_KEY", settings.GOOGLE_MAPS_API_KEY)
        if not settings.GOOGLE_MAPS_API_KEY or settings.GOOGLE_MAPS_API_KEY == "YOUR_GOOGLE_MAPS_API_KEY":
            logger.error("GOOGLE_MAPS_API_KEY is not configured.")
            raise ConfigurationError("GOOGLE_MAPS_API_KEY must be set.")

        try:
            # Initialize Routes API client (uses ADC implicitly or API Key if configured)
            self.routes_client = routing_v2.RoutesAsyncClient()
            logger.info("Google Maps Routes API AsyncClient initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize Google Maps Routes client: {e}", exc_info=True)
            raise ConfigurationError(f"Google Maps Routes client initialization failed: {e}", original_exception=e)

        try:
             # Initialize legacy client for Geocoding/Places
             self.legacy_client = googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)
             logger.info("Google Maps legacy client (for Geocode/Places) initialized.")
        except Exception as e:
             logger.error(f"Failed to initialize Google Maps legacy client: {e}", exc_info=True)
             # Allow proceeding if only routing is essential? Or fail hard? Let's fail hard.
             raise ConfigurationError(f"Google Maps legacy client initialization failed: {e}", original_exception=e)


    def _make_waypoint(self, location: Tuple[float, float] | str) -> routing_v2.Waypoint:
        """Creates a Waypoint object for the Routes API."""
        if isinstance(location, str):
            # Use address for geocoding by the API
            return routing_v2.Waypoint(address=location)
        elif isinstance(location, tuple) and len(location) == 2:
            # Use LatLng coordinates
            return routing_v2.Waypoint(
                location=routing_v2.Location(
                    lat_lng=latlng_pb2.LatLng(latitude=location[0], longitude=location[1])
                )
            )
        else:
            raise InvalidRequestError(f"Invalid location format for waypoint: {location}")

    def _parse_routes_api_warnings(self, response: routing_v2.ComputeRoutesResponse) -> List[RouteWarning]:
        """Parses warnings and advisories from the Routes API response."""
        warnings = []
        if response.routes and response.routes[0]:
            route = response.routes[0]
            # Travel Advisory (e.g., tolls)
            if route.travel_advisory:
                 if route.travel_advisory.toll_info:
                     # Example: just add a generic toll warning
                     warnings.append(RouteWarning(severity="INFO", message="Route contains tolls."))
                 # Add parsing for speed_reading_intervals, fuel_consumption_microliters etc. if needed

            # Warnings (usually strings about limitations)
            # The API schema for route.warnings isn't well-documented for v2 yet,
            # assuming it might be a list of strings or simple objects. Adjust as needed.
            if hasattr(route, 'warnings') and route.warnings:
                 for w in route.warnings:
                      if isinstance(w, str):
                           warnings.append(RouteWarning(severity="WARNING", message=w))
                      # elif isinstance(w, some_structured_warning_object):
                      #     warnings.append(RouteWarning(severity=w.severity, message=w.text))

        return warnings


    def _parse_compute_routes_response(
        self,
        response: routing_v2.ComputeRoutesResponse
        ) -> Optional[RouteInfo]:
        """Parses the ComputeRoutesResponse into a RouteInfo object."""
        if not response.routes:
            logger.warning("Received empty routes list from Routes API.")
            return None

        try:
            # Assume the first route is the primary one
            route = response.routes[0]

            # Extract core info
            duration: Optional[timedelta] = route.duration if route.duration else None
            distance_meters: Optional[int] = route.distance_meters if route.distance_meters else None
            polyline_encoded: Optional[str] = route.polyline.encoded_polyline if route.polyline else None

            # Extract localized values (requires specific field mask)
            localized_vals = None
            if route.localized_values:
                 localized_vals = RouteLocalizedValues(
                     distance=route.localized_values.distance.text if route.localized_values.distance else None,
                     duration=route.localized_values.duration.text if route.localized_values.duration else None,
                     static_duration=route.localized_values.static_duration.text if route.localized_values.static_duration else None,
                 )

            # Extract warnings
            warnings = self._parse_routes_api_warnings(response)

            # Create the base RouteInfo object
            route_info = RouteInfo(
                duration=duration,
                distance_meters=distance_meters,
                polyline_encoded=polyline_encoded,
                warnings=warnings,
                localized_values=localized_vals
            )

            # Derive user-friendly text fields (if localized values are present)
            if localized_vals:
                route_info.duration_text = localized_vals.duration
                route_info.distance_text = localized_vals.distance
            # Fallback using raw values if localized text not available/requested
            if not route_info.duration_text and duration:
                 route_info.duration_text = f"{round(duration.seconds / 60)} mins"
            if not route_info.distance_text and distance_meters:
                 route_info.distance_text = f"{distance_meters / 1000:.1f} km"

            return route_info

        except (AttributeError, IndexError, TypeError, ValueError) as e:
            logger.error(f"Error parsing Google Routes API response: {e}. Response snippet: {response.routes[0] if response.routes else 'N/A'}", exc_info=True)
            raise NavigationError(f"Failed to parse navigation data from Routes API: {e}", original_exception=e)


    async def compute_route(
        self,
        origin: Tuple[float, float] | str,
        destination: Tuple[float, float] | str,
        mode: Optional[str] = None, # e.g., "DRIVE", "WALK", "TWO_WHEELER"
        departure_time: Optional[datetime] = None, # Use datetime object for future/specific times
        compute_alternative_routes: bool = False,
        route_preference: Optional[str] = "TRAFFIC_AWARE_OPTIMAL", # e.g., "TRAFFIC_AWARE", "TRAFFIC_UNAWARE"
        region_code: Optional[str] = None
    ) -> Optional[RouteInfo]:
        """
        Computes a route using the Google Maps Routes API v2.

        Args:
            origin: Lat/Lon tuple or address string.
            destination: Lat/Lon tuple or address string.
            mode: Travel mode (use routing_v2.RouteTravelMode enums like DRIVE). Defaults to settings.
            departure_time: Specific departure time. If None, uses current time.
            compute_alternative_routes: Whether to request alternatives.
            route_preference: Routing preference (TRAFFIC_AWARE_OPTIMAL, TRAFFIC_AWARE, TRAFFIC_UNAWARE).
            region_code: Region bias (e.g., 'SG'). Uses settings default if None.

        Returns:
            A RouteInfo object or None if no route found.

        Raises:
            NavigationError: If the API call fails or parsing fails.
            InvalidRequestError: For invalid inputs.
        """
        if not origin or not destination:
            raise InvalidRequestError("Origin and destination are required for routing.")

        try:
            origin_wp = self._make_waypoint(origin)
            destination_wp = self._make_waypoint(destination)
        except InvalidRequestError as e:
            logger.error(f"Failed to create waypoints: {e}")
            raise e

        effective_mode_str = mode or self.settings.MAPS_DEFAULT_TRAVEL_MODE
        try:
            # Map string mode to Routes API enum
            travel_mode_enum = routing_v2.RouteTravelMode[effective_mode_str.upper()]
        except KeyError:
            logger.warning(f"Invalid travel mode '{effective_mode_str}'. Defaulting to DRIVE.")
            travel_mode_enum = routing_v2.RouteTravelMode.DRIVE

        try:
             # Map string preference to enum
             routing_preference_enum = routing_v2.RoutingPreference[route_preference.upper()]
        except KeyError:
             logger.warning(f"Invalid route preference '{route_preference}'. Defaulting to TRAFFIC_AWARE_OPTIMAL.")
             routing_preference_enum = routing_v2.RoutingPreference.TRAFFIC_AWARE_OPTIMAL

        # Define the fields to request in the response (crucial!)
        field_mask = self.settings.MAPS_ROUTES_FIELD_MASK
        if not field_mask:
             logger.warning("MAPS_ROUTES_FIELD_MASK not set in config, using a basic default.")
             field_mask = "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline,routes.localized_values"


        request = routing_v2.ComputeRoutesRequest(
            origin=origin_wp,
            destination=destination_wp,
            travel_mode=travel_mode_enum,
            routing_preference=routing_preference_enum,
            # Add departure_time if provided
            departure_time=departure_time if departure_time else None,
            compute_alternative_routes=compute_alternative_routes,
            language_code=self.settings.NLU_PROCESSING_LANGUAGE, # Or user's language? Let's use NLU lang for consistency
            region_code=region_code or self.settings.MAPS_DEFAULT_REGION,
            # Units.METRIC or Units.IMPERIAL - default is METRIC
            # units=routing_v2.Units.METRIC,
            # requested_reference_routes # For comparing alternatives
            # route_modifiers # For tolls, highways etc.
        )

        logger.info(f"Requesting route via Routes API from '{origin}' to '{destination}'. Mode: {travel_mode_enum.name}, Preference: {routing_preference_enum.name}")
        logger.debug(f"Routes API FieldMask: {field_mask}")

        try:
            response = await self.routes_client.compute_routes(
                request=request,
                metadata=[('x-goog-fieldmask', field_mask)] # Pass field mask in metadata
            )

            # Parse the result
            route_info = self._parse_compute_routes_response(response)

            if route_info:
                 logger.info(f"Routes API returned route. Duration: {route_info.duration_text}, Distance: {route_info.distance_text}")
                 # We need to geocode separately to get start/end addresses if they were passed as strings
                 # This makes the flow a bit more complex. Alternatively, parse from response if available?
                 # Routes API response doesn't seem to directly return full addresses easily.
            else:
                 logger.warning(f"No route found by Routes API between '{origin}' and '{destination}'.")


            return route_info

        except InvalidArgument as e:
             logger.error(f"Invalid argument provided to Routes API: {e}", exc_info=True)
             # Check if it's a ZERO_RESULTS type error
             if "Unable to compute routes" in str(e) or "ZERO_RESULTS" in str(e).upper(): # Heuristic check
                 logger.warning(f"Routes API returned ZERO_RESULTS for query: {origin} -> {destination}")
                 return None
             raise NavigationError(f"Invalid argument for Routes API: {e}", original_exception=e)
        except GoogleAPIError as e:
            logger.error(f"Google Routes API error: {e}", exc_info=True)
            raise NavigationError(f"Routes API request failed: {e}", original_exception=e)
        except Exception as e:
            # Catch parsing errors or other unexpected issues
            logger.error(f"Unexpected error computing route: {e}", exc_info=True)
            if isinstance(e, NavigationError): # Re-raise if it's already our specific type
                raise e
            raise NavigationError(f"An unexpected error occurred during route computation: {e}", original_exception=e)


    # --- Geocoding and Places methods using the legacy client ---

    async def geocode_address(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Geocodes an address string to coordinates and Place ID using legacy client.

        Returns:
            A dictionary containing 'geometry.location' (dict with lat/lng)
            and 'place_id', or None if not found.
        """
        if not address:
            raise InvalidRequestError("Address string is required for geocoding.")
        logger.info(f"Geocoding address using legacy client: '{address}'")
        try:
            loop = asyncio.get_running_loop()
            geocode_func_with_kwargs = functools.partial(
                self.legacy_client.geocode,
                region=self.settings.MAPS_DEFAULT_REGION
            )

            geocode_result = await loop.run_in_executor(
                None,
                geocode_func_with_kwargs,
                address
            )
            if geocode_result:
                first_result = geocode_result[0]
                logger.info(
                    f"Geocoding successful. Place ID: {first_result.get('place_id')}, Types: {first_result.get('types', [])}")
                return {
                    "geometry": first_result.get("geometry", {}),
                    "place_id": first_result.get("place_id"),
                    "formatted_address": first_result.get("formatted_address"),
                    "types": first_result.get("types", [])  # Return types from geocoding
                }
            else:
                logger.warning(f"Geocoding returned no results for address: '{address}'")
                return None
        except googlemaps.exceptions.ApiError as e:
            logger.error(f"Google Geocoding API error: {e}", exc_info=True)
            raise NavigationError(f"Geocoding API request failed: {e}", original_exception=e)
        except Exception as e:
            logger.error(f"Unexpected error during geocoding: {e}", exc_info=True)
            raise NavigationError(f"An unexpected error occurred during geocoding: {e}", original_exception=e)

    async def reverse_geocode_location(self, location: Tuple[float, float]) -> Optional[Dict[str, Any]]:
        """
        Reverse geocodes coordinates to get address components using legacy client.

        Returns:
            A dictionary similar to geocode_address (containing address_components),
            or None if not found.
        """
        if not location or len(location) != 2:
            raise InvalidRequestError("Valid (lat, lon) tuple is required for reverse geocoding.")

        lat, lon = location
        logger.info(f"Reverse geocoding location using legacy client: Lat={lat}, Lon={lon}")
        try:
            loop = asyncio.get_running_loop()
            reverse_geocode_result = await loop.run_in_executor(
                None,
                self.legacy_client.reverse_geocode,
                (lat, lon),
                # You can add result_type or location_type filters if needed
                # result_type=['administrative_area_level_1'] # Example: To potentially only get state faster
            )
            if reverse_geocode_result:
                # Return the first result, which is usually the most specific
                first_result = reverse_geocode_result[0]
                logger.info(f"Reverse geocoding successful. Formatted Address: {first_result.get('formatted_address')}")
                # Return structure similar to geocode for consistency
                return {
                    "geometry": first_result.get("geometry", {}),
                    "place_id": first_result.get("place_id"),
                    "formatted_address": first_result.get("formatted_address"),
                    "types": first_result.get("types", []),
                    "address_components": first_result.get("address_components", [])
                }
            else:
                logger.warning(f"Reverse geocoding returned no results for location: {location}")
                return None
        except googlemaps.exceptions.ApiError as e:
            logger.error(f"Google Reverse Geocoding API error: {e}", exc_info=True)
            raise NavigationError(f"Reverse Geocoding API request failed: {e}", original_exception=e)
        except Exception as e:
            logger.error(f"Unexpected error during reverse geocoding: {e}", exc_info=True)
            raise NavigationError(f"An unexpected error occurred during reverse geocoding: {e}", original_exception=e)

    async def get_place_details(
        self,
        place_id: str,
        fields: Optional[List[str]] = None # e.g., ['name', 'type', 'formatted_address']
        ) -> Optional[Dict[str, Any]]:
        """
        Gets details for a specific Place ID using the legacy client.

        Args:
            place_id: The Google Maps Place ID.
            fields: List of fields to request (recommended for efficiency). Ensure 'types' is included for complexity check.

        Returns:
            A dictionary containing the requested place details, or None if not found/error.
        """
        if not place_id:
            raise InvalidRequestError("Place ID is required to get details.")

        # Ensure 'types' is always requested for our complexity check logic
        request_fields = set(fields or [])
        request_fields.add('types') # Ensure 'types' is present
        # Add other useful defaults if fields is None
        if fields is None:
             request_fields.update(['place_id', 'name', 'formatted_address', 'geometry'])

        final_fields_list = list(request_fields)

        logger.info(f"Getting Place Details using legacy client for Place ID: '{place_id}', Fields: {final_fields_list}")
        try:
            loop = asyncio.get_running_loop()
            place_result = await loop.run_in_executor(
                None,
                self.legacy_client.place,
                place_id=place_id,
                fields=final_fields_list,
                # language= ? # Consider user's language?
            )
            if place_result and place_result.get('result'):
                logger.info(f"Place Details retrieved successfully for {place_id}. Types: {place_result.get('result', {}).get('types')}")
                return place_result.get('result')
            else:
                logger.warning(f"Places API returned no result for Place ID: '{place_id}'. Response: {place_result}")
                return None
        except googlemaps.exceptions.ApiError as e:
             # Handle specific errors like NOT_FOUND gracefully
             if e.status == 'NOT_FOUND':
                  logger.warning(f"Place ID '{place_id}' not found by Places API.")
                  return None
             logger.error(f"Google Places API error: {e}", exc_info=True)
             raise NavigationError(f"Places API request failed: {e}", original_exception=e)
        except Exception as e:
            logger.error(f"Unexpected error getting place details: {e}", exc_info=True)
            raise NavigationError(f"An unexpected error occurred getting place details: {e}", original_exception=e)

    # --- Reroute Check (Needs adaptation) ---
    async def check_for_reroute(
        self,
        current_location: Tuple[float, float],
        destination: Tuple[float, float] | str,
        current_route_info: Optional[RouteInfo] = None # Now expects new RouteInfo structure
        ) -> Optional[RouteInfo]:
        """
        Checks if a significantly better route exists using the Routes API.
        Comparison logic is still a placeholder.
        """
        logger.info(f"Checking for potential reroute from {current_location} to {destination} using Routes API")
        try:
            new_route_info = await self.compute_route(
                origin=current_location,
                destination=destination,
                departure_time=None # Use current time for traffic
            )

            if not new_route_info:
                logger.info("Reroute check: No new route found by Routes API.")
                return None

            # --- Comparison Logic (Placeholder - Needs to compare Durations) ---
            if current_route_info and current_route_info.duration:
                 current_duration_sec = current_route_info.duration.seconds
                 new_duration_sec = new_route_info.duration.seconds if new_route_info.duration else float('inf')
                 threshold_sec = 300 # e.g., only suggest if > 5 mins faster

                 logger.info(f"Reroute check: Current route duration {current_duration_sec}s, New check duration {new_duration_sec}s.")
                 if new_duration_sec < current_duration_sec - threshold_sec:
                    logger.info("Reroute suggested: New route is significantly faster.")
                    # Populate start/end address if needed before returning
                    # new_route_info = await self._populate_addresses(new_route_info, current_location, destination)
                    return new_route_info
                 else:
                    logger.info("No significant reroute advantage found.")
                    return None
            else:
                 logger.info("Reroute check: No current route duration provided for comparison.")
                 return None # Don't suggest reroute without comparison baseline

        except NavigationError as e:
            logger.error(f"Error during reroute check navigation query: {e}")
            return None
        except Exception as e:
             logger.error(f"Unexpected error during reroute check: {e}", exc_info=True)
             return None

    # Helper potentially needed if addresses aren't in RouteInfo directly
    async def _populate_addresses(self, route_info: RouteInfo, origin_input: Any, dest_input: Any) -> RouteInfo:
         """Populates start/end address via geocoding if not already present."""
         # This logic depends on whether compute_route returns addresses or if we need separate geocoding calls
         # For now, assume they need separate population if inputs were strings
         if isinstance(origin_input, str) and not route_info.start_address:
              geo_origin = await self.geocode_address(origin_input)
              route_info.start_address = geo_origin.get("formatted_address") if geo_origin else origin_input
         if isinstance(dest_input, str) and not route_info.end_address:
              geo_dest = await self.geocode_address(dest_input)
              route_info.end_address = geo_dest.get("formatted_address") if geo_dest else dest_input
         return route_info