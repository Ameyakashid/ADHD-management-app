"""Tests for Task model, pure helpers, and serialization."""

from datetime import datetime, timezone

import pytest

from task_store import (
    ALL_PRIORITIES,
    ALL_STATUSES,
    Task,
    TaskUpdate,
    apply_updates,
    build_task,
    deserialize_tasks,
    serialize_tasks,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_task() -> Task:
    now = datetime.now(timezone.utc)
    return Task(
        id="abc123",
        title="Test task",
        description="A task for testing",
        status="pending",
        priority="medium",
        created_at=now,
        updated_at=now,
        due_date=None,
        tags=["test"],
    )


# ---------------------------------------------------------------------------
# Type constant tests
# ---------------------------------------------------------------------------

class TestTypeConstants:
    """Verify the Literal types match the frozenset constants."""

    def test_all_statuses(self) -> None:
        assert ALL_STATUSES == {"pending", "in_progress", "done"}

    def test_all_priorities(self) -> None:
        assert ALL_PRIORITIES == {"low", "medium", "high"}


# ---------------------------------------------------------------------------
# Task model tests
# ---------------------------------------------------------------------------

class TestTaskModel:
    """Verify Task model validation and serialization."""

    def test_task_round_trip_json(self, sample_task: Task) -> None:
        dumped = sample_task.model_dump(mode="json")
        restored = Task.model_validate(dumped)
        assert restored.id == sample_task.id
        assert restored.title == sample_task.title
        assert restored.status == sample_task.status

    def test_task_rejects_invalid_status(self) -> None:
        with pytest.raises(Exception):
            Task(
                id="x",
                title="bad",
                status="invalid",
                priority="low",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

    def test_task_rejects_invalid_priority(self) -> None:
        with pytest.raises(Exception):
            Task(
                id="x",
                title="bad",
                status="pending",
                priority="critical",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

    def test_task_optional_fields_default(self) -> None:
        now = datetime.now(timezone.utc)
        task = Task(
            id="x",
            title="minimal",
            status="pending",
            priority="low",
            created_at=now,
            updated_at=now,
        )
        assert task.description is None
        assert task.due_date is None
        assert task.tags == []

    def test_datetime_survives_json_round_trip(self, sample_task: Task) -> None:
        dumped = sample_task.model_dump(mode="json")
        restored = Task.model_validate(dumped)
        assert restored.created_at == sample_task.created_at


# ---------------------------------------------------------------------------
# Pure helper tests
# ---------------------------------------------------------------------------

class TestBuildTask:
    """Verify build_task constructs valid tasks."""

    def test_creates_task_with_pending_status(self) -> None:
        task = build_task("Do thing", "high", None, None, [])
        assert task.status == "pending"
        assert task.title == "Do thing"
        assert task.priority == "high"

    def test_generates_unique_ids(self) -> None:
        task_a = build_task("A", "low", None, None, [])
        task_b = build_task("B", "low", None, None, [])
        assert task_a.id != task_b.id

    def test_sets_utc_timestamps(self) -> None:
        task = build_task("T", "medium", None, None, [])
        assert task.created_at.tzinfo is not None
        assert task.updated_at.tzinfo is not None

    def test_defensive_copies_tags(self) -> None:
        original_tags = ["a", "b"]
        task = build_task("T", "low", None, None, original_tags)
        original_tags.append("c")
        assert task.tags == ["a", "b"]

    def test_includes_description_and_due_date(self) -> None:
        due = datetime(2026, 12, 31, tzinfo=timezone.utc)
        task = build_task("T", "high", "desc", due, ["urgent"])
        assert task.description == "desc"
        assert task.due_date == due
        assert task.tags == ["urgent"]


class TestApplyUpdates:
    """Verify apply_updates returns new task with changes applied."""

    def test_updates_title(self, sample_task: Task) -> None:
        updated = apply_updates(sample_task, TaskUpdate(title="New title"))
        assert updated.title == "New title"
        assert updated.id == sample_task.id

    def test_updates_status(self, sample_task: Task) -> None:
        updated = apply_updates(sample_task, TaskUpdate(status="done"))
        assert updated.status == "done"

    def test_preserves_unchanged_fields(self, sample_task: Task) -> None:
        updated = apply_updates(sample_task, TaskUpdate(title="Changed"))
        assert updated.description == sample_task.description
        assert updated.priority == sample_task.priority
        assert updated.tags == sample_task.tags

    def test_does_not_mutate_original(self, sample_task: Task) -> None:
        apply_updates(sample_task, TaskUpdate(title="New"))
        assert sample_task.title == "Test task"

    def test_bumps_updated_at(self, sample_task: Task) -> None:
        updated = apply_updates(sample_task, TaskUpdate(title="New"))
        assert updated.updated_at >= sample_task.updated_at

    def test_no_changes_returns_same_task(self, sample_task: Task) -> None:
        result = apply_updates(sample_task, TaskUpdate())
        assert result is sample_task


class TestSerialization:
    """Verify serialize/deserialize round-trip."""

    def test_round_trip(self, sample_task: Task) -> None:
        tasks = {sample_task.id: sample_task}
        raw = serialize_tasks(tasks)
        restored = deserialize_tasks(raw)
        assert sample_task.id in restored
        assert restored[sample_task.id].title == sample_task.title

    def test_deserialize_rejects_missing_tasks_key(self) -> None:
        with pytest.raises(ValueError, match="top-level 'tasks' key"):
            deserialize_tasks('{"items": []}')

    def test_deserialize_empty_list(self) -> None:
        result = deserialize_tasks('{"tasks": []}')
        assert result == {}
