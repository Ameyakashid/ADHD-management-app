"""Tests for buffer formatting pure helpers."""

from datetime import date, timedelta
from pathlib import Path

import pytest

from buffer_store import BufferStore
from buffer_tools import format_buffer, format_buffer_list


@pytest.fixture()
def storage_path(tmp_path: Path) -> Path:
    return tmp_path / "buffers.json"


@pytest.fixture()
def store(storage_path: Path) -> BufferStore:
    return BufferStore(storage_path)


class TestFormatBuffer:
    def test_basic_format(self, store: BufferStore) -> None:
        buffer = store.create_buffer("Rent", 3, 4, 30, date.today() + timedelta(days=15), 1)
        result = format_buffer(buffer)
        assert buffer.id[:8] in result
        assert "Rent" in result
        assert "3/4" in result
        assert "active" in result
        assert "every 30 days" in result
        assert "Alert threshold: 1" in result

    def test_days_until_due(self, store: BufferStore) -> None:
        future = date.today() + timedelta(days=10)
        buffer = store.create_buffer("Test", 2, 4, 7, future, 1)
        result = format_buffer(buffer)
        assert "10 days" in result

    def test_below_threshold_warning(self, store: BufferStore) -> None:
        buffer = store.create_buffer("Low", 1, 4, 7, date.today(), 2)
        result = format_buffer(buffer)
        assert "Below alert threshold" in result

    def test_at_threshold_warning(self, store: BufferStore) -> None:
        buffer = store.create_buffer("At", 2, 4, 7, date.today(), 2)
        result = format_buffer(buffer)
        assert "Below alert threshold" in result

    def test_above_threshold_no_warning(self, store: BufferStore) -> None:
        buffer = store.create_buffer("Ok", 3, 4, 7, date.today(), 2)
        result = format_buffer(buffer)
        assert "Below alert threshold" not in result


class TestFormatBufferList:
    def test_empty_list(self) -> None:
        assert format_buffer_list([]) == "No buffers found."

    def test_multiple_buffers(self, store: BufferStore) -> None:
        store.create_buffer("Rent", 3, 4, 30, date.today(), 1)
        store.create_buffer("Meds", 2, 3, 7, date.today(), 1)
        result = format_buffer_list(store.list_buffers())
        assert "Rent" in result
        assert "Meds" in result
