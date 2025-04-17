import logging
from fastapi import APIRouter, Depends, HTTPException, status, Body

# Models
from ..models.request import CrashDetectionRequest, AnalyzeSleepinessRequest # Import new request model
from ..models.response import SafetyResponse
from ..models.internal import CrashReport, SleepinessReport # Import internal models
# Services & Dependencies
from ..services.safety_service import SafetyService
# Exceptions
from ..core.exception import SafetyError, ConfigurationError, CommunicationError, InvalidRequestError

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/safety",
    tags=["Safety Features"],
)

@router.post(
    "/crash-detected",
    response_model=SafetyResponse,
    summary="Report a detected crash event",
    description="Receives crash details (location, timestamp) from the frontend/device sensors "
                "and triggers the backend safety workflow (logging, notifications).",
    status_code=status.HTTP_202_ACCEPTED # Acknowledge receipt, processing happens async
)
async def crash_detected(
    request_data: CrashDetectionRequest,
    # safety_service: SafetyService = Depends(get_safety_service)
) -> SafetyResponse:
    """
    Endpoint to handle crash detection events reported by the client.
    """
    logger.critical(f"Received crash detection report via API for session {request_data.session_id}, driver {request_data.driver_id}")

    # Convert API request model to internal model for service
    crash_report = CrashReport(
        session_id=request_data.session_id,
        driver_id=request_data.driver_id,
        location=request_data.location,
        timestamp=request_data.timestamp # Assumes already datetime
    )

    try:
        # Delegate handling to the safety service
        # Note: This call might take time if it involves external notifications.
        # Consider running it in a background task for immediate API response.
        # For now, await its completion.
        result = await safety_service.handle_crash_detection(crash_report)

        logger.info(f"Crash detection handling completed for driver {request_data.driver_id}. Result: {result}")

        # Return a response based on the service outcome
        if result.get("status") == "failed":
             # If fetching contacts failed critically
             raise HTTPException(
                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                 detail=f"Failed to handle crash event: {result.get('errors', ['Unknown error'])[0]}"
             )
        elif not result.get("notifications_sent", True) and result.get("errors"):
             # Acknowledged, but some notifications failed
             return SafetyResponse(
                 status="acknowledged_with_errors",
                 message="Crash event acknowledged, but some notifications failed.",
                 details={"errors": result.get("errors")}
             )
        else:
             # Success or notifications disabled/no contacts
             return SafetyResponse(
                 status="acknowledged",
                 message="Crash event acknowledged and notifications processed (if applicable)."
             )

    except SafetyError as e: # Catch errors explicitly raised by the service
        logger.error(f"Safety service error handling crash report: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error handling crash: {e.message}")
    except CommunicationError as e:
        logger.error(f"Communication error during crash notification: {e}", exc_info=True)
        # Don't fail the whole request, return acknowledged with errors
        return SafetyResponse(
            status="acknowledged_with_errors",
            message=f"Crash event acknowledged, but notification failed: {e.message}",
            details={"errors": [str(e)]}
        )
    except InvalidRequestError as e: # e.g., if service needed driver_id but wasn't provided
        logger.warning(f"Invalid request for crash handling: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ConfigurationError as e:
         logger.critical(f"Configuration error during crash handling: {e}", exc_info=True)
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal configuration error prevented handling.")
    except Exception as e:
        logger.exception(f"Unexpected error handling crash detection report: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected internal error occurred.")


# --- Add Sleepiness Endpoint (Placeholder) ---
# @router.post("/sleepiness-detected")
# async def sleepiness_detected(...):
#    Requires image upload handling or data structure
#    logger.info("Received sleepiness detection report (Placeholder).")
#    image_data = ...
#    context = ...
#    report = await safety_service.analyze_sleepiness(image_data, context)
#    if report:
#       # Trigger alert or log?
#       logger.warning(f"Sleepiness detected: {report}")
#       return {"status": "sleepiness_detected", "report": report}
#    else:
#       return {"status": "ok"}