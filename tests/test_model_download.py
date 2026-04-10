"""Tests for TTS model download and platform detection in setup_workspace."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from setup_workspace import (
    KOKORO_MODEL_FILES,
    detect_platform,
    download_file,
    download_tts_models,
)


class TestDetectPlatform:
    def test_returns_windows_on_win32(self) -> None:
        with patch("setup_workspace.sys") as mock_sys:
            mock_sys.platform = "win32"
            assert detect_platform() == "windows"

    def test_returns_darwin_on_macos(self) -> None:
        with patch("setup_workspace.sys") as mock_sys:
            mock_sys.platform = "darwin"
            assert detect_platform() == "darwin"

    def test_returns_linux_on_linux(self) -> None:
        with patch("setup_workspace.sys") as mock_sys:
            mock_sys.platform = "linux"
            assert detect_platform() == "linux"

    def test_returns_linux_on_unknown(self) -> None:
        with patch("setup_workspace.sys") as mock_sys:
            mock_sys.platform = "freebsd"
            assert detect_platform() == "linux"


class TestDownloadFile:
    def test_downloads_to_target(self, tmp_path: Path) -> None:
        target = tmp_path / "output.bin"
        fake_content = b"fake model data"

        def fake_urlretrieve(url: str, dest: Path) -> None:
            Path(dest).write_bytes(fake_content)

        with patch("setup_workspace.urllib.request.urlretrieve", side_effect=fake_urlretrieve):
            download_file("https://example.com/model.bin", target)
        assert target.exists()
        assert target.read_bytes() == fake_content

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        target = tmp_path / "deep" / "nested" / "model.bin"

        def fake_urlretrieve(url: str, dest: Path) -> None:
            Path(dest).write_bytes(b"data")

        with patch("setup_workspace.urllib.request.urlretrieve", side_effect=fake_urlretrieve):
            download_file("https://example.com/model.bin", target)
        assert target.exists()

    def test_cleans_up_temp_file_on_failure(self, tmp_path: Path) -> None:
        target = tmp_path / "model.bin"

        def failing_urlretrieve(url: str, dest: Path) -> None:
            Path(dest).write_bytes(b"partial")
            raise ConnectionError("Download failed")

        with patch("setup_workspace.urllib.request.urlretrieve", side_effect=failing_urlretrieve):
            with pytest.raises(ConnectionError, match="Download failed"):
                download_file("https://example.com/model.bin", target)
        assert not target.exists()
        # Temp file should also be cleaned up
        remaining = list(tmp_path.iterdir())
        assert len(remaining) == 0


class TestDownloadTtsModels:
    def test_downloads_all_model_files(self, tmp_path: Path) -> None:
        models_dir = tmp_path / "models"

        call_log: list[str] = []

        def fake_download(url: str, target: Path) -> None:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"fake")
            call_log.append(target.name)

        with patch("setup_workspace.download_file", side_effect=fake_download):
            result = download_tts_models(models_dir)
        assert set(result) == set(KOKORO_MODEL_FILES.keys())

    def test_skips_existing_files(self, tmp_path: Path) -> None:
        models_dir = tmp_path / "models"
        models_dir.mkdir(parents=True)
        for filename in KOKORO_MODEL_FILES:
            (models_dir / filename).write_bytes(b"existing")

        with patch("setup_workspace.download_file") as mock_dl:
            result = download_tts_models(models_dir)
        assert result == []
        mock_dl.assert_not_called()

    def test_downloads_only_missing_files(self, tmp_path: Path) -> None:
        models_dir = tmp_path / "models"
        models_dir.mkdir(parents=True)
        first_file = list(KOKORO_MODEL_FILES.keys())[0]
        (models_dir / first_file).write_bytes(b"existing")

        downloaded_targets: list[str] = []

        def fake_download(url: str, target: Path) -> None:
            target.write_bytes(b"new")
            downloaded_targets.append(target.name)

        with patch("setup_workspace.download_file", side_effect=fake_download):
            result = download_tts_models(models_dir)
        assert first_file not in result
        assert len(result) == len(KOKORO_MODEL_FILES) - 1

    def test_creates_models_directory(self, tmp_path: Path) -> None:
        models_dir = tmp_path / "nonexistent" / "models"

        with patch("setup_workspace.download_file", side_effect=lambda u, t: t.write_bytes(b"f")):
            download_tts_models(models_dir)
        assert models_dir.exists()


class TestKokoroModelConstants:
    def test_model_files_has_onnx_and_voices(self) -> None:
        assert "kokoro-v1.0.onnx" in KOKORO_MODEL_FILES
        assert "voices-v1.0.bin" in KOKORO_MODEL_FILES

    def test_urls_point_to_github_releases(self) -> None:
        for url in KOKORO_MODEL_FILES.values():
            assert "github.com" in url
            assert "kokoro-onnx" in url
            assert "releases" in url
