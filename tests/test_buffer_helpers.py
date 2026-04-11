"""Tests for buffer pure helpers (decrement, refill, apply_updates) and serialization."""

from datetime import date, datetime, timedelta, timezone

import pytest

from buffer_store import (
    Buffer,
    BufferUpdate,
    apply_buffer_updates,
    decrement_buffer,
    deserialize_buffers,
    refill_buffer,
    serialize_buffers,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_buffer() -> Buffer:
    now = datetime.now(timezone.utc)
    return Buffer(
        id="buf123",
        name="Rent",
        buffer_level=3,
        buffer_capacity=6,
        recurrence_interval_days=30,
        next_due_date=date(2026, 5, 1),
        alert_threshold=1,
        status="active",
        created_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# decrement_buffer tests
# ---------------------------------------------------------------------------

class TestDecrementBuffer:
    def test_reduces_level_by_one(self, sample_buffer: Buffer) -> None:
        result = decrement_buffer(sample_buffer)
        assert result.buffer_level == sample_buffer.buffer_level - 1

    def test_advances_next_due_date(self, sample_buffer: Buffer) -> None:
        result = decrement_buffer(sample_buffer)
        expected = sample_buffer.next_due_date + timedelta(
            days=sample_buffer.recurrence_interval_days
        )
        assert result.next_due_date == expected

    def test_raises_at_level_zero(self) -> None:
        now = datetime.now(timezone.utc)
        empty = Buffer(
            id="empty", name="Empty", buffer_level=0, buffer_capacity=3,
            recurrence_interval_days=7, next_due_date=date(2026, 5, 1),
            alert_threshold=0, status="active",
            created_at=now, updated_at=now,
        )
        with pytest.raises(ValueError, match="buffer_level is already 0"):
            decrement_buffer(empty)

    def test_does_not_mutate_original(self, sample_buffer: Buffer) -> None:
        original_level = sample_buffer.buffer_level
        original_date = sample_buffer.next_due_date
        decrement_buffer(sample_buffer)
        assert sample_buffer.buffer_level == original_level
        assert sample_buffer.next_due_date == original_date

    def test_updates_updated_at(self, sample_buffer: Buffer) -> None:
        result = decrement_buffer(sample_buffer)
        assert result.updated_at >= sample_buffer.updated_at

    def test_preserves_other_fields(self, sample_buffer: Buffer) -> None:
        result = decrement_buffer(sample_buffer)
        assert result.id == sample_buffer.id
        assert result.name == sample_buffer.name
        assert result.buffer_capacity == sample_buffer.buffer_capacity
        assert result.status == sample_buffer.status


# ---------------------------------------------------------------------------
# refill_buffer tests
# ---------------------------------------------------------------------------

class TestRefillBuffer:
    def test_increases_level_by_units(self, sample_buffer: Buffer) -> None:
        result = refill_buffer(sample_buffer, 2)
        assert result.buffer_level == sample_buffer.buffer_level + 2

    def test_caps_at_capacity(self, sample_buffer: Buffer) -> None:
        result = refill_buffer(sample_buffer, 100)
        assert result.buffer_level == sample_buffer.buffer_capacity

    def test_raises_for_zero_units(self, sample_buffer: Buffer) -> None:
        with pytest.raises(ValueError, match="units must be at least 1"):
            refill_buffer(sample_buffer, 0)

    def test_raises_for_negative_units(self, sample_buffer: Buffer) -> None:
        with pytest.raises(ValueError, match="units must be at least 1"):
            refill_buffer(sample_buffer, -1)

    def test_does_not_mutate_original(self, sample_buffer: Buffer) -> None:
        original_level = sample_buffer.buffer_level
        refill_buffer(sample_buffer, 2)
        assert sample_buffer.buffer_level == original_level

    def test_updates_updated_at(self, sample_buffer: Buffer) -> None:
        result = refill_buffer(sample_buffer, 1)
        assert result.updated_at >= sample_buffer.updated_at

    def test_refill_to_exact_capacity(self) -> None:
        now = datetime.now(timezone.utc)
        buf = Buffer(
            id="x", name="Near full", buffer_level=4, buffer_capacity=5,
            recurrence_interval_days=7, next_due_date=date(2026, 5, 1),
            alert_threshold=1, status="active",
            created_at=now, updated_at=now,
        )
        result = refill_buffer(buf, 1)
        assert result.buffer_level == 5


# ---------------------------------------------------------------------------
# apply_buffer_updates tests
# ---------------------------------------------------------------------------

class TestApplyBufferUpdates:
    def test_updates_name(self, sample_buffer: Buffer) -> None:
        updated = apply_buffer_updates(
            sample_buffer, BufferUpdate(name="New name")
        )
        assert updated.name == "New name"
        assert updated.id == sample_buffer.id

    def test_updates_status(self, sample_buffer: Buffer) -> None:
        updated = apply_buffer_updates(
            sample_buffer, BufferUpdate(status="paused")
        )
        assert updated.status == "paused"

    def test_preserves_unchanged_fields(self, sample_buffer: Buffer) -> None:
        updated = apply_buffer_updates(
            sample_buffer, BufferUpdate(name="Changed")
        )
        assert updated.buffer_level == sample_buffer.buffer_level
        assert updated.buffer_capacity == sample_buffer.buffer_capacity
        assert updated.next_due_date == sample_buffer.next_due_date

    def test_does_not_mutate_original(self, sample_buffer: Buffer) -> None:
        apply_buffer_updates(sample_buffer, BufferUpdate(name="New"))
        assert sample_buffer.name == "Rent"

    def test_bumps_updated_at(self, sample_buffer: Buffer) -> None:
        updated = apply_buffer_updates(
            sample_buffer, BufferUpdate(name="New")
        )
        assert updated.updated_at >= sample_buffer.updated_at

    def test_no_changes_returns_same_buffer(self, sample_buffer: Buffer) -> None:
        result = apply_buffer_updates(sample_buffer, BufferUpdate())
        assert result is sample_buffer

    def test_rejects_capacity_below_current_level(
        self, sample_buffer: Buffer
    ) -> None:
        with pytest.raises(Exception, match="buffer_level.*cannot exceed"):
            apply_buffer_updates(
                sample_buffer, BufferUpdate(buffer_capacity=1)
            )


# ---------------------------------------------------------------------------
# Serialization tests
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_round_trip(self, sample_buffer: Buffer) -> None:
        buffers = {sample_buffer.id: sample_buffer}
        raw = serialize_buffers(buffers)
        restored = deserialize_buffers(raw)
        assert sample_buffer.id in restored
        assert restored[sample_buffer.id].name == sample_buffer.name
        assert restored[sample_buffer.id].next_due_date == sample_buffer.next_due_date

    def test_deserialize_rejects_missing_buffers_key(self) -> None:
        with pytest.raises(ValueError, match="top-level 'buffers' key"):
            deserialize_buffers('{"items": []}')

    def test_deserialize_empty_list(self) -> None:
        result = deserialize_buffers('{"buffers": []}')
        assert result == {}
