"""Tests for Buffer model validation and build_buffer."""

from datetime import date, datetime, timezone

import pytest

from buffer_store import (
    ALL_BUFFER_STATUSES,
    Buffer,
    build_buffer,
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
# Type constant tests
# ---------------------------------------------------------------------------

class TestTypeConstants:
    def test_all_buffer_statuses(self) -> None:
        assert ALL_BUFFER_STATUSES == {"active", "paused", "archived"}


# ---------------------------------------------------------------------------
# Buffer model validation tests
# ---------------------------------------------------------------------------

class TestBufferModel:
    def test_round_trip_json(self, sample_buffer: Buffer) -> None:
        dumped = sample_buffer.model_dump(mode="json")
        restored = Buffer.model_validate(dumped)
        assert restored.id == sample_buffer.id
        assert restored.name == sample_buffer.name
        assert restored.buffer_level == sample_buffer.buffer_level
        assert restored.next_due_date == sample_buffer.next_due_date

    def test_rejects_invalid_status(self) -> None:
        with pytest.raises(Exception):
            Buffer(
                id="x", name="Bad", buffer_level=1, buffer_capacity=3,
                recurrence_interval_days=7, next_due_date=date(2026, 5, 1),
                alert_threshold=0, status="invalid",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

    def test_rejects_negative_buffer_level(self) -> None:
        with pytest.raises(Exception):
            Buffer(
                id="x", name="Bad", buffer_level=-1, buffer_capacity=3,
                recurrence_interval_days=7, next_due_date=date(2026, 5, 1),
                alert_threshold=0, status="active",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

    def test_rejects_zero_buffer_capacity(self) -> None:
        with pytest.raises(Exception):
            Buffer(
                id="x", name="Bad", buffer_level=0, buffer_capacity=0,
                recurrence_interval_days=7, next_due_date=date(2026, 5, 1),
                alert_threshold=0, status="active",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

    def test_rejects_level_exceeding_capacity(self) -> None:
        with pytest.raises(Exception, match="buffer_level.*cannot exceed.*buffer_capacity"):
            Buffer(
                id="x", name="Bad", buffer_level=5, buffer_capacity=3,
                recurrence_interval_days=7, next_due_date=date(2026, 5, 1),
                alert_threshold=0, status="active",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

    def test_rejects_zero_recurrence_interval(self) -> None:
        with pytest.raises(Exception):
            Buffer(
                id="x", name="Bad", buffer_level=1, buffer_capacity=3,
                recurrence_interval_days=0, next_due_date=date(2026, 5, 1),
                alert_threshold=0, status="active",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

    def test_rejects_negative_alert_threshold(self) -> None:
        with pytest.raises(Exception):
            Buffer(
                id="x", name="Bad", buffer_level=1, buffer_capacity=3,
                recurrence_interval_days=7, next_due_date=date(2026, 5, 1),
                alert_threshold=-1, status="active",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

    def test_rejects_alert_threshold_exceeding_capacity(self) -> None:
        with pytest.raises(Exception, match="alert_threshold.*cannot exceed.*buffer_capacity"):
            Buffer(
                id="x", name="Bad", buffer_level=1, buffer_capacity=3,
                recurrence_interval_days=7, next_due_date=date(2026, 5, 1),
                alert_threshold=4, status="active",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

    def test_datetime_survives_json_round_trip(self, sample_buffer: Buffer) -> None:
        dumped = sample_buffer.model_dump(mode="json")
        restored = Buffer.model_validate(dumped)
        assert restored.created_at == sample_buffer.created_at

    def test_date_survives_json_round_trip(self, sample_buffer: Buffer) -> None:
        dumped = sample_buffer.model_dump(mode="json")
        restored = Buffer.model_validate(dumped)
        assert restored.next_due_date == sample_buffer.next_due_date

    def test_level_at_capacity_is_valid(self) -> None:
        buf = Buffer(
            id="x", name="Full", buffer_level=3, buffer_capacity=3,
            recurrence_interval_days=7, next_due_date=date(2026, 5, 1),
            alert_threshold=1, status="active",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        assert buf.buffer_level == buf.buffer_capacity

    def test_zero_level_is_valid(self) -> None:
        buf = Buffer(
            id="x", name="Empty", buffer_level=0, buffer_capacity=3,
            recurrence_interval_days=7, next_due_date=date(2026, 5, 1),
            alert_threshold=0, status="active",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        assert buf.buffer_level == 0


# ---------------------------------------------------------------------------
# build_buffer tests
# ---------------------------------------------------------------------------

class TestBuildBuffer:
    def test_creates_buffer_with_active_status(self) -> None:
        buf = build_buffer("Rent", 3, 6, 30, date(2026, 5, 1), 1)
        assert buf.status == "active"
        assert buf.name == "Rent"
        assert buf.buffer_level == 3
        assert buf.buffer_capacity == 6

    def test_generates_unique_ids(self) -> None:
        buf_a = build_buffer("A", 1, 3, 7, date(2026, 5, 1), 0)
        buf_b = build_buffer("B", 1, 3, 7, date(2026, 5, 1), 0)
        assert buf_a.id != buf_b.id

    def test_sets_utc_timestamps(self) -> None:
        buf = build_buffer("T", 1, 3, 7, date(2026, 5, 1), 0)
        assert buf.created_at.tzinfo is not None
        assert buf.updated_at.tzinfo is not None

    def test_preserves_next_due_date(self) -> None:
        due = date(2026, 12, 25)
        buf = build_buffer("Gift fund", 2, 4, 30, due, 1)
        assert buf.next_due_date == due
