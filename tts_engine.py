"""Kokoro TTS engine wrapper using kokoro-onnx.

Provides synthesize_speech() which takes text and returns WAV audio bytes.
Model files must be downloaded first via setup_workspace.py.
"""

import io
import logging
import wave
from pathlib import Path
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)

NANOBOT_HOME = Path.home() / ".nanobot"
MODELS_DIR = NANOBOT_HOME / "models" / "kokoro"
MODEL_PATH = MODELS_DIR / "kokoro-v1.0.onnx"
VOICES_PATH = MODELS_DIR / "voices-v1.0.bin"

DEFAULT_VOICE = "af_heart"
DEFAULT_SPEED = 1.0
DEFAULT_LANG = "en-us"
SAMPLE_RATE = 24000

_kokoro_instance: Optional[object] = None


def _get_model_paths() -> tuple[Path, Path]:
    """Return validated paths to model and voices files."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"TTS model not found at {MODEL_PATH}. "
            f"Run 'python setup_workspace.py' to download it."
        )
    if not VOICES_PATH.exists():
        raise FileNotFoundError(
            f"TTS voices file not found at {VOICES_PATH}. "
            f"Run 'python setup_workspace.py' to download it."
        )
    return MODEL_PATH, VOICES_PATH


def _load_kokoro() -> object:
    """Lazy-load the Kokoro TTS instance. Cached after first call."""
    global _kokoro_instance
    if _kokoro_instance is not None:
        return _kokoro_instance

    model_path, voices_path = _get_model_paths()

    from kokoro_onnx import Kokoro

    log.info("Loading Kokoro TTS model from %s", model_path)
    _kokoro_instance = Kokoro(str(model_path), str(voices_path))
    log.info("Kokoro TTS model loaded")
    return _kokoro_instance


def samples_to_wav_bytes(samples: np.ndarray, sample_rate: int) -> bytes:
    """Convert float32 audio samples to WAV bytes using stdlib wave module."""
    int16_samples = np.clip(samples * 32767, -32768, 32767).astype(np.int16)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int16_samples.tobytes())
    return buffer.getvalue()


def synthesize_speech(
    text: str,
    voice: str,
    speed: float,
    lang: str,
) -> bytes:
    """Synthesize text to WAV audio bytes using Kokoro TTS.

    Args:
        text: The text to synthesize.
        voice: Kokoro voice name (e.g. 'af_heart', 'am_adam').
        speed: Playback speed multiplier (1.0 = normal).
        lang: Language code (e.g. 'en-us', 'en-gb').

    Returns:
        WAV audio bytes (mono, 16-bit PCM, 24kHz).

    Raises:
        FileNotFoundError: If model files haven't been downloaded.
        ValueError: If text is empty.
    """
    if not text.strip():
        raise ValueError("Cannot synthesize empty text")

    kokoro = _load_kokoro()
    samples, sample_rate = kokoro.create(  # type: ignore[union-attr]
        text, voice=voice, speed=speed, lang=lang,
    )
    return samples_to_wav_bytes(samples, sample_rate)
