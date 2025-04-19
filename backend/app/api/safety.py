import logging
from fastapi import APIRouter, Depends, HTTPException, status, Body
from typing import Optional

from ..models.request import CrashDetectionRequest, AnalyzeSleepinessRequest
from ..models.response import SafetyResponse
from ..models.internal import CrashReport, SleepinessReport
# Services & Dependencies
from ..services import safety_service
# Import the dependency getter
from ..api.dependencies import get_safety_service
# Exceptions
from ..core.exception import SafetyError, ConfigurationError, CommunicationError, InvalidRequestError
from ..services.safety_service import SafetyService

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


@router.post(
    "/analyze-sleepiness",
    response_model=SafetyResponse,
    summary="Analyze image frames for driver drowsiness",
    description="Receives a batch of recent image frames (base64 encoded) and analyzes them "
                "using the safety service to detect signs of drowsiness.",
    status_code=status.HTTP_200_OK # Return result directly
)
async def analyze_sleepiness(
    request_data: AnalyzeSleepinessRequest,
    safety_service: SafetyService = Depends(get_safety_service) # Inject the service
) -> SafetyResponse:
    """
    Endpoint to handle requests for drowsiness analysis based on image frames.
    """
    logger.info(f"Received sleepiness analysis request for session {request_data.session_id}, driver {request_data.driver_id}")

    if not safety_service.drowsiness_enabled:
        logger.warning("Sleepiness analysis requested, but feature is disabled in settings.")
        # Return a specific status indicating it's disabled or just that driver is awake?
        # Let's return 'feature_disabled' for clarity.
        return SafetyResponse(
            status="feature_disabled",
            message="Drowsiness detection feature is currently disabled in the server configuration."
        )

    try:
        # Call the analysis function in the safety service
        sleepiness_report: Optional[SleepinessReport] = await safety_service.analyze_driver_state(
            image_frames_base64=request_data.image_frames_base64,
            batch_duration_sec=request_data.batch_duration_sec
        )

        if sleepiness_report:
            logger.warning(f"Drowsiness detected for session {request_data.session_id}. Report: {sleepiness_report}")
            return SafetyResponse(
                status="drowsiness_detected",
                message="Potential drowsiness detected based on frame analysis.",
                details={
                    "confidence": sleepiness_report.confidence,
                    "evidence": sleepiness_report.evidence_type,
                    "timestamp": sleepiness_report.timestamp.isoformat()
                }
            )
        else:
            logger.info(f"No significant drowsiness detected for session {request_data.session_id}.")
            return SafetyResponse(
                status="driver_awake",
                message="Analysis complete. No significant signs of drowsiness detected."
            )

    except InvalidRequestError as e:
        logger.warning(f"Invalid request for sleepiness analysis: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except SafetyError as e:
        logger.error(f"Error during sleepiness analysis: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error during analysis: {e.message}")
    except Exception as e:
        logger.exception(f"Unexpected error during sleepiness analysis: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected internal error occurred during analysis.")