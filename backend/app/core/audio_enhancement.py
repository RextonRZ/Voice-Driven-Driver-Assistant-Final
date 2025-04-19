# backend/core/audio_enhancement.py
import numpy as np
import logging
import warnings

# Import librosa and handle potential errors if not installed
try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    # We need librosa for simple_vad, so NR won't work without it
    logging.error("Librosa library not found. Please install it (`pip install librosa`). VAD and noise reduction depend on it.")

# Import noisereduce; handle error if not installed
try:
    import noisereduce as nr
    NOISEREDUCE_AVAILABLE = True
except ImportError:
    NOISEREDUCE_AVAILABLE = False
    logging.error("noisereduce library not found. Please install it (`pip install noisereduce`). Tunable noise reduction will be skipped.")

# Import scipy.signal and handle potential errors
try:
    from scipy import signal
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logging.error("SciPy library not found. Please install it (`pip install scipy`). Some audio processing features might be limited.")


logger = logging.getLogger(__name__)

# Suppress warnings from libraries
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# --- Helper Function: Basic VAD (Adapted from noise_reduction.py) ---
def simple_vad(audio: np.ndarray, sr: int, frame_length=2048, hop_length=512, energy_thresh_db=-40) -> np.ndarray:
    """Basic energy-based Voice Activity Detection. Requires Librosa."""
    if not LIBROSA_AVAILABLE:
        logger.warning("Librosa not available, cannot perform VAD. Assuming all frames contain noise.")
        n_frames = 1 + max(0, len(audio) - frame_length) // hop_length
        return np.zeros(n_frames, dtype=bool) # Assume all noise for NR

    if len(audio) < frame_length:
        logger.warning("Audio too short for VAD processing.")
        # Decide a default: assume speech? Assume noise? Let's assume noise for NR.
        return np.array([False])

    try:
        rms = librosa.feature.rms(y=audio, frame_length=frame_length, hop_length=hop_length)[0]
        if np.max(rms) < 1e-10:
            return np.zeros(len(rms), dtype=bool) # All silent
        rms_db = librosa.amplitude_to_db(rms, ref=np.max(rms))
        vad_mask = rms_db > energy_thresh_db
        return vad_mask
    except Exception as e:
        logger.error(f"Error during VAD: {e}. Defaulting to no speech detected (all noise).")
        n_frames = 1 + max(0, len(audio) - frame_length) // hop_length
        return np.zeros(n_frames, dtype=bool)

# --- Noise Reduction Method: Tunable Noisereduce (Adapted from noise_reduction.py) ---
def apply_tunable_noise_reduction(
    audio_data: np.ndarray, # Expects float32 numpy array
    sr: int,
    prop_decrease=0.95,
    time_smooth_ms=80,
    freq_smooth_hz=150, # Note: freq_smooth_hz is not used in the original function's nr.reduce_noise call
    n_passes=1
    ) -> np.ndarray:
    """
    Applies noisereduce with tunable parameters directly on a NumPy array.
    Requires noisereduce and librosa.
    """
    if not NOISEREDUCE_AVAILABLE:
         logger.error("Cannot apply tunable noise reduction: 'noisereduce' library not available.")
         return audio_data
    if not LIBROSA_AVAILABLE:
         logger.error("Cannot apply tunable noise reduction: 'librosa' library not available (needed for VAD).")
         return audio_data

    logger.debug(f"Applying tunable noisereduce...")
    logger.debug(f"  Parameters: prop_decrease={prop_decrease}, time_smooth_ms={time_smooth_ms}, passes={n_passes}")

    # Ensure input is float32, as expected by noisereduce and VAD helpers
    if not np.issubdtype(audio_data.dtype, np.floating):
        logger.warning(f"Input audio data for NR is not float ({audio_data.dtype}). Converting to float32. Ensure data was properly normalized.")
        # Attempt conversion assuming it was normalized int previously
        if np.issubdtype(audio_data.dtype, np.integer):
            max_val = np.iinfo(audio_data.dtype).max
            audio_data = audio_data.astype(np.float32) / max_val
        else:
             # Fallback for unexpected types
             audio_data = audio_data.astype(np.float32)


    n_fft = 2048
    hop_length = 512 # Must match VAD hop_length if used for noise estimation
    if len(audio_data) < n_fft:
         logger.warning("Audio too short for tunable Noisereduce processing.")
         return audio_data

    processed_audio = audio_data.copy() # Work on a copy

    try:
        noise_clip = None
        # Estimate noise from likely non-speech parts (using VAD) only for first pass
        if n_passes > 0: # Only estimate if we are actually doing a pass
            logger.debug("  Estimating noise profile for first pass using VAD...")
            # Use VAD with the same hop_length as STFT defaults in noisereduce
            vad_mask_frames = simple_vad(processed_audio, sr, frame_length=n_fft, hop_length=hop_length)
            noise_frame_indices = np.where(~vad_mask_frames)[0]

            if len(noise_frame_indices) > 1:
                noise_segments = []
                for idx in noise_frame_indices:
                    start_sample = idx * hop_length
                    end_sample = start_sample + n_fft
                    # Ensure segment slicing is within bounds
                    segment = processed_audio[start_sample : min(end_sample, len(processed_audio))]
                    if len(segment) > 0:
                         noise_segments.append(segment)

                if noise_segments:
                    noise_clip_concat = np.concatenate(noise_segments)
                    # Check if concatenated noise is long enough for FFT analysis
                    if len(noise_clip_concat) >= n_fft:
                         noise_clip = noise_clip_concat
                         logger.debug(f"  VAD-based noise clip created, length: {len(noise_clip)} samples.")
                    else: logger.warning(f"  Concatenated noise segments too short ({len(noise_clip_concat)} < {n_fft}).")
                else: logger.warning("  No valid noise segments collected from VAD.")
            else: logger.warning("  Not enough noise frames identified by VAD (< 2).")

            # Fallback if noise estimation failed
            if noise_clip is None:
                 logger.warning("  Using start of audio for noise profile fallback.")
                 noise_duration_samples = min(len(processed_audio), int(sr * 0.5)) # Use up to first 0.5 seconds
                 if noise_duration_samples >= n_fft:
                      noise_clip = processed_audio[:noise_duration_samples]
                 else:
                      logger.error("  Fallback noise clip also too short. Cannot perform noise reduction.")
                      return audio_data # Return original if no noise profile possible


        # Apply reduction potentially multiple times
        for i in range(n_passes):
            logger.debug(f"  Noisereduce Pass {i+1}/{n_passes}...")
            processed_audio = nr.reduce_noise(
                y=processed_audio,
                sr=sr,
                y_noise=noise_clip if i == 0 and noise_clip is not None else None, # Use estimated noise only on first pass
                prop_decrease=prop_decrease,
                n_fft=n_fft,
                hop_length=hop_length,
                stationary=False, # Assume non-stationary noise typical in driving
                time_mask_smooth_ms=time_smooth_ms,
                # freq_mask_smooth_hz parameter doesn't exist in standard noisereduce call, was likely a typo in original script.
                # If frequency smoothing is desired, explore nr parameters or other libraries.
            )
            # For subsequent passes, noisereduce uses the previous output's noise profile
            noise_clip = None # Don't provide explicit noise after first pass

        logger.debug("Tunable noisereduce processing applied.")
        return processed_audio

    except Exception as e:
        logger.error(f"Error during tunable noisereduce: {e}", exc_info=True)
        return audio_data # Return original audio data on error

# --- Placeholder for Wiener filter if needed later ---
# def apply_wiener_filter(audio_data: np.ndarray, sr: int) -> np.ndarray:
#     if not LIBROSA_AVAILABLE or not SCIPY_AVAILABLE:
#         logger.error("Cannot apply Wiener filter: librosa or scipy not available.")
#         return audio_data
#     # ... (Implement Wiener filter logic adapted for numpy array input) ...
#     logger.debug("Applying Wiener filter...")
#     # ... implementation ...
#     return processed_audio