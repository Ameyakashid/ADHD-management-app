"""Tests for BufferStore CRUD operations and persistence."""

from datetime import date, timedelta
from pathlib import Path

import pytest

from buffer_store import BufferStore, BufferUpdate


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def storage_path(tmp_path: Path) -> Path:
    return tmp_path / "buffers.json"


@pytest.fixture()
def store(storage_path: Path) -> BufferStore:
    return BufferStore(storage_path)


# ---------------------------------------------------------------------------
# Create tests
# ---------------------------------------------------------------------------

class TestBufferStoreCreate:
    def test_create_returns_buffer(self, store: BufferStore) -> None:
        buf = store.create_buffer("Rent", 3, 6, 30, date(2026, 5, 1), 1)
        assert buf.name == "Rent"
        assert buf.status == "active"
        assert buf.buffer_level == 3

    def test_create_persists_to_disk(
        self, store: BufferStore, storage_path: Path
    ) -> None:
        store.create_buffer("Rent", 3, 6, 30, date(2026, 5, 1), 1)
        assert storage_path.exists()

    def test_create_multiple_buffers(self, store: BufferStore) -> None:
        store.create_buffer("Rent", 3, 6, 30, date(2026, 5, 1), 1)
        store.create_buffer("Gym", 2, 4, 7, date(2026, 5, 3), 0)
        assert len(store.list_buffers()) == 2

    def test_create_rejects_invalid_level(self, store: BufferStore) -> None:
        with pytest.raises(Exception):
            store.create_buffer("Bad", 10, 3, 7, date(2026, 5, 1), 0)


# ---------------------------------------------------------------------------
# Get tests
# ---------------------------------------------------------------------------

class TestBufferStoreGet:
    def test_get_existing_buffer(self, store: BufferStore) -> None:
        created = store.create_buffer("Find me", 2, 4, 7, date(2026, 5, 1), 0)
        found = store.get_buffer(created.id)
        assert found.name == "Find me"

    def test_get_nonexistent_raises(self, store: BufferStore) -> None:
        with pytest.raises(KeyError, match="Buffer not found"):
            store.get_buffer("nonexistent-id")


# ---------------------------------------------------------------------------
# List tests
# ---------------------------------------------------------------------------

class TestBufferStoreList:
    def test_list_empty_store(self, store: BufferStore) -> None:
        assert store.list_buffers() == []

    def test_list_active_buffers(self, store: BufferStore) -> None:
        store.create_buffer("Active", 2, 4, 7, date(2026, 5, 1), 0)
        buf_b = store.create_buffer("To pause", 1, 3, 14, date(2026, 5, 1), 0)
        store.update_buffer(buf_b.id, BufferUpdate(status="paused"))

        active = store.list_active_buffers()
        all_buffers = store.list_buffers()
        assert len(active) == 1
        assert len(all_buffers) == 2
        assert active[0].name == "Active"


# ---------------------------------------------------------------------------
# Update tests
# ---------------------------------------------------------------------------

class TestBufferStoreUpdate:
    def test_update_changes_fields(self, store: BufferStore) -> None:
        buf = store.create_buffer("Old name", 2, 4, 7, date(2026, 5, 1), 0)
        updated = store.update_buffer(buf.id, BufferUpdate(name="New name"))
        assert updated.name == "New name"
        assert updated.buffer_level == 2

    def test_update_nonexistent_raises(self, store: BufferStore) -> None:
        with pytest.raises(KeyError, match="Buffer not found"):
            store.update_buffer("fake-id", BufferUpdate(name="x"))

    def test_update_bumps_updated_at(self, store: BufferStore) -> None:
        buf = store.create_buffer("Timestamped", 2, 4, 7, date(2026, 5, 1), 0)
        updated = store.update_buffer(buf.id, BufferUpdate(name="Changed"))
        assert updated.updated_at >= buf.updated_at

    def test_update_status_to_archived(self, store: BufferStore) -> None:
        buf = store.create_buffer("Archive me", 2, 4, 7, date(2026, 5, 1), 0)
        updated = store.update_buffer(buf.id, BufferUpdate(status="archived"))
        assert updated.status == "archived"

    def test_update_rejects_capacity_below_level(
        self, store: BufferStore
    ) -> None:
        buf = store.create_buffer("Test", 3, 6, 30, date(2026, 5, 1), 1)
        with pytest.raises(Exception):
            store.update_buffer(buf.id, BufferUpdate(buffer_capacity=2))


# ---------------------------------------------------------------------------
# Decrement tests
# ---------------------------------------------------------------------------

class TestBufferStoreDecrement:
    def test_decrement_reduces_level(self, store: BufferStore) -> None:
        buf = store.create_buffer("Rent", 3, 6, 30, date(2026, 5, 1), 1)
        result = store.decrement(buf.id)
        assert result.buffer_level == 2

    def test_decrement_advances_due_date(self, store: BufferStore) -> None:
        buf = store.create_buffer("Rent", 3, 6, 30, date(2026, 5, 1), 1)
        result = store.decrement(buf.id)
        assert result.next_due_date == date(2026, 5, 31)

    def test_decrement_persists(
        self, store: BufferStore, storage_path: Path
    ) -> None:
        buf = store.create_buffer("Rent", 3, 6, 30, date(2026, 5, 1), 1)
        store.decrement(buf.id)
        fresh = BufferStore(storage_path)
        assert fresh.get_buffer(buf.id).buffer_level == 2

    def test_decrement_at_zero_raises(self, store: BufferStore) -> None:
        buf = store.create_buffer("Empty", 0, 3, 7, date(2026, 5, 1), 0)
        with pytest.raises(ValueError, match="buffer_level is already 0"):
            store.decrement(buf.id)

    def test_decrement_at_zero_does_not_corrupt(
        self, store: BufferStore
    ) -> None:
        buf = store.create_buffer("Empty", 0, 3, 7, date(2026, 5, 1), 0)
        with pytest.raises(ValueError):
            store.decrement(buf.id)
        assert store.get_buffer(buf.id).buffer_level == 0

    def test_decrement_nonexistent_raises(self, store: BufferStore) -> None:
        with pytest.raises(KeyError, match="Buffer not found"):
            store.decrement("fake-id")


# ---------------------------------------------------------------------------
# Refill tests
# ---------------------------------------------------------------------------

class TestBufferStoreRefill:
    def test_refill_increases_level(self, store: BufferStore) -> None:
        buf = store.create_buffer("Rent", 2, 6, 30, date(2026, 5, 1), 1)
        result = store.refill(buf.id, 3)
        assert result.buffer_level == 5

    def test_refill_caps_at_capacity(self, store: BufferStore) -> None:
        buf = store.create_buffer("Rent", 4, 6, 30, date(2026, 5, 1), 1)
        result = store.refill(buf.id, 100)
        assert result.buffer_level == 6

    def test_refill_persists(
        self, store: BufferStore, storage_path: Path
    ) -> None:
        buf = store.create_buffer("Rent", 1, 6, 30, date(2026, 5, 1), 1)
        store.refill(buf.id, 2)
        fresh = BufferStore(storage_path)
        assert fresh.get_buffer(buf.id).buffer_level == 3

    def test_refill_zero_units_raises(self, store: BufferStore) -> None:
        buf = store.create_buffer("Rent", 2, 6, 30, date(2026, 5, 1), 1)
        with pytest.raises(ValueError, match="units must be at least 1"):
            store.refill(buf.id, 0)

    def test_refill_nonexistent_raises(self, store: BufferStore) -> None:
        with pytest.raises(KeyError, match="Buffer not found"):
            store.refill("fake-id", 1)


# ---------------------------------------------------------------------------
# Delete tests
# ---------------------------------------------------------------------------

class TestBufferStoreDelete:
    def test_delete_removes_buffer(self, store: BufferStore) -> None:
        buf = store.create_buffer("Delete me", 2, 4, 7, date(2026, 5, 1), 0)
        deleted = store.delete_buffer(buf.id)
        assert deleted.id == buf.id
        assert len(store.list_buffers()) == 0

    def test_delete_nonexistent_raises(self, store: BufferStore) -> None:
        with pytest.raises(KeyError, match="Cannot delete"):
            store.delete_buffer("fake-id")

    def test_delete_persists(
        self, store: BufferStore, storage_path: Path
    ) -> None:
        buf = store.create_buffer("Gone soon", 2, 4, 7, date(2026, 5, 1), 0)
        store.delete_buffer(buf.id)
        fresh = BufferStore(storage_path)
        assert len(fresh.list_buffers()) == 0


# ---------------------------------------------------------------------------
# Persistence round-trip tests
# ---------------------------------------------------------------------------

class TestPersistenceRoundTrip:
    def test_buffers_survive_restart(
        self, store: BufferStore, storage_path: Path
    ) -> None:
        store.create_buffer("Rent", 3, 6, 30, date(2026, 5, 1), 1)
        fresh = BufferStore(storage_path)
        buffers = fresh.list_buffers()
        assert len(buffers) == 1
        assert buffers[0].name == "Rent"
        assert buffers[0].buffer_level == 3
        assert buffers[0].next_due_date == date(2026, 5, 1)

    def test_empty_store_initializes_cleanly(
        self, storage_path: Path
    ) -> None:
        store = BufferStore(storage_path)
        assert store.list_buffers() == []

    def test_multiple_buffers_round_trip(
        self, store: BufferStore, storage_path: Path
    ) -> None:
        store.create_buffer("A", 1, 3, 7, date(2026, 5, 1), 0)
        store.create_buffer("B", 2, 4, 14, date(2026, 5, 8), 1)
        store.create_buffer("C", 3, 6, 30, date(2026, 5, 15), 2)
        fresh = BufferStore(storage_path)
        assert len(fresh.list_buffers()) == 3

    def test_reload_picks_up_external_changes(
        self, store: BufferStore, storage_path: Path
    ) -> None:
        store.create_buffer("Original", 2, 4, 7, date(2026, 5, 1), 0)
        other = BufferStore(storage_path)
        other.create_buffer("External", 1, 3, 14, date(2026, 5, 8), 0)
        store.reload()
        assert len(store.list_buffers()) == 2

    def test_decrement_survives_restart(
        self, store: BufferStore, storage_path: Path
    ) -> None:
        buf = store.create_buffer("Rent", 3, 6, 30, date(2026, 5, 1), 1)
        store.decrement(buf.id)
        fresh = BufferStore(storage_path)
        reloaded = fresh.get_buffer(buf.id)
        assert reloaded.buffer_level == 2
        assert reloaded.next_due_date == date(2026, 5, 31)
