"""Tests for dashboard static file serving and resolve_static_file."""

import threading
import urllib.request
from http.server import HTTPServer
from pathlib import Path

import pytest

from dashboard_api import (
    make_handler_class,
    resolve_static_file,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def static_dir(tmp_path: Path) -> Path:
    d = tmp_path / "static"
    d.mkdir()
    (d / "index.html").write_text("<html><body>test</body></html>")
    (d / "style.css").write_text("body { color: red; }")
    (d / "app.js").write_text("var x = 1;")
    return d


@pytest.fixture()
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    d.mkdir()
    return d


@pytest.fixture()
def server_url(data_dir: Path, static_dir: Path) -> str:
    handler_class = make_handler_class(data_dir, static_dir)
    server = HTTPServer(("127.0.0.1", 0), handler_class)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


# ---------------------------------------------------------------------------
# Pure function tests: resolve_static_file
# ---------------------------------------------------------------------------


class TestResolveStaticFile:
    def test_root_serves_index_html(self, static_dir: Path) -> None:
        result = resolve_static_file(static_dir, "/")
        assert result is not None
        content, content_type = result
        assert b"<html>" in content
        assert "text/html" in content_type

    def test_serves_css_file(self, static_dir: Path) -> None:
        result = resolve_static_file(static_dir, "/style.css")
        assert result is not None
        content, content_type = result
        assert b"color: red" in content
        assert "text/css" in content_type

    def test_serves_js_file(self, static_dir: Path) -> None:
        result = resolve_static_file(static_dir, "/app.js")
        assert result is not None
        content, content_type = result
        assert b"var x" in content
        assert "javascript" in content_type

    def test_returns_none_for_missing_file(self, static_dir: Path) -> None:
        assert resolve_static_file(static_dir, "/nope.html") is None

    def test_rejects_path_traversal(self, static_dir: Path) -> None:
        assert resolve_static_file(static_dir, "/../secret.txt") is None

    def test_rejects_unknown_extension(self, static_dir: Path) -> None:
        (static_dir / "data.json").write_text("{}")
        assert resolve_static_file(static_dir, "/data.json") is None

    def test_returns_none_for_nonexistent_dir(self, tmp_path: Path) -> None:
        missing = tmp_path / "no_such_dir"
        assert resolve_static_file(missing, "/index.html") is None


# ---------------------------------------------------------------------------
# HTTP integration tests: static serving through the server
# ---------------------------------------------------------------------------


class TestStaticHTTPServing:
    def test_root_returns_html(self, server_url: str) -> None:
        req = urllib.request.Request(f"{server_url}/")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            assert "text/html" in resp.headers["Content-Type"]
            body = resp.read()
            assert b"<html>" in body

    def test_css_returns_stylesheet(self, server_url: str) -> None:
        req = urllib.request.Request(f"{server_url}/style.css")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            assert "text/css" in resp.headers["Content-Type"]

    def test_js_returns_javascript(self, server_url: str) -> None:
        req = urllib.request.Request(f"{server_url}/app.js")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            assert "javascript" in resp.headers["Content-Type"]

    def test_api_takes_priority_over_static(
        self, server_url: str, static_dir: Path
    ) -> None:
        (static_dir / "state").write_text("not an api")
        req = urllib.request.Request(f"{server_url}/state")
        with urllib.request.urlopen(req) as resp:
            assert "application/json" in resp.headers["Content-Type"]

    def test_missing_static_returns_404(self, server_url: str) -> None:
        req = urllib.request.Request(f"{server_url}/missing.html")
        try:
            urllib.request.urlopen(req)
            assert False, "Expected 404"
        except urllib.error.HTTPError as exc:
            assert exc.code == 404

    def test_static_has_cors_headers(self, server_url: str) -> None:
        req = urllib.request.Request(f"{server_url}/style.css")
        with urllib.request.urlopen(req) as resp:
            assert resp.headers["Access-Control-Allow-Origin"] == "*"
