import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, Tuple

# Models
from ..models.request import RerouteCheckRequest
from ..models.response import NavigationResponse
from ..models.internal import RouteInfo # Use internal model for service layer
# Services & Dependencies
from ..services.navigation_service import NavigationService
from ..api.dependencies import get_navigation_service
# Exceptions
from ..core.exception import NavigationError, InvalidRequestError

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/navigation",
    tags=["Navigation Features"],
)

@router.post(
    "/reroute-check",
    response_model=NavigationResponse,
    summary="Check for a better route",
    description="Checks if a significantly faster or better route exists from the current location to the destination.",
)
async def check_reroute(
    request_data: RerouteCheckRequest,
    navigation_service: NavigationService = Depends(get_navigation_service)
) -> NavigationResponse:
    """
    Endpoint for the frontend to periodically check for better routes.
    """
    logger.info(f"Received reroute check request for session {request_data.session_id} from {request_data.current_location} to {request_data.destination_address}")

    try:
        # We might need current route info for better comparison, but request model doesn't mandate it yet
        new_route: Optional[RouteInfo] = await navigation_service.check_for_reroute(
            current_location=request_data.current_location,
            destination=request_data.destination_address,
            # current_route_info=... # Pass if available from request_data
        )

        if new_route:
            logger.info(f"Reroute suggested for session {request_data.session_id}.")
            return NavigationResponse(
                status="reroute_available",
                message="A potentially better route was found.",
                route_info=new_route,
                warnings=new_route.warnings
            )
        else:
            logger.info(f"No better reroute found for session {request_data.session_id}.")
            return NavigationResponse(
                status="no_reroute_needed",
                message="Current route appears optimal."
            )

    except InvalidRequestError as e:
        logger.warning(f"Invalid request for reroute check: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except NavigationError as e:
        logger.error(f"Navigation error during reroute check: {e}")
        # Don't necessarily fail request, maybe return status indicating check failed
        return NavigationResponse(
            status="error",
            message=f"Could not perform reroute check: {e.message}"
        )
        # Or raise 502 if it's an API failure:
        # raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Reroute check failed: {e.message}")
    except Exception as e:
        logger.exception(f"Unexpected error during reroute check: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred during reroute check.")