import logging
import platform
from typing import Tuple, Optional
import base64
import binascii
import io
import os
import numpy as np

from .translation_service import TranslationService
from ..core.clients.openai_client import OpenAiClient

# Make sure imports for pydub, noisereduce, speech are present

try:
    from pydub import AudioSegment
    from pydub.exceptions import CouldntDecodeError
    PYDUB_AVAILABLE = True

    current_os = platform.system()

    # Define the directory containing ffmpeg binaries
    if current_os == "Windows":
        # Define the directory containing FFmpeg binaries for Windows
        ffmpeg_bin_dir = r'C:\Users\hongy\Downloads\ffmpeg-n6.1-latest-win64-gpl-6.1\bin'  
        ffmpeg_executable = os.path.join(ffmpeg_bin_dir, 'ffmpeg.exe')
        ffprobe_executable = os.path.join(ffmpeg_bin_dir, 'ffprobe.exe')
    elif current_os == "Darwin":  # macOS
        # Define the path to FFmpeg for macOS
        ffmpeg_executable = "/opt/homebrew/bin/ffmpeg"  
        ffprobe_executable = "/opt/homebrew/bin/ffprobe"
    else:
        logging.error(f"Unsupported operating system: {current_os}")
        raise OSError(f"Unsupported operating system: {current_os}")


    # Set converter path
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
from ..core.exception import TranscriptionError, InvalidRequestError, ConfigurationError

logger = logging.getLogger(__name__)

TARGET_ENCODING = speech.RecognitionConfig.AudioEncoding.LINEAR16
TARGET_MIME_TYPE = "audio/wav"

class TranscriptionService:
    def __init__(
        self,
        stt_client: GoogleSttClient,
        openai_client: OpenAiClient,
        translation_service: TranslationService, # Add translation_service parameter
        settings: Settings
    ):
        self.stt_client = stt_client
        self.openai_client = openai_client
        self.translation_service = translation_service # Store the service
        self.settings = settings
        # ... (pydub check) ...
        if not PYDUB_AVAILABLE: logger.critical("pydub library is not available or failed to configure.")

        # ... (NR check remains the same) ...
        self.noise_reduction_enabled = (NOISEREDUCE_AVAILABLE and LIBROSA_AVAILABLE and self.settings.NOISE_REDUCTION_METHOD == 'tunable_nr')
        if self.settings.NOISE_REDUCTION_METHOD != 'none' and not self.noise_reduction_enabled: logger.warning(f"Noise reduction method '{self.settings.NOISE_REDUCTION_METHOD}' requested, but prerequisites missing/unsupported. Disabling NR.")
        elif self.noise_reduction_enabled: logger.info(f"Noise reduction enabled using method: {self.settings.NOISE_REDUCTION_METHOD}")
        else: logger.info("Noise reduction is disabled.")

        self.openai_fallback_possible = self.openai_client and self.openai_client.enabled
        if self.openai_fallback_possible: logger.info("OpenAI Whisper fallback is configured and enabled.")
        else: logger.info("OpenAI Whisper fallback is disabled.")

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

    def _process_and_convert_audio(self, raw_audio_bytes: bytes) -> Tuple[Optional[AudioSegment], int]:
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
            # Ensure sample width is 2 for int16 compatibility later
            if audio.sample_width != 2:
                logger.warning(f"Original sample width is {audio.sample_width}. Setting to 2 (16-bit) for processing.")
                audio = audio.set_sample_width(2)

            dtype_map = {1: np.int8, 2: np.int16, 4: np.int32}
            # Always expect int16 now due to set_sample_width(2)
            expected_dtype = np.int16
            logger.debug(f"Extracting audio samples as NumPy array with dtype: {expected_dtype}")
            samples = np.array(audio.get_array_of_samples()).astype(expected_dtype)

            # --- Apply Noise Reduction ---
            if np.issubdtype(samples.dtype, np.integer):
                max_val = np.iinfo(samples.dtype).max
                samples_float = samples.astype(np.float32) / max_val
            else:  # Should be int16, but handle float case just in case
                samples_float = samples.astype(np.float32)

            reduced_samples_float = samples_float  # Start with original float samples

            if self.noise_reduction_enabled and self.settings.NOISE_REDUCTION_METHOD == 'tunable_nr':
                logger.info("Applying tunable noise reduction via audio_enhancement module...")
                try:
                    reduced_samples_float = apply_tunable_noise_reduction(
                        audio_data=samples_float,  # Pass float32 data
                        sr=sample_rate,
                        prop_decrease=self.settings.NR_PROP_DECREASE,
                        time_smooth_ms=self.settings.NR_TIME_SMOOTH_MS,
                        n_passes=self.settings.NR_PASSES
                    )
                    logger.info("Tunable noise reduction applied successfully.")
                except Exception as e:
                    logger.error(f"Error during tunable noise reduction call: {e}", exc_info=True)
                    logger.warning("Falling back to audio without noise reduction due to error.")

            # --- Convert float samples back to int16 NumPy array ---
            target_dtype = np.int16
            max_val_out = np.iinfo(target_dtype).max
            final_samples_int16 = (np.clip(reduced_samples_float * max_val_out, -max_val_out, max_val_out)).astype(
                target_dtype)
            logger.debug(f"Converted processed float samples back to {target_dtype}.")

            # --- Create a *new* AudioSegment from the processed samples ---
            # Ensure parameters match the processed data
            processed_audio_segment = AudioSegment(
                data=final_samples_int16.tobytes(),
                sample_width=2,  # Must be 2 for int16
                frame_rate=sample_rate,
                channels=1  # Mono
            )
            logger.info(
                f"Audio processing complete. Reconstructed AudioSegment - Rate: {sample_rate} Hz, Channels: 1, SampleWidth: 2")

            # **** RETURN the AudioSegment object and sample rate ****
            return processed_audio_segment, sample_rate

        except CouldntDecodeError as e:
            logger.error(f"pydub (ffmpeg) could not decode audio file: {e}", exc_info=True)
            raise InvalidRequestError(
                f"Failed to decode audio file. Ensure it's a supported format and ffmpeg is installed/configured. Error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during audio processing/conversion: {e}", exc_info=True)
            raise InvalidRequestError(f"An unexpected error occurred while processing the audio file: {e}")

    async def process_audio(self, audio_data: bytes | str, language_code_hint: Optional[str] = None) -> Tuple[str, Optional[str]]:
        """
        Processes raw audio data and transcribes it using Google STT,
        with a fallback to OpenAI Whisper and subsequent language detection if needed.
        """
        logger.info("Starting audio processing and transcription pipeline.")
        transcript = ""
        detected_language_bcp47 = None # Final language to return
        processed_audio_segment: Optional[AudioSegment] = None
        detected_sample_rate = None

        try:
            # 1. Decode and Process Audio -> Get AudioSegment
            decoded_audio_bytes = self._decode_audio(audio_data)
            if not decoded_audio_bytes: return "", None
            processed_audio_segment, detected_sample_rate = self._process_and_convert_audio(decoded_audio_bytes)
            if not processed_audio_segment or not detected_sample_rate: raise TranscriptionError("Failed to prepare audio for transcription.")

            # 2. Attempt Google STT
            google_transcript = ""
            google_detected_language = None
            try:
                google_stt_bytes = processed_audio_segment.raw_data
                logger.debug(f"Attempting Google STT - Size: {len(google_stt_bytes)}, Rate: {detected_sample_rate} Hz")
                google_transcript, google_detected_language = await self.stt_client.transcribe(
                    audio_data=google_stt_bytes,
                    sample_rate_hertz=detected_sample_rate,
                    input_encoding=TARGET_ENCODING,
                    language_code_hint=language_code_hint
                )
                logger.info(f"Google STT result - Detected Lang: {google_detected_language}, Transcript: '{google_transcript[:50]}...'")
            except TranscriptionError as google_err:
                logger.error(f"Google STT transcription failed: {google_err}")
            except Exception as google_ex:
                logger.error(f"Unexpected error during Google STT call: {google_ex}", exc_info=True)

            # 3. Determine if Fallback Needed
            # Fallback if Google failed OR Google succeeded but didn't detect language OR Google transcript is empty
            needs_fallback = (google_detected_language is None) or (not google_transcript)

            if needs_fallback:
                logger.warning(f"Google STT failed detection/transcription (Lang: {google_detected_language}, Empty Transcript: {not google_transcript}). Attempting OpenAI Whisper fallback.")

                if self.openai_fallback_possible:
                    openai_transcript = None
                    try:
                        # Export to WAV for OpenAI
                        wav_exporter = processed_audio_segment.export(format="wav")
                        openai_wav_bytes = wav_exporter.read()
                        wav_exporter.close()

                        if not openai_wav_bytes:
                             logger.error("Failed to export processed audio to WAV bytes for OpenAI.")
                        else:
                             dummy_filename = "audio.wav"
                             logger.debug(f"Sending WAV bytes to OpenAI Whisper ({len(openai_wav_bytes)} bytes)")
                             openai_transcript = await self.openai_client.transcribe(
                                 audio_data=openai_wav_bytes,
                                 filename=dummy_filename,
                                 language_code_hint=language_code_hint # Pass original hint
                             )

                             if openai_transcript:
                                 logger.info(f"OpenAI Whisper fallback successful. Transcript: '{openai_transcript[:50]}...'")
                                 transcript = openai_transcript.strip() # Use Whisper transcript

                                 # **** Attempt to determine language of Whisper transcript ****
                                 if language_code_hint:
                                     logger.info(f"Using provided language hint '{language_code_hint}' for fallback transcript.")
                                     detected_language_bcp47 = language_code_hint
                                 else:
                                     logger.info("No language hint provided, attempting detection on fallback transcript...")
                                     detected_language_bcp47 = await self.translation_service.detect_language_of_text(transcript)
                                     if not detected_language_bcp47:
                                         logger.warning("Could not detect language of fallback transcript. Language will remain None.")
                                         # Keep detected_language_bcp47 as None
                                 # **** End language determination ****

                             else:
                                 logger.warning("OpenAI Whisper fallback also returned empty transcript. Falling back to Google's (empty) result.")
                                 transcript = google_transcript.strip() if google_transcript else "" # Use empty google transcript
                                 detected_language_bcp47 = google_detected_language # Will be None

                    except ConfigurationError as conf_err: logger.error(f"OpenAI Client config error during fallback: {conf_err}")
                    except TranscriptionError as openai_err: logger.error(f"OpenAI Whisper fallback API call failed: {openai_err}")
                    except Exception as fallback_err: logger.error(f"Unexpected error during OpenAI fallback: {fallback_err}", exc_info=True)

                    # If any error occurred during fallback, ensure we use Google's (failed) results
                    if detected_language_bcp47 is None and transcript == "": # Check if fallback didn't successfully set results
                        transcript = google_transcript.strip() if google_transcript else ""
                        detected_language_bcp47 = google_detected_language

                else: # Fallback not possible
                    logger.warning("OpenAI fallback skipped: Client not configured or enabled.")
                    transcript = google_transcript.strip() if google_transcript else ""
                    detected_language_bcp47 = google_detected_language

            else: # Google STT was successful and detected language
                transcript = google_transcript.strip() if google_transcript else ""
                detected_language_bcp47 = google_detected_language

            # 4. Return Final Result
            logger.info(f"Final transcription result - Detected Lang: {detected_language_bcp47}, Transcript: '{transcript[:50]}...'")
            return transcript, detected_language_bcp47

        except InvalidRequestError as e:
            logger.error(f"Audio processing/decoding failed: {e}")
            raise e
        except Exception as e:
             logger.error(f"Unexpected error during transcription pipeline setup: {e}", exc_info=True)
             raise TranscriptionError(f"An unexpected error occurred during transcription pipeline setup: {e}", original_exception=e)