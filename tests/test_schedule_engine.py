"""Tests for state-aware scheduling logic — evaluation matrix, sorting, filtering, context assembly."""

from datetime import date, datetime, time, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from checkin_schedule import CheckInType
from memory_store import MemoryEntry, MemoryEntryStore
from schedule_engine import (
    CheckInContext,
    ScheduleAction,
    assemble_checkin_context,
    evaluate_checkin,
    filter_overdue_tasks,
    filter_tasks_completed_today,
    sort_tasks_by_priority,
)
from state_detection import StateName
from task_store import Task, TaskStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(
    title: str,
    status: str,
    priority: str,
    due_date: datetime | None,
    updated_at: datetime | None,
) -> Task:
    """Build a Task with minimal required fields for testing."""
    now = updated_at or datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc)
    return Task(
        id=title.lower().replace(" ", "_"),
        title=title,
        status=status,  # type: ignore[arg-type]
        priority=priority,  # type: ignore[arg-type]
        created_at=now,
        updated_at=now,
        due_date=due_date,
    )


def _make_memory(
    category: str,
    content: str,
) -> MemoryEntry:
    """Build a MemoryEntry for testing."""
    return MemoryEntry(
        id=content.lower().replace(" ", "_")[:16],
        category=category,  # type: ignore[arg-type]
        content=content,
        created_at=datetime(2026, 4, 10, 8, 0, tzinfo=timezone.utc),
    )


# ---------------------------------------------------------------------------
# ScheduleAction model tests
# ---------------------------------------------------------------------------

class TestScheduleAction:
    def test_fire_action(self) -> None:
        action = ScheduleAction(action="fire", reason="test")
        assert action.action == "fire"
        assert action.modified_scope is None

    def test_modify_action_with_scope(self) -> None:
        action = ScheduleAction(
            action="modify", reason="test", modified_scope="reduced",
        )
        assert action.modified_scope == "reduced"

    def test_rejects_invalid_action(self) -> None:
        with pytest.raises(ValueError):
            ScheduleAction(action="explode", reason="bad")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Evaluate check-in — baseline and focus (fire everything)
# ---------------------------------------------------------------------------

ALL_CHECKIN_TYPES: list[CheckInType] = [
    "morning_motivation", "morning_plan", "afternoon_check", "evening_review",
]


class TestEvaluateBaselineFocus:
    @pytest.mark.parametrize("state", ["baseline", "focus"])
    @pytest.mark.parametrize("checkin_type", ALL_CHECKIN_TYPES)
    def test_fires_all_checkins(
        self, state: StateName, checkin_type: CheckInType,
    ) -> None:
        result = evaluate_checkin(checkin_type, state)
        assert result.action == "fire"


# ---------------------------------------------------------------------------
# Evaluate check-in — hyperfocus
# ---------------------------------------------------------------------------

class TestEvaluateHyperfocus:
    @pytest.mark.parametrize("checkin_type", [
        "morning_motivation", "morning_plan", "afternoon_check",
    ])
    def test_suppresses_non_critical(self, checkin_type: CheckInType) -> None:
        result = evaluate_checkin(checkin_type, "hyperfocus")
        assert result.action == "suppress"

    def test_fires_evening_review(self) -> None:
        result = evaluate_checkin("evening_review", "hyperfocus")
        assert result.action == "fire"


# ---------------------------------------------------------------------------
# Evaluate check-in — avoidance
# ---------------------------------------------------------------------------

class TestEvaluateAvoidance:
    def test_fires_morning_motivation_with_icnu(self) -> None:
        result = evaluate_checkin("morning_motivation", "avoidance")
        assert result.action == "fire"
        assert "ICNU" in result.reason

    def test_fires_evening_review(self) -> None:
        result = evaluate_checkin("evening_review", "avoidance")
        assert result.action == "fire"

    @pytest.mark.parametrize("checkin_type", [
        "morning_plan", "afternoon_check",
    ])
    def test_modifies_task_checkins(self, checkin_type: CheckInType) -> None:
        result = evaluate_checkin(checkin_type, "avoidance")
        assert result.action == "modify"
        assert result.modified_scope == "reduced"


# ---------------------------------------------------------------------------
# Evaluate check-in — overwhelm
# ---------------------------------------------------------------------------

class TestEvaluateOverwhelm:
    def test_fires_morning_motivation(self) -> None:
        result = evaluate_checkin("morning_motivation", "overwhelm")
        assert result.action == "fire"

    @pytest.mark.parametrize("checkin_type", [
        "morning_plan", "afternoon_check", "evening_review",
    ])
    def test_modifies_to_single_item(self, checkin_type: CheckInType) -> None:
        result = evaluate_checkin(checkin_type, "overwhelm")
        assert result.action == "modify"
        assert result.modified_scope == "single_item"


# ---------------------------------------------------------------------------
# Evaluate check-in — RSD
# ---------------------------------------------------------------------------

class TestEvaluateRsd:
    def test_fires_morning_motivation(self) -> None:
        result = evaluate_checkin("morning_motivation", "rsd")
        assert result.action == "fire"
        assert "emotional" in result.reason

    @pytest.mark.parametrize("checkin_type", [
        "morning_plan", "afternoon_check", "evening_review",
    ])
    def test_suppresses_task_checkins(self, checkin_type: CheckInType) -> None:
        result = evaluate_checkin(checkin_type, "rsd")
        assert result.action == "suppress"


# ---------------------------------------------------------------------------
# sort_tasks_by_priority
# ---------------------------------------------------------------------------

class TestSortTasksByPriority:
    def test_sorts_high_before_low(self) -> None:
        low = _make_task("Low", "pending", "low", None, None)
        high = _make_task("High", "pending", "high", None, None)
        result = sort_tasks_by_priority([low, high])
        assert result[0].priority == "high"
        assert result[1].priority == "low"

    def test_due_date_sorts_before_no_due_date(self) -> None:
        no_due = _make_task("NoDue", "pending", "high", None, None)
        has_due = _make_task(
            "HasDue", "pending", "high",
            datetime(2026, 4, 15, tzinfo=timezone.utc), None,
        )
        result = sort_tasks_by_priority([no_due, has_due])
        assert result[0].title == "HasDue"
        assert result[1].title == "NoDue"

    def test_earlier_due_date_first(self) -> None:
        later = _make_task(
            "Later", "pending", "medium",
            datetime(2026, 5, 1, tzinfo=timezone.utc), None,
        )
        earlier = _make_task(
            "Earlier", "pending", "medium",
            datetime(2026, 4, 12, tzinfo=timezone.utc), None,
        )
        result = sort_tasks_by_priority([later, earlier])
        assert result[0].title == "Earlier"

    def test_empty_list(self) -> None:
        assert sort_tasks_by_priority([]) == []

    def test_preserves_all_tasks(self) -> None:
        tasks = [
            _make_task("A", "pending", "low", None, None),
            _make_task("B", "pending", "high", None, None),
            _make_task("C", "pending", "medium", None, None),
        ]
        result = sort_tasks_by_priority(tasks)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# filter_tasks_completed_today
# ---------------------------------------------------------------------------

class TestFilterTasksCompletedToday:
    def test_includes_tasks_updated_today(self) -> None:
        today = date(2026, 4, 10)
        task = _make_task(
            "Done", "done", "medium", None,
            datetime(2026, 4, 10, 15, 30, tzinfo=timezone.utc),
        )
        assert filter_tasks_completed_today([task], today) == [task]

    def test_excludes_tasks_updated_yesterday(self) -> None:
        today = date(2026, 4, 10)
        task = _make_task(
            "Old", "done", "medium", None,
            datetime(2026, 4, 9, 23, 0, tzinfo=timezone.utc),
        )
        assert filter_tasks_completed_today([task], today) == []

    def test_empty_list(self) -> None:
        assert filter_tasks_completed_today([], date(2026, 4, 10)) == []


# ---------------------------------------------------------------------------
# filter_overdue_tasks
# ---------------------------------------------------------------------------

class TestFilterOverdueTasks:
    def test_includes_past_due(self) -> None:
        today = date(2026, 4, 10)
        task = _make_task(
            "Late", "pending", "high",
            datetime(2026, 4, 8, tzinfo=timezone.utc), None,
        )
        result = filter_overdue_tasks([task], today)
        assert len(result) == 1

    def test_excludes_future_due(self) -> None:
        today = date(2026, 4, 10)
        task = _make_task(
            "Future", "pending", "high",
            datetime(2026, 4, 15, tzinfo=timezone.utc), None,
        )
        assert filter_overdue_tasks([task], today) == []

    def test_excludes_no_due_date(self) -> None:
        today = date(2026, 4, 10)
        task = _make_task("NoDue", "pending", "high", None, None)
        assert filter_overdue_tasks([task], today) == []

    def test_excludes_due_today(self) -> None:
        today = date(2026, 4, 10)
        task = _make_task(
            "Today", "pending", "high",
            datetime(2026, 4, 10, tzinfo=timezone.utc), None,
        )
        assert filter_overdue_tasks([task], today) == []


# ---------------------------------------------------------------------------
# assemble_checkin_context
# ---------------------------------------------------------------------------

class TestAssembleCheckinContext:
    def _make_task_store(self, tmp_path: Path) -> TaskStore:
        store = TaskStore(tmp_path / "tasks.json")
        store.create_task("High Task", "high", None, None, [])
        store.create_task("Low Task", "low", None, None, [])
        return store

    def _make_memory_store(self, tmp_path: Path) -> MemoryEntryStore:
        store = MemoryEntryStore(tmp_path / "memories.json")
        store.create_entry("deadline", "Report due Friday", {})
        store.create_entry("energy_state", "Feeling tired", {})
        return store

    def test_morning_motivation_has_no_data(self, tmp_path: Path) -> None:
        task_store = TaskStore(tmp_path / "tasks.json")
        mem_store = MemoryEntryStore(tmp_path / "memories.json")
        ctx = assemble_checkin_context(
            "morning_motivation", task_store, mem_store, date(2026, 4, 10),
        )
        assert ctx.checkin_type == "morning_motivation"
        assert ctx.pending_tasks == []
        assert ctx.in_progress_tasks == []

    def test_morning_plan_has_sorted_pending_and_deadlines(
        self, tmp_path: Path,
    ) -> None:
        task_store = self._make_task_store(tmp_path)
        mem_store = self._make_memory_store(tmp_path)
        ctx = assemble_checkin_context(
            "morning_plan", task_store, mem_store, date(2026, 4, 10),
        )
        assert ctx.checkin_type == "morning_plan"
        assert len(ctx.pending_tasks) == 2
        assert ctx.pending_tasks[0].priority == "high"
        assert len(ctx.deadline_memories) == 1

    def test_afternoon_check_has_in_progress_and_energy(
        self, tmp_path: Path,
    ) -> None:
        task_store = TaskStore(tmp_path / "tasks.json")
        task = task_store.create_task("Active", "high", None, None, [])
        from task_store import TaskUpdate
        task_store.update_task(task.id, TaskUpdate(status="in_progress"))
        mem_store = self._make_memory_store(tmp_path)
        ctx = assemble_checkin_context(
            "afternoon_check", task_store, mem_store, date(2026, 4, 10),
        )
        assert ctx.checkin_type == "afternoon_check"
        assert len(ctx.in_progress_tasks) == 1
        assert len(ctx.energy_memories) == 1

    def test_evening_review_has_completed_and_overdue(
        self, tmp_path: Path,
    ) -> None:
        task_store = TaskStore(tmp_path / "tasks.json")
        task = task_store.create_task("Finished", "medium", None, None, [])
        task_store.mark_complete(task.id)
        overdue_task = task_store.create_task(
            "Overdue", "high", None,
            datetime(2026, 4, 8, tzinfo=timezone.utc), [],
        )
        mem_store = MemoryEntryStore(tmp_path / "memories.json")
        today = task_store.get_task(task.id).updated_at.date()
        ctx = assemble_checkin_context(
            "evening_review", task_store, mem_store, today,
        )
        assert ctx.checkin_type == "evening_review"
        assert len(ctx.completed_today_tasks) == 1
        assert len(ctx.overdue_tasks) == 1

    def test_evening_review_excludes_old_completions(
        self, tmp_path: Path,
    ) -> None:
        task_store = TaskStore(tmp_path / "tasks.json")
        task = task_store.create_task("Old", "medium", None, None, [])
        task_store.mark_complete(task.id)
        mem_store = MemoryEntryStore(tmp_path / "memories.json")
        future = date(2026, 12, 25)
        ctx = assemble_checkin_context(
            "evening_review", task_store, mem_store, future,
        )
        assert ctx.completed_today_tasks == []
