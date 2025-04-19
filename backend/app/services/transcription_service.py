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

    # Define the directory containing ffmpeg binaries
    ffmpeg_bin_dir = r'C:\Users\hongy\Downloads\ffmpeg-n6.1-latest-win64-gpl-6.1\bin' # Or C:\ffmpeg\bin
    # Construct the full path to the ffmpeg.exe file
    ffmpeg_executable = os.path.join(ffmpeg_bin_dir, 'ffmpeg.exe')
    ffprobe_executable = os.path.join(ffmpeg_bin_dir, 'ffprobe.exe')

    # Set converter path
    if os.path.exists(ffmpeg_executable):
        AudioSegment.converter = ffmpeg_executable
        logging.info(f"Explicitly setting pydub converter path to: {AudioSegment.converter}")
    else:
        logging.error(f"FFmpeg executable not found at: {ffmpeg_executable}. pydub will likely fail.")
        # raise FileNotFoundError(f"Required FFmpeg executable not found at: {ffmpeg_executable}")

    # Set ffprobe path
    if os.path.exists(ffprobe_executable):
         AudioSegment.ffprobe = ffprobe_executable
         logging.info(f"Explicitly setting pydub ffprobe path to: {AudioSegment.ffprobe}")
    else:
         logging.error(f"ffprobe executable not found at: {ffprobe_executable}. pydub needs ffprobe to get media info.")
         # raise FileNotFoundError(f"Required ffprobe executable not found at: {ffprobe_executable}")

except ImportError:
    AudioSegment = None
    CouldntDecodeError = None
    logging.error("pydub library not found. Please install it (`pip install pydub`).")
except Exception as e:
    AudioSegment = None
    CouldntDecodeError = None
    logging.error(f"Error occurred during pydub/ffmpeg path configuration: {e}", exc_info=True)
# -------------------------------------

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
        if AudioSegment is None:
            raise ImportError("TranscriptionService requires pydub.")

        self.noise_reduction_enabled = nr is not None
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

    def _apply_noise_reduction(self, audio_data: np.ndarray, sample_rate: int) -> np.ndarray:
        if not self.noise_reduction_enabled:
            logger.debug("Skipping noise reduction as library is not available.")
            return audio_data

        logger.info(f"Applying noise reduction (spectral gating)... Sample rate: {sample_rate} Hz")
        try:
            # Parameters can be tuned:
            # prop_decrease: How much to reduce noise (0.0 to 1.0). Default 1.0
            # n_fft: Size of FFT window. Default 2048
            # hop_length: Hop length for FFT. Default 512
            # For non-stationary noise, tweaking might be needed, or using a different algo.
            reduced_noise_audio = nr.reduce_noise(
                y=audio_data,  # Use 'y' instead of 'audio_clip' for newer versions
                sr=sample_rate,
                stationary=False,  # Experiment with stationary=False for non-stationary noise
                prop_decrease=0.8,  # Try reducing less aggressively initially
                n_fft=2048,
                hop_length=512
            )
            logger.info("Noise reduction applied successfully.")
            return reduced_noise_audio
        except Exception as e:
            # Catch potential errors during noise reduction process
            logger.error(f"Error during noise reduction: {e}", exc_info=True)
            # Fallback: return original audio if reduction fails
            return audio_data

    def _process_and_convert_audio(self, raw_audio_bytes: bytes) -> Tuple[bytes, int]:
        if not raw_audio_bytes:
            logger.warning("Cannot process empty audio data.")
            raise InvalidRequestError("Cannot process empty audio data.")

        try:
            logger.info("Loading audio using pydub...")
            audio = AudioSegment.from_file(io.BytesIO(raw_audio_bytes))
            logger.info(
                f"pydub loaded audio. Original - Channels: {audio.channels}, Rate: {audio.frame_rate} Hz, Sample Width: {audio.sample_width}, Duration: {len(audio) / 1000.0:.2f}s")

            # Ensure audio is suitable for STT (Mono, potentially resample if needed - keeping original rate for now)
            if audio.channels > 1:
                logger.debug("Converting to mono...")
                audio = audio.set_channels(1)

            sample_rate = audio.frame_rate

            # --- Convert pydub audio to NumPy array for noise reduction ---
            # Ensure correct dtype based on sample_width (bytes per sample)
            # 1 byte = 8 bit (int8), 2 bytes = 16 bit (int16), 4 bytes = 32 bit (int32/float32)
            dtype_map = {1: np.int8, 2: np.int16, 4: np.int32}  # Simple map
            expected_dtype = dtype_map.get(audio.sample_width, np.int16)  # Default to int16 if unsure
            logger.debug(f"Extracting audio samples as NumPy array with dtype: {expected_dtype}")
            samples = np.array(audio.get_array_of_samples()).astype(expected_dtype)

            # --- Apply Noise Reduction ---
            # noisereduce works best with float data between -1 and 1. Convert if necessary.
            # Check max value to see if normalization is needed
            if np.issubdtype(samples.dtype, np.integer):
                max_val = np.iinfo(samples.dtype).max
                samples_float = samples.astype(np.float32) / max_val
                logger.debug(f"Converted integer samples to float32, max_val used: {max_val}")
            else:
                samples_float = samples.astype(np.float32)  # Assume already float if not integer
                logger.debug("Samples already float, ensuring float32.")

            reduced_samples_float = self._apply_noise_reduction(samples_float, sample_rate)

            # --- Convert back to original integer type for export ---
            if np.issubdtype(expected_dtype, np.integer):
                max_val = np.iinfo(expected_dtype).max
                # Clamp values to avoid clipping/wrap-around errors after potential NR amplification
                reduced_samples_int = (np.clip(reduced_samples_float * max_val, -max_val, max_val)).astype(
                    expected_dtype)
                logger.debug(f"Converted float samples back to {expected_dtype}.")
            else:
                # If original was float, just ensure it's float32
                reduced_samples_int = reduced_samples_float.astype(np.float32)  # Or original float type if known
                logger.debug(f"Keeping reduced samples as {reduced_samples_int.dtype}.")

            # --- Convert NumPy array back to bytes (LINEAR16 format) ---
            # Google STT LINEAR16 expects signed 16-bit PCM.
            # If our original wasn't 16-bit, we need to ensure the output is.
            # Best practice: Standardize output to 16-bit PCM after noise reduction.
            if reduced_samples_int.dtype != np.int16:
                logger.warning(
                    f"Original/Reduced dtype ({reduced_samples_int.dtype}) is not int16. Converting to int16 for LINEAR16 export. This might affect quality if original bit depth was higher.")
                # Re-normalize if converting from different integer types or floats
                if np.issubdtype(reduced_samples_int.dtype, np.integer):
                    max_val_in = np.iinfo(reduced_samples_int.dtype).max
                    normalized_float = reduced_samples_int.astype(np.float32) / max_val_in
                else:  # Already float
                    normalized_float = reduced_samples_int

                max_val_out = np.iinfo(np.int16).max
                final_samples = (np.clip(normalized_float * max_val_out, -max_val_out, max_val_out)).astype(np.int16)
                logger.debug("Converted final samples to int16.")

            else:
                final_samples = reduced_samples_int  # Already int16

            processed_audio_bytes = final_samples.tobytes()
            processed_audio_base64 = base64.b64encode(processed_audio_bytes).decode('utf-8')
            logger.info(
                f"Audio processing complete (including noise reduction). Final Bytes: {len(processed_audio_bytes)}, Sample Rate: {sample_rate} Hz, Encoding: LINEAR16 (int16)")
            return processed_audio_bytes, sample_rate

        except CouldntDecodeError as e:
            logger.error(f"pydub (ffmpeg) could not decode audio file: {e}", exc_info=True)
            raise InvalidRequestError(
                f"Failed to decode audio file. Ensure it's a supported format and ffmpeg is installed. Error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during audio processing/noise reduction: {e}", exc_info=True)
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