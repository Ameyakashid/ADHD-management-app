"""WAV-to-OGG/Opus audio conversion for Telegram voice messages.

Telegram requires OGG/Opus format for voice messages (inline waveform).
Uses PyAV (pip-installable FFmpeg bindings) for conversion since OGG/Opus
encoding requires native code — not writable in pure Python.
"""

import io
import logging
import os
import tempfile
from pathlib import Path

import av

log = logging.getLogger(__name__)

OPUS_BITRATE = 32_000


def convert_wav_to_ogg(wav_bytes: bytes) -> bytes:
    """Convert WAV audio bytes to OGG/Opus bytes for Telegram voice messages.

    Args:
        wav_bytes: Raw WAV file bytes (mono, 16-bit PCM).

    Returns:
        OGG/Opus encoded audio bytes.

    Raises:
        ValueError: If wav_bytes is empty.
    """
    if not wav_bytes:
        raise ValueError("Cannot convert empty WAV data")

    input_buffer = io.BytesIO(wav_bytes)
    output_buffer = io.BytesIO()

    with av.open(input_buffer, mode="r") as input_container:
        input_stream = input_container.streams.audio[0]

        with av.open(output_buffer, mode="w", format="ogg") as output_container:
            output_stream = output_container.add_stream("libopus")
            output_stream.bit_rate = OPUS_BITRATE

            for frame in input_container.decode(input_stream):
                for packet in output_stream.encode(frame):
                    output_container.mux(packet)

            for packet in output_stream.encode(None):
                output_container.mux(packet)

    return output_buffer.getvalue()


def save_temp_ogg(ogg_bytes: bytes) -> Path:
    """Save OGG bytes to a temporary file and return its path.

    Caller is responsible for cleanup via cleanup_temp_file().

    Args:
        ogg_bytes: OGG/Opus encoded audio bytes.

    Returns:
        Path to the temporary .ogg file.

    Raises:
        ValueError: If ogg_bytes is empty.
    """
    if not ogg_bytes:
        raise ValueError("Cannot save empty OGG data")

    fd, path_str = tempfile.mkstemp(suffix=".ogg", prefix="voice_")
    os.close(fd)
    path = Path(path_str)
    try:
        path.write_bytes(ogg_bytes)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path


def cleanup_temp_file(path: Path) -> None:
    """Remove a temporary file, logging but not raising on failure."""
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        log.warning("Failed to clean up temp file %s: %s", path, exc)
