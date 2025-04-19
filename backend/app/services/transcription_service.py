import logging
from typing import Tuple, Optional
import base64
import binascii
import io
import os
import numpy as np
# Make sure imports for pydub, noisereduce, speech are present

try:
    from pydub import AudioSegment
    from pydub.exceptions import CouldntDecodeError
    PYDUB_AVAILABLE = True

    # --- FFmpeg path configuration (KEEP AS BEFORE) ---
    ffmpeg_bin_dir = r'C:\Users\hongy\Downloads\ffmpeg-n6.1-latest-win64-gpl-6.1\bin' # Or C:\ffmpeg\bin
    ffmpeg_executable = os.path.join(ffmpeg_bin_dir, 'ffmpeg.exe')
    ffprobe_executable = os.path.join(ffmpeg_bin_dir, 'ffprobe.exe')
    if os.path.exists(ffmpeg_executable):
        AudioSegment.converter = ffmpeg_executable
        logging.info(f"Explicitly setting pydub converter path to: {AudioSegment.converter}")
    else:
        logging.error(f"FFmpeg executable not found at: {ffmpeg_executable}. pydub will likely fail.")
    if os.path.exists(ffprobe_executable):
         AudioSegment.ffprobe = ffprobe_executable
         logging.info(f"Explicitly setting pydub ffprobe path to: {AudioSegment.ffprobe}")
    else:
         logging.error(f"ffprobe executable not found at: {ffprobe_executable}. pydub needs ffprobe.")
    # --- End FFmpeg path configuration ---

except ImportError:
    AudioSegment = None
    CouldntDecodeError = None
    PYDUB_AVAILABLE = False
    logging.error("pydub library not found. Please install it (`pip install pydub`). Audio loading/conversion will fail.")
except Exception as e:
    AudioSegment = None
    CouldntDecodeError = None
    PYDUB_AVAILABLE = False
    logging.error(f"Error occurred during pydub/ffmpeg path configuration: {e}", exc_info=True)

from ..core.audio_enhancement import (
    apply_tunable_noise_reduction,
    NOISEREDUCE_AVAILABLE, # Check availability from the new module
    LIBROSA_AVAILABLE      # Also check if librosa is available, as it's needed by VAD
)

try:
    import noisereduce as nr
except ImportError:
    nr = None
    logging.error("noisereduce library not found. Please install it (`pip install noisereduce`). Noise reduction will be skipped.")

# Now import other things
from google.cloud import speech
from ..core.clients.google_stt import GoogleSttClient
from ..core.config import Settings
from ..core.exception import TranscriptionError, InvalidRequestError

logger = logging.getLogger(__name__)

TARGET_ENCODING = speech.RecognitionConfig.AudioEncoding.LINEAR16
TARGET_MIME_TYPE = "audio/wav"

class TranscriptionService:
    def __init__(self, stt_client: GoogleSttClient, settings: Settings):
        self.stt_client = stt_client
        self.settings = settings
        if not PYDUB_AVAILABLE:
            # Log error or raise if pydub is absolutely essential
            logger.critical("pydub library is not available or failed to configure. TranscriptionService may not function.")
            # raise ImportError("TranscriptionService requires pydub and ffmpeg.")

        # Update noise reduction check based on the new module's flags
        self.noise_reduction_enabled = (
            NOISEREDUCE_AVAILABLE and
            LIBROSA_AVAILABLE and # VAD dependency
            self.settings.NOISE_REDUCTION_METHOD == 'tunable_nr' # Check setting
        )
        if self.settings.NOISE_REDUCTION_METHOD != 'none' and not self.noise_reduction_enabled:
             logger.warning(f"Noise reduction method '{self.settings.NOISE_REDUCTION_METHOD}' requested in settings, but prerequisites (noisereduce/librosa) are missing or method is unsupported. Disabling NR.")
        elif self.noise_reduction_enabled:
             logger.info(f"Noise reduction enabled using method: {self.settings.NOISE_REDUCTION_METHOD}")
        else:
            logger.info("Noise reduction is disabled (either by setting or missing dependencies).")

        logger.debug("TranscriptionService initialized.")

    def _decode_audio(self, audio_data: bytes | str) -> bytes:
        logger.debug("Attempting to decode audio if base64 encoded...")
        if isinstance(audio_data, str):
            try:
                decoded_bytes = base64.b64decode(audio_data)
                logger.debug(f"Successfully decoded base64 audio. Size: {len(decoded_bytes)} bytes.")
                return decoded_bytes
            except (binascii.Error, ValueError) as e:
                logger.error(f"Invalid base64 audio data received: {e}")
                raise InvalidRequestError(f"Invalid base64 encoding for audio data: {e}")
        elif isinstance(audio_data, bytes):
            logger.debug(f"Audio data is already bytes. Size: {len(audio_data)} bytes.")
            return audio_data
        else:
            # ... (error handling) ...
            logger.error(f"Unexpected audio data type received: {type(audio_data)}")
            raise InvalidRequestError("Audio data must be bytes or a base64 encoded string.")


    def _process_and_convert_audio(self, raw_audio_bytes: bytes) -> Tuple[bytes, int]:
        # --- MODIFIED METHOD ---
        if not raw_audio_bytes:
            logger.warning("Cannot process empty audio data.")
            raise InvalidRequestError("Cannot process empty audio data.")
        if not PYDUB_AVAILABLE or AudioSegment is None:
             logger.error("Cannot process audio: pydub is not available.")
             raise InvalidRequestError("Audio processing library (pydub) is not configured correctly.")


        try:
            logger.info("Loading audio using pydub...")
            audio = AudioSegment.from_file(io.BytesIO(raw_audio_bytes))
            logger.info(
                f"pydub loaded audio. Original - Channels: {audio.channels}, Rate: {audio.frame_rate} Hz, Sample Width: {audio.sample_width}, Duration: {len(audio) / 1000.0:.2f}s")

            if audio.channels > 1:
                logger.debug("Converting to mono...")
                audio = audio.set_channels(1)

            sample_rate = audio.frame_rate

            dtype_map = {1: np.int8, 2: np.int16, 4: np.int32}
            expected_dtype = dtype_map.get(audio.sample_width, np.int16)
            logger.debug(f"Extracting audio samples as NumPy array with dtype: {expected_dtype}")
            samples = np.array(audio.get_array_of_samples()).astype(expected_dtype)

            # --- Apply Noise Reduction using the new module ---
            # Convert to float32 for processing
            if np.issubdtype(samples.dtype, np.integer):
                max_val = np.iinfo(samples.dtype).max
                samples_float = samples.astype(np.float32) / max_val
                logger.debug(f"Converted integer samples to float32 for NR, max_val used: {max_val}")
            else:
                samples_float = samples.astype(np.float32)
                logger.debug("Samples already float, ensuring float32 for NR.")

            reduced_samples_float = samples_float # Start with original float samples

            # Apply NR if enabled and method matches
            if self.noise_reduction_enabled and self.settings.NOISE_REDUCTION_METHOD == 'tunable_nr':
                logger.info("Applying tunable noise reduction via audio_enhancement module...")
                try:
                    # Call the function from the new module
                    reduced_samples_float = apply_tunable_noise_reduction(
                        audio_data=samples_float, # Pass float32 data
                        sr=sample_rate,
                        prop_decrease=self.settings.NR_PROP_DECREASE,
                        time_smooth_ms=self.settings.NR_TIME_SMOOTH_MS,
                        n_passes=self.settings.NR_PASSES
                        # Pass other parameters from settings if added later
                    )
                    logger.info("Tunable noise reduction applied successfully.")
                except Exception as e:
                    logger.error(f"Error during tunable noise reduction call: {e}", exc_info=True)
                    # Fallback: keep samples_float unchanged (original float samples)
                    # reduced_samples_float remains samples_float from before the try block
                    logger.warning("Falling back to audio without noise reduction due to error.")
            # Add elif for 'wiener' if implemented later
            # elif self.noise_reduction_enabled and self.settings.NOISE_REDUCTION_METHOD == 'wiener':
            #    reduced_samples_float = apply_wiener_filter(...)

            # --- Convert back to target format (int16 for LINEAR16) ---
            # This part remains largely the same as before
            target_dtype = np.int16
            if np.issubdtype(target_dtype, np.integer):
                max_val_out = np.iinfo(target_dtype).max
                # Clamp values after potential NR amplification
                final_samples = (np.clip(reduced_samples_float * max_val_out, -max_val_out, max_val_out)).astype(target_dtype)
                logger.debug(f"Converted float samples back to target {target_dtype}.")
            else:
                # Should not happen if target is LINEAR16/int16
                final_samples = reduced_samples_float.astype(np.float32)
                logger.debug(f"Keeping reduced samples as {final_samples.dtype} (unexpected target).")

            processed_audio_bytes = final_samples.tobytes()
            logger.info(
                f"Audio processing complete. Final Bytes: {len(processed_audio_bytes)}, Sample Rate: {sample_rate} Hz, Encoding: LINEAR16 (int16)")
            return processed_audio_bytes, sample_rate

        except CouldntDecodeError as e:
            logger.error(f"pydub (ffmpeg) could not decode audio file: {e}", exc_info=True)
            raise InvalidRequestError(
                f"Failed to decode audio file. Ensure it's a supported format and ffmpeg is installed/configured. Error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during audio processing/conversion: {e}", exc_info=True)
            raise InvalidRequestError(f"An unexpected error occurred while processing the audio file: {e}")

    async def process_audio(self, audio_data: bytes | str, language_code_hint: Optional[str] = None) -> Tuple[str, str | None]:
        """
        Processes raw audio data (decoding, noise reduction, conversion)
        and then transcribes it using the STT client.
        """
        logger.info("Starting audio processing and transcription.")
        try:
            decoded_audio_bytes = self._decode_audio(audio_data)
            if not decoded_audio_bytes:
                 logger.warning("Decoded audio is empty.")
                 return "", None

            processed_audio_bytes, detected_sample_rate = self._process_and_convert_audio(decoded_audio_bytes)
            if not processed_audio_bytes or not detected_sample_rate:
                 logger.error("Audio processing failed to return valid data/rate.")
                 raise TranscriptionError("Failed to prepare audio for transcription.")

            logger.debug(f"Passing processed audio to STT Client - Size: {len(processed_audio_bytes)}, Rate: {detected_sample_rate} Hz")
            transcript, detected_language = await self.stt_client.transcribe(
                audio_data=processed_audio_bytes,
                sample_rate_hertz=detected_sample_rate,
                input_encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16, # Should be consistent output from _process_and_convert
                language_code_hint=language_code_hint
            )

            logger.info(f"Transcription complete. Detected Lang: {detected_language}. Transcript: '{transcript[:50]}...'")
            return transcript, detected_language

        except InvalidRequestError as e:
            logger.error(f"Audio processing/decoding failed: {e}")
            raise e
        except TranscriptionError as e:
             logger.error(f"Google STT transcription failed in service: {e}")
             raise e
        except Exception as e:
             logger.error(f"Unexpected error during audio processing/transcription: {e}", exc_info=True)
             raise TranscriptionError(f"An unexpected error occurred during transcription: {e}", original_exception=e)