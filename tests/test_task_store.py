"""Tests for TaskStore CRUD operations and persistence."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from task_store import TaskStore, TaskUpdate


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def storage_path(tmp_path: Path) -> Path:
    return tmp_path / "tasks.json"


@pytest.fixture()
def store(storage_path: Path) -> TaskStore:
    return TaskStore(storage_path)


# ---------------------------------------------------------------------------
# Create tests
# ---------------------------------------------------------------------------

class TestTaskStoreCreate:
    """Verify task creation through TaskStore."""

    def test_create_returns_task(self, store: TaskStore) -> None:
        task = store.create_task("Buy milk", "low", None, None, [])
        assert task.title == "Buy milk"
        assert task.status == "pending"

    def test_create_persists_to_disk(
        self, store: TaskStore, storage_path: Path
    ) -> None:
        store.create_task("Persisted", "medium", None, None, [])
        assert storage_path.exists()

    def test_create_multiple_tasks(self, store: TaskStore) -> None:
        store.create_task("A", "low", None, None, [])
        store.create_task("B", "high", None, None, [])
        assert len(store.list_tasks()) == 2


# ---------------------------------------------------------------------------
# Get tests
# ---------------------------------------------------------------------------

class TestTaskStoreGet:
    """Verify get_task retrieval."""

    def test_get_existing_task(self, store: TaskStore) -> None:
        created = store.create_task("Find me", "low", None, None, [])
        found = store.get_task(created.id)
        assert found.title == "Find me"

    def test_get_nonexistent_raises(self, store: TaskStore) -> None:
        with pytest.raises(KeyError, match="Task not found"):
            store.get_task("nonexistent-id")


# ---------------------------------------------------------------------------
# List tests
# ---------------------------------------------------------------------------

class TestTaskStoreList:
    """Verify list operations."""

    def test_list_empty_store(self, store: TaskStore) -> None:
        assert store.list_tasks() == []

    def test_list_by_status(self, store: TaskStore) -> None:
        store.create_task("Pending", "low", None, None, [])
        task_b = store.create_task("Also pending", "low", None, None, [])
        store.mark_complete(task_b.id)

        pending = store.list_tasks_by_status("pending")
        done = store.list_tasks_by_status("done")
        assert len(pending) == 1
        assert len(done) == 1
        assert pending[0].title == "Pending"
        assert done[0].title == "Also pending"


# ---------------------------------------------------------------------------
# Update tests
# ---------------------------------------------------------------------------

class TestTaskStoreUpdate:
    """Verify update and mark_complete operations."""

    def test_update_changes_fields(self, store: TaskStore) -> None:
        task = store.create_task("Old title", "low", None, None, [])
        updated = store.update_task(task.id, TaskUpdate(title="New title"))
        assert updated.title == "New title"
        assert updated.priority == "low"

    def test_update_nonexistent_raises(self, store: TaskStore) -> None:
        with pytest.raises(KeyError, match="Task not found"):
            store.update_task("fake-id", TaskUpdate(title="x"))

    def test_mark_complete_sets_done(self, store: TaskStore) -> None:
        task = store.create_task("Finish me", "high", None, None, [])
        completed = store.mark_complete(task.id)
        assert completed.status == "done"

    def test_update_bumps_updated_at(self, store: TaskStore) -> None:
        task = store.create_task("Timestamped", "low", None, None, [])
        updated = store.update_task(task.id, TaskUpdate(priority="high"))
        assert updated.updated_at >= task.updated_at


# ---------------------------------------------------------------------------
# Delete tests
# ---------------------------------------------------------------------------

class TestTaskStoreDelete:
    """Verify delete operations."""

    def test_delete_removes_task(self, store: TaskStore) -> None:
        task = store.create_task("Delete me", "low", None, None, [])
        deleted = store.delete_task(task.id)
        assert deleted.id == task.id
        assert len(store.list_tasks()) == 0

    def test_delete_nonexistent_raises(self, store: TaskStore) -> None:
        with pytest.raises(KeyError, match="Cannot delete"):
            store.delete_task("fake-id")

    def test_delete_persists(
        self, store: TaskStore, storage_path: Path
    ) -> None:
        task = store.create_task("Gone soon", "low", None, None, [])
        store.delete_task(task.id)
        fresh = TaskStore(storage_path)
        assert len(fresh.list_tasks()) == 0


# ---------------------------------------------------------------------------
# Persistence round-trip tests
# ---------------------------------------------------------------------------

class TestPersistenceRoundTrip:
    """Verify data survives a simulated restart."""

    def test_tasks_survive_restart(
        self, store: TaskStore, storage_path: Path
    ) -> None:
        due = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
        store.create_task("Survive", "high", "important", due, ["critical"])
        fresh = TaskStore(storage_path)
        tasks = fresh.list_tasks()
        assert len(tasks) == 1
        assert tasks[0].title == "Survive"
        assert tasks[0].description == "important"
        assert tasks[0].due_date == due
        assert tasks[0].tags == ["critical"]

    def test_empty_store_initializes_cleanly(
        self, storage_path: Path
    ) -> None:
        store = TaskStore(storage_path)
        assert store.list_tasks() == []

    def test_multiple_tasks_round_trip(
        self, store: TaskStore, storage_path: Path
    ) -> None:
        store.create_task("A", "low", None, None, ["a"])
        store.create_task("B", "medium", None, None, ["b"])
        store.create_task("C", "high", None, None, ["c"])
        fresh = TaskStore(storage_path)
        assert len(fresh.list_tasks()) == 3

    def test_reload_picks_up_external_changes(
        self, store: TaskStore, storage_path: Path
    ) -> None:
        store.create_task("Original", "low", None, None, [])
        other = TaskStore(storage_path)
        other.create_task("External", "high", None, None, [])
        store.reload()
        assert len(store.list_tasks()) == 2
