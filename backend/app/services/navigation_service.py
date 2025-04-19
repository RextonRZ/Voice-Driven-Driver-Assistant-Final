# backend/services/navigation_service.py
import logging
from typing import Optional, Tuple, List, Any, Dict

# Use the refactored client
from ..core.clients.google_maps import GoogleMapsClient, COMPLEX_PLACE_TYPES
from ..core.config import Settings
from ..core.exception import NavigationError, InvalidRequestError, StateError
# Use the updated models
from ..models.internal import RouteInfo, RouteWarning, OrderContext

logger = logging.getLogger(__name__)

class NavigationService:
    """Handles navigation-related tasks like routing, ETA, and checks using Routes API."""

    def __init__(self, maps_client: GoogleMapsClient, settings: Settings):
        self.maps_client = maps_client
        self.settings = settings
        logger.debug("NavigationService initialized (using Routes API via client).")

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
        route_info: Optional[RouteInfo] = None,
        location: Optional[Tuple[float, float]] = None
        ) -> List[RouteWarning]:
        """Checks for flood warnings (Placeholder logic remains)."""
        # ... existing placeholder logic ...
        # Note: The route_info.warnings now come from the Routes API parse
        if not self.settings.FLOOD_CHECK_ENABLED:
             return []

        warnings = []
        logger.info("Performing flood zone check (Placeholder)...")

        # 1. Check warnings from Routes API response
        if route_info and route_info.warnings:
             # Filter or reformat warnings if needed
             for warning in route_info.warnings:
                 # You might want to check severity or specific messages
                 warnings.append(warning) # Add directly for now

        # 2. Query External Flood APIs (Placeholder)
        # ...

        # Simple Placeholder based on address (use populated address now)
        destination_address = route_info.end_address if route_info else ""
        if location and not route_info:
            # Maybe geocode location to get an address hint?
             geo_result = await self.maps_client.geocode_address(f"{location[0]},{location[1]}") # Geocode tuple
             destination_address = geo_result.get("formatted_address", f"area around {location}") if geo_result else f"area around {location}"

        if "bedok" in destination_address.lower() or "geylang" in destination_address.lower():
            # Ensure no duplicates if API already warned
            if not any("bedok" in w.message.lower() or "geylang" in w.message.lower() for w in warnings):
                 warnings.append(RouteWarning(type="FLOOD_PLACEHOLDER", message=f"Placeholder: Potential flood risk noted in {destination_address}.", location=location))

        if warnings:
             logger.warning(f"Flood check found {len(warnings)} potential warnings.")
        else:
             logger.info("No flood warnings found.")

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