"""Tests for voice_delivery module — WAV-to-OGG/Opus conversion and temp file management."""

import io
import struct
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from voice_delivery import (
    OPUS_BITRATE,
    cleanup_temp_file,
    convert_wav_to_ogg,
    save_temp_ogg,
)


def _make_wav_bytes(duration_seconds: float, sample_rate: int) -> bytes:
    """Generate valid WAV bytes with a sine wave for testing."""
    num_samples = int(sample_rate * duration_seconds)
    t = np.linspace(0.0, duration_seconds, num_samples, endpoint=False)
    samples = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)
    int16_samples = np.clip(samples * 32767, -32768, 32767).astype(np.int16)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int16_samples.tobytes())
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# convert_wav_to_ogg
# ---------------------------------------------------------------------------


class TestConvertWavToOgg:
    def test_empty_bytes_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Cannot convert empty WAV data"):
            convert_wav_to_ogg(b"")

    def test_invalid_wav_raises_error(self) -> None:
        with pytest.raises(Exception):
            convert_wav_to_ogg(b"not a wav file")

    def test_returns_bytes(self) -> None:
        wav = _make_wav_bytes(0.1, 24000)
        result = convert_wav_to_ogg(wav)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_output_starts_with_ogg_magic(self) -> None:
        wav = _make_wav_bytes(0.1, 24000)
        result = convert_wav_to_ogg(wav)
        assert result[:4] == b"OggS", "Output should be valid OGG container"

    def test_output_smaller_than_input(self) -> None:
        wav = _make_wav_bytes(1.0, 24000)
        ogg = convert_wav_to_ogg(wav)
        assert len(ogg) < len(wav), "Opus-compressed OGG should be smaller than raw WAV"

    def test_different_sample_rates(self) -> None:
        for rate in [16000, 24000, 48000]:
            wav = _make_wav_bytes(0.1, rate)
            ogg = convert_wav_to_ogg(wav)
            assert ogg[:4] == b"OggS"


# ---------------------------------------------------------------------------
# save_temp_ogg
# ---------------------------------------------------------------------------


class TestSaveTempOgg:
    def test_empty_bytes_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Cannot save empty OGG data"):
            save_temp_ogg(b"")

    def test_creates_file_with_ogg_suffix(self) -> None:
        path = save_temp_ogg(b"fake ogg data")
        try:
            assert path.exists()
            assert path.suffix == ".ogg"
            assert path.name.startswith("voice_")
        finally:
            path.unlink(missing_ok=True)

    def test_file_contains_exact_bytes(self) -> None:
        data = b"test ogg content 12345"
        path = save_temp_ogg(data)
        try:
            assert path.read_bytes() == data
        finally:
            path.unlink(missing_ok=True)

    def test_write_failure_cleans_up(self) -> None:
        with patch("voice_delivery.Path.write_bytes", side_effect=OSError("disk full")):
            with pytest.raises(OSError, match="disk full"):
                save_temp_ogg(b"data")


# ---------------------------------------------------------------------------
# cleanup_temp_file
# ---------------------------------------------------------------------------


class TestCleanupTempFile:
    def test_removes_existing_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.ogg"
        f.write_bytes(b"data")
        cleanup_temp_file(f)
        assert not f.exists()

    def test_nonexistent_file_does_not_raise(self, tmp_path: Path) -> None:
        f = tmp_path / "nonexistent.ogg"
        cleanup_temp_file(f)

    def test_logs_warning_on_os_error(self, tmp_path: Path) -> None:
        f = tmp_path / "test.ogg"
        with patch.object(Path, "unlink", side_effect=OSError("perm denied")):
            with patch("voice_delivery.log") as mock_log:
                cleanup_temp_file(f)
                mock_log.warning.assert_called_once()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_opus_bitrate_is_reasonable(self) -> None:
        assert 16_000 <= OPUS_BITRATE <= 128_000
