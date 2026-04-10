"""Tests for cognitive state persistence."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cognitive_state_writer import (
    MAX_HISTORY_ENTRIES,
    CognitiveStateFile,
    CognitiveStateSnapshot,
    append_to_history,
    build_snapshot,
    deserialize_state_file,
    read_cognitive_state,
    serialize_state_file,
    write_cognitive_state,
)


# ---------------------------------------------------------------------------
# Pure function tests
# ---------------------------------------------------------------------------


class TestBuildSnapshot:
    def test_creates_snapshot_with_all_fields(self) -> None:
        now = datetime.now(timezone.utc)
        snap = build_snapshot("focus", "baseline", False, now)
        assert snap.state == "focus"
        assert snap.previous_state == "baseline"
        assert snap.is_transition_blocked is False
        assert snap.detected_at == now

    def test_transition_blocked_flag(self) -> None:
        now = datetime.now(timezone.utc)
        snap = build_snapshot("hyperfocus", "focus", True, now)
        assert snap.is_transition_blocked is True


class TestAppendToHistory:
    def test_appends_to_empty(self) -> None:
        snap = build_snapshot(
            "focus", "baseline", False, datetime.now(timezone.utc)
        )
        result = append_to_history([], snap)
        assert len(result) == 1
        assert result[0] == snap

    def test_preserves_existing(self) -> None:
        existing = build_snapshot(
            "baseline", "baseline", False, datetime.now(timezone.utc)
        )
        new = build_snapshot(
            "focus", "baseline", False, datetime.now(timezone.utc)
        )
        result = append_to_history([existing], new)
        assert len(result) == 2
        assert result[0] == existing
        assert result[1] == new

    def test_trims_to_max(self) -> None:
        now = datetime.now(timezone.utc)
        history = [
            build_snapshot("baseline", "baseline", False, now)
            for _ in range(MAX_HISTORY_ENTRIES)
        ]
        new = build_snapshot("focus", "baseline", False, now)
        result = append_to_history(history, new)
        assert len(result) == MAX_HISTORY_ENTRIES
        assert result[-1] == new
        assert result[0] == history[1]


class TestSerializeDeserialize:
    def test_roundtrip(self) -> None:
        now = datetime.now(timezone.utc)
        snap = build_snapshot("focus", "baseline", False, now)
        state_file = CognitiveStateFile(current=snap, history=[snap])
        raw = serialize_state_file(state_file)
        parsed = deserialize_state_file(raw)
        assert parsed.current.state == "focus"
        assert len(parsed.history) == 1

    def test_json_is_valid(self) -> None:
        snap = build_snapshot(
            "avoidance", "baseline", False, datetime.now(timezone.utc)
        )
        state_file = CognitiveStateFile(current=snap, history=[])
        raw = serialize_state_file(state_file)
        data = json.loads(raw)
        assert "current" in data
        assert "history" in data
        assert data["current"]["state"] == "avoidance"


# ---------------------------------------------------------------------------
# File I/O tests
# ---------------------------------------------------------------------------


class TestWriteCognitiveState:
    def test_creates_file(self, tmp_path: Path) -> None:
        file_path = tmp_path / "data" / "cognitive_state.json"
        result = write_cognitive_state(file_path, "focus", "baseline", False)
        assert file_path.exists()
        assert result.current.state == "focus"
        assert result.current.previous_state == "baseline"

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        file_path = tmp_path / "nested" / "dir" / "state.json"
        write_cognitive_state(file_path, "focus", "baseline", False)
        assert file_path.exists()

    def test_accumulates_history(self, tmp_path: Path) -> None:
        file_path = tmp_path / "state.json"
        write_cognitive_state(file_path, "baseline", "baseline", False)
        write_cognitive_state(file_path, "focus", "baseline", False)
        result = write_cognitive_state(file_path, "hyperfocus", "focus", False)
        assert len(result.history) == 3
        assert result.history[0].state == "baseline"
        assert result.history[1].state == "focus"
        assert result.history[2].state == "hyperfocus"
        assert result.current.state == "hyperfocus"

    def test_trims_history_at_max(self, tmp_path: Path) -> None:
        file_path = tmp_path / "state.json"
        for i in range(MAX_HISTORY_ENTRIES + 5):
            write_cognitive_state(file_path, "baseline", "baseline", False)
        result = read_cognitive_state(file_path)
        assert result is not None
        assert len(result.history) == MAX_HISTORY_ENTRIES

    def test_handles_corrupt_file(self, tmp_path: Path) -> None:
        file_path = tmp_path / "state.json"
        file_path.write_text("not json", encoding="utf-8")
        result = write_cognitive_state(file_path, "focus", "baseline", False)
        assert result.current.state == "focus"
        assert len(result.history) == 1

    def test_atomic_write_no_leftover_tmp(self, tmp_path: Path) -> None:
        file_path = tmp_path / "state.json"
        write_cognitive_state(file_path, "focus", "baseline", False)
        tmp_file = file_path.with_suffix(".tmp")
        assert not tmp_file.exists()


class TestReadCognitiveState:
    def test_returns_none_when_missing(self, tmp_path: Path) -> None:
        result = read_cognitive_state(tmp_path / "nonexistent.json")
        assert result is None

    def test_reads_written_state(self, tmp_path: Path) -> None:
        file_path = tmp_path / "state.json"
        write_cognitive_state(file_path, "overwhelm", "baseline", False)
        result = read_cognitive_state(file_path)
        assert result is not None
        assert result.current.state == "overwhelm"
