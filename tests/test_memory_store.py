"""Tests for MemoryEntryStore CRUD operations and persistence."""

from pathlib import Path

import pytest

from memory_store import MemoryEntryStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def storage_path(tmp_path: Path) -> Path:
    return tmp_path / "memory_entries.json"


@pytest.fixture()
def store(storage_path: Path) -> MemoryEntryStore:
    return MemoryEntryStore(storage_path)


# ---------------------------------------------------------------------------
# Create tests
# ---------------------------------------------------------------------------

class TestMemoryStoreCreate:
    """Verify entry creation through MemoryEntryStore."""

    def test_create_returns_entry(self, store: MemoryEntryStore) -> None:
        entry = store.create_entry("commitment", "Will do X", {})
        assert entry.category == "commitment"
        assert entry.content == "Will do X"
        assert entry.resolved_at is None

    def test_create_persists_to_disk(
        self, store: MemoryEntryStore, storage_path: Path,
    ) -> None:
        store.create_entry("deadline", "Due Friday", {"due_date": "2026-04-11"})
        assert storage_path.exists()

    def test_create_multiple_entries(self, store: MemoryEntryStore) -> None:
        store.create_entry("commitment", "A", {})
        store.create_entry("blocker", "B", {})
        store.create_entry("energy_state", "C", {})
        assert len(store.list_entries()) == 3

    def test_create_with_metadata(self, store: MemoryEntryStore) -> None:
        entry = store.create_entry(
            "deadline", "Report", {"due_date": "2026-04-15"},
        )
        assert entry.metadata == {"due_date": "2026-04-15"}


# ---------------------------------------------------------------------------
# Get tests
# ---------------------------------------------------------------------------

class TestMemoryStoreGet:
    """Verify get_entry retrieval."""

    def test_get_existing_entry(self, store: MemoryEntryStore) -> None:
        created = store.create_entry("blocker", "Stuck on API", {})
        found = store.get_entry(created.id)
        assert found.content == "Stuck on API"

    def test_get_nonexistent_raises(self, store: MemoryEntryStore) -> None:
        with pytest.raises(KeyError, match="Memory entry not found"):
            store.get_entry("nonexistent-id")


# ---------------------------------------------------------------------------
# List tests
# ---------------------------------------------------------------------------

class TestMemoryStoreList:
    """Verify list operations."""

    def test_list_empty_store(self, store: MemoryEntryStore) -> None:
        assert store.list_entries() == []

    def test_list_active_excludes_resolved(
        self, store: MemoryEntryStore,
    ) -> None:
        entry_a = store.create_entry("commitment", "Active", {})
        entry_b = store.create_entry("commitment", "Resolved", {})
        store.resolve_entry(entry_b.id)

        active = store.list_active_entries()
        assert len(active) == 1
        assert active[0].id == entry_a.id

    def test_list_active_on_empty_store(self, store: MemoryEntryStore) -> None:
        assert store.list_active_entries() == []

    def test_list_by_category(self, store: MemoryEntryStore) -> None:
        store.create_entry("commitment", "C1", {})
        store.create_entry("deadline", "D1", {})
        store.create_entry("commitment", "C2", {})

        commitments = store.list_entries_by_category("commitment")
        deadlines = store.list_entries_by_category("deadline")
        assert len(commitments) == 2
        assert len(deadlines) == 1

    def test_list_by_category_excludes_resolved(
        self, store: MemoryEntryStore,
    ) -> None:
        entry = store.create_entry("blocker", "Blocked", {})
        store.resolve_entry(entry.id)
        assert store.list_entries_by_category("blocker") == []

    def test_list_by_category_no_entries(
        self, store: MemoryEntryStore,
    ) -> None:
        assert store.list_entries_by_category("energy_state") == []

    def test_list_entries_includes_resolved(
        self, store: MemoryEntryStore,
    ) -> None:
        entry = store.create_entry("commitment", "Will resolve", {})
        store.resolve_entry(entry.id)
        all_entries = store.list_entries()
        assert len(all_entries) == 1
        assert all_entries[0].resolved_at is not None


# ---------------------------------------------------------------------------
# Resolve tests
# ---------------------------------------------------------------------------

class TestMemoryStoreResolve:
    """Verify resolve_entry soft-delete behavior."""

    def test_resolve_sets_resolved_at(self, store: MemoryEntryStore) -> None:
        entry = store.create_entry("commitment", "Done now", {})
        resolved = store.resolve_entry(entry.id)
        assert resolved.resolved_at is not None

    def test_resolve_nonexistent_raises(
        self, store: MemoryEntryStore,
    ) -> None:
        with pytest.raises(KeyError, match="Memory entry not found"):
            store.resolve_entry("fake-id")

    def test_resolve_is_idempotent(self, store: MemoryEntryStore) -> None:
        entry = store.create_entry("blocker", "Resolved twice", {})
        first = store.resolve_entry(entry.id)
        second = store.resolve_entry(entry.id)
        assert second.resolved_at is not None
        assert second.resolved_at >= first.resolved_at

    def test_resolve_persists(
        self, store: MemoryEntryStore, storage_path: Path,
    ) -> None:
        entry = store.create_entry("deadline", "Persisted resolve", {})
        store.resolve_entry(entry.id)
        fresh = MemoryEntryStore(storage_path)
        reloaded = fresh.get_entry(entry.id)
        assert reloaded.resolved_at is not None


# ---------------------------------------------------------------------------
# Persistence round-trip tests
# ---------------------------------------------------------------------------

class TestPersistenceRoundTrip:
    """Verify data survives a simulated restart."""

    def test_entries_survive_restart(
        self, store: MemoryEntryStore, storage_path: Path,
    ) -> None:
        store.create_entry(
            "commitment", "Survive this", {"context": "meeting"},
        )
        fresh = MemoryEntryStore(storage_path)
        entries = fresh.list_entries()
        assert len(entries) == 1
        assert entries[0].content == "Survive this"
        assert entries[0].metadata == {"context": "meeting"}

    def test_empty_store_initializes_cleanly(
        self, storage_path: Path,
    ) -> None:
        store = MemoryEntryStore(storage_path)
        assert store.list_entries() == []

    def test_multiple_entries_round_trip(
        self, store: MemoryEntryStore, storage_path: Path,
    ) -> None:
        store.create_entry("commitment", "A", {})
        store.create_entry("deadline", "B", {})
        store.create_entry("blocker", "C", {})
        fresh = MemoryEntryStore(storage_path)
        assert len(fresh.list_entries()) == 3

    def test_reload_picks_up_external_changes(
        self, store: MemoryEntryStore, storage_path: Path,
    ) -> None:
        store.create_entry("commitment", "Original", {})
        other = MemoryEntryStore(storage_path)
        other.create_entry("deadline", "External", {})
        store.reload()
        assert len(store.list_entries()) == 2

    def test_all_categories_round_trip(
        self, store: MemoryEntryStore, storage_path: Path,
    ) -> None:
        categories = [
            "commitment", "deadline", "blocker", "energy_state", "context_switch",
        ]
        for cat in categories:
            store.create_entry(cat, f"test {cat}", {})
        fresh = MemoryEntryStore(storage_path)
        assert len(fresh.list_entries()) == 5
        restored_cats = {e.category for e in fresh.list_entries()}
        assert restored_cats == set(categories)
