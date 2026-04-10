"""Tests for TTS engine wrapper — mocked, no model files required."""

import io
import struct
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from tts_engine import (
    DEFAULT_LANG,
    DEFAULT_SPEED,
    DEFAULT_VOICE,
    MODELS_DIR,
    MODEL_PATH,
    SAMPLE_RATE,
    VOICES_PATH,
    _get_model_paths,
    _load_kokoro,
    samples_to_wav_bytes,
    synthesize_speech,
)


class TestSamplesToWavBytes:
    def test_returns_valid_wav(self) -> None:
        samples = np.zeros(480, dtype=np.float32)
        result = samples_to_wav_bytes(samples, 24000)
        assert result[:4] == b"RIFF"

    def test_wav_has_correct_sample_rate(self) -> None:
        samples = np.zeros(480, dtype=np.float32)
        result = samples_to_wav_bytes(samples, 24000)
        with wave.open(io.BytesIO(result), "rb") as wf:
            assert wf.getframerate() == 24000

    def test_wav_is_mono_16bit(self) -> None:
        samples = np.zeros(480, dtype=np.float32)
        result = samples_to_wav_bytes(samples, 24000)
        with wave.open(io.BytesIO(result), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2

    def test_wav_frame_count_matches_input(self) -> None:
        samples = np.zeros(1000, dtype=np.float32)
        result = samples_to_wav_bytes(samples, 24000)
        with wave.open(io.BytesIO(result), "rb") as wf:
            assert wf.getnframes() == 1000

    def test_clips_samples_to_int16_range(self) -> None:
        samples = np.array([2.0, -2.0], dtype=np.float32)
        result = samples_to_wav_bytes(samples, 24000)
        with wave.open(io.BytesIO(result), "rb") as wf:
            raw = wf.readframes(2)
            val1, val2 = struct.unpack("<hh", raw)
            assert val1 == 32767
            assert val2 == -32768

    def test_silence_produces_zero_samples(self) -> None:
        samples = np.zeros(100, dtype=np.float32)
        result = samples_to_wav_bytes(samples, 24000)
        with wave.open(io.BytesIO(result), "rb") as wf:
            raw = wf.readframes(100)
            values = struct.unpack(f"<{100}h", raw)
            assert all(v == 0 for v in values)


class TestGetModelPaths:
    def test_raises_when_model_missing(self, tmp_path: Path) -> None:
        with patch("tts_engine.MODEL_PATH", tmp_path / "missing.onnx"):
            with pytest.raises(FileNotFoundError, match="TTS model not found"):
                _get_model_paths()

    def test_raises_when_voices_missing(self, tmp_path: Path) -> None:
        model = tmp_path / "model.onnx"
        model.write_bytes(b"fake")
        with patch("tts_engine.MODEL_PATH", model), \
             patch("tts_engine.VOICES_PATH", tmp_path / "missing.bin"):
            with pytest.raises(FileNotFoundError, match="TTS voices file not found"):
                _get_model_paths()

    def test_returns_paths_when_both_exist(self, tmp_path: Path) -> None:
        model = tmp_path / "model.onnx"
        voices = tmp_path / "voices.bin"
        model.write_bytes(b"fake-model")
        voices.write_bytes(b"fake-voices")
        with patch("tts_engine.MODEL_PATH", model), \
             patch("tts_engine.VOICES_PATH", voices):
            mp, vp = _get_model_paths()
            assert mp == model
            assert vp == voices


class TestLoadKokoro:
    def setup_method(self) -> None:
        import tts_engine
        tts_engine._kokoro_instance = None

    def test_caches_instance(self, tmp_path: Path) -> None:
        model = tmp_path / "model.onnx"
        voices = tmp_path / "voices.bin"
        model.write_bytes(b"fake")
        voices.write_bytes(b"fake")
        mock_kokoro_cls = MagicMock()
        mock_instance = MagicMock()
        mock_kokoro_cls.return_value = mock_instance

        with patch("tts_engine.MODEL_PATH", model), \
             patch("tts_engine.VOICES_PATH", voices), \
             patch("tts_engine.Kokoro", mock_kokoro_cls, create=True), \
             patch.dict("sys.modules", {"kokoro_onnx": MagicMock(Kokoro=mock_kokoro_cls)}):
            result1 = _load_kokoro()
            result2 = _load_kokoro()
            assert result1 is result2
            assert mock_kokoro_cls.call_count == 1

    def test_raises_when_model_missing(self) -> None:
        with patch("tts_engine.MODEL_PATH", Path("/nonexistent/model.onnx")):
            with pytest.raises(FileNotFoundError):
                _load_kokoro()


class TestSynthesizeSpeech:
    def setup_method(self) -> None:
        import tts_engine
        tts_engine._kokoro_instance = None

    def test_returns_wav_bytes(self) -> None:
        mock_kokoro = MagicMock()
        fake_samples = np.random.uniform(-1, 1, 24000).astype(np.float32)
        mock_kokoro.create.return_value = (fake_samples, 24000)

        import tts_engine
        tts_engine._kokoro_instance = mock_kokoro

        result = synthesize_speech(
            text="Hello world",
            voice="af_heart",
            speed=1.0,
            lang="en-us",
        )
        assert result[:4] == b"RIFF"
        mock_kokoro.create.assert_called_once_with(
            "Hello world", voice="af_heart", speed=1.0, lang="en-us",
        )

    def test_rejects_empty_text(self) -> None:
        with pytest.raises(ValueError, match="Cannot synthesize empty text"):
            synthesize_speech(text="", voice="af_heart", speed=1.0, lang="en-us")

    def test_rejects_whitespace_only_text(self) -> None:
        with pytest.raises(ValueError, match="Cannot synthesize empty text"):
            synthesize_speech(text="   ", voice="af_heart", speed=1.0, lang="en-us")

    def test_passes_voice_and_speed_to_kokoro(self) -> None:
        mock_kokoro = MagicMock()
        fake_samples = np.zeros(100, dtype=np.float32)
        mock_kokoro.create.return_value = (fake_samples, 24000)

        import tts_engine
        tts_engine._kokoro_instance = mock_kokoro

        synthesize_speech(
            text="test",
            voice="am_adam",
            speed=1.5,
            lang="en-gb",
        )
        mock_kokoro.create.assert_called_once_with(
            "test", voice="am_adam", speed=1.5, lang="en-gb",
        )


class TestConstants:
    def test_default_voice_is_valid_kokoro_name(self) -> None:
        assert DEFAULT_VOICE == "af_heart"

    def test_default_speed_is_normal(self) -> None:
        assert DEFAULT_SPEED == 1.0

    def test_default_lang_is_american_english(self) -> None:
        assert DEFAULT_LANG == "en-us"

    def test_sample_rate_is_24khz(self) -> None:
        assert SAMPLE_RATE == 24000

    def test_models_dir_is_under_nanobot_home(self) -> None:
        assert "models" in str(MODELS_DIR)
        assert "kokoro" in str(MODELS_DIR)

    def test_model_path_points_to_onnx_file(self) -> None:
        assert MODEL_PATH.name == "kokoro-v1.0.onnx"

    def test_voices_path_points_to_bin_file(self) -> None:
        assert VOICES_PATH.name == "voices-v1.0.bin"
