import logging
from typing import Optional, Tuple, Dict, Any, List
from datetime import datetime
import asyncio
import cv2
import numpy as np
import base64
import mediapipe as mp
from ultralytics import YOLO
import io # For BytesIO if needed

from ..core.clients.twillio_client import TwilioClient # Placeholder client
from ..core.config import Settings
from ..core.exception import SafetyError, ConfigurationError, StateError, CommunicationError, InvalidRequestError
from ..models.internal import CrashReport, SleepinessReport

logger = logging.getLogger(__name__)

# Facial landmarks IDs from the original code
# Adjust if needed based on MediaPipe version/model
FACEMESH_LANDMARK_IDS = {
    "mouth_roi_p1": 187, # Example: Top-left X for mouth ROI
    "mouth_roi_p2": 411, # Example: Top-right X for mouth ROI
    "mouth_roi_p3": 152, # Example: Bottom Y for mouth ROI
    "right_eye_roi_p1": 68,  # Example: Top-left for right eye ROI
    "right_eye_roi_p2": 174, # Example: Bottom-right for right eye ROI
    "left_eye_roi_p1": 399, # Example: Top-left for left eye ROI
    "left_eye_roi_p2": 298, # Example: Bottom-right for left eye ROI
}


class SafetyService:
    """Handles safety features including drowsiness detection."""

    def __init__(self, settings: Settings, twilio_client: Optional[TwilioClient] = None):
        self.settings = settings
        self.twilio_client = twilio_client
        self.drowsiness_enabled = settings.DROWSINESS_DETECTION_ENABLED

        if self.drowsiness_enabled:
            logger.info("Initializing Drowsiness Detection models...")
            try:
                # Initialize MediaPipe Face Mesh
                self.face_mesh = mp.solutions.face_mesh.FaceMesh(
                    static_image_mode=True, # Process images independently
                    max_num_faces=1, # Assume driver is the only relevant face
                    refine_landmarks=True, # Get more detailed landmarks (eyes, lips)
                    min_detection_confidence=settings.DROWSINESS_MEDIAPIPE_MIN_DET_CONF,
                    min_tracking_confidence=settings.DROWSINESS_MEDIAPIPE_MIN_TRACK_CONF
                )

                # Load YOLO models
                self.yawn_model = YOLO(settings.YAWN_MODEL_PATH)
                self.eye_model = YOLO(settings.EYE_MODEL_PATH)
                # You might want to run a dummy prediction to fully initialize models/GPU here
                # dummy_img = np.zeros((64, 64, 3), dtype=np.uint8)
                # self.yawn_model.predict(dummy_img, verbose=False)
                # self.eye_model.predict(dummy_img, verbose=False)
                logger.info("MediaPipe FaceMesh and YOLO models loaded successfully.")
            except Exception as e:
                logger.error(f"FATAL: Failed to load drowsiness detection models: {e}", exc_info=True)
                self.drowsiness_enabled = False # Disable feature if models fail
                # Optionally raise ConfigurationError to prevent startup?
        else:
             logger.warning("Drowsiness detection is disabled in settings.")

        logger.debug("SafetyService initialized.")

    async def _get_emergency_contacts(self, driver_id: str) -> List[str]:
        """
        Retrieves emergency contacts for a driver. Placeholder.
        Requires integration with a user profile service/database.
        """
        if not driver_id:
            logger.warning("Cannot fetch emergency contacts without driver_id.")
            return []

        source = self.settings.EMERGENCY_CONTACT_SOURCE
        logger.info(f"Fetching emergency contacts for driver '{driver_id}' from source: {source} (Placeholder)...")

        # --- Placeholder Logic ---
        # In a real system, query DB or internal API:
        # e.g., response = await http_client.get(source.format(driver_id=driver_id))
        # contacts = response.json().get('contacts', [])
        await asyncio.sleep(0.1) # Simulate lookup
        # Return dummy data for testing
        if driver_id == "driver123":
            return ["+6588881111", "+6599992222"] # Example phone numbers
        else:
            return ["+6511112222"] # Default dummy contact
        # --- End Placeholder ---

    async def handle_crash_detection(self, report: CrashReport) -> Dict[str, Any]:
        """
        Handles the workflow triggered by a crash detection event.

        Args:
            report: CrashReport object containing event details.

        Returns:
            A dictionary indicating the outcome (e.g., {'status': 'acknowledged', 'notifications_sent': True}).

        Raises:
            SafetyError: If critical steps fail.
        """
        logger.critical(f"CRASH DETECTED: Received crash report for session {report.session_id}, driver {report.driver_id} at {report.location} on {report.timestamp}")

        outcome = {"status": "acknowledged", "notifications_sent": False, "errors": []}

        if not self.settings.CRASH_DETECTION_NOTIFICATION_ENABLED:
            logger.warning("Crash detection notification is disabled in settings. Logging only.")
            return outcome

        if not self.twilio_client or not self.twilio_client.enabled:
             logger.error("Cannot send crash notifications: Twilio client is disabled or not configured.")
             outcome["errors"].append("Notification client disabled.")
             # Don't raise, just report failure in outcome
             return outcome

        if not report.driver_id:
             logger.error("Cannot send crash notifications: driver_id is missing in the report.")
             outcome["errors"].append("Missing driver_id.")
             return outcome # Or maybe notify a general emergency number?

        # 1. Get Emergency Contacts
        contacts = []
        try:
            contacts = await self._get_emergency_contacts(report.driver_id)
            if not contacts:
                logger.error(f"No emergency contacts found for driver {report.driver_id}. Cannot send notifications.")
                outcome["errors"].append("No emergency contacts found.")
                return outcome # Critical failure? Or proceed? Let's stop here for now.
        except Exception as e:
            logger.error(f"Failed to retrieve emergency contacts for driver {report.driver_id}: {e}", exc_info=True)
            outcome["status"] = "failed"
            outcome["errors"].append(f"Contact retrieval failed: {e}")
            raise SafetyError(f"Failed to get emergency contacts: {e}", original_exception=e)


        # 2. Send Notifications (SMS/Call)
        location_str = f"{report.location[0]:.5f},{report.location[1]:.5f}"
        maps_link = f"https://www.google.com/maps?q={location_str}"
        message = (f"Emergency Alert: A potential crash involving driver {report.driver_id} "
                   f"was detected near location {location_str} at {report.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}. "
                   f"Map: {maps_link}")

        notifications_successful = True
        for contact in contacts:
            try:
                logger.info(f"Sending crash alert SMS to {contact}...")
                sms_sent = await self.twilio_client.send_sms(contact, message)
                if not sms_sent:
                     logger.warning(f"Failed to send SMS to {contact} (client returned false).")
                     notifications_successful = False
                     outcome["errors"].append(f"SMS failed for {contact}")
                # Optionally follow up with a call?
                # await self.twilio_client.make_call(contact, "This is an automated emergency alert. A potential crash was detected. Please check the SMS message for details.")
            except CommunicationError as e:
                logger.error(f"Failed to send notification to {contact}: {e}", exc_info=True)
                notifications_successful = False
                outcome["errors"].append(f"Notification failed for {contact}: {e}")
            except Exception as e:
                 logger.error(f"Unexpected error sending notification to {contact}: {e}", exc_info=True)
                 notifications_successful = False
                 outcome["errors"].append(f"Unexpected notification error for {contact}")


        outcome["notifications_sent"] = notifications_successful
        if not notifications_successful:
             # Even if some notifications failed, the event was still handled.
             # Status remains 'acknowledged' unless contact retrieval failed critically.
             logger.error(f"One or more crash notifications failed to send for driver {report.driver_id}.")
        else:
             logger.critical(f"Successfully sent crash notifications for driver {report.driver_id} to contacts: {contacts}")

        return outcome


    async def _run_prediction_async(self, model, roi):
        """Helper to run synchronous YOLO predict in an executor."""
        if roi is None or roi.size == 0:
             return [] # Return empty results for empty ROI
        loop = asyncio.get_running_loop()
        # Pass necessary args to predict. verbose=False reduces console spam.
        results = await loop.run_in_executor(None, model.predict, roi, verbose=False)
        return results

    async def _process_single_frame(self, frame_bgr: np.ndarray, frame_idx: int) -> Dict[str, Any]:
        """Processes a single frame for face landmarks and ROI predictions."""
        frame_results = {"frame_idx": frame_idx, "face_found": False, "left_eye_state": None, "right_eye_state": None, "yawn_state": None}

        try:
            # 1. MediaPipe FaceMesh
            image_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            image_rgb.flags.writeable = False # Performance hint
            mp_results = self.face_mesh.process(image_rgb)
            image_rgb.flags.writeable = True

            if not mp_results.multi_face_landmarks:
                 # logger.debug(f"Frame {frame_idx}: No face landmarks detected.")
                 return frame_results # No face, no analysis needed

            frame_results["face_found"] = True
            landmarks = mp_results.multi_face_landmarks[0].landmark # Get first face
            ih, iw, _ = frame_bgr.shape

            # 2. Extract ROIs (Add error handling for boundary conditions)
            try:
                # --- Mouth ROI --- (Adjust indices based on FACEMESH_LANDMARK_IDS map)
                # Example using rough bounding box around mouth landmarks
                # More robust: Use specific lip landmarks if available (e.g., ids 13, 14, 61, 291, 78, 308 etc.)
                mouth_y_top = int(landmarks[FACEMESH_LANDMARK_IDS["mouth_roi_p1"]].y * ih)
                mouth_y_bottom = int(landmarks[FACEMESH_LANDMARK_IDS["mouth_roi_p3"]].y * ih)
                mouth_x_left = int(landmarks[FACEMESH_LANDMARK_IDS["mouth_roi_p1"]].x * iw)
                mouth_x_right = int(landmarks[FACEMESH_LANDMARK_IDS["mouth_roi_p2"]].x * iw)
                mouth_roi = frame_bgr[max(0, mouth_y_top-10):min(ih, mouth_y_bottom+10), max(0, mouth_x_left-10):min(iw, mouth_x_right+10)] # Add padding

                # --- Left Eye ROI --- (Indices 399, 298 are far apart, likely need adjustment)
                # Use standard eye landmarks: e.g., Left eye: 33, 160, 158, 133, 153, 144
                # Example using a bounding box around key left eye points (e.g., 33, 133)
                leye_p1 = landmarks[33] # Top
                leye_p2 = landmarks[133] # Bottom (approx)
                leye_p3 = landmarks[159] # Left corner
                leye_p4 = landmarks[145] # Right corner (approx)
                lx_coords = [int(p.x * iw) for p in [leye_p1, leye_p2, leye_p3, leye_p4]]
                ly_coords = [int(p.y * ih) for p in [leye_p1, leye_p2, leye_p3, leye_p4]]
                lx1, lx2 = min(lx_coords)-5, max(lx_coords)+5 # Add padding
                ly1, ly2 = min(ly_coords)-5, max(ly_coords)+5
                left_eye_roi = frame_bgr[max(0,ly1):min(ih,ly2), max(0,lx1):min(iw,lx2)]

                # --- Right Eye ROI --- (Indices 68, 174 are far apart)
                # Use standard eye landmarks: e.g., Right eye: 362, 385, 387, 263, 373, 380
                # Example using a bounding box around key right eye points (e.g., 362, 263)
                reye_p1 = landmarks[362] # Top
                reye_p2 = landmarks[263] # Bottom (approx)
                reye_p3 = landmarks[386] # Left corner (approx)
                reye_p4 = landmarks[374] # Right corner
                rx_coords = [int(p.x * iw) for p in [reye_p1, reye_p2, reye_p3, reye_p4]]
                ry_coords = [int(p.y * ih) for p in [reye_p1, reye_p2, reye_p3, reye_p4]]
                rx1, rx2 = min(rx_coords)-5, max(rx_coords)+5 # Add padding
                ry1, ry2 = min(ry_coords)-5, max(ry_coords)+5
                right_eye_roi = frame_bgr[max(0,ry1):min(ih,ry2), max(0,rx1):min(iw,rx2)]

            except (IndexError, AttributeError) as e:
                 logger.warning(f"Frame {frame_idx}: Error accessing landmarks for ROI extraction: {e}")
                 return frame_results # Cannot proceed without ROIs

            # 3. Run YOLO Predictions (Asynchronously)
            yawn_pred_task = self._run_prediction_async(self.yawn_model, mouth_roi)
            left_eye_pred_task = self._run_prediction_async(self.eye_model, left_eye_roi)
            right_eye_pred_task = self._run_prediction_async(self.eye_model, right_eye_roi)

            yawn_results, left_eye_results, right_eye_results = await asyncio.gather(
                yawn_pred_task, left_eye_pred_task, right_eye_pred_task
            )

            # 4. Interpret Predictions
            conf_threshold = self.settings.DROWSINESS_YOLO_CONF_THRESHOLD

            # Yawn state (Class 0: Yawn, Class 1: No Yawn)
            if yawn_results and yawn_results[0].boxes:
                boxes = yawn_results[0].boxes
                if len(boxes) > 0:
                    best_idx = boxes.conf.argmax()
                    if boxes.conf[best_idx] >= conf_threshold:
                        frame_results["yawn_state"] = "Yawn" if int(boxes.cls[best_idx]) == 0 else "No Yawn"

            # Left Eye state (Class 0: Open, Class 1: Close)
            if left_eye_results and left_eye_results[0].boxes:
                 boxes = left_eye_results[0].boxes
                 if len(boxes) > 0:
                    best_idx = boxes.conf.argmax()
                    if boxes.conf[best_idx] >= conf_threshold:
                        frame_results["left_eye_state"] = "Close" if int(boxes.cls[best_idx]) == 1 else "Open"

            # Right Eye state (Class 0: Open, Class 1: Close)
            if right_eye_results and right_eye_results[0].boxes:
                 boxes = right_eye_results[0].boxes
                 if len(boxes) > 0:
                    best_idx = boxes.conf.argmax()
                    if boxes.conf[best_idx] >= conf_threshold:
                        frame_results["right_eye_state"] = "Close" if int(boxes.cls[best_idx]) == 1 else "Open"

        except Exception as e:
            logger.error(f"Error processing frame {frame_idx}: {e}", exc_info=True)
            # Return default results for this frame on error

        # logger.debug(f"Frame {frame_idx} Results: {frame_results}")
        return frame_results


    async def analyze_driver_state(
        self,
        image_frames_base64: List[str],
        batch_duration_sec: Optional[float] = None
        ) -> Optional[SleepinessReport]:
        """
        Analyzes a batch of image frames for signs of drowsiness.

        Args:
            image_frames_base64: List of base64 encoded image frame strings.
            batch_duration_sec: Optional total duration the batch represents.

        Returns:
            A SleepinessReport if drowsiness thresholds are met, otherwise None.
        """
        if not self.drowsiness_enabled:
            logger.debug("Skipping drowsiness analysis as it's disabled.")
            return None
        if not image_frames_base64:
             raise InvalidRequestError("No image frames provided for analysis.")

        num_frames = len(image_frames_base64)
        logger.info(f"Analyzing driver state for a batch of {num_frames} frames.")

        # Estimate time per frame if batch duration isn't provided
        time_per_frame = batch_duration_sec / num_frames if batch_duration_sec and num_frames > 0 else self.settings.DROWSINESS_FRAME_INTERVAL_SEC

        # Decode frames (can be done in parallel too, but might consume more memory)
        decoded_frames = []
        for i, frame_b64 in enumerate(image_frames_base64):
            try:
                img_bytes = base64.b64decode(frame_b64)
                img_array = np.frombuffer(img_bytes, dtype=np.uint8)
                frame_bgr = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                if frame_bgr is None:
                     logger.warning(f"Failed to decode frame {i}. Skipping.")
                     continue
                decoded_frames.append(frame_bgr)
            except (ValueError, TypeError, binascii.Error) as e:
                 logger.warning(f"Error decoding base64 frame {i}: {e}. Skipping.")
            except Exception as e:
                 logger.error(f"Unexpected error decoding frame {i}: {e}", exc_info=True)

        if not decoded_frames:
             logger.warning("No frames could be successfully decoded in the batch.")
             return None

        # Process frames sequentially for state tracking within the batch
        batch_yawn_duration = 0.0
        batch_microsleep_duration = 0.0
        yawn_in_progress = False
        eyes_closed_in_progress = False

        all_frame_results = []
        for i, frame in enumerate(decoded_frames):
            frame_result = await self._process_single_frame(frame, i)
            all_frame_results.append(frame_result)

            # Update batch state based on this frame's result
            # Microsleep: Both eyes must be closed
            if frame_result["left_eye_state"] == "Close" and frame_result["right_eye_state"] == "Close":
                eyes_closed_in_progress = True
                batch_microsleep_duration += time_per_frame
            else:
                eyes_closed_in_progress = False
                # Don't reset duration here, we want total time closed within the batch

            # Yawn
            if frame_result["yawn_state"] == "Yawn":
                yawn_in_progress = True
                batch_yawn_duration += time_per_frame
            else:
                yawn_in_progress = False
                # Don't reset duration here

        logger.info(f"Batch analysis complete. Microsleep duration: {batch_microsleep_duration:.2f}s, Yawn duration: {batch_yawn_duration:.2f}s")

        # Check thresholds
        drowsy_reason = None
        confidence = 0.0 # Simplified confidence for now

        if batch_microsleep_duration >= self.settings.DROWSINESS_MICROSLEEP_THRESHOLD_SEC:
            drowsy_reason = f"Microsleep detected ({batch_microsleep_duration:.2f}s >= {self.settings.DROWSINESS_MICROSLEEP_THRESHOLD_SEC:.2f}s threshold)"
            # Confidence could be higher if duration is much longer than threshold
            confidence = max(0.7, min(0.95, 0.7 + (batch_microsleep_duration - self.settings.DROWSINESS_MICROSLEEP_THRESHOLD_SEC) / 5.0)) # Example scaling
            logger.warning(f"DROWSINESS DETECTED: {drowsy_reason}")

        if batch_yawn_duration >= self.settings.DROWSINESS_YAWN_THRESHOLD_SEC:
            # Prioritize microsleep alert if both detected
            if not drowsy_reason:
                drowsy_reason = f"Prolonged yawn detected ({batch_yawn_duration:.2f}s >= {self.settings.DROWSINESS_YAWN_THRESHOLD_SEC:.2f}s threshold)"
                confidence = max(0.6, min(0.9, 0.6 + (batch_yawn_duration - self.settings.DROWSINESS_YAWN_THRESHOLD_SEC) / 10.0)) # Example scaling
                logger.warning(f"DROWSINESS DETECTED: {drowsy_reason}")
            else:
                 logger.info(f"Prolonged yawn also detected but microsleep alert takes precedence.")


        if drowsy_reason:
            return SleepinessReport(
                confidence=confidence,
                evidence_type=drowsy_reason # Use the reason string as evidence type
            )
        else:
            logger.info("No significant drowsiness indicators found in this batch.")
            return None