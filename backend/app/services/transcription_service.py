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
        # Add checks for pydub/noisereduce availability
        # self.noise_reduction_enabled = nr is not None
        # ...
        logger.debug("TranscriptionService initialized.")

    def _decode_audio(self, audio_data: bytes | str) -> bytes:
        # ... Implementation from previous version ...
        logger.debug("Decoding audio...")
        if isinstance(audio_data, str):
            try:
                return base64.b64decode(audio_data)
            except (binascii.Error, ValueError) as e:
                raise InvalidRequestError(f"Invalid base64 audio data: {e}")
        elif isinstance(audio_data, bytes):
            return audio_data
        else:
            raise InvalidRequestError("Audio data must be bytes or base64 string.")

    def _apply_noise_reduction(self, audio_data: np.ndarray, sample_rate: int) -> np.ndarray:
        # ... Implementation from previous version ...
        logger.debug("Applying noise reduction (placeholder)...")
        # if self.noise_reduction_enabled:
             # try: return nr.reduce_noise(...)
             # except Exception: return audio_data
        # return audio_data
        return audio_data # Placeholder

    def _process_and_convert_audio(self, raw_audio_bytes: bytes) -> Tuple[bytes, int]:
        # ... Implementation from previous version ...
        # Includes: pydub loading, mono conversion, numpy conversion,
        # calling _apply_noise_reduction, converting back to bytes (LINEAR16)
        logger.info("Processing/converting audio (placeholder)...")
        # Placeholder: Assume input is already correct for simplicity
        # In reality, this needs the full pydub/numpy logic
        if not raw_audio_bytes:
             raise InvalidRequestError("Cannot process empty audio data.")
        # Assume 16kHz, 16-bit mono for placeholder
        sample_rate = 16000
        processed_bytes = raw_audio_bytes # Needs actual processing
        logger.info(f"Audio processing complete. Rate: {sample_rate} Hz, Encoding: LINEAR16")
        return processed_bytes, sample_rate


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